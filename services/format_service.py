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
    Consumer-Friendly Deep Analysis (3-Level Structure).
    Level 1: Instant Signal
    Level 2: Simple Explanation
    Level 3: Technical Details
    """
    try:
        # --- 1. METRICS & LOGIC (UNCHANGED) ---
        p_model = deep.model_probability
        # Fix 300% bug
        if p_model > 1.0: p_model = p_model / 100.0
        p_model = max(0.0, min(1.0, p_model))
        
        p_market = market.yes_price
        edge_raw = p_model - p_market
        edge_pp = edge_raw * 100.0
        
        # Kelly data
        k_safe = 0.0
        fraction_name = "0"
        
        if deep.kelly:
            k_safe = deep.kelly.kelly_final_pct or 0.0
            fraction_name = deep.kelly.fraction_name

        rec_side = "YES" if edge_raw > 0 else "NO"
        is_positive_setup = (abs(edge_pp) >= 2.0) and (k_safe > 0.0)
        
        pp_unit = get_text("quant.pp", lang)
        
        # --- 2. CONFIDENCE SCORE CALCULATION ---
        # Formula: Base (max 50) + Whale (25) + Liq (15) + Certainty (10)
        
        score_base = min(50, abs(edge_pp) * 10)
        
        score_whale = 0
        wa = market.whale_analysis
        whale_agrees = False
        if wa and wa.is_significant:
            if wa.dominance_side == rec_side:
                score_whale = 25
                whale_agrees = True
            elif wa.dominance_side != "NEUTRAL":
                # Whale disagrees
                pass

        score_liq = 0
        if market.liquidity >= 50000: score_liq = 15
        elif market.liquidity >= 10000: score_liq = 10
        elif market.liquidity >= 2000: score_liq = 5
        
        score_cert = 0
        # If model is far from 50/50
        if p_model >= 0.60 or p_model <= 0.40:
            score_cert = 10
            
        # Cap confidence at 95
        conf_score = int(min(95, score_base + score_whale + score_liq + score_cert))
        
        # Calculate Potential ROI (if wins)
        # ROI = (Payout - Stake) / Stake = (1 - Price) / Price
        roi_win = 0.0
        entry_price = market.yes_price if rec_side == "YES" else market.no_price
        if entry_price > 0:
            roi_win = ((1.0 / entry_price) - 1.0) * 100
        
        # --- 3. LEVEL 1: INSTANT SIGNAL ---
        # 🟢 BUY YES @ X¢  or  🛑 SKIP
        # Confidence: X/100 · Edge: ±X% · Size: $X
        
        l1_text = ""
        if is_positive_setup:
            price_display = int(market.yes_price * 100) if rec_side == "YES" else int(market.no_price * 100)
            l1_text += f"{get_text('l1.signal_buy', lang, side=rec_side, price=price_display)}\n"
            
            # Size calc
            size_str = f"{k_safe:.1f}%"
            l1_text += f"{get_text('l1.stats', lang, score=conf_score, edge=f'{edge_pp:+.1f}', size=size_str, roi=f'{roi_win:.0f}')}\n"
        else:
            l1_text += f"{get_text('l1.signal_skip', lang)}\n"
            l1_text += f"{get_text('l1.stats_skip', lang, score=conf_score, edge=f'{edge_pp:+.1f}')}\n"
            
        l1_text += "\n"

        # --- 4. LEVEL 2: SIMPLE EXPLANATION ---
        # 💬 WHY:
        # • [Whale]
        # • [Model]
        # • [Risk]
        # ⚡ ACTION: ...
        
        l2_text = f"{get_text('l2.why', lang)}\n"
        reasons = []
        
        # Reason 1: Whales (Detailed)
        if wa and wa.is_significant:
            wa_vol = wa.yes_volume if rec_side == "YES" else wa.no_volume
            # If whale disagrees, show counter-volume
            if not whale_agrees and wa.dominance_side != "NEUTRAL":
                 wa_vol = wa.yes_volume if wa.dominance_side == "YES" else wa.no_volume
                 
            wa_amt_str = format_volume(wa_vol)
            wa_pct_str = f"{wa.dominance_pct:.0f}"
            
            if whale_agrees:
                reasons.append(get_text('l2.reason_whale_good', lang, side=rec_side, pct=wa_pct_str, amt=wa_amt_str))
            else:
                reasons.append(get_text('l2.reason_whale_bad', lang, side=wa.dominance_side, pct=wa_pct_str, amt=wa_amt_str))
        else:
             reasons.append(get_text('l2.reason_whale_none', lang))
             
        # Reason 2: Model
        # "Model sees X% vs Market Y%"
        reasons.append(get_text('l2.reason_model_view', lang, model=f"{p_model*100:.0f}", market=f"{p_market*100:.0f}"))
        
        # Reason 3: Risk/Factor
        if market.liquidity < 2000:
            reasons.append(get_text('l2.risk_liq', lang))
        elif market.days_to_close > 30:
            reasons.append(get_text('l2.risk_time', lang))
        elif not is_positive_setup:
             reasons.append(get_text('l2.risk_low_edge', lang))
        else:
             reasons.append(get_text('l2.factor_good', lang))
             
        for r in reasons:
            l2_text += f"• {r}\n"
            
        # ACTION
        action_val = ""
        if is_positive_setup:
             action_val = get_text('l2.act_buy', lang, pct=f"{k_safe:.1f}")
        else:
             action_val = get_text('l2.act_wait', lang)
             
        l2_text += f"\n{get_text('l2.action_label', lang, action=action_val)}\n"
        
        # Separator (Standard Dash)
        l2_text += "────────────────────────────\n"

        # --- 5. LEVEL 3: TECHNICAL DETAILS (ALL MODELS) ---
        # 📊 MODELS & DATA
        l3_text = f"{get_text('l3.header', lang)}\n\n"
        
        # MC
        mc = deep.monte_carlo
        if mc:
            mc_runs = 10000 
            mc_pnl = mc.edge if mc.edge else 0.0
            
            # Hide PnL if it's strangely 0.00 despite edge, or too small
            mc_detail = f"{mc_runs} {get_text('l3.runs', lang)}"
            if abs(mc_pnl) >= 0.005:
                mc_detail += f", PnL: {mc_pnl:+.2f}"
            
            l3_text += f"🎲 <b>{get_text('l3.mc_label', lang)}:</b> {mc.probability_yes*100:.1f}% YES\n"
            l3_text += f"   <i>({mc_detail})</i>\n"
            
        # Bayesian
        bayes = deep.bayesian
        if bayes:
            # Neutral as fallback
            try:
                sig_str = get_text('l3.signal_neutral', lang)
            except:
                sig_str = "Neutral"
            
            if bayes.has_signal:
                strength = "strong" if abs(bayes.posterior - bayes.prior) > 0.05 else "weak"
                sig_str = get_text(f'l3.signal_{strength}', lang)

            prior_disp = market.yes_price
            
            l3_text += f"🧠 <b>{get_text('l3.bayes_label', lang)}:</b> {prior_disp*100:.0f}% → {bayes.posterior*100:.1f}%\n"
            l3_text += f"   <i>({get_text('l3.signal_label', lang)}: {sig_str})</i>\n"
            
        # Kelly
        if deep.kelly:
            rec_str = "Rec"
            try: rec_str = get_text('l3.rec', lang)
            except: pass
            
            l3_text += f"💰 <b>Kelly:</b> Full {deep.kelly.kelly_full*100:.1f}%, Time {deep.kelly.kelly_time_adj_pct:.1f}%\n" 
            # Note: Hardcoded Kelly label to match previous code style or we can try localize it too
            # Let's keep it safe. "Kelly" is international.
            
            try:
                l3_text = l3_text.replace("Kelly", get_text('l3.kelly_label', lang))
            except: pass

            l3_text += f"   <i>({rec_str}: {k_safe:.1f}%)</i>\n"
            
        # Theta - Hide if days < 1
        if deep.greeks and deep.greeks.theta and market.days_to_close >= 1:
             th = deep.greeks.theta.theta_yes if rec_side == "YES" else deep.greeks.theta.theta_no
             
             theta_label = "Theta"
             day_label = "day"
             try: theta_label = get_text('l3.theta_label', lang)
             except: pass
             try: day_label = get_text('l3.day', lang)
             except: pass

             l3_text += f"⏳ <b>{theta_label}:</b> {th:+.2f}¢/{day_label}\n"
             
        l3_text += "\n"
        
        # Whale Flow
        if wa:
            w_label = "Whale Flow"
            t_label = "Tilt"
            try: w_label = get_text('l3.whale_label', lang)
            except: pass
            try: t_label = get_text('l3.tilt_label', lang)
            except: pass
            
            l3_text += f"🐋 <b>{w_label}:</b> ${format_volume(wa.yes_volume)} YES / ${format_volume(wa.no_volume)} NO\n"
            l3_text += f"   <i>({t_label}: {wa.dominance_side} {wa.dominance_pct:.0f}%)</i>\n"
            
        # Liquidity & Time
        liq_lbl = get_text("liquidity.high" if market.liquidity > 25000 else "liquidity.low" if market.liquidity < 2000 else "liquidity.med", lang)
        l3_text += f"💧 <b>{get_text('l3.liq_label', lang)}:</b> ${format_volume(market.liquidity)} ({liq_lbl})\n"
        if market.days_to_close > 0:
            time_val = f"{market.days_to_close}{get_text('l3.days_short', lang)}"
            suffix = f" {get_text('l3.to_res', lang)}"
        else:
            time_val = f"&lt;1{get_text('l3.days_short', lang)}"
            suffix = f" ({get_text('l3.expires_today', lang)}) ⚠️"
            
        l3_text += f"⏱️ <b>{get_text('l3.time_label', lang)}:</b> {time_val}{suffix}\n"

        # Combine
        return l1_text + l2_text + l3_text

    except Exception as e:
        logger.error(f"Quant Format Error: {e}", exc_info=True)
        return f"⚠️ <b>Analysis Info Error</b>: {e}"


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
