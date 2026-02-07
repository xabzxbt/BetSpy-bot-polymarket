"""
Keyboard builders for BetSpy Market Intelligence features.
"""

from typing import List, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from market_intelligence import MarketStats, Category, TimeFrame


# Cache for markets to use short indices instead of long condition_ids
# Key: short index (string), Value: MarketStats
_market_cache: Dict[str, MarketStats] = {}
_cache_counter = 0


def cache_markets(markets: List[MarketStats]) -> List[str]:
    """
    Cache markets and return list of short keys.
    This avoids BUTTON_DATA_INVALID error from long condition_ids.
    """
    global _cache_counter, _market_cache
    
    keys = []
    for market in markets:
        _cache_counter += 1
        # Use short numeric key (max 8 chars)
        key = str(_cache_counter % 100000000)
        _market_cache[key] = market
        keys.append(key)
    
    # Clean old entries if cache gets too large
    if len(_market_cache) > 1000:
        # Keep only the last 500 entries
        items = list(_market_cache.items())
        _market_cache = dict(items[-500:])
    
    return keys


def get_cached_market(key: str) -> MarketStats:
    """Get market from cache by short key."""
    return _market_cache.get(key)


def get_category_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Category selection keyboard with all Polymarket categories."""
    builder = InlineKeyboardBuilder()
    
    # Row 1: Politics, Sports
    builder.row(
        InlineKeyboardButton(text="🏛️ Політика", callback_data="intel:cat:politics"),
        InlineKeyboardButton(text="⚽ Спорт", callback_data="intel:cat:sports"),
    )
    # Row 2: Pop Culture, Business
    builder.row(
        InlineKeyboardButton(text="🎬 Поп-культура", callback_data="intel:cat:pop-culture"),
        InlineKeyboardButton(text="💼 Бізнес", callback_data="intel:cat:business"),
    )
    # Row 3: Crypto, Science
    builder.row(
        InlineKeyboardButton(text="₿ Крипто", callback_data="intel:cat:crypto"),
        InlineKeyboardButton(text="🔬 Наука", callback_data="intel:cat:science"),
    )
    # Row 4: Gaming, Entertainment
    builder.row(
        InlineKeyboardButton(text="🎮 Ігри", callback_data="intel:cat:gaming"),
        InlineKeyboardButton(text="🎭 Розваги", callback_data="intel:cat:entertainment"),
    )
    # Row 5: World, Tech
    builder.row(
        InlineKeyboardButton(text="🌍 Світ", callback_data="intel:cat:world"),
        InlineKeyboardButton(text="💻 Технології", callback_data="intel:cat:tech"),
    )
    # Row 6: All categories
    builder.row(
        InlineKeyboardButton(text="📊 Всі категорії", callback_data="intel:cat:all"),
    )
    # Row 7: Back to main menu
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
    
    # Cache markets and get short keys
    keys = cache_markets(markets[:10])
    
    # Market buttons (up to 10)
    row_buttons = []
    for i, key in enumerate(keys, 1):
        btn = InlineKeyboardButton(
            text=f"{i}",
            callback_data=f"intel:m:{key}"  # Short format: intel:m:12345
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
    
    # Cache markets and get short keys
    keys = cache_markets(markets[:10])
    
    # Market buttons
    row_buttons = []
    for i, key in enumerate(keys, 1):
        btn = InlineKeyboardButton(
            text=f"{i}",
            callback_data=f"intel:m:{key}"  # Short format
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
            text="📊 Категорії",
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
