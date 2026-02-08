"""
Handlers for BetSpy Market Intelligence features (v2).

Refactored:
- format functions use lang parameter properly
- whale analysis block shows score breakdown
- market quality labels integrated
- stable keyboard buttons (always at bottom of latest message)
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from loguru import logger
import html
import math
import time
from typing import Any

from database import db
from repository import UserRepository
from translations import get_text
from market_intelligence import (
    market_intelligence,
    Category,
    TimeFrame,
    SignalStrength,
    MarketQuality,
    MarketStats,
    BetRecommendation,
)
from keyboards_intelligence import (
    get_trending_keyboard,
    get_category_keyboard,
    get_market_detail_keyboard,
    get_cached_market,
)


router = Router(name="intelligence")


# ==================== FORMATTERS ====================

def format_volume(volume: float) -> str:
    if volume >= 1_000_000:
        return f"${volume/1_000_000:.1f}M"
    elif volume >= 1_000:
        return f"${volume/1_000:.0f}K"
    else:
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
    """Human-readable market quality label."""
    labels = {
        MarketQuality.HIGH_CONVICTION: "💎 High Conviction",
        MarketQuality.MODERATE_SIGNAL: "📊 Moderate Signal",
        MarketQuality.NOISY: "🔇 Noisy",
        MarketQuality.LOW_LIQUIDITY: "⚠️ Low Liquidity",
        MarketQuality.AVOID: "❌ Avoid",
    }
    return labels.get(quality, "—")


def format_whale_analysis_block(wa: Any, lang: str) -> str:
    """Format the structured whale analysis block."""
    if not wa or not wa.is_significant:
        return ""

    text = f"🐋 <b>SMART MONEY</b> ({wa.duration_text})\n"

    # Sentiment headline
    if wa.dominance_side == "NEUTRAL":
        text += f"⚖️ {wa.sentiment}\n"
    else:
        text += f"💡 <b>{wa.sentiment}</b> ({wa.dominance_pct:.0f}%)\n"

    # Visual bar
    bar_len = 10
    yes_share = wa.yes_volume / wa.total_volume if wa.total_volume > 0 else 0.5
    filled = max(0, min(bar_len, int(yes_share * bar_len)))
    bar = "▓" * filled + "░" * (bar_len - filled)
    text += f"YES {bar} NO\n\n"

    # Key stats
    if wa.top_trade_size > 0:
        text += f"🏆 Top: <b>{format_volume(wa.top_trade_size)}</b> → {wa.top_trade_side}\n"

    if wa.last_trade_timestamp > 0:
        hours = wa.hours_since_last_trade
        if hours < 1:
            ts = f"{int(hours * 60)}m ago"
        elif hours < 24:
            ts = f"{int(hours)}h ago"
        else:
            ts = "1d+ ago"
        text += f"⏱ Last: {ts} → {wa.last_trade_side}\n"

    text += "\n"

    # Breakdown
    text += f"📈 <b>YES:</b> {format_volume(wa.yes_volume)} ({wa.yes_count} trades)\n"
    text += f"📉 <b>NO:</b> {format_volume(wa.no_volume)} ({wa.no_count} trades)\n"
    text += (
        f"💰 Total: <b>{format_volume(wa.total_volume)}</b>"
        f" ({wa.large_whale_share_pct:.0f}% whales $2K+)\n"
    )

    return text


def format_market_card(market: MarketStats, index: int, lang: str) -> str:
    """Compact card for list view."""
    sig = format_signal_emoji(market.signal_strength)
    wa = market.whale_analysis

    whale_str = "—"
    if wa and wa.is_significant:
        whale_str = f"{wa.dominance_side} {wa.dominance_pct:.0f}%"

    if market.days_to_close == 0:
        time_str = "⏰ Today"
    elif market.days_to_close == 1:
        time_str = "⏰ Tomorrow"
    else:
        time_str = f"📅 {market.days_to_close}d"

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
    """Detailed market analysis card."""
    sig = format_signal_emoji(market.signal_strength)
    q = html.escape(market.question)

    text = f"<b>{q}</b>\n{'─' * 28}\n\n"

    # Prices
    text += f"💰 YES: <b>{format_price(market.yes_price)}</b>  ·  NO: <b>{format_price(market.no_price)}</b>\n"
    text += f"📊 Vol 24h: {format_volume(market.volume_24h)}  ·  Total: {format_volume(market.volume_total)}\n"
    if market.liquidity > 0:
        text += f"💧 Liquidity: {format_volume(market.liquidity)}\n"

    # Time
    if market.days_to_close == 0:
        text += "⏰ Closes <b>today</b>\n"
    elif market.days_to_close == 1:
        text += "⏰ Closes <b>tomorrow</b>\n"
    else:
        text += f"⏰ {market.end_date.strftime('%d.%m.%Y')} ({market.days_to_close}d)\n"

    text += "\n"

    # Whale analysis
    wa_block = format_whale_analysis_block(market.whale_analysis, lang)
    if wa_block:
        text += wa_block
    else:
        text += "🐋 <b>SMART MONEY</b>\n"
        text += "<i>No significant whale activity (&lt;$1K)</i>\n"

    text += "\n"

    # Quality label
    ql = format_quality_label(market.market_quality, lang)
    text += f"🏷 {ql}\n"

    # Score breakdown
    bd = market.score_breakdown
    if bd:
        text += f"\n📐 <b>Score breakdown:</b>\n"
        labels = {
            "tilt": "Tilt",
            "volume": "Volume",
            "sm_ratio": "SM Ratio",
            "liquidity": "Liquidity",
            "recency": "Recency",
        }
        maxes = {"tilt": 40, "volume": 25, "sm_ratio": 15, "liquidity": 10, "recency": 10}
        for key, label in labels.items():
            val = bd.get(key, 0)
            mx = maxes.get(key, 0)
            text += f"  {label}: {val}/{mx}\n"

    text += f"\n{'─' * 28}\n"
    text += f"{sig} <b>Signal: {market.signal_score}/100</b>\n\n"

    # Recommendation
    if rec.should_bet:
        text += f"✅ <b>Rec: {rec.side} @ {format_price(rec.entry_price)}</b>\n"
        if rec.entry_price > 0:
            tgt_pct = ((rec.target_price / rec.entry_price) - 1) * 100
            stop_pct = (1 - (rec.stop_loss_price / rec.entry_price)) * 100
        else:
            tgt_pct = stop_pct = 0
        text += f"🎯 Target: {format_price(rec.target_price)} (+{tgt_pct:.0f}%)"
        text += f"  ·  🛑 Stop: {format_price(rec.stop_loss_price)} (-{stop_pct:.0f}%)\n"
        text += f"📊 R:R = {rec.risk_reward_ratio:.1f}x\n"
    else:
        text += "❌ <b>Do not bet</b>\n"

    # Reasons
    if rec.reasons:
        text += "\n"
        for r in rec.reasons:
            text += f"  {r}\n"
    if rec.warnings:
        text += "\n"
        for w in rec.warnings:
            text += f"  {w}\n"

    return text


def format_market_links_footer(
    markets: list, start_idx: int, lang: str,
) -> str:
    text = "\n🔗 <b>Links:</b>\n"
    for i, m in enumerate(markets[:5]):
        idx = start_idx + i
        text += f"  {idx}. <a href='{m.market_url}'>{html.escape(m.question[:40])}</a>\n"
    return text


# ==================== HANDLERS ====================

@router.callback_query(F.data == "menu:trending")
@router.callback_query(F.data == "intel:back_categories")
async def callback_categories(callback: CallbackQuery) -> None:
    """Show category selection."""
    async with db.session() as session:
        user = await UserRepository(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )

    try:
        await callback.answer()
    except Exception:
        pass

    try:
        await callback.message.edit_text(
            "📊 <b>MARKET SIGNALS</b>\n\nChoose a category:",
            reply_markup=get_category_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await callback.message.answer(
            "📊 <b>MARKET SIGNALS</b>\n\nChoose a category:",
            reply_markup=get_category_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(F.data.startswith("intel:cat:"))
@router.callback_query(F.data.startswith("intel:time:"))
@router.callback_query(F.data.startswith("intel:p:"))
async def callback_trending(callback: CallbackQuery) -> None:
    """Handle category/timeframe/pagination selection."""
    parts = callback.data.split(":")
    action = parts[1]

    if action == "cat":
        cat_str = parts[2]
        tf_str = "week"
        page = 1
    elif action == "time":
        cat_str = parts[2]
        tf_str = parts[3]
        page = int(parts[4]) if len(parts) > 4 else 1
    elif action == "p":
        cat_str = parts[2]
        tf_str = parts[3]
        page = int(parts[4]) if len(parts) > 4 else 1
    else:
        await callback.answer("Unknown action")
        return

    category = Category(cat_str) if cat_str in [c.value for c in Category] else Category.ALL
    timeframe = TimeFrame(tf_str) if tf_str in [t.value for t in TimeFrame] else TimeFrame.WEEK

    async with db.session() as session:
        user = await UserRepository(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )

    try:
        await callback.answer()
    except Exception:
        pass

    try:
        await callback.message.edit_text(
            get_text("loading", user.language),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

    try:
        markets = await market_intelligence.fetch_trending_markets(
            category=category, timeframe=timeframe, limit=50,
        )

        if not markets and timeframe != TimeFrame.MONTH:
            markets = await market_intelligence.fetch_trending_markets(
                category=category, timeframe=TimeFrame.MONTH, limit=50,
            )
            timeframe = TimeFrame.MONTH

        if not markets:
            await callback.message.edit_text(
                get_text("no_signals", user.language),
                reply_markup=get_category_keyboard(user.language),
                parse_mode=ParseMode.HTML,
            )
            return

        # Pagination
        PER_PAGE = 10
        total_pages = math.ceil(len(markets) / PER_PAGE)
        page = max(1, min(page, total_pages))
        start = (page - 1) * PER_PAGE
        page_markets = markets[start : start + PER_PAGE]

        # Build text
        cat_name = get_text(f"cat_{cat_str}" if cat_str != "pop-culture" else "cat_pop_culture", user.language)
        text = f"📊 <b>{cat_name.upper()}</b>\n"
        text += f"📄 Page {page}/{total_pages} ({len(markets)} markets)\n\n"

        for i, m in enumerate(page_markets):
            text += format_market_card(m, start + i + 1, user.language)
            text += "\n"

        text += format_market_links_footer(page_markets, start + 1, user.language)
        text += "\n💡 Tap a number to see details"

        await callback.message.edit_text(
            text,
            reply_markup=get_trending_keyboard(
                user.language, page_markets,
                category.value, timeframe.value,
                page=page, total_pages=total_pages,
            ),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        try:
            await callback.message.edit_text(
                get_text("error_generic", user.language),
                reply_markup=get_category_keyboard(user.language),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("intel:m:"))
async def callback_market_detail(callback: CallbackQuery) -> None:
    """Show detailed market analysis."""
    cache_key = callback.data.split(":")[2]

    async with db.session() as session:
        user = await UserRepository(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )

    try:
        await callback.answer()
    except Exception:
        pass

    market = get_cached_market(cache_key)
    if not market:
        try:
            await callback.message.edit_text(
                "❌ Market not found. Try refreshing the list.",
                reply_markup=get_category_keyboard(user.language),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
        return

    try:
        rec = market_intelligence.generate_recommendation(market)
        text = format_market_detail(market, rec, user.language)

        await callback.message.edit_text(
            text,
            reply_markup=get_market_detail_keyboard(user.language, market),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Market detail error: {e}", exc_info=True)
        try:
            await callback.message.edit_text(
                "❌ Error loading market data.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("intel:"))
async def catch_intel_callbacks(callback: CallbackQuery):
    """Catch-all for unhandled intel: callbacks."""
    logger.warning(f"Unhandled intel callback: {callback.data}")
    await callback.answer("⚠️ Handler not found")


def setup_intelligence_handlers(dp) -> None:
    dp.include_router(router)
    logger.info("Intelligence handlers registered")
