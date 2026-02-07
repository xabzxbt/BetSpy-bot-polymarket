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
        # Show pause icon if paused
        status_icon = "⏸️" if wallet.is_paused else "👤"
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon} {wallet.nickname}",
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
    wallet_id: int,
    wallet_address: str = ""
) -> InlineKeyboardMarkup:
    """Keyboard for wallet details view."""
    builder = InlineKeyboardBuilder()
    
    # Row 1: View data
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_view_positions", lang),
            callback_data=f"wallet:positions:{wallet_id}"
        ),
        InlineKeyboardButton(
            text=get_text("btn_recent_trades", lang),
            callback_data=f"wallet:trades:{wallet_id}"
        )
    )
    
    # Row 2: Stats
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_view_detailed_stats", lang),
            callback_data=f"wallet:stats_range:{wallet_id}"
        )
    )
    
    # Row 3: Profile link (if address provided)
    if wallet_address:
        builder.row(
            InlineKeyboardButton(
                text=get_text("btn_view_profile", lang),
                url=get_profile_url(wallet_address)
            )
        )
    
    # Row 4: Settings & Remove
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_wallet_settings", lang),
            callback_data=f"wallet:settings:{wallet_id}"
        ),
        InlineKeyboardButton(
            text=get_text("btn_remove_wallet", lang),
            callback_data=f"wallet:remove:{wallet_id}"
        )
    )
    
    # Row 5: Back
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="menu:my_wallets"
        )
    )
    
    return builder.as_markup()


def get_wallet_settings_keyboard(
    lang: str,
    wallet_id: int,
    is_paused: bool
) -> InlineKeyboardMarkup:
    """Keyboard for wallet settings."""
    builder = InlineKeyboardBuilder()
    
    # Pause/Resume button
    if is_paused:
        builder.row(
            InlineKeyboardButton(
                text=get_text("btn_resume_wallet", lang),
                callback_data=f"wallet:resume:{wallet_id}"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=get_text("btn_pause_wallet", lang),
                callback_data=f"wallet:pause:{wallet_id}"
            )
        )
    
    # Min amount button
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_set_min_amount", lang),
            callback_data=f"wallet:min_amount:{wallet_id}"
        )
    )
    
    # Back button
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data=f"wallet:view:{wallet_id}"
        )
    )
    
    return builder.as_markup()


def get_min_amount_keyboard(
    lang: str,
    wallet_id: int
) -> InlineKeyboardMarkup:
    """Keyboard for selecting minimum trade amount."""
    builder = InlineKeyboardBuilder()
    
    # Amount options
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_min_amount_0", lang),
            callback_data=f"set_min:0:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_min_amount_100", lang),
            callback_data=f"set_min:100:{wallet_id}"
        ),
        InlineKeyboardButton(
            text=get_text("btn_min_amount_500", lang),
            callback_data=f"set_min:500:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_min_amount_1000", lang),
            callback_data=f"set_min:1000:{wallet_id}"
        ),
        InlineKeyboardButton(
            text=get_text("btn_min_amount_5000", lang),
            callback_data=f"set_min:5000:{wallet_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_min_amount_10000", lang),
            callback_data=f"set_min:10000:{wallet_id}"
        )
    )
    
    # Back button
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data=f"wallet:settings:{wallet_id}"
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


def get_profile_url(wallet_address: str) -> str:
    """Generate Polymarket profile URL with referral code."""
    from config import get_settings
    settings = get_settings()
    
    base_url = f"https://polymarket.com/profile/{wallet_address}"
    
    if settings.polymarket_referral_code:
        return f"{base_url}?via={settings.polymarket_referral_code}"
    
    return base_url
