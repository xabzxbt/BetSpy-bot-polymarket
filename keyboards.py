"""
BetSpy Keyboard Factory (v3)

Two keyboard types:
1. REPLY keyboard (persistent, always visible under input):
   - Home, Signals, Analyze, Wallets, Settings
   - Shown after /start, stays until explicitly changed

2. INLINE keyboard (attached to messages):
   - Context-specific buttons (market details, wallet actions, etc.)
   - Disappears when message scrolls up — that's OK, persistent nav below

This separation ensures users always have navigation access.
"""

from typing import List, Optional
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from i18n import get_text


# =====================================================================
# REPLY KEYBOARDS (persistent, under input field)
# =====================================================================

def get_persistent_menu(lang: str) -> ReplyKeyboardMarkup:
    """Main persistent reply keyboard — always visible.
    
    Layout:
    [ 📊 Signals ] [ 🔥 Hot ]  [ 🔗 Analyze ]
    [ 📋 Wallets ] [ ⭐ Watchlist ]
    [ ⚙️ Settings ] [ ❓ Help ]
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=get_text("reply.signals", lang)),
        KeyboardButton(text=get_text("reply.hot", lang)),
        KeyboardButton(text=get_text("reply.analyze", lang)),
    )
    builder.row(
        KeyboardButton(text=get_text("reply.wallets", lang)),
        KeyboardButton(text=get_text("reply.watchlist", lang)),
    )
    builder.row(
        KeyboardButton(text=get_text("reply.settings", lang)),
        KeyboardButton(text=get_text("reply.help", lang)),
    )
    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


# =====================================================================
# INLINE KEYBOARDS (attached to specific messages)
# =====================================================================

def get_language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"))
    builder.row(InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang:uk"))
    builder.row(InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"))
    return builder.as_markup()


def get_main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Inline quick-action menu (shown in welcome message)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=get_text("btn.add_wallet", lang), callback_data="menu:add_wallet"),
        InlineKeyboardButton(text=get_text("btn.my_wallets", lang), callback_data="menu:my_wallets"),
    )
    builder.row(
        InlineKeyboardButton(text=get_text("btn.trending", lang), callback_data="intel:back_categories"),
    )
    builder.row(
        InlineKeyboardButton(text=get_text("btn.analyze_link", lang), callback_data="menu:analyze_link"),
    )
    builder.row(
        InlineKeyboardButton(text=get_text("btn.hot_today", lang), callback_data="intel:hot"),
        InlineKeyboardButton(text=get_text("btn.watchlist", lang), callback_data="menu:watchlist"),
    )
    builder.row(
        InlineKeyboardButton(text=get_text("btn.settings", lang), callback_data="menu:settings"),
        InlineKeyboardButton(text=get_text("btn.help", lang), callback_data="menu:help"),
    )
    return builder.as_markup()


def get_cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("btn.cancel", lang), callback_data="action:cancel",
    ))
    return builder.as_markup()


def get_back_to_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("btn.back_to_menu", lang), callback_data="menu:main",
    ))
    return builder.as_markup()


def get_nickname_keyboard(
    lang: str, wallet_address: str, detected_name: Optional[str] = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if detected_name:
        builder.row(InlineKeyboardButton(
            text=get_text("btn.use_detected_name", lang, name=detected_name),
            callback_data=f"nickname:use:{detected_name[:50]}",
        ))
    short = f"{wallet_address[:6]}...{wallet_address[-4:]}"
    builder.row(InlineKeyboardButton(
        text=get_text("btn.use_address", lang),
        callback_data=f"nickname:addr:{short}",
    ))
    builder.row(InlineKeyboardButton(
        text=get_text("btn.cancel", lang), callback_data="action:cancel",
    ))
    return builder.as_markup()


def get_wallet_list_keyboard(lang: str, wallets) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for w in wallets:
        icon = "⏸️" if w.is_paused else "👤"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {w.nickname}",
            callback_data=f"wallet:view:{w.id}",
        ))
    builder.row(InlineKeyboardButton(
        text=get_text("btn.add_wallet", lang), callback_data="menu:add_wallet",
    ))
    builder.row(InlineKeyboardButton(
        text=get_text("btn.back_to_menu", lang), callback_data="menu:main",
    ))
    return builder.as_markup()


def get_wallet_details_keyboard(
    lang: str, wallet_id: int, wallet_address: str = "",
) -> InlineKeyboardMarkup:
    from config import get_settings
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=get_text("btn.view_positions", lang), callback_data=f"wallet:positions:{wallet_id}"),
        InlineKeyboardButton(text=get_text("btn.recent_trades", lang), callback_data=f"wallet:trades:{wallet_id}"),
    )
    builder.row(InlineKeyboardButton(
        text=get_text("btn.view_detailed_stats", lang), callback_data=f"wallet:stats_range:{wallet_id}",
    ))
    if wallet_address:
        settings = get_settings()
        url = f"https://polymarket.com/profile/{wallet_address}"
        if settings.polymarket_referral_code:
            url += f"?via={settings.polymarket_referral_code}"
        builder.row(InlineKeyboardButton(text=get_text("btn.view_profile", lang), url=url))
    builder.row(
        InlineKeyboardButton(text=get_text("btn.wallet_settings", lang), callback_data=f"wallet:settings:{wallet_id}"),
        InlineKeyboardButton(text=get_text("btn.remove_wallet", lang), callback_data=f"wallet:remove:{wallet_id}"),
    )
    builder.row(InlineKeyboardButton(text=get_text("btn.back", lang), callback_data="menu:my_wallets"))
    return builder.as_markup()


def get_wallet_settings_keyboard(lang: str, wallet_id: int, is_paused: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_paused:
        builder.row(InlineKeyboardButton(text=get_text("btn.resume_wallet", lang), callback_data=f"wallet:resume:{wallet_id}"))
    else:
        builder.row(InlineKeyboardButton(text=get_text("btn.pause_wallet", lang), callback_data=f"wallet:pause:{wallet_id}"))
    builder.row(InlineKeyboardButton(text=get_text("btn.set_min_amount", lang), callback_data=f"wallet:min_amount:{wallet_id}"))
    builder.row(InlineKeyboardButton(text=get_text("btn.back", lang), callback_data=f"wallet:view:{wallet_id}"))
    return builder.as_markup()


def get_min_amount_keyboard(lang: str, wallet_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn.min_amount_0", lang), callback_data=f"set_min:0:{wallet_id}"))
    builder.row(
        InlineKeyboardButton(text=get_text("btn.min_amount_100", lang), callback_data=f"set_min:100:{wallet_id}"),
        InlineKeyboardButton(text=get_text("btn.min_amount_500", lang), callback_data=f"set_min:500:{wallet_id}"),
    )
    builder.row(
        InlineKeyboardButton(text=get_text("btn.min_amount_1000", lang), callback_data=f"set_min:1000:{wallet_id}"),
        InlineKeyboardButton(text=get_text("btn.min_amount_5000", lang), callback_data=f"set_min:5000:{wallet_id}"),
    )
    builder.row(InlineKeyboardButton(text=get_text("btn.min_amount_10000", lang), callback_data=f"set_min:10000:{wallet_id}"))
    builder.row(InlineKeyboardButton(text=get_text("btn.back", lang), callback_data=f"wallet:settings:{wallet_id}"))
    return builder.as_markup()


def get_confirm_remove_keyboard(lang: str, wallet_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn.confirm_remove", lang), callback_data=f"wallet:confirm_remove:{wallet_id}"))
    builder.row(InlineKeyboardButton(text=get_text("btn.cancel", lang), callback_data=f"wallet:view:{wallet_id}"))
    return builder.as_markup()


def get_wallet_back_keyboard(lang: str, wallet_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn.back", lang), callback_data=f"wallet:view:{wallet_id}"))
    return builder.as_markup()


def get_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn.change_language", lang), callback_data="settings:language"))
    builder.row(InlineKeyboardButton(text=get_text("btn.back_to_menu", lang), callback_data="menu:main"))
    return builder.as_markup()


def get_settings_language_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang:en"))
    builder.row(InlineKeyboardButton(text="🇺🇦 Українська", callback_data="setlang:uk"))
    builder.row(InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang:ru"))
    builder.row(InlineKeyboardButton(text=get_text("btn.back", lang), callback_data="menu:settings"))
    return builder.as_markup()


def get_stats_range_keyboard(lang: str, wallet_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn.stats_1_day", lang), callback_data=f"stats_range:1:{wallet_id}"))
    builder.row(InlineKeyboardButton(text=get_text("btn.stats_1_week", lang), callback_data=f"stats_range:7:{wallet_id}"))
    builder.row(InlineKeyboardButton(text=get_text("btn.stats_1_month", lang), callback_data=f"stats_range:30:{wallet_id}"))
    builder.row(InlineKeyboardButton(text=get_text("btn.stats_all_time", lang), callback_data=f"stats_range:365:{wallet_id}"))
    builder.row(InlineKeyboardButton(text=get_text("btn.back", lang), callback_data=f"wallet:view:{wallet_id}"))
    return builder.as_markup()
    