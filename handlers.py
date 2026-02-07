"""
Aiogram 3.x handlers for the Polymarket Whale Tracker bot.
"""

import re
from datetime import datetime
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from database import db
from repository import UserRepository, WalletRepository
from polymarket_api import api_client
from translations import get_text, get_side_text, get_pnl_emoji, Language
from keyboards import (
    get_language_keyboard,
    get_main_menu_keyboard,
    get_cancel_keyboard,
    get_back_to_menu_keyboard,
    get_nickname_keyboard,
    get_wallet_list_keyboard,
    get_wallet_details_keyboard,
    get_confirm_remove_keyboard,
    get_wallet_back_keyboard,
    get_settings_keyboard,
    get_settings_language_keyboard,
    get_stats_range_keyboard,
    get_wallet_settings_keyboard,
    get_wallet_settings_keyboard,
    get_min_amount_keyboard,
)
from config import get_settings
from aiogram.fsm.state import State, StatesGroup
from market_intelligence import market_intelligence
from handlers_intelligence import format_market_detail

# Create router
router = Router(name="main")

# Regex for Ethereum address validation
ETH_ADDRESS_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")


def is_valid_eth_address(address: str) -> bool:
    """Validate Ethereum address format."""
    return bool(ETH_ADDRESS_REGEX.match(address))


class AddWalletStates(StatesGroup):
    """States for add wallet flow."""
    waiting_for_address = State()
    waiting_for_nickname = State()


class AnalyzeEventStates(StatesGroup):
    """States for analyze event flow."""
    waiting_for_link = State()


# ==================== COMMAND HANDLERS ====================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command."""
    await state.clear()
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        
        if not user:
            # New user - show language selection
            await message.answer(
                get_text("welcome_choose_language", "en"),
                reply_markup=get_language_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        else:
            # Existing user - show main menu
            settings = get_settings()
            await message.answer(
                get_text("welcome_main", user.language, limit=settings.max_wallets_per_user),
                reply_markup=get_main_menu_keyboard(user.language),
                parse_mode=ParseMode.HTML,
            )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        
        await message.answer(
            get_text("help_text", user.language),
            reply_markup=get_back_to_menu_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )


# ==================== LANGUAGE SELECTION (ONBOARDING) ====================

@router.callback_query(F.data.startswith("lang:"))
async def callback_language_onboarding(callback: CallbackQuery) -> None:
    """Handle initial language selection."""
    lang_code = callback.data.split(":")[1]
    
    if lang_code not in [l.value for l in Language]:
        await callback.answer("Invalid language")
        return
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            language=lang_code,
        )
        user.language = lang_code
        await session.commit()
        
        settings = get_settings()
        await callback.message.edit_text(
            get_text("welcome_main", lang_code, limit=settings.max_wallets_per_user),
            reply_markup=get_main_menu_keyboard(lang_code),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


# ==================== MAIN MENU ====================

@router.callback_query(F.data == "menu:main")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show main menu."""
    await state.clear()
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        settings = get_settings()
        await callback.message.edit_text(
            get_text("welcome_main", user.language, limit=settings.max_wallets_per_user),
            reply_markup=get_main_menu_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def callback_help(callback: CallbackQuery) -> None:
    """Show help."""
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        await callback.message.edit_text(
            get_text("help_text", user.language),
            reply_markup=get_back_to_menu_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


# ==================== ANALYZE LINK FLOW ====================

@router.callback_query(F.data == "menu:analyze_link")
async def callback_analyze_link(callback: CallbackQuery, state: FSMContext) -> None:
    """Start analyze link flow."""
    # Get user language
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        lang = user.language if user else "en"

    await state.set_state(AnalyzeEventStates.waiting_for_link)
    
    await callback.message.edit_text(
        get_text("prompt_analyze_link", lang),
        reply_markup=get_cancel_keyboard(lang),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.message(AnalyzeEventStates.waiting_for_link)
async def process_analyze_link(message: Message, state: FSMContext) -> None:
    """Process the link from user."""
    # Get user language
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        lang = user.language if user else "en"
        
    url = message.text.strip()
    
    # Check if user cancelled via text (improbable with inline buttons but possible)
    if url.lower() in ["cancel", "скасувати", "отмена"]:
        await state.clear()
        await message.answer(get_text("action_cancelled", lang), reply_markup=get_main_menu_keyboard(lang))
        return
    
    # Simple validation and slug extraction
    slug = None
    market_slug = None
    
    if "polymarket.com/event/" in url:
        try:
            # Extract everything after event/
            # Example: https://polymarket.com/event/nba-was-bkn-2026-02-07
            # Example: https://polymarket.com/event/nba-was-bkn-2026-02-07/who-will-win
            parts = url.split("polymarket.com/event/")
            if len(parts) > 1:
                # Take the first part of the path, ignore query params
                path_parts = parts[1].split("?")[0].split("/")
                if len(path_parts) > 0:
                    slug = path_parts[0] # Event slug or market slug (if only 1 part)
                    
                    if len(path_parts) > 1 and path_parts[1]:
                        market_slug = path_parts[1] # Specific market slug
        except Exception:
            pass
            
    if not slug:
        await message.answer(
            get_text("invalid_link", lang),
            reply_markup=get_cancel_keyboard(lang),
            parse_mode=ParseMode.HTML,
        )
        return

    # Notify user we are working
    working_msg = await message.answer(
        get_text("analyzing_event", lang, slug=slug),
        parse_mode=ParseMode.HTML,
    )
    
    try:
        # Fetch markets
        # We need to ensure we have a functional market_intelligence instance
        # It is imported from market_intelligence module
        markets = await market_intelligence.fetch_event_markets(slug, market_slug)
        
        if not markets:
            await working_msg.edit_text(
                get_text("analysis_error", lang),
                reply_markup=get_back_to_menu_keyboard(lang),
                parse_mode=ParseMode.HTML,
            )
            await state.clear()
            return
            
        # Check if this is a multi-outcome event
        if len(markets) > 1:
            # Multi-outcome event: show TOP-3
            top_markets = markets[:3]
            
            # Header explaining this is a multi-outcome event
            text = f"📊 <b>Подія з {len(markets)} учасниками</b>\n"
            text += f"Показуємо ТОП-3 за обсягом торгів:\n"
            text += f"{'─'*28}\n\n"
            
            for i, market in enumerate(top_markets, 1):
                rec = market_intelligence.generate_recommendation(market)
                
                # Compact format for each outcome
                signal_emoji = "🟢" if market.signal_score >= 70 else "🟡" if market.signal_score >= 50 else "🔴"
                
                text += f"<b>{i}. {market.question[:80]}{'...' if len(market.question) > 80 else ''}</b>\n"
                text += f"💰 YES: {int(market.yes_price*100)}¢ · NO: {int(market.no_price*100)}¢\n"
                text += f"📊 Vol: ${market.volume_24h/1000:.1f}K · {signal_emoji} Сигнал: {market.signal_score}/100\n"
                
                # Whale info if available
                wa = market.whale_analysis
                if wa and wa.is_significant:
                    whale_side = wa.dominance_side
                    whale_pct = int(wa.dominance_pct)
                    text += f"🐋 Smart Money: {whale_pct}% {whale_side}\n"
                
                # Recommendation
                if rec.should_bet:
                    text += f"✅ Рекомендація: <b>{rec.side}</b>\n"
                else:
                    text += f"❌ Не ставити\n"
                
                text += "\n"
            
            # Footer with link
            if markets:
                event_url = f"https://polymarket.com/event/{markets[0].event_slug}"
                text += f"🔗 <a href='{event_url}'>Відкрити подію на Polymarket</a>"
        else:
            # Single outcome: show detailed view
            best_market = markets[0]
            rec = market_intelligence.generate_recommendation(best_market)
            text = format_market_detail(best_market, rec, lang)
        
        await working_msg.edit_text(
            text,
            reply_markup=get_back_to_menu_keyboard(lang),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        
    except Exception as e:
        logger.error(f"Error analyzing link: {e}")
        await working_msg.edit_text(
            get_text("analysis_error", lang),
            reply_markup=get_back_to_menu_keyboard(lang),
            parse_mode=ParseMode.HTML,
        )
        
    await state.clear()





# ==================== ADD WALLET FLOW ====================

@router.callback_query(F.data == "menu:add_wallet")
async def callback_add_wallet_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Start add wallet flow."""
    async with db.session() as session:
        user_repo = UserRepository(session)
        wallet_repo = WalletRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Check wallet limit
        settings = get_settings()
        wallet_count = await wallet_repo.count_user_wallets(user.id)
        
        if wallet_count >= settings.max_wallets_per_user:
            await callback.message.edit_text(
                get_text("wallet_limit_reached", user.language, limit=settings.max_wallets_per_user),
                reply_markup=get_back_to_menu_keyboard(user.language),
                parse_mode=ParseMode.HTML,
            )
            await callback.answer()
            return
        
        await state.set_state(AddWalletStates.waiting_for_address)
        
        await callback.message.edit_text(
            get_text("add_wallet_prompt", user.language),
            reply_markup=get_cancel_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.message(AddWalletStates.waiting_for_address)
async def process_wallet_address(message: Message, state: FSMContext) -> None:
    """Process wallet address input."""
    wallet_address = message.text.strip()
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        wallet_repo = WalletRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        lang = user.language
        
        # Validate address
        if not is_valid_eth_address(wallet_address):
            await message.answer(
                get_text("invalid_address", lang),
                reply_markup=get_cancel_keyboard(lang),
                parse_mode=ParseMode.HTML,
            )
            return
        
        # Check if already exists
        existing = await wallet_repo.get_by_user_and_address(user.id, wallet_address)
        if existing:
            await state.clear()
            await message.answer(
                get_text("wallet_already_exists", lang),
                reply_markup=get_back_to_menu_keyboard(lang),
                parse_mode=ParseMode.HTML,
            )
            return
        
        # Store address in state
        await state.update_data(wallet_address=wallet_address)
        await state.set_state(AddWalletStates.waiting_for_nickname)
        
        # Try to fetch profile
        loading_msg = await message.answer(
            get_text("loading", lang),
            parse_mode=ParseMode.HTML,
        )
        
        detected_name = None
        try:
            profile = await api_client.get_profile(wallet_address)
            if profile and profile.display_name:
                detected_name = profile.display_name
        except Exception as e:
            logger.warning(f"Failed to fetch profile: {e}")
        
        await state.update_data(detected_name=detected_name)
        
        await loading_msg.edit_text(
            get_text("add_wallet_nickname_prompt", lang, address=wallet_address),
            reply_markup=get_nickname_keyboard(lang, wallet_address, detected_name),
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(F.data.startswith("nickname:"), AddWalletStates.waiting_for_nickname)
async def callback_nickname_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle nickname selection from buttons."""
    parts = callback.data.split(":", 2)
    action = parts[1]
    nickname = parts[2] if len(parts) > 2 else None
    
    data = await state.get_data()
    wallet_address = data.get("wallet_address")
    
    if not wallet_address:
        await state.clear()
        await callback.answer("Error: wallet address lost")
        return
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        wallet_repo = WalletRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Create wallet
        wallet = await wallet_repo.create(
            user_id=user.id,
            wallet_address=wallet_address,
            nickname=nickname,
        )
        
        await state.clear()
        
        await callback.message.edit_text(
            get_text("wallet_added", user.language, name=nickname, address=wallet_address),
            reply_markup=get_back_to_menu_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.message(AddWalletStates.waiting_for_nickname)
async def process_custom_nickname(message: Message, state: FSMContext) -> None:
    """Process custom nickname input."""
    nickname = message.text.strip()[:100]
    
    data = await state.get_data()
    wallet_address = data.get("wallet_address")
    
    if not wallet_address:
        await state.clear()
        return
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        wallet_repo = WalletRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        
        # Create wallet
        wallet = await wallet_repo.create(
            user_id=user.id,
            wallet_address=wallet_address,
            nickname=nickname,
        )
        
        await state.clear()
        
        await message.answer(
            get_text("wallet_added", user.language, name=nickname, address=wallet_address),
            reply_markup=get_back_to_menu_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(F.data == "action:cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel current action."""
    await state.clear()
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        settings = get_settings()
        await callback.message.edit_text(
            get_text("welcome_main", user.language, limit=settings.max_wallets_per_user),
            reply_markup=get_main_menu_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer(get_text("action_cancelled", "en"))


# ==================== MY WALLETS ====================

@router.callback_query(F.data == "menu:my_wallets")
async def callback_my_wallets(callback: CallbackQuery) -> None:
    """Show user's wallets."""
    async with db.session() as session:
        user_repo = UserRepository(session)
        wallet_repo = WalletRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        wallets = await wallet_repo.get_user_wallets(user.id)
        settings = get_settings()
        
        if not wallets:
            await callback.message.edit_text(
                get_text("no_wallets", user.language),
                reply_markup=get_main_menu_keyboard(user.language),
                parse_mode=ParseMode.HTML,
            )
        else:
            await callback.message.edit_text(
                get_text(
                    "wallet_list_header",
                    user.language,
                    count=len(wallets),
                    limit=settings.max_wallets_per_user
                ),
                reply_markup=get_wallet_list_keyboard(user.language, wallets),
                parse_mode=ParseMode.HTML,
            )
    
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:view:"))
async def callback_wallet_view(callback: CallbackQuery) -> None:
    """View wallet details."""
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        wallet_repo = WalletRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        date_str = wallet.created_at.strftime("%d.%m.%Y")
        
        # Show pause status if paused
        status_text = ""
        if wallet.is_paused:
            status_text = "\n\n⏸️ " + get_text("wallet_paused", user.language)
        
        await callback.message.edit_text(
            get_text(
                "wallet_details",
                user.language,
                name=wallet.nickname,
                address=wallet.wallet_address,
                date=date_str
            ) + status_text,
            reply_markup=get_wallet_details_keyboard(user.language, wallet_id, wallet.wallet_address),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


# ==================== WALLET ACTIONS ====================

@router.callback_query(F.data.startswith("wallet:positions:"))
async def callback_wallet_positions(callback: CallbackQuery) -> None:
    """View wallet positions."""
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        # Show loading
        await callback.message.edit_text(
            get_text("loading", user.language),
            parse_mode=ParseMode.HTML,
        )
        
        # Fetch positions
        positions = await api_client.get_wallet_positions(wallet.wallet_address)
        
        if not positions:
            await callback.message.edit_text(
                get_text("positions_header", user.language, name=wallet.nickname) +
                get_text("no_positions", user.language),
                reply_markup=get_wallet_back_keyboard(user.language, wallet_id),
                parse_mode=ParseMode.HTML,
            )
            await callback.answer()
            return
        
        # Build positions message
        text = get_text("positions_header", user.language, name=wallet.nickname)
        total_value = 0
        
        for pos in positions[:10]:  # Limit to 10 positions
            pnl_emoji = get_pnl_emoji(pos.cash_pnl)
            text += get_text(
                "position_item",
                user.language,
                title=pos.title[:50],
                outcome=pos.outcome,
                size=pos.size,
                avg_price=pos.avg_price,
                current_value=pos.current_value,
                pnl=pos.cash_pnl,
                pnl_percent=pos.percent_pnl,
                pnl_emoji=pnl_emoji,
            )
            total_value += pos.current_value
        
        text += get_text("positions_summary", user.language, total_value=total_value)
        
        await callback.message.edit_text(
            text,
            reply_markup=get_wallet_back_keyboard(user.language, wallet_id),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()





# Consolidated to detailed stats view
# @router.callback_query(F.data.startswith("wallet:pnl_range:"))
# async def callback_wallet_pnl_range_select(callback: CallbackQuery) -> None:
#     """Show date range selection for PnL report."""
#     wallet_id = int(callback.data.split(":")[2])
#     
#     async with db.session() as session:
#         user_repo = UserRepository(session)
#         
#         user = await user_repo.get_or_create(
#             telegram_id=callback.from_user.id,
#             username=callback.from_user.username,
#             first_name=callback.from_user.first_name,
#         )
#         
#         # Get wallet
#         from sqlalchemy import select
#         from models import TrackedWallet
#         
#         stmt = select(TrackedWallet).where(
#             TrackedWallet.id == wallet_id,
#             TrackedWallet.user_id == user.id
#         )
#         result = await session.execute(stmt)
#         wallet = result.scalar_one_or_none()
#         
#         if not wallet:
#             await callback.answer("Wallet not found")
#             return
#         
#         # Show date range selection
#         await callback.message.edit_text(
#             get_text("pnl_range_header", user.language, name=wallet.nickname, days="Period"),
#             reply_markup=get_pnl_range_keyboard(user.language, wallet_id),
#             parse_mode=ParseMode.HTML,
#         )
#     
#     await callback.answer()





@router.callback_query(F.data.startswith("wallet:stats_range:"))
async def callback_wallet_stats_range_select(callback: CallbackQuery) -> None:
    """Show date range selection for statistics report."""
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        # Show date range selection
        await callback.message.edit_text(
            get_text("stats_header", user.language, name=wallet.nickname, days="Period"),
            reply_markup=get_stats_range_keyboard(user.language, wallet_id),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("stats_range:"))
async def callback_wallet_stats_range(callback: CallbackQuery) -> None:
    """View wallet statistics for selected date range."""
    parts = callback.data.split(":")
    days = int(parts[1])
    wallet_id = int(parts[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        # Show loading
        await callback.message.edit_text(
            get_text("loading", user.language),
            parse_mode=ParseMode.HTML,
        )
        
        # Fetch detailed statistics for date range
        stats = await api_client.get_detailed_statistics_for_date_range(wallet.wallet_address, days)
        
        # Format the statistics message
        # Determine interval string based on days
        if days <= 1:
            interval_str = "1D"
        elif days <= 7:
            interval_str = "1W"
        elif days <= 31:
            interval_str = "1M"
        else:
            interval_str = "ALL"
            
        text = get_text("stats_header", user.language, name=wallet.nickname, days=days)
        
        # Add main statistics
        text += get_text(
            "stat_position_value",
            user.language,
            value=stats["position_value"]
        )
        
        # Add Gain/Loss/Net Total based on interval
        text += f"\n{get_text('interval_pnl_section', user.language, interval=interval_str)}\n"
        
        # Format values with proper signs
        gain_sign = "+" if stats['gain'] >= 0 else ""
        loss_sign = "-"  # Loss is always shown as negative
        net_sign = "+" if stats['net_pnl'] >= 0 else "-"
        
        # Prepare values
        gain_value = f'{gain_sign}{abs(stats["gain"]):.2f}'
        loss_value = f'{loss_sign}{abs(stats["loss"]):.2f}'  # Show loss as negative
        net_value = f'{net_sign}{abs(stats["net_pnl"]):.2f}'
        
        text += f"{get_text('gain_label', user.language, value=gain_value, emoji=get_pnl_emoji(stats['gain']))}\n"
        text += f"{get_text('loss_label', user.language, value=loss_value, emoji=get_pnl_emoji(-stats['loss']))}\n"  # Negative for loss emoji
        text += f"{get_text('net_total_label', user.language, value=net_value, emoji=get_pnl_emoji(stats['net_pnl']))}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_wallet_back_keyboard(user.language, wallet_id),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:debug:"))
async def callback_wallet_debug(callback: CallbackQuery) -> None:
    """Debug wallet data - admin function to troubleshoot profile/data issues."""
    # Only allow for admin users, or comment out the admin check for testing
    # For now, let's allow it for testing purposes
    
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        # Show loading
        await callback.message.edit_text(
            get_text("loading", user.language),
            parse_mode=ParseMode.HTML,
        )
        
        # Fetch debug data
        debug_data = await api_client.debug_wallet_data(wallet.wallet_address)
        
        # Format debug information
        profile_info = debug_data.get('profile', 'None')
        positions_count = debug_data.get('positions_count', 0)
        trades_count = debug_data.get('trades_count', 0)
        activity_count = debug_data.get('activity_count', 0)
        wallet_addr = debug_data.get('wallet_address', wallet.wallet_address)
        proxy_wallet = debug_data.get('proxy_wallet', 'N/A')
        pnl_1m_len = debug_data.get('pnl_series_1m_length', 0)
        proxy_pnl_1m_len = debug_data.get('proxy_pnl_series_1m_length', 0)
        
        debug_text = f"🔧 <b>Debug Info for {wallet.nickname}</b>\n\n"
        debug_text += f"💳 Address: <code>{wallet_addr}</code>\n"
        debug_text += f"🔗 Proxy Wallet: <code>{proxy_wallet}</code>\n\n"
        
        if profile_info and hasattr(profile_info, 'display_name'):
            debug_text += f"👤 Display Name: {profile_info.display_name or 'N/A'}\n"
            debug_text += f"🏷️ Pseudonym: {getattr(profile_info, 'pseudonym', 'N/A')}\n"
            debug_text += f"👀 Display Public: {getattr(profile_info, 'display_username_public', 'N/A')}\n\n"
        else:
            debug_text += "👤 Profile: Not found or incomplete\n\n"
        
        debug_text += f"📊 Positions: {positions_count}\n"
        debug_text += f"📈 Trades: {trades_count}\n"
        debug_text += f"🔄 Activity: {activity_count}\n\n"
        
        debug_text += f"📈 PnL Series (1M): {pnl_1m_len} points\n"
        debug_text += f"🔗 Proxy PnL Series (1M): {proxy_pnl_1m_len} points\n\n"
        
        debug_text += "ℹ️ <b>Note:</b> This is debug information to help troubleshoot data mismatches."
        
        await callback.message.edit_text(
            debug_text,
            reply_markup=get_wallet_back_keyboard(user.language, wallet_id),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:trades:"))
async def callback_wallet_trades(callback: CallbackQuery) -> None:
    """View recent trades."""
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        # Show loading
        await callback.message.edit_text(
            get_text("loading", user.language),
            parse_mode=ParseMode.HTML,
        )
        
        # Fetch trades
        trades = await api_client.get_wallet_trades(wallet.wallet_address, limit=10)
        
        if not trades:
            await callback.message.edit_text(
                get_text("recent_trades_header", user.language, name=wallet.nickname) +
                get_text("no_recent_trades", user.language),
                reply_markup=get_wallet_back_keyboard(user.language, wallet_id),
                parse_mode=ParseMode.HTML,
            )
            await callback.answer()
            return
        
        # Build trades message
        text = get_text("recent_trades_header", user.language, name=wallet.nickname)
        
        for trade in trades:
            side_emoji = "🟢" if trade.side.upper() == "BUY" else "🔴"
            text += get_text(
                "trade_item",
                user.language,
                side_emoji=side_emoji,
                side=trade.side,
                outcome=trade.outcome,
                title=trade.title[:40],
                usdc_size=trade.usdc_size,
                price=trade.price,
                time=trade.formatted_time,
            )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_wallet_back_keyboard(user.language, wallet_id),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:remove:"))
async def callback_wallet_remove(callback: CallbackQuery) -> None:
    """Confirm wallet removal."""
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        await callback.message.edit_text(
            get_text("confirm_remove_wallet", user.language, name=wallet.nickname),
            reply_markup=get_confirm_remove_keyboard(user.language, wallet_id),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:confirm_remove:"))
async def callback_wallet_confirm_remove(callback: CallbackQuery) -> None:
    """Actually remove wallet."""
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        wallet_repo = WalletRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get and delete wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        wallet_name = wallet.nickname
        await wallet_repo.delete(wallet)
        
        await callback.message.edit_text(
            get_text("wallet_removed", user.language, name=wallet_name),
            reply_markup=get_back_to_menu_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


# ==================== WALLET SETTINGS ====================

@router.callback_query(F.data.startswith("wallet:settings:"))
async def callback_wallet_settings(callback: CallbackQuery) -> None:
    """Show wallet settings menu."""
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        # Format min amount text
        if wallet.min_trade_amount > 0:
            min_amount_text = f"${wallet.min_trade_amount:,.0f}+"
        else:
            min_amount_text = get_text("min_amount_all", user.language)
        
        # Status text
        status_text = get_text("wallet_paused" if wallet.is_paused else "wallet_active", user.language)
        
        await callback.message.edit_text(
            get_text(
                "wallet_settings_menu",
                user.language,
                name=wallet.nickname,
                address=wallet.wallet_address,
                status=status_text,
                min_amount=min_amount_text,
            ),
            reply_markup=get_wallet_settings_keyboard(user.language, wallet_id, wallet.is_paused),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:pause:"))
async def callback_wallet_pause(callback: CallbackQuery) -> None:
    """Pause notifications for wallet."""
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get and update wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        wallet.is_paused = True
        await session.commit()
        
        await callback.message.edit_text(
            get_text("wallet_pause_success", user.language, name=wallet.nickname),
            reply_markup=get_wallet_settings_keyboard(user.language, wallet_id, True),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:resume:"))
async def callback_wallet_resume(callback: CallbackQuery) -> None:
    """Resume notifications for wallet."""
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get and update wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        wallet.is_paused = False
        await session.commit()
        
        await callback.message.edit_text(
            get_text("wallet_resume_success", user.language, name=wallet.nickname),
            reply_markup=get_wallet_settings_keyboard(user.language, wallet_id, False),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:min_amount:"))
async def callback_wallet_min_amount(callback: CallbackQuery) -> None:
    """Show min amount selection."""
    wallet_id = int(callback.data.split(":")[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        await callback.message.edit_text(
            get_text("select_min_amount", user.language),
            reply_markup=get_min_amount_keyboard(user.language, wallet_id),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("set_min:"))
async def callback_set_min_amount(callback: CallbackQuery) -> None:
    """Set minimum trade amount for wallet."""
    parts = callback.data.split(":")
    amount = float(parts[1])
    wallet_id = int(parts[2])
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        # Get and update wallet
        from sqlalchemy import select
        from models import TrackedWallet
        
        stmt = select(TrackedWallet).where(
            TrackedWallet.id == wallet_id,
            TrackedWallet.user_id == user.id
        )
        result = await session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            await callback.answer("Wallet not found")
            return
        
        wallet.min_trade_amount = amount
        await session.commit()
        
        # Format amount text
        if amount > 0:
            amount_text = f"${amount:,.0f}+"
        else:
            amount_text = get_text("min_amount_all", user.language)
        
        await callback.message.edit_text(
            get_text("min_amount_updated", user.language, amount=amount_text, name=wallet.nickname),
            reply_markup=get_wallet_settings_keyboard(user.language, wallet_id, wallet.is_paused),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


# ==================== SETTINGS ====================

@router.callback_query(F.data == "menu:settings")
async def callback_settings(callback: CallbackQuery) -> None:
    """Show settings menu."""
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        await callback.message.edit_text(
            get_text("settings_menu", user.language),
            reply_markup=get_settings_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data == "settings:language")
async def callback_settings_language(callback: CallbackQuery) -> None:
    """Show language selection in settings."""
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        await callback.message.edit_text(
            get_text("select_language", user.language),
            reply_markup=get_settings_language_keyboard(user.language),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("setlang:"))
async def callback_set_language(callback: CallbackQuery) -> None:
    """Change language in settings."""
    lang_code = callback.data.split(":")[1]
    
    if lang_code not in [l.value for l in Language]:
        await callback.answer("Invalid language")
        return
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        await user_repo.update_language(callback.from_user.id, lang_code)
        
        await callback.message.edit_text(
            get_text("language_changed", lang_code),
            reply_markup=get_settings_keyboard(lang_code),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


def setup_handlers(dp) -> None:
    """Register handlers with dispatcher."""
    dp.include_router(router)
    logger.info("Handlers registered")
