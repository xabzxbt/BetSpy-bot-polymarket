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
            median=f"{int(yes.median_pnl):+}",
            count_5k=yes.smart_count_5k, # Using Smart (Lifetime PnL > 3k)
            pct=f"{smart_pct_yes:.1f}"
        )
        # Show Novoregs if any
        if getattr(yes, "novoreg_count", 0) > 0:
            line_yes += f" (👶 {yes.novoreg_count})"
    
    # Format No line
    no = holders.no_stats
    if no.count == 0:
        line_no = get_text("holders.line_empty", lang, side="NO")
    else:
        smart_pct_no = (no.smart_count_5k / no.count * 100) if no.count > 0 else 0.0
        line_no = get_text("holders.line", lang, side="NO", 
            count=no.count, 
            median=f"{int(no.median_pnl):+}",
            count_10k=no.smart_count_5k, # Using Smart > 3k for consistency
            count_5k=no.smart_count_5k,  # Param definition might vary in locale keys
            pct=f"{smart_pct_no:.1f}"
        )
        # Show Novoregs if any
        if getattr(no, "novoreg_count", 0) > 0:
            line_no += f" (👶 {no.novoreg_count})"
    
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
        return _format_quant_analysis_v3(market, deep_result, lang)
    else:
        return _format_simple_analysis(market, lang)





def _format_quant_analysis_v3(market: MarketStats, deep: Any, lang: str) -> str:
    """
    Consumer-Friendly Deep Analysis (Strict Layout).
    Matches user's exact visual request:
    Header -> Signal -> Why -> Action -> (NO DETAILS)
    """
    try:
        # --- 0. PRE-CALC METRICS ---
        p_model = deep.model_probability
        if p_model > 1.0: p_model /= 100.0
        p_model = max(0.0, min(1.0, p_model))
        p_market = market.yes_price

        # Guardrail: Removed to allow small edges
        model_confirms_market = False 

        # Kelly
        k_safe = deep.kelly.kelly_final_pct if deep.kelly else 0.0
        
        # Edge
        edge_pp = deep.edge * 100 if deep.edge else 0.0
        rec_side = deep.recommended_side or "NEUTRAL"
        
        # Confidence
        conf_score = deep.confidence if deep.confidence else 50
        
        # Sizing Logic
        if conf_score < 30: k_safe *= 0.3
        elif conf_score < 50: k_safe *= 0.6
        k_safe = min(6.0, round(k_safe, 1))

        # Update threshold to 0.5% to match Kelly
        is_positive_setup = (rec_side in ("YES", "NO")) and (abs(edge_pp) >= 0.5) and (k_safe > 0.0)
        
        # Formatting Helpers
        edge_disp = f"{edge_pp:+.1f}%" if abs(edge_pp) >= 0.1 else "~0%"
        
        # ---------------------------
        # 1. HEADER
        # ---------------------------
        text = ""
        # Counter-Strike: Sinners vs fnatic (BO3)
        text += f"<b>{html.escape(market.question)}</b>\n\n"
        
        # 💰 YES 59¢ · NO 40¢ · Vol 24h: $113K
        text += f"💰 YES {format_price(market.yes_price)} · NO {format_price(market.no_price)} · Vol 24h: {format_volume(market.volume_24h)}\n"
        text += "────────────────────────────\n"



        # ---------------------------
        # 3. WHY (Bulleted)
        # ---------------------------
        why_lbl = "WHY"
        w_text = get_text("l2.why_label", lang)
        if "l2.why" not in w_text:
             why_lbl = w_text
             
        text += f"💬 {why_lbl}:\n"
        
        current_bullets = []
        
        # Bullet: Whales
        wa = market.whale_analysis
        if wa and wa.is_significant:
            current_bullets.append(f"Whale Flow: {wa.dominance_side} {wa.dominance_pct:.0f}% sum volume")
            
        # Bullet: Smart Money
        holders = getattr(deep, "holders", None)
        if holders:
            sm_score = holders.smart_score
            sm_side = holders.smart_score_side
            if sm_side != "NEUTRAL":
                current_bullets.append(f"Smart Money: {sm_side} Score {sm_score}/100")
        
        # Add bullets to text
        if current_bullets:
             for b in current_bullets:
                 text += f"• {b}\n"
        else:
             text += f"• {get_text('l2.reason_whale_none', lang)}\n"

        text += "\n"
        
        # ---------------------------
        # 4. ACTION (REMOVED)
        # ---------------------------
        
        # ---------------------------
        # 5. DETAILED (REMOVED)
        # ---------------------------
        
        # ---------------------------
        # 6. FOOTER
        # ---------------------------
        liq_lbl = "MED"
        if market.liquidity > 100000: liq_lbl = "HIGH"
        elif market.liquidity < 5000: liq_lbl = "LOW"
        c_time = f"{market.days_to_close}d" if market.days_to_close > 0 else "&lt;1d"
        
        text += f"💧 Liq: {format_volume(market.liquidity)} ({liq_lbl}) | ⏱️ Closes: {c_time}"

        return text

    except Exception as e:
        logger.error(f"Quant Format V3 Error: {e}", exc_info=True)
        return f"⚠️ <b>Analysis Info Error</b>: {e}"


def format_new_trade(
    wallet_name: str,
    wallet_address: str,
    market_title: str,
    outcome: str,
    side: str,
    size: float,
    price: float,
    usdc_size: float,
    market_slug: str,
    lang: str = "en",
    is_whale: bool = False,
    referral_code: str = "xabzxbt" # Default can be overridden, usually passed from config but here just to ensure links work
) -> str:
    """Format a new trade notification."""
    
    # Profile link with referral
    profile_link = f"https://polymarket.com/profile/{wallet_address}"
    if referral_code:
        profile_link += f"?via={referral_code}"
        
    # Market link with referral
    market_link = f"https://polymarket.com/event/{market_slug}"
    if referral_code:
        market_link += f"?via={referral_code}"
    
    # Side styling
    side_emoji = "🟢" if side.upper() == "BUY" else "🔴"
    side_text = get_text("trade.side_buy", lang) if side.upper() == "BUY" else get_text("trade.side_sell", lang)
    
    key = "new_trade" if is_whale else "new_trade_small"
    
    return get_text(
        key, lang,
        wallet_name=wallet_name,
        profile_link=profile_link,
        market_title=html.escape(market_title),
        side=f"{side_emoji} {side_text}", # "🟢 ПОКУПКА"
        outcome=outcome,
        size=size,
        price=price,
        usdc_size=usdc_size,
        market_link=market_link,
    )
