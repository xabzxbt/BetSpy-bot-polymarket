"""
Reply keyboard handler — processes persistent bottom menu buttons.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from loguru import logger

from database import db
from repository import UserRepository, WalletRepository
from keyboards import get_wallet_list_keyboard, get_cancel_keyboard
from config import get_settings
from handlers import AddWalletStates


router = Router(name="reply_nav")


@router.message(F.text == "📋 My Traders")
async def reply_my_traders(message: Message) -> None:
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
                "Use /subscribe or the button below to add a trader.",
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer(
                f"📋 <b>Your Subscriptions</b>\n\n"
                f"Tracking {len(wallets)}/{settings.max_wallets_per_user} traders:",
                reply_markup=get_wallet_list_keyboard(wallets),
                parse_mode=ParseMode.HTML,
            )


@router.message(F.text == "➕ Subscribe")
async def reply_subscribe(message: Message, state: FSMContext) -> None:
    """Start subscription flow from button."""
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


def setup_reply_handlers(dp) -> None:
    dp.include_router(router)
    logger.info("Reply navigation handlers registered")
