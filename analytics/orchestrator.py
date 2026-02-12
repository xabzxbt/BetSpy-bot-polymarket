"""
BetSpy Deep Analysis Orchestrator

The single entry point that runs ALL analytics modules on a market
and produces a unified DeepAnalysis result.

Flow:
    1. Fetch shared data (price history, crypto data, trades) — in parallel
    2. Run all modules (Kelly, Greeks, Monte Carlo, Bayesian)
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
    4. Returns a DeepAnalysis with everything

    Args:
        market: MarketStats from the existing intelligence engine
        bankroll: User's bankroll in USDC
        kelly_fraction: Kelly fraction (default 0.25 = Quarter Kelly)

    Returns:
        DeepAnalysis with all module results
    """
    errors: Dict[str, str] = {}

    # --- Signal probability (instant, no API call) ---
    signal_prob = signal_to_probability(market)

    # --- Phase 1: Data fetching (parallel) ---
    price_history = PriceHistory()
    crypto_data = None
    trades = []

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
    # Uses Bayesian + MC only (no signal_prob which was biased by whale tilt).
    # This prevents the contradiction where signal_prob=24% but MC/Bayes=13-14%.
    model_prob = _compute_model_probability(
        mc_result=mc_result,
        bayesian_result=bayesian_result,
        market_price=market.yes_price,
    )

    # --- Phase 4: Edge & recommendation ---
    # 2 p.p. threshold (down from 3) as requested
    EDGE_THRESHOLD = 0.02

    edge_yes = model_prob - market.yes_price
    edge_no = -edge_yes  # symmetric: (1-model) - (1-market) = market - model

    if edge_yes > EDGE_THRESHOLD:
        rec_side = "YES"
        edge = edge_yes
    elif edge_no > EDGE_THRESHOLD:
        rec_side = "NO"
        edge = edge_no
    else:
        # Guardrail: model ≈ market → no edge → SKIP
        rec_side = "NEUTRAL"
        edge = 0.0

    # --- Phase 5: Kelly (uses unified model_prob) ---
    kelly_result = None
    try:
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
    if rec_side == "NEUTRAL" and kelly_result and kelly_result.kelly_final_pct > 0:
        kelly_result = calculate_kelly(
            model_prob=market.yes_price,  # force model=market → edge=0 → Kelly=0
            market_price=market.yes_price,
            bankroll=bankroll,
            fraction=kelly_fraction,
            days_to_resolve=market.days_to_close,
        )

    # --- Phase 6: Confidence ---
    # When model ≈ market (SKIP), confidence reflects certainty that there is NO edge
    if rec_side == "NEUTRAL":
        # High confidence that edge is absent (60-80 range)
        confidence = 65
        if bayesian_result and abs(bayesian_result.posterior - bayesian_result.prior) < 0.02:
            confidence = 75  # Bayesian explicitly confirms market
        if mc_result and abs(mc_result.edge) < 0.02:
            confidence = min(80, confidence + 5)  # MC also confirms
    else:
        # BUY scenario: confidence reflects conviction in the edge
        conf_base = min(50, abs(edge) * 100 * 10)  # |edge_pp| * 10, max 50
        conf_whale = 0
        wa = market.whale_analysis
        if wa and wa.is_significant and wa.dominance_side == rec_side:
            conf_whale = 25
        conf_liq = 0
        if market.liquidity >= 50000:
            conf_liq = 15
        elif market.liquidity >= 10000:
            conf_liq = 10
        elif market.liquidity >= 2000:
            conf_liq = 5
        conf_cert = 10 if (model_prob >= 0.60 or model_prob <= 0.40) else 0
        confidence = int(min(95, conf_base + conf_whale + conf_liq + conf_cert))

    return DeepAnalysis(
        market=market,
        market_price=market.yes_price,
        model_probability=model_prob,
        signal_probability=signal_prob,
        kelly=kelly_result,
        greeks=greeks_result,
        monte_carlo=mc_result,
        bayesian=bayesian_result,
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

    Logic:
    - If Bayesian moved significantly (|posterior - prior| >= 2 p.p.):
        model_prob = 0.7 * bayes_posterior + 0.3 * mc_prob
        (Bayesian is primary, MC provides baseline support)
    - If Bayesian barely moved (|posterior - prior| < 2 p.p.):
        Model confirms market → model_prob ≈ market_price
        This forces edge ≈ 0 → Kelly = 0 → SKIP

    The old signal_to_probability (whale-tilt-based) is intentionally excluded
    because it can produce inflated probabilities (e.g. 24%) that contradict
    the actual model outputs (MC=13%, Bayes=14%), causing the Pisa-type bug.
    """
    bayes_posterior = market_price
    bayes_shift = 0.0

    if bayesian_result:
        bayes_posterior = bayesian_result.posterior
        bayes_shift = abs(bayes_posterior - bayesian_result.prior)

    # MC probability (for generic markets this equals market_price)
    mc_prob = market_price
    if mc_result:
        mc_prob = mc_result.probability_yes

    # Decision: does the model have independent signal?
    if bayes_shift >= 0.02:
        # Bayesian detected meaningful evidence → blend with MC
        model_prob = 0.7 * bayes_posterior + 0.3 * mc_prob
    else:
        # No meaningful Bayesian shift → model confirms market price
        # This prevents phantom edges from whale-tilt inflation
        model_prob = market_price

    return max(0.03, min(0.97, model_prob))


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
