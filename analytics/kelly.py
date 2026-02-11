"""
BetSpy Kelly Criterion — Optimal Position Sizing

SAFE VERSION:
1. Clamps model probability [0.05, 0.95]
2. Ignores small edges (< 2%)
3. Caps Full Kelly at 20% max allocation
4. Returns fractional recommendation
"""

from dataclasses import dataclass
from typing import Optional
from analytics.probability import signal_to_probability


# =====================================================================
# Constants
# =====================================================================

DEFAULT_FRACTION = 0.25     # Quarter Kelly
MAX_FULL_KELLY_CAP = 0.20   # Absolute limit for Full Kelly (20% of bankroll)
MIN_EDGE_THRESHOLD = 0.02   # Ignore edges < 2 p.p.
DEFAULT_BANKROLL = 10_000   # Default bankroll


# =====================================================================
# Data class
# =====================================================================

@dataclass
class KellyResult:
    """Result of Kelly Criterion calculation."""
    # Input
    model_probability: float
    market_price: float
    bankroll: float
    fraction: float

    # Calculated
    edge: float                # model_prob - market_price
    edge_pct: float            # Edge as % of market price
    kelly_full: float          # Full Kelly fraction (capped)
    kelly_fraction: float      # Fractional Kelly (kelly_full * fraction)
    recommended_size: float    # Dollar amount to bet
    recommended_side: str      # "YES" or "NO"

    # Metadata
    has_edge: bool
    is_significant: bool
    fraction_name: str         # "¼ Kelly", etc.

    @property
    def size_pct(self) -> float:
        """Recommended size as % of bankroll."""
        if self.bankroll > 0:
            return (self.recommended_size / self.bankroll) * 100
        return 0.0
    
    @property
    def potential_profit(self) -> float:
        """Profit if bet wins."""
        if self.market_price > 0:
            return self.recommended_size * ((1.0 / self.market_price) - 1.0)
        return 0.0


# =====================================================================
# Calculator
# =====================================================================

def calculate_kelly(
    model_prob: float,
    market_price: float,
    bankroll: float = DEFAULT_BANKROLL,
    fraction: float = DEFAULT_FRACTION,
) -> KellyResult:
    """
    Calculate Safe Kelly Criterion.
    """
    # 1. Safety Clamp Probability
    # Never fully trust a model > 95% or < 5%
    safe_prob = max(0.05, min(0.95, model_prob))
    
    # 2. Determine Side & Edge
    edge_raw = safe_prob - market_price
    
    if edge_raw > 0:
        recommended_side = "YES"
        p = safe_prob
        price = market_price
    else:
        recommended_side = "NO"
        p = 1.0 - safe_prob
        price = 1.0 - market_price
        
    edge_abs = p - price
    edge_pct = (edge_abs / price * 100) if price > 0 else 0.0
    
    # 3. Check Significance
    # If edge is tiny (< 2%), return 0
    if edge_abs < MIN_EDGE_THRESHOLD:
        return KellyResult(
            model_probability=safe_prob,
            market_price=market_price,
            bankroll=bankroll,
            fraction=fraction,
            edge=edge_abs,
            edge_pct=edge_pct,
            kelly_full=0.0,
            kelly_fraction=0.0,
            recommended_size=0.0,
            recommended_side=recommended_side,
            has_edge=False,
            is_significant=False,
            fraction_name=_get_fraction_name(fraction)
        )
        
    # 4. Kelly Formula: f = (bp - q) / b
    # b = net odds = (1/price) - 1
    if price <= 0 or price >= 1:
        kelly_full = 0.0
    else:
        b = (1.0 / price) - 1.0
        q = 1.0 - p
        if b > 0:
            kelly_full = (b * p - q) / b
        else:
            kelly_full = 0.0
            
    # 5. Cap Full Kelly
    # Even if Kelly says 80%, we cap at MAX_FULL_KELLY_CAP (20%)
    # This prevents blowing up on "sure things" that fail
    kelly_full = max(0.0, min(MAX_FULL_KELLY_CAP, kelly_full))
    
    # 6. Apply User Fraction
    kelly_frac = kelly_full * fraction
    
    # 7. Dollar Size
    rec_size = round(kelly_frac * bankroll, 0)
    
    return KellyResult(
        model_probability=safe_prob,
        market_price=market_price,
        bankroll=bankroll,
        fraction=fraction,
        edge=edge_abs,
        edge_pct=edge_pct,
        kelly_full=kelly_full,
        kelly_fraction=kelly_frac,
        recommended_size=rec_size,
        recommended_side=recommended_side,
        has_edge=(edge_abs > 0),
        is_significant=(rec_size > 0),
        fraction_name=_get_fraction_name(fraction)
    )

def kelly_from_market(market, bankroll=10000, fraction=0.25):
    """Wrapper that uses signal_score as a proxy for probability if needed."""
    return calculate_kelly(
        model_prob=signal_to_probability(market),
        market_price=market.yes_price,
        bankroll=bankroll,
        fraction=fraction
    )

def _get_fraction_name(f: float) -> str:
    if f <= 0.15: return "1/8 Kelly"
    if f <= 0.30: return "1/4 Kelly"
    if f <= 0.55: return "1/2 Kelly"
    return "Full Kelly"
