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
    Strict Quant Analyst Template as requested by user.
    """
    try:
        # --- PREPARE METRICS ---
        
        # 1. Market & Setup
        safe_q = market.question.replace("{", "(").replace("}", ")")
        yes_price = market.yes_price
        no_price = market.no_price
        
        # 2. Monte Carlo
        mc = deep.monte_carlo
        mc_runs = mc.num_simulations if mc else 10000
        mc_prob_up = int(mc.probability_yes * 100) if mc else 0
        mc_expected_pnl = f"{mc.edge:+.2f}" if mc else "дані відсутні"
        
        # 3. Bayesian
        bayes = deep.bayesian
        bayes_prior = int(market.yes_price * 100) # Prior is usually market
        bayes_posterior = int(bayes.posterior * 100) if bayes else int(market.yes_price * 100)
        
        bayes_comment = "кити не змінили картину"
        if bayes and bayes.has_signal:
            if bayes.posterior > market.yes_price + 0.05:
                bayes_comment = "кити суттєво підсилюють YES"
            elif bayes.posterior < market.yes_price - 0.05:
                bayes_comment = "кити тиснуть на NO, послаблюють YES"
            else:
                bayes_comment = "активність китів підтверджує ринок"
        elif not bayes:
             bayes_comment = "дані відсутні"

        # 4. Edge
        edge_raw = deep.edge
        edge_pct = int(edge_raw * 100)
        edge_sign = "+" if edge_pct > 0 else ""
        
        # 5. Kelly
        if deep.kelly:
            k_full = deep.kelly.kelly_full
            k_safe = deep.kelly.kelly_fraction # This is already reduced by fraction (e.g. 0.25)
        else:
            k_full = 0.0
            k_safe = 0.0

        kelly_fraction = int(k_full * 100)
        kelly_fraction_safe = int(k_safe * 100)
        
        # 6. Theta
        theta_val = deep.greeks.theta if deep.greeks else 0.0
        theta_daily = f"{theta_val:+.1f}¢" if deep.greeks else "дані відсутні"
        theta_comment = "ви платите за час (theta-)" if theta_val < 0 else "час грає на вас (theta+)"
        
        # 7. Internals
        wa = market.whale_analysis
        tilt_str = f"{int(wa.dominance_pct)}% {wa.dominance_side}" if wa and wa.is_significant else "нейтрально"
        
        vol_mom = "стабільно"
        if market.score_breakdown.get('volume', 0) > 15:
            vol_mom = "зростання активності"
        elif market.score_breakdown.get('volume', 0) < 5:
             vol_mom = "спад активності"
             
        # Liquidity score interpretation
        liq_score = market.score_breakdown.get('liquidity', 0)
        if liq_score >= 8:
            liq_desc = f"висока (${format_volume(market.liquidity)})"
        elif liq_score >= 4:
            liq_desc = f"середня (${format_volume(market.liquidity)})"
        else:
            liq_desc = f"низька (${format_volume(market.liquidity)})"
            
        recency = "давно"
        if wa and wa.hours_since_last_trade < 1:
            recency = f"активно ({int(wa.hours_since_last_trade*60)}m ago)"
        elif wa:
            recency = f"помірно ({int(wa.hours_since_last_trade)}h ago)"

        # --- SETUP SUMMARY ---
        setup = "нейтральний"
        if edge_pct > 3 and kelly_fraction_safe > 0:
            setup = "bullish (є edge)"
        elif edge_pct < -3:
            setup = "bearish (YES переоцінений)"
            
        intro = f"Сетап {setup}, edge {edge_sign}{edge_pct} п.п."
        if kelly_fraction_safe == 0:
            intro += ", позиція не рекомендується."
        else:
            intro += ", можна розглянути вхід."

        # --- BUILD TEXT ---
        text = f"🔎 АНАЛІЗ\n{safe_q}\n\n"
        text += f"Коротко: {intro}\n\n"
        
        text += "────────────────────────────\n"
        
        text += "🎲 Monte Carlo\n"
        text += f"- Кількість симуляцій: {mc_runs}\n"
        text += f"- Ймовірність плюсового результату: {mc_prob_up}%\n"
        text += f"- Середній очікуваний PnL: {mc_expected_pnl}\n\n"
        
        text += "🧠 Bayesian\n"
        text += f"- Початкова ймовірність (prior): {bayes_prior}%\n"
        text += f"- Оновлена ймовірність (posterior): {bayes_posterior}%\n"
        text += f"- Коментар: {bayes_comment}.\n\n"
        
        text += "📐 Edge\n"
        text += f"- Edge: {edge_sign}{edge_pct} п.п.\n"
        if edge_pct <= 0:
            text += "- Математично ставка НЕвигідна (edge ≤ 0).\n"
        else:
             text += "- Математична перевага присутня.\n"
        text += "\n"
        
        text += "💰 Kelly Criterion\n"
        text += f"- Оптимальна частка (Kelly): {kelly_fraction}%\n"
        if kelly_fraction <= 0:
            text += "- Рекомендована ставка: 0% (пропустити).\n"
        else:
            text += f"- Рекомендована консервативна ставка: {kelly_fraction_safe}% від банкролу.\n"
        text += "\n"
        
        text += "⏳ Theta\n"
        text += f"- Орієнтовний \"time edge\": {theta_daily} на день.\n"
        text += f"- Коротко: {theta_comment}.\n\n"

        text += f"├ 🐋 Smart Money Tilt: {tilt_str}\n"
        text += f"├ 📈 Volume Momentum: {vol_mom}\n"
        text += f"├ 💡 Smart/Retail Ratio: {market.score_breakdown.get('sm_ratio', 0)}/15\n"
        text += f"├ 💧 Liquidity: {liq_desc}\n"
        text += f"└ ⏱️ Activity Recency: {recency}\n\n"
        
        text += "🏁 ВИСНОВОК\n"
        if kelly_fraction_safe > 0 and edge_pct > 2:
             text += f"Маємо підтверджений edge {edge_pct}%. Рекомендуємо вхід на {kelly_fraction_safe}% банкролу (консервативно). "
        else:
             text += "На даний момент чіткого edge немає або ризики зависокі. Краще утриматись (HOLD). "
        
        # Risks
        risks = []
        if market.liquidity < 50000: risks.append("низька ліквідність")
        if wa and wa.dominance_pct > 70 and wa.dominance_side != deep.recommended_side: risks.append("smart money проти вас")
        if market.days_to_close > 60: risks.append("довгий лок капіталу")
        
        if risks:
            text += f"\n⚠️ Ризики: {', '.join(risks)}."
            
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

