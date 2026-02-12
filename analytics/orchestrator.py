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

from market_intelligence import MarketStats
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
# Result
# =====================================================================

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
    holders_positions = []

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
        yes_stats = calculate_side_stats(holders_positions, "YES")
        no_stats = calculate_side_stats(holders_positions, "NO")
        
        # Calculate Smart Score
        # We need model probability for the score logic
        s_score, s_side, s_breakdown = calc_smart_score(
            yes_stats, no_stats, market.whale_analysis, model_prob
        )
        
        holders_res = HoldersAnalysisResult(
            yes_stats=yes_stats,
            no_stats=no_stats,
            smart_score=s_score,
            smart_score_side=s_side,
            smart_score_breakdown=s_breakdown
        )
    except Exception as e:
        logger.warning(f"Holders analysis failed: {e}")
        errors["holders"] = str(e)


    # --- Phase 6: Confidence ---
    # Update confidence logic to include Smart Score
    
    if rec_side == "NEUTRAL":
        # Model confirms market (SKIP)
        confidence = 65
        if model_confirms_market:
            confidence = 75
        if holders_res and holders_res.smart_score > 70:
             # If holders analysis sees something strongly but model is neutral
             pass
    else:
        # BUY scenario
        # Base confidence from Edge
        conf_base = min(50, abs(edge) * 100 * 5)  # |edge|*5, e.g. 5% edge -> 25pts
        
        # Smart Score influence (0-100)
        # If score aligns with side
        conf_smart = 0
        if holders_res:
             if holders_res.smart_score_side == rec_side:
                 conf_smart = holders_res.smart_score * 0.4 # up to 40pts
             else:
                 conf_smart = -10 # Penalty if smart score disagrees
        
        # Liquidity factor
        conf_liq = 0
        if market.liquidity >= 50000: conf_liq = 10
        elif market.liquidity >= 10000: conf_liq = 5
        
        # Model certainty
        conf_cert = 10 if (model_prob >= 0.60 or model_prob <= 0.40) else 0

        confidence = int(min(95, conf_base + conf_smart + conf_liq + conf_cert))
        if confidence < 10: confidence = 10

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
