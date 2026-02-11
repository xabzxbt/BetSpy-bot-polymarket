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
    Unified Human-Readable Analysis Format.
    Replaces format_market_detail and Deep Analysis view.
    Generates a coherent analyst report.
    """
    try:
        # --- 1. PREPARE DATA ---
        is_deep = deep_result is not None
        
        # Prices
        yes_price = market.yes_price
        no_price = market.no_price
        market_prob = yes_price * 100
        
        # Signal / Score / Recommendations
        if is_deep:
            model_prob = deep_result.model_probability * 100
            edge = deep_result.edge * 100
            kelly_pct = (deep_result.kelly.fraction * 100) if deep_result.kelly else 0
            rec_side = deep_result.recommended_side
        else:
            # Fallback heuristics
            model_prob = market.signal_score # Rough proxy
            edge = model_prob - market_prob
            kelly_pct = 0
            rec_side = market.recommended_side

        # Liquidity Level
        liq = market.liquidity
        if liq < 50_000:
            liq_key = "unified.liq_low"
        elif liq < 250_000:
            liq_key = "unified.liq_med"
        else:
            liq_key = "unified.liq_high"
            
        liq_text = get_text(liq_key, lang)
        
        # Whale Sentiment
        wa = market.whale_analysis
        if wa and wa.is_significant:
            whales_pct = int(wa.dominance_pct)
            if wa.dominance_side == "YES":
                whales_key = "unified.whales_strong_yes"
            elif wa.dominance_side == "NO":
                whales_key = "unified.whales_strong_no"
            else:
                whales_key = "unified.whales_mixed"
        else:
            whales_key = "unified.whales_mixed"
            whales_pct = 50

        whales_text = get_text(whales_key, lang)
        
        # --- 2. BUILD TEXT ---
        
        # HEADER (Safe escaping)
        safe_q = market.question.replace("{", "(").replace("}", ")")
        text = get_text("unified.header", lang, question=safe_q) + "\n\n"
        
        # SHORT SUMMARY
        # Determine template based on rec_side and strength
        if rec_side == "YES":
            if edge > 10 or market.signal_score > 70:
                sum_key = "unified.short_yes_strong"
            else:
                sum_key = "unified.short_yes_mod"
            rec_key = "unified.rec_buy"
        elif rec_side == "NO":
            if edge < -10 or market.signal_score < 30: # Edge is negative for YES means NO is good? 
                # If Deep Analysis returns edge for NO, it might be positive for NO side.
                # Usually edge is calculated for the recommended side.
                # Assuming edge is favorable for rec_side.
                sum_key = "unified.short_no_strong"
            else:
                sum_key = "unified.short_no_mod"
            rec_key = "unified.rec_buy" # "Buy NO"
        else:
            sum_key = "unified.short_neutral"
            rec_key = "unified.rec_wait"
        
        # Recommendation text
        text += get_text(sum_key, lang) + "\n"
        if rec_side in ["YES", "NO"]:
            text += get_text(rec_key, lang, side=rec_side) + "\n"
        else:
            text += get_text(rec_key, lang) + "\n"
            
        text += "────────────────────────────\n"
        
        # PRICES
        text += get_text("unified.section_prices", lang) + "\n"
        text += get_text("unified.prices_line", lang, yes=format_price(yes_price), no=format_price(no_price)) + "\n"
        text += get_text("unified.liquidity_line", lang, liq_text=liq_text, vol=format_volume(market.volume_24h)) + "\n\n"
        
        # WHALES
        text += get_text("unified.section_whales", lang) + "\n"
        text += get_text("unified.whales_sentiment", lang, sentiment=whales_text, pct=whales_pct) + "\n"
        if wa and wa.top_trade_size > 0:
            text += get_text("unified.whales_last_trade", lang, amount=format_volume(wa.top_trade_size), side=wa.top_trade_side, time=f"{int(wa.hours_since_last_trade*60)}m ago") + "\n"
        text += "\n"
        
        # PROBABILITIES
        text += get_text("unified.section_probs", lang) + "\n"
        text += get_text("unified.prob_est", lang, prob=f"{int(model_prob)}") + "\n"
        
        diff = model_prob - market_prob
        if diff > 5:
            text += get_text("unified.prob_cmp_higher", lang, market=f"{int(market_prob)}") + "\n"
        elif diff < -5:
            text += get_text("unified.prob_cmp_lower", lang, market=f"{int(market_prob)}") + "\n"
        else:
            text += get_text("unified.prob_cmp_equal", lang, market=f"{int(market_prob)}") + "\n"
        text += "\n"
        
        # EDGE
        text += get_text("unified.section_edge", lang) + "\n"
        if abs(edge) > 2:
            text += get_text("unified.edge_mismatch", lang, market=f"{int(market_prob)}", model=f"{int(model_prob)}", edge=f"{abs(edge):.1f}") + "\n"
            if kelly_pct > 0:
                text += get_text("unified.kelly_safe", lang, pct=f"{int(kelly_pct)}") + "\n"
            else:
                text += get_text("unified.kelly_zero", lang) + "\n"
        else:
            text += get_text("unified.edge_none", lang) + "\n"
        text += "\n"
        
        # RISKS
        text += get_text("unified.section_risks", lang) + "\n"
        risks_shown = 0
        if market.liquidity < 50_000:
            text += get_text("unified.risk_low_liq", lang) + "\n"
            risks_shown += 1
        if market.days_to_close <= 2:
            text += get_text("unified.risk_time", lang) + "\n"
            risks_shown += 1
        # Check Volatility if available (Deep)
        vol = 0
        if deep_result and deep_result.greeks:
             vol = deep_result.greeks.iv_24h * 100
        if vol > 80:
            text += get_text("unified.risk_volatility", lang) + "\n"
            risks_shown += 1
        
        # Check alignment mismatch
        if rec_side == "YES" and wa and wa.dominance_side == "NO" and wa.dominance_pct > 60:
             text += get_text("unified.risk_whale_opp", lang) + "\n"
             risks_shown += 1
        
        if risks_shown == 0:
            text += get_text("unified.risk_generic", lang) + "\n"
        text += "\n"
        
        # CONCLUSION
        text += get_text("unified.section_concl", lang) + "\n"
        if rec_side in ["YES", "NO"] and abs(edge) > 3 and kelly_pct > 0:
            max_alloc = min(kelly_pct, 15) # Cap at 15% for safety advice
            text += get_text("unified.concl_buy", lang, side=rec_side, pct=f"{int(max_alloc)}")
        elif abs(edge) < 3:
            text += get_text("unified.concl_wait", lang)
        else:
            text += get_text("unified.concl_avoid", lang)
            
        return text

    except Exception as e:
        logger.error(f"Format Unified Error: {e}", exc_info=True)
        return f"⚠️ <b>Analysis Display Error</b>: {e}"

