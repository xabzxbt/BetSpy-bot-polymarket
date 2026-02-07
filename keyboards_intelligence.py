"""
Keyboard builders for BetSpy Market Intelligence features.
"""

from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from market_intelligence import MarketStats, Category, TimeFrame


def get_category_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Category selection keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="⚽ Спорт", callback_data="intel:cat:sports"),
        InlineKeyboardButton(text="₿ Крипто", callback_data="intel:cat:crypto"),
    )
    builder.row(
        InlineKeyboardButton(text="🎮 Кіберспорт", callback_data="intel:cat:esports"),
        InlineKeyboardButton(text="🔥 Trending", callback_data="intel:cat:trending"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Всі категорії", callback_data="intel:cat:all"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Головне меню", callback_data="menu:main"),
    )
    
    return builder.as_markup()


def get_timeframe_keyboard(lang: str, category: str) -> InlineKeyboardMarkup:
    """Timeframe selection keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🕐 Сьогодні", 
            callback_data=f"intel:time:{category}:today"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📅 2 дні", 
            callback_data=f"intel:time:{category}:2days"
        ),
        InlineKeyboardButton(
            text="📅 3 дні", 
            callback_data=f"intel:time:{category}:3days"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📆 Тиждень", 
            callback_data=f"intel:time:{category}:week"
        ),
        InlineKeyboardButton(
            text="📆 Місяць", 
            callback_data=f"intel:time:{category}:month"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад", 
            callback_data="intel:back_categories"
        ),
    )
    
    return builder.as_markup()


def get_trending_keyboard(
    lang: str, 
    markets: List[MarketStats],
    category: str,
    timeframe: str,
) -> InlineKeyboardMarkup:
    """Keyboard with market selection buttons."""
    builder = InlineKeyboardBuilder()
    
    # Market buttons (up to 10)
    row_buttons = []
    for i, market in enumerate(markets[:10], 1):
        btn = InlineKeyboardButton(
            text=f"{i}",
            callback_data=f"intel:detail:{market.condition_id}"
        )
        row_buttons.append(btn)
        
        # 5 buttons per row
        if len(row_buttons) == 5:
            builder.row(*row_buttons)
            row_buttons = []
    
    # Add remaining buttons
    if row_buttons:
        builder.row(*row_buttons)
    
    # Refresh button
    builder.row(
        InlineKeyboardButton(
            text="🔄 Оновити",
            callback_data=f"intel:time:{category}:{timeframe}"
        ),
    )
    
    # Navigation
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Категорії",
            callback_data="intel:back_categories"
        ),
        InlineKeyboardButton(
            text="🏠 Меню",
            callback_data="menu:main"
        ),
    )
    
    return builder.as_markup()


def get_signals_keyboard(
    lang: str,
    markets: List[MarketStats],
) -> InlineKeyboardMarkup:
    """Keyboard for signals view."""
    builder = InlineKeyboardBuilder()
    
    # Market buttons
    row_buttons = []
    for i, market in enumerate(markets[:10], 1):
        btn = InlineKeyboardButton(
            text=f"{i}",
            callback_data=f"intel:detail:{market.condition_id}"
        )
        row_buttons.append(btn)
        
        if len(row_buttons) == 5:
            builder.row(*row_buttons)
            row_buttons = []
    
    if row_buttons:
        builder.row(*row_buttons)
    
    # Refresh
    builder.row(
        InlineKeyboardButton(
            text="🔄 Оновити",
            callback_data="intel:refresh_signals"
        ),
    )
    
    # Navigation
    builder.row(
        InlineKeyboardButton(
            text="🔥 Trending",
            callback_data="intel:back_categories"
        ),
        InlineKeyboardButton(
            text="🏠 Меню",
            callback_data="menu:main"
        ),
    )
    
    return builder.as_markup()


def get_market_detail_keyboard(
    lang: str,
    market: MarketStats,
) -> InlineKeyboardMarkup:
    """Keyboard for market detail view."""
    builder = InlineKeyboardBuilder()
    
    # Open market link
    builder.row(
        InlineKeyboardButton(
            text="💰 Відкрити на Polymarket",
            url=market.market_url
        ),
    )
    
    # Set alert (future feature)
    # builder.row(
    #     InlineKeyboardButton(
    #         text="🔔 Сповіщати про зміни",
    #         callback_data=f"intel:alert:{market.condition_id}"
    #     ),
    # )
    
    # Back to list
    builder.row(
        InlineKeyboardButton(
            text="⬅️ До списку",
            callback_data="intel:back_categories"
        ),
        InlineKeyboardButton(
            text="🏠 Меню",
            callback_data="menu:main"
        ),
    )
    
    return builder.as_markup()
