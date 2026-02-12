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
    MarketStats, BetRecommendation, SignalStrength, MarketQuality, WhaleAnalysis,
)
from analytics.orchestrator import DeepAnalysisResult


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


def format_holders_block(holders: Any, lang: str) -> str:
    """Format holders analysis block."""
    if not holders:
        return ""
        
    # NEW: Hide entire block if no holders data - DISABLED per user request
    # if holders.yes_stats.count == 0 and holders.no_stats.count == 0:
    #     return ""
    
    # Format Yes line
    yes = holders.yes_stats
    if yes.count == 0:
        line_yes = get_text("holders.line_empty", lang, side="YES")
    else:
        smart_pct_yes = (yes.smart_count_5k / yes.count * 100) if yes.count > 0 else 0.0
        line_yes = get_text("holders.line", lang, side="YES", 
            count=yes.count, 
            median=f"{yes.median_pnl:+.0f}",
            count_5k=yes.smart_count_5k, # Using Smart (Lifetime PnL > 3k)
            pct=f"{smart_pct_yes:.1f}"
        )
    
    # Format No line
    no = holders.no_stats
    if no.count == 0:
        line_no = get_text("holders.line_empty", lang, side="NO")
    else:
        smart_pct_no = (no.smart_count_5k / no.count * 100) if no.count > 0 else 0.0
        line_no = get_text("holders.line", lang, side="NO", 
            count=no.count, 
            median=f"{no.median_pnl:+.0f}",
            count_10k=no.smart_count_5k, # Using Smart > 3k for consistency
            count_5k=no.smart_count_5k,  # Param definition might vary in locale keys
            pct=f"{smart_pct_no:.1f}"
        )
    
    # Smart Score
    smart = get_text("holders.smart_score", lang, 
        side=holders.smart_score_side,
        score=holders.smart_score
    )
    
    # Smart Score Breakdown (NEW)
    hs_bd = holders.smart_score_breakdown
    if hs_bd:
         holders_pts = int(hs_bd.get('holders', 0))
         whales_pts = int(hs_bd.get('tilt', 0))
         model_pts = int(hs_bd.get('model', 0))
         
         breakdown_line = get_text("holders.smart_score_breakdown", lang,
             holders=holders_pts, whales=whales_pts, model=model_pts
         )
         smart += f"\n{breakdown_line}"

    # Top Holder
    top_side = holders.yes_stats.side
    max_prof = holders.yes_stats.top_holder_profit
    
    # Determine which top holder to show
    if holders.no_stats.top_holder_profit > max_prof:
        top_side = holders.no_stats.side
        max_prof = holders.no_stats.top_holder_profit
    
    # Only show top holder if we actually have one (or profit != 0)
    top_line = ""
    # Check if we have valid top holder address
    holder_addr = holders.yes_stats.top_holder_address if top_side == "YES" else holders.no_stats.top_holder_address
    
    if max_prof != 0 and holder_addr:
        # Get stats for the winning top holder
        stats = holders.yes_stats if top_side == "YES" else holders.no_stats
        addr = stats.top_holder_address
        wins = stats.top_holder_wins
        losses = stats.top_holder_losses
        
        addr_short = addr[:5] if addr else "???"
        
        # Win rate logic
        winrate_str = ""
        if wins + losses > 0:
             total = wins + losses
             wr = (wins / total) * 100
             # Note: get_text calls should match placeholders exactly
             top_line = get_text("holders.top_holder_with_winrate", lang,
                 side=top_side,
                 profit=f"{int(max_prof):+}",
                 winrate=f"{wr:.0f}",
                 wins=wins,
                 losses=losses,
                 addr=addr_short
             )
        else:
             top_line = get_text("holders.top_holder", lang,
                 side=top_side,
                 profit=f"{int(max_prof):+}",
                 addr=addr_short
             )
    
    title = get_text("holders.title", lang)
    
    # Comparison Block (NEW)
    comparison = format_comparison(holders.yes_stats, holders.no_stats, lang)
    
    return f"{title}\n{line_yes}\n{line_no}\n\n{smart}\n{top_line}\n{comparison}".strip()


def format_comparison(yes_stats: Any, no_stats: Any, lang: str) -> str:
    """Format YES vs NO comparison table."""
    try:
        title = get_text("holders.comparison_title", lang)
        
        # Helper for checkmark
        def get_check(y, n):
            if n > y: return "✅"
            if y > n: return "✅ (YES)"
            return ""

        # Median Lifetime PnL
        yes_med = yes_stats.median_pnl
        no_med = no_stats.median_pnl
        
        med_line = get_text("holders.comparison_med", lang,
            yes_med=f"{yes_med:.0f}",
            no_med=f"{no_med:.0f}",
            check=get_check(yes_med, no_med)
        )
        
        # Smart Count >$3K (Lifetime Profit)
        yes_smart = yes_stats.smart_count_5k
        no_smart = no_stats.smart_count_5k
        count_line = get_text("holders.comparison_count", lang,
            yes_count=str(yes_smart),
            no_count=str(no_smart),
            check=get_check(yes_smart, no_smart)
        )
        
        # Profitable % (Lifetime)
        yes_pct = yes_stats.profitable_pct
        no_pct = no_stats.profitable_pct
        prof_line = get_text("holders.comparison_prof", lang,
            yes_pct=f"{yes_pct:.0f}",
            no_pct=f"{no_pct:.0f}",
            check=get_check(yes_pct, no_pct)
        )
        
        # Construct table
        return f"\n{title}\n{med_line}\n{count_line}\n{prof_line}"
        
    except Exception as e:
        logger.error(f"Format Comparison Error: {e}")
        return ""


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
    HARDCODED ENGLISH VERSION
    """
    try:
        # --- 1. METRICS & LOGIC ---
        p_model = deep.model_probability
        if p_model > 1.0: p_model /= 100.0
        p_model = max(0.0, min(1.0, p_model))

        p_market = market.yes_price

        # Guardrail: if model ≈ market (< 2 p.p.) → force SKIP
        model_confirms_market = abs(p_model - p_market) < 0.02
        if model_confirms_market:
            p_model = p_market 

        # Kelly data
        k_safe = 0.0
        if deep.kelly:
            k_safe = deep.kelly.kelly_final_pct or 0.0

        # Edge logic
        edge_yes = (p_model - p_market) * 100
        edge_pp = deep.edge * 100 if deep.edge else 0.0
        rec_side = deep.recommended_side or "NEUTRAL"

        # Confidence Score
        conf_score = deep.confidence if deep.confidence else 50
        
        # Dynamic Sizing based on Confidence
        if conf_score < 30:
            k_safe *= 0.3
        elif conf_score < 50:
            k_safe *= 0.6
        k_safe = round(k_safe, 1)

        is_positive_setup = (rec_side in ("YES", "NO")) and (abs(edge_pp) >= 2.0) and (k_safe >= 1.0)
        
        # SM Conflict Check for is_positive_setup
        holders = getattr(deep, "holders", None)
        if holders and holders.smart_score >= 80 and holders.smart_score_side not in ("NEUTRAL", rec_side):
            is_positive_setup = False

        if k_safe < 1.0:
            is_positive_setup = False
            k_safe = 0.0
            
        # Cap recommended size
        if k_safe > 6.0: k_safe = 6.0

        # --- HEADER ---
        q_title = html.escape(market.question)
        text = f"<b>{q_title}</b>\n\n"
        text += f"💰 YES {int(market.yes_price*100)}¢ · NO {int(market.no_price*100)}¢ · Vol 24h: {format_volume(market.volume_24h)}\n"
        text += "────────────────────────────\n"

        # --- LEVEL 1: ACTION ---
        if is_positive_setup:
            price_display = int(market.yes_price * 100) if rec_side == "YES" else int(market.no_price * 100)
            if conf_score >= 50:
                text += f"🚀 <b>BET {rec_side} @ {price_display}¢</b>\n"
            else:
                text += f"🟡 <b>Lean {rec_side} @ {price_display}¢</b> (small size)\n"
            
            text += f"Confidence: {conf_score}/100 · Edge: +{abs(edge_pp):.1f}%\n"
        else:
            text += "🛑 <b>SKIP / WAIT</b>\n"
            text += f"Confidence: {conf_score}/100 · Edge: ~0%\n"
            
        text += "\n"

        # --- LEVEL 2: WHY ---
        text += "💬 <b>WHY:</b>\n"
        text += format_why_section(deep, "en") # Hardcoded EN
        text += "\n\n"

        # --- ACTION LINE ---
        act_text = ""
        if is_positive_setup:
            act_text = f"⚡️ <b>ACTION:</b> Bet {rec_side} (Kelly {k_safe}%)"
        else:
            act_text = "⚡️ <b>ACTION:</b> Skip or wait for better price (Kelly 0%)"
        text += f"{act_text}\n"
        text += "────────────────────────────\n"

        # --- LEVEL 3: DETAILED ---
        text += "📊 <b>DETAILED ANALYSIS</b>\n\n"

        # Monte Carlo
        mc = deep.monte_carlo
        if mc:
            mc_prob = mc.probability_yes * 100
            text += f"🎲 Monte Carlo: {mc_prob:.1f}% YES (10000 sims)\n"
        
        # Bayesian
        bayes = deep.bayesian
        if bayes:
            b_prior = market.yes_price * 100
            b_post = bayes.posterior * 100
            
            if abs(b_post - b_prior) < 2.0:
                 bayes_msg = f"confirms market ({b_prior:.0f}% → {b_post:.0f}%)"
            else:
                 dir_str = "Bullish" if b_post > b_prior else "Bearish"
                 bayes_msg = f"{dir_str} ({b_prior:.0f}% → {b_post:.0f}%)"
                 
            text += f"🧠 Bayesian: {bayes_msg}\n"

        # Kelly detail
        if deep.kelly:
            k_full = deep.kelly.kelly_full * 100
            if abs(edge_pp) < 1.0:
                 text += f"💰 Kelly: 0% (no edge)\n"
            else:
                 text += f"💰 Kelly: {k_safe}% (Full {k_full:.1f}%, Time Adj)\n"

        text += "\n"

        # Whale Flow
        wa = market.whale_analysis
        if wa:
            text += "🐋 <b>Whale Flow (24h):</b>\n"
            
            # Helper for whale line
            def _w_line(side, vol, count, max_sz, is_dom):
                pct = (vol / wa.total_volume * 100) if wa.total_volume > 0 else 0
                dom_mark = "🔥 " if is_dom and vol > 1000 else "   "
                return f"{dom_mark}{side}: {format_volume(vol)} ({pct:.0f}% vol) | max: {format_volume(max_sz)}"

            w_yes = _w_line("YES", wa.yes_volume, wa.yes_count, wa.biggest_yes_size, wa.dominance_side == "YES")
            w_no = _w_line("NO", wa.no_volume, wa.no_count, wa.biggest_no_size, wa.dominance_side == "NO")
            
            text += f"{w_yes}\n{w_no}\n"
            if wa.last_trade_timestamp > 0:
                 ago = int((time.time() - wa.last_trade_timestamp)/3600)
                 ago_str = f"{ago}h ago" if ago > 0 else "<1h ago"
                 text += f"   (Last active: {ago_str})\n"
            text += "\n"

        # Holders
        if holders:
            text += "👥 <b>Smart Money Holders:</b>\n"
            
            # Function to format holder line
            def _h_line(stats):
                if stats.count == 0:
                    return "   N/A (no data or <3 holders)"
                
                # Format: "26 holders (6 smart, med PnL -$569)"
                return f"   {stats.count} holders ({stats.smart_count_5k} smart, med PnL ${stats.median_pnl:+.0f})"
            
            text += f"YES: {_h_line(holders.yes_stats)}\n"
            text += f"NO:  {_h_line(holders.no_stats)}\n"
            
            h_score_side = holders.smart_score_side
            text += f"   🎯 Smart Score: {h_score_side} {holders.smart_score}/100\n"
            
            # Score breakdown
            bd = holders.smart_score_breakdown
            if bd:
                text += f"   └ Holders: {int(bd.get('holders',0))}pts | Whales: {int(bd.get('tilt',0))}pts | Model: {int(bd.get('model',0))}pts\n"
            
            # Top Holder
            # Find best
            top_s = holders.yes_stats if holders.yes_stats.top_holder_profit > holders.no_stats.top_holder_profit else holders.no_stats
            if top_s.top_holder_profit != 0:
                 text += f"   🔥 Top holder ({top_s.side}): ${format_volume(top_s.top_holder_profit)} lifetime PnL\n"
            
            text += "\n"

        # Footer
        liq_lbl = "HIGH" if market.liquidity > 50000 else "LOW"
        closes = f"<1d" if market.days_to_close == 0 else f"{market.days_to_close}d"
        text += f"💧 Liq: {format_volume(market.liquidity)} ({liq_lbl}) | ⏱️ Closes: {closes}\n"

        return text

    except Exception as e:
        logger.error(f"Quant Format Error: {e}", exc_info=True)
        return f"⚠️ <b>Analysis Info Error</b>: {e}"


def format_why_section(deep: Any, lang: str) -> str:
    """
    WHY section: max 3 bullets, English only.
    """
    rec = deep.recommended_side
    edge = deep.edge
    conf = deep.confidence
    holders = getattr(deep, "holders", None)
    market = deep.market
    
    bullets = []
    
    # 1. NEUTRAL (SKIP)
    if rec == "NEUTRAL":
        if abs(edge) < 0.02:
            bullets.append(f"• Model confirms market ({deep.model_probability*100:.0f}% ≈ {deep.market_price*100:.0f}%, no edge)")
            
            if holders and holders.smart_score >= 70:
                bullets.append(f"• Smart Money ({holders.smart_score_side} {holders.smart_score}/100) also agrees with price")
            
            bullets.append("• No value for entry — wait for better price")
        else:
            bullets.append(f"• Edge {edge*100:+.1f}%, but confidence {conf}/100 (too low)")
            
            if holders and holders.smart_score >= 80 and holders.smart_score_side != rec:
                bullets.append(f"• Smart Money ({holders.smart_score_side} {holders.smart_score}/100) strictly against")
            
            bullets.append("• Risk exceeds potential profit")
    
    # 2. YES/NO — Positive Setup
    else:
        bullets.append(f"• Edge {edge*100:+.1f}% on {rec} (model {deep.model_probability*100:.0f}% vs market {deep.market_price*100:.0f}%)")
        
        # SM alignment
        if holders:
            if holders.smart_score_side == rec:
                bullets.append(f"• Smart Money supports {rec} ({holders.smart_score}/100) ✅")
            elif holders.smart_score >= 60:
                bullets.append(f"• ⚠️ Smart Money on {holders.smart_score_side} ({holders.smart_score}/100), but edge is sufficient")
        
        # Liquidity/Time context
        if market.liquidity >= 100000:
            bullets.append(f"• High liquidity (${market.liquidity/1000:.0f}K) — low slippage")
        elif market.days_to_close == 0:
            bullets.append("• Closes today — fast resolution")
    
    return "\n".join(bullets)


def _format_simple_analysis(market: MarketStats, lang: str) -> str:
    """
    Simplified Fact-Based Format (Fallback).
    """
    try:
        # Prices
        yes_price = market.yes_price
        no_price = market.no_price
        
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
             text += f"Possible entry {rec_side} (see Deep Analysis)."
        else:
             text += get_text("unified.concl_final_wait", lang)
             
        return text
    except Exception as e:
        logger.error(f"Simple Format Error: {e}", exc_info=True)
        return f"⚠️ <b>Analysis Error</b>: {e}"


# --- New Formatting Functions for Hot & Signals ---

def format_hot_line(idx: int, m: MarketStats, lang: str) -> str:
    """Format single line for Hot Today list with edge/Kelly/SM conflict."""
    # Title (truncate if too long)
    title = html.escape(m.question[:55]) + ("..." if len(m.question) > 55 else "")
    
    # Prices & volume
    yes_p = format_price(m.yes_price)
    no_p = format_price(m.no_price)
    vol = format_volume(m.volume_24h)
    
    # Whale tilt
    wa = m.whale_analysis
    if wa and wa.is_significant:
        whale_side = wa.dominance_side
        whale_pct = int(wa.dominance_pct)
        whale_str = f"🐋 {whale_side} {whale_pct}%"
    else:
        whale_str = "🐋 —"
    
    # Timing
    if m.days_to_close == 0:
        time_str = "<1d"
    else:
        time_str = f"{m.days_to_close}d"
    
    # Edge & Kelly
    edge_val = getattr(m, "edge", 0.0)
    rec_side = getattr(m, "rec_side", "NEUTRAL")
    kelly_pct = getattr(m, "kelly_pct", 0.0)
    
    if abs(edge_val) >= 0.02:
        edge_str = f"📈 Edge: {edge_val*100:+.1f}% → {rec_side}"
        size_str = f"💼 {kelly_pct:.1f}%"
    else:
        edge_str = get_text("hot.edge_zero", lang)
        size_str = get_text("hot.skip", lang)
    
    # Smart Money conflict marker
    sm_icon = ""
    if hasattr(m, "holders") and m.holders:
        smart_side = m.holders.smart_score_side
        if smart_side not in ("NEUTRAL", rec_side) and m.holders.smart_score >= 60:
            sm_icon = "  SM ⚠️"
        elif rec_side != "NEUTRAL" and abs(edge_val) >= 0.02:
            sm_icon = "  SM ✅"
    
    # Score emoji
    score = m.signal_score
    if score >= 90:
        emoji = "🟢🟢"
    elif score >= 70:
        emoji = "🟢"
    elif score >= 50:
        emoji = "🟡"
    else:
        emoji = "🔴"
    
    final_rec = rec_side if rec_side != "NEUTRAL" else "—"
    
    # Add HOT Score if available
    hot_tag = ""
    if getattr(m, "hot_score", 0) > 0:
        hot_tag = f" ⚡{int(m.hot_score)}"

    return (
        f"{idx}. {title}\n"
        f"   💰 YES {yes_p} · NO {no_p}  📊 {vol}\n"
        f"   {whale_str}  ⏰ {time_str}{hot_tag}\n"
        f"   {edge_str}   {size_str}{sm_icon}\n"
        f"   {emoji} {score}/100 → {final_rec}\n"
    )


def format_hot_markets(markets: List[MarketStats], category_name: str, lang: str) -> str:
    """Format full Hot Today message with header & footer."""
    if not markets:
        return get_text("hot.no_markets", lang)
    
    # Header
    text = f"🔥 <b>Hot {category_name}</b>\n\n"
    text += f"{get_text('hot.desc', lang)}\n\n"
    
    # List markets
    for idx, m in enumerate(markets[:10], start=1):
        text += format_hot_line(idx, m, lang)
        text += "\n"
    
    # Footer: Total risk
    total_kelly = sum(getattr(m, "kelly_pct", 0.0) for m in markets[:10])
    text += f"\n💡 {get_text('hot.total_risk', lang, risk=f'{total_kelly:.1f}')}\n"
    text += f"{get_text('hot.advice', lang)}\n"
    
    return text.strip()


def format_signal_card(m: MarketStats, lang: str) -> str:
    """Compact signal card for quick opportunities."""
    title = html.escape(m.question[:60]) + ("..." if len(m.question) > 60 else "")
    
    # Prices
    yes_p = format_price(m.yes_price)
    no_p = format_price(m.no_price)
    
    # Edge & side
    edge_val = getattr(m, "effective_edge", getattr(m, "edge", 0.0))
    rec_side = getattr(m, "rec_side", "NEUTRAL")
    kelly_pct = getattr(m, "kelly_pct", 0.0)
    
    # Emoji for recommendation
    if rec_side == "YES":
        action_emoji = "🟢"
    elif rec_side == "NO":
        action_emoji = "🔴"
    else:
        action_emoji = "⚪"
    
    # Build card
    text = f"{action_emoji} <b>{title}</b>\n"
    text += f"   💰 YES {yes_p} · NO {no_p}\n"
    text += f"   📈 Edge: {edge_val*100:+.1f}% → <b>{rec_side}</b>\n"
    text += f"   💼 Size: {kelly_pct:.1f}%\n"
    
    if m.days_to_close == 0:
        text += "   ⏰ Closes today\n"
    else:
        text += f"   ⏰ {m.days_to_close}d left\n"
    
    return text


def format_deep_analysis_result(result: DeepAnalysisResult, lang: str) -> str:
    """
    Format deep analysis result with proper conflict handling.
    FIXED: Uses 50 confidence threshold and blocks BUY on SM conflict.
    """
    m = result.market
    title = html.escape(m.question[:60]) + ("..." if len(m.question) > 60 else "")
    
    # Determine header based on setup strength
    if result.is_positive_setup:
        if result.confidence >= 70:
            header_emoji = "🟢"
            header_text = f"BUY {result.rec_side}"
        else:
            header_emoji = "🟡"
            header_text = f"Lean {result.rec_side}"
    else:
        header_emoji = "🛑"
        header_text = "SKIP"
    
    # Price display
    if result.rec_side == "YES":
        price_display = format_price(m.yes_price)
    elif result.rec_side == "NO":
        price_display = format_price(m.no_price)
    else:
        # Average
        price_display = format_price((m.yes_price + m.no_price) / 2)
    
    # Build output
    text = f"{header_emoji} <b>{header_text} @ {price_display}</b>\n"
    text += f"<b>{title}</b>\n\n"
    
    # WHY section
    text += "<b>WHY:</b>\n"
    # Using float to match expectations
    edge_val = float(m.edge)
    eff_edge_val = float(m.effective_edge)
    text += f"• Edge: {edge_val*100:+.1f}% (after fees: {eff_edge_val*100:+.1f}%)\n"
    text += f"• Confidence: {result.confidence}/100\n"
    
    # Smart Money indicator
    if m.holders and m.holders.smart_score > 0:
        sm_side = m.holders.smart_score_side
        sm_score = m.holders.smart_score
        
        if sm_side == result.rec_side:
            text += f"• {get_text('l2.reason_holders_align', lang, side=sm_side, score=sm_score)}\n"
        else:
            text += f"• {get_text('l2.reason_holders_conflict', lang, side=sm_side, score=sm_score)}\n"
    
    # Conflicts warning
    if result.conflicts:
        text += "\n<b>⚠️ CONFLICTS:</b>\n"
        for c in result.conflicts:
            if c["type"] == "SMART_MONEY":
                text += f"• Strong Smart Money on {c['side']} ({c['score']}/100)\n"
    
    # Size recommendation
    text += f"\n<b>SIZE:</b> {result.kelly_pct:.1f}% of bankroll\n"
    
    if result.confidence < 50 and result.confidence >= 30:
        text += "💡 Reduced size due to lower confidence\n"
    elif result.confidence < 30:
        text += "💡 Very small size — high uncertainty\n"
    
    # Risk warning for NO positions
    if result.rec_side == "NO" and result.is_positive_setup:
        text += "\n⚠️ <b>NO positions:</b> Limited upside, ensure edge is strong\n"
    
    return text


def format_signals_list(markets: List[MarketStats], lang: str) -> str:
    """Format list of signal opportunities."""
    if not markets:
        return "🔍 No strong signals found right now.\n\nMarkets are fairly priced or lack liquidity."
    
    text = "⚡ <b>Quick Signals</b>\n\n"
    text += "High-confidence opportunities (next 3 days):\n\n"
    
    for idx, m in enumerate(markets[:5], start=1):
        text += f"{idx}. {format_signal_card(m, lang)}\n"
    
    text += "\n<i>Signals update every 15 minutes. Act quickly — edges fade.</i>"
    return text


def format_brief_signal(result: DeepAnalysisResult) -> str:
    """Brief format for signal list."""
    m = result.market
    title = html.escape(m.question[:45]) + ("..." if len(m.question) > 45 else "")
    
    emoji = "🟢" if result.confidence >= 70 else "🟡"
    conf = result.confidence
    
    return (
        f"{emoji} <b>{result.rec_side}</b> | {title}\n"
        f"   Edge: {m.effective_edge*100:+.1f}% | Conf: {conf}/100 | Size: {result.kelly_pct:.1f}%"
    )
