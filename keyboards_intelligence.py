"""
Keyboard builders for BetSpy Market Intelligence features.
"""

from typing import List, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from market_intelligence import MarketStats, Category, TimeFrame
from translations import get_text


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
        InlineKeyboardButton(text=f"🏛️ {get_text('cat_politics', lang)}", callback_data="intel:cat:politics"),
        InlineKeyboardButton(text=f"⚽ {get_text('cat_sports', lang)}", callback_data="intel:cat:sports"),
    )
    # Row 2: Pop Culture, Business
    builder.row(
        InlineKeyboardButton(text=f"🎬 {get_text('cat_pop_culture', lang)}", callback_data="intel:cat:pop-culture"),
        InlineKeyboardButton(text=f"💼 {get_text('cat_business', lang)}", callback_data="intel:cat:business"),
    )
    # Row 3: Crypto, Science
    builder.row(
        InlineKeyboardButton(text=f"₿ {get_text('cat_crypto', lang)}", callback_data="intel:cat:crypto"),
        InlineKeyboardButton(text=f"🔬 {get_text('cat_science', lang)}", callback_data="intel:cat:science"),
    )
    # Row 4: Gaming, Entertainment
    builder.row(
        InlineKeyboardButton(text=f"🎮 {get_text('cat_gaming', lang)}", callback_data="intel:cat:gaming"),
        InlineKeyboardButton(text=f"🎭 {get_text('cat_entertainment', lang)}", callback_data="intel:cat:entertainment"),
    )
    # Row 5: World, Tech
    builder.row(
        InlineKeyboardButton(text=f"🌍 {get_text('cat_world', lang)}", callback_data="intel:cat:world"),
        InlineKeyboardButton(text=f"💻 {get_text('cat_tech', lang)}", callback_data="intel:cat:tech"),
    )
    # Row 6: All categories
    builder.row(
        InlineKeyboardButton(text=f"📊 {get_text('cat_all', lang)}", callback_data="intel:cat:all"),
    )
    # Row 7: Back to main menu
    builder.row(
        InlineKeyboardButton(text=f"🏠 {get_text('btn_back_to_menu', lang)}", callback_data="menu:main"),
    )
    
    return builder.as_markup()


def get_trending_keyboard(
    lang: str, 
    markets: List[MarketStats],
    category: str,
    timeframe: str,
    page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """Keyboard with market selection buttons and pagination."""
    builder = InlineKeyboardBuilder()
    
    # Cache markets and get short keys
    keys = cache_markets(markets)  # Cache all passed markets (should only be limits for this page)
    
    # Market buttons (up to limit)
    row_buttons = []
    start_index = (page - 1) * 10 + 1  # Global index for labels
    
    for i, key in enumerate(keys):
        btn_text = f"{start_index + i}"
        btn = InlineKeyboardButton(
            text=btn_text,
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
    
    # Pagination Navigation
    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text=get_text("btn_prev_page", lang), 
                callback_data=f"intel:p:{category}:{timeframe}:{page-1}"
            )
        )
    
    # Page indicator
    nav_row.append(
        InlineKeyboardButton(
            text=f"📄 {page}/{total_pages}",
            callback_data="noop"  # Non-clickable
        )
    )
        
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text=get_text("btn_next_page", lang), 
                callback_data=f"intel:p:{category}:{timeframe}:{page+1}"
            )
        )
    
    builder.row(*nav_row)
    
    # Refresh & Back
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_refresh", lang),
            callback_data=f"intel:time:{category}:{timeframe}:{page}"  # Include page to refresh current view
        ),
    )
    
    # Navigation
    builder.row(
        InlineKeyboardButton(
            text=f"🔙 {get_text('btn_trending', lang)}",
            callback_data="intel:back_categories"
        ),
        InlineKeyboardButton(
            text=f"🏠 {get_text('btn_back_to_menu', lang)}",
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
            text=get_text("intel_link_text", lang), # NEW key needed
            url=market.market_url
        ),
    )
    
    # Back to list
    builder.row(
        InlineKeyboardButton(
            text=f"⬅️ {get_text('btn_trending', lang)}",
            callback_data="intel:back_categories"
        ),
        InlineKeyboardButton(
            text=f"🏠 {get_text('btn_back_to_menu', lang)}",
            callback_data="menu:main"
        ),
    )
    
    return builder.as_markup()
