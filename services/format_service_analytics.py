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
    
    # 1. PROBABILITIES (Consensus is King)
    # Use the consensus model_probability computed by orchestrator.
    # It safely blends Signal, Monte Carlo, and Bayesian.
    p_model = analysis.model_probability
    
    # Safety Check: If p_model > 1.0 (e.g. 300.0), normalize it.
    # This prevents the "300%" bug if upstream modules return percentages.
    if p_model > 1.0:
        p_model = p_model / 100.0
    
    # Ensure it's clamped 0-1
    p_model = max(0.0, min(1.0, p_model))

    p_market = m.yes_price
    
    # 2. EDGE CALCULATION
    # True edge = Model - Market
    edge_abs = p_model - p_market
    edge_pp = edge_abs * 100  # Percentage points (e.g. +1.5 or -2.0)
    
    # ROI (Return on Investment)
    edge_roi = (edge_abs / p_market) * 100 if p_market > 0 else 0.0
    
    # 3. RECOMMENDATION LOGIC
    # Rule: Edge < 2 pp OR Kelly says 0 -> SKIP
    # Rule: Edge >= 2 pp AND Kelly > 0 -> CONSIDER
    
    THRESHOLD_PP = 2.0
    k = analysis.kelly
    kelly_capped = k.kelly_full * 100
    rec_size_pct = k.size_pct
    
    # Logic
    is_positive_setup = (edge_pp >= THRESHOLD_PP) and (kelly_capped > 0)
    
    if is_positive_setup:
        # RECOMMEND
        side_text = "YES" if edge_abs > 0 else "NO"
        side_text_loc = side_text # Could localize if needed
        short_intro_key = "deep.shortly"
        conclusion_key = "deep.final_word"
        emoji = "🟢"
    else:
        # SKIP
        # Even if edge is positive but small (e.g. +1%), we skip.
        side_text = "N/A" # Not really used in skip
        short_intro_key = "deep.shortly_skip"
        conclusion_key = "deep.final_word_skip"
        emoji = "🔴" if edge_pp < 0 else "🟡" # Red for negative, Yellow for small positive

    # 4. SCENARIOS (MC)
    mc = analysis.monte_carlo
    mc_low = "N/A"
    mc_high = "N/A"
    win_prob = p_model * 100 # Consistent with p_model

    if mc and mc.mode == "crypto":
        # Only use MC percentiles if it's actually a crypto/asset market
        mc_low = f"${_fmt(mc.percentile_5)}"
        mc_high = f"${_fmt(mc.percentile_95)}"
        # If MC is the driver (crypto), win_prob matches MC
        # But we stuck to p_model (consensus) for consistency. 
        # Usually for crypto p_model is heavily weighted to MC anyway.
    
    # 5. RISKS / CONTEXT
    liq_val = m.liquidity
    liq_label = get_text("liq.high" if liq_val > 500000 else "liq.med" if liq_val > 100000 else "liq.low", lang)
    vol_label = get_text("vol.med", lang) 
    smart_flow_side = "YES" if p_model > p_market else "NO"
    
    # --- Construct Message ---
    
    # Header & Summary
    text = f"{get_text('deep.title', lang)}\n"
    text += f"{html.escape(m.question)}\n\n"
    
    # Conditional Summary
    if is_positive_setup:
        text += f"{get_text(short_intro_key, lang, side=side_text)}\n\n"
    else:
        text += f"{get_text(short_intro_key, lang)}\n\n"

    # Prices & Vol
    text += f"{get_text('deep.prices_vol', lang)}\n"
    text += f"{get_text('deep.prices_line', lang, yes=round(m.yes_price*100, 1), no=round((1-m.yes_price)*100, 1))}\n"
    text += f"{get_text('deep.liq_line', lang, val=round(m.liquidity/1000000, 1))}\n\n"
    
    # Flow
    text += f"{get_text('deep.flow', lang)}\n"
    text += f"{get_text('deep.tilt_line', lang, yes=50, no=50)}\n"  # Placeholder
    text += f"{get_text('deep.last_whale', lang, val=0, side='N/A', time='0m')}\n\n"
    
    # Probabilities
    # Note: p_model and p_market are 0.0-1.0 here, multiplied by 100 for display
    text += f"{get_text('deep.probs', lang)}\n"
    text += f"{get_text('deep.prob_market', lang, pct=round(p_market*100, 1))}\n"
    text += f"{get_text('deep.prob_model', lang, pct=round(p_model*100, 1))}\n"
    
    # Edge Line with formatted sign
    edge_sign = "+" if edge_pp > 0 else ""
    formatted_edge = f"{edge_sign}{round(edge_pp, 1)}" # e.g. "+5.2" or "-1.3" or "0.0"
    text += f"{get_text('deep.edge_line', lang, emoji=emoji, diff=formatted_edge, roi=round(edge_roi, 1))}\n\n"
    
    # Sizing
    text += f"{get_text('deep.sizing_title', lang)}\n"
    text += f"{get_text('deep.edge_expl', lang, m_pct=round(p_market*100, 1), my_pct=round(p_model*100, 1), diff=round(edge_abs*100, 1))}\n"
    text += f"{get_text('deep.kelly_capped', lang, pct=round(kelly_capped, 1))}\n"
    text += f"{get_text('deep.cons_stake', lang, pct=round(rec_size_pct, 1), fract=k.fraction_name)}\n\n"
    
    # Scenarios
    text += f"{get_text('deep.risk_scenarios', lang)}\n"
    text += f"{get_text('deep.perc_5', lang, val=mc_low)}\n"
    text += f"{get_text('deep.perc_95', lang, val=mc_high)}\n"
    text += f"{get_text('deep.win_prob', lang, pct=round(win_prob, 1))}\n\n"
    
    # Risk Factors
    text += f"{get_text('deep.risks_title', lang)}\n"
    text += f"{get_text('deep.risk_liq', lang, val=liq_label)}\n"
    text += f"{get_text('deep.risk_vol', lang, val=vol_label)}\n"
    text += f"{get_text('deep.risk_flow', lang, side=smart_flow_side)}\n\n"
    
    # Conclusion
    text += f"{get_text('deep.conclusion', lang)}\n"
    
    if is_positive_setup:
        text += f"{get_text(conclusion_key, lang, side=side_text, pct=round(rec_size_pct, 1))}"
    else:
        # Pass edge_pp to the negative summary
        text += f"{get_text(conclusion_key, lang, edge=round(edge_pp, 1))}"

    return text

def _fmt(val: float) -> str:
    if isinstance(val, str): return val
    if val >= 1000: return f"{val:,.0f}"
    return f"{val:.2f}"
