
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from loguru import logger
import html

from database import db
from services.user_service import resolve_user
from services.format_service import format_market_card, format_volume, format_price
from i18n import get_text
from market_intelligence import market_intelligence, Category, TimeFrame
from keyboards_intelligence import get_trending_keyboard, get_category_keyboard

router = Router(name="hot_today")


async def get_hot_page_content(page: int, lang: str):
    """
    Fetch and format hot markets page.
    Returns (text, reply_markup) or (None, None) if empty/error.
    """
    try:
        # Fetch markets (limit 100)
        markets = await market_intelligence.fetch_trending_markets(
            category=Category.ALL,
            timeframe=TimeFrame.MONTH, # Ignored by simplified logic
            limit=100,
        )

        if not markets:
            return None, None

        # Pagination Logic
        items_per_page = 10
        total_items = len(markets)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        # Clamp page
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_markets = markets[start_idx:end_idx]

        # Build Text List
        text = f"🔥 <b>{get_text('hot.title', lang)}</b> (Page {page}/{total_pages})\n\n"
        
        for i, m in enumerate(page_markets):
            idx = start_idx + i + 1
            # Clean title
            q = html.escape(m.question)
            
            vol = format_volume(m.volume_24h)
            y_p = format_price(m.yes_price)
            n_p = format_price(m.no_price)
            
            text += f"<b>{idx}. {q}</b>\n"
            text += f"📊 Vol: {vol} · 💰 {y_p} / {n_p}\n"
            text += f"🔗 <a href='{m.market_url}'>Open Market</a>\n\n"

        # Build Pagination Keyboard
        builder = InlineKeyboardBuilder()
        nav_row = []
        
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"intel:hot:{page-1}"))
            
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
        
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"intel:hot:{page+1}"))
            
        builder.row(*nav_row)
        
        # Back button
        builder.row(InlineKeyboardButton(text=get_text("btn.back", lang), callback_data="menu:main"))
        
        return text, builder.as_markup()

    except Exception as e:
        logger.error(f"Error generating hot page: {e}", exc_info=True)
        return None, None


@router.callback_query(F.data.startswith("intel:hot"))
async def callback_hot_today(callback: CallbackQuery) -> None:
    """Show Hot Today — paginated list of top markets by volume."""
    user, lang = await resolve_user(callback.from_user)

    # Parse page from callback data: "intel:hot:PAGE"
    page = 1
    parts = callback.data.split(":")
    if len(parts) >= 3:
        try:
            page = int(parts[2])
        except ValueError:
            page = 1
            
    try:
        if page == 1:
            # Only answer/loading on first load to avoid flicker on pagination
            await callback.answer()
            await callback.message.edit_text(
                get_text("loading", lang),
                parse_mode=ParseMode.HTML,
            )
    except Exception:
        pass

    try:
        text, reply_markup = await get_hot_page_content(page, lang)

        if not text:
            await callback.message.edit_text(
                get_text("hot.title", lang) + "\n\n" + get_text("hot.empty", lang),
                # reply_markup=get_category_keyboard(lang), # Optional fallback
                parse_mode=ParseMode.HTML,
            )
            return

        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Hot today error: {e}", exc_info=True)
        try:
            await callback.message.edit_text(
                get_text("error_generic", lang),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


def setup_hot_handlers(dp) -> None:
    dp.include_router(router)
    logger.info("Hot Today handlers registered")

