"""
BetSpy Keyboard Factory
"""

from typing import Optional
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,  # <-- ДОДАТИ ЦІ ІМПОРТИ
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder  # <-- ДОДАТИ ReplyKeyboardBuilder

from config import get_settings


# =====================================================================
# REPLY KEYBOARD (persistent buttons at bottom)
# =====================================================================

def get_persistent_menu() -> ReplyKeyboardMarkup:
    """Main persistent reply keyboard - always visible."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📋 My Traders"),
    )
    builder.row(
        KeyboardButton(text="➕ Subscribe"),
    )
    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


# =====================================================================
# INLINE KEYBOARDS (for wallet subscriptions)
# =====================================================================

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel button for operations."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="❌ Cancel", callback_data="action:cancel",
    ))
    return builder.as_markup()


def get_nickname_keyboard(
    wallet_address: str, detected_name: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Keyboard for choosing wallet nickname."""
    builder = InlineKeyboardBuilder()
    if detected_name:
        builder.row(InlineKeyboardButton(
            text=f"✅ Use: {detected_name}",
            callback_data=f"nickname:use:{detected_name[:50]}",
        ))
    short = f"{wallet_address[:6]}...{wallet_address[-4:]}"
    builder.row(InlineKeyboardButton(
        text=f"Use address: {short}",
        callback_data=f"nickname:addr:{short}",
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Cancel", callback_data="action:cancel",
    ))
    return builder.as_markup()


def get_wallet_list_keyboard(wallets) -> InlineKeyboardMarkup:
    """List all tracked wallets."""
    settings = get_settings()
    builder = InlineKeyboardBuilder()
    
    for w in wallets:
        icon = "⏸️" if w.is_paused else "👤"
        short_addr = f"{w.wallet_address[:6]}…{w.wallet_address[-4:]}"
        
        # Row: [wallet name + address] [🔗 profile link]
        profile_url = f"https://polymarket.com/profile/{w.wallet_address}"
        if settings.polymarket_referral_code:
            profile_url += f"?via={settings.polymarket_referral_code}"
        
        builder.row(
            InlineKeyboardButton(
                text=f"{icon} {w.nickname} ({short_addr})",
                callback_data=f"wallet:view:{w.id}",
            ),
            InlineKeyboardButton(
                text="🔗",
                url=profile_url,
            ),
        )
    
    return builder.as_markup()


def get_wallet_details_keyboard(
    wallet_id: int, wallet_address: str = "",
) -> InlineKeyboardMarkup:
    """Wallet details with actions."""
    builder = InlineKeyboardBuilder()
    
    # View profile link
    if wallet_address:
        settings = get_settings()
        url = f"https://polymarket.com/profile/{wallet_address}"
        if settings.polymarket_referral_code:
            url += f"?via={settings.polymarket_referral_code}"
        builder.row(InlineKeyboardButton(text="👤 View Profile", url=url))
    
    # Actions
    builder.row(
        InlineKeyboardButton(text="⚙️ Settings", callback_data=f"wallet:settings:{wallet_id}"),
        InlineKeyboardButton(text="🗑️ Unsubscribe", callback_data=f"wallet:remove:{wallet_id}"),
    )
    
    return builder.as_markup()


def get_wallet_settings_keyboard(wallet_id: int, is_paused: bool) -> InlineKeyboardMarkup:
    """Wallet notification settings."""
    builder = InlineKeyboardBuilder()
    
    if is_paused:
        builder.row(InlineKeyboardButton(
            text="▶️ Resume Notifications", 
            callback_data=f"wallet:resume:{wallet_id}"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="⏸️ Pause Notifications", 
            callback_data=f"wallet:pause:{wallet_id}"
        ))
    
    builder.row(InlineKeyboardButton(
        text="💰 Set Min Amount", 
        callback_data=f"wallet:min_amount:{wallet_id}"
    ))
    
    builder.row(InlineKeyboardButton(
        text="⬅️ Back", 
        callback_data=f"wallet:view:{wallet_id}"
    ))
    
    return builder.as_markup()


def get_min_amount_keyboard(wallet_id: int) -> InlineKeyboardMarkup:
    """Choose minimum trade amount filter."""
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="All trades ($0+)", 
        callback_data=f"set_min:0:{wallet_id}"
    ))
    
    builder.row(
        InlineKeyboardButton(text="$100+", callback_data=f"set_min:100:{wallet_id}"),
        InlineKeyboardButton(text="$500+", callback_data=f"set_min:500:{wallet_id}"),
    )
    
    builder.row(
        InlineKeyboardButton(text="$1,000+", callback_data=f"set_min:1000:{wallet_id}"),
        InlineKeyboardButton(text="$5,000+", callback_data=f"set_min:5000:{wallet_id}"),
    )
    
    builder.row(InlineKeyboardButton(
        text="$10,000+", 
        callback_data=f"set_min:10000:{wallet_id}"
    ))
    
    builder.row(InlineKeyboardButton(
        text="⬅️ Back", 
        callback_data=f"wallet:settings:{wallet_id}"
    ))
    
    return builder.as_markup()


def get_confirm_remove_keyboard(wallet_id: int) -> InlineKeyboardMarkup:
    """Confirm unsubscribe action."""
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="✅ Yes, Unsubscribe", 
        callback_data=f"wallet:confirm_remove:{wallet_id}"
    ))
    
    builder.row(InlineKeyboardButton(
        text="❌ Cancel", 
        callback_data=f"wallet:view:{wallet_id}"
    ))
    
    return builder.as_markup()


def get_wallet_back_keyboard(wallet_id: int) -> InlineKeyboardMarkup:
    """Simple back button."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⬅️ Back", 
        callback_data=f"wallet:view:{wallet_id}"
    ))
    return builder.as_markup()
