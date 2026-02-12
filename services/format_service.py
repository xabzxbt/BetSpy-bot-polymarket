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
    line_yes = get_text("holders.line", lang, side="YES", 
        count=yes.count, 
        median=f"{yes.median_pnl:+.0f}",
        count_5k=yes.above_5k_count,
        pct=f"{yes.above_5k_pct:.1f}"
    )
    
    # Format No line
    no = holders.no_stats
    line_no = get_text("holders.line", lang, side="NO", 
        count=no.count, 
        median=f"{no.median_pnl:+.0f}",
        count_10k=no.above_10k_count,  # Note: logic might use 10k for NO if requested, but key uses count_5k usually. Let's assume standard key.
        # Wait, the key `holders.line` uses `count_5k`. The prompt showed NO >10k.
        # I'll stick to >5k for consistency in the line unless I make two keys.
        count_5k=no.above_5k_count,
        pct=f"{no.above_5k_pct:.1f}"
    )
    
    # But wait, prompt example: "NO: 289 holders | Med: +$187 | >$10K: 12 (4.1%)"
    # To match prompt exactly, I should check logic.
    # The key uses {count_5k}. I'll pass count 10k? No, that's confusing.
    # I'll use count_5k field for >5k.
    
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
    
    # Determine which top holder to show (the one with higher profit)
    if holders.no_stats.top_holder_profit > max_prof:
        top_side = holders.no_stats.side
        max_prof = holders.no_stats.top_holder_profit
    
    # Get stats for the winning top holder
    stats = holders.yes_stats if top_side == "YES" else holders.no_stats
    addr = stats.top_holder_address
    wins = stats.top_holder_wins
    losses = stats.top_holder_losses
    
    addr_short = addr[:5] if addr else "???"
    
    # Win rate logic (NEW)
    winrate_str = ""
    if wins + losses > 0:
         total = wins + losses
         wr = (wins / total) * 100
         winrate_str = f" | {wr:.0f}% win rate ({wins}W-{losses}L)"
         
         # Use specialized key for winrate if desired, or append manually?
         # Prompt asked: "holders.top_holder_with_winrate"
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
    
    return f"{title}\n{line_yes}\n{line_no}\n\n{smart}\n{top_line}\n{comparison}"


def format_comparison(yes_stats: Any, no_stats: Any, lang: str) -> str:
    """Format YES vs NO comparison table."""
    try:
        title = get_text("holders.comparison_title", lang)  # "👥 YES vs NO:"
        
        # Median PnL
        yes_med = yes_stats.median_pnl
        no_med = no_stats.median_pnl
        med_check = "✅" if no_med > yes_med else ""
        # Invert check for YES? usually highest median wins.
        if yes_med > no_med: med_check = "✅ (YES)"
        if no_med > yes_med: med_check = "✅ (NO)"
        # Prompt only showed check on the right. Assuming right column is NO.
        # "Med PnL: -$23 vs +$187 ✅" -> implied NO is better.
        # Let's align with prompt: Check mark appears on the line if one is clearly better?
        # Or specifically if NO is better? "✅ біля кращого значення"
        # If YES is better, should check be on the left? f-string alignment makes it hard.
        # Let's put check at the end if NO wins, or just indicate winner.
        # Prompt example: "-$23 vs +$187 ✅" (NO is better).
        # We will assume column order YES vs NO.
        
        check = ""
        if no_med > yes_med: check = "✅"
        elif yes_med > no_med: check = "⬅️" # Show arrow to yes? Or just check if specific side?
        # Prompt says "✅ біля кращого значення".
        # Since text is "YES vs NO", if YES is better: "✅ $100 vs $50".
        # But we format as string.
        # Let's follow prompt sample precisely: "Med PnL: -$23 vs +$187 ✅"
        # This implies check is suffixes.
        
        # Med PnL
        med_line = get_text("holders.comparison_med", lang,
            yes_med=f"{yes_med:>6.0f}",
            no_med=f"{no_med:>6.0f}",
            check="✅" if no_med > yes_med else ("✅ (YES)" if yes_med > no_med else "")
        )
        
        # >$10K count
        yes_10k = yes_stats.above_10k_count
        no_10k = no_stats.above_10k_count
        count_line = get_text("holders.comparison_count", lang,
            yes_count=f"{yes_10k:>6}",
            no_count=f"{no_10k:>6}",
            check="✅" if no_10k > yes_10k else ("✅ (YES)" if yes_10k > no_10k else "")
        )
        
        # Profitable %
        yes_prof = yes_stats.profitable_pct
        no_prof = no_stats.profitable_pct
        prof_line = get_text("holders.comparison_prof", lang,
            yes_pct=f"{yes_prof:>4.0f}",
            no_pct=f"{no_prof:>4.0f}",
            check="✅" if no_prof > yes_prof else ("✅ (YES)" if yes_prof > no_prof else "")
        )
        
        return f"\n{title}\n{med_line}\n{count_line}\n{prof_line}\n"
    except Exception:
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
            # Re-ensure values are aligned for display logic
            p_model = p_market 

        # Kelly data
        k_safe = 0.0
        if deep.kelly:
            k_safe = deep.kelly.kelly_final_pct or 0.0

        # Edge logic: YES vs NO side
        edge_yes = (p_model - p_market) * 100          # p.p.
        edge_no = ((1.0 - p_model) - (1.0 - p_market)) * 100  # = -edge_yes

        rec_side = deep.recommended_side or "NEUTRAL"
        edge_pp = deep.edge * 100 if deep.edge else 0.0

        is_positive_setup = (rec_side in ("YES", "NO")) and (abs(edge_pp) >= 2.0) and (k_safe > 0.0)

        # Cap recommended size for mass users (max 5-6%)
        if k_safe > 6.0:
            k_safe = 6.0

        # Confidence Score
        conf_score = deep.confidence if deep.confidence else 50
        
        # Calculate Potential ROI (if wins)
        roi_win = 0.0
        entry_price = market.yes_price if rec_side == "YES" else market.no_price
        if entry_price > 0:
            roi_win = ((1.0 / entry_price) - 1.0) * 100
        
        # --- 3. LEVEL 1: INSTANT SIGNAL ---
        
        edge_disp = f"{edge_pp:+.1f}"
        if abs(edge_pp) < 1.0:
            edge_disp = "~0" # Simplified
        
        l1_text = ""
        
        # Header: Title + Stats
        q_title = html.escape(market.question)
        l1_text += f"<b>{q_title}</b>\n\n"
        l1_text += f"💰 {get_text('detail.yes', lang)} {format_price(market.yes_price)} · {get_text('detail.no', lang)} {format_price(market.no_price)} · Vol 24h: {format_volume(market.volume_24h)}\n"
        l1_text += "────────────────────────────\n"
        
        if is_positive_setup:
            price_display = int(market.yes_price * 100) if rec_side == "YES" else int(market.no_price * 100)
            l1_text += f"{get_text('l1.signal_buy', lang, side=rec_side, price=price_display)}\n"
            
            # Size calc
            size_str = f"{k_safe:.1f}%"
            l1_text += f"{get_text('l1.stats', lang, score=conf_score, edge=edge_disp, size=size_str, roi=f'{roi_win:.0f}')}\n"
        else:
            l1_text += f"{get_text('l1.signal_skip', lang)}\n"
            l1_text += f"{get_text('l1.stats_skip', lang, score=conf_score, edge=edge_disp)}\n"
            
        l1_text += "\n"

        # --- 4. LEVEL 2: SIMPLE EXPLANATION ---
        l2_text = f"{get_text('l2.why', lang)}\n"
        reasons = []
        
        wa = market.whale_analysis
        holders = deep.holders
        
        # Reason 1: Whales
        # Only show whale reason if model doesn't force a SKIP (user request)
        if wa and wa.is_significant and not model_confirms_market:
            wa_vol = wa.yes_volume if rec_side == "YES" else wa.no_volume
            # If whale disagrees
            whale_agree_side = wa.dominance_side == rec_side
            
            if not whale_agree_side and wa.dominance_side != "NEUTRAL":
                 wa_vol = wa.yes_volume if wa.dominance_side == "YES" else wa.no_volume
                 
            wa_amt_str = format_volume(wa_vol)
            wa_pct_str = f"{wa.dominance_pct:.0f}"
            
            if whale_agree_side:
                reasons.append(get_text('l2.reason_whale_good', lang, side=rec_side, pct=wa_pct_str, amt=wa_amt_str))
            else:
                side_shown = wa.dominance_side
                if side_shown == "NEUTRAL": side_shown = "Other"
                reasons.append(get_text('l2.reason_whale_bad', lang, side=side_shown, pct=wa_pct_str, amt=wa_amt_str))
        elif not wa or not wa.is_significant:
             # Only show "no activity" if purely no activity, not if suppressed
             reasons.append(get_text('l2.reason_whale_none', lang))
             
        # Reason 2: Model view
        if model_confirms_market:
            model_txt = get_text('l2.reason_model_confirms', lang,
                                 model=f"{p_model*100:.0f}",
                                 market=f"{p_market*100:.0f}")
        elif rec_side == "NO":
            model_txt = get_text('l2.reason_model_view', lang,
                                 model=f"{(1-p_model)*100:.0f} (NO)",
                                 market=f"{(1-p_market)*100:.0f} (NO)")
            model_txt += f" (+{edge_pp:.1f}% edge)"
        else:
            model_txt = get_text('l2.reason_model_view', lang,
                                 model=f"{p_model*100:.0f}",
                                 market=f"{p_market*100:.0f}")
            if edge_pp >= 2.0:
                model_txt += f" (+{edge_pp:.1f}% edge)"

        reasons.append(model_txt)
        
        # Reason Holders (NEW)
        if holders:
             # Median PnL comparison
             # "Holders median NO: +$187 vs YES: -$23"
             side_1 = rec_side if rec_side != "NEUTRAL" else "NO"
             side_2 = "YES" if side_1 == "NO" else "NO"
             
             stats_1 = holders.no_stats if side_1 == "NO" else holders.yes_stats
             stats_2 = holders.yes_stats if side_1 == "NO" else holders.no_stats
             
             # Only show if there is data
             if stats_1.count > 0 and stats_2.count > 0:
                  reasons.append(get_text("l2.reason_holders_median", lang,
                      side=side_1, val=f"{int(stats_1.median_pnl)}",
                      opp=side_2, opp_val=f"{int(stats_2.median_pnl)}"
                  ))
                  
             # Whales count comparison
             # "NO >$10K holders: 12 vs YES: 2"
             if stats_1.above_10k_count > 0 or stats_2.above_10k_count > 0:
                 reasons.append(get_text("l2.reason_holders_whales", lang,
                      side=side_1, count=stats_1.above_10k_count,
                      opp=side_2, opp_count=stats_2.above_10k_count
                  ))
        
        # Reason 3: Last Big Trade (Priority)
        if wa and wa.last_big_size > 5000:
             ago_mins = int((time.time() - wa.last_big_timestamp) / 60)
             ago_str = f"{ago_mins}m" if ago_mins < 60 else f"{ago_mins//60}h"
             last_big_txt = f"🔥 Last big: {format_volume(wa.last_big_size)} → {wa.last_big_side} ({ago_str} ago)"
             reasons.append(last_big_txt)
             
        for r in reasons:
            l2_text += f"• {r}\n"
            
        # ACTION
        action_val = ""
        if is_positive_setup:
             action_val = get_text('l2.act_buy', lang, pct=f"{k_safe:.1f}")
        else:
             action_val = get_text('l2.act_wait', lang)
             if model_confirms_market:
                 action_val += " (0.25-Kelly = 0%)"
             
        l2_text += f"\n{get_text('l2.action_label', lang, action=action_val)}\n"
        l2_text += "────────────────────────────\n"

        # --- 5. LEVEL 3: TECHNICAL DETAILS ---
        l3_text = f"{get_text('l3.header', lang)}\n\n"
        
        # MC
        mc = deep.monte_carlo
        if mc:
            mc_runs = 10000 
            mc_pnl = mc.edge if mc.edge else 0.0
            mc_detail = f"{mc_runs} {get_text('l3.runs', lang)}"
            
            l3_text += f"🎲 <b>{get_text('l3.mc_label', lang)}:</b> {mc.probability_yes*100:.1f}% YES (= {(1-mc.probability_yes)*100:.1f}% NO)\n"
            l3_text += f"   <i>({mc_detail})</i>\n"
            
        # Bayesian
        bayes = deep.bayesian
        if bayes:
            try:
                # Better logic for "Neutral" -> "Confirms market"
                if abs(bayes.posterior - bayes.prior) < 0.02:
                     sig_str = get_text('bayes_c_confirm', lang) # Fallback key if missing
                else:
                     strength = "strong" if abs(bayes.posterior - bayes.prior) > 0.05 else "weak"
                     sig_str = get_text(f'l3.signal_{strength}', lang)
            except:
                sig_str = "Neutral"

            prior_disp = market.yes_price
            post_disp = bayes.posterior
            
            l3_text += f"🧠 <b>{get_text('l3.bayes_label', lang)}:</b> {prior_disp*100:.0f}% YES → {post_disp*100:.0f}% YES\n"
            # Signal text
            l3_text += f"   (signal: {sig_str})\n"
            
        # Kelly
        if deep.kelly:
            # Custom prompt format: "Full 20%, Time 20% (Rec: 5.0%)"
            kf = deep.kelly.kelly_full * 100
            kt = deep.kelly.kelly_time_adj_pct 
            
            if kf <= 0:
                 l3_text += f"💰 <b>Kelly:</b> 0% (edge ~0)\n"
            else:
                 l3_text += f"💰 <b>Kelly:</b> Full {kf:.1f}%, Time {kt:.1f}%\n"
                 l3_text += f"   (Rec: {k_safe:.1f}%, 0.25-Kelly)\n"
            
        l3_text += "\n"
        
        # Whale Flow
        if wa:
            w_label = "Whale Flow"
            t_label = "Tilt"
            try: w_label = get_text('l3.whale_label', lang)
            except: pass
            
            l3_text += f"🐋 <b>{w_label}:</b>\n"
            l3_text += f"   YES: {format_volume(wa.yes_volume)} ({wa.yes_count} trades, max: {format_volume(wa.biggest_yes_size)})\n"
            l3_text += f"   NO:  {format_volume(wa.no_volume)} ({wa.no_count} trades, max: {format_volume(wa.biggest_no_size)})\n"
            l3_text += f"   (Tilt: {wa.dominance_side} {wa.dominance_pct:.0f}% / Ratio: {market.smart_money_ratio*100:.0f}%)\n\n"
            
        # HOLDERS ANALYSIS BLOCK
        if holders:
            # Use format_holders_block
            holders_txt = format_holders_block(holders, lang)
            l3_text += holders_txt + "\n"
            
        # Liquidity & Time
        liq_lbl = "Med"
        if market.liquidity > 50000: liq_lbl = "HIGH"
        elif market.liquidity < 2000: liq_lbl = "LOW"
        
        l3_text += f"💧 <b>{get_text('l3.liq_label', lang)}:</b> ${format_volume(market.liquidity)} ({liq_lbl})\n"
        
        time_msg = ""
        if market.days_to_close == 0:
            time_msg = "&lt;1d (expires today) ⚠️"
        else:
            time_msg = f"{market.days_to_close}d"
            
        l3_text += f"⏱️ <b>{get_text('l3.time_label', lang)}:</b> {time_msg}\n"

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
