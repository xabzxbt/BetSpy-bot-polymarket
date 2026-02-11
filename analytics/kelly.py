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
    
    # Time-adjusted Kelly fields
    days_to_resolve: int = 0              # Days until market resolves
    kelly_capped_pct: float = 0.0         # Capped Kelly percentage (same as kelly_full * 100)
    kelly_time_adj_pct: float = 0.0       # Time-adjusted Kelly percentage
    kelly_final_pct: float = 0.0          # Final recommended percentage after time adjustment and fraction

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
# Time-adjusted Kelly Calculator
# =====================================================================

TIME_ADJUSTED_REF_HORIZON = 30  # Reference time horizon in days


def calculate_time_adjusted_kelly(kelly_capped: float, days_to_resolve: int) -> tuple[float, float]:
    """
    Calculate time-adjusted Kelly position sizing.
    
    Formula: f_time = f_kelly * min(1, T_ref / T_market)
    Where:
    - f_kelly = already calculated capped Kelly (0-0.2 as fraction of bankroll)
    - T_market = days until market resolves
    - T_ref = reference horizon (30 days)
    
    Args:
        kelly_capped: Capped Kelly fraction (already calculated)
        days_to_resolve: Number of days until market resolves
        
    Returns:
        tuple: (time_adjusted_fraction, final_fraction)
            - time_adjusted_fraction: Kelly adjusted for time horizon
            - final_fraction: Final recommendation (time_adjusted * 0.25)
    """
    # Reference time horizon
    T_ref = TIME_ADJUSTED_REF_HORIZON
    
    # Handle edge case where days_to_resolve is very small or negative
    if days_to_resolve <= 0:
        multiplier = 1.0
    else:
        multiplier = min(1.0, T_ref / days_to_resolve)
    
    # Calculate time-adjusted Kelly
    kelly_time_adj = kelly_capped * multiplier
    
    # Calculate final recommendation (1/4 of time-adjusted Kelly)
    kelly_final = kelly_time_adj * DEFAULT_FRACTION
    
    return kelly_time_adj, kelly_final


# =====================================================================
# Calculator
# =====================================================================

def calculate_kelly(
    model_prob: float,
    market_price: float,
    bankroll: float = DEFAULT_BANKROLL,
    fraction: float = DEFAULT_FRACTION,
    days_to_resolve: int = 0,
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
    
    # 8. Time-adjusted Kelly Calculation
    kelly_capped_pct = kelly_full * 100  # Convert to percentage
    kelly_time_adj, kelly_final = calculate_time_adjusted_kelly(kelly_full, days_to_resolve)
    kelly_time_adj_pct = kelly_time_adj * 100  # Convert to percentage
    kelly_final_pct = kelly_final * 100  # Convert to percentage
    
    # Calculate the recommended size based on the time-adjusted final Kelly
    time_adj_rec_size = round(kelly_final * bankroll, 0)
    
    return KellyResult(
        model_probability=safe_prob,
        market_price=market_price,
        bankroll=bankroll,
        fraction=fraction,
        edge=edge_abs,
        edge_pct=edge_pct,
        kelly_full=kelly_full,
        kelly_fraction=kelly_final,  # Use time-adjusted final Kelly as the recommended fraction
        recommended_size=time_adj_rec_size,
        recommended_side=recommended_side,
        has_edge=(edge_abs > 0),
        is_significant=(time_adj_rec_size > 0),
        fraction_name=_get_fraction_name(fraction),
        days_to_resolve=days_to_resolve,
        kelly_capped_pct=kelly_capped_pct,
        kelly_time_adj_pct=kelly_time_adj_pct,
        kelly_final_pct=kelly_final_pct
    )

def kelly_from_market(market, bankroll=10000, fraction=0.25, days_to_resolve=0):
    """Wrapper that uses signal_score as a proxy for probability if needed."""
    return calculate_kelly(
        model_prob=signal_to_probability(market),
        market_price=market.yes_price,
        bankroll=bankroll,
        fraction=fraction,
        days_to_resolve=days_to_resolve
    )

def _get_fraction_name(f: float) -> str:
    if f <= 0.15: return "1/8 Kelly"
    if f <= 0.30: return "1/4 Kelly"
    if f <= 0.55: return "1/2 Kelly"
    return "Full Kelly"
