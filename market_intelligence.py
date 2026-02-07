"""
BetSpy Market Intelligence Engine

Mathematical analysis of Polymarket events for profitable betting signals.
Focuses on short-term events (1 day to 1 month) in Sports, Crypto, and Esports.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

import aiohttp
from aiolimiter import AsyncLimiter
from loguru import logger

try:
    from py_clob_client.client import ClobClient
    CLOB_CLIENT_AVAILABLE = True
except ImportError:
    CLOB_CLIENT_AVAILABLE = False
    logger.warning("py_clob_client not found. Using HTTP fallback for trade data.")

from config import get_settings


class TimeFrame(Enum):
    """Supported time frames for events."""
    TODAY = "today"          # Closes within 24 hours
    DAYS_2 = "2days"         # Closes in 1-2 days
    DAYS_3 = "3days"         # Closes in 2-3 days
    WEEK = "week"            # Closes in 3-7 days
    MONTH = "month"          # Closes in 7-30 days


class Category(Enum):
    """Supported market categories matching Polymarket."""
    POLITICS = "politics"
    SPORTS = "sports"
    POP_CULTURE = "pop-culture"
    BUSINESS = "business"
    CRYPTO = "crypto"
    SCIENCE = "science"
    GAMING = "gaming"
    ENTERTAINMENT = "entertainment"
    WORLD = "world"
    TECH = "tech"
    ALL = "all"


class SignalStrength(Enum):
    """Signal strength levels."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    MODERATE = "moderate"
    WEAK = "weak"
    AVOID = "avoid"
    STRONG_SELL = "strong_sell"


@dataclass
class WhaleAnalysis:
    """Structured analysis of whale activity."""
    yes_volume: float = 0.0
    no_volume: float = 0.0
    yes_count: int = 0
    no_count: int = 0
    total_volume: float = 0.0
    dominance_side: str = "NEUTRAL" # YES, NO, NEUTRAL
    dominance_pct: float = 0.0
    sentiment: str = "NEUTRAL"
    
    # Granular details
    top_trade_size: float = 0.0
    top_trade_side: str = ""
    last_trade_timestamp: int = 0
    last_trade_side: str = ""
    
    # Tier breakdown
    medium_volume: float = 0.0 # $500 - $2000
    large_volume: float = 0.0  # $2000+
    
    # Context
    analysis_duration: float = 0.0 # Seconds covered by the analysis
    
    @property
    def is_significant(self) -> bool:
        return self.total_volume > 1000 # Minimum threshold to show specific analysis

    @property
    def large_whale_share_pct(self) -> float:
        """Percentage of total whale volume that comes from large whales ($2000+)."""
        if self.total_volume > 0:
            return (self.large_volume / self.total_volume) * 100
        return 0.0

    @property
    def duration_text(self) -> str:
        """Formatted string for analysis duration (e.g. 'in last 4h')."""
        if self.analysis_duration <= 0:
            return ""
        if self.analysis_duration < 3600:
            return f"in last {int(self.analysis_duration/60)}m"
        elif self.analysis_duration < 86400:
            return f"in last {int(self.analysis_duration/3600)}h"
        else:
            return f"in last {int(self.analysis_duration/86400)}d"


@dataclass
class MarketStats:
    """Statistics for a single market."""
    condition_id: str
    question: str
    slug: str
    event_slug: str
    
    # Prices
    yes_price: float
    no_price: float
    
    # Volume
    volume_24h: float
    volume_total: float
    volume_change_pct: float  # vs yesterday
    
    # Liquidity
    liquidity: float
    
    # Time
    end_date: datetime
    days_to_close: int
    
    # Category
    category: str
    tags: List[str] = field(default_factory=list)
    
    # Whale analysis
    whale_yes_volume: float = 0.0
    whale_no_volume: float = 0.0
    whale_yes_count: int = 0
    whale_no_count: int = 0
    
    # Retail analysis
    retail_yes_volume: float = 0.0
    retail_no_volume: float = 0.0

    # New Structured Analysis
    whale_analysis: Optional[WhaleAnalysis] = None
    
    # Price history
    price_24h_ago: float = 0.0
    price_7d_ago: float = 0.0
    
    # CLOB token IDs (needed for public trade events API)
    clob_token_ids: List[str] = field(default_factory=list)
    
    # Computed scores
    whale_consensus: Optional[float] = None  # None defines no data
    signal_score: int = 0  # 0-100
    signal_strength: SignalStrength = SignalStrength.AVOID
    recommended_side: str = "NONE"
    
    @property
    def whale_total_volume(self) -> float:
        return self.whale_yes_volume + self.whale_no_volume
    
    @property
    def retail_total_volume(self) -> float:
        return self.retail_yes_volume + self.retail_no_volume
    
    @property
    def price_change_24h(self) -> float:
        if self.price_24h_ago > 0:
            return (self.yes_price - self.price_24h_ago) / self.price_24h_ago
        return 0.0
    
    @property
    def price_change_7d(self) -> float:
        if self.price_7d_ago > 0:
            return (self.yes_price - self.price_7d_ago) / self.price_7d_ago
        return 0.0
    
    @property
    def market_url(self) -> str:
        from config import get_settings
        settings = get_settings()
        base_url = f"https://polymarket.com/event/{self.event_slug}/{self.slug}"
        if settings.polymarket_referral_code:
            return f"{base_url}?via={settings.polymarket_referral_code}"
        return base_url


@dataclass
class BetRecommendation:
    """Final betting recommendation."""
    market: MarketStats
    should_bet: bool
    side: str  # "YES" or "NO"
    confidence: int  # 0-100
    entry_price: float
    target_price: float
    stop_loss_price: float
    risk_reward_ratio: float
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class MarketIntelligenceEngine:
    """
    Engine for analyzing Polymarket events and generating betting signals.
    
    Uses mathematical analysis without AI:
    - Whale consensus tracking
    - Volume momentum analysis
    - Price trend analysis
    - Liquidity scoring
    - Time value assessment
    """
    
    # Whale threshold in USD
    MEDIUM_THRESHOLD = 500
    WHALE_THRESHOLD = 2000 # Considered "Large Whale"
    
    # Minimum volume to consider a market
    
    # Minimum volume to consider a market
    MIN_VOLUME_24H = 10000
    
    # Category tag mappings for all Polymarket categories
    CATEGORY_TAGS = {
        Category.POLITICS: ["politics", "election", "president", "trump", "biden", "congress",
                           "senate", "republican", "democrat", "vote", "poll", "government",
                           "political", "white house", "governor", "legislation"],
        Category.SPORTS: ["sports", "nfl", "nba", "mlb", "nhl", "soccer", "football", 
                         "basketball", "baseball", "hockey", "tennis", "mma", "ufc",
                         "boxing", "golf", "f1", "racing", "olympics", "fifa", "super bowl"],
        Category.POP_CULTURE: ["pop culture", "celebrity", "movie", "film", "music", "grammy",
                               "oscars", "actor", "actress", "singer", "album", "kardashian",
                               "taylor swift", "hollywood", "netflix", "streaming"],
        Category.BUSINESS: ["business", "company", "stock", "market", "ceo", "merger",
                           "acquisition", "ipo", "earnings", "revenue", "apple", "google",
                           "amazon", "microsoft", "tesla", "nasdaq", "dow"],
        Category.CRYPTO: ["crypto", "bitcoin", "btc", "ethereum", "eth", "solana", 
                         "sol", "cryptocurrency", "defi", "nft", "blockchain", "binance",
                         "coinbase", "altcoin", "memecoin", "web3"],
        Category.SCIENCE: ["science", "space", "nasa", "spacex", "climate", "research",
                          "discovery", "mars", "moon", "satellite", "physics", "biology",
                          "medicine", "vaccine", "health", "pandemic"],
        Category.GAMING: ["gaming", "esports", "cs2", "csgo", "dota", "dota2", 
                         "league of legends", "lol", "valorant", "overwatch",
                         "counter-strike", "call of duty", "fortnite", "playstation",
                         "xbox", "nintendo", "twitch", "streamer"],
        Category.ENTERTAINMENT: ["entertainment", "tv", "television", "show", "series",
                                "reality tv", "streaming", "disney", "hbo", "award",
                                "premiere", "finale", "season", "episode"],
        Category.WORLD: ["world", "international", "war", "conflict", "country", "nation",
                        "russia", "ukraine", "china", "europe", "asia", "global",
                        "treaty", "sanctions", "diplomacy", "middle east"],
        Category.TECH: ["tech", "technology", "ai", "artificial intelligence", "openai",
                       "chatgpt", "software", "hardware", "startup", "silicon valley",
                       "iphone", "android", "computer", "internet", "social media"],
    }
    
    def __init__(self):
        self.gamma_api_url = "https://gamma-api.polymarket.com"
        self.data_api_url = "https://data-api.polymarket.com"
        self.clob_api_url = "https://clob.polymarket.com"
        
        # Rate limit: 60 requests per minute
        self._limiter = AsyncLimiter(60, 60)
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Initialize ClobClient for public read methods (get_price, get_last_trade_price)
        # Trade data is fetched via data-api.polymarket.com/trades (no auth needed)
        self.clob_client = None
        settings = get_settings()
        
        if CLOB_CLIENT_AVAILABLE:
            try:
                # Create read-only client for public methods
                self.clob_client = ClobClient(
                    host="https://clob.polymarket.com",
                    chain_id=137,
                )
                logger.info("✅ ClobClient initialized (public read-only mode)")
            except Exception as e:
                logger.error(f"❌ Failed to init ClobClient: {e}")
        else:
            logger.warning("⚠️ py-clob-client not installed. Using HTTP fallback for trade data.")
    
    async def init(self) -> None:
        """Initialize HTTP session."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=20)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )
            logger.info("Market Intelligence Engine initialized")
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _request(self, url: str, params: Dict = None) -> Any:
        """Make HTTP request with rate limiting."""
        if not self._session:
            await self.init()
        
        async with self._limiter:
            try:
                async with self._session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        logger.warning(f"Rate limited, waiting 5 seconds...")
                        await asyncio.sleep(5)
                        return None
                    else:
                        logger.warning(f"API error {response.status}: {url}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"Request timeout: {url}")
                return None
            except Exception as e:
                logger.error(f"Request failed: {e}")
                return None
    
    # ==================== DATA FETCHING ====================
    
    async def fetch_event_markets(self, slug: str, market_slug: Optional[str] = None, skip_long_term_filter: bool = False) -> List[MarketStats]:
        """Fetch markets for a specific event slug, optionally filtering by market slug.
        
        Args:
            slug: Event or market slug
            market_slug: Optional specific market slug to filter
            skip_long_term_filter: If True, don't filter out long-term markets (>35 days)
        """
        logger.info(f"Fetching markets for slug: {slug}, market_slug: {market_slug}")
        
        # Gamma API URL
        url = f"{self.gamma_api_url}/markets"
        
        data = []
        is_event_slug_match = False
        from_embedded_event = False  # Flag to skip strict filtering for embedded markets
        
        # 1. First try: treat as event_slug
        params = {
            "event_slug": slug,
            "active": "true",
            "closed": "false",
        }
        
        data = await self._request(url, params)
        
        # Validate event_slug response
        has_valid_event_match = False
        if data:
            for item in data:
                if item.get("eventSlug") == slug:
                    has_valid_event_match = True
                    break
        
        if not data or not has_valid_event_match:
            # 2. If empty or junk response, try /events endpoint
            if data:
                 logger.info(f"API returned {len(data)} items but none matched event_slug={slug}. Likely trending fallback. Ignoring.")
            
            logger.info(f"Trying /events endpoint for slug: {slug}")
            events_url = f"{self.gamma_api_url}/events"
            events_params = {"slug": slug}
            events_data = await self._request(events_url, events_params)
            
            # /events returns a list of events
            if events_data and len(events_data) > 0:
                # Find the event that matches our slug
                target_event = None
                for event in events_data:
                    if event.get("slug") == slug:
                        target_event = event
                        break
                
                if target_event:
                    # Extract markets from event object if present
                    event_markets = target_event.get("markets", [])
                    if event_markets:
                        logger.info(f"Found {len(event_markets)} markets in event object for slug {slug}")
                        data = event_markets
                        is_event_slug_match = True
                        from_embedded_event = True  # Skip strict filtering
                    else:
                        # Try using condition_id or other identifiers
                        event_id = target_event.get("id")
                        if event_id:
                            logger.info(f"Event found but no markets embedded. Trying markets by event ID: {event_id}")
                            params = {"event_id": event_id, "active": "true", "closed": "false"}
                            data = await self._request(url, params)
                            if data:
                                is_event_slug_match = True
            
            # 3. If still nothing, try as market slug directly
            if not data or len(data) == 0:
                logger.info(f"Trying as market slug: {slug}")
                params = {
                    "slug": slug,
                    "active": "true",
                    "closed": "false",
                }
                data = await self._request(url, params)
                is_event_slug_match = False
        else:
            is_event_slug_match = True
            
        if not data or len(data) == 0:
            logger.warning(f"No markets found for slug {slug}")
            return []
            
        logger.info(f"Found {len(data)} markets for slug {slug}")
        
        markets = []
        for item in data:
            try:
                item_event_slug = item.get("eventSlug", "")
                item_slug = item.get("slug", "")

                # FILTERING LOGIC
                # If we have a market_slug, ONLY return that market
                if market_slug and item_slug != market_slug:
                    continue

                # Skip slug validation if markets came from embedded event object
                # (they are already guaranteed to belong to the correct event)
                if not from_embedded_event:
                    if is_event_slug_match:
                        # Strict check: item must belong to the requested event
                        if item_event_slug != slug:
                            continue
                    else:
                        # Strict check: item must match the requested slug (or its event)
                        if item_slug != slug and item_event_slug != slug and item.get("id") != slug:
                            continue

                market = await self._parse_market(item, skip_long_term_filter=skip_long_term_filter)
                if market:
                    # Enrich with whale data and calculate signals
                    enriched = await self._enrich_market_data(market)
                    self._calculate_signal(enriched)
                    markets.append(enriched)
            except Exception as e:
                logger.error(f"Failed to process market for slug {slug}: {e}")
                continue
                    
        # Sort by volume (liquidity usually correlates with volume)
        markets.sort(key=lambda m: m.volume_24h, reverse=True)
        return markets
    
    async def fetch_trending_markets(
        self,
        category: Category = Category.ALL,
        timeframe: TimeFrame = TimeFrame.WEEK,
        limit: int = 20,
    ) -> List[MarketStats]:
        """
        Fetch trending markets filtered by category and timeframe.
        """
        # Calculate date range based on timeframe
        now = datetime.utcnow()
        
        # More inclusive timeframe ranges
        if timeframe == TimeFrame.TODAY:
            end_before = now + timedelta(days=1, hours=12)  # Include events closing in next 36h
            end_after = now - timedelta(hours=1)  # Include events closing very soon
        elif timeframe == TimeFrame.DAYS_2:
            end_before = now + timedelta(days=3)
            end_after = now
        elif timeframe == TimeFrame.DAYS_3:
            end_before = now + timedelta(days=4)
            end_after = now
        elif timeframe == TimeFrame.WEEK:
            end_before = now + timedelta(days=8)
            end_after = now
        else:  # MONTH
            end_before = now + timedelta(days=35)
            end_after = now
        
        logger.info(f"Fetching markets: category={category.value}, timeframe={timeframe.value}")
        logger.info(f"Date range: {end_after} to {end_before}")
        
        # Fetch markets from Gamma API
        params = {
            "active": "true",
            "closed": "false",
            "limit": 200,  # Fetch more to have better selection
            "order": "volume24hr",
            "ascending": "false",
        }
        
        url = f"{self.gamma_api_url}/markets"
        data = await self._request(url, params)
        
        if not data:
            logger.warning("No data returned from API")
            return []
        
        logger.info(f"API returned {len(data)} markets")
        
        markets = []
        skipped_timeframe = 0
        skipped_category = 0
        skipped_volume = 0
        
        for item in data:
            try:
                market = await self._parse_market(item)
                if market is None:
                    continue
                
                # Filter by timeframe (only for specific timeframes, not ALL)
                if timeframe != TimeFrame.MONTH:  # Month is basically "all"
                    if market.end_date < end_after or market.end_date > end_before:
                        skipped_timeframe += 1
                        continue
                
                # Filter by category
                if category != Category.ALL:
                    if not self._matches_category(market, category):
                        skipped_category += 1
                        continue
                
                # Lower minimum volume for short-term events
                min_vol = self.MIN_VOLUME_24H
                if timeframe in [TimeFrame.TODAY, TimeFrame.DAYS_2, TimeFrame.DAYS_3]:
                    min_vol = 1000  # Lower threshold for short-term
                
                if market.volume_24h < min_vol:
                    skipped_volume += 1
                    continue
                
                markets.append(market)
                
            except Exception as e:
                logger.debug(f"Failed to parse market: {e}")
                continue
        
        logger.info(f"Filtered: {len(markets)} markets passed, skipped: timeframe={skipped_timeframe}, category={skipped_category}, volume={skipped_volume}")
        
        # If no markets found with strict filters, try without timeframe filter
        if len(markets) == 0 and timeframe != TimeFrame.MONTH:
            logger.info("No markets found with timeframe filter, fetching all active markets")
            for item in data[:50]:  # Try first 50
                try:
                    market = await self._parse_market(item)
                    if market is None:
                        continue
                    
                    # Only filter by category if specified
                    if category != Category.ALL:
                        if not self._matches_category(market, category):
                            continue
                    
                    if market.volume_24h >= 1000:  # Very low threshold
                        markets.append(market)
                        
                except Exception as e:
                    continue
            
            logger.info(f"After fallback: {len(markets)} markets")
        
        # Sort by volume and limit
        markets.sort(key=lambda m: m.volume_24h, reverse=True)
        markets = markets[:limit]
        
        # Enrich with whale data and calculate signals
        enriched_markets = []
        for market in markets:
            try:
                enriched = await self._enrich_market_data(market)
                self._calculate_signal(enriched)
                enriched_markets.append(enriched)
            except Exception as e:
                logger.error(f"Failed to enrich market {market.slug}: {e}")
                enriched_markets.append(market)
        
        # Sort by signal score
        enriched_markets.sort(key=lambda m: m.signal_score, reverse=True)
        
        return enriched_markets
    
    async def _parse_market(self, data: Dict, skip_long_term_filter: bool = False) -> Optional[MarketStats]:
        """Parse market data from API response.
        
        Args:
            data: Raw market data from API
            skip_long_term_filter: If True, don't filter out long-term markets
        """
        try:
            # Parse end date
            end_date_str = data.get("endDate") or data.get("end_date_iso")
            if not end_date_str:
                logger.warning(f"Market rejected: no endDate - {data.get('question', 'N/A')[:50]}")
                return None
            
            # Handle various date formats
            try:
                if "T" in end_date_str:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                else:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            except:
                logger.warning(f"Market rejected: date parse error - {data.get('question', 'N/A')[:50]}")
                return None
            
            # Make end_date timezone-naive for comparison
            if end_date.tzinfo is not None:
                end_date = end_date.replace(tzinfo=None)
            
            now = datetime.utcnow()
            if end_date < now:
                logger.warning(f"Market rejected: already closed - {data.get('question', 'N/A')[:50]}")
                return None  # Already closed
            
            days_to_close = (end_date - now).days
            
            # Filter out long-term markets (> 35 days) unless explicitly skipped
            if days_to_close > 35 and not skip_long_term_filter:
                logger.warning(f"Market rejected: long-term ({days_to_close} days) - {data.get('question', 'N/A')[:50]}")
                return None
            
            # Parse prices
            outcomes = data.get("outcomes", ["Yes", "No"])
            outcome_prices = data.get("outcomePrices", [])
            
            if isinstance(outcome_prices, str):
                # Sometimes it's a JSON string
                import json
                outcome_prices = json.loads(outcome_prices)
            
            if len(outcome_prices) >= 2:
                yes_price = float(outcome_prices[0])
                no_price = float(outcome_prices[1])
            else:
                yes_price = 0.5
                no_price = 0.5
            
            # Parse volume
            volume_24h = float(data.get("volume24hr", 0) or 0)
            volume_total = float(data.get("volume", 0) or 0)
            
            # Parse liquidity
            liquidity = float(data.get("liquidity", 0) or 0)
            
            # Parse tags
            tags = data.get("tags", []) or []
            if isinstance(tags, str):
                tags = [tags]
            
            # Parse clobTokenIds (needed for public trade events API)
            clob_token_ids = data.get("clobTokenIds", []) or []
            if isinstance(clob_token_ids, str):
                import json as _json
                try:
                    clob_token_ids = _json.loads(clob_token_ids)
                except:
                    clob_token_ids = []
            
            # Determine category from tags
            category = self._detect_category(tags, data.get("question", ""))
            
            return MarketStats(
                condition_id=data.get("conditionId", ""),
                question=data.get("question", ""),
                slug=data.get("slug", ""),
                event_slug=data.get("eventSlug", data.get("slug", "")),
                yes_price=yes_price,
                no_price=no_price,
                volume_24h=volume_24h,
                volume_total=volume_total,
                volume_change_pct=0.0,
                liquidity=liquidity,
                end_date=end_date,
                days_to_close=days_to_close,
                category=category,
                tags=tags,
                clob_token_ids=clob_token_ids,
            )
            
        except Exception as e:
            logger.debug(f"Error parsing market: {e}")
            return None
    
    def _detect_category(self, tags: List[str], question: str) -> str:
        """Detect market category from tags and question."""
        tags_lower = [t.lower() for t in tags]
        question_lower = question.lower()
        
        for category, keywords in self.CATEGORY_TAGS.items():
            for keyword in keywords:
                if keyword in tags_lower or keyword in question_lower:
                    return category.value
        
        return "other"
    
    def _matches_category(self, market: MarketStats, category: Category) -> bool:
        """Check if market matches the specified category."""
        if category == Category.ALL:
            return True
        
        keywords = self.CATEGORY_TAGS.get(category, [])
        
        # Check tags
        for tag in market.tags:
            if tag.lower() in keywords:
                return True
        
        # Check question
        question_lower = market.question.lower()
        for keyword in keywords:
            if keyword in question_lower:
                return True
        
        return market.category == category.value
    
    async def _enrich_market_data(self, market: MarketStats) -> MarketStats:
        """Enrich market with whale/retail data and price history."""
        
        # Fetch recent trades using PUBLIC API (no auth needed)
        trades = await self._fetch_market_trades_public(market)
        

        
        # Tiers
        medium_vol = 0.0
        large_vol = 0.0
        
        whale_yes_vol = 0.0
        whale_no_vol = 0.0
        whale_yes_count = 0
        whale_no_count = 0
        
        top_trade_size = 0.0
        top_trade_side = ""
        last_trade_ts = 0
        last_trade_side = ""
        
        # Track time range
        min_ts = 0
        max_ts = 0
        
        retail_yes_vol = 0.0
        retail_no_vol = 0.0
        
        for trade in trades:
            # Data API /trades returns: size (token amount), price (per token)
            # USDC value = size * price
            try:
                size = float(trade.get("size", 0) or 0)
                price = float(trade.get("price", 0) or 0)
                amount = size * price  # USDC value of the trade
            except (ValueError, TypeError):
                continue
            
            if amount <= 0:
                continue
            
            side = str(trade.get("side", "")).upper()
            outcome_index = int(trade.get("outcomeIndex", 0) or 0)
            
            # Determine YES or NO direction
            # BUY + outcomeIndex=0 = buying YES tokens = bullish YES
            # BUY + outcomeIndex=1 = buying NO tokens = bullish NO
            # SELL + outcomeIndex=0 = selling YES tokens = bearish YES (bullish NO)
            # SELL + outcomeIndex=1 = selling NO tokens = bearish NO (bullish YES)
            is_yes = (side == "BUY" and outcome_index == 0) or (side == "SELL" and outcome_index == 1)
            
            # Check Tiers
            if amount >= self.MEDIUM_THRESHOLD:
                # It's Smart Money (Medium or Whale)
                if is_yes:
                    whale_yes_vol += amount
                    whale_yes_count += 1
                else:
                    whale_no_vol += amount
                    whale_no_count += 1
                
                # Categorize Tier
                if amount >= self.WHALE_THRESHOLD:
                    large_vol += amount
                else:
                    medium_vol += amount

                # Check for top trade
                if amount > top_trade_size:
                    top_trade_size = amount
                    top_trade_side = "YES" if is_yes else "NO"
                
                # Check for last trade timestamp (max) and first (min)
                ts = int(trade.get("timestamp", 0) or 0)
                if ts > 0:
                    if min_ts == 0 or ts < min_ts:
                        min_ts = ts
                    if ts > max_ts:
                        max_ts = ts
                
                if ts > last_trade_ts:
                    last_trade_ts = ts
                    last_trade_side = "YES" if is_yes else "NO"
            else:
                if is_yes:
                    retail_yes_vol += amount
                else:
                    retail_no_vol += amount
        
        market.whale_yes_volume = whale_yes_vol
        market.whale_no_volume = whale_no_vol
        market.whale_yes_count = whale_yes_count
        market.whale_no_count = whale_no_count
        market.retail_yes_volume = retail_yes_vol
        market.retail_no_volume = retail_no_vol
        
        # Calculate whale consensus
        total_whale = whale_yes_vol + whale_no_vol
        if total_whale > 0:
            market.whale_consensus = whale_yes_vol / total_whale
        else:
            market.whale_consensus = None
        
        # Fetch price history
        price_history = await self._fetch_price_history(market.condition_id)
        if price_history:
            market.price_24h_ago = price_history.get("price_24h", market.yes_price)
            market.price_7d_ago = price_history.get("price_7d", market.yes_price)
        
        # Calculate duration
        duration = max_ts - min_ts if max_ts > min_ts else 0
        
        # Run analysis
        self._analyze_whales(market, top_trade_size, top_trade_side, 
                           last_trade_ts, last_trade_side, 
                           medium_vol, large_vol, duration)
            
        return market

    def _analyze_whales(self, market: MarketStats, 
                       top_size: float = 0, top_side: str = "",
                       last_ts: int = 0, last_side: str = "",
                       med_vol: float = 0, lrg_vol: float = 0,
                       duration: float = 0) -> None:
        """Perform structured whale analysis and populate market.whale_analysis."""
        yes_vol = market.whale_yes_volume
        no_vol = market.whale_no_volume
        total_vol = yes_vol + no_vol
        
        yes_count = market.whale_yes_count
        no_count = market.whale_no_count
        
        analysis = WhaleAnalysis(
            yes_volume=yes_vol,
            no_volume=no_vol,
            yes_count=yes_count,
            no_count=no_count,
            total_volume=total_vol,
            top_trade_size=top_size,
            top_trade_side=top_side,
            last_trade_timestamp=last_ts,
            last_trade_side=last_side,
            medium_volume=med_vol,
            large_volume=lrg_vol,
            analysis_duration=duration
        )
        
        if total_vol > 0:
            yes_pct = (yes_vol / total_vol) * 100
            no_pct = (no_vol / total_vol) * 100
            
            if yes_pct > no_pct:
                analysis.dominance_side = "YES"
                analysis.dominance_pct = yes_pct
            else:
                analysis.dominance_side = "NO"
                analysis.dominance_pct = no_pct
                
            # Determine sentiment
            if analysis.dominance_pct >= 80:
                analysis.sentiment = f"💎 Strong {analysis.dominance_side}"
            elif analysis.dominance_pct >= 60:
                analysis.sentiment = f"bullish {analysis.dominance_side}"
            elif analysis.dominance_pct >= 55:
                analysis.sentiment = f"leaning {analysis.dominance_side}"
            else:
                analysis.sentiment = "Neutral / Mixed"
        else:
            analysis.dominance_side = "NEUTRAL"
            analysis.dominance_pct = 0
            analysis.sentiment = "No Activity"
            
        market.whale_analysis = analysis
    
    async def _fetch_market_trades_public(self, market: MarketStats, limit: int = 500) -> List[Dict]:
        """
        Fetch recent trades for a market using the PUBLIC Data API.
        
        Endpoint: GET https://data-api.polymarket.com/trades
        Params:
          - market: conditionId (0x-prefixed)
          - limit: max 10000
          - takerOnly: true (default)
        
        This is a PUBLIC endpoint. No authentication required.
        Returns: [{proxyWallet, side, size, price, outcomeIndex, outcome, ...}]
        """
        url = f"{self.data_api_url}/trades"
        params = {
            "market": market.condition_id,
            "limit": min(limit, 1500),
        }
        
        data = await self._request(url, params)
        if data and isinstance(data, list):
            return data
        return []
    
    async def _fetch_price_history(self, condition_id: str) -> Dict:
        """Fetch price history for a market using public CLOB timeseries endpoint."""
        # prices-history is a public endpoint, no auth needed
        url = f"{self.clob_api_url}/prices-history"
        params = {
            "market": condition_id,
            "interval": "1d",
            "fidelity": 60,
        }
        
        data = await self._request(url, params)
        
        result = {}
        if data and isinstance(data, dict):
            # API may return {"history": [...]} or direct list
            prices = data.get("history", data) if isinstance(data, dict) else data
            if isinstance(prices, list) and len(prices) > 0:
                if len(prices) >= 24:
                    result["price_24h"] = float(prices[-24].get("p", prices[-24].get("price", 0.5)))
                if len(prices) >= 168:
                    result["price_7d"] = float(prices[-168].get("p", prices[-168].get("price", 0.5)))
        elif data and isinstance(data, list) and len(data) > 0:
            prices = data
            if len(prices) >= 24:
                result["price_24h"] = float(prices[-24].get("p", prices[-24].get("price", 0.5)))
            if len(prices) >= 168:
                result["price_7d"] = float(prices[-168].get("p", prices[-168].get("price", 0.5)))
        
        return result
    
    # ==================== SIGNAL CALCULATION ====================
    
    def _calculate_signal(self, market: MarketStats) -> None:
        """
        Calculate betting signal using mathematical analysis.
        
        Total score: 0-100 points
        - Whale Consensus: 0-40 points
        - Volume Momentum: 0-20 points
        - Price Trend: 0-20 points
        - Liquidity: 0-10 points
        - Time Value: 0-10 points
        """
        scores = {}
        
        # 1. Whale Consensus Score (max 40 points)
        scores["whale"] = self._calc_whale_score(market)
        
        # 2. Volume Momentum Score (max 20 points)
        scores["volume"] = self._calc_volume_score(market)
        
        # 3. Price Trend Score (max 20 points)
        scores["trend"] = self._calc_trend_score(market)
        
        # 4. Liquidity Score (max 10 points)
        scores["liquidity"] = self._calc_liquidity_score(market)
        
        # 5. Time Value Score (max 10 points)
        scores["time"] = self._calc_time_score(market)
        
        # Total score
        total_score = sum(scores.values())
        market.signal_score = int(total_score)
        
        # Determine signal strength and side
        # Logic modified to handle missing whale data
        if market.whale_consensus is not None:
            # Use whale consensus if available
            if market.whale_consensus >= 0.5:
                market.recommended_side = "YES"
            else:
                market.recommended_side = "NO"
        else:
            # No whale data: determine side from price levels
            # If YES is cheap (< 50¢), market says NO is likely → recommend NO
            # If YES is expensive (> 50¢), market says YES is likely → recommend YES
            # But we look for VALUE — buy the side the market leans toward at a reasonable price
            if market.yes_price > 0.5:
                market.recommended_side = "YES"
            elif market.no_price > 0.5:
                market.recommended_side = "NO"
            elif market.price_change_24h > 0.02:
                market.recommended_side = "YES"
            elif market.price_change_24h < -0.02:
                market.recommended_side = "NO"
            else:
                # Truly 50/50 — go with volume side (more activity = more conviction)
                market.recommended_side = "YES" if market.yes_price >= market.no_price else "NO"
                
            # Boost score to compensate for missing whale metrics (max 60 points available without whales)
            # Multiplier ~1.66
            total_score = int(total_score * 1.6)
            if total_score > 100: total_score = 100
                
        market.signal_score = int(total_score)
        adjusted_score = total_score # For compatibility logic below
        
        # Signal strength based on score
        if adjusted_score >= 75:
            market.signal_strength = SignalStrength.STRONG_BUY
        elif adjusted_score >= 65:
            market.signal_strength = SignalStrength.BUY
        elif adjusted_score >= 50:
            market.signal_strength = SignalStrength.MODERATE
        elif adjusted_score >= 35:
            market.signal_strength = SignalStrength.WEAK
        else:
            market.signal_strength = SignalStrength.AVOID
    
    def _calc_whale_score(self, market: MarketStats) -> float:
        """Calculate whale consensus score (max 45 points)."""
        # Whales are the smartest money. Their consensus is the strongest signal.
        if market.whale_consensus is None:
            return 0
            
        total_whale = market.whale_total_volume
        
        if total_whale < self.WHALE_THRESHOLD:
            return 0  # Changed from 5 to 0 because low volume is not a signal
        
        # Use structured analysis if available
        if market.whale_analysis:
            dominance = market.whale_analysis.dominance_pct
            side = market.whale_analysis.dominance_side
            
            # 50% is neutral (0.5). We want deviation from 0.5
            # If dominance is 80%, deviation is 0.3
            if dominance >= 50:
                 deviation = (dominance - 50) / 100
            else:
                 deviation = (50 - dominance) / 100
        else:
            # Fallback to legacy
            consensus = market.whale_consensus
            deviation = abs(consensus - 0.5)
        
        # Exponential scoring for high consensus
        if deviation >= 0.30: return 45      # Super strong consensus (80%+)
        elif deviation >= 0.25: return 35    # Strong consensus (75%+)
        elif deviation >= 0.20: return 25    # Good consensus (70%+)
        elif deviation >= 0.15: return 15    # Moderate consensus (65%+)
        elif deviation >= 0.10: return 10    # Weak consensus (60%+)
        else: return 0
    
    def _calc_volume_score(self, market: MarketStats) -> float:
        """Calculate volume momentum score (max 25 points)."""
        # Volume confirms correctness of the move.
        vol_24h = market.volume_24h
        
        if vol_24h >= 250000: return 25
        elif vol_24h >= 100000: return 20
        elif vol_24h >= 50000: return 15
        elif vol_24h >= 25000: return 10
        elif vol_24h >= 10000: return 5
        else: return 0
    
    def _calc_trend_score(self, market: MarketStats) -> float:
        """Calculate price trend score (max 20 points)."""
        # We want to catch the wave, but not at the very top.
        change_24h = market.price_change_24h
        
        # Align direction
        if market.whale_consensus is not None and market.whale_consensus < 0.5:
            change_24h = -change_24h
        
        # Ideal trend: steady growth +5% to +15%
        if 0.05 <= change_24h <= 0.15: return 20        # Perfect momentum
        elif 0.02 <= change_24h < 0.05: return 15       # Starting to move
        elif 0.15 < change_24h <= 0.25: return 10       # Strong but maybe overheating
        elif change_24h > 0.25: return 5                # FOMO zone, risky
        elif -0.05 <= change_24h < 0.02: return 5       # Consolidation
        else: return 0                                  # Against trend
    
    def _calc_liquidity_score(self, market: MarketStats) -> float:
        """Calculate liquidity score (max 10 points)."""
        # Liquidity ensures we can enter and exit without slippage.
        liq = market.liquidity
        if liq >= 50000: return 10
        elif liq >= 25000: return 8
        elif liq >= 10000: return 5
        else: return 0

    def _calc_time_score(self, market: MarketStats) -> float:
        """Calculate time value (legacy, kept for structure but unused in new formula)."""
        return 0

    
    # ==================== RECOMMENDATION ====================
    
    def generate_recommendation(self, market: MarketStats) -> BetRecommendation:
        """Generate detailed betting recommendation."""
        should_bet = market.signal_score >= 60
        side = market.recommended_side
        
        # CRITICAL: Don't recommend a side priced at 0¢ (fully resolved / no upside)
        # If YES=100¢ the market is basically resolved YES. NO=0¢ has no buyers.
        # If NO=100¢ the market is basically resolved NO. YES=0¢ has no buyers.
        if side == "YES" and market.yes_price <= 0.02:
            # YES is basically 0 — flip to NO if it has value, else don't bet
            if market.no_price >= 0.05:
                side = "NO"
            else:
                should_bet = False
        elif side == "NO" and market.no_price <= 0.02:
            # NO is basically 0 — flip to YES if it has value, else don't bet
            if market.yes_price >= 0.05:
                side = "YES"
            else:
                should_bet = False
        
        # Don't bet on extremely one-sided markets (95%+)
        if market.yes_price >= 0.95 or market.no_price >= 0.95:
            should_bet = False
        
        # Entry price
        if side == "YES":
            entry_price = market.yes_price
        else:
            entry_price = market.no_price
        
        # Don't recommend entry at 0
        if entry_price <= 0.01:
            should_bet = False
            entry_price = max(entry_price, 0.01)
        
        # Target and stop-loss
        target_price = min(0.90, entry_price * 1.3)
        stop_loss_price = max(0.02, entry_price * 0.75)
        
        # Risk/Reward ratio
        potential_gain = target_price - entry_price
        potential_loss = entry_price - stop_loss_price
        risk_reward = potential_gain / potential_loss if potential_loss > 0 else 0
        
        # Build reasons and warnings
        reasons = []
        warnings = []
        
        # Whale analysis
        # Whale analysis - Conflict Check
        if market.whale_analysis and market.whale_analysis.is_significant:
            wa = market.whale_analysis
            whale_side = wa.dominance_side
            
            # Check for conflict: Signal says YES, Whales say NO (or vice versa)
            if should_bet:
                if side == "YES" and whale_side == "NO" and wa.dominance_pct >= 60:
                     warnings.append(f"⚠️ Увага: Smart Money ставлять проти тренду (на NO)")
                     risk_reward *= 0.8 # Penalize R:R
                elif side == "NO" and whale_side == "YES" and wa.dominance_pct >= 60:
                     warnings.append(f"⚠️ Увага: Smart Money ставлять проти тренду (на YES)")
                     risk_reward *= 0.8
            
            # Add supportive reason if aligned
            if whale_side == side and wa.dominance_pct >= 60:
                reasons.append(f"🐋 Smart Money на вашому боці ({wa.dominance_pct:.0f}% {side})")
                
        elif market.whale_consensus is not None:
             # Legacy
             whale_pct = market.whale_consensus if side == "YES" else (1 - market.whale_consensus)
             if whale_pct >= 0.60:
                reasons.append(f"🐋 Консенсус китів: {whale_pct*100:.0f}% на {side}")
             elif whale_pct <= 0.40:
                warnings.append(f"⚠️ Кити ставлять проти ({100-whale_pct*100:.0f}% на інше)")
        else:
            warnings.append("⚠️ Дані китів недоступні — аналіз на основі volume/price")
        
        # Volume
        if market.volume_24h >= 100000:
            reasons.append(f"📈 Високий volume: ${market.volume_24h/1000:.0f}K за 24h")
        elif market.volume_24h >= 50000:
            reasons.append(f"📊 Помірний volume: ${market.volume_24h/1000:.0f}K за 24h")
        else:
            warnings.append(f"⚠️ Низький volume: ${market.volume_24h/1000:.0f}K")
        
        # Price trend
        trend = market.price_change_24h
        if side == "NO":
            trend = -trend
        
        if trend > 0.10:
            reasons.append(f"📈 Сильний тренд: +{trend*100:.1f}% за 24h")
        elif trend > 0:
            reasons.append(f"📈 Позитивний тренд: +{trend*100:.1f}%")
        elif trend > -0.05:
            warnings.append("⚠️ Слабкий тренд")
        else:
            warnings.append(f"⚠️ Негативний тренд: {trend*100:.1f}%")
        
        # Liquidity
        if market.liquidity < 20000:
            warnings.append("⚠️ Низька ліквідність")
        
        # Time
        if market.days_to_close < 1:
            warnings.append("⚠️ Закривається сьогодні — високий ризик")
        elif market.days_to_close > 21:
            warnings.append("⚠️ Довгий термін — капітал заблоковано")
        
        # Don't bet if too many warnings
        if len(warnings) >= 3:
            should_bet = False
        
        return BetRecommendation(
            market=market,
            should_bet=should_bet,
            side=side,
            confidence=market.signal_score,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
            risk_reward_ratio=risk_reward,
            reasons=reasons,
            warnings=warnings,
        )


# Global instance
market_intelligence = MarketIntelligenceEngine()
