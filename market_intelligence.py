"""
BetSpy Market Intelligence Engine — v2 (Refactored)

Mathematical analysis of Polymarket events for profitable betting signals.
All formulas documented with examples. No AI — pure math.

Key changes vs v1:
- Fixed USDC calculation (prefer usdcSize field)
- Time-windowed whale analysis (24h default, configurable)
- New 5-metric scoring (tilt, volume, smart ratio, liquidity, recency)
- Deterministic event→market mapping with garbage filtering
- Market quality labels
- All edge cases handled (zero volume, single-side, etc.)
"""

import asyncio
import time as _time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

import aiohttp
from aiolimiter import AsyncLimiter
from loguru import logger

from config import get_settings


# =====================================================================
# ENUMS
# =====================================================================

class TimeFrame(Enum):
    TODAY = "today"
    DAYS_2 = "2days"
    DAYS_3 = "3days"
    WEEK = "week"
    MONTH = "month"


class Category(Enum):
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
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    MODERATE = "moderate"
    WEAK = "weak"
    AVOID = "avoid"


class MarketQuality(Enum):
    HIGH_CONVICTION = "high_conviction"
    MODERATE_SIGNAL = "moderate_signal"
    NOISY = "noisy"
    LOW_LIQUIDITY = "low_liquidity"
    AVOID = "avoid"


# =====================================================================
# DATA CLASSES
# =====================================================================

@dataclass
class WhaleAnalysis:
    """Structured analysis of whale (smart money) activity.

    Tiers:
      - Medium: $500–$2000 per trade
      - Large (Whale): $2000+ per trade
      - Retail: < $500

    All volumes are in USDC.
    """
    yes_volume: float = 0.0
    no_volume: float = 0.0
    yes_count: int = 0
    no_count: int = 0
    total_volume: float = 0.0

    # Tilt: (yes - no) / total, range [-1, +1]. 0 = neutral.
    tilt: float = 0.0
    dominance_side: str = "NEUTRAL"
    dominance_pct: float = 50.0
    sentiment: str = "NEUTRAL"

    # Top single trade
    top_trade_size: float = 0.0
    top_trade_side: str = ""

    # Recency
    last_trade_timestamp: int = 0
    last_trade_side: str = ""

    # Tier breakdown
    medium_volume: float = 0.0  # $500–$2000
    large_volume: float = 0.0   # $2000+

    # Time window
    window_hours: int = 24

    trade_count: int = 0

    # New fields for detailed report
    last_big_timestamp: int = 0
    last_big_side: str = ""
    last_big_size: float = 0.0
    biggest_yes_size: float = 0.0
    biggest_no_size: float = 0.0

    @property
    def is_significant(self) -> bool:
        """At least $1000 smart money volume to be meaningful."""
        return self.total_volume >= 1000

    @property
    def large_whale_share_pct(self) -> float:
        """% of smart money from large ($2000+) whales."""
        if self.total_volume > 0:
            return (self.large_volume / self.total_volume) * 100
        return 0.0

    @property
    def hours_since_last_trade(self) -> float:
        """Hours since last smart money trade."""
        if self.last_trade_timestamp <= 0:
            return 999.0
        return (_time.time() - self.last_trade_timestamp) / 3600

    @property
    def duration_text(self) -> str:
        if self.window_hours <= 0:
            return ""
        if self.window_hours <= 24:
            return f"in last {self.window_hours}h"
        return f"in last {self.window_hours // 24}d"


@dataclass
class HoldersAnalysis:
    smart_score: int
    smart_score_side: str

    def __post_init__(self):
        if self.smart_score_side is None:
            self.smart_score_side = "NEUTRAL"


@dataclass
class MarketStats:
    """Statistics for a single market."""
    condition_id: str
    question: str
    slug: str
    event_slug: str

    # Prices (0.0–1.0)
    yes_price: float
    no_price: float

    # Volume (USDC)
    volume_24h: float
    volume_total: float

    # Liquidity (USDC)
    liquidity: float

    # Time
    end_date: datetime
    days_to_close: int

    # Category
    category: str
    tags: List[str] = field(default_factory=list)

    # Whale analysis (populated by _enrich_market_data)
    whale_analysis: Optional[WhaleAnalysis] = None

    # Retail volumes
    retail_yes_volume: float = 0.0
    retail_no_volume: float = 0.0

    # Price history
    price_24h_ago: float = 0.0
    price_7d_ago: float = 0.0

    # CLOB token IDs
    clob_token_ids: List[str] = field(default_factory=list)

    # Computed signal (filled by _calculate_signal)
    signal_score: int = 0
    signal_strength: SignalStrength = SignalStrength.AVOID
    market_quality: MarketQuality = MarketQuality.AVOID
    recommended_side: str = "NONE"

    holders: Optional[HoldersAnalysis] = None
    
    # Calculated fields
    model_prob: float = 0.0
    edge: float = 0.0
    effective_edge: float = 0.0
    rec_side: str = "NEUTRAL"
    kelly_pct: float = 0.0
    arbitrage_available: bool = False
    hot_score: float = 0.0

    # Score breakdown for transparency
    score_breakdown: Dict[str, float] = field(default_factory=dict)

    @property
    def whale_total_volume(self) -> float:
        if self.whale_analysis:
            return self.whale_analysis.total_volume
        return 0.0

    @property
    def total_volume_all(self) -> float:
        """All volume: smart + retail."""
        retail = self.retail_yes_volume + self.retail_no_volume
        return self.whale_total_volume + retail

    @property
    def smart_money_ratio(self) -> float:
        """Fraction of total volume that is smart money."""
        total = self.total_volume_all
        if total > 0:
            return self.whale_total_volume / total
        return 0.0

    @property
    def price_change_24h(self) -> float:
        if self.price_24h_ago > 0:
            return (self.yes_price - self.price_24h_ago) / self.price_24h_ago
        return 0.0

    @property
    def market_url(self) -> str:
        from config import get_settings, get_referral_link
        return get_referral_link(self.event_slug, self.slug)


@dataclass
class BetRecommendation:
    """Final betting recommendation for display."""
    market: MarketStats
    should_bet: bool
    side: str  # "YES" or "NO"
    confidence: int  # 0–100 = signal_score
    entry_price: float
    target_price: float
    stop_loss_price: float
    risk_reward_ratio: float
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# =====================================================================
# ENGINE
# =====================================================================

class MarketIntelligenceEngine:
    """
    Core engine: fetches data, computes metrics, assigns signals.

    Scoring (100 pts max):
      1. Smart Money Tilt:  0–40 pts
      2. Volume Momentum:   0–25 pts
      3. Smart/Retail Ratio: 0–15 pts
      4. Liquidity:          0–10 pts
      5. Activity Recency:   0–10 pts
    """

    FEE_RATE = 0.005  # Polymarket 0.5% per trade
    MIN_EDGE = 0.02
    MAX_KELLY_PCT = 15.0
    
    # --- Thresholds ---
    MEDIUM_THRESHOLD = 500    # $500+ = medium smart money
    WHALE_THRESHOLD = 2000    # $2000+ = large whale
    MIN_VOLUME_24H = 1000     # Minimum 24h vol to show in trending
    WHALE_WINDOW_HOURS = 24   # Default analysis window

    # --- Category keywords ---
    CATEGORY_TAGS = {
        Category.POLITICS: ["politics", "election", "president", "trump", "biden",
                           "congress", "senate", "republican", "democrat", "vote",
                           "government", "governor", "legislation", "primary",
                           "presidential", "political", "parliament", "minister",
                           "cabinet", "impeach", "white house", "executive order",
                           "supreme court", "scotus", "fed", "federal"],
        Category.SPORTS: ["sports", "nfl", "nba", "mlb", "nhl", "soccer",
                         "football", "basketball", "baseball", "hockey", "tennis",
                         "mma", "ufc", "boxing", "golf", "f1", "racing",
                         "olympics", "fifa", "super bowl", "premier league",
                         "la liga", "serie a", "bundesliga", "champions league",
                         "europa league", "cricket", "rugby", "playoffs",
                         "world series", "stanley cup", "march madness",
                         "pga", "grand prix", "formula 1", "atp", "wta",
                         "ncaa", "epl", "world cup", "mvp"],
        Category.POP_CULTURE: ["pop culture", "celebrity", "movie", "music",
                               "grammy", "oscars", "singer", "album",
                               "hollywood", "netflix", "taylor swift",
                               "beyonce", "kanye", "kardashian", "tiktok",
                               "instagram", "youtube", "influencer", "viral"],
        Category.BUSINESS: ["business", "company", "stock", "ceo", "merger",
                           "ipo", "earnings", "revenue", "apple", "google",
                           "tesla", "nasdaq", "s&p", "dow", "market cap",
                           "acquisition", "sec", "fed rate", "interest rate",
                           "gdp", "inflation", "unemployment", "layoff",
                           "profit", "valuation", "startup"],
        Category.CRYPTO: ["crypto", "bitcoin", "btc", "ethereum", "eth",
                         "solana", "sol", "defi", "nft", "blockchain",
                         "binance", "coinbase", "memecoin", "web3",
                         "altcoin", "doge", "dogecoin", "xrp", "ripple",
                         "cardano", "ada", "polygon", "matic", "avax",
                         "avalanche", "polkadot", "dot", "chainlink",
                         "link", "uniswap", "aave", "token", "staking",
                         "halving", "etf", "crypto etf", "spot etf",
                         "pepe", "shib", "sui", "apt", "aptos", "ton",
                         "tron", "near", "arbitrum", "optimism",
                         "layer 2", "l2", "dex", "cex", "exchange"],
        Category.SCIENCE: ["science", "space", "nasa", "spacex", "climate",
                          "research", "mars", "vaccine", "health",
                          "covid", "fda", "who", "pandemic", "study",
                          "moon", "asteroid", "nuclear", "quantum",
                          "fusion", "telescope", "nobel", "pharmaceutical"],
        Category.GAMING: ["gaming", "esports", "cs2", "cs:go", "csgo",
                         "counter-strike", "counter strike", "dota", "dota2",
                         "valorant", "league of legends", "lol",
                         "overwatch", "fortnite", "twitch", "steam",
                         "xbox", "playstation", "nintendo", "gta",
                         "call of duty", "cod", "apex", "pubg",
                         "fnatic", "navi", "faze", "g2", "cloud9",
                         "team liquid", "vitality", "heroic", "og ",
                         "map winner", "tournament", "major", "blast",
                         "esl", "iem", "pgl", "faceit", "hltv",
                         "lcs", "lec", "worlds", "the international",
                         "ti ", "game ", "games", "gamer"],
        Category.ENTERTAINMENT: ["entertainment", "tv", "show", "series",
                                "streaming", "disney", "hbo", "award",
                                "emmy", "golden globe", "box office",
                                "anime", "manga", "comic", "marvel",
                                "dc", "star wars", "reality tv",
                                "bachelor", "snl", "late night"],
        Category.WORLD: ["world", "international", "war", "conflict",
                        "russia", "ukraine", "china", "europe",
                        "sanctions", "middle east", "nato", "un",
                        "north korea", "iran", "israel", "palestine",
                        "gaza", "taiwan", "india", "brazil",
                        "ceasefire", "peace", "treaty", "migration",
                        "refugee", "diplomacy", "summit", "g7", "g20"],
        Category.TECH: ["tech", "ai", "artificial intelligence", "openai",
                       "chatgpt", "software", "startup", "iphone",
                       "microsoft", "meta", "amazon", "nvidia",
                       "semiconductor", "chip", "robot", "autonomous",
                       "self-driving", "virtual reality", "vr", "ar",
                       "augmented reality", "gpt", "llm", "anthropic",
                       "claude", "gemini", "deepmind", "machine learning",
                       "neural", "computing", "android", "samsung",
                       "huawei", "5g", "6g", "quantum computing"],
    }

    def __init__(self):
        self.gamma_api_url = "https://gamma-api.polymarket.com"
        self.data_api_url = "https://data-api.polymarket.com"
        self.clob_api_url = "https://clob.polymarket.com"
        self._limiter = AsyncLimiter(60, 60)
        self._session: Optional[aiohttp.ClientSession] = None

    async def init(self) -> None:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=20)
            self._session = aiohttp.ClientSession(
                timeout=timeout, connector=connector,
            )
            logger.info("Market Intelligence Engine initialized")

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(self, url: str, params: Dict = None) -> Any:
        if not self._session:
            await self.init()
        async with self._limiter:
            try:
                async with self._session.get(url, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:
                        logger.warning("Rate limited, waiting 5s")
                        await asyncio.sleep(5)
                        return None
                    else:
                        logger.warning(f"API {resp.status}: {url}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"Timeout: {url}")
                return None
            except Exception as e:
                logger.error(f"Request failed: {e}")
                return None

    # =================================================================
    # DATA FETCHING
    # =================================================================

    async def fetch_event_markets(
        self,
        slug: str,
        market_slug: Optional[str] = None,
        skip_long_term_filter: bool = False,
    ) -> List[MarketStats]:
        """
        Fetch markets for event slug. Deterministic & defensive.

        Strategy:
        1. Try Gamma /markets?event_slug=<slug> → validate eventSlug match
        2. Fallback: Gamma /events?slug=<slug> → extract embedded markets
        3. Fallback: Gamma /markets?slug=<slug> (direct market lookup)
        4. Filter garbage: only items where eventSlug matches OR came from
           the trusted event object.
        """
        logger.info(f"fetch_event_markets: slug={slug}, market_slug={market_slug}")
        url = f"{self.gamma_api_url}/markets"

        raw_items = []
        source = "unknown"

        # --- Strategy 1: event_slug query ---
        params = {"event_slug": slug, "active": "true", "closed": "false"}
        data = await self._request(url, params)

        valid_items = [
            item for item in (data or [])
            if item.get("eventSlug") == slug
        ]

        if valid_items:
            raw_items = valid_items
            source = "event_slug_query"
            dropped = len(data or []) - len(valid_items)
            if dropped > 0:
                logger.info(f"Dropped {dropped} garbage items (eventSlug mismatch)")
        else:
            # --- Strategy 2: /events endpoint ---
            logger.info(f"Trying /events for slug: {slug}")
            events_data = await self._request(
                f"{self.gamma_api_url}/events", {"slug": slug}
            )
            target_event = None
            for ev in (events_data or []):
                if ev.get("slug") == slug:
                    target_event = ev
                    break

            if target_event:
                embedded = target_event.get("markets", [])
                if embedded:
                    raw_items = embedded
                    source = "event_object_embedded"
                    logger.info(f"Found {len(embedded)} markets in event object")
                else:
                    event_id = target_event.get("id")
                    if event_id:
                        data2 = await self._request(url, {
                            "event_id": event_id, "active": "true", "closed": "false"
                        })
                        if data2:
                            raw_items = [
                                item for item in data2
                                if item.get("eventSlug") == slug or item.get("eventSlug") is None
                            ]
                            source = "event_id_query"

            # --- Strategy 3: direct market slug ---
            if not raw_items:
                logger.info(f"Trying as market slug: {slug}")
                data3 = await self._request(url, {
                    "slug": slug, "active": "true", "closed": "false"
                })
                if data3:
                    raw_items = data3
                    source = "market_slug_query"

        if not raw_items:
            logger.warning(f"No markets found for slug={slug}")
            return []

        logger.info(f"Found {len(raw_items)} raw items (source: {source})")

        # --- Parse & filter ---
        markets = []
        # Determine the event_slug to use for URL generation
        # For event_object_embedded and event_id_query sources, we know the correct event slug
        known_event_slug = slug if source in ("event_object_embedded", "event_id_query", "event_slug_query") else ""
        
        for item in raw_items:
            try:
                # If market_slug specified, only that market
                if market_slug and item.get("slug") != market_slug:
                    continue

                # Final slug validation (skip for embedded — already trusted)
                if source not in ("event_object_embedded",):
                    item_event = item.get("eventSlug", "")
                    item_slug = item.get("slug", "")
                    if item_event != slug and item_slug != slug:
                        continue

                parsed = self._parse_market(
                    item, 
                    skip_long_term_filter, 
                    override_event_slug=known_event_slug,
                    include_expired=True  # Allow analyzing closed events if user asks
                )
                if parsed:
                    markets.append(parsed)
            except Exception as e:
                logger.error(f"Failed to parse market item: {e}")

        logger.info(f"Parsed {len(markets)} valid markets for slug={slug}")

        # Enrich with whale data
        enriched = []
        for m in markets:
            try:
                m = await self._enrich_market_data(m)
                self._calculate_signal(m)
                enriched.append(m)
            except Exception as e:
                logger.error(f"Failed to enrich {m.slug}: {e}")
                enriched.append(m)

        enriched.sort(key=lambda m: m.volume_24h, reverse=True)
        return enriched

    async def fetch_trending_markets(
        self,
        category: Category = Category.ALL,
        timeframe: TimeFrame = TimeFrame.WEEK,
        limit: int = 20,
    ) -> List[MarketStats]:
        """Fetch trending markets filtered by category and timeframe."""
        now = datetime.utcnow()

        tf_ranges = {
            TimeFrame.TODAY: (now - timedelta(hours=1), now + timedelta(hours=36)),
            TimeFrame.DAYS_2: (now, now + timedelta(days=3)),
            TimeFrame.DAYS_3: (now, now + timedelta(days=4)),
            TimeFrame.WEEK: (now, now + timedelta(days=8)),
            TimeFrame.MONTH: (now, now + timedelta(days=35)),
        }
        end_after, end_before = tf_ranges.get(timeframe, tf_ranges[TimeFrame.MONTH])

        params = {
            "active": "true", "closed": "false",
            "limit": 200, "order": "volume24hr", "ascending": "false",
        }
        data = await self._request(f"{self.gamma_api_url}/markets", params)
        if not data:
            return []

        markets = []
        for item in data:
            try:
                m = self._parse_market(item)
                if not m:
                    continue

                # Timeframe filter
                if timeframe != TimeFrame.MONTH:
                    if m.end_date < end_after or m.end_date > end_before:
                        continue

                # Category filter
                if category != Category.ALL:
                    if not self._matches_category(m, category):
                        continue

                # Volume filter — lower for short-term and specific categories
                if category != Category.ALL:
                    min_vol = 500  # Lower threshold for specific categories
                elif timeframe in (TimeFrame.TODAY, TimeFrame.DAYS_2, TimeFrame.DAYS_3):
                    min_vol = 500
                else:
                    min_vol = self.MIN_VOLUME_24H
                if m.volume_24h < min_vol:
                    continue

                markets.append(m)
            except Exception:
                continue

        # Fallback: if nothing found, relax timeframe and volume
        if not markets and timeframe != TimeFrame.MONTH:
            for item in data:
                try:
                    m = self._parse_market(item)
                    if not m:
                        continue
                    if category != Category.ALL and not self._matches_category(m, category):
                        continue
                    if m.volume_24h >= 100:  # Very low threshold as fallback
                        markets.append(m)
                except Exception:
                    continue

        markets.sort(key=lambda m: m.volume_24h, reverse=True)
        markets = markets[:limit]

        # Enrich and filter out noise for "money-making" focus
        enriched = []
        for m in markets:
            try:
                m = await self._enrich_market_data(m)
                self._calculate_signal(m)
                m = self.enrich_with_edge_kelly(m)
                
                # Filter noise
                if m.yes_price > 0.95 or m.no_price > 0.95:
                    continue
                if m.days_to_close > 7:
                    continue
                if m.liquidity < 30000:
                    continue
                    
                enriched.append(m)
            except Exception as e:
                logger.error(f"Enrich failed for {m.slug}: {e}")
                # Don't append if failed, we want quality
        
        # Sort by volume first, then by signal score
        enriched.sort(key=lambda m: (m.volume_24h, m.signal_score), reverse=True)
        return enriched[:limit]

    def enrich_with_edge_kelly(self, market: MarketStats) -> MarketStats:
        """
        Quick edge & Kelly calculation with safety caps and fee adjustment.
        """
        from analytics.probability import signal_to_probability, calculate_edge
        
        try:
            model_prob = signal_to_probability(market)
        except Exception:
            model_prob = market.yes_price
            
        gross_edge = calculate_edge(model_prob, market.yes_price)
        
        # Fee-adjusted edge (buy + sell consideration)
        effective_edge = abs(gross_edge) - 2 * self.FEE_RATE
        
        rec_side = "NEUTRAL"
        kelly_pct = 0.0
        
        # Check for arbitrage opportunity
        if market.yes_price + market.no_price < 0.98:
            market.arbitrage_available = True
        
        # Determine recommendation side with safety checks
        cost = market.yes_price
        p = model_prob
        
        if gross_edge >= self.MIN_EDGE and market.yes_price >= 0.05:
            rec_side = "YES"
            p, cost = model_prob, market.yes_price
        elif gross_edge <= -self.MIN_EDGE and market.no_price >= 0.05:
            rec_side = "NO"
            p, cost = 1.0 - model_prob, market.no_price
        
        # Kelly calculation with safety caps
        if rec_side != "NEUTRAL" and effective_edge > 0:
            b = (1.0 - cost) / cost if cost > 0 else 0
            if b > 0:
                q = 1.0 - p
                f_full = max(0, (b * p - q) / b)
                
                # Quarter-Kelly with confidence scaling
                conf = getattr(market, "signal_score", 70) / 100.0
                if conf <= 0:
                    conf = 0.5
                kelly_pct = min(f_full * 0.25 * conf * 100, self.MAX_KELLY_PCT)
        
        market.model_prob = model_prob
        market.edge = gross_edge
        market.effective_edge = effective_edge
        market.rec_side = rec_side
        market.kelly_pct = round(kelly_pct, 1)
        
        return market

    async def fetch_signal_markets(self, limit: int = 5) -> List[MarketStats]:
        """
        Fetch markets with strong signals (for quick trading opportunities).
        Filters: score ≥ 75, effective edge ≥ 3%, liquidity ≥ 50k, time ≤ 3 days.
        """
        markets = await self.fetch_trending_markets(
            category=Category.ALL,
            timeframe=TimeFrame.DAYS_3,
            limit=50
        )
        
        signals = []
        for m in markets:
            # Re-enrich with latest edge/Kelly
            m = self.enrich_with_edge_kelly(m)
            
            # Strong signal filters
            if m.signal_score < 75:
                continue
            if abs(getattr(m, "effective_edge", 0.0)) < 0.03:
                continue
            if m.liquidity < 50000:
                continue
            if m.days_to_close > 3:
                continue
            
            signals.append(m)
        
        # Sort by effective_edge * score (value-weighted signal strength)
        signals.sort(
            key=lambda m: abs(m.effective_edge) * m.signal_score, 
            reverse=True
        )
        
        return signals[:limit]

    async def fetch_hot_opportunities(self, limit: int = 15) -> List[MarketStats]:
        """
        Global HOT: best money-making markets across ALL categories.
        Сортує по edge × score × ліквідність, з урахуванням SM-конфліктів.
        """
        # Беремо ширший пул по ВСІХ категоріях
        base = await self.fetch_trending_markets(
            category=Category.ALL,
            timeframe=TimeFrame.TODAY,
            limit=120,  # беремо запас, потім відфільтруємо
        )

        hot = []
        for m in base:
            # Edge/Kelly вже є після fetch_trending_markets,
            # але на всяк випадок перевіряємо атрибути
            edge_abs = abs(getattr(m, "effective_edge", getattr(m, "edge", 0.0)))
            score = getattr(m, "signal_score", 0)
            kelly = getattr(m, "kelly_pct", 0.0)
            liq = m.liquidity

            # Сильний SM-конфлікт — штраф
            sm_penalty = 0
            h = getattr(m, "holders", None)
            if h and h.smart_score_side not in ("NEUTRAL", m.rec_side) and h.smart_score >= 80:
                sm_penalty = -40
            elif h and h.smart_score_side not in ("NEUTRAL", m.rec_side) and h.smart_score >= 60:
                sm_penalty = -20

            # Формула hot-score
            # 1. Edge (найважливіший)
            # 2. Signal Score (модельна впевненість)
            # 3. Liquidity (бонус за виконання без сліппеджу)
            # 4. Kelly (рекомендований розмір)
            # 5. Smart Money Penalty (конфлікт інтересів)
            
            hot_score = (
                edge_abs * 100 * 2 +       # кожні 1% edge = 2 бали
                score * 1.2 +              # сигнал
                min(liq / 10000, 10) * 3 + # ліквідність (max 30 балів)
                kelly * 1.5 +              # розмір ставки
                sm_penalty                 # штраф
            )

            m.hot_score = hot_score
            hot.append(m)

        # Сортуємо за hot_score, потім за 24h volume
        hot.sort(key=lambda m: (m.hot_score, m.volume_24h), reverse=True)
        return hot[:limit]

    # =================================================================
    # PARSING
    # =================================================================

    def _parse_market(
        self, data: Dict, skip_long_term_filter: bool = False,
        override_event_slug: str = "", include_expired: bool = False,
    ) -> Optional[MarketStats]:
        """Parse raw API dict into MarketStats. Returns None if invalid.
        
        Args:
            data: Raw API response dict
            skip_long_term_filter: If True, don't filter by price or long-term date
            override_event_slug: If provided, use this as event_slug instead of extracting from data
        """
        try:
            # End date
            end_str = data.get("endDate") or data.get("end_date_iso")
            if not end_str:
                return None

            try:
                if "T" in end_str:
                    end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                else:
                    end_date = datetime.strptime(end_str, "%Y-%m-%d")
            except Exception:
                return None

            if end_date.tzinfo is not None:
                end_date = end_date.replace(tzinfo=None)

            now = datetime.utcnow()
            if end_date < now and not include_expired:
                return None

            days_to_close = (end_date - now).days
            if days_to_close > 180 and not skip_long_term_filter:
                return None

            # Prices
            outcome_prices = data.get("outcomePrices", [])
            if isinstance(outcome_prices, str):
                import json
                outcome_prices = json.loads(outcome_prices)
            yes_price = float(outcome_prices[0]) if len(outcome_prices) >= 1 else 0.5
            no_price = float(outcome_prices[1]) if len(outcome_prices) >= 2 else 0.5

            # Skip already-resolved markets (either side >= 95¢)
            if not skip_long_term_filter:
                if yes_price >= 0.95 or no_price >= 0.95:
                    return None

            # Volume
            vol_24h = float(data.get("volume24hr", 0) or 0)
            vol_total = float(data.get("volume", 0) or 0)

            # Liquidity
            liquidity = float(data.get("liquidity", 0) or 0)

            # Tags
            tags = data.get("tags", []) or []
            if isinstance(tags, str):
                tags = [tags]

            # CLOB token IDs
            clob_ids = data.get("clobTokenIds", []) or []
            if isinstance(clob_ids, str):
                import json as _j
                try:
                    clob_ids = _j.loads(clob_ids)
                except Exception:
                    clob_ids = []

            category = self._detect_category(tags, data.get("question", ""))
            
            # Determine event_slug - order of preference:
            # 1. override_event_slug (if provided)
            # 2. eventSlug from data
            # 3. slug from nested events array (events[0].slug)
            # 4. DO NOT use market slug as fallback - it's not valid for URLs!
            event_slug = ""
            if override_event_slug:
                event_slug = override_event_slug
            elif data.get("eventSlug"):
                event_slug = data.get("eventSlug", "")
            else:
                # Try to extract from nested events array
                events = data.get("events", [])
                if events and isinstance(events, list) and len(events) > 0:
                    event_slug = events[0].get("slug", "")
            
            # If still no event_slug, log warning - URL will be broken
            if not event_slug:
                logger.warning(f"No event_slug found for market: {data.get('question', '')[:50]}")
                # Use market slug as last resort, but strip number suffixes (e.g., -644-513-935)
                market_slug = data.get("slug", "")
                # Try to clean the slug by removing trailing -XXX-XXX-XXX patterns
                import re
                cleaned = re.sub(r'(-\d+)+$', '', market_slug)
                event_slug = cleaned if cleaned else market_slug

            return MarketStats(
                condition_id=data.get("conditionId", ""),
                question=data.get("question", ""),
                slug=data.get("slug", ""),
                event_slug=event_slug,
                yes_price=yes_price,
                no_price=no_price,
                volume_24h=vol_24h,
                volume_total=vol_total,
                liquidity=liquidity,
                end_date=end_date,
                days_to_close=days_to_close,
                category=category,
                tags=tags,
                clob_token_ids=clob_ids,
            )
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None


    def _detect_category(self, tags: List[str], question: str) -> str:
        tags_lower = {t.lower() for t in tags}
        q_lower = question.lower()
        for cat, keywords in self.CATEGORY_TAGS.items():
            for kw in keywords:
                if kw in tags_lower or kw in q_lower:
                    return cat.value
        return "other"

    def _matches_category(self, market: MarketStats, category: Category) -> bool:
        if category == Category.ALL:
            return True
        keywords = self.CATEGORY_TAGS.get(category, [])
        # Check tags
        for tag in market.tags:
            if tag.lower() in keywords:
                return True
        # Check question
        q_lower = market.question.lower()
        for kw in keywords:
            if kw in q_lower:
                return True
        # Check slug and event_slug (e.g. "nba-mvp-2025", "cs2-blast-major")
        slug_text = f"{market.slug} {market.event_slug}".lower().replace("-", " ")
        for kw in keywords:
            if kw in slug_text:
                return True
        return market.category == category.value

    # =================================================================
    # ENRICHMENT — whale data, price history
    # =================================================================

    async def _enrich_market_data(self, market: MarketStats) -> MarketStats:
        """Fetch trades, compute whale analysis, price history."""
        # Fetch recent trades (time-windowed)
        trades = await self._fetch_market_trades(market, limit=1500)

        # Time window: last WHALE_WINDOW_HOURS
        now_ts = int(_time.time())
        window_start = now_ts - (self.WHALE_WINDOW_HOURS * 3600)

        # Accumulators
        whale_yes_vol = whale_no_vol = 0.0
        whale_yes_count = whale_no_count = 0
        retail_yes_vol = retail_no_vol = 0.0
        medium_vol = large_vol = 0.0
        top_size = 0.0
        top_side = ""
        last_ts = 0
        last_side = ""
        trade_count = 0
        
        # New trackers
        last_big_ts = 0
        last_big_side = ""
        last_big_size = 0.0
        biggest_yes = 0.0
        biggest_no = 0.0

        for trade in trades:
            ts = int(trade.get("timestamp", 0) or 0)

            # Only count trades within the time window
            if ts < window_start:
                continue

            # Calculate USDC amount
            # Prefer usdcSize if available; otherwise size * price
            usdc_size = trade.get("usdcSize")
            if usdc_size is not None:
                try:
                    amount = abs(float(usdc_size))
                except (ValueError, TypeError):
                    amount = 0.0
            else:
                try:
                    size = float(trade.get("size", 0) or 0)
                    price = float(trade.get("price", 0) or 0)
                    amount = size * price
                except (ValueError, TypeError):
                    continue

            if amount <= 0:
                continue

            trade_count += 1
            side = str(trade.get("side", "")).upper()
            outcome_idx = int(trade.get("outcomeIndex", 0) or 0)

            # Direction:
            # BUY+idx0 = YES, BUY+idx1 = NO
            # SELL+idx0 = NO, SELL+idx1 = YES
            is_yes = (
                (side == "BUY" and outcome_idx == 0)
                or (side == "SELL" and outcome_idx == 1)
            )

            if amount >= self.MEDIUM_THRESHOLD:
                # Smart money
                if is_yes:
                    whale_yes_vol += amount
                    whale_yes_count += 1
                else:
                    whale_no_vol += amount
                    whale_no_count += 1

                if amount >= self.WHALE_THRESHOLD:
                    large_vol += amount
                else:
                    medium_vol += amount

                if amount > top_size:
                    top_size = amount
                    top_side = "YES" if is_yes else "NO"

                if ts > last_ts:
                    last_ts = ts
                    last_side = "YES" if is_yes else "NO"
                
                # Check for big whale (> $5000) for "Last big"
                if amount >= 5000:
                    if ts > last_big_ts:
                        last_big_ts = ts
                        last_big_side = "YES" if is_yes else "NO"
                        last_big_size = amount
                
                # Biggest bet split
                if is_yes:
                    if amount > biggest_yes: biggest_yes = amount
                else:
                    if amount > biggest_no: biggest_no = amount
            else:
                # Retail
                if is_yes:
                    retail_yes_vol += amount
                else:
                    retail_no_vol += amount

        market.retail_yes_volume = retail_yes_vol
        market.retail_no_volume = retail_no_vol

        # Build WhaleAnalysis
        total_whale = whale_yes_vol + whale_no_vol
        wa = WhaleAnalysis(
            yes_volume=whale_yes_vol,
            no_volume=whale_no_vol,
            yes_count=whale_yes_count,
            no_count=whale_no_count,
            total_volume=total_whale,
            medium_volume=medium_vol,
            large_volume=large_vol,
            top_trade_size=top_size,
            top_trade_side=top_side,
            last_trade_timestamp=last_ts,
            last_trade_side=last_side,
            window_hours=self.WHALE_WINDOW_HOURS,
            trade_count=trade_count,
            last_big_timestamp=last_big_ts,
            last_big_side=last_big_side,
            last_big_size=last_big_size,
            biggest_yes_size=biggest_yes,
            biggest_no_size=biggest_no,
        )

        # Tilt & dominance
        if total_whale > 0:
            wa.tilt = (whale_yes_vol - whale_no_vol) / total_whale
            yes_pct = (whale_yes_vol / total_whale) * 100
            no_pct = (whale_no_vol / total_whale) * 100

            # Neutral zone: 45–55%
            if yes_pct > 55:
                wa.dominance_side = "YES"
                wa.dominance_pct = yes_pct
            elif no_pct > 55:
                wa.dominance_side = "NO"
                wa.dominance_pct = no_pct
            else:
                wa.dominance_side = "NEUTRAL"
                wa.dominance_pct = max(yes_pct, no_pct)

            # Sentiment label
            if wa.dominance_pct >= 80:
                wa.sentiment = f"💎 Strong {wa.dominance_side}"
            elif wa.dominance_pct >= 65:
                wa.sentiment = f"Bullish {wa.dominance_side}"
            elif wa.dominance_pct > 55:
                wa.sentiment = f"Leaning {wa.dominance_side}"
            else:
                wa.sentiment = "Neutral / Mixed"
        else:
            wa.dominance_side = "NEUTRAL"
            wa.dominance_pct = 50.0
            wa.tilt = 0.0
            wa.sentiment = "No Activity"

        market.whale_analysis = wa

        # Price history
        history = await self._fetch_price_history(market.condition_id)
        if history:
            market.price_24h_ago = history.get("price_24h", market.yes_price)
            market.price_7d_ago = history.get("price_7d", market.yes_price)

        return market

    async def _fetch_market_trades(
        self, market: MarketStats, limit: int = 1500,
    ) -> List[Dict]:
        """Fetch trades via public Data API."""
        data = await self._request(
            f"{self.data_api_url}/trades",
            {"market": market.condition_id, "limit": min(limit, 2000)},
        )
        if data and isinstance(data, list):
            return data
        return []

    async def _fetch_price_history(self, condition_id: str) -> Dict:
        """Fetch price history for 24h and 7d ago from CLOB timeseries."""
        data = await self._request(
            f"{self.clob_api_url}/prices-history",
            {"market": condition_id, "interval": "1d", "fidelity": 60},
        )
        result = {}
        prices = None
        if isinstance(data, dict):
            prices = data.get("history", data)
        elif isinstance(data, list):
            prices = data

        if prices and isinstance(prices, list) and len(prices) > 0:
            if len(prices) >= 24:
                result["price_24h"] = float(
                    prices[-24].get("p", prices[-24].get("price", 0.5))
                )
            if len(prices) >= 168:
                result["price_7d"] = float(
                    prices[-168].get("p", prices[-168].get("price", 0.5))
                )
        return result

    # =================================================================
    # SIGNAL CALCULATION — 5 metrics, 100 pts max
    # =================================================================

    def _calculate_signal(self, market: MarketStats) -> None:
        """
        5-metric scoring. Each metric has a clear formula and max points.

        1. Smart Money Tilt (0–40):  abs(tilt) mapped to score
        2. Volume Momentum  (0–25):  vol_24h tier
        3. Smart/Retail Ratio (0–15): whale_vol/total_vol
        4. Liquidity         (0–10):  raw liquidity tier
        5. Recency           (0–10):  hours since last whale trade
        """
        scores = {}
        wa = market.whale_analysis

        # 1. SMART MONEY TILT (max 40)
        # Formula: tilt = (yes_vol - no_vol) / total_vol ∈ [-1, 1]
        # Score based on |tilt|:
        #   |tilt| >= 0.60 → 40  (80%+ on one side)
        #   |tilt| >= 0.50 → 35  (75%+)
        #   |tilt| >= 0.40 → 28  (70%+)
        #   |tilt| >= 0.30 → 20  (65%+)
        #   |tilt| >= 0.20 → 12  (60%+)
        #   |tilt| >= 0.10 → 5   (55%+)
        #   else           → 0
        if wa and wa.is_significant:
            abs_tilt = abs(wa.tilt)
            if abs_tilt >= 0.60:
                scores["tilt"] = 40
            elif abs_tilt >= 0.50:
                scores["tilt"] = 35
            elif abs_tilt >= 0.40:
                scores["tilt"] = 28
            elif abs_tilt >= 0.30:
                scores["tilt"] = 20
            elif abs_tilt >= 0.20:
                scores["tilt"] = 12
            elif abs_tilt >= 0.10:
                scores["tilt"] = 5
            else:
                scores["tilt"] = 0
        else:
            scores["tilt"] = 0

        # 2. VOLUME MOMENTUM (max 25)
        v = market.volume_24h
        if v >= 250_000:
            scores["volume"] = 25
        elif v >= 100_000:
            scores["volume"] = 20
        elif v >= 50_000:
            scores["volume"] = 15
        elif v >= 20_000:
            scores["volume"] = 10
        elif v >= 5_000:
            scores["volume"] = 5
        else:
            scores["volume"] = 0

        # 3. SMART / RETAIL RATIO (max 15)
        # Formula: ratio = whale_total_vol / max(total_all_vol, 1)
        # High ratio → market driven by smart money (good signal)
        ratio = market.smart_money_ratio
        if ratio >= 0.50:
            scores["sm_ratio"] = 15
        elif ratio >= 0.30:
            scores["sm_ratio"] = 12
        elif ratio >= 0.15:
            scores["sm_ratio"] = 8
        elif ratio >= 0.05:
            scores["sm_ratio"] = 4
        else:
            scores["sm_ratio"] = 0

        # 4. LIQUIDITY (max 10)
        liq = market.liquidity
        if liq >= 50_000:
            scores["liquidity"] = 10
        elif liq >= 25_000:
            scores["liquidity"] = 8
        elif liq >= 10_000:
            scores["liquidity"] = 5
        elif liq >= 5_000:
            scores["liquidity"] = 2
        else:
            scores["liquidity"] = 0

        # 5. ACTIVITY RECENCY (max 10)
        # Stale whale data ≠ current signal
        if wa and wa.last_trade_timestamp > 0:
            hours = wa.hours_since_last_trade
            if hours <= 1:
                scores["recency"] = 10
            elif hours <= 4:
                scores["recency"] = 8
            elif hours <= 12:
                scores["recency"] = 5
            elif hours <= 24:
                scores["recency"] = 3
            else:
                scores["recency"] = 0
        else:
            scores["recency"] = 0

        total = sum(scores.values())
        market.signal_score = min(total, 100)
        market.score_breakdown = scores

        # Determine recommended side
        if wa and wa.is_significant and wa.dominance_side != "NEUTRAL":
            market.recommended_side = wa.dominance_side
        else:
            # Fallback: use price momentum
            if market.yes_price > 0.5:
                market.recommended_side = "YES"
            elif market.no_price > 0.5:
                market.recommended_side = "NO"
            else:
                market.recommended_side = "YES" if market.price_change_24h >= 0 else "NO"

        # Signal strength
        s = market.signal_score
        if s >= 70:
            market.signal_strength = SignalStrength.STRONG_BUY
        elif s >= 55:
            market.signal_strength = SignalStrength.BUY
        elif s >= 40:
            market.signal_strength = SignalStrength.MODERATE
        elif s >= 25:
            market.signal_strength = SignalStrength.WEAK
        else:
            market.signal_strength = SignalStrength.AVOID

        # Market quality label
        if s >= 70 and liq >= 25_000 and market.whale_total_volume >= 5_000:
            market.market_quality = MarketQuality.HIGH_CONVICTION
        elif liq < 10_000:
            market.market_quality = MarketQuality.LOW_LIQUIDITY
        elif s >= 50:
            market.market_quality = MarketQuality.MODERATE_SIGNAL
        elif s >= 30:
            market.market_quality = MarketQuality.NOISY
        else:
            market.market_quality = MarketQuality.AVOID

    # =================================================================
    # RECOMMENDATION
    # =================================================================

    def generate_recommendation(self, market: MarketStats) -> BetRecommendation:
        """Generate betting recommendation from computed signal.
        
        New logic:
        - Always show a recommended side (YES/NO)
        - should_bet=True means confident recommendation
        - should_bet=False means risky but still shows side
        - Only truly unplayable markets get no side
        """
        should_bet = market.signal_score >= 40  # Lowered from 55
        side = market.recommended_side

        # Safety: don't recommend sides priced at ~0 or ~100
        if side == "YES" and market.yes_price <= 0.03:
            side = "NO" if market.no_price >= 0.05 else side
            if market.no_price < 0.05:
                should_bet = False
        elif side == "NO" and market.no_price <= 0.03:
            side = "YES" if market.yes_price >= 0.05 else side
            if market.yes_price < 0.05:
                should_bet = False

        price_resolved = False
        if market.yes_price >= 0.95 or market.no_price >= 0.95:
            should_bet = False
            price_resolved = True

        entry = market.yes_price if side == "YES" else market.no_price
        if entry <= 0.01:
            should_bet = False
            entry = max(entry, 0.01)

        target = min(0.92, entry * 1.30)
        stop = max(0.02, entry * 0.75)

        gain = target - entry
        loss = entry - stop
        rr = gain / loss if loss > 0 else 0

        # Reasons & warnings — use i18n key format for format_service to resolve
        reasons = []
        warnings = []
        wa = market.whale_analysis

        if price_resolved:
            # Price at 95¢+ means market is essentially resolved
            dominant = "YES" if market.yes_price >= 0.95 else "NO"
            pct = int(max(market.yes_price, market.no_price) * 100)
            warnings.append(f"⚠️ Market at {pct}¢ {dominant} — already resolved, no edge")

        if wa and wa.is_significant:
            if wa.dominance_side == side and wa.dominance_pct >= 60:
                reasons.append(
                    f"🐋 SM aligned ({wa.dominance_pct:.0f}% {side})"
                )
            elif wa.dominance_side != "NEUTRAL" and wa.dominance_side != side:
                warnings.append(
                    f"⚠️ SM against ({wa.dominance_side})"
                )
                rr *= 0.8
        else:
            warnings.append("⚠️ Limited SM data")

        vol_k = market.volume_24h / 1000
        if market.volume_24h >= 100_000:
            reasons.append(f"📈 High volume: ${vol_k:.0f}K/24h")
        elif market.volume_24h >= 30_000:
            reasons.append(f"📊 Moderate volume: ${vol_k:.0f}K")
        elif market.volume_24h >= 5_000:
            pass  # Acceptable volume, no warning needed
        else:
            warnings.append(f"⚠️ Low volume: ${vol_k:.0f}K")

        trend = market.price_change_24h
        if side == "NO":
            trend = -trend
        if trend > 0.10:
            reasons.append(f"📈 Strong trend: +{trend*100:.1f}%")
        elif trend > 0:
            reasons.append(f"📈 Positive trend: +{trend*100:.1f}%")
        elif trend > -0.05:
            pass  # Neutral trend, not a warning
        else:
            warnings.append(f"⚠️ Negative trend: {trend*100:.1f}%")

        if market.liquidity < 10_000:
            warnings.append("⚠️ Low liquidity — slippage risk")

        if market.days_to_close < 1:
            warnings.append("⚠️ Closes today!")
        elif market.days_to_close > 21:
            warnings.append("⚠️ Long term — capital locked")

        # EV analysis for cheap shares — this is the core value proposition
        # If you buy YES at 31¢ and it wins, you profit 69¢ per share (222% return)
        # If you buy NO at 31¢ and it wins, you profit 69¢ per share (222% return)
        if entry > 0 and entry < 0.50:
            potential_return = ((1.0 - entry) / entry) * 100
            reasons.append(f"💰 EV: +{potential_return:.0f}% if {side} wins at ${entry:.2f}")
        elif entry > 0 and entry < 0.70:
            potential_return = ((1.0 - entry) / entry) * 100
            if potential_return > 50:
                reasons.append(f"💰 Potential: +{potential_return:.0f}% return")

        # Smart decision: only block should_bet for truly critical issues
        # Don't block just because there are many minor warnings
        critical_warnings = sum(1 for w in warnings if 
            "resolved" in w.lower() or 
            "against" in w.lower()
        )
        if critical_warnings >= 1:
            should_bet = False

        # High signal score overrides minor warnings
        if market.signal_score >= 55 and not price_resolved:
            should_bet = True

        return BetRecommendation(
            market=market,
            should_bet=should_bet,
            side=side,
            confidence=market.signal_score,
            entry_price=entry,
            target_price=target,
            stop_loss_price=stop,
            risk_reward_ratio=rr,
            reasons=reasons,
            warnings=warnings,
        )


# Global instance
market_intelligence = MarketIntelligenceEngine()