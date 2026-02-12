"""
BetSpy Deep Analysis Handlers

Handles the 🔬 Deep Analysis button on market detail cards.
Runs the full analytics pipeline and shows results.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from loguru import logger

from i18n import get_text
from services.user_service import resolve_user
from services.format_service import format_unified_analysis
from analytics.orchestrator import run_deep_analysis
from analytics.kelly import DEFAULT_BANKROLL
from keyboards_intelligence import get_cached_market, get_category_keyboard


router = Router(name="analytics")


@router.callback_query(F.data.startswith("deep:"))
async def callback_deep_analysis(callback: CallbackQuery) -> None:
    """
    Run deep analysis on a market.
    
    Callback data: deep:{cache_key}
    """
    cache_key = callback.data.split(":")[1]
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

    # Show loading
    try:
        await callback.message.edit_text(
            get_text("deep.loading", lang),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

    try:
        # Run deep analysis
        # TODO: load user bankroll from DB (for now use default)
        bankroll = DEFAULT_BANKROLL

        # --- TEMPORARY TEST AS REQUESTED ---
        try:
            from polymarket_api import PolymarketApiClient
            async with PolymarketApiClient() as api:
                await api.test_holders_endpoint(market.condition_id)
        except Exception as e:
            logger.error(f"Test endpoint failed: {e}")
        # -----------------------------------

        result = await run_deep_analysis(
            market=market,
            bankroll=bankroll,
        )

        text = format_unified_analysis(market, result, lang)

        # Build keyboard with back button
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text=get_text("intel.link_text", lang),
                url=market.market_url,
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=get_text("btn.back", lang),
                callback_data="intel:back_categories",
            ),
            InlineKeyboardButton(
                text=get_text("btn.back_to_menu", lang),
                callback_data="menu:main",
            ),
        )

        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Deep analysis error: {e}", exc_info=True)
        try:
            await callback.message.edit_text(
                get_text("deep.error", lang),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


def setup_analytics_handlers(dp) -> None:
    """Register analytics handlers with dispatcher."""
    dp.include_router(router)
    logger.info("Analytics (Deep Analysis) handlers registered")
