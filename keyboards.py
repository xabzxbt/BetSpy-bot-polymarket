"""
Keyboard builders for the Polymarket Whale Tracker bot.
"""

from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from translations import get_text
from models import TrackedWallet


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")
    )
    builder.row(
        InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang:uk")
    )
    builder.row(
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")
    )
    return builder.as_markup()


def get_main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_add_wallet", lang),
            callback_data="menu:add_wallet"
        ),
        InlineKeyboardButton(
            text=get_text("btn_my_wallets", lang),
            callback_data="menu:my_wallets"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_settings", lang),
            callback_data="menu:settings"
        ),
        InlineKeyboardButton(
            text=get_text("btn_help", lang),
            callback_data="menu:help"
        )
    )
    return builder.as_markup()


def get_cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Cancel action keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_cancel", lang),
            callback_data="action:cancel"
        )
    )
    return builder.as_markup()


def get_back_to_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Back to main menu keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back_to_menu", lang),
            callback_data="menu:main"
        )
    )
    return builder.as_markup()


def get_nickname_keyboard(
    lang: str,
    wallet_address: str,
    detected_name: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Keyboard for nickname selection when adding wallet."""
    builder = InlineKeyboardBuilder()
    
    if detected_name:
        builder.row(
            InlineKeyboardButton(
                text=get_text("btn_use_detected_name", lang, name=detected_name),
                callback_data=f"nickname:use:{detected_name[:50]}"
            )
        )
    
    # Use shortened address as name
    short_addr = f"{wallet_address[:6]}...{wallet_address[-4:]}"
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_use_address", lang),
            callback_data=f"nickname:addr:{short_addr}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_cancel", lang),
            callback_data="action:cancel"
        )
    )
    
    return builder.as_markup()


def get_wallet_list_keyboard(
    lang: str,
    wallets: List[TrackedWallet]
) -> InlineKeyboardMarkup:
    """Keyboard with list of wallets."""
    builder = InlineKeyboardBuilder()
    
    for wallet in wallets:
        short_addr = f"{wallet.wallet_address[:6]}...{wallet.wallet_address[-4:]}"
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {wallet.nickname}",
                callback_data=f"wallet:view:{wallet.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_add_wallet", lang),
            callback_data="menu:add_wallet"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back_to_menu", lang),
            callback_data="menu:main"
        )
    )
    
    return builder.as_markup()


def get_wallet_details_keyboard(
    lang: str,
    wallet_id: int
) -> InlineKeyboardMarkup:
    """Keyboard for wallet details view."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_view_positions", lang),
            callback_data=f"wallet:positions:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_view_detailed_stats", lang),
            callback_data=f"wallet:stats_range:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_recent_trades", lang),
            callback_data=f"wallet:trades:{wallet_id}"
        )
    )
    # Debug button - only show for admin/debug purposes
    # Uncomment the next line if you want to enable debug mode
    # builder.row(InlineKeyboardButton(text=get_text("btn_debug_wallet", lang), callback_data=f"wallet:debug:{wallet_id}"))
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_remove_wallet", lang),
            callback_data=f"wallet:remove:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="menu:my_wallets"
        )
    )
    
    return builder.as_markup()


def get_confirm_remove_keyboard(
    lang: str,
    wallet_id: int
) -> InlineKeyboardMarkup:
    """Confirmation keyboard for wallet removal."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_confirm_remove", lang),
            callback_data=f"wallet:confirm_remove:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_cancel", lang),
            callback_data=f"wallet:view:{wallet_id}"
        )
    )
    
    return builder.as_markup()


def get_wallet_back_keyboard(
    lang: str,
    wallet_id: int
) -> InlineKeyboardMarkup:
    """Back button to wallet details."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data=f"wallet:view:{wallet_id}"
        )
    )
    return builder.as_markup()


def get_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Settings menu keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_change_language", lang),
            callback_data="settings:language"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back_to_menu", lang),
            callback_data="menu:main"
        )
    )
    
    return builder.as_markup()


def get_settings_language_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Language selection in settings."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang:en")
    )
    builder.row(
        InlineKeyboardButton(text="🇺🇦 Українська", callback_data="setlang:uk")
    )
    builder.row(
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang:ru")
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="menu:settings"
        )
    )
    
    return builder.as_markup()



def get_stats_range_keyboard(lang: str, wallet_id: int) -> InlineKeyboardMarkup:
    """Keyboard for selecting Statistics date range."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_stats_1_day", lang),
            callback_data=f"stats_range:1:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_stats_1_week", lang),
            callback_data=f"stats_range:7:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_stats_1_month", lang),
            callback_data=f"stats_range:30:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_stats_all_time", lang),
            callback_data=f"stats_range:365:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data=f"wallet:view:{wallet_id}"
        )
    )
    
    return builder.as_markup()
