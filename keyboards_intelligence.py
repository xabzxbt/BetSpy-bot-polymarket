"""
Keyboard builders for BetSpy Market Intelligence (v2).

Changes:
- Market cache uses TTL (15 min) instead of unbounded growth
- Cache cleanup on every access
"""

import time
from typing import List, Dict, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from market_intelligence import MarketStats, Category, TimeFrame
from translations import get_text


# =====================================================================
# Market cache with TTL
# =====================================================================

_market_cache: Dict[str, Tuple[MarketStats, float]] = {}  # key → (market, expires_at)
_cache_counter = 0
_CACHE_TTL = 900  # 15 minutes


def _cleanup_cache() -> None:
    """Remove expired entries."""
    now = time.time()
    expired = [k for k, (_, exp) in _market_cache.items() if exp < now]
    for k in expired:
        del _market_cache[k]


def cache_markets(markets: List[MarketStats]) -> List[str]:
    """Cache markets with TTL. Returns short keys."""
    global _cache_counter
    _cleanup_cache()

    now = time.time()
    keys = []
    for market in markets:
        _cache_counter += 1
        key = str(_cache_counter % 100_000_000)
        _market_cache[key] = (market, now + _CACHE_TTL)
        keys.append(key)
    return keys


def get_cached_market(key: str) -> Optional[MarketStats]:
    """Get market from cache. Returns None if expired or missing."""
    _cleanup_cache()
    entry = _market_cache.get(key)
    if entry:
        return entry[0]
    return None


# =====================================================================
# Keyboards
# =====================================================================

def get_category_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Category selection keyboard."""
    builder = InlineKeyboardBuilder()

    rows = [
        [("🏛️", "cat_politics", "politics"), ("⚽", "cat_sports", "sports")],
        [("🎬", "cat_pop_culture", "pop-culture"), ("💼", "cat_business", "business")],
        [("₿", "cat_crypto", "crypto"), ("🔬", "cat_science", "science")],
        [("🎮", "cat_gaming", "gaming"), ("🎭", "cat_entertainment", "entertainment")],
        [("🌍", "cat_world", "world"), ("💻", "cat_tech", "tech")],
    ]

    for row in rows:
        buttons = [
            InlineKeyboardButton(
                text=f"{emoji} {get_text(text_key, lang)}",
                callback_data=f"intel:cat:{cat_val}",
            )
            for emoji, text_key, cat_val in row
        ]
        builder.row(*buttons)

    builder.row(
        InlineKeyboardButton(
            text=f"📊 {get_text('cat_all', lang)}",
            callback_data="intel:cat:all",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🏠 {get_text('btn_back_to_menu', lang)}",
            callback_data="menu:main",
        )
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
    """Market list with numbered buttons + pagination."""
    builder = InlineKeyboardBuilder()

    keys = cache_markets(markets)
    start_index = (page - 1) * 10 + 1

    # Market buttons (5 per row)
    row = []
    for i, key in enumerate(keys):
        row.append(
            InlineKeyboardButton(
                text=str(start_index + i),
                callback_data=f"intel:m:{key}",
            )
        )
        if len(row) == 5:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)

    # Pagination
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(
            text="◀️", callback_data=f"intel:p:{category}:{timeframe}:{page - 1}",
        ))
    nav.append(InlineKeyboardButton(
        text=f"📄 {page}/{total_pages}", callback_data="noop",
    ))
    if page < total_pages:
        nav.append(InlineKeyboardButton(
            text="▶️", callback_data=f"intel:p:{category}:{timeframe}:{page + 1}",
        ))
    builder.row(*nav)

    # Refresh
    builder.row(
        InlineKeyboardButton(
            text=f"🔄 {get_text('btn_refresh', lang)}",
            callback_data=f"intel:time:{category}:{timeframe}:{page}",
        )
    )

    # Navigation
    builder.row(
        InlineKeyboardButton(
            text=f"🔙 Categories",
            callback_data="intel:back_categories",
        ),
        InlineKeyboardButton(
            text=f"🏠 Menu",
            callback_data="menu:main",
        ),
    )
    return builder.as_markup()


def get_market_detail_keyboard(
    lang: str, market: MarketStats,
) -> InlineKeyboardMarkup:
    """Keyboard for market detail view."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔗 Open on Polymarket",
            url=market.market_url,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Categories",
            callback_data="intel:back_categories",
        ),
        InlineKeyboardButton(
            text="🏠 Menu",
            callback_data="menu:main",
        ),
    )
    return builder.as_markup()
