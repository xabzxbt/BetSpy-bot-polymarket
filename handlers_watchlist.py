"""
Watchlist handlers — add/remove/view saved markets.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from loguru import logger
import html

from database import db
from services.user_service import resolve_user
from services.watchlist_service import WatchlistService
from services.format_service import format_volume, format_price, format_signal_emoji
from i18n import get_text
from keyboards import get_back_to_menu_keyboard
from keyboards_intelligence import get_cached_market

router = Router(name="watchlist")


@router.callback_query(F.data == "menu:watchlist")
async def callback_watchlist(callback: CallbackQuery) -> None:
    """Show user's watchlist."""
    user, lang = await resolve_user(callback.from_user)

    try:
        await callback.answer()
    except Exception:
        pass

    async with db.session() as session:
        items = await WatchlistService.get_all(session, user.id)

    if not items:
        await callback.message.edit_text(
            get_text("watchlist.title", lang) + "\n\n" + get_text("watchlist.empty", lang),
            reply_markup=get_back_to_menu_keyboard(lang),
            parse_mode=ParseMode.HTML,
        )
        return

    text = get_text("watchlist.title", lang) + f" ({len(items)})\n\n"

    for i, item in enumerate(items[:20], 1):
        q = html.escape(item.question[:60])
        text += f"{i}. <b>{q}</b>\n"
        from config import get_referral_link
        market_url = get_referral_link(item.event_slug, item.market_slug)
        text += f"   🔗 <a href='{market_url}'>"
        text += f"Open</a>\n\n"

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("btn.back_to_menu", lang),
        callback_data="menu:main",
    ))

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


@router.callback_query(F.data.startswith("wl:add:"))
async def callback_watchlist_add(callback: CallbackQuery) -> None:
    """Add market to watchlist."""
    cache_key = callback.data.split(":")[2]
    user, lang = await resolve_user(callback.from_user)

    market = get_cached_market(cache_key)
    if not market:
        await callback.answer(get_text("intel.market_not_found", lang))
        return

    async with db.session() as session:
        added = await WatchlistService.add(
            session, user.id,
            market.slug, market.event_slug,
            market.question, market.condition_id,
        )

    if added:
        await callback.answer(get_text("watchlist.added", lang), show_alert=True)
    else:
        await callback.answer("Already in watchlist", show_alert=False)


@router.callback_query(F.data.startswith("wl:rm:"))
async def callback_watchlist_remove(callback: CallbackQuery) -> None:
    """Remove market from watchlist."""
    slug = callback.data.split(":")[2]
    user, lang = await resolve_user(callback.from_user)

    async with db.session() as session:
        await WatchlistService.remove(session, user.id, slug)

    await callback.answer(get_text("watchlist.removed", lang))


def setup_watchlist_handlers(dp) -> None:
    dp.include_router(router)
    logger.info("Watchlist handlers registered")
