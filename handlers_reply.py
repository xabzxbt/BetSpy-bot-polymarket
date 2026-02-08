"""
Reply keyboard handler — processes the persistent bottom menu buttons.

When user taps a reply keyboard button (Home, Signals, etc.),
this sends a NEW message with the appropriate inline keyboard.
This is the correct pattern: reply keyboard = navigation, inline = actions.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from loguru import logger

from services.user_service import resolve_user
from i18n import get_text
from keyboards import (
    get_main_menu_keyboard,
    get_persistent_menu,
    get_settings_keyboard,
    get_cancel_keyboard,
)
from config import get_settings

router = Router(name="reply_nav")


@router.message(F.text.in_([
    "🏠 Home", "🏠 Домів", "🏠 Домой",  # EN, UK, RU
]))
async def reply_home(message: Message, state: FSMContext) -> None:
    """Handle Home button from reply keyboard."""
    await state.clear()
    user, lang = await resolve_user(message.from_user)
    settings = get_settings()
    await message.answer(
        get_text("welcome_main", lang, limit=settings.max_wallets_per_user),
        reply_markup=get_main_menu_keyboard(lang),
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text.in_([
    "📊 Signals", "📊 Сигнали", "📊 Сигналы",
]))
async def reply_signals(message: Message) -> None:
    """Handle Signals button — show category selection."""
    user, lang = await resolve_user(message.from_user)
    from keyboards_intelligence import get_category_keyboard
    await message.answer(
        get_text("intel.market_signals_title", lang),
        reply_markup=get_category_keyboard(lang),
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text.in_([
    "🔗 Analyze", "🔗 Аналіз", "🔗 Анализ",
]))
async def reply_analyze(message: Message, state: FSMContext) -> None:
    """Handle Analyze button — prompt for link."""
    user, lang = await resolve_user(message.from_user)
    from handlers import AnalyzeEventStates
    await state.set_state(AnalyzeEventStates.waiting_for_link)
    await message.answer(
        get_text("prompt_analyze_link", lang),
        reply_markup=get_cancel_keyboard(lang),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


@router.message(F.text.in_([
    "📋 Wallets", "📋 Гаманці", "📋 Кошельки",
]))
async def reply_wallets(message: Message) -> None:
    """Handle Wallets button."""
    user, lang = await resolve_user(message.from_user)
    from database import db
    from repository import WalletRepository
    from keyboards import get_wallet_list_keyboard, get_main_menu_keyboard

    async with db.session() as session:
        repo = WalletRepository(session)
        wallets = await repo.get_user_wallets(user.id)

    settings = get_settings()
    if not wallets:
        await message.answer(
            get_text("no_wallets", lang),
            reply_markup=get_main_menu_keyboard(lang),
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.answer(
            get_text("wallet_list_header", lang, count=len(wallets), limit=settings.max_wallets_per_user),
            reply_markup=get_wallet_list_keyboard(lang, wallets),
            parse_mode=ParseMode.HTML,
        )


@router.message(F.text.in_([
    "⚙️ Settings", "⚙️ Налашт.", "⚙️ Настройки",
]))
async def reply_settings(message: Message) -> None:
    """Handle Settings button."""
    user, lang = await resolve_user(message.from_user)
    await message.answer(
        get_text("settings_menu", lang),
        reply_markup=get_settings_keyboard(lang),
        parse_mode=ParseMode.HTML,
    )


def setup_reply_handlers(dp) -> None:
    dp.include_router(router)
    logger.info("Reply navigation handlers registered")
