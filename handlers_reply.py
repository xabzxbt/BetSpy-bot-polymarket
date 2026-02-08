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
from keyboards import get_settings_keyboard, get_cancel_keyboard
from config import get_settings

router = Router(name="reply_nav")


# ── Signals ──────────────────────────────────────────

@router.message(F.text.in_(["📊 Signals", "📊 Сигнали", "📊 Сигналы"]))
async def reply_signals(message: Message) -> None:
    user, lang = await resolve_user(message.from_user)
    from keyboards_intelligence import get_category_keyboard
    await message.answer(
        get_text("intel.market_signals_title", lang),
        reply_markup=get_category_keyboard(lang),
        parse_mode=ParseMode.HTML,
    )


# ── Hot Today ────────────────────────────────────────

@router.message(F.text.in_(["🔥 Hot", "🔥 Гарячі", "🔥 Горячие"]))
async def reply_hot(message: Message) -> None:
    user, lang = await resolve_user(message.from_user)
    await message.answer(get_text("loading", lang), parse_mode=ParseMode.HTML)

    from market_intelligence import market_intelligence, Category, TimeFrame
    from services.format_service import format_market_card
    from keyboards_intelligence import get_trending_keyboard, get_category_keyboard

    try:
        markets = await market_intelligence.fetch_trending_markets(
            category=Category.ALL, timeframe=TimeFrame.WEEK, limit=10,
        )
        if not markets:
            await message.answer(
                get_text("hot.title", lang) + "\n\n" + get_text("hot.empty", lang),
                parse_mode=ParseMode.HTML,
            )
            return

        text = get_text("hot.title", lang) + "\n\n"
        for i, m in enumerate(markets, 1):
            text += format_market_card(m, i, lang) + "\n"
        text += f"\n💡 {get_text('intel.click_hint', lang)}"

        await message.answer(
            text,
            reply_markup=get_trending_keyboard(lang, markets, "all", "week", page=1, total_pages=1),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Hot today reply error: {e}")
        await message.answer(get_text("error_generic", lang), parse_mode=ParseMode.HTML)


# ── Analyze ──────────────────────────────────────────

@router.message(F.text.in_(["🔗 Analyze", "🔗 Аналіз", "🔗 Анализ"]))
async def reply_analyze(message: Message, state: FSMContext) -> None:
    user, lang = await resolve_user(message.from_user)
    from handlers import AnalyzeEventStates
    await state.set_state(AnalyzeEventStates.waiting_for_link)
    await message.answer(
        get_text("prompt_analyze_link", lang),
        reply_markup=get_cancel_keyboard(lang),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


# ── Wallets ──────────────────────────────────────────

@router.message(F.text.in_(["📋 Wallets", "📋 Гаманці", "📋 Кошельки"]))
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


# ── Watchlist ────────────────────────────────────────

@router.message(F.text.in_(["⭐ Watchlist", "⭐ Обрані", "⭐ Избранное"]))
async def reply_watchlist(message: Message) -> None:
    user, lang = await resolve_user(message.from_user)
    from database import db
    from services.watchlist_service import WatchlistService
    import html

    async with db.session() as session:
        items = await WatchlistService.get_all(session, user.id)

    if not items:
        await message.answer(
            get_text("watchlist.title", lang) + "\n\n" + get_text("watchlist.empty", lang),
            parse_mode=ParseMode.HTML,
        )
        return

    text = get_text("watchlist.title", lang) + f" ({len(items)})\n\n"
    for i, item in enumerate(items[:20], 1):
        q = html.escape(item.question[:60])
        text += f"{i}. <b>{q}</b>\n"
        from config import get_referral_link
        market_url = get_referral_link(item.event_slug, item.market_slug)
        text += f"   🔗 <a href='{market_url}'>Open</a>\n\n"

    await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


# ── Settings ─────────────────────────────────────────

@router.message(F.text.in_(["⚙️ Settings", "⚙️ Налашт.", "⚙️ Настройки"]))
async def reply_settings(message: Message) -> None:
    user, lang = await resolve_user(message.from_user)
    await message.answer(
        get_text("settings_menu", lang),
        reply_markup=get_settings_keyboard(lang),
        parse_mode=ParseMode.HTML,
    )


# ── Help ─────────────────────────────────────────────

@router.message(F.text.in_(["❓ Help", "❓ Допомога", "❓ Помощь"]))
async def reply_help(message: Message) -> None:
    user, lang = await resolve_user(message.from_user)
    await message.answer(get_text("help_text", lang), parse_mode=ParseMode.HTML)


def setup_reply_handlers(dp) -> None:
    dp.include_router(router)
    logger.info("Reply navigation handlers registered")
    