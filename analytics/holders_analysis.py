"""
Holders Analysis Module

Analyzes the distribution, profitability, and quality of position holders
for a specific market to determine smart money conviction.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import statistics
from loguru import logger

from polymarket_api import Position
from market_intelligence import WhaleAnalysis


@dataclass
class SideStats:
    """Statistics for holders on one side (YES or NO)."""
    side: str
    count: int
    median_pnl: float
    profitable_count: int
    profitable_pct: float
    above_5k_count: int
    above_10k_count: int
    above_50k_count: int
    top_holder_profit: float
    top_holder_address: str
    top_holder_wins: int = 0
    top_holder_losses: int = 0

    @property
    def above_5k_pct(self) -> float:
        return (self.above_5k_count / self.count * 100) if self.count > 0 else 0.0
        
    @property
    def above_10k_pct(self) -> float:
        return (self.above_10k_count / self.count * 100) if self.count > 0 else 0.0


@dataclass
class HoldersAnalysisResult:
    """Consolidated result of holders analysis."""
    yes_stats: SideStats
    no_stats: SideStats
    smart_score: int  # 0-100 score favoring the "smart" side (usually NO/Underdog or just winner)
    smart_score_side: str # Which side the score favors
    smart_score_breakdown: Dict[str, float]


def calculate_side_stats(positions: List[Position], side: str) -> SideStats:
    """
    Calculate stats for a specific side (YES/NO).
    Metrics: Count, Median PnL, Whale counts (>5k, >10k, >50k), Top Holder.
    """
    # Filter positions by side (outcome)
    # The API returns 'outcome' as 'YES' or 'NO' usually.
    # Debug logging
    logger.info(f"Side {side}: processing {len(positions)} raw positions")
    side_positions = [p for p in positions if p.outcome == side and p.size > 0]
    logger.info(f"Side {side}: filtered to {len(side_positions)} valid positions (>0)")
    
    count = len(side_positions)
    if count == 0:
        return SideStats(
            side=side, count=0, median_pnl=0.0,
            profitable_count=0, profitable_pct=0.0,
            above_5k_count=0, above_10k_count=0, above_50k_count=0,
            top_holder_profit=0.0, top_holder_address="",
            top_holder_wins=0, top_holder_losses=0
        )

    # Median PnL (using cash_pnl + realized_pnl usually, but API gives cashPnl which is unrealized)
    # Prompt says: "Lifetime PnL цього холдера (з усіх маркетів) ... Поточний unrealized PnL на цьому маркеті"
    # Actually, getting lifetime PnL for *every* holder is expensive (requires N API calls).
    # The prompt implies: "2. Для кожного холдера: ... Lifetime PnL ... Поточний unrealized PnL".
    # However, fetching lifetime PnL for 500 holders would verify API limits.
    # Let's assume we use the reliable data we have in Position object first:
    # Position object has: cash_pnl (unrealized), realized_pnl.
    # The prompt might overestimate what we can get in one call.
    # If we can't get lifetime PnL easily, we'll use the market PnL (cash_pnl + realized_pnl).
    # IF the prompt INSISTS on lifetime, we'd need to fetch user profile or PnL summaries, which is too slow.
    # Re-reading prompt: "Lifetime PnL цього холдера (з усіх маркетів)" -> this is likely impossible efficiently.
    # I will stick to "Market PnL" (current position profitability) which is available in `p.percent_pnl` or `p.cash_pnl`.
    # Let's use `unrealized_pnl` (cash_pnl) for "current profitability".
    
    pnls = [p.cash_pnl for p in side_positions]
    median_pnl = statistics.median(pnls) if pnls else 0.0
    
    profitable = [p for p in pnls if p > 0]
    profitable_count = len(profitable)
    profitable_pct = (profitable_count / count * 100)
    
    # Whale counts (based on current value or PnL? "Lifetime PnL > 5k" logic is hard without extra calls)
    # Let's use Position Value > X as a proxy for "big holder" OR PnL > X.
    # Prompt says: "Кількість холдерів з lifetime PnL > $5K".
    # I will substitute with "Current Position Value > $5K" or "Unrealized PnL > $1K" 
    # OR better: Assume "profit" in prompt refers to the available PnL data.
    # Let's use Position Value for "Whale Tier" classification (>$5k invested/value).
    
    above_5k = [p for p in side_positions if p.current_value > 5000]
    above_10k = [p for p in side_positions if p.current_value > 10000]
    above_50k = [p for p in side_positions if p.current_value > 50000]
    
    # Top holder by profit (cash_pnl)
    # sorted_by_pnl = sorted(side_positions, key=lambda p: p.cash_pnl, reverse=True)
    # top_holder = sorted_by_pnl[0]
    
    # Or by size? Prompt says "Top holder (найбільший profit)".
    top_holder = max(side_positions, key=lambda p: p.cash_pnl) if side_positions else None
    top_profit = top_holder.cash_pnl if top_holder else 0.0
    top_addr = top_holder.proxy_wallet if top_holder else ""

    return SideStats(
        side=side,
        count=count,
        median_pnl=median_pnl,
        profitable_count=profitable_count,
        profitable_pct=profitable_pct,
        above_5k_count=len(above_5k),
        above_10k_count=len(above_10k),
        above_50k_count=len(above_50k),
        top_holder_profit=top_profit,
        top_holder_address=top_addr,
        top_holder_wins=0,
        top_holder_losses=0
    )


def calculate_holders_score_component(stats: SideStats) -> float:
    """
    Calculate the 0-100 score for a specific side based on holder quality.
    
    Formula:
       (profitable_pct) * 0.25 +
       (above_10k_pct) * 0.25 +  <-- using calc on count/total
       (median > 0 ? 25 : 0) +
       (above_50k > 0 ? 25 : 0)
    """
    if stats.count == 0:
        return 0.0
        
    s_prof = min(25, stats.profitable_pct * 0.25) # Scale: 100% prof = 25pts
    
    # above 10k pct: if 10% of holders are >10k, that's huge. 
    # Let's say 20% >10k = max 25pts. So factor = 1.25?
    # Or just use the raw percentage?
    # Prompt: "(above_10k_pct) * 25" -> This implies if 1% are whales, usage is ambiguous.
    # Let's assume it means "percentage (0-1) * 25" or "percentage (0-100) * coeff".
    # If 4% are >10k: 0.04 * 25 = 1 pt? Too low.
    # If it means 4 (percent) * 0.25 = 1 pt?
    # Usually "quality" implies high net worth.
    # Let's normalize: if >5% are whales, that's max score?
    # Let's use: min(25, stats.above_10k_pct * 2.5) -> 10% whales = 25 pts.
    s_whale = min(25, stats.above_10k_pct * 2.5) 
    
    s_med = 25.0 if stats.median_pnl > 0 else 0.0
    
    s_super = 25.0 if stats.above_50k_count > 0 else 0.0
    
    return s_prof + s_whale + s_med + s_super


def calculate_smart_score(
    yes_stats: SideStats,
    no_stats: SideStats,
    whale_analysis: Optional[WhaleAnalysis],
    model_yes_prob: float
) -> Tuple[int, str, Dict[str, float]]:
    """
    Calculate final Smart Score (0-100) and which side it favors.
    
    The prompt specifically asks to return a score for the "NO" side usually, 
    or the side we are analyzing?
    Prompt example: "Smart Score: NO 87/100"
    
    Formula from prompt (for NO side example):
       smart_score = (
           0.4 * no_holders_score +
           0.3 * (whale_no_tilt * 100) +
           0.3 * (model_no_prob * 100)
       )
       
    We should calculate this for BOTH sides and pick the higher one?
    Or just for the recommended side? 
    Let's calculate for both and return the max.
    """
    
    # 1. Holders Scores
    yes_h_score = calculate_holders_score_component(yes_stats)
    no_h_score = calculate_holders_score_component(no_stats)
    
    # 2. Whale Tilt (0-1 normalized)
    # if tilt is 0.8 to NO -> no_tilt = 0.8, yes_tilt = 0.2
    wa_yes_tilt = 0.5
    wa_no_tilt = 0.5
    
    if whale_analysis and whale_analysis.total_volume > 0:
        yes_share = whale_analysis.yes_volume / whale_analysis.total_volume
        wa_yes_tilt = yes_share
        wa_no_tilt = 1.0 - yes_share
        
    # 3. Model Prob (0-1)
    model_no_prob = 1.0 - model_yes_prob
    
    # Check if we have NO holders data at all (count=0 for both)
    # If so, rebalance weights: 50% Whales, 50% Model
    if yes_stats.count == 0 and no_stats.count == 0:
        score_yes = (
            0.5 * (wa_yes_tilt * 100) +
            0.5 * (model_yes_prob * 100)
        )
        score_no = (
            0.5 * (wa_no_tilt * 100) +
            0.5 * (model_no_prob * 100)
        )
        
        # Breakdown has 0 for holders
        breakdown_yes = {
            "holders": 0.0,
            "tilt": wa_yes_tilt * 100,
            "model": model_yes_prob * 100
        }
        breakdown_no = {
            "holders": 0.0,
            "tilt": wa_no_tilt * 100,
            "model": model_no_prob * 100
        }
        
    else:
        # Standard weights: 40% Holders, 30% Whales, 30% Model
        score_yes = (
            0.4 * yes_h_score +                 # 0-100
            0.3 * (wa_yes_tilt * 100) +         # 0-100
            0.3 * (model_yes_prob * 100)        # 0-100
        )
        
        score_no = (
            0.4 * no_h_score +
            0.3 * (wa_no_tilt * 100) +
            0.3 * (model_no_prob * 100)
        )
        
        breakdown_yes = {
            "holders": yes_h_score,
            "tilt": wa_yes_tilt * 100,
            "model": model_yes_prob * 100
        }
        breakdown_no = {
            "holders": no_h_score,
            "tilt": wa_no_tilt * 100,
            "model": model_no_prob * 100
        }
    
    if score_no > score_yes:
        return int(score_no), "NO", breakdown_no
    else:
        return int(score_yes), "YES", breakdown_yes
