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


class TimeFrame(Enum):
    """Supported time frames for events."""
    TODAY = "today"          # Closes within 24 hours
    DAYS_2 = "2days"         # Closes in 1-2 days
    DAYS_3 = "3days"         # Closes in 2-3 days
    WEEK = "week"            # Closes in 3-7 days
    MONTH = "month"          # Closes in 7-30 days


class Category(Enum):
    """Supported market categories."""
    SPORTS = "sports"
    CRYPTO = "crypto"
    ESPORTS = "esports"
    TRENDING = "trending"
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
    
    # Price history
    price_24h_ago: float = 0.0
    price_7d_ago: float = 0.0
    
    # Computed scores
    whale_consensus: float = 0.0  # 0-1, >0.5 = YES, <0.5 = NO
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
    WHALE_THRESHOLD = 5000
    
    # Minimum volume to consider a market
    MIN_VOLUME_24H = 10000
    
    # Category tag mappings
    CATEGORY_TAGS = {
        Category.SPORTS: ["sports", "nfl", "nba", "mlb", "nhl", "soccer", "football", 
                         "basketball", "baseball", "hockey", "tennis", "mma", "ufc",
                         "boxing", "golf", "f1", "racing"],
        Category.CRYPTO: ["crypto", "bitcoin", "btc", "ethereum", "eth", "solana", 
                         "sol", "cryptocurrency", "defi", "nft", "blockchain"],
        Category.ESPORTS: ["esports", "gaming", "cs2", "csgo", "dota", "dota2", 
                          "league of legends", "lol", "valorant", "overwatch",
                          "counter-strike", "call of duty", "fortnite"],
    }
    
    def __init__(self):
        self.gamma_api_url = "https://gamma-api.polymarket.com"
        self.data_api_url = "https://data-api.polymarket.com"
        self.clob_api_url = "https://clob.polymarket.com"
        
        # Increased rate limit: 60 requests per minute (was 20)
        self._limiter = AsyncLimiter(60, 60)
        self._session: Optional[aiohttp.ClientSession] = None
    
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
                if category != Category.ALL and category != Category.TRENDING:
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
                    if category != Category.ALL and category != Category.TRENDING:
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
    
    async def _parse_market(self, data: Dict) -> Optional[MarketStats]:
        """Parse market data from API response."""
        try:
            # Parse end date
            end_date_str = data.get("endDate") or data.get("end_date_iso")
            if not end_date_str:
                return None
            
            # Handle various date formats
            try:
                if "T" in end_date_str:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                else:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            except:
                return None
            
            # Make end_date timezone-naive for comparison
            if end_date.tzinfo is not None:
                end_date = end_date.replace(tzinfo=None)
            
            now = datetime.utcnow()
            if end_date < now:
                return None  # Already closed
            
            days_to_close = (end_date - now).days
            
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
                volume_change_pct=0.0,  # Will be calculated
                liquidity=liquidity,
                end_date=end_date,
                days_to_close=days_to_close,
                category=category,
                tags=tags,
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
        
        # Fetch recent trades for whale analysis
        trades = await self._fetch_market_trades(market.condition_id)
        
        whale_yes_vol = 0.0
        whale_no_vol = 0.0
        whale_yes_count = 0
        whale_no_count = 0
        retail_yes_vol = 0.0
        retail_no_vol = 0.0
        
        for trade in trades:
            amount = trade.get("usdcSize", 0) or trade.get("size", 0)
            if not amount:
                continue
            
            amount = float(amount)
            side = trade.get("side", "").upper()
            outcome_index = trade.get("outcomeIndex", 0)
            
            # Determine if YES or NO based on side and outcome
            is_yes = (side == "BUY" and outcome_index == 0) or (side == "SELL" and outcome_index == 1)
            
            if amount >= self.WHALE_THRESHOLD:
                if is_yes:
                    whale_yes_vol += amount
                    whale_yes_count += 1
                else:
                    whale_no_vol += amount
                    whale_no_count += 1
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
            market.whale_consensus = 0.5  # Neutral
        
        # Fetch price history
        price_history = await self._fetch_price_history(market.condition_id)
        if price_history:
            market.price_24h_ago = price_history.get("price_24h", market.yes_price)
            market.price_7d_ago = price_history.get("price_7d", market.yes_price)
        
        return market
    
    async def _fetch_market_trades(self, condition_id: str, limit: int = 500) -> List[Dict]:
        """Fetch recent trades for a market."""
        if not condition_id:
            return []
        
        # Try the activity endpoint first (more reliable)
        url = f"{self.data_api_url}/activity"
        params = {
            "market": condition_id,
            "limit": limit,
        }
        
        data = await self._request(url, params)
        if data and isinstance(data, list):
            return data
        
        # Fallback to trades endpoint
        url = f"{self.data_api_url}/trades"
        params = {
            "market": condition_id,
            "limit": limit,
        }
        
        data = await self._request(url, params)
        return data if isinstance(data, list) else []
    
    async def _fetch_price_history(self, condition_id: str) -> Dict:
        """Fetch price history for a market."""
        # Try to get historical prices from timeseries endpoint
        url = f"{self.clob_api_url}/prices-history"
        params = {
            "market": condition_id,
            "interval": "1d",
            "fidelity": 60,  # minutes
        }
        
        data = await self._request(url, params)
        
        result = {}
        if data and isinstance(data, list) and len(data) > 0:
            prices = data
            if len(prices) >= 24:
                result["price_24h"] = float(prices[-24].get("price", 0.5))
            if len(prices) >= 168:  # 7 days
                result["price_7d"] = float(prices[-168].get("price", 0.5))
        
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
        # If whale consensus < 0.5, we should bet NO
        if market.whale_consensus >= 0.5:
            market.recommended_side = "YES"
            adjusted_score = total_score
        else:
            market.recommended_side = "NO"
            # Recalculate score for NO side
            adjusted_score = total_score
        
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
        """Calculate whale consensus score (max 40 points)."""
        total_whale = market.whale_total_volume
        
        if total_whale < 10000:
            return 10  # Not enough whale data
        
        consensus = market.whale_consensus
        
        # Strong consensus in either direction is good
        deviation_from_neutral = abs(consensus - 0.5)
        
        if deviation_from_neutral >= 0.30:  # 80%+ on one side
            return 40
        elif deviation_from_neutral >= 0.20:  # 70%+
            return 32
        elif deviation_from_neutral >= 0.15:  # 65%+
            return 26
        elif deviation_from_neutral >= 0.10:  # 60%+
            return 20
        else:
            return 12  # No clear consensus
    
    def _calc_volume_score(self, market: MarketStats) -> float:
        """Calculate volume momentum score (max 20 points)."""
        vol_24h = market.volume_24h
        
        # Based on absolute volume (higher = more interest)
        if vol_24h >= 500000:
            return 20
        elif vol_24h >= 200000:
            return 17
        elif vol_24h >= 100000:
            return 14
        elif vol_24h >= 50000:
            return 11
        elif vol_24h >= 20000:
            return 8
        else:
            return 5
    
    def _calc_trend_score(self, market: MarketStats) -> float:
        """Calculate price trend score (max 20 points)."""
        change_24h = market.price_change_24h
        change_7d = market.price_change_7d
        
        # For the recommended side, we want positive momentum
        # But not too fast (might be overbought)
        
        # Get trend aligned with whale consensus
        if market.whale_consensus < 0.5:
            # Whales favor NO, so price dropping is good
            change_24h = -change_24h
            change_7d = -change_7d
        
        # Ideal: steady upward trend (5-15% in 24h)
        if 0.05 <= change_24h <= 0.15 and change_7d > 0:
            return 20  # Perfect trend
        elif 0.02 <= change_24h <= 0.20 and change_7d >= 0:
            return 16  # Good trend
        elif change_24h > 0.25:
            return 10  # Too fast, might reverse
        elif change_24h > 0:
            return 14  # Positive but weak
        elif change_24h > -0.05:
            return 10  # Flat
        else:
            return 6   # Downtrend against position
    
    def _calc_liquidity_score(self, market: MarketStats) -> float:
        """Calculate liquidity score (max 10 points)."""
        liq = market.liquidity
        
        if liq >= 100000:
            return 10
        elif liq >= 50000:
            return 8
        elif liq >= 20000:
            return 6
        elif liq >= 10000:
            return 4
        else:
            return 2
    
    def _calc_time_score(self, market: MarketStats) -> float:
        """Calculate time value score (max 10 points)."""
        days = market.days_to_close
        
        # Sweet spot: 2-14 days
        # Not too short (can't enter/exit)
        # Not too long (capital locked)
        
        if 2 <= days <= 7:
            return 10  # Ideal short-term
        elif 7 < days <= 14:
            return 9
        elif 1 <= days < 2:
            return 7   # Very short, risky
        elif 14 < days <= 21:
            return 7
        elif 21 < days <= 30:
            return 5
        elif days < 1:
            return 3   # Too close to expiry
        else:
            return 4   # Too far out
    
    # ==================== RECOMMENDATION ====================
    
    def generate_recommendation(self, market: MarketStats) -> BetRecommendation:
        """Generate detailed betting recommendation."""
        should_bet = market.signal_score >= 60
        side = market.recommended_side
        
        # Entry price (current price)
        if side == "YES":
            entry_price = market.yes_price
            # Target: move toward 0.70-0.85 range
            target_price = min(0.85, entry_price * 1.3)
            # Stop loss: 15-20% below entry
            stop_loss_price = max(0.05, entry_price * 0.80)
        else:
            entry_price = market.no_price
            target_price = min(0.85, entry_price * 1.3)
            stop_loss_price = max(0.05, entry_price * 0.80)
        
        # Risk/Reward ratio
        potential_gain = target_price - entry_price
        potential_loss = entry_price - stop_loss_price
        risk_reward = potential_gain / potential_loss if potential_loss > 0 else 0
        
        # Build reasons
        reasons = []
        warnings = []
        
        # Whale analysis
        whale_pct = market.whale_consensus if side == "YES" else (1 - market.whale_consensus)
        whale_pct_str = f"{whale_pct*100:.0f}%"
        
        if whale_pct >= 0.75:
            reasons.append(f"🐋 Сильний консенсус китів: {whale_pct_str} на {side}")
        elif whale_pct >= 0.60:
            reasons.append(f"🐋 Помірний консенсус китів: {whale_pct_str} на {side}")
        else:
            warnings.append(f"⚠️ Слабкий консенсус китів: {whale_pct_str}")
        
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
            reasons.append(f"📈 Позитивний тренд: +{trend*100:.1f}% за 24h")
        elif trend > -0.05:
            warnings.append("⚠️ Слабкий тренд")
        else:
            warnings.append(f"⚠️ Негативний тренд: {trend*100:.1f}%")
        
        # Liquidity
        if market.liquidity < 20000:
            warnings.append("⚠️ Низька ліквідність — складно вийти")
        
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
