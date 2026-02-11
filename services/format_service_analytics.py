"""
BetSpy Deep Analysis Formatter

Formats DeepAnalysis results into a structured "Quantitative Report".
"""

import html
from typing import Optional

from services.format_service import format_volume, format_price
from analytics.orchestrator import DeepAnalysis
from i18n import get_text


def format_deep_analysis(analysis: DeepAnalysis, lang: str) -> str:
    """Format complete deep analysis into a Quant Report (Detailed Analysis Style)."""
    m = analysis.market
    
    # --- Prepare Data ---
    
    # 1. VALUATION
    if analysis.monte_carlo and analysis.monte_carlo.mode == "crypto":
        p_model = analysis.monte_carlo.probability_yes
    elif analysis.bayesian:
        p_model = analysis.bayesian.posterior
    else:
        p_model = analysis.model_probability

    p_market = m.yes_price
    
    # Edge calculation
    edge_abs = p_model - p_market
    edge_pct = (edge_abs / p_market) * 100 if p_market > 0 else 0.0
    
    emoji = "🟢" if edge_abs > 0 else "🔴"
    
    # 2. SIZING
    k = analysis.kelly
    rec_size_pct = k.size_pct
    kelly_capped = k.kelly_full * 100
    
    # 3. SCENARIOS (MC)
    mc = analysis.monte_carlo
    mc_low = "N/A"
    mc_high = "N/A"
    win_prob = p_model * 100

    if mc and mc.mode == "crypto":
        mc_low = f"${_fmt(mc.percentile_5)}"
        mc_high = f"${_fmt(mc.percentile_95)}"
        win_prob = mc.probability_yes * 100
    
    # Risks placeholders (logic would need to be computed, here using simple heuristics/placeholders)
    liq_val = m.liquidity
    liq_label = get_text("liq.high" if liq_val > 500000 else "liq.med" if liq_val > 100000 else "liq.low", lang)
    vol_label = get_text("vol.med", lang) # Placeholder
    smart_flow_side = "YES" if p_model > p_market else "NO"
    
    # Side Text
    side_text = "YES" if p_model > 0.5 else "NO"

    # --- Construct Message Using i18n Keys ---
    
    text = (
        f"{get_text('deep.title', lang)}\n"
        f"{html.escape(m.question)}\n\n"
        f"{get_text('deep.shortly', lang, side=side_text.upper())}\n\n"
        
        f"{get_text('deep.prices_vol', lang)}\n"
        f"{get_text('deep.prices_line', lang, yes=round(m.yes_price*100, 1), no=round((1-m.yes_price)*100, 1))}\n"
        f"{get_text('deep.liq_line', lang, val=round(m.liquidity/1000000, 1))}\n\n"
        
        f"{get_text('deep.flow', lang)}\n"
        # Placeholder for tilt numbers as they are not directly in DeepAnalysis object in this context
        f"{get_text('deep.tilt_line', lang, yes=50, no=50)}\n" 
        f"{get_text('deep.last_whale', lang, val=0, side='N/A', time='0m')}\n\n"
        
        f"{get_text('deep.probs', lang)}\n"
        f"{get_text('deep.prob_market', lang, pct=round(p_market*100, 1))}\n"
        f"{get_text('deep.prob_model', lang, pct=round(p_model*100, 1))}\n"
        f"{get_text('deep.edge_line', lang, emoji=emoji, diff=round(edge_abs*100, 1), roi=round(edge_pct, 1))}\n\n"
        
        f"{get_text('deep.sizing_title', lang)}\n"
        f"{get_text('deep.edge_expl', lang, m_pct=round(p_market*100, 1), my_pct=round(p_model*100, 1), diff=round(edge_abs*100, 1))}\n"
        f"{get_text('deep.kelly_capped', lang, pct=round(kelly_capped, 1))}\n"
        f"{get_text('deep.cons_stake', lang, pct=round(rec_size_pct, 1), fract=k.fraction_name)}\n\n"
        
        f"{get_text('deep.risk_scenarios', lang)}\n"
        f"{get_text('deep.perc_5', lang, val=mc_low)}\n"
        f"{get_text('deep.perc_95', lang, val=mc_high)}\n"
        f"{get_text('deep.win_prob', lang, pct=round(win_prob, 1))}\n\n"
        
        f"{get_text('deep.risks_title', lang)}\n"
        f"{get_text('deep.risk_liq', lang, val=liq_label)}\n"
        f"{get_text('deep.risk_vol', lang, val=vol_label)}\n"
        f"{get_text('deep.risk_flow', lang, side=smart_flow_side)}\n\n"
        
        f"{get_text('deep.conclusion', lang)}\n"
        f"{get_text('deep.final_word', lang, side=side_text.upper(), pct=round(rec_size_pct, 1))}"
    )

    return text

def _fmt(val: float) -> str:
    if isinstance(val, str): return val
    if val >= 1000: return f"{val:,.0f}"
    return f"{val:.2f}"
