"""
BetSpy Probability Converter

Converts the existing signal_score (0–100) + whale tilt + market price
into a calibrated model_probability that other modules can use.

This is the bridge between the existing scoring engine and the new
analytics modules (Kelly, Monte Carlo, Bayesian).

Formula:
    model_prob = market_price + edge_adjustment

    edge_adjustment is derived from:
    1. whale tilt direction & strength
    2. signal_score (higher score = more confidence in edge)
    3. smart money ratio (more whale activity = more trust)

    Clamped to [0.03, 0.97] to avoid extreme positions.
"""

from market_intelligence import MarketStats


def signal_to_probability(market: MarketStats) -> float:
    """
    Convert market signal data into a model probability for YES outcome.

    The model probability represents our ESTIMATE of the true probability,
    which may differ from the market price (that difference = edge).

    Returns:
        float in [0.03, 0.97] — estimated true probability of YES
    """
    base = market.yes_price  # market's current estimate
    wa = market.whale_analysis

    if not wa or not wa.is_significant:
        # No whale data → trust market price
        return _clamp(base)

    # --- Edge from whale tilt ---
    # tilt ∈ [-1, +1], where +1 = all whales on YES, -1 = all on NO
    # We scale this into a price adjustment
    tilt = wa.tilt

    # Confidence multiplier based on signal_score
    # score 0–30: low confidence → small adjustment
    # score 30–60: moderate → medium adjustment
    # score 60–100: high → full adjustment
    score = market.signal_score
    if score >= 70:
        confidence = 0.12  # max ±12% edge
    elif score >= 55:
        confidence = 0.08
    elif score >= 40:
        confidence = 0.05
    elif score >= 25:
        confidence = 0.03
    else:
        confidence = 0.01

    # Smart money ratio boost: if most volume is from whales, trust tilt more
    sm_ratio = market.smart_money_ratio
    if sm_ratio >= 0.5:
        confidence *= 1.3
    elif sm_ratio >= 0.3:
        confidence *= 1.1

    # Edge = tilt * confidence
    # tilt > 0 → whales favor YES → increase probability
    # tilt < 0 → whales favor NO → decrease probability
    edge = tilt * confidence

    model_prob = base + edge
    return _clamp(model_prob)


def calculate_edge(model_prob: float, market_price: float) -> float:
    """
    Calculate edge: difference between our estimate and market price.

    Positive edge = we think YES is underpriced (buy YES)
    Negative edge = we think YES is overpriced (buy NO)

    Returns:
        float — edge as absolute probability difference
    """
    return model_prob - market_price


def edge_percentage(model_prob: float, market_price: float) -> float:
    """
    Edge as percentage of market price.

    Example: model=0.63, market=0.55 → edge = 14.5%
    """
    if market_price <= 0:
        return 0.0
    return ((model_prob - market_price) / market_price) * 100


def recommended_side_from_prob(model_prob: float) -> str:
    """Which side to bet based on model probability."""
    if model_prob >= 0.55:
        return "YES"
    elif model_prob <= 0.45:
        return "NO"
    return "NEUTRAL"


def _clamp(p: float, lo: float = 0.03, hi: float = 0.97) -> float:
    return max(lo, min(hi, p))
