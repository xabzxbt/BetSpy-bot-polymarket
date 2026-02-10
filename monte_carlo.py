"""
BetSpy Monte Carlo Simulations

Instead of guessing "will it happen?", we run 10,000 simulations of the future.

Two modes:

1. CRYPTO MODE — for markets tied to crypto asset prices
   Uses Geometric Brownian Motion (GBM) with real price + volatility from CoinGecko.
   Example: "Will Bitcoin exceed $120K by March?"
   → Fetch BTC price ($108K), vol (65%), run 10K paths → P(BTC > $120K) = 41%

2. GENERIC MODE — for all other markets (politics, sports, etc.)
   Simulates the Polymarket price itself using its historical volatility.
   Less precise, but still gives a distribution of possible outcomes.

Formulas:
    GBM: S(t+1) = S(t) × exp((μ - σ²/2)Δt + σ√Δt × Z)
    where Z ~ N(0,1)
"""

import math
import random
import re
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
# Matches: "$100,000", "$100k", "$120K", "$100000", "$1.5M", etc.
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

    Examples:
        "Will Bitcoin exceed $120,000 by March?" → (bitcoin, 120000, above)
        "Bitcoin below $80K?"                    → (bitcoin, 80000, below)
        "ETH price above $5k?"                   → (ethereum, 5000, above)
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

    # Distribution buckets (for display)
    distribution: List[Tuple[str, float]] = field(default_factory=list)

    # Crypto-specific
    coin_id: str = ""
    current_asset_price: float = 0.0
    threshold: float = 0.0
    direction: str = ""

    # Stats
    mean_final_price: float = 0.0
    median_final_price: float = 0.0
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

    Simulates `n_sims` price paths and counts how many cross threshold.
    """
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    S0 = crypto.current_price
    mu = crypto.mu
    sigma = crypto.sigma

    if sigma < 0.01:
        sigma = 0.50  # default 50% vol if data is bad

    dt = 1.0 / 365  # daily steps
    drift = (mu - 0.5 * sigma ** 2) * dt
    diffusion = sigma * math.sqrt(dt)

    final_prices = []
    yes_count = 0

    for _ in range(n_sims):
        price = S0
        for _ in range(days):
            z = random.gauss(0, 1)
            price *= math.exp(drift + diffusion * z)

        final_prices.append(price)

        if direction == "above":
            if price >= threshold:
                yes_count += 1
        else:
            if price <= threshold:
                yes_count += 1

    prob_yes = yes_count / n_sims

    # Distribution buckets
    final_prices.sort()
    distribution = _build_crypto_distribution(final_prices, threshold)

    # Stats
    mean_p = sum(final_prices) / n_sims
    median_p = final_prices[n_sims // 2]
    var = sum((p - mean_p) ** 2 for p in final_prices) / n_sims
    std_p = math.sqrt(var)

    return MonteCarloResult(
        mode="crypto",
        num_simulations=n_sims,
        probability_yes=prob_yes,
        market_price=market_price,
        edge=prob_yes - market_price,
        distribution=distribution,
        coin_id=crypto.coin_id,
        current_asset_price=crypto.current_price,
        threshold=threshold,
        direction=direction,
        mean_final_price=mean_p,
        median_final_price=median_p,
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

    Simulates the Polymarket price itself based on its historical volatility.
    Counts how many simulations end above 50¢ (YES wins).
    """
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    # Use market's own volatility
    if not price_history.is_empty:
        sigma = price_history.volatility()
    else:
        sigma = 0.30  # default

    if sigma < 0.01:
        sigma = 0.30

    # Daily vol
    daily_vol = sigma / math.sqrt(365)

    yes_count = 0
    final_prices = []

    for _ in range(n_sims):
        price = current_price
        for _ in range(days):
            # Mean-reverting random walk (prices tend toward 0 or 1)
            # Small drift toward current direction
            if price > 0.50:
                drift = 0.001  # slight YES drift
            else:
                drift = -0.001  # slight NO drift

            shock = random.gauss(drift, daily_vol)
            price = max(0.01, min(0.99, price + shock))

        final_prices.append(price)
        if price > 0.50:
            yes_count += 1

    prob_yes = yes_count / n_sims

    # Distribution
    final_prices.sort()
    distribution = _build_generic_distribution(final_prices)

    mean_p = sum(final_prices) / n_sims

    return MonteCarloResult(
        mode="generic",
        num_simulations=n_sims,
        probability_yes=prob_yes,
        market_price=market_price,
        edge=prob_yes - market_price,
        distribution=distribution,
        mean_final_price=mean_p,
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

    # Create 5 buckets centered around threshold
    step = threshold * 0.10  # 10% of threshold per bucket
    boundaries = [
        threshold - 2 * step,
        threshold - step,
        threshold,
        threshold + step,
        threshold + 2 * step,
    ]

    buckets = []
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
        ("0–20¢ (Strong NO)", 0.0, 0.20),
        ("20–40¢ (Lean NO)", 0.20, 0.40),
        ("40–60¢ (Toss-up)", 0.40, 0.60),
        ("60–80¢ (Lean YES)", 0.60, 0.80),
        ("80–100¢ (Strong YES)", 0.80, 1.01),
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
