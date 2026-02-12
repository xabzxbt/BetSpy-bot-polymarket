"""
BetSpy Greeks — Time Decay (Theta) & Volatility (Vega)

Binary options on Polymarket have "Greeks" similar to financial options:

Theta (Time Decay):
    How much the price SHOULD change per day just from time passing.
    If an event is unlikely (YES = 15¢), NO should slowly drift toward 100¢
    as the end date approaches. If NO is NOT drifting → anomaly → opportunity.

    Formula:
        expected_theta = (target_price - current_price) / days_remaining
        actual_theta = (price_today - price_N_days_ago) / N
        theta_anomaly = expected_theta - actual_theta

    Positive anomaly = price "should" be moving but isn't → opportunity

Vega (Volatility Sensitivity):
    How sensitive is this market to news/shocks?

    historical_vol = std(daily returns) over last 7 days, annualized
    recent_vol = std(daily returns) over last 24h, annualized

    If recent_vol >> historical_vol → market just got shocked (news)
    If recent_vol << historical_vol → market is sleeping (calm before storm)
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from analytics.data_fetcher import PriceHistory


# =====================================================================
# Data classes
# =====================================================================

@dataclass
class ThetaResult:
    """Time decay analysis."""
    days_remaining: int
    current_price: float          # YES price
    expected_daily_drift: float   # How much YES should move per day
    actual_daily_drift: float     # How much YES actually moved per day
    theta_anomaly: float          # expected - actual (positive = opportunity)
    time_value: float             # How much "extra" is priced in for uncertainty
    dominant_side: str            # Which side benefits from time passing
    is_opportunity: bool          # Is the anomaly significant?

    @property
    def theta_yes(self) -> float:
        """Theta for YES side (¢ per day)."""
        return self.expected_daily_drift * 100

    @property
    def theta_no(self) -> float:
        """Theta for NO side (¢ per day)."""
        return -self.expected_daily_drift * 100


@dataclass
class VegaResult:
    """Volatility analysis."""
    historical_vol_7d: float     # 7-day annualized vol
    recent_vol_24h: float        # 24h annualized vol
    vol_ratio: float             # recent / historical
    regime: str                  # "high", "low", "normal", "spike"
    is_sleeping: bool            # Low vol → possible breakout
    is_spiking: bool             # High vol → news event happening

    @property
    def vol_change_pct(self) -> float:
        """Recent vol vs historical as % change."""
        if self.historical_vol_7d > 0:
            return ((self.recent_vol_24h - self.historical_vol_7d)
                    / self.historical_vol_7d) * 100
        return 0.0


@dataclass
class GreeksResult:
    """Combined Greeks analysis."""
    theta: ThetaResult
    vega: VegaResult

    @property
    def has_time_opportunity(self) -> bool:
        return self.theta.is_opportunity

    @property
    def has_vol_signal(self) -> bool:
        return self.vega.is_sleeping or self.vega.is_spiking


# =====================================================================
# Calculators
# =====================================================================

def calculate_theta(
    yes_price: float,
    days_remaining: int,
    price_history: PriceHistory,
    lookback_points: int = 24,  # ~1 day of hourly data
) -> ThetaResult:
    """
    Calculate time decay (Theta) for a binary market.

    Logic:
    - If YES < 50¢ → market expects NO to win → NO should drift to 100¢
    - If YES > 50¢ → market expects YES to win → YES should drift to 100¢
    - expected_daily_drift = how fast price should move toward resolution
    - actual_daily_drift = how fast it's actually moving (from price history)
    - Anomaly = expected - actual (positive = price is "stuck")
    """
    if days_remaining <= 0:
        days_remaining = 1

    # Determine expected direction
    if yes_price >= 0.50:
        # Market leans YES → YES should drift toward $1
        target = 1.0
        dominant_side = "YES"
    else:
        # Market leans NO → YES should drift toward $0
        target = 0.0
        dominant_side = "NO"

    expected_daily_drift = (target - yes_price) / days_remaining

    # Actual drift from price history
    actual_daily_drift = 0.0
    if not price_history.is_empty and len(price_history.points) >= 2:
        n = min(lookback_points, len(price_history.points) - 1)
        if n > 0:
            recent = price_history.points[-1].price
            past = price_history.points[-(n + 1)].price
            # Time between points (approximate days)
            t_recent = price_history.points[-1].timestamp
            t_past = price_history.points[-(n + 1)].timestamp
            dt_days = max((t_recent - t_past) / 86400, 0.1)
            actual_daily_drift = (recent - past) / dt_days

    theta_anomaly = expected_daily_drift - actual_daily_drift

    # Time value: how much extra is priced in beyond the "intrinsic" value
    # Intrinsic = max(0, price - 0.5) for YES, or max(0, 0.5 - price) for NO
    intrinsic = abs(yes_price - 0.50)
    time_value = yes_price - intrinsic if yes_price >= 0.50 else (1 - yes_price) - intrinsic
    time_value = max(0, time_value)

    # Significant opportunity: anomaly > 0.5¢/day AND days remaining > 3
    is_opportunity = (
        abs(theta_anomaly) > 0.005
        and days_remaining >= 3
    )

    return ThetaResult(
        days_remaining=days_remaining,
        current_price=yes_price,
        expected_daily_drift=expected_daily_drift,
        actual_daily_drift=actual_daily_drift,
        theta_anomaly=theta_anomaly,
        time_value=time_value,
        dominant_side=dominant_side,
        is_opportunity=is_opportunity,
    )


def calculate_vega(price_history: PriceHistory) -> VegaResult:
    """
    Calculate volatility (Vega) analysis.

    Compares 7-day historical vol with 24h recent vol to detect:
    - Sleeping markets (recent << historical) → breakout potential
    - Spiking markets (recent >> historical) → news event
    """
    if price_history.is_empty or len(price_history.points) < 5:
        return VegaResult(
            historical_vol_7d=0.0,
            recent_vol_24h=0.0,
            vol_ratio=1.0,
            regime="unknown",
            is_sleeping=False,
            is_spiking=False,
        )

    # 7-day volatility (all available data up to ~168 hourly points)
    hist_vol = price_history.volatility()

    # 24h volatility (last ~24 hourly points)
    recent_vol = price_history.recent_volatility(n=24)

    # Vol ratio
    if hist_vol > 0.001:
        vol_ratio = recent_vol / hist_vol
    else:
        vol_ratio = 1.0

    # Regime classification
    is_sleeping = vol_ratio < 0.4 and hist_vol > 0.05
    is_spiking = vol_ratio > 2.5

    if is_spiking:
        regime = "spike"
    elif is_sleeping:
        regime = "low"
    elif vol_ratio > 1.5:
        regime = "high"
    else:
        regime = "normal"

    return VegaResult(
        historical_vol_7d=hist_vol,
        recent_vol_24h=recent_vol,
        vol_ratio=vol_ratio,
        regime=regime,
        is_sleeping=is_sleeping,
        is_spiking=is_spiking,
    )


def calculate_greeks(
    yes_price: float,
    days_remaining: int,
    price_history: PriceHistory,
) -> GreeksResult:
    """Calculate both Theta and Vega."""
    theta = calculate_theta(yes_price, days_remaining, price_history)
    vega = calculate_vega(price_history)
    return GreeksResult(theta=theta, vega=vega)
