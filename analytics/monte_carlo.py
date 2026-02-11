"""
BetSpy Monte Carlo Simulations

Instead of guessing "will it happen?", we run 10,000 simulations of the future.

Two modes:

1. CRYPTO MODE — for markets tied to crypto asset prices
   Uses Geometric Brownian Motion (GBM) with real price + volatility from CoinGecko.
   Example: "Will Bitcoin exceed $120K by March?"
   → Fetch BTC price ($108K), vol (65%), run 10K paths → P(BTC > $120K) = 41%

2. GENERIC MODE — for all other markets (politics, sports, etc.)
   Simulates the PRICE VOLATILITY itself to show risk/drawdown.
   Does NOT predict the winner (drift = 0).
   The "probability" returned is just the current price (neutral).
"""

import math
import random
import re
import statistics
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from analytics.data_fetcher import PriceHistory, CryptoData
from loguru import logger


# =====================================================================
# Constants
# =====================================================================

NUM_SIMULATIONS = 10_000
RANDOM_SEED = None  # Set for reproducibility in tests


# =====================================================================
# Crypto market detection
# =====================================================================

# Maps keywords in question → CoinGecko coin_id
CRYPTO_PATTERNS = {
    "bitcoin": "bitcoin",
    "btc": "bitcoin",
    "ethereum": "ethereum",
    "eth ": "ethereum",
    "solana": "solana",
    "sol ": "solana",
    "dogecoin": "dogecoin",
    "doge": "dogecoin",
    "xrp": "ripple",
    "ripple": "ripple",
    "cardano": "cardano",
    "ada ": "cardano",
    "polygon": "matic-network",
    "matic": "matic-network",
    "avalanche": "avalanche-2",
    "avax": "avalanche-2",
    "chainlink": "chainlink",
    "link ": "chainlink",
    "polkadot": "polkadot",
    "dot ": "polkadot",
    "sui ": "sui",
    "aptos": "aptos",
    "apt ": "aptos",
    "near": "near",
    "toncoin": "the-open-network",
    "ton ": "the-open-network",
}

# Regex to extract price thresholds from questions
PRICE_THRESHOLD_RE = re.compile(
    r'\$\s*([0-9,]+(?:\.\d+)?)\s*([kKmMbB])?'
)

# Direction keywords
ABOVE_KEYWORDS = ["above", "exceed", "over", "reach", "hit", "surpass", "break", "top"]
BELOW_KEYWORDS = ["below", "under", "fall", "drop", "dip", "crash"]


@dataclass
class CryptoMarketInfo:
    """Parsed crypto market information from question text."""
    coin_id: str
    threshold: float
    direction: str  # "above" or "below"
    is_valid: bool = True


def detect_crypto_market(question: str) -> Optional[CryptoMarketInfo]:
    """
    Parse a question to detect if it's about a crypto price target.
    """
    q_lower = question.lower()

    # Find coin
    coin_id = None
    for keyword, cg_id in CRYPTO_PATTERNS.items():
        if keyword in q_lower:
            coin_id = cg_id
            break

    if not coin_id:
        return None

    # Find price threshold
    matches = PRICE_THRESHOLD_RE.findall(question)
    if not matches:
        return None

    # Parse the first price match
    num_str, suffix = matches[0]
    num_str = num_str.replace(",", "")
    try:
        value = float(num_str)
    except ValueError:
        return None

    # Apply suffix
    suffix = suffix.lower() if suffix else ""
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    elif suffix == "b":
        value *= 1_000_000_000

    if value <= 0:
        return None

    # Detect direction
    direction = "above"  # default
    for kw in BELOW_KEYWORDS:
        if kw in q_lower:
            direction = "below"
            break

    return CryptoMarketInfo(
        coin_id=coin_id,
        threshold=value,
        direction=direction,
    )


# =====================================================================
# Data classes
# =====================================================================

@dataclass
class MonteCarloResult:
    """Result of Monte Carlo simulation."""
    mode: str                    # "crypto" or "generic"
    num_simulations: int
    probability_yes: float       # Simulated P(YES)
    market_price: float          # Current market YES price
    edge: float                  # probability_yes - market_price

    # Percentiles (for risk analysis)
    percentile_5: float = 0.0    # 5th percentile outcome
    percentile_50: float = 0.0   # Median outcome
    percentile_95: float = 0.0   # 95th percentile outcome

    # Distribution buckets (for display)
    distribution: List[Tuple[str, float]] = field(default_factory=list)

    # Crypto-specific
    coin_id: str = ""
    current_asset_price: float = 0.0
    threshold: float = 0.0
    direction: str = ""

    # Stats
    mean_final_price: float = 0.0
    std_final_price: float = 0.0

    @property
    def has_edge(self) -> bool:
        return abs(self.edge) >= 0.03  # at least 3% edge

    @property
    def edge_pct(self) -> float:
        if self.market_price > 0:
            return (self.edge / self.market_price) * 100
        return 0.0


# =====================================================================
# Simulators
# =====================================================================

def run_crypto_simulation(
    crypto: CryptoData,
    threshold: float,
    direction: str,
    days: int,
    market_price: float,
    n_sims: int = NUM_SIMULATIONS,
) -> MonteCarloResult:
    """
    Monte Carlo simulation for crypto price markets using GBM.
    
    Includes SAFETY CAPS to prevent 100% or 0% probability.
    """
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    S0 = crypto.current_price
    mu = crypto.mu
    sigma = crypto.sigma

    if sigma < 0.01:
        sigma = 0.50  # default 50% vol if data is bad

    dt = 1.0 / 365.0
    # GBM drift & diffusion
    drift_part = (mu - 0.5 * sigma ** 2) * dt
    diffusion_part = sigma * math.sqrt(dt)

    final_prices = []
    yes_count = 0

    # Optimization: pre-calculate randoms if we were using numpy
    # Here we use a loop but keep it simple
    for _ in range(n_sims):
        # We only need the FINAL price for a "European" option style check
        # But correctly simulating the path requires summing the log returns
        # sum_Z ~ N(0, days)
        # So ln(St) = ln(S0) + (mu - 0.5*sigma^2)*T + sigma*sqrt(T)*Z
        # This is much faster than looping days!
        
        T = days * dt
        effective_drift = (mu - 0.5 * sigma ** 2) * T
        effective_diffusion = sigma * math.sqrt(T)
        
        z = random.gauss(0, 1)
        final_price = S0 * math.exp(effective_drift + effective_diffusion * z)
        final_prices.append(final_price)

        if direction == "above":
            if final_price >= threshold:
                yes_count += 1
        else:
            if final_price <= threshold:
                yes_count += 1

    prob_yes = yes_count / n_sims

    # SAFETY CAP: Never report 0% or 100%
    # We clamp to [0.1%, 99.9%]
    prob_yes = max(0.001, min(0.999, prob_yes))

    # Distribution buckets
    final_prices.sort()
    distribution = _build_crypto_distribution(final_prices, threshold)

    # Stats
    try:
        pct_5 = final_prices[int(n_sims * 0.05)]
        pct_50 = final_prices[int(n_sims * 0.50)]
        pct_95 = final_prices[int(n_sims * 0.95)]
        mean_p = statistics.mean(final_prices)
        std_p = statistics.stdev(final_prices) if n_sims > 1 else 0.0
    except (IndexError, ValueError):
        pct_5 = pct_50 = pct_95 = mean_p = std_p = 0.0

    return MonteCarloResult(
        mode="crypto",
        num_simulations=n_sims,
        probability_yes=prob_yes,
        market_price=market_price,
        edge=prob_yes - market_price,
        percentile_5=pct_5,
        percentile_50=pct_50,
        percentile_95=pct_95,
        distribution=distribution,
        coin_id=crypto.coin_id,
        current_asset_price=crypto.current_price,
        threshold=threshold,
        direction=direction,
        mean_final_price=mean_p,
        std_final_price=std_p,
    )


def run_generic_simulation(
    current_price: float,
    days: int,
    price_history: PriceHistory,
    market_price: float,
    n_sims: int = NUM_SIMULATIONS,
) -> MonteCarloResult:
    """
    Monte Carlo simulation for generic markets.
    
    NO DRIFT "prediction". 
    We pretend the price follows a geometric random walk with NO drift (Martingale).
    The 'probability_yes' is simply the current price (neutral).
    This simulation is used ONLY to visualize VOLATILITY/RISK (percentiles).
    """
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    # Use market's own volatility
    if not price_history.is_empty:
        sigma = price_history.volatility()
    else:
        sigma = 0.40  # default generic vol

    if sigma < 0.01:
        sigma = 0.40

    # For binary options (0 to 1), Standard Brownian Motion is often better fit for probability space
    # but let's stick to log-normal price approximation or just simple Log-Odds walk.
    # To keep it robust: Use bounded random walk.
    # Or simpler: Just return voltage stats without simulating full paths if we don't predict.
    # But to satisfy the loop:
    
    dt = 1.0 / 365.0
    T = days * dt
    daily_vol = sigma * math.sqrt(dt) # approx daily move
    total_vol = sigma * math.sqrt(T)  # approx move over 'days'
    
    final_prices = []
    
    # We simulate 10k final prices assuming current_price is fair
    # Using Logit-Normal or just Normal clipped is easiest for "Probability"
    # Let's use Normal distribution on the PROBABILITY space
    # centered at current_price
    
    for _ in range(n_sims):
        # random shock based on total time volatility
        shock = random.gauss(0, total_vol)
        p_final = current_price + shock
        # Clip to [0.01, 0.99]
        p_final = max(0.01, min(0.99, p_final))
        final_prices.append(p_final)

    # The model "prediction" is just the current price (Neutral)
    # We DO NOT predict the winner here.
    prob_yes = current_price 

    final_prices.sort()
    
    try:
        pct_5 = final_prices[int(n_sims * 0.05)]
        pct_50 = final_prices[int(n_sims * 0.50)]
        pct_95 = final_prices[int(n_sims * 0.95)]
        mean_p = statistics.mean(final_prices)
        std_p = statistics.stdev(final_prices) if n_sims > 1 else 0.0
    except (IndexError, ValueError):
        pct_5 = pct_50 = pct_95 = mean_p = std_p = 0.0
        
    distribution = _build_generic_distribution(final_prices)

    return MonteCarloResult(
        mode="generic",
        num_simulations=n_sims,
        probability_yes=prob_yes,
        market_price=market_price,
        edge=0.0, # NO EDGE claimed from generic simulation
        percentile_5=pct_5,
        percentile_50=pct_50,
        percentile_95=pct_95,
        distribution=distribution,
        mean_final_price=mean_p,
        std_final_price=std_p,
    )


# =====================================================================
# Helpers
# =====================================================================

def _build_crypto_distribution(
    prices: List[float], threshold: float
) -> List[Tuple[str, float]]:
    """Build distribution buckets around the threshold."""
    n = len(prices)
    if n == 0:
        return []

    step = threshold * 0.10
    boundaries = [
        threshold - 2 * step,
        threshold - step,
        threshold,
        threshold + step,
        threshold + 2 * step,
    ]

    bucket_names = [
        f"< ${_fmt_price(boundaries[0])}",
        f"${_fmt_price(boundaries[0])}–${_fmt_price(boundaries[1])}",
        f"${_fmt_price(boundaries[1])}–${_fmt_price(boundaries[2])}",
        f"${_fmt_price(boundaries[2])}–${_fmt_price(boundaries[3])}",
        f"> ${_fmt_price(boundaries[3])}",
    ]

    counts = [0] * 5
    for p in prices:
        if p < boundaries[0]:
            counts[0] += 1
        elif p < boundaries[1]:
            counts[1] += 1
        elif p < boundaries[2]:
            counts[2] += 1
        elif p < boundaries[3]:
            counts[3] += 1
        else:
            counts[4] += 1

    return [(name, count / n) for name, count in zip(bucket_names, counts)]


def _build_generic_distribution(
    prices: List[float],
) -> List[Tuple[str, float]]:
    """Build distribution for generic market simulations."""
    n = len(prices)
    if n == 0:
        return []

    buckets = [
        ("0–20¢", 0.0, 0.20),
        ("20–40¢", 0.20, 0.40),
        ("40–60¢", 0.40, 0.60),
        ("60–80¢", 0.60, 0.80),
        ("80–100¢", 0.80, 1.01),
    ]

    result = []
    for name, lo, hi in buckets:
        count = sum(1 for p in prices if lo <= p < hi)
        result.append((name, count / n))

    return result


def _fmt_price(v: float) -> str:
    """Format a large price nicely."""
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    elif v >= 1_000:
        return f"{v / 1_000:.0f}K"
    return f"{v:.0f}"
