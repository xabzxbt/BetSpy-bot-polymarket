from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from market_intelligence import market_intelligence as engine, Category, TimeFrame
from services.format_service import format_hot_markets
from services.user_service import resolve_user
from i18n import get_text
from loguru import logger

router = Router(name="hot")


@router.callback_query(F.data == "hot_all")
@router.callback_query(F.data == "intel:hot")
async def hot_all_handler(callback: CallbackQuery):
    """Hot Today — all categories"""
    _, lang = await resolve_user(callback.from_user)
    
    try:
        await callback.answer(get_text("loading", lang))
    except Exception:
        pass
    
    markets = await engine.fetch_trending_markets(
        category=Category.ALL,
        timeframe=TimeFrame.TODAY,
        limit=15
    )
    
    text = format_hot_markets(markets, "Today", lang)
    
    # Inline buttons for category filters
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏀 Sports", callback_data="hot_sports"),
            InlineKeyboardButton(text="₿ Crypto", callback_data="hot_crypto"),
        ],
        [
            InlineKeyboardButton(text="🏛 Politics", callback_data="hot_politics"),
            InlineKeyboardButton(text="🔥 All", callback_data="hot_all"),
        ],
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Hot all error: {e}")
        # If edit failed (e.g. same text), just answer
        await callback.answer()


@router.callback_query(F.data == "hot_sports")
async def hot_sports_handler(callback: CallbackQuery):
    _, lang = await resolve_user(callback.from_user)
    try:
        await callback.answer(get_text("loading", lang))
    except Exception:
        pass
    
    markets = await engine.fetch_trending_markets(
        category=Category.SPORTS,
        timeframe=TimeFrame.TODAY,
        limit=10
    )
    
    text = format_hot_markets(markets, "Sports", lang)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back", callback_data="hot_all")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "hot_crypto")
async def hot_crypto_handler(callback: CallbackQuery):
    _, lang = await resolve_user(callback.from_user)
    try:
        await callback.answer(get_text("loading", lang))
    except Exception:
        pass
    
    markets = await engine.fetch_trending_markets(
        category=Category.CRYPTO,
        timeframe=TimeFrame.TODAY,
        limit=10
    )
    
    text = format_hot_markets(markets, "Crypto", lang)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back", callback_data="hot_all")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "hot_politics")
async def hot_politics_handler(callback: CallbackQuery):
    _, lang = await resolve_user(callback.from_user)
    try:
        await callback.answer(get_text("loading", lang))
    except Exception:
        pass
    
    markets = await engine.fetch_trending_markets(
        category=Category.POLITICS,
        timeframe=TimeFrame.TODAY,
        limit=10
    )
    
    text = format_hot_markets(markets, "Politics", lang)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back", callback_data="hot_all")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


def setup_hot_handlers(dp) -> None:
    dp.include_router(router)
    logger.info("Hot handlers registered")
