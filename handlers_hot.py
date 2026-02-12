"""
Hot Today handler — shows top markets by 24h volume + whale activity.

Feature: users tap 🔥 Hot Today and get a quick overview of what's
happening right now on Polymarket. No category selection needed.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from loguru import logger

from database import db
from services.user_service import resolve_user
from services.format_service import format_market_card
from i18n import get_text
from market_intelligence import market_intelligence, Category, TimeFrame
from keyboards_intelligence import get_trending_keyboard, get_category_keyboard

router = Router(name="hot_today")


@router.callback_query(F.data == "intel:hot")
async def callback_hot_today(callback: CallbackQuery) -> None:
    """Show Hot Today — top 10 markets by volume, any category."""
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
            category=Category.ALL,
            timeframe=TimeFrame.WEEK,
            limit=10,
        )

        if not markets:
            await callback.message.edit_text(
                get_text("hot.title", lang) + "\n\n" + get_text("hot.empty", lang),
                reply_markup=get_category_keyboard(lang),
                parse_mode=ParseMode.HTML,
            )
            return

        text = get_text("hot.title", lang) + "\n\n"
        for i, m in enumerate(markets, 1):
            text += format_market_card(m, i, lang)
            text += "\n"

        text += f"\n💡 {get_text('intel.click_hint', lang)}"

        await callback.message.edit_text(
            text,
            reply_markup=get_trending_keyboard(
                lang, markets, "all", "week", page=1, total_pages=1,
            ),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Hot today error: {e}")
        try:
            await callback.message.edit_text(
                get_text("error_generic", lang),
                reply_markup=get_category_keyboard(lang),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


def setup_hot_handlers(dp) -> None:
    dp.include_router(router)
    logger.info("Hot Today handlers registered")
