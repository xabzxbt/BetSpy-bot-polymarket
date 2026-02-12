"""
BetSpy Deep Analysis Orchestrator

The single entry point that runs ALL analytics modules on a market
and produces a unified DeepAnalysis result.

Flow:
    1. Fetch shared data (price history, crypto data, trades, holders) — in parallel
    2. Run all modules (Kelly, Greeks, Monte Carlo, Bayesian, Holders)
    3. Calculate consensus probability from all models
    4. Produce final recommendation

Usage:
    from analytics import run_deep_analysis
    result = await run_deep_analysis(market, bankroll=10000)
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from loguru import logger

from market_intelligence import MarketStats, HoldersAnalysis
from analytics.data_fetcher import data_fetcher, PriceHistory, CryptoData
from analytics.probability import signal_to_probability, calculate_edge
from analytics.kelly import KellyResult, calculate_kelly, DEFAULT_BANKROLL
from analytics.greeks import GreeksResult, calculate_greeks
from analytics.monte_carlo import (
    MonteCarloResult,
    detect_crypto_market,
    run_crypto_simulation,
    run_generic_simulation,
)
from analytics.bayesian import BayesianResult, bayesian_update
from analytics.holders_analysis import (
    calculate_side_stats,
    calculate_smart_score as calc_smart_score,
    HoldersAnalysisResult
)
from polymarket_api import PolymarketApiClient


# =====================================================================
# Result Classes
# =====================================================================

@dataclass
class DeepAnalysisResult:
    market: MarketStats
    rec_side: str
    confidence: int
    kelly_pct: float
    is_positive_setup: bool
    conflicts: list


class Orchestrator:
    """Deep analysis orchestrator with proper confidence calculation."""
    
    def __init__(self):
        self.base_kelly = 3.0  # Base 3% Kelly size

    def _calculate_confidence_and_sizing(
        self, market: MarketStats, rec_side: str, edge: float, model_prob: float, holders_res: Any
    ) -> Tuple[int, float, bool, List[Dict]]:
        """
        Standardized confidence and sizing logic.
        Returns: (confidence, kelly_pct, is_positive_setup, conflicts)
        """
        # 1. Base confidence from edge (up to 40 pts)
        edge_abs = abs(edge)
        conf_base = min(40, int(edge_abs * 500))  # 8% edge = 40 pts max
        
        # 2. Liquidity bonus (up to 10 pts)
        liq_bonus = min(10, int(market.liquidity / 10000))
        
        # 3. Time urgency bonus (up to 10 pts)
        time_bonus = 10 if market.days_to_close == 0 else (5 if market.days_to_close <= 2 else 0)
        
        # 4. Model Certainty (up to 10 pts)
        # Extreme probabilities provide more confidence in the direction
        prob = market.yes_price if rec_side == "YES" else market.no_price
        cert_bonus = 10 if (prob >= 0.80 or prob <= 0.20) else 0
        
        # 5. SMART CONFLICT HANDLING - Proportional penalty
        conf_smart = 0
        if holders_res:
             score = getattr(holders_res, "smart_score", 0)
             side = getattr(holders_res, "smart_score_side", "NEUTRAL")
             
             if side == rec_side:
                 conf_smart = score * 0.4
             elif score >= 80:
                 conf_smart = -min(50, score * 0.5)
             elif score >= 60:
                 conf_smart = -min(30, score * 0.3)
             elif score >= 40:
                 conf_smart = -20
             else:
                 conf_smart = -10
        
        # Calculate total confidence (clamped 5-95)
        conf_score = int(conf_base + conf_smart + liq_bonus + time_bonus + cert_bonus)
        conf_score = max(5, min(95, conf_score))
        
        # Determine if setup is positive
        is_positive_setup = conf_score >= 50
        
        # Check for strong smart money conflict (override)
        if holders_res:
            score = getattr(holders_res, "smart_score", 0)
            side = getattr(holders_res, "smart_score_side", "NEUTRAL")
            if score >= 80 and side not in ("NEUTRAL", rec_side):
                is_positive_setup = False
        
        # Dynamic sizing based on confidence
        k_safe = min(self.base_kelly, market.kelly_pct if hasattr(market, 'kelly_pct') else 2.0)
        
        if conf_score < 30:
            k_safe *= 0.3
        elif conf_score < 50:
            k_safe *= 0.6
        k_safe = round(k_safe, 1)
        
        # CRITICAL: Block BUY if size becomes too small
        if k_safe < 1.0:
            is_positive_setup = False
            
        # Conflicts
        conflicts = []
        if holders_res:
            score = getattr(holders_res, "smart_score", 0)
            side = getattr(holders_res, "smart_score_side", "NEUTRAL")
            if score >= 60 and side not in ("NEUTRAL", rec_side):
                conflicts.append({
                    "type": "SMART_MONEY",
                    "side": side,
                    "score": score,
                    "severity": "high" if score >= 80 else "medium"
                })
        
        return conf_score, k_safe, is_positive_setup, conflicts
    
    async def analyze_market(self, market: MarketStats) -> DeepAnalysisResult:
        """
        Deep analysis with corrected confidence calculation.
        Includes proportional smart conflict penalty.
        """
        # Note: Holders data is already on the market object in this model
        holders_res = getattr(market, "holders", None)
        
        # If missing, try to fetch (needed for Signal markets)
        if not holders_res:
            try:
                async with PolymarketApiClient() as client:
                    holders_data = await client.get_market_holders(market.condition_id)
                    if holders_data:
                        from analytics.holders_analysis import calculate_side_stats
                        yes_stats = calculate_side_stats(holders_data, "YES")
                        no_stats = calculate_side_stats(holders_data, "NO")
                        
                        # Simplified Smart Score calculation for quick analysis
                        yes_smart = yes_stats.smart_count_5k
                        no_smart = no_stats.smart_count_5k
                        
                        smart_side = "NEUTRAL"
                        smart_score = 50
                        if yes_smart > no_smart:
                            smart_side = "YES"
                            smart_score = min(100, 50 + (yes_smart - no_smart) * 10)
                        elif no_smart > yes_smart:
                            smart_side = "NO"
                            smart_score = min(100, 50 + (no_smart - yes_smart) * 10)
                        
                        holders_res = HoldersAnalysis(smart_score=smart_score, smart_score_side=smart_side)
                        market.holders = holders_res
            except Exception as e:
                logger.warning(f"Quick holders fetch failed: {e}")
                holders_res = HoldersAnalysis(smart_score=0, smart_score_side="NEUTRAL")

        # Use unified logic
        conf_score, k_safe, is_positive_setup, conflicts = self._calculate_confidence_and_sizing(
            market, market.rec_side, getattr(market, "effective_edge", 0.0), getattr(market, "model_prob", market.yes_price), holders_res
        )
        
        return DeepAnalysisResult(
            market=market,
            rec_side=market.rec_side,
            confidence=conf_score,
            kelly_pct=k_safe,
            is_positive_setup=is_positive_setup,
            conflicts=conflicts
        )


@dataclass
class DeepAnalysis:
    """Unified result from all analytics modules."""

    market: MarketStats

    # Probabilities
    market_price: float           # Current YES price
    model_probability: float      # Consensus from all models
    signal_probability: float     # From existing signal engine

    # Modules
    kelly: Optional[KellyResult] = None
    greeks: Optional[GreeksResult] = None
    monte_carlo: Optional[MonteCarloResult] = None
    bayesian: Optional[BayesianResult] = None
    holders: Optional[HoldersAnalysisResult] = None

    # Consensus
    recommended_side: str = "NEUTRAL"
    edge: float = 0.0
    confidence: int = 0           # 0–100

    # Errors (non-fatal, per module)
    errors: Dict[str, str] = field(default_factory=dict)

    @property
    def has_edge(self) -> bool:
        return abs(self.edge) >= 0.02

    @property
    def edge_pct(self) -> float:
        # Determine cost basis based on recommendation
        cost = self.market_price
        if self.recommended_side == "NO":
            cost = 1.0 - self.market_price
            
        if cost > 0:
            return (self.edge / cost) * 100
        return 0.0


# =====================================================================
# Orchestrator
# =====================================================================

async def run_deep_analysis(
    market: MarketStats,
    bankroll: float = DEFAULT_BANKROLL,
    kelly_fraction: float = 0.25,
) -> DeepAnalysis:
    """
    Run full deep analysis on a market.

    This is the main entry point. It:
    1. Fetches all required data in parallel
    2. Runs each analytics module (catching errors per-module)
    3. Computes consensus probability
    4. Returns a DeepAnalysis with everything from holders to Greek.

    Args:
        market: MarketStats from the existing intelligence engine
        bankroll: User's bankroll in USDC
        kelly_fraction: Kelly fraction (default 0.25 = Quarter Kelly)

    Returns:
        DeepAnalysis with all module results
    """
    errors: Dict[str, str] = {}

    # --- Signal probability (instant, no API call) ---
    try:
        signal_prob = signal_to_probability(market)
    except Exception:
        signal_prob = 0.5

    # --- Phase 1: Data fetching (parallel) ---
    price_history = PriceHistory()
    crypto_data = None
    trades = []
    holders_positions = ([], []) # (yes, no)

    # Determine which CLOB token ID to use for price history
    clob_id = market.clob_token_ids[0] if market.clob_token_ids else ""

    # Check if this is a crypto market
    crypto_info = detect_crypto_market(market.question)

    try:
        # Build fetch tasks
        tasks = {}

        if clob_id:
            tasks["price_history"] = data_fetcher.fetch_price_history(
                clob_id, interval="1w", fidelity=60,
            )

        if crypto_info:
            tasks["crypto"] = data_fetcher.fetch_crypto_data(crypto_info.coin_id)

        # Trades: use the existing data from whale analysis if available, 
        # otherwise fetch fresh
        tasks["trades"] = _fetch_trades(market)
        
        # Holders (New)
        async def _fetch_holders_task():
            async with PolymarketApiClient() as client:
                return await client.get_market_holders(
                    market.condition_id,
                    yes_price=market.yes_price,
                    no_price=market.no_price,
                )
        
        tasks["holders"] = _fetch_holders_task()

        # Run all fetches in parallel
        if tasks:
            keys = list(tasks.keys())
            results = await asyncio.gather(
                *tasks.values(), return_exceptions=True,
            )

            for key, result in zip(keys, results):
                if isinstance(result, Exception):
                    errors[f"fetch_{key}"] = str(result)
                    logger.warning(f"Fetch {key} failed: {result}")
                elif key == "price_history" and result:
                    price_history = result
                elif key == "crypto" and result:
                    crypto_data = result
                elif key == "trades" and result:
                    trades = result
                elif key == "holders" and result:
                    holders_positions = result
                    yes_h, no_h = result
                    logger.info(f"Market holders (Orchestrator): {len(yes_h)} YES, {len(no_h)} NO")
                    if not yes_h and not no_h:
                        logger.warning(f"No holders data for market {market.condition_id}. Check /holders endpoint.")

    except Exception as e:
        errors["data_fetch"] = str(e)
        logger.error(f"Data fetch phase failed: {e}")

    # --- Phase 2: Run modules ---

    # Greeks
    greeks_result = None
    try:
        greeks_result = calculate_greeks(
            yes_price=market.yes_price,
            days_remaining=market.days_to_close,
            price_history=price_history,
        )
    except Exception as e:
        errors["greeks"] = str(e)
        logger.warning(f"Greeks failed: {e}")

    # Monte Carlo
    mc_result = None
    try:
        if crypto_info and crypto_data and crypto_data.is_valid:
            mc_result = run_crypto_simulation(
                crypto=crypto_data,
                threshold=crypto_info.threshold,
                direction=crypto_info.direction,
                days=market.days_to_close,
                market_price=market.yes_price,
            )
        elif not price_history.is_empty:
            mc_result = run_generic_simulation(
                current_price=market.yes_price,
                days=market.days_to_close,
                price_history=price_history,
                market_price=market.yes_price,
            )
    except Exception as e:
        errors["monte_carlo"] = str(e)
        logger.warning(f"Monte Carlo failed: {e}")

    # Bayesian
    bayesian_result = None
    try:
        if trades:
            # Estimate average hourly volume from whale analysis
            avg_hourly_vol = 0.0
            wa = market.whale_analysis
            if wa and wa.window_hours > 0 and wa.total_volume > 0:
                avg_hourly_vol = wa.total_volume / wa.window_hours

            bayesian_result = bayesian_update(
                prior=market.yes_price,
                trades=trades,
                price_change_24h=market.price_change_24h,
                avg_hourly_volume=avg_hourly_vol,
            )
    except Exception as e:
        errors["bayesian"] = str(e)
        logger.warning(f"Bayesian failed: {e}")

    # --- Phase 3: Unified model probability ---
    # Uses Bayesian + MC only.
    model_prob = _compute_model_probability(
        mc_result=mc_result,
        bayesian_result=bayesian_result,
        market_price=market.yes_price,
    )
    
    # --- PROMPT REQUIREMENT 1: GUARDRAIL ---
    # If |model - market| < 2 p.p. => model confirms market => edge=0, Kelly=0, SKIP
    model_confirms_market = abs(model_prob - market.yes_price) < 0.02
    if model_confirms_market:
        model_prob = market.yes_price # Force equality to ensure edge=0

    # --- Phase 4: Edge & recommendation ---
    # 2 p.p. threshold
    EDGE_THRESHOLD = 0.02

    edge_yes = model_prob - market.yes_price
    edge_no = (1.0 - model_prob) - market.no_price  # = market.yes_price - model_prob
    # edge_no is effectively -edge_yes if using 1-p logic

    rec_side = "NEUTRAL"
    edge = 0.0

    if model_confirms_market:
        rec_side = "NEUTRAL"
        edge = 0.0
    elif edge_yes > EDGE_THRESHOLD and edge_yes > edge_no:
        rec_side = "YES"
        edge = edge_yes
    elif edge_no > EDGE_THRESHOLD and edge_no > edge_yes:
        rec_side = "NO"
        edge = edge_no
    else:
        # Both small or negative
        rec_side = "NEUTRAL"
        edge = 0.0

    # --- Phase 5: Kelly ---
    kelly_result = None
    try:
        # Calculate strictly based on the model vs market
        # Note: calculate_kelly internally handles edge calculation
        kelly_result = calculate_kelly(
            model_prob=model_prob,
            market_price=market.yes_price,
            bankroll=bankroll,
            fraction=kelly_fraction,
            days_to_resolve=market.days_to_close,
        )
    except Exception as e:
        errors["kelly"] = str(e)
        logger.warning(f"Kelly failed: {e}")

    # Force Kelly to 0 when there's no edge (guardrail)
    if rec_side == "NEUTRAL":
        if kelly_result:
            kelly_result.kelly_final_pct = 0.0
            kelly_result.kelly_full = 0.0
            kelly_result.kelly_time_adj_pct = 0.0
    
    # Fix bug: Kelly calculator might return positive stake for negative edge if inputs wrong
    if edge <= 0:
         if kelly_result: 
            kelly_result.kelly_final_pct = 0.0
            kelly_result.kelly_full = 0.0

    # Holders Analysis (Phase 2.5 inserted here)
    holders_res = None
    
    try:
        from types import SimpleNamespace
        
        yes_holders, no_holders = holders_positions
        
        # Changed from 5000 to 3000 per user request
        SMART_PNL_THRESHOLD = 3000 
        
        def _calc_holder_stats(positions, side: str):
            if not positions:
                return SimpleNamespace(
                    side=side,
                    count=0,
                    median_pnl=0.0,
                    smart_count_5k=0,
                    profitable_pct=0.0,
                    top_holder_profit=0.0,
                    top_holder_address="",
                    top_holder_wins=0,
                    top_holder_losses=0,
                    # Added for compatibility with existing SideStats if needed
                    profitable_count=0,
                    above_5k_count=0,
                    above_10k_count=0,
                    above_50k_count=0,
                    smart_count_10k=0
                )

            # Calculate stats from enriched positions
            # holder_lifetime_pnl is populated in get_market_holders
            pnls = [getattr(p, "holder_lifetime_pnl", 0.0) for p in positions]
            pnls = [x for x in pnls if x is not None] # Safety check
            
            if not pnls:
                 median = 0.0
            else:
                 pnls_sorted = sorted(pnls)
                 median = pnls_sorted[len(pnls_sorted) // 2]

            # Smart Money (Lifetime Profit > 3k)
            smart_3k = sum(1 for p in positions if getattr(p, "holder_lifetime_pnl", 0.0) >= SMART_PNL_THRESHOLD)
            
            # Profitable %
            profitable = sum(1 for p in positions if getattr(p, "holder_lifetime_pnl", 0.0) > 0)
            profitable_pct = (profitable / len(positions)) * 100 if positions else 0.0

            # Top holder by PnL
            top = max(positions, key=lambda p: getattr(p, "holder_lifetime_pnl", 0.0))
            top_profit = getattr(top, "holder_lifetime_pnl", 0.0)
            top_addr = getattr(top, "wallet_address", getattr(top, "proxy_wallet", ""))

            # Extra stats matching SideStats
            above_10k = sum(1 for p in positions if getattr(p, "current_value", 0.0) > 10000)
            
            return SimpleNamespace(
                side=side,
                count=len(positions),
                median_pnl=median,
                smart_count_5k=smart_3k, # Field name kept for compatibility, but logic is >3k
                profitable_pct=profitable_pct,
                top_holder_profit=top_profit,
                top_holder_address=top_addr,
                top_holder_wins=0,
                top_holder_losses=0,
                # Extra fields for formatter compatibility
                above_10k_count=above_10k,
                above_5k_pct=(smart_3k/len(positions)*100) if positions else 0.0 # metric for smart money
            )

        yes_stats_obj = _calc_holder_stats(yes_holders, "YES")
        no_stats_obj = _calc_holder_stats(no_holders, "NO")
        
        # Calculate Smart Score
        # Simple Logic as requested
        yes_smart = yes_stats_obj.smart_count_5k
        no_smart = no_stats_obj.smart_count_5k
        
        wa = market.whale_analysis
        
        # Base score on smart holder count difference
        smart_side = "NEUTRAL"
        smart_score = 50
        
        if yes_smart > no_smart:
            smart_side = "YES"
            diff = yes_smart - no_smart
            smart_score = min(100, 50 + diff * 10)
        elif no_smart > yes_smart:
             smart_side = "NO"
             diff = no_smart - yes_smart
             smart_score = min(100, 50 + diff * 10)
             
        # Breakdown
        smart_score_breakdown = {
            "holders": float(smart_score * 0.4),
            "tilt": float(abs(wa.tilt) * 100 * 0.3) if wa else 0.0,
            "model": 0.0 # simplified
        }

        # Build final object for DeepAnalysis.holders
        holders_res = SimpleNamespace(
            yes_stats=yes_stats_obj,
            no_stats=no_stats_obj,
            smart_score=smart_score,
            smart_score_side=smart_side,
            smart_score_breakdown=smart_score_breakdown
        )
        
        logger.info(f"Holders Analysis Computed: YES Smart={yes_smart}, NO Smart={no_smart}, Score={smart_side} {smart_score}")

    except Exception as e:
        logger.warning(f"Holders analysis failed: {e}")
        errors["holders"] = str(e)
        import traceback
        logger.debug(traceback.format_exc())


    # Phase 6: Confidence (Unified Logic)
    orch = Orchestrator()
    confidence, k_safe, is_positive_setup_final, conflicts_list = orch._calculate_confidence_and_sizing(
        market, rec_side, edge, model_prob, holders_res
    )

    # Log confidence components for debugging as requested
    logger.info(
        f"Confidence calc for {market.slug}: final={confidence}, "
        f"rec_side={rec_side}, "
        f"holders_side={getattr(holders_res, 'smart_score_side', 'None')}, "
        f"smart_score={getattr(holders_res, 'smart_score', 0)}"
    )

    return DeepAnalysis(
        market=market,
        market_price=market.yes_price,
        model_probability=model_prob,
        signal_probability=signal_prob,
        kelly=kelly_result,
        greeks=greeks_result,
        monte_carlo=mc_result,
        bayesian=bayesian_result,
        holders=holders_res,
        recommended_side=rec_side,
        edge=edge,
        confidence=confidence,
        errors=errors,
    )


# =====================================================================
# Helpers
# =====================================================================

def _compute_model_probability(
    mc_result: Optional[MonteCarloResult],
    bayesian_result: Optional[BayesianResult],
    market_price: float,
) -> float:
    """
    Compute a single unified model_yes_prob from Bayesian + MC results.
    """
    bayes_posterior = market_price
    bayes_shift = 0.0

    if bayesian_result:
        bayes_posterior = bayesian_result.posterior
        bayes_shift = abs(bayes_posterior - bayesian_result.prior)

    # MC probability
    mc_prob = market_price
    if mc_result:
        mc_prob = mc_result.probability_yes

    # Decision: does the model have independent signal?
    if bayes_shift >= 0.02:
        # Bayesian detected meaningful evidence → blend with MC
        model_prob = 0.7 * bayes_posterior + 0.3 * mc_prob
    else:
        # No meaningful Bayesian shift → model confirms market price
        model_prob = market_price

    return max(0.01, min(0.99, model_prob))


async def _fetch_trades(market: MarketStats) -> List[Dict[str, Any]]:
    """Fetch recent trades for Bayesian analysis."""
    try:
        from analytics.data_fetcher import data_fetcher as df
        data = await df._get(
            f"{df.DATA_API_URL}/trades",
            {"market": market.condition_id, "limit": "500"},
        )
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []
