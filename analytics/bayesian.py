"""
BetSpy Bayesian Inference — Probability Updates from Whale Evidence

Instead of blind market price, we update probability using Bayes' theorem
with WHALE BEHAVIOR as evidence (no news API needed).

Bayes' Theorem:
    P(YES|evidence) = P(evidence|YES) × P(YES) / P(evidence)

Simplified via likelihood ratios:
    posterior_odds = prior_odds × LR₁ × LR₂ × LR₃
    posterior_prob = posterior_odds / (1 + posterior_odds)

Three types of evidence:

1. WHALE SURGE — unusual whale volume in last 2h vs average
   LR > 1 if surge on YES side, LR < 1 if surge on NO side

2. PRICE-VOLUME DIVERGENCE — price goes one way, whales go the other
   Classic "smart money" signal: whales buying the dip = bullish

3. CONSENSUS — multiple large independent wallets bet the same side
   3+ whales ($5K+) same direction in 4h window = strong signal
"""

import math
import time as _time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from loguru import logger


# =====================================================================
# Constants
# =====================================================================

# Likelihood ratio bounds (prevent extreme updates)
MAX_LR = 3.0
MIN_LR = 0.33

# Minimum whale volume to consider evidence
MIN_EVIDENCE_VOLUME = 500  # $500 total


# Likelihoods (derived from historical backtesting/heuristics)
LIKELIHOOD_SMART_MONEY_STRONG_YES = 2.5
LIKELIHOOD_SMART_MONEY_STRONG_NO = 0.4
LIKELIHOOD_WHALE_SURGE_YES = 1.8
LIKELIHOOD_WHALE_SURGE_NO = 0.55

# =====================================================================
# Data classes
# =====================================================================

@dataclass
class Evidence:
    """Single piece of Bayesian evidence."""
    name: str
    description: str
    likelihood_ratio: float  # > 1 = supports YES, < 1 = supports NO
    emoji: str = "📊"

    @property
    def supports_yes(self) -> bool:
        return self.likelihood_ratio > 1.0

    @property
    def supports_no(self) -> bool:
        return self.likelihood_ratio < 1.0

    @property
    def strength(self) -> str:
        lr = self.likelihood_ratio
        if lr >= 2.0 or lr <= 0.5:
            return "strong"
        elif lr >= 1.3 or lr <= 0.77:
            return "moderate"
        return "weak"


@dataclass
class BayesianResult:
    """Result of Bayesian probability update."""
    prior: float                    # Starting probability (market price)
    posterior: float                 # Updated probability
    evidence_list: List[Evidence] = field(default_factory=list)
    combined_lr: float = 1.0        # Product of all LRs
    update_magnitude: float = 0.0   # |posterior - prior|

    @property
    def edge_vs_market(self) -> float:
        """How much our estimate differs from market."""
        return self.posterior - self.prior

    @property
    def is_overreaction(self) -> bool:
        """Market overreacted if price moved away from our posterior."""
        return abs(self.edge_vs_market) >= 0.08

    @property
    def direction(self) -> str:
        if self.posterior > self.prior + 0.02:
            return "YES"
        elif self.posterior < self.prior - 0.02:
            return "NO"
        return "NEUTRAL"

    @property
    def has_signal(self) -> bool:
        return len(self.evidence_list) > 0 and abs(self.edge_vs_market) >= 0.03


# =====================================================================
# Evidence Detectors
# =====================================================================

def detect_whale_surge(
    trades: List[Dict[str, Any]],
    window_hours: int = 2,
    avg_hourly_volume: float = 0.0,
) -> Optional[Evidence]:
    """
    Detect unusual whale volume surge in recent window.

    If recent whale volume is 3×+ above average → strong signal.
    Direction determined by which side (YES/NO) has more surge.
    """
    now = _time.time()
    cutoff = now - (window_hours * 3600)

    recent_yes = 0.0
    recent_no = 0.0

    for t in trades:
        ts = int(t.get("timestamp", 0) or 0)
        if ts < cutoff:
            continue

        amount = _get_trade_amount(t)
        if amount < 500:  # only whale trades
            continue

        side = str(t.get("side", "")).upper()
        idx = int(t.get("outcomeIndex", 0) or 0)
        is_yes = (side == "BUY" and idx == 0) or (side == "SELL" and idx == 1)

        if is_yes:
            recent_yes += amount
        else:
            recent_no += amount

    total_recent = recent_yes + recent_no
    if total_recent < MIN_EVIDENCE_VOLUME:
        return None

    # Calculate surge ratio
    if avg_hourly_volume > 0:
        expected = avg_hourly_volume * window_hours
        surge_ratio = total_recent / expected
    else:
        # No baseline: use total as indicator, assume moderate surge
        surge_ratio = 2.0 if total_recent > 5000 else 1.0

    if surge_ratio < 1.5:
        return None  # Not a surge

    # Direction: which side dominates the surge?
    if total_recent > 0:
        yes_share = recent_yes / total_recent
    else:
        return None

    # LR: surge + direction
    if surge_ratio >= 5.0:
        base_lr = 2.0  # massive surge
    elif surge_ratio >= 3.0:
        base_lr = 1.5
    else:
        base_lr = 1.3

    if yes_share > 0.6:
        lr = base_lr  # favors YES
        desc = f"Whale surge {surge_ratio:.1f}× avg → {yes_share*100:.0f}% YES"
    elif yes_share < 0.4:
        lr = 1.0 / base_lr  # favors NO
        desc = f"Whale surge {surge_ratio:.1f}× avg → {(1-yes_share)*100:.0f}% NO"
    else:
        return None  # mixed surge, not useful

    lr = _clamp_lr(lr)

    return Evidence(
        name="Whale Surge",
        description=desc,
        likelihood_ratio=lr,
        emoji="🐋",
    )


def detect_price_volume_divergence(
    trades: List[Dict[str, Any]],
    price_change_24h: float,
    window_hours: int = 4,
) -> Optional[Evidence]:
    """
    Detect divergence between price movement and whale behavior.

    Price falling + whales buying = overreaction → buy signal
    Price rising + whales selling = distribution → caution signal
    """
    now = _time.time()
    cutoff = now - (window_hours * 3600)

    whale_yes = 0.0
    whale_no = 0.0

    for t in trades:
        ts = int(t.get("timestamp", 0) or 0)
        if ts < cutoff:
            continue

        amount = _get_trade_amount(t)
        if amount < 500:
            continue

        side = str(t.get("side", "")).upper()
        idx = int(t.get("outcomeIndex", 0) or 0)
        is_yes = (side == "BUY" and idx == 0) or (side == "SELL" and idx == 1)

        if is_yes:
            whale_yes += amount
        else:
            whale_no += amount

    total = whale_yes + whale_no
    if total < MIN_EVIDENCE_VOLUME:
        return None

    whale_yes_share = whale_yes / total if total > 0 else 0.5

    # Price drop + whales buy YES = classic divergence (bullish)
    if price_change_24h < -0.05 and whale_yes_share > 0.60:
        strength = min(abs(price_change_24h) * 10, 1.0)  # 0–1
        lr = 1.3 + strength * 0.7  # 1.3–2.0
        desc = f"Price ↓{abs(price_change_24h)*100:.1f}% but whales {whale_yes_share*100:.0f}% YES"
        emoji = "📉"

    # Price rise + whales sell YES (buy NO) = distribution (bearish)
    elif price_change_24h > 0.05 and whale_yes_share < 0.40:
        strength = min(price_change_24h * 10, 1.0)
        lr = 1.0 / (1.3 + strength * 0.7)
        desc = f"Price ↑{price_change_24h*100:.1f}% but whales {(1-whale_yes_share)*100:.0f}% NO"
        emoji = "📈"
    else:
        return None  # No divergence

    lr = _clamp_lr(lr)

    return Evidence(
        name="Price-Volume Divergence",
        description=desc,
        likelihood_ratio=lr,
        emoji=emoji,
    )


def detect_smart_money_score(
    smart_score: float,
    smart_side: str,
) -> Optional[Evidence]:
    """
    Incorporate Smart Money Score (Holders Analysis) as Bayesian Evidence.
    """
    if smart_score < 60:
        return None  # Not significant

    # Map score 60-100 to Likelihood Ratio
    # 100 -> 2.5x (Strong)
    # 60 -> 1.2x (Weak)
    
    normalized = (smart_score - 60) / 40.0  # 0.0 to 1.0
    
    if smart_side == "YES":
        lr = 1.2 + (normalized * (LIKELIHOOD_SMART_MONEY_STRONG_YES - 1.2))
        desc = f"Smart Money Score {smart_score:.0f}/100 favors YES"
        emoji = "🧠"
    elif smart_side == "NO":
        # For NO, we want LR < 1. 
        # If Strong NO (100) -> 0.4
        # If Weak NO (60) -> 0.8
        lr_inv = 1.2 + (normalized * ( (1/LIKELIHOOD_SMART_MONEY_STRONG_NO) - 1.2 ))
        lr = 1.0 / lr_inv
        desc = f"Smart Money Score {smart_score:.0f}/100 favors NO"
        emoji = "🧠"
    else:
        return None

    lr = _clamp_lr(lr)
    
    return Evidence(
        name="Smart Money Holders",
        description=desc,
        likelihood_ratio=lr,
        emoji=emoji,
    )


def detect_consensus(
    trades: List[Dict[str, Any]],
    window_hours: int = 4,
    min_wallets: int = 3,
    min_trade_size: float = 5000,
) -> Optional[Evidence]:
    """
    Detect whale consensus: multiple large independent wallets betting same side.

    If 3+ different wallets each bet $5K+ on the same side in 4h → strong signal.
    """
    now = _time.time()
    cutoff = now - (window_hours * 3600)

    wallets_yes: Dict[str, float] = {}
    wallets_no: Dict[str, float] = {}

    for t in trades:
        ts = int(t.get("timestamp", 0) or 0)
        if ts < cutoff:
            continue

        amount = _get_trade_amount(t)
        if amount < min_trade_size:
            continue

        wallet = t.get("proxyWallet", t.get("maker", ""))
        if not wallet:
            continue

        side = str(t.get("side", "")).upper()
        idx = int(t.get("outcomeIndex", 0) or 0)
        is_yes = (side == "BUY" and idx == 0) or (side == "SELL" and idx == 1)

        if is_yes:
            wallets_yes[wallet] = wallets_yes.get(wallet, 0) + amount
        else:
            wallets_no[wallet] = wallets_no.get(wallet, 0) + amount

    yes_count = len(wallets_yes)
    no_count = len(wallets_no)

    if yes_count >= min_wallets and yes_count > no_count:
        lr = 1.4 + min((yes_count - min_wallets) * 0.15, 0.6)  # 1.4–2.0
        desc = f"{yes_count} whales (${min_trade_size/1000:.0f}K+) consensus YES"
        emoji = "🤝"
    elif no_count >= min_wallets and no_count > yes_count:
        lr = 1.0 / (1.4 + min((no_count - min_wallets) * 0.15, 0.6))
        desc = f"{no_count} whales (${min_trade_size/1000:.0f}K+) consensus NO"
        emoji = "🤝"
    else:
        return None

    lr = _clamp_lr(lr)

    return Evidence(
        name="Whale Consensus",
        description=desc,
        likelihood_ratio=lr,
        emoji=emoji,
    )


# =====================================================================
# Bayesian Updater
# =====================================================================

def bayesian_update(
    prior: float,
    trades: List[Dict[str, Any]],
    price_change_24h: float = 0.0,
    avg_hourly_volume: float = 0.0,
) -> BayesianResult:
    """
    Run full Bayesian update using all available evidence.

    Args:
        prior: Starting probability (typically market YES price)
        trades: Raw trade data from Data API
        price_change_24h: 24h price change of YES
        avg_hourly_volume: Average hourly whale volume (for surge detection)

    Returns:
        BayesianResult with posterior probability and evidence breakdown
    """
    evidence_list: List[Evidence] = []

    # Collect evidence
    e1 = detect_whale_surge(trades, window_hours=2, avg_hourly_volume=avg_hourly_volume)
    if e1:
        evidence_list.append(e1)

    e2 = detect_price_volume_divergence(trades, price_change_24h, window_hours=4)
    if e2:
        evidence_list.append(e2)

    e3 = detect_consensus(trades, window_hours=4, min_wallets=3, min_trade_size=5000)
    if e3:
        evidence_list.append(e3)

    # Sequential Bayesian update using likelihood ratios
    # Convert probability to odds, multiply by LRs, convert back
    prior_clamped = max(0.01, min(0.99, prior))
    odds = prior_clamped / (1.0 - prior_clamped)

    combined_lr = 1.0
    for ev in evidence_list:
        odds *= ev.likelihood_ratio
        combined_lr *= ev.likelihood_ratio

    posterior = odds / (1.0 + odds)
    posterior = max(0.03, min(0.97, posterior))

    return BayesianResult(
        prior=prior,
        posterior=posterior,
        evidence_list=evidence_list,
        combined_lr=combined_lr,
        update_magnitude=abs(posterior - prior),
    )


def bayesian_update_with_holders(
    prior: float,
    trades: List[Dict[str, Any]],
    price_change_24h: float,
    avg_hourly_volume: float,
    smart_score: float,
    smart_side: str,
) -> BayesianResult:
    """
    Enhanced Bayesian update including Holders Analysis (Smart Money) evidence.
    """
    evidence_list: List[Evidence] = []

    # 1. Whale Surge
    e1 = detect_whale_surge(trades, window_hours=2, avg_hourly_volume=avg_hourly_volume)
    if e1: evidence_list.append(e1)

    # 2. Divergence
    e2 = detect_price_volume_divergence(trades, price_change_24h, window_hours=4)
    if e2: evidence_list.append(e2)

    # 3. Consensus
    e3 = detect_consensus(trades, window_hours=4, min_wallets=3, min_trade_size=5000)
    if e3: evidence_list.append(e3)

    # 4. Smart Money (Holders)
    e4 = detect_smart_money_score(smart_score, smart_side)
    if e4: evidence_list.append(e4)

    # Prior check
    prior_clamped = max(0.01, min(0.99, prior))
    
    # Odds form
    odds = prior_clamped / (1.0 - prior_clamped)

    combined_lr = 1.0
    for ev in evidence_list:
        odds *= ev.likelihood_ratio
        combined_lr *= ev.likelihood_ratio

    # Posterior
    posterior = odds / (1.0 + odds)
    posterior = max(0.01, min(0.99, posterior))

    return BayesianResult(
        prior=prior,
        posterior=posterior,
        evidence_list=evidence_list,
        combined_lr=combined_lr,
        update_magnitude=abs(posterior - prior),
    )


# =====================================================================
# Helpers
# =====================================================================

def _get_trade_amount(trade: Dict) -> float:
    """Extract USDC amount from trade dict."""
    usdc_size = trade.get("usdcSize")
    if usdc_size is not None:
        try:
            return abs(float(usdc_size))
        except (ValueError, TypeError):
            pass
    try:
        size = float(trade.get("size", 0) or 0)
        price = float(trade.get("price", 0) or 0)
        return size * price
    except (ValueError, TypeError):
        return 0.0


def _clamp_lr(lr: float) -> float:
    """Clamp likelihood ratio to prevent extreme updates."""
    return max(MIN_LR, min(MAX_LR, lr))
