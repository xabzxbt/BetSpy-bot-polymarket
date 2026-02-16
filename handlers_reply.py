"""
Reply keyboard handler — processes the persistent bottom menu buttons.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from loguru import logger

from services.user_service import resolve_user
from i18n import get_text
from config import get_settings
from keyboards import get_settings_keyboard

router = Router(name="reply_nav")


# ── Hot Today ────────────────────────────────────────

@router.message(F.text.in_(["🔥 Hot", "🔥 Гарячі", "🔥 Горячие"]))
async def reply_hot(message: Message) -> None:
    user, lang = await resolve_user(message.from_user)
    await message.answer(get_text("loading", lang), parse_mode=ParseMode.HTML)

    from handlers_hot import get_hot_page_content

    try:
        text, reply_markup = await get_hot_page_content(1, lang)
        
        if not text:
            await message.answer(
                get_text("hot.title", lang) + "\n\n" + get_text("hot.empty", lang),
                parse_mode=ParseMode.HTML,
            )
            return

        await message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Hot today reply error: {e}")
        await message.answer(get_text("error_generic", lang), parse_mode=ParseMode.HTML)


# ── Wallets ──────────────────────────────────────────

@router.message(F.text.in_(['📋 Wallets', '📋 Валлети', '📋 Кошельки']))
async def reply_wallets(message: Message) -> None:
    user, lang = await resolve_user(message.from_user)
    from database import db
    from repository import WalletRepository
    from keyboards import get_wallet_list_keyboard

    async with db.session() as session:
        repo = WalletRepository(session)
        wallets = await repo.get_user_wallets(user.id)

    settings = get_settings()
    if not wallets:
        await message.answer(get_text("no_wallets", lang), parse_mode=ParseMode.HTML)
    else:
        await message.answer(
            get_text("wallet_list_header", lang, count=len(wallets), limit=settings.max_wallets_per_user),
            reply_markup=get_wallet_list_keyboard(lang, wallets),
            parse_mode=ParseMode.HTML,
        )




# ── Settings ─────────────────────────────────────────

@router.message(F.text.in_(["⚙️ Settings", "⚙️ Налашт", "⚙️ Настройки"]))
async def reply_settings(message: Message) -> None:
    user, lang = await resolve_user(message.from_user)
    await message.answer(
        get_text("settings_menu", lang),
        reply_markup=get_settings_keyboard(lang),
        parse_mode=ParseMode.HTML,
    )


# ── Help ─────────────────────────────────────────────

@router.message(F.text.in_(['❓ Help', '❓ Інфо', '❓ Помощь']))
async def reply_help(message: Message) -> None:
    user, lang = await resolve_user(message.from_user)
    await message.answer(get_text("help_text", lang), parse_mode=ParseMode.HTML)


def setup_reply_handlers(dp) -> None:
    dp.include_router(router)
    logger.info("Reply navigation handlers registered")
    