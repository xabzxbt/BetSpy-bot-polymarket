"""
Polymarket API client with exponential backoff and rate limiting.

Uses:
- Data API (positions, activity, trades, user-pnl)
- Gamma API (profiles)
"""

import asyncio
from dataclasses import dataclass
from typing import Optional, List, Any, Dict, Tuple
import time
from datetime import datetime

import aiohttp
from aiolimiter import AsyncLimiter
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from loguru import logger

from config import get_settings, get_referral_link


# =========================
# Dataclasses
# =========================

@dataclass
class Trade:
    """Represents a trade on Polymarket."""
    proxy_wallet: str
    side: str  # BUY or SELL
    size: float
    usdc_size: float
    price: float
    timestamp: int
    condition_id: str
    title: str
    slug: str
    event_slug: str
    outcome: str
    outcome_index: int
    transaction_hash: str
    name: Optional[str] = None
    pseudonym: Optional[str] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Trade":
        """Create Trade from API response dict."""
        return cls(
            proxy_wallet=data.get("proxyWallet", ""),
            side=data.get("side", ""),
            size=float(data.get("size", 0)),
            usdc_size=float(data.get("usdcSize", 0)),
            price=float(data.get("price", 0)),
            timestamp=int(data.get("timestamp", 0)),
            condition_id=data.get("conditionId", ""),
            title=data.get("title", ""),
            slug=data.get("slug", ""),
            event_slug=data.get("eventSlug", ""),
            outcome=data.get("outcome", ""),
            outcome_index=int(data.get("outcomeIndex", 0)),
            transaction_hash=data.get("transactionHash", ""),
            name=data.get("name"),
            pseudonym=data.get("pseudonym"),
        )

    @property
    def market_link(self) -> str:
        """Get link to the market on Polymarket with referral code."""
        return get_referral_link(self.event_slug, self.slug)

    @property
    def formatted_time(self) -> str:
        """Get formatted timestamp."""
        dt = datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%d.%m.%Y %H:%M")


@dataclass
class Position:
    """Represents a position on Polymarket."""
    proxy_wallet: str
    asset: str
    condition_id: str
    size: float
    avg_price: float
    initial_value: float
    current_value: float
    cash_pnl: float
    percent_pnl: float
    realized_pnl: float
    cur_price: float
    title: str
    slug: str
    event_slug: str
    outcome: str
    outcome_index: int
    redeemable: bool = False
    # Enrichment fields (not from /positions API directly)
    holder_lifetime_pnl: float = 0.0
    holder_volume: float = 0.0

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Position":
        """Create Position from API response dict."""
        return cls(
            proxy_wallet=data.get("proxyWallet", ""),
            asset=data.get("asset", ""),
            condition_id=data.get("conditionId", ""),
            size=float(data.get("size", 0)),
            avg_price=float(data.get("avgPrice", 0)),
            initial_value=float(data.get("initialValue", 0)),
            current_value=float(data.get("currentValue", 0)),
            cash_pnl=float(data.get("cashPnl", 0)),
            percent_pnl=float(data.get("percentPnl", 0)),
            realized_pnl=float(data.get("realizedPnl", 0)),
            cur_price=float(data.get("curPrice", 0)),
            title=data.get("title", ""),
            slug=data.get("slug", ""),
            event_slug=data.get("eventSlug", ""),
            outcome=data.get("outcome", ""),
            outcome_index=int(data.get("outcomeIndex", 0)),
            redeemable=data.get("redeemable", False),
            holder_lifetime_pnl=0.0, # Default, will be enriched later
            holder_volume=0.0, # Default, will be enriched later
        )

    @property
    def market_link(self) -> str:
        """Get link to the market on Polymarket with referral code."""
        return get_referral_link(self.event_slug, self.slug)


@dataclass
class Profile:
    """Represents a Polymarket user profile."""
    proxy_wallet: str
    name: Optional[str] = None
    pseudonym: Optional[str] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    display_username_public: bool = False
    pnl: float = 0.0
    volume: float = 0.0

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Profile":
        """Create Profile from API response dict."""
        stats = data.get("stats", {})
        # Try various fields for PnL/Profit
        pnl = float(data.get("pnl", data.get("profit", stats.get("pnl", stats.get("profit", 0.0)))))
        # Try various fields for Volume
        volume = float(data.get("volume", data.get("volumeTraded", stats.get("volume", 0.0))))
        
        return cls(
            proxy_wallet=data.get("proxyWallet", ""),
            name=data.get("name"),
            pseudonym=data.get("pseudonym"),
            bio=data.get("bio"),
            profile_image=data.get("profileImage"),
            display_username_public=data.get("displayUsernamePublic", False),
            pnl=pnl,
            volume=volume
        )

    @property
    def display_name(self) -> Optional[str]:
        """Get the best display name for this profile."""
        if self.display_username_public and self.name:
            return self.name
        if self.pseudonym:
            return self.pseudonym
        return None


@dataclass
class PnLSummary:
    """PnL summary for a wallet."""
    total_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    @property
    def total_pnl(self) -> float:
        return self.unrealized_pnl + self.realized_pnl


# =========================
# Exceptions
# =========================

class RateLimitError(Exception):
    """Raised when API rate limit is hit."""
    pass


class ApiError(Exception):
    """Raised for general API errors."""
    pass


# =========================
# Client
# =========================

class PolymarketApiClient:
    """
    Async client for Polymarket APIs.

    Implements:
    - Exponential backoff for retries
    - Rate limiting to avoid 429 errors
    - Connection pooling via aiohttp
    """

    def __init__(self):
        settings = get_settings()
        self.data_api_url = settings.polymarket_data_api_url
        self.gamma_api_url = settings.polymarket_gamma_api_url
        # окремо: base для user-pnl (USER_PNL_URL у фронті)
        # якщо в конфігу той самий, можна використати data_api_url
        self.user_pnl_base_url = getattr(settings, "polymarket_user_pnl_url", self.data_api_url)

        # Rate limiter: X requests per Y seconds
        self._limiter = AsyncLimiter(
            settings.api_rate_limit_requests,
            settings.api_rate_limit_period_seconds,
        )

        self._profile_cache: Dict[str, Tuple[Profile, float]] = {}
        self._cache_ttl = 1800  # 30 minutes user cache

        self._session: Optional[aiohttp.ClientSession] = None
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    async def __aenter__(self) -> "PolymarketApiClient":
        await self.init()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def init(self) -> None:
        """Initialize the HTTP session."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=self._headers,
            )
            logger.info("Polymarket API client initialized")

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info("Polymarket API client closed")

    # ---------- low-level request ----------

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((RateLimitError, aiohttp.ClientError)),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an HTTP request with rate limiting and retry logic."""
        if not self._session:
            await self.init()

        async with self._limiter:
            logger.debug(f"API Request: {method} {url} params={params}")
            try:
                async with self._session.request(method, url, params=params) as response:
                    if response.status == 429:
                        retry_after = response.headers.get("Retry-After", "60")
                        logger.warning(f"Rate limited. Retry after {retry_after}s")
                        raise RateLimitError(f"Rate limited. Retry after {retry_after}s")

                    if response.status == 404:
                        return None

                    if response.status >= 400:
                        text = await response.text()
                        # Suppress logging for auth/method errors (common with protected endpoints)
                        if response.status in [401, 403, 405]:
                            logger.debug(f"API access denied/method not allowed ({response.status}): {text}")
                        else:
                            logger.error(f"API error {response.status}: {text}")
                        raise ApiError(f"API error {response.status}: {text}")

                    data = await response.json()
                    logger.debug(f"API Response: status={response.status}")
                    return data

            except aiohttp.ClientError as e:
                logger.error(f"HTTP client error: {e}")
                raise

    # =========================
    # Public API methods
    # =========================

    async def get_wallet_activity(
        self,
        wallet_address: str,
        activity_type: str = "TRADE",
        limit: int = 100,
        start_timestamp: Optional[int] = None,
    ) -> List[Trade]:
        """Get on-chain activity for a wallet."""
        url = f"{self.data_api_url}/activity"
        params: Dict[str, Any] = {
            "user": wallet_address.lower(),
            "type": activity_type,
            "limit": limit,
            "sortBy": "TIMESTAMP",
            "sortDirection": "DESC",
        }
        if start_timestamp:
            params["start"] = start_timestamp

        try:
            data = await self._request("GET", url, params)
            if not isinstance(data, list):
                logger.warning(f"Unexpected response format for activity: {type(data)}")
                return []

            trades = [Trade.from_api_response(item) for item in data]
            logger.info(f"Fetched {len(trades)} trades for wallet {wallet_address[:10]}...")
            return trades
        except Exception as e:
            logger.error(f"Failed to get activity for {wallet_address}: {e}")
            return []

    async def get_wallet_trades(
        self,
        wallet_address: str,
        limit: int = 10,
    ) -> List[Trade]:
        """Get recent trades for a wallet."""
        url = f"{self.data_api_url}/trades"
        params = {
            "user": wallet_address.lower(),
            "limit": limit,
        }

        try:
            data = await self._request("GET", url, params)
            if not isinstance(data, list):
                return []

            trades = [Trade.from_api_response(item) for item in data]
            logger.info(f"Fetched {len(trades)} trades for wallet {wallet_address[:10]}...")
            return trades
        except Exception as e:
            logger.error(f"Failed to get trades for {wallet_address}: {e}")
            return []

    async def get_wallet_positions(
        self,
        wallet_address: str,
        limit: int = 100,
    ) -> List[Position]:
        """Get current positions for a wallet."""
        url = f"{self.data_api_url}/positions"
        params = {
            "user": wallet_address.lower(),
            "limit": limit,
            "sizeThreshold": 0.01,  # Show even small positions
            "sortBy": "CURRENT",
            "sortDirection": "DESC",
        }

        try:
            data = await self._request("GET", url, params)
            if not isinstance(data, list):
                return []

            positions = [Position.from_api_response(item) for item in data]
            logger.info(f"Fetched {len(positions)} positions for wallet {wallet_address[:10]}...")
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions for {wallet_address}: {e}")
            return []

    async def get_wallet_pnl(self, wallet_address: str) -> PnLSummary:
        """Get PnL summary for a wallet based on positions."""
        positions = await self.get_wallet_positions(wallet_address)
        summary = PnLSummary()
        for pos in positions:
            summary.total_value += pos.current_value
            summary.unrealized_pnl += pos.cash_pnl
            summary.realized_pnl += pos.realized_pnl
        return summary

    async def get_market_holders(
        self,
        condition_id: str,
        yes_price: float = 0.5,
        no_price: float = 0.5,
        limit: int = 50,
    ) -> Tuple[List[Position], List[Position]]:
        """
        Get market holders split by YES/NO outcome.
        Returns: (yes_positions, no_positions)
        """
        url = f"{self.data_api_url}/holders"
        
        async def _fetch_raw(idx):
            params = {
                "conditionId": condition_id,
                "outcomeIndex": str(idx),
                "limit": limit,
            }
            try:
                resp = await self._request("GET", url, params)
                if isinstance(resp, list): return resp
                if isinstance(resp, dict) and "holders" in resp: return resp["holders"]
                return []
            except Exception:
                return []

        # Fetch YES and NO raw holder lists in parallel
        yes_raw, no_raw = await asyncio.gather(_fetch_raw(0), _fetch_raw(1))
        
        # Combine top holders from both sides for detailed analysis
        # We take top 20 from each side to keep processing load reasonable
        top_yes = yes_raw[:20]
        top_no = no_raw[:20]
        
        yes_positions = []
        no_positions = []
        
        async def _enrich_holder(h_data, expected_side_idx):
            wallet = h_data.get("proxyWallet") or h_data.get("address")
            if not wallet: return None
            
            try:
                # 1. Fetch positions for this wallet
                p_url = f"{self.data_api_url}/positions"
                p_params = {"user": wallet.lower(), "limit": 40}
                pos_data = await self._request("GET", p_url, p_params)
                p_list = pos_data if isinstance(pos_data, list) else []
                
                target_pos = None
                for item in p_list:
                    if item.get("conditionId") == condition_id:
                        # Only accept if it matches the side we are looking for OR any side if we want full classification
                        # But since we are enriching a specific side's top holder, it's safer to just match conditionId
                        target_pos = Position.from_api_response(item)
                        break
                
                if not target_pos:
                    # Fallback: create a dummy position from holder data if we can't find it in /positions 
                    # (sometimes Data API is inconsistent)
                    target_pos = Position(
                        proxy_wallet=wallet, asset="", condition_id=condition_id,
                        size=float(h_data.get("size", 0)), avg_price=0.0,
                        initial_value=0.0, current_value=float(h_data.get("size", 0)) * (yes_price if expected_side_idx == 0 else no_price),
                        cash_pnl=0.0, percent_pnl=0.0, realized_pnl=0.0,
                        cur_price=(yes_price if expected_side_idx == 0 else no_price),
                        title="", slug="", event_slug="", outcome="YES" if expected_side_idx == 0 else "NO",
                        outcome_index=expected_side_idx
                    )

                # 2. Enrich with profile (PnL)
                profile = await self.get_profile(wallet)
                if profile:
                    target_pos.holder_lifetime_pnl = profile.pnl
                    target_pos.holder_volume = profile.volume
                
                return target_pos
            except Exception as e:
                logger.debug(f"Enrichment failed for {wallet}: {e}")
                return None

        # Fetch all details in parallel
        tasks = []
        for h in top_yes: tasks.append(_enrich_holder(h, 0))
        for h in top_no: tasks.append(_enrich_holder(h, 1))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
            if isinstance(res, Position):
                if res.outcome_index == 0:
                    yes_positions.append(res)
                else:
                    no_positions.append(res)
        
        # If we have raw counts but enrichment failed to find them in /positions, 
        # ensure SideStats at least has the correct count for reporting.
        # This is handled by holders_analysis.py using these lists.
        # But we should log the success
        logger.info(f"Holders classified for {condition_id}: YES={len(yes_positions)} (raw:{len(yes_raw)}), NO={len(no_positions)} (raw:{len(no_raw)})")
        
        # If one side is empty but raw had data, it usually means /positions API didn't return that specific market.
        # The fallback dummy position above helps with this.
        
        return yes_positions, no_positions

    async def test_holders_endpoint(self, condition_id: str):
        """Debug method to test /holders endpoint"""
        url = f"{self.data_api_url}/holders"
        params = {"market": condition_id, "limit": 20}
        
        try:
            data = await self._request("GET", url, params)
            logger.info(f"Raw /holders response: {data}")
            return data
        except Exception as e:
            logger.error(f"/holders failed: {e}")
            raise

    async def get_user_pnl_series(self, wallet_address: str, interval: str = "ALL") -> List[Dict[str, Any]]:
        """Get user PnL history series (Frontend API)."""
        # Construct URL similar to frontend: /profit/history
        url = self.user_pnl_base_url
        if "profit/history" not in url:
            url = url.rstrip("/") + "/profit/history"
            
        params = {"user": wallet_address.lower(), "window": interval}
        
        try:
            data = await self._request("GET", url, params=params)
            if isinstance(data, list):
                return data
            return []
        except Exception:
            return []

    async def get_profile(self, wallet_address: str) -> Optional[Profile]:
        """
        Get profile data using Data API instead of Gamma /profiles.
        Uses PnL history or Positions fallback.
        """
        wallet = wallet_address.lower()
        now = time.time()
        
        # Check cache
        cached = self._profile_cache.get(wallet)
        if cached:
            profile, cached_at = cached
            if now - cached_at < self._cache_ttl:
                return profile

        try:
            # 1. Try PnL Series (Best precision for Lifetime PnL)
            series = await self.get_user_pnl_series(wallet, interval="ALL")
            
            if series and len(series) >= 1:
                current_pnl = series[-1].get("p", 0.0)
                
                # Estimate volume from PnL changes
                total_volume = sum(
                    abs(series[i]["p"] - series[i-1]["p"]) 
                    for i in range(1, len(series))
                ) if len(series) > 1 else 0.0
                
                profile = Profile(
                    proxy_wallet=wallet,
                    name=None, pseudonym=None, # Gamma API skipped
                    pnl=float(current_pnl),
                    volume=float(total_volume)
                )
            else:
                # 2. Fallback: Position-based calculation
                positions = await self.get_wallet_positions(wallet)
                total_pnl = sum(pos.realized_pnl for pos in positions)
                total_volume = sum(pos.current_value for pos in positions)
                
                profile = Profile(
                    proxy_wallet=wallet,
                    name=None, pseudonym=None,
                    pnl=total_pnl,
                    volume=total_volume
                )

            # Cache result
            self._profile_cache[wallet] = (profile, now)
            return profile
            
        except Exception as e:
            logger.debug(f"Profile fetch failed for {wallet}: {e}")
            # Return empty profile on failure
            empty = Profile(proxy_wallet=wallet, pnl=0.0, volume=0.0)
            self._profile_cache[wallet] = (empty, now)
            return empty

    async def get_new_trades_for_wallet(
        self,
        wallet_address: str,
        since_timestamp: Optional[int] = None,
    ) -> List[Trade]:
        """Get new trades for a wallet since a given timestamp."""
        trades = await self.get_wallet_activity(
            wallet_address=wallet_address,
            activity_type="TRADE",
            limit=200,  # Increased to avoid missing high frequency trades
            start_timestamp=since_timestamp,
        )

        # Filtering logic moved to scheduler for better control
        if since_timestamp:
            trades = [t for t in trades if t.timestamp >= since_timestamp]

        trades.sort(key=lambda t: t.timestamp)
        return trades

    # =========================
    # USER PnL (як у фронті)
    # =========================

    @staticmethod
    def _interval_to_fidelity(interval: str) -> str:
        """
        Map 1D/1W/1M/ALL -> fidelity, точно як у фронті. [file:29]
        """
        if interval == "1D":
            return "1h"
        if interval == "1W":
            return "3h"
        if interval == "1M":
            return "18h"
        if interval == "ALL":
            return "12h"  # For ALL interval
        return "1d"  # дефолт

    async def get_user_pnl_series(
        self,
        proxy_wallet: str,
        interval: str = "1M",  # "1D" | "1W" | "1M" | "ALL"
    ) -> List[Dict[str, float]]:
        """
        Отримати масив [{t,p}, ...] з /user-pnl, як у фронті. [file:29]
        """
        fidelity = self._interval_to_fidelity(interval)
        
        # Try multiple URL formats and parameter combinations for the user-pnl endpoint
        endpoints_to_try = [
            {
                "url": f"{self.user_pnl_base_url}/user-pnl",
                "params": {
                    "user_address": proxy_wallet,
                    "interval": interval.lower(),  # "1d", "1w", "1m", "all"
                    "fidelity": fidelity,
                }
            },
            {
                "url": f"{self.data_api_url}/user-pnl",
                "params": {
                    "user_address": proxy_wallet,
                    "interval": interval.lower(),
                    "fidelity": fidelity,
                }
            },
            # Alternative parameter format that might be used by frontend
            {
                "url": f"{self.user_pnl_base_url}/user-pnl",
                "params": {
                    "userAddress": proxy_wallet,
                    "interval": interval.lower(),
                    "fidelity": fidelity,
                }
            },
            # Try with different case variations
            {
                "url": f"{self.user_pnl_base_url}/user-pnl",
                "params": {
                    "userAddress": proxy_wallet,
                    "interval": interval,
                    "fidelity": fidelity,
                }
            },
        ]
        
        for endpoint_info in endpoints_to_try:
            url = endpoint_info["url"]
            params = endpoint_info["params"]
            
            try:
                logger.debug(f"Trying PnL endpoint: {url} with params: {params}")
                data = await self._request("GET", url, params)
                
                if data:
                    if isinstance(data, list):
                        series: List[Dict[str, float]] = []
                        for item in data:
                            try:
                                t = int(item["t"])
                                p = float(item["p"])
                                series.append({"t": t, "p": p})
                            except (KeyError, TypeError, ValueError) as e:
                                logger.warning(f"Skipping invalid PnL item {item}: {e}")
                                continue
                        
                        if series:
                            series.sort(key=lambda x: x["t"])
                            logger.info(f"Successfully fetched {len(series)} PnL data points from {url}")
                            return series
                        else:
                            logger.debug(f"Got empty series from {url}")
                    else:
                        logger.debug(f"Got non-list response from {url}: {type(data)}")
                else:
                    logger.debug(f"Got empty response from {url}")
            except ApiError as e:
                if "405" in str(e):
                    logger.warning(f"Method not allowed error for {url}, trying alternatives...")
                else:
                    logger.debug(f"API error for {url}: {e}")
            except Exception as e:
                logger.debug(f"Request failed for {url}: {e}")
                continue  # Try next endpoint
        
        # If all attempts failed, return empty list
        logger.info(f"All PnL endpoint attempts failed for wallet {proxy_wallet}. Will calculate from trade data.")
        return []

    @staticmethod
    def _compute_gain_loss_net(
        points: List[Dict[str, float]],
        interval: str,
    ) -> Dict[str, float]:
        """
        Точна реалізація gain/loss/netTotal з фронтенд-коду. [file:29]
        """
        if not isinstance(points, list) or len(points) < 2:
            return {"gain": 0.0, "loss": 0.0, "netTotal": 0.0}

        gain = 0.0
        loss = 0.0
        net = 0.0

        if interval == "ALL":
            s = points[0].get("p", 0.0) or 0.0
            net = points[-1].get("p", 0.0) or 0.0

            if s > 0:
                gain += s
            elif s < 0:
                loss += abs(s)

            for idx in range(1, len(points)):
                diff = (points[idx]["p"] - points[idx - 1]["p"])
                if diff > 0:
                    gain += diff
                elif diff < 0:
                    loss += abs(diff)
        else:
            s = points[0].get("p", 0.0) or 0.0
            net = (points[-1].get("p", 0.0) or 0.0) - s

            for idx in range(1, len(points)):
                diff = (points[idx]["p"] - points[idx - 1]["p"])
                if diff > 0:
                    gain += diff
                elif diff < 0:
                    loss += abs(diff)

        if gain == 0 and loss == 0:
            if net > 0:
                gain = net
                loss = 0.0
            elif net < 0:
                gain = 0.0
                loss = abs(net)

        return {"gain": gain, "loss": loss, "netTotal": net}

    async def get_detailed_statistics_for_date_range(
        self,
        wallet_address: str,
        days: int,
        proxy_wallet: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Статистика за період у стилі Polymarket:
        - position_value / unrealized_pnl / realized_pnl / total_pnl з /positions
        - gain/loss/netTotal за 1D/1W/1M/ALL на основі /user-pnl (як у фронті)
        """
        from datetime import timedelta
        
        # 1. Портфель зараз
        positions = await self.get_wallet_positions(wallet_address)
        total_position_value = sum(pos.current_value for pos in positions)
        total_unrealized_pnl = sum(pos.cash_pnl for pos in positions)
        total_realized_pnl = sum(pos.realized_pnl for pos in positions)
        total_pnl_now = total_unrealized_pnl + total_realized_pnl

        # 2. Визначаємо інтервал як на UI
        if days <= 1:
            interval = "1D"
        elif days <= 7:
            interval = "1W"
        elif days <= 31:
            interval = "1M"
        else:
            interval = "ALL"

        # Try to get the proxy wallet from profile if not provided
        if not proxy_wallet:
            profile = await self.get_profile(wallet_address)
            if profile and profile.proxy_wallet:
                proxy_wallet = profile.proxy_wallet
            else:
                proxy_wallet = wallet_address.lower()
        
        # Use the proxy wallet for getting PnL series
        series = await self.get_user_pnl_series(proxy_wallet, interval=interval)
        
        # Calculate PnL stats from series if available
        if series and len(series) >= 2:
            pnl_stats = self._compute_gain_loss_net(series, interval=interval)
            gain = pnl_stats["gain"]
            loss = pnl_stats["loss"]
            net_total = pnl_stats["netTotal"]
            logger.info(f"Successfully fetched PnL series for wallet {proxy_wallet}, {len(series)} data points")
        else:
            # If we can't get PnL series from API, start with zero values but try to calculate from trades
            gain = 0.0
            loss = 0.0
            net_total = 0.0
            logger.info(f"Could not fetch PnL series for wallet {proxy_wallet}, will calculate from trade data")

        # Get trades for predictions count in the specific period
        now = datetime.now()
        start_date = now - timedelta(days=days)
        start_ts = int(start_date.timestamp())

        trades = await self.get_wallet_activity(
            wallet_address=wallet_address,
            activity_type="TRADE",
            limit=1000,
            start_timestamp=start_ts,
        )
        
        # Initialize trades_by_condition here to ensure it's always defined
        trades_by_condition: Dict[str, List[Trade]] = {}
        for trade in trades:
            trades_by_condition.setdefault(trade.condition_id, []).append(trade)

        # Calculate from trades if we couldn't get PnL series
        if net_total == 0.0 and gain == 0.0 and loss == 0.0 and len(trades) > 0:
            # Use trade data to calculate period-specific PnL
            # Group trades by condition and calculate PnL using FIFO
            
            total_gain = 0.0
            total_loss = 0.0
            total_net = 0.0
            
            for condition_trades in trades_by_condition.values():
                condition_trades.sort(key=lambda x: x.timestamp)
                open_buys: List[tuple] = []  # (size, price)
                condition_pnl = 0.0
                
                for trade in condition_trades:
                    if trade.side.upper() == "BUY":
                        open_buys.append((trade.size, trade.price))
                    else:  # SELL
                        sell_size = trade.size
                        sell_price = trade.price
                        
                        while sell_size > 0 and open_buys:
                            buy_size, buy_price = open_buys[0]
                            matched = min(sell_size, buy_size)
                            
                            trade_pnl = matched * (sell_price - buy_price)
                            condition_pnl += trade_pnl
                            
                            # Track gain vs loss
                            if trade_pnl > 0:
                                total_gain += trade_pnl
                            else:
                                total_loss += abs(trade_pnl)
                            
                            if buy_size <= sell_size:
                                open_buys.pop(0)
                                sell_size -= buy_size
                            else:
                                open_buys[0] = (buy_size - sell_size, buy_price)
                                sell_size = 0
            
            gain = total_gain
            loss = total_loss
            net_total = total_gain - total_loss  # Net total is gain minus loss
        
        # Find the biggest win from positions
        all_pnls = []
        for pos in positions:
            if pos.cash_pnl > 0:
                all_pnls.append(pos.cash_pnl)
            if pos.realized_pnl > 0:
                all_pnls.append(pos.realized_pnl)
        
        # Also check for biggest win in trades if positions don't have high values
        # Make sure trades_by_condition is always defined
        for condition_trades in trades_by_condition.values():
            condition_trades.sort(key=lambda x: x.timestamp)
            open_buys: List[tuple] = []
            for trade in condition_trades:
                if trade.side.upper() == "BUY":
                    open_buys.append((trade.size, trade.price))
                else:  # SELL
                    sell_size = trade.size
                    sell_price = trade.price
                    
                    while sell_size > 0 and open_buys:
                        buy_size, buy_price = open_buys[0]
                        matched = min(sell_size, buy_size)
                        trade_pnl = matched * (sell_price - buy_price)
                        
                        if trade_pnl > 0:
                            all_pnls.append(trade_pnl)
                        
                        if buy_size <= sell_size:
                            open_buys.pop(0)
                            sell_size -= buy_size
                        else:
                            open_buys[0] = (buy_size - sell_size, buy_price)
                            sell_size = 0
        
        biggest_win = max(all_pnls) if all_pnls else 0.0
        total_predictions = len(trades)

        stats = {
            "position_value": total_position_value,
            "unrealized_pnl": total_unrealized_pnl,
            "realized_pnl": total_realized_pnl,
            "total_pnl": total_pnl_now,
            "gain": gain,
            "loss": loss,
            "net_pnl": net_total,          # це те саме, що Net total на UI
            "period_realized_pnl": net_total,
            "biggest_win": biggest_win,
            "biggest_loss": 0.0,  # Placeholder
            "predictions_count": total_predictions,
            "wins_count": 0,      # Placeholder
            "losses_count": 0,    # Placeholder
            "total_won": 0.0,     # Placeholder
            "total_lost": 0.0,    # Placeholder
            "days": days,
            "interval": interval,
        }

        return stats

    async def debug_wallet_data(self, wallet_address: str) -> Dict[str, Any]:
        """
        Debug method to fetch comprehensive wallet data for troubleshooting.
        """
        # Get profile
        profile = await self.get_profile(wallet_address)
        
        # Get positions
        positions = await self.get_wallet_positions(wallet_address)
        
        # Get trades
        trades = await self.get_wallet_trades(wallet_address, limit=50)
        
        # Get activity
        activity = await self.get_wallet_activity(wallet_address, limit=50)
        
        # Get PnL series for different intervals
        pnl_series_1d = await self.get_user_pnl_series(wallet_address.lower(), interval="1D")
        pnl_series_1w = await self.get_user_pnl_series(wallet_address.lower(), interval="1W")
        pnl_series_1m = await self.get_user_pnl_series(wallet_address.lower(), interval="1M")
        
        # Get proxy wallet if available
        proxy_wallet = wallet_address.lower()
        if profile and hasattr(profile, 'proxy_wallet') and profile.proxy_wallet:
            proxy_wallet = profile.proxy_wallet
        
        # Get PnL series using proxy wallet if available
        proxy_pnl_series_1m = await self.get_user_pnl_series(proxy_wallet, interval="1M")
        
        return {
            'profile': profile,
            'positions_count': len(positions),
            'trades_count': len(trades),
            'activity_count': len(activity),
            'pnl_series_1d_length': len(pnl_series_1d),
            'pnl_series_1w_length': len(pnl_series_1w),
            'pnl_series_1m_length': len(pnl_series_1m),
            'proxy_pnl_series_1m_length': len(proxy_pnl_series_1m),
            'wallet_address': wallet_address,
            'proxy_wallet': proxy_wallet,
            'pnl_series_1m_first': pnl_series_1m[0] if pnl_series_1m else None,
            'pnl_series_1m_last': pnl_series_1m[-1] if pnl_series_1m else None,
            'proxy_pnl_series_1m_first': proxy_pnl_series_1m[0] if proxy_pnl_series_1m else None,
            'proxy_pnl_series_1m_last': proxy_pnl_series_1m[-1] if proxy_pnl_series_1m else None,
        }


# Global client instance
api_client = PolymarketApiClient()
