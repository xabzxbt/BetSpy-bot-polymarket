"""
BetSpy Data Fetcher — shared data layer for all analytics modules.

Fetches:
  - CLOB price history (timeseries)
  - CoinGecko crypto prices + volatility
  - Market holders (Data API)

All results are cached with TTL to avoid redundant API calls.
"""

import asyncio
import math
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import aiohttp
from aiolimiter import AsyncLimiter
from loguru import logger


# =====================================================================
# Data classes
# =====================================================================

@dataclass
class PricePoint:
    """Single price point in a timeseries."""
    timestamp: int
    price: float


@dataclass
class PriceHistory:
    """Price timeseries for a market."""
    points: List[PricePoint] = field(default_factory=list)
    clob_token_id: str = ""

    @property
    def prices(self) -> List[float]:
        return [p.price for p in self.points]

    @property
    def is_empty(self) -> bool:
        return len(self.points) == 0

    @property
    def latest_price(self) -> float:
        return self.points[-1].price if self.points else 0.0

    def daily_returns(self) -> List[float]:
        """Calculate log returns between consecutive points."""
        p = self.prices
        if len(p) < 2:
            return []
        returns = []
        for i in range(1, len(p)):
            if p[i - 1] > 0 and p[i] > 0:
                returns.append(math.log(p[i] / p[i - 1]))
        return returns

    def volatility(self) -> float:
        """Annualized volatility from daily returns."""
        ret = self.daily_returns()
        if len(ret) < 2:
            return 0.0
        mean = sum(ret) / len(ret)
        variance = sum((r - mean) ** 2 for r in ret) / (len(ret) - 1)
        daily_vol = math.sqrt(variance)
        return daily_vol * math.sqrt(365)

    def recent_volatility(self, n: int = 24) -> float:
        """Volatility from last N points only."""
        if len(self.points) < n + 1:
            return self.volatility()
        recent = self.points[-n:]
        prices = [p.price for p in recent]
        if len(prices) < 2:
            return 0.0
        ret = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0 and prices[i] > 0:
                ret.append(math.log(prices[i] / prices[i - 1]))
        if len(ret) < 2:
            return 0.0
        mean = sum(ret) / len(ret)
        variance = sum((r - mean) ** 2 for r in ret) / (len(ret) - 1)
        return math.sqrt(variance) * math.sqrt(365)


@dataclass
class CryptoData:
    """Crypto asset data from CoinGecko."""
    coin_id: str
    current_price: float
    prices_30d: List[float] = field(default_factory=list)
    mu: float = 0.0       # annualized drift
    sigma: float = 0.0    # annualized volatility

    @property
    def is_valid(self) -> bool:
        return self.current_price > 0 and len(self.prices_30d) >= 7


@dataclass
class HolderInfo:
    """Top holder of a market token."""
    address: str
    size: float
    side: str  # "YES" or "NO"


# =====================================================================
# Simple TTL cache
# =====================================================================

class _Cache:
    def __init__(self, ttl: int = 300):
        self._data: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        if key in self._data and self._expires.get(key, 0) > time.time():
            return self._data[key]
        # Cleanup expired
        if key in self._data:
            del self._data[key]
            del self._expires[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._expires[key] = time.time() + self._ttl

    def clear(self) -> None:
        self._data.clear()
        self._expires.clear()


# =====================================================================
# Fetcher
# =====================================================================

class DataFetcher:
    """
    Centralized data fetcher for analytics modules.
    
    Uses shared aiohttp session with rate limiting.
    Results cached for 5 minutes (price history) and 10 minutes (crypto).
    """

    CLOB_URL = "https://clob.polymarket.com"
    DATA_API_URL = "https://data-api.polymarket.com"
    COINGECKO_URL = "https://api.coingecko.com/api/v3"

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._clob_limiter = AsyncLimiter(30, 60)
        self._cg_limiter = AsyncLimiter(25, 60)  # CoinGecko free: 30/min
        self._price_cache = _Cache(ttl=300)       # 5 min
        self._crypto_cache = _Cache(ttl=600)      # 10 min
        self._holder_cache = _Cache(ttl=600)      # 10 min

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            connector = aiohttp.TCPConnector(limit=10)
            self._session = aiohttp.ClientSession(
                timeout=timeout, connector=connector,
            )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _get(self, url: str, params: Dict = None,
                   limiter: AsyncLimiter = None) -> Optional[Any]:
        await self._ensure_session()
        _limiter = limiter or self._clob_limiter
        async with _limiter:
            try:
                async with self._session.get(url, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:
                        logger.warning(f"Rate limited: {url}")
                        await asyncio.sleep(3)
                        return None
                    else:
                        logger.warning(f"HTTP {resp.status}: {url}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"Timeout: {url}")
                return None
            except Exception as e:
                logger.error(f"Fetch error: {e}")
                return None

    # -----------------------------------------------------------------
    # CLOB Price History
    # -----------------------------------------------------------------

    async def fetch_price_history(
        self,
        clob_token_id: str,
        interval: str = "1w",
        fidelity: int = 60,
    ) -> PriceHistory:
        """
        Fetch price timeseries from CLOB API.

        Args:
            clob_token_id: CLOB token ID (from MarketStats.clob_token_ids)
            interval: Time range — "1h", "6h", "1d", "1w", "1m", "max"
            fidelity: Resolution in minutes (60 = hourly points)

        Returns:
            PriceHistory with list of PricePoint
        """
        cache_key = f"ph:{clob_token_id}:{interval}:{fidelity}"
        cached = self._price_cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._get(
            f"{self.CLOB_URL}/prices-history",
            {"market": clob_token_id, "interval": interval, "fidelity": fidelity},
            self._clob_limiter,
        )

        result = PriceHistory(clob_token_id=clob_token_id)

        raw_points = []
        if isinstance(data, dict):
            raw_points = data.get("history", [])
        elif isinstance(data, list):
            raw_points = data

        for pt in raw_points:
            try:
                t = int(pt.get("t", 0))
                p = float(pt.get("p", 0))
                if t > 0 and 0 < p <= 1.0:
                    result.points.append(PricePoint(timestamp=t, price=p))
            except (ValueError, TypeError, AttributeError):
                continue

        # Sort by time
        result.points.sort(key=lambda x: x.timestamp)

        self._price_cache.set(cache_key, result)
        logger.debug(f"Price history: {len(result.points)} points for {clob_token_id[:20]}...")
        return result

    # -----------------------------------------------------------------
    # CoinGecko — crypto prices
    # -----------------------------------------------------------------

    async def fetch_crypto_data(self, coin_id: str) -> Optional[CryptoData]:
        """
        Fetch current price + 30-day history from CoinGecko.

        Args:
            coin_id: CoinGecko coin ID (e.g., "bitcoin", "ethereum", "solana")

        Returns:
            CryptoData with price, 30d history, mu, sigma — or None on failure
        """
        cache_key = f"cg:{coin_id}"
        cached = self._crypto_cache.get(cache_key)
        if cached is not None:
            return cached

        # Fetch 30-day chart
        data = await self._get(
            f"{self.COINGECKO_URL}/coins/{coin_id}/market_chart",
            {"vs_currency": "usd", "days": "30", "interval": "daily"},
            self._cg_limiter,
        )

        if not data or "prices" not in data:
            logger.warning(f"CoinGecko: no data for {coin_id}")
            return None

        prices_raw = data["prices"]  # [[timestamp_ms, price], ...]
        prices = [p[1] for p in prices_raw if len(p) == 2 and p[1] > 0]

        if len(prices) < 7:
            return None

        current_price = prices[-1]

        # Calculate mu (annualized drift) and sigma (annualized vol)
        daily_returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                daily_returns.append(math.log(prices[i] / prices[i - 1]))

        if len(daily_returns) >= 2:
            mu_daily = sum(daily_returns) / len(daily_returns)
            var = sum((r - mu_daily) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            sigma_daily = math.sqrt(var)
            mu = mu_daily * 365
            sigma = sigma_daily * math.sqrt(365)
        else:
            mu = 0.0
            sigma = 0.5  # default high vol

        result = CryptoData(
            coin_id=coin_id,
            current_price=current_price,
            prices_30d=prices,
            mu=mu,
            sigma=sigma,
        )

        self._crypto_cache.set(cache_key, result)
        logger.debug(f"CoinGecko: {coin_id} = ${current_price:.2f}, σ={sigma:.2%}")
        return result

    # -----------------------------------------------------------------
    # Data API — holders
    # -----------------------------------------------------------------

    async def fetch_holders(
        self, condition_id: str, outcome_index: int = 0
    ) -> List[HolderInfo]:
        """
        Fetch top holders for a market token.

        Args:
            condition_id: Market condition ID
            outcome_index: 0=YES, 1=NO

        Returns:
            List of HolderInfo (up to 20)
        """
        cache_key = f"hold:{condition_id}:{outcome_index}"
        cached = self._holder_cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._get(
            f"{self.DATA_API_URL}/holders",
            {"conditionId": condition_id, "outcomeIndex": str(outcome_index)},
            self._clob_limiter,
        )

        holders = []
        if isinstance(data, list):
            for h in data[:20]:
                try:
                    holders.append(HolderInfo(
                        address=h.get("proxyWallet", h.get("address", "")),
                        size=float(h.get("size", 0)),
                        side="YES" if outcome_index == 0 else "NO",
                    ))
                except (ValueError, TypeError):
                    continue

        self._holder_cache.set(cache_key, holders)
        return holders


# Global singleton
data_fetcher = DataFetcher()
