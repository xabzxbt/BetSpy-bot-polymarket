"""
Market formatting service — all display formatting in one place.

Extracted from handlers_intelligence.py to:
1. Remove formatting logic from handlers (SRP)
2. Make all strings go through i18n
3. Allow reuse in notifications, watchlist, etc.
"""

import html
import time
from typing import Any, List
from loguru import logger

from i18n import get_text
from market_intelligence import (
    MarketStats, BetRecommendation, SignalStrength, MarketQuality,
)


def format_volume(volume: float) -> str:
    if volume >= 1_000_000:
        return f"${volume/1_000_000:.1f}M"
    elif volume >= 1_000:
        return f"${volume/1_000:.0f}K"
    return f"${volume:.0f}"


def format_price(price: float) -> str:
    return f"{int(price * 100)}¢"


def format_signal_emoji(strength: SignalStrength) -> str:
    return {
        SignalStrength.STRONG_BUY: "🟢🟢",
        SignalStrength.BUY: "🟢",
        SignalStrength.MODERATE: "🟡",
        SignalStrength.WEAK: "🟠",
        SignalStrength.AVOID: "🔴",
    }.get(strength, "⚪")


def format_quality_label(quality: MarketQuality, lang: str) -> str:
    key_map = {
        MarketQuality.HIGH_CONVICTION: "quality.high_conviction",
        MarketQuality.MODERATE_SIGNAL: "quality.moderate_signal",
        MarketQuality.NOISY: "quality.noisy",
        MarketQuality.LOW_LIQUIDITY: "quality.low_liquidity",
        MarketQuality.AVOID: "quality.avoid",
    }
    return get_text(key_map.get(quality, "quality.avoid"), lang)


def format_whale_block(wa: Any, lang: str) -> str:
    """Format whale analysis block — fully i18n."""
    if not wa or not wa.is_significant:
        return ""

    if wa.duration_text:
        text = get_text("detail.smart_money_window", lang, window=wa.duration_text) + "\n"
    else:
        text = get_text("detail.smart_money", lang) + "\n"

    # Sentiment
    if wa.dominance_side == "NEUTRAL":
        text += f"⚖️ {wa.sentiment}\n"
    else:
        text += f"💡 <b>{wa.sentiment}</b> ({wa.dominance_pct:.0f}%)\n"

    # Bar
    bar_len = 10
    yes_share = wa.yes_volume / wa.total_volume if wa.total_volume > 0 else 0.5
    filled = max(0, min(bar_len, int(yes_share * bar_len)))
    bar = "▓" * filled + "░" * (bar_len - filled)
    text += f"YES {bar} NO\n\n"

    # Top trade
    if wa.top_trade_size > 0:
        text += get_text("detail.top_trade", lang, vol=format_volume(wa.top_trade_size), side=wa.top_trade_side) + "\n"

    # Last activity
    if wa.last_trade_timestamp > 0:
        hours = wa.hours_since_last_trade
        if hours < 1:
            ts = f"{int(hours * 60)}m ago"
        elif hours < 24:
            ts = f"{int(hours)}h ago"
        else:
            ts = "1d+ ago"
        text += get_text("detail.last_activity", lang, time=ts, side=wa.last_trade_side) + "\n"

    text += "\n"

    # Breakdown
    text += get_text("detail.yes_breakdown", lang, vol=format_volume(wa.yes_volume), count=wa.yes_count) + "\n"
    text += get_text("detail.no_breakdown", lang, vol=format_volume(wa.no_volume), count=wa.no_count) + "\n"
    text += get_text("detail.total_sm_vol", lang, vol=format_volume(wa.total_volume), pct=f"{wa.large_whale_share_pct:.0f}") + "\n"

    return text


def format_market_card(market: MarketStats, index: int, lang: str) -> str:
    """Compact card for list view."""
    sig = format_signal_emoji(market.signal_strength)
    wa = market.whale_analysis

    whale_str = "—"
    if wa and wa.is_significant:
        whale_str = f"{wa.dominance_side} {wa.dominance_pct:.0f}%"

    if market.days_to_close == 0:
        time_str = get_text("card.today", lang)
    elif market.days_to_close == 1:
        time_str = get_text("card.tomorrow", lang)
    else:
        time_str = get_text("card.days", lang, days=market.days_to_close)

    q = html.escape(market.question[:55])
    ellipsis = "..." if len(market.question) > 55 else ""

    return (
        f"<b>{index}. {q}{ellipsis}</b>\n"
        f"   💰 YES {format_price(market.yes_price)} · NO {format_price(market.no_price)}"
        f"  📊 {format_volume(market.volume_24h)}\n"
        f"   🐋 {whale_str}  {time_str}\n"
        f"   {sig} <b>{market.signal_score}/100 → {market.recommended_side}</b>\n"
    )


def format_market_detail(market: MarketStats, rec: BetRecommendation, lang: str) -> str:
    """Full market detail card — fully i18n."""
    sig = format_signal_emoji(market.signal_strength)
    q = html.escape(market.question)

    text = f"<b>{q}</b>\n{'─' * 28}\n\n"

    # Prices
    text += f"💰 YES: <b>{format_price(market.yes_price)}</b>  ·  NO: <b>{format_price(market.no_price)}</b>\n"
    text += get_text("detail.vol_24h", lang, vol=format_volume(market.volume_24h), total=format_volume(market.volume_total)) + "\n"

    if market.liquidity > 0:
        text += get_text("detail.liquidity", lang, vol=format_volume(market.liquidity)) + "\n"

    # Time
    if market.days_to_close < 0:
        text += "🔒 <b>" + get_text("event_finished", lang) + "</b>\n"
    elif market.days_to_close == 0:
        text += get_text("detail.closes_today", lang) + "\n"
    elif market.days_to_close == 1:
        text += get_text("detail.closes_tomorrow", lang) + "\n"
    else:
        text += get_text("detail.closes_date", lang, date=market.end_date.strftime("%d.%m.%Y"), days=market.days_to_close) + "\n"

    text += "\n"

    # Whale analysis
    wa_block = format_whale_block(market.whale_analysis, lang)
    if wa_block:
        text += wa_block
    else:
        text += get_text("detail.smart_money", lang) + "\n"
        text += get_text("detail.no_whale_activity", lang) + "\n"

    text += "\n"

    # Quality
    text += f"🏷 {format_quality_label(market.market_quality, lang)}\n"

    # Score breakdown
    bd = market.score_breakdown
    if bd:
        text += f"\n{get_text('detail.score_breakdown', lang)}\n"
        score_keys = [
            ("tilt", "detail.score_tilt", 40),
            ("volume", "detail.score_volume", 25),
            ("sm_ratio", "detail.score_sm_ratio", 15),
            ("liquidity", "detail.score_liquidity", 10),
            ("recency", "detail.score_recency", 10),
        ]
        for key, text_key, mx in score_keys:
            text += get_text(text_key, lang, v=bd.get(key, 0), max=mx) + "\n"

    text += f"\n{'─' * 28}\n"
    text += get_text("detail.signal", lang, emoji=sig, score=market.signal_score) + "\n\n"

    # Recommendation
    if rec.should_bet:
        text += get_text("detail.rec_bet", lang, side=rec.side, price=format_price(rec.entry_price)) + "\n"
        if rec.entry_price > 0:
            tgt_pct = ((rec.target_price / rec.entry_price) - 1) * 100
            stop_pct = (1 - (rec.stop_loss_price / rec.entry_price)) * 100
        else:
            tgt_pct = stop_pct = 0
        text += get_text("detail.rec_target", lang,
                         target=format_price(rec.target_price), pct=f"{tgt_pct:.0f}",
                         stop=format_price(rec.stop_loss_price), spct=f"{stop_pct:.0f}") + "\n"
        text += get_text("detail.rec_rr", lang, rr=f"{rec.risk_reward_ratio:.1f}") + "\n"
    else:
        text += get_text("detail.rec_no_bet", lang, side=rec.side) + "\n"

    # Reasons & warnings
    if rec.reasons:
        text += "\n"
        for r in rec.reasons:
            text += f"  {r}\n"
    if rec.warnings:
        text += "\n"
        for w in rec.warnings:
            text += f"  {w}\n"

    return text


def format_market_links_footer(markets: List[MarketStats], start_idx: int, lang: str) -> str:
    text = "\n🔗 <b>Links:</b>\n"
    for i, m in enumerate(markets[:5]):
        idx = start_idx + i
        text += f"  {idx}. <a href='{m.market_url}'>{html.escape(m.question[:40])}</a>\n"
    return text


def format_unified_analysis(market: MarketStats, deep_result: Any, lang: str) -> str:
    """
    Dispatcher:
    - If Deep Analysis is available: returns strictly formatted "Quant Analyst" report.
    - If not: returns "Simple Fact-Based" report.
    """
    if deep_result:
        return _format_quant_analysis(market, deep_result, lang)
    else:
        return _format_simple_analysis(market, lang)


def _format_quant_analysis(market: MarketStats, deep: Any, lang: str) -> str:
    """
    Strict Quant Analyst Template (Corrected and Robust).
    """
    try:
        # --- 1. UNIFIED PROBABILITY & EDGE CALCULATION ---
        # Consensus model probability (0.0-1.0)
        p_model = deep.model_probability
        
        # SURY PROTIBUG: Fix 300% probability if upstream sends percentage
        if p_model > 1.0:
            p_model = p_model / 100.0
        p_model = max(0.0, min(1.0, p_model))
        
        p_market = market.yes_price
        
        # Edge (Model - Market)
        edge_abs = p_model - p_market
        edge_pp = edge_abs * 100.0  # Percentage points (e.g. +1.5 or -2.0)
        
        # --- 2. RECOMMENDATION LOGIC ---
        # Rule: Edge >= 2.0 pp AND Kelly > 0 -> CONSIDER
        # Else -> SKIP
        
        kelly_fraction_safe = 0.0
        fraction_name = "0"
        if deep.kelly:
            # Use the conservative/safe fraction recommended by the system
            kelly_fraction_safe = deep.kelly.kelly_final_pct 
            if kelly_fraction_safe is None: kelly_fraction_safe = 0.0
            fraction_name = deep.kelly.fraction_name
            
        # Strict Thresholds
        is_positive_setup = (edge_pp >= 2.0) and (kelly_fraction_safe > 0.0)
        
        # Determine Direction
        rec_side = "YES" if edge_abs > 0 else "NO"
        
        # Localization Keys
        if is_positive_setup:
            short_intro_key = "deep.shortly"
            conclusion_key = "deep.final_word"
        else:
            rec_side = "N/A" # Not relevant for skip
            short_intro_key = "deep.shortly_skip"
            conclusion_key = "deep.final_word_skip"

        # --- 3. CONSTRUCT TEXT ---
        
        # HEADER
        # ESCAPE HTML CHARACTERS IN QUESTION (Critical fix for Telegram)
        safe_q = html.escape(market.question)
        text = f"🔎 {get_text('unified.analysis_title', lang)}\n{safe_q}\n\n"
        
        # SUMMARY (Briefly)
        # Using the same edge logic as below
        text += f"{get_text(short_intro_key, lang, side=rec_side)}\n\n"
        
        # PRICES & LIQUIDITY
        text += f"💰 <b>{get_text('deep.prices_vol', lang)}</b>\n"
        text += f"• YES: {int(market.yes_price*100)}¢  NO: {int(market.no_price*100)}¢\n"
        # Calculate Gap/spread
        gap = abs(market.yes_price - market.no_price) * 100
        # text += f"• Gap: {gap:.0f}¢\n" # Optional
        text += f"• {get_text('unified.liq', lang)}: {format_volume(market.liquidity)}\n\n"
        
        # WHALE FLOW (Brief)
        wa = market.whale_analysis
        text += f"🐋 <b>{get_text('deep.flow', lang)}</b>\n"
        if wa and wa.is_significant:
            text += f"• Tilt: {int(wa.dominance_pct)}% {wa.dominance_side}\n"
            text += f"• Top: {format_volume(wa.top_trade_size)} → {wa.top_trade_side}\n"
        else:
            text += f"• {get_text('detail.no_whale_activity', lang)}\n"
        text += "\n"

        # PROBABILITIES & EDGE (The Critical Block)
        text += f"{get_text('deep.probs', lang)}\n"
        text += f"• {get_text('deep.prob_market', lang, pct=f'{p_market*100:.1f}')}\n"
        
        # MODEL PROBABILITY (Fixed format)
        text += f"• {get_text('deep.prob_model', lang, pct=f'{p_model*100:.1f}')}\n"
        
        # EDGE (Fixed format)
        edge_sign = "+" if edge_pp > 0 else ""
        roi = (edge_abs / p_market) * 100 if p_market > 0 else 0.0
        emoji = "🟢" if edge_pp > 0 else "🔴"
        
        # Use deep.edge_line but we need to ensure formatting matches
        # deep.edge_line: "• Edge: {emoji} <b>{diff} п.п.</b> (ROI {roi}%)"
        edge_str = f"{edge_sign}{edge_pp:.1f}"
        text += f"{get_text('deep.edge_line', lang, emoji=emoji, diff=edge_str, roi=f'{roi:.1f}')}\n\n"

        # SIZING
        text += f"{get_text('deep.sizing_title', lang)}\n"
        if is_positive_setup:
            text += f"{get_text('deep.edge_expl', lang, m_pct=f'{p_market*100:.1f}', my_pct=f'{p_model*100:.1f}', diff=f'{edge_pp:.1f}')}\n"
            text += f"{get_text('deep.cons_stake', lang, pct=f'{kelly_fraction_safe:.1f}', fract=fraction_name)}\n"
        else:
            # FIX: Escape < to &lt; to prevent HTML parsing error in 'Edge < 2%'
            text += "• Edge &lt; 2% або Kelly = 0 → <b>SKIP</b>\n"
        text += "\n"

        # SCENARIOS (Monte Carlo)
        mc = deep.monte_carlo
        if mc:
            text += f"{get_text('deep.risk_scenarios', lang)}\n"
            # Try to format percentiles if available (Crypto mode)
            if mc.mode == "crypto":
                p5 = mc.percentile_5 if hasattr(mc, 'percentile_5') else 0
                p95 = mc.percentile_95 if hasattr(mc, 'percentile_95') else 0
                val_p5 = f"${p5:,.2f}" if p5 >= 1000 else f"${p5:.2f}"
                val_p95 = f"${p95:,.2f}" if p95 >= 1000 else f"${p95:.2f}"
                text += f"• P5: {val_p5}\n• P95: {val_p95}\n"
            text += f"{get_text('deep.win_prob', lang, pct=f'{mc.probability_yes*100:.1f}')}\n\n"
        
        # CONCLUSION
        text += f"{get_text('deep.conclusion', lang)}\n"
        if is_positive_setup:
            text += get_text(conclusion_key, lang, side=rec_side, pct=f"{kelly_fraction_safe:.1f}")
        else:
            text += get_text(conclusion_key, lang, edge=f"{edge_pp:.1f}")

        return text

    except Exception as e:
        logger.error(f"Quant Format Error: {e}", exc_info=True)
        return f"⚠️ <b>Analysis Display Error</b>: {e}"


def _format_simple_analysis(market: MarketStats, lang: str) -> str:
    """
    Simplified Fact-Based Format (Fallback).
    """
    try:
        # Prices
        yes_price = market.yes_price
        no_price = market.no_price
        market_prob = int(yes_price * 100)
        
        # Smart Money / Whales
        wa = market.whale_analysis
        whale_str = "—"
        last_whale_str = "—"
        whale_side = "NEUTRAL"
        whale_pct = 50
        
        if wa and wa.is_significant:
            whale_side = wa.dominance_side
            whale_pct = int(wa.dominance_pct)
            whale_str = f"{whale_pct}% {get_text('unified.in', lang)} {whale_side}"
            
            # Last whale trade
            if wa.top_trade_size > 0:
                ago = f"{int(wa.hours_since_last_trade*60)}m" if wa.hours_since_last_trade < 1 else f"{int(wa.hours_since_last_trade)}h"
                last_whale_str = f"{format_volume(wa.top_trade_size)} → {wa.top_trade_side} ({ago} ago)"
        
        rec_side = market.recommended_side
        
        # HEADER
        safe_q = market.question.replace("{", "(").replace("}", ")")
        text = f"🔎 {get_text('unified.analysis_title', lang)} <b>{safe_q}</b>\n\n"
        
        # SHORT SUMMARY (Fact-based)
        summary_key = "unified.summary_neutral"
        if rec_side == "YES":
            summary_key = "unified.summary_buy_yes"
        elif rec_side == "NO":
            summary_key = "unified.summary_buy_no"
            
        text += f"{get_text('unified.briefly', lang)}: {get_text(summary_key, lang, side=whale_side, pct=whale_pct)}\n"
        
        text += "────────────────────────────\n"
        
        # MONEY & PRICES
        text += f"💰 <b>{get_text('unified.prices_vol', lang)}</b>\n"
        text += f"• YES: {int(yes_price*100)}¢ NO: {int(no_price*100)}¢\n"
        text += f"• {get_text('unified.vol', lang)}: {format_volume(market.volume_24h)} | {get_text('unified.liq', lang)}: {format_volume(market.liquidity)}\n\n"
        
        # WHALE FLOW
        text += f"🐋 <b>{get_text('unified.flow', lang)}</b>\n"
        text += f"• Smart money: {whale_str}\n"
        text += f"• {get_text('unified.last_whale', lang)}: {last_whale_str}\n\n"
        
        # Conclusion
        text += f"🏁 <b>{get_text('unified.conclusion_title', lang)}</b>\n"
        if rec_side != "NEUTRAL":
             text += f"Можливий вхід в {rec_side} (див. деталі в Deep Analysis)."
        else:
             text += get_text("unified.concl_final_wait", lang)
             
        return text
    except Exception as e:
        logger.error(f"Simple Format Error: {e}", exc_info=True)
        return f"⚠️ <b>Analysis Error</b>: {e}"
