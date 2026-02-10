"""
BetSpy Deep Analysis Formatter

Formats DeepAnalysis results into a Telegram-friendly HTML message.
"""

import html
from typing import Optional

from i18n import get_text
from services.format_service import format_volume, format_price
from analytics.orchestrator import DeepAnalysis


def format_deep_analysis(analysis: DeepAnalysis, lang: str) -> str:
    """Format complete deep analysis into Telegram HTML message."""
    m = analysis.market
    q = html.escape(m.question[:80])

    text = f"🔬 <b>DEEP ANALYSIS</b>\n"
    text += f"<b>{q}</b>\n"
    text += f"{'─' * 28}\n\n"

    # Market info
    text += f"💰 YES <b>{format_price(m.yes_price)}</b> · NO <b>{format_price(m.no_price)}</b>"
    text += f" · 💧 {format_volume(m.liquidity)}\n"

    if m.days_to_close == 0:
        text += f"⏳ {get_text('detail.closes_today', lang)}\n"
    elif m.days_to_close == 1:
        text += f"⏳ {get_text('detail.closes_tomorrow', lang)}\n"
    else:
        text += f"⏳ {get_text('deep.days_left', lang, days=m.days_to_close)}\n"

    text += "\n"

    # ── PROBABILITY MODELS ──
    text += f"<b>── {get_text('deep.section_probability', lang)} ──</b>\n"

    if analysis.monte_carlo:
        mc = analysis.monte_carlo
        mc_pct = f"{mc.probability_yes * 100:.1f}%"
        mode_label = "10K sims" if mc.mode == "crypto" else "generic"
        text += f"🎲 Monte Carlo ({mode_label}): <b>{mc_pct}</b> YES\n"

    if analysis.bayesian and analysis.bayesian.has_signal:
        bay_pct = f"{analysis.bayesian.posterior * 100:.1f}%"
        text += f"🧠 Bayesian: <b>{bay_pct}</b> YES\n"

    text += f"📊 Signal engine: {analysis.signal_probability * 100:.1f}% YES\n"
    text += f"📈 Market price: {analysis.market_price * 100:.1f}% YES\n"
    text += f"✅ <b>Consensus: ~{analysis.model_probability * 100:.1f}% YES</b>\n\n"

    # ── EDGE & SIZING ──
    text += f"<b>── {get_text('deep.section_edge', lang)} ──</b>\n"

    if analysis.kelly:
        k = analysis.kelly
        text += f"📐 Edge: <b>{k.edge_pct:+.1f}%</b>"
        text += f" (model {k.model_probability*100:.0f}% vs market {k.market_price*100:.0f}%)\n"

        if k.is_significant:
            fname = _fraction_name(k.fraction)
            text += f"💰 Kelly ({fname}): <b>${k.recommended_size:.0f}</b>"
            text += f" on {k.recommended_side} ({k.size_pct:.1f}%)\n"
            if k.potential_profit > 0:
                text += f"🎯 Potential: +${k.potential_profit:.0f} if wins\n"
        else:
            text += f"⚠️ {get_text('deep.edge_too_small', lang)}\n"
    else:
        text += f"📐 {get_text('deep.no_edge_data', lang)}\n"

    text += "\n"

    # ── TIME & VOLATILITY ──
    if analysis.greeks:
        text += f"<b>── {get_text('deep.section_greeks', lang)} ──</b>\n"
        g = analysis.greeks
        th = g.theta

        if th.dominant_side == "YES":
            text += f"⏳ Theta: YES {th.theta_yes:+.1f}¢/day\n"
        else:
            text += f"⏳ Theta: NO {th.theta_no:+.1f}¢/day\n"

        if th.is_opportunity:
            text += f"💡 {get_text('deep.theta_anomaly', lang)}\n"

        if th.time_value > 0.01:
            tv = f"{th.time_value * 100:.1f}"
            text += f"⏱ {get_text('deep.time_value', lang, value=tv)}\n"

        v = g.vega
        if v.historical_vol_7d > 0:
            text += f"📊 Vol 7d: {v.historical_vol_7d*100:.1f}%"
            text += f" · 24h: {v.recent_vol_24h*100:.1f}%\n"
            if v.is_sleeping:
                text += f"😴 {get_text('deep.vega_sleeping', lang)}\n"
            elif v.is_spiking:
                text += f"⚡ {get_text('deep.vega_spiking', lang)}\n"

        text += "\n"

    # ── WHALE INTELLIGENCE ──
    if analysis.bayesian and analysis.bayesian.evidence_list:
        bay = analysis.bayesian
        text += f"<b>── {get_text('deep.section_whale_intel', lang)} ──</b>\n"

        for ev in bay.evidence_list:
            text += f"{ev.emoji} {ev.description}\n"

        if bay.is_overreaction:
            text += f"⚠️ {get_text('deep.overreaction', lang)}\n"

        text += "\n"

    # ── MONTE CARLO DISTRIBUTION (crypto only) ──
    if analysis.monte_carlo and analysis.monte_carlo.mode == "crypto":
        mc = analysis.monte_carlo
        if mc.distribution:
            text += f"<b>── {get_text('deep.section_distribution', lang)} ──</b>\n"

            if mc.current_asset_price > 0:
                text += f"💲 {mc.coin_id.title()}: ${mc.current_asset_price:,.0f}"
                text += f" → target ${mc.threshold:,.0f}\n"

            for label, pct in mc.distribution:
                bar_len = max(0, min(15, int(pct * 15)))
                bar = "█" * bar_len + "░" * (15 - bar_len)
                text += f"  {bar} {pct*100:4.1f}% {label}\n"

            text += "\n"

    # ── VERDICT ──
    text += f"{'─' * 28}\n"

    side = analysis.recommended_side
    if analysis.has_edge and side != "NEUTRAL":
        emoji = "🟢" if side == "YES" else "🔴"
        entry = m.yes_price if side == "YES" else m.no_price
        text += f"{emoji} <b>BUY {side} @ {format_price(entry)}</b>\n"
        text += f"Confidence: {analysis.confidence}/100"
        text += f" · Edge: {analysis.edge_pct:+.1f}%"
        if analysis.kelly and analysis.kelly.is_significant:
            text += f" · Size: ${analysis.kelly.recommended_size:.0f}"
        text += "\n"
    else:
        text += f"⚪ {get_text('deep.no_clear_edge', lang)}\n"

    # Warnings
    if analysis.errors:
        text += f"\n⚠️ {len(analysis.errors)} module(s) had issues\n"

    return text


def _fraction_name(f: float) -> str:
    """Human-readable Kelly fraction name."""
    if f <= 0.15:
        return "⅛ Kelly"
    elif f <= 0.30:
        return "¼ Kelly"
    elif f <= 0.55:
        return "½ Kelly"
    return "Full Kelly"
