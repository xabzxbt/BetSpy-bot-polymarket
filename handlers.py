"""
Aiogram 3.x handlers for subscription management.
"""

import re

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
from keyboards import (
    get_cancel_keyboard,
    get_nickname_keyboard,
    get_wallet_list_keyboard,
    get_wallet_details_keyboard,
    get_confirm_remove_keyboard,
    get_wallet_settings_keyboard,
    get_min_amount_keyboard,
)
from config import get_settings


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


# ==================== COMMAND HANDLERS ====================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command."""
    await state.clear()
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        
        from keyboards import get_persistent_menu
        settings = get_settings()
        welcome_text = f"""👋 <b>Welcome to BetSpy Polymarket Bot!</b>

Track whale traders on Polymarket and get instant notifications about their trades.

<b>Commands:</b>
/subscribe - Subscribe to a trader
/my_traders - View your subscriptions

<b>Limit:</b> Up to {settings.max_wallets_per_user} traders per user

Use the buttons below for quick access 👇"""
        
        await message.answer(
            welcome_text,
            reply_markup=get_persistent_menu(),
            parse_mode=ParseMode.HTML,
        )



@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, state: FSMContext) -> None:
    """Start subscription flow."""
    async with db.session() as session:
        user_repo = UserRepository(session)
        wallet_repo = WalletRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        
        # Check wallet limit
        settings = get_settings()
        wallet_count = await wallet_repo.count_user_wallets(user.id)
        
        if wallet_count >= settings.max_wallets_per_user:
            await message.answer(
                f"❌ You've reached the limit of {settings.max_wallets_per_user} traders.\n\n"
                f"Remove one to add a new trader.",
                parse_mode=ParseMode.HTML,
            )
            return
        
        await state.set_state(AddWalletStates.waiting_for_address)
        
        await message.answer(
            "📝 <b>Subscribe to a Trader</b>\n\n"
            "Send me the Ethereum wallet address (0x...):",
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML,
        )


@router.message(Command("my_traders"))
async def cmd_my_traders(message: Message) -> None:
    """Show subscribed traders."""
    async with db.session() as session:
        user_repo = UserRepository(session)
        wallet_repo = WalletRepository(session)
        
        user = await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        
        wallets = await wallet_repo.get_user_wallets(user.id)
        settings = get_settings()
        
        if not wallets:
            await message.answer(
                "📭 <b>No Subscriptions</b>\n\n"
                "You're not tracking any traders yet.\n\n"
                "Use /subscribe to add a trader.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.answer(
                f"📋 <b>Your Subscriptions</b>\n\n"
                f"Tracking {len(wallets)}/{settings.max_wallets_per_user} traders:",
                reply_markup=get_wallet_list_keyboard(wallets),
                parse_mode=ParseMode.HTML,
            )


# ==================== ADD WALLET FLOW ====================

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
        
        # Validate address
        if not is_valid_eth_address(wallet_address):
            await message.answer(
                "❌ Invalid Ethereum address.\n\n"
                "Please send a valid address starting with 0x...",
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return
        
        # Check if already exists
        existing = await wallet_repo.get_by_user_and_address(user.id, wallet_address)
        if existing:
            await state.clear()
            await message.answer(
                "⚠️ You're already tracking this trader!",
                parse_mode=ParseMode.HTML,
            )
            return
        
        # Store address in state
        await state.update_data(wallet_address=wallet_address)
        await state.set_state(AddWalletStates.waiting_for_nickname)
        
        # Try to fetch profile
        loading_msg = await message.answer("🔍 Loading trader info...", parse_mode=ParseMode.HTML)
        
        detected_name = None
        try:
            profile = await api_client.get_profile(wallet_address)
            if profile and profile.display_name:
                detected_name = profile.display_name
        except Exception as e:
            logger.warning(f"Failed to fetch profile: {e}")
        
        await state.update_data(detected_name=detected_name)
        
        await loading_msg.edit_text(
            f"✏️ <b>Choose Nickname</b>\n\n"
            f"Address: <code>{wallet_address}</code>",
            reply_markup=get_nickname_keyboard(wallet_address, detected_name),
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
            f"✅ <b>Subscribed!</b>\n\n"
            f"👤 {nickname}\n"
            f"💳 <code>{wallet_address}</code>\n\n"
            f"You'll receive notifications about their trades.",
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
            f"✅ <b>Subscribed!</b>\n\n"
            f"👤 {nickname}\n"
            f"💳 <code>{wallet_address}</code>\n\n"
            f"You'll receive notifications about their trades.",
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(F.data == "action:cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel current action."""
    await state.clear()
    await callback.message.edit_text("❌ Cancelled.", parse_mode=ParseMode.HTML)
    await callback.answer()


# ==================== WALLET DETAILS ====================

@router.callback_query(F.data.startswith("wallet:view:"))
async def callback_wallet_view(callback: CallbackQuery) -> None:
    """View wallet details."""
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
        
        date_str = wallet.created_at.strftime("%d.%m.%Y")
        
        # Show pause status if paused
        status_text = ""
        if wallet.is_paused:
            status_text = "\n\n⏸️ <b>Notifications paused</b>"
        
        await callback.message.edit_text(
            f"👤 <b>{wallet.nickname}</b>\n\n"
            f"💳 Address: <code>{wallet.wallet_address}</code>\n"
            f"📅 Added: {date_str}" + status_text,
            reply_markup=get_wallet_details_keyboard(wallet_id, wallet.wallet_address),
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
            min_amount_text = "All trades ($0+)"
        
        # Status text
        status_text = "⏸️ Paused" if wallet.is_paused else "✅ Active"
        
        await callback.message.edit_text(
            f"⚙️ <b>Settings: {wallet.nickname}</b>\n\n"
            f"💳 <code>{wallet.wallet_address}</code>\n\n"
            f"<b>Status:</b> {status_text}\n"
            f"<b>Min Amount:</b> {min_amount_text}",
            reply_markup=get_wallet_settings_keyboard(wallet_id, wallet.is_paused),
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
            f"⏸️ Notifications paused for <b>{wallet.nickname}</b>",
            reply_markup=get_wallet_settings_keyboard(wallet_id, True),
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
            f"▶️ Notifications resumed for <b>{wallet.nickname}</b>",
            reply_markup=get_wallet_settings_keyboard(wallet_id, False),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:min_amount:"))
async def callback_wallet_min_amount(callback: CallbackQuery) -> None:
    """Show min amount selection."""
    wallet_id = int(callback.data.split(":")[2])
    
    await callback.message.edit_text(
        "💰 <b>Minimum Trade Amount</b>\n\n"
        "Select the minimum trade size for notifications:",
        reply_markup=get_min_amount_keyboard(wallet_id),
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
            amount_text = "All trades ($0+)"
        
        await callback.message.edit_text(
            f"✅ Min amount updated to <b>{amount_text}</b> for {wallet.nickname}",
            reply_markup=get_wallet_settings_keyboard(wallet_id, wallet.is_paused),
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


# ==================== REMOVE WALLET ====================

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
            f"🗑️ <b>Unsubscribe from {wallet.nickname}?</b>\n\n"
            f"You'll stop receiving notifications about their trades.",
            reply_markup=get_confirm_remove_keyboard(wallet_id),
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
            f"✅ Unsubscribed from <b>{wallet_name}</b>",
            parse_mode=ParseMode.HTML,
        )
    
    await callback.answer()


def setup_handlers(dp) -> None:
    """Register handlers with dispatcher."""
    dp.include_router(router)
    logger.info("Handlers registered")
