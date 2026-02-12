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
from analytics.bayesian import BayesianResult, bayesian_update_with_holders, detect_smart_money_score
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
                    limit=100,  # "Rocket Mode": Top 100 is enough for Smart Money analysis
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

    # --- Phase 2: Holders Analysis (Moved Up) ---
    holders_res = None
    smart_score = 50.0
    smart_side = "NEUTRAL"
    
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
                    profitable_count=0,
                    above_10k_count=0,
                    above_5k_pct=0.0, 
                    veteran_count=0,
                    novoreg_count=0
                )
            
            # Novoreg Analysis
            import time
            now_ts = int(time.time())
            thirty_days = 30 * 24 * 60 * 60
            
            veterans = 0
            novoregs = 0
            
            # Filter analyzed positions
            analyzed_positions = [p for p in positions if getattr(p, "holder_first_trade_timestamp", 0) > 0]

            for p in analyzed_positions:
                ts = getattr(p, "holder_first_trade_timestamp", 0)
                if ts > 0:
                    age = now_ts - ts
                    if age >= thirty_days:
                        veterans += 1
                    else:
                        novoregs += 1

            # Smart Money (Lifetime Profit > 3k)
            smart_3k = sum(1 for p in analyzed_positions if getattr(p, "holder_lifetime_pnl", 0.0) >= SMART_PNL_THRESHOLD)
            
            # Profitable %
            if analyzed_positions:
                profitable = sum(1 for p in analyzed_positions if getattr(p, "holder_lifetime_pnl", 0.0) > 0)
                profitable_pct = (profitable / len(analyzed_positions)) * 100
            else:
                profitable_pct = 0.0

            # Top holder
            if analyzed_positions:
                top = max(analyzed_positions, key=lambda p: getattr(p, "holder_lifetime_pnl", 0.0))
                top_profit = getattr(top, "holder_lifetime_pnl", 0.0)
                top_addr = getattr(top, "wallet_address", getattr(top, "proxy_wallet", ""))
            else:
                top_profit = 0.0
                top_addr = ""

            # Extra stats
            above_10k = sum(1 for p in positions if getattr(p, "current_value", 0.0) > 10000)
            
            return SimpleNamespace(
                side=side,
                count=len(positions),
                median_pnl=0.0, # Removed computational burden
                smart_count_5k=smart_3k,
                profitable_pct=profitable_pct,
                top_holder_profit=top_profit,
                top_holder_address=top_addr,
                top_holder_wins=0,
                top_holder_losses=0,
                above_10k_count=above_10k,
                above_5k_pct=(smart_3k/len(positions)*100) if positions else 0.0,
                veteran_count=veterans,
                novoreg_count=novoregs
            )

        yes_stats_obj = _calc_holder_stats(yes_holders, "YES")
        no_stats_obj = _calc_holder_stats(no_holders, "NO")
        
        # Calculate Smart Score
        yes_smart = yes_stats_obj.smart_count_5k
        no_smart = no_stats_obj.smart_count_5k
        
        wa = market.whale_analysis
        
        # Base score on smart holder count difference
        if yes_smart > no_smart:
            smart_side = "YES"
            diff = yes_smart - no_smart
            smart_score = min(100, 50 + diff * 10)
        elif no_smart > yes_smart:
            smart_side = "NO"
            diff = no_smart - yes_smart
            smart_score = min(100, 50 + diff * 10)
        else:
            smart_score = 50.0
            smart_side = "NEUTRAL"
            
        # Breakdown
        smart_score_breakdown = {
            "holders": float(smart_score * 0.4),
            "tilt": float(abs(wa.tilt) * 100 * 0.3) if wa else 0.0,
            "model": 0.0 
        }

        holders_res = SimpleNamespace(
            yes_stats=yes_stats_obj,
            no_stats=no_stats_obj,
            smart_score=smart_score,
            smart_score_side=smart_side,
            smart_score_breakdown=smart_score_breakdown
        )
        
        logger.info(f"Holders Analysis Computed: Score={smart_side} {smart_score}")

    except Exception as e:
        logger.warning(f"Holders analysis failed: {e}")
        errors["holders"] = str(e)

    # --- Phase 3: Bayesian Update (uses Holders Evidence) ---
    bayesian_result = None
    try:
        if trades:
            avg_hourly_vol = 0.0
            wa = market.whale_analysis
            if wa and wa.window_hours > 0 and wa.total_volume > 0:
                avg_hourly_vol = wa.total_volume / wa.window_hours

            bayesian_result = bayesian_update_with_holders(
                prior=market.yes_price,
                trades=trades,
                price_change_24h=market.price_change_24h,
                avg_hourly_volume=avg_hourly_vol,
                smart_score=smart_score,
                smart_side=smart_side,
            )
    except Exception as e:
        errors["bayesian"] = str(e)
        logger.warning(f"Bayesian failed: {e}")
        
    # --- Phase 4: Monte Carlo (Seeded with Bayesian Posterior) ---
    # Determine base probability for MC
    base_prob_for_mc = market.yes_price
    if bayesian_result:
        base_prob_for_mc = bayesian_result.posterior

    mc_result = None
    try:
        if crypto_info and crypto_data and crypto_data.is_valid:
            # Crypto simulation (GBM) ignores base_probability as it uses fundamental price
            mc_result = run_crypto_simulation(
                crypto=crypto_data,
                threshold=crypto_info.threshold,
                direction=crypto_info.direction,
                days=market.days_to_close,
                market_price=market.yes_price,
            )
        elif not price_history.is_empty:
            # Generic simulation uses base_probability as center
            mc_result = run_generic_simulation(
                current_price=market.yes_price,
                days=market.days_to_close,
                price_history=price_history,
                market_price=market.yes_price,
                base_probability=base_prob_for_mc, # NEW: Seed with Posterior
            )
    except Exception as e:
        errors["monte_carlo"] = str(e)
        logger.warning(f"Monte Carlo failed: {e}")

    # --- Phase 5: Unified Probability & Decision ---
    
    # If Crypto: Blend MC (Fundamental) and Bayesian (Whale)
    if crypto_info and mc_result and bayesian_result:
        # 60% Fundamental, 40% Whale
        model_prob = (0.6 * mc_result.probability_yes) + (0.4 * bayesian_result.posterior)
    
    # If Generic: MC result IS the refined Bayesian posterior (with volatility)
    elif mc_result:
        model_prob = mc_result.probability_yes
        
    # Fallback
    elif bayesian_result:
        model_prob = bayesian_result.posterior
    else:
        model_prob = market.yes_price

    model_prob = max(0.01, min(0.99, model_prob))

    # --- Phase 6: Edge & recommendation ---
    EDGE_THRESHOLD = 0.005 # 0.5% edge (aligned with Kelly)

    edge_yes = model_prob - market.yes_price
    edge_no = (1.0 - model_prob) - market.no_price  # = market.yes_price - model_prob
    # edge_no is effectively -edge_yes if using 1-p logic

    rec_side = "NEUTRAL"
    edge = 0.0

    if False: # Removed guardrail
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

    # Removed artificial Kelly zeroing logic
    # if edge <= 0: ...


    # Removed old Holders Analysis Block 
    # (It is now computed earlier in Phase 2)


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
