"""
Polymarket API client for trade notifications.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, List, Any, Dict, Tuple
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
class Profile:
    """Represents a Polymarket user profile."""
    proxy_wallet: str
    name: Optional[str] = None
    pseudonym: Optional[str] = None
    pnl: float = 0.0
    volume: float = 0.0

    @property
    def display_name(self) -> Optional[str]:
        """Get the best display name for this profile."""
        if self.name:
            return self.name
        if self.pseudonym:
            return self.pseudonym
        return None


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
        
        # Rate limiter
        self._limiter = AsyncLimiter(
            settings.api_rate_limit_requests,
            settings.api_rate_limit_period_seconds,
        )
        
        self._profile_cache: Dict[str, Tuple[Profile, float]] = {}
        self._cache_ttl = 1800  # 30 minutes
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
            # Convert params to string
            safe_params = None
            if params:
                safe_params = {}
                for k, v in params.items():
                    if isinstance(v, bool):
                        safe_params[k] = str(v).lower()
                    else:
                        safe_params[k] = str(v)

            logger.debug(f"API Request: {method} {url} params={safe_params}")
            try:
                async with self._session.request(method, url, params=safe_params) as response:
                    if response.status == 429:
                        retry_after = response.headers.get("Retry-After", "60")
                        logger.warning(f"Rate limited. Retry after {retry_after}s")
                        raise RateLimitError(f"Rate limited. Retry after {retry_after}s")

                    if response.status == 404:
                        return None

                    if response.status >= 400:
                        text = await response.text()
                        if response.status in [401, 403, 405]:
                            logger.debug(f"API access denied ({response.status}): {text}")
                        else:
                            logger.error(f"API error {response.status}: {text}")
                        raise ApiError(f"API error {response.status}: {text}")

                    data = await response.json()
                    logger.debug(f"API Response: status={response.status}")
                    return data

            except aiohttp.ClientError as e:
                logger.error(f"HTTP client error: {e}")
                raise

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

    async def get_new_trades_for_wallet(
        self,
        wallet_address: str,
        since_timestamp: Optional[int] = None,
    ) -> List[Trade]:
        """Get new trades for a wallet since a given timestamp."""
        trades = await self.get_wallet_activity(
            wallet_address=wallet_address,
            activity_type="TRADE",
            limit=200,
            start_timestamp=since_timestamp,
        )

        if since_timestamp:
            trades = [t for t in trades if t.timestamp >= since_timestamp]

        trades.sort(key=lambda t: t.timestamp)
        return trades

    async def get_profile(self, wallet_address: str) -> Optional[Profile]:
        """Get basic profile info for a wallet (cached)."""
        wallet = wallet_address.lower()
        now = time.time()
        
        # Check cache
        cached = self._profile_cache.get(wallet)
        if cached:
            profile, cached_at = cached
            if now - cached_at < self._cache_ttl:
                return profile

        try:
            # Simple profile with just name/pseudonym
            # In production, you might call gamma API or extract from trades
            profile = Profile(
                proxy_wallet=wallet,
                name=None,
                pseudonym=None,
                pnl=0.0,
                volume=0.0,
            )
            
            # Cache result
            self._profile_cache[wallet] = (profile, now)
            return profile
            
        except Exception as e:
            logger.debug(f"Profile fetch failed for {wallet}: {e}")
            empty = Profile(proxy_wallet=wallet)
            self._profile_cache[wallet] = (empty, now)
            return empty


# Global client instance
api_client = PolymarketApiClient()
