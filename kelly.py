"""
BetSpy Kelly Criterion — Optimal Position Sizing

The Kelly Criterion answers: "How much of my bankroll should I bet?"

Formula:
    f* = (b × p - q) / b

    where:
        p = estimated probability of winning (model_probability)
        q = 1 - p = probability of losing
        b = net odds received on the bet = (1 / entry_price) - 1
        f* = fraction of bankroll to wager

    Example:
        Model says YES = 63%, market price = 55¢
        b = (1/0.55) - 1 = 0.818
        f* = (0.818 * 0.63 - 0.37) / 0.818 = 0.178 (17.8%)
        With Quarter Kelly: 0.178 * 0.25 = 4.5% of bankroll

    We use fractional Kelly (default Quarter) because:
    - Full Kelly is too aggressive for imperfect probability estimates
    - Quarter Kelly provides ~75% of growth with ~50% less variance
    - Protects against model errors

Safety rules:
    - Never bet more than MAX_POSITION_PCT (10%) on a single market
    - Kelly < 0 means negative edge → don't bet
    - Kelly < MIN_KELLY_THRESHOLD (1%) → edge too small
"""

from dataclasses import dataclass
from typing import Optional

from analytics.probability import signal_to_probability, calculate_edge, edge_percentage


# =====================================================================
# Constants
# =====================================================================

DEFAULT_FRACTION = 0.25     # Quarter Kelly
MAX_POSITION_PCT = 0.10     # Never more than 10% on one market
MIN_KELLY_THRESHOLD = 0.01  # Ignore edges below 1% Kelly
DEFAULT_BANKROLL = 10_000   # Default if user hasn't set one


# =====================================================================
# Data class
# =====================================================================

@dataclass
class KellyResult:
    """Result of Kelly Criterion calculation."""

    # Input
    model_probability: float   # Our estimate of true probability
    market_price: float        # Current market price (entry)
    bankroll: float            # User's bankroll in USDC
    fraction: float            # Kelly fraction used (0.25 = Quarter)

    # Calculated
    edge: float                # model_prob - market_price
    edge_pct: float            # Edge as % of market price
    net_odds: float            # (1/price) - 1
    kelly_full: float          # Full Kelly fraction
    kelly_fraction: float      # Fractional Kelly (kelly_full * fraction)
    recommended_size: float    # Dollar amount to bet
    recommended_side: str      # "YES" or "NO"

    # Flags
    has_edge: bool             # Is there a positive edge?
    is_significant: bool       # Is the edge worth betting on?

    @property
    def size_pct(self) -> float:
        """Recommended size as % of bankroll."""
        if self.bankroll > 0:
            return (self.recommended_size / self.bankroll) * 100
        return 0.0

    @property
    def potential_profit(self) -> float:
        """Profit if bet wins (buy at entry, sell at $1)."""
        if self.market_price > 0:
            return self.recommended_size * ((1.0 / self.market_price) - 1)
        return 0.0


# =====================================================================
# Calculator
# =====================================================================

def calculate_kelly(
    model_prob: float,
    market_price: float,
    bankroll: float = DEFAULT_BANKROLL,
    fraction: float = DEFAULT_FRACTION,
    side: str = "AUTO",
) -> KellyResult:
    """
    Calculate Kelly Criterion position sizing.

    Args:
        model_prob: Our estimated probability of YES (0–1)
        market_price: Current YES price on Polymarket (0–1)
        bankroll: User's bankroll in USDC
        fraction: Kelly fraction (0.25 = Quarter Kelly)
        side: "YES", "NO", or "AUTO" (auto-detect from edge)

    Returns:
        KellyResult with sizing recommendation
    """
    # Determine which side has edge
    edge = model_prob - market_price

    if side == "AUTO":
        if edge > 0:
            # YES is underpriced → buy YES
            bet_side = "YES"
            p = model_prob
            entry = market_price
        else:
            # NO is underpriced → buy NO
            bet_side = "NO"
            p = 1.0 - model_prob
            entry = 1.0 - market_price
    elif side == "YES":
        bet_side = "YES"
        p = model_prob
        entry = market_price
    else:
        bet_side = "NO"
        p = 1.0 - model_prob
        entry = 1.0 - market_price

    # Edge for the chosen side
    side_edge = p - entry
    side_edge_pct = ((p - entry) / entry * 100) if entry > 0 else 0.0

    # Net odds: how much you win per dollar risked
    # Binary option: pay `entry`, receive $1 if win → net odds = (1/entry) - 1
    if entry > 0 and entry < 1:
        net_odds = (1.0 / entry) - 1.0
    else:
        net_odds = 0.0

    # Kelly formula: f* = (b*p - q) / b
    q = 1.0 - p
    if net_odds > 0:
        kelly_full = (net_odds * p - q) / net_odds
    else:
        kelly_full = 0.0

    # Fractional Kelly
    kelly_frac = kelly_full * fraction

    # Cap at maximum position
    kelly_frac = min(kelly_frac, MAX_POSITION_PCT)

    # Determine if edge is significant
    has_edge = kelly_full > 0
    is_significant = kelly_full >= MIN_KELLY_THRESHOLD

    # Calculate dollar size
    if has_edge and is_significant:
        recommended_size = round(kelly_frac * bankroll, 2)
    else:
        recommended_size = 0.0

    return KellyResult(
        model_probability=model_prob,
        market_price=market_price,
        bankroll=bankroll,
        fraction=fraction,
        edge=side_edge,
        edge_pct=side_edge_pct,
        net_odds=net_odds,
        kelly_full=kelly_full,
        kelly_fraction=kelly_frac,
        recommended_size=recommended_size,
        recommended_side=bet_side,
        has_edge=has_edge,
        is_significant=is_significant,
    )


def kelly_from_market(
    market,  # MarketStats
    bankroll: float = DEFAULT_BANKROLL,
    fraction: float = DEFAULT_FRACTION,
) -> KellyResult:
    """
    Convenience: calculate Kelly directly from a MarketStats object.
    Uses signal_to_probability() for the model estimate.
    """
    model_prob = signal_to_probability(market)
    return calculate_kelly(
        model_prob=model_prob,
        market_price=market.yes_price,
        bankroll=bankroll,
        fraction=fraction,
    )
