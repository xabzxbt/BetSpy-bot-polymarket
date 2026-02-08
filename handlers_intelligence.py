"""
Handlers for BetSpy Market Intelligence features (v3).

Changes from v2:
- All formatting functions moved to services/format_service.py
- All user-facing strings go through i18n (get_text)
- User resolution via resolve_user() — no boilerplate
- format_market_detail imported from services, not defined here
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from loguru import logger
import math

from i18n import get_text
from services.user_service import resolve_user
from services.format_service import (
    format_market_card,
    format_market_detail,
    format_market_links_footer,
)
from market_intelligence import (
    market_intelligence,
    Category,
    TimeFrame,
    MarketStats,
)
from keyboards_intelligence import (
    get_trending_keyboard,
    get_category_keyboard,
    get_market_detail_keyboard,
    get_cached_market,
)


router = Router(name="intelligence")


# ==================== HANDLERS ====================

@router.callback_query(F.data == "menu:trending")
@router.callback_query(F.data == "intel:back_categories")
async def callback_categories(callback: CallbackQuery) -> None:
    """Show category selection."""
    user, lang = await resolve_user(callback.from_user)

    try:
        await callback.answer()
    except Exception:
        pass

    try:
        await callback.message.edit_text(
            get_text("intel.market_signals_title", lang),
            reply_markup=get_category_keyboard(lang),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await callback.message.answer(
            get_text("intel.market_signals_title", lang),
            reply_markup=get_category_keyboard(lang),
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

    user, lang = await resolve_user(callback.from_user)

    try:
        await callback.answer()
    except Exception:
        pass

    try:
        await callback.message.edit_text(
            get_text("loading", lang),
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
                get_text("intel.no_signals", lang),
                reply_markup=get_category_keyboard(lang),
                parse_mode=ParseMode.HTML,
            )
            return

        # Pagination
        PER_PAGE = 10
        total_pages = math.ceil(len(markets) / PER_PAGE)
        page = max(1, min(page, total_pages))
        start = (page - 1) * PER_PAGE
        page_markets = markets[start : start + PER_PAGE]

        # Build text — category name from i18n
        cat_key = f"cat.{cat_str.replace('-', '_')}"
        cat_name = get_text(cat_key, lang)

        text = get_text("intel.header_category", lang, emoji="📊", category=cat_name.upper()) + "\n"
        text += get_text("intel.page_info", lang, page=page, total_pages=total_pages, total_items=len(markets)) + "\n\n"

        for i, m in enumerate(page_markets):
            text += format_market_card(m, start + i + 1, lang)
            text += "\n"

        text += format_market_links_footer(page_markets, start + 1, lang)
        text += f"\n💡 {get_text('intel.click_hint', lang)}"

        await callback.message.edit_text(
            text,
            reply_markup=get_trending_keyboard(
                lang, page_markets,
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
                get_text("error_generic", lang),
                reply_markup=get_category_keyboard(lang),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("intel:m:"))
async def callback_market_detail(callback: CallbackQuery) -> None:
    """Show detailed market analysis."""
    cache_key = callback.data.split(":")[2]

    user, lang = await resolve_user(callback.from_user)

    try:
        await callback.answer()
    except Exception:
        pass

    market = get_cached_market(cache_key)
    if not market:
        try:
            await callback.message.edit_text(
                get_text("intel.market_not_found", lang),
                reply_markup=get_category_keyboard(lang),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
        return

    try:
        rec = market_intelligence.generate_recommendation(market)
        text = format_market_detail(market, rec, lang)

        await callback.message.edit_text(
            text,
            reply_markup=get_market_detail_keyboard(lang, market),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Market detail error: {e}", exc_info=True)
        try:
            await callback.message.edit_text(
                get_text("intel.error_loading", lang),
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
