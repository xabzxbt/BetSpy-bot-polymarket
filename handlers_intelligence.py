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
import html

from i18n import get_text
from services.user_service import resolve_user
from services.format_service import (
    format_market_card,
    format_market_detail,
    format_market_links_footer,
    format_unified_analysis,
)
from analytics.orchestrator import run_deep_analysis, DeepAnalysis
from market_intelligence import (
    market_intelligence,
    Category,
    TimeFrame,
    MarketStats,
)
from keyboards_intelligence import (
    get_trending_keyboard,
    get_market_detail_keyboard,
    get_cached_market,
)


router = Router(name="intelligence")


# ==================== HANDLERS ====================




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
        # Show Loading
        try:
            await callback.message.edit_text("⏳ Analyzing market deeply...", parse_mode=ParseMode.HTML)
        except Exception:
            pass

        # Run Deep Analysis
        error_info = None
        try:
            deep_result = await run_deep_analysis(market)
        except Exception as e:
            logger.error(f"Deep analysis error: {e}")
            # Create dummy result to force V2 format with error
            deep_result = DeepAnalysis(
                market=market,
                market_price=market.yes_price,
                model_probability=0.5,
                signal_probability=0.5,
                errors={"CRASH": str(e)}
            )
            error_info = str(e)

        text = format_unified_analysis(market, deep_result, lang)
        
        if error_info:
            text += f"\n\n🛑 <b>DEBUG ERROR:</b> {html.escape(error_info)}"

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
