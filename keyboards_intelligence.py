"""
Keyboard builders for BetSpy Market Intelligence (v3).

Changes from v2:
- All strings go through i18n (get_text)
- Watchlist button added to market detail
- Category keys use dot notation (cat.politics, not cat_politics)
"""

import time
from typing import List, Dict, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from market_intelligence import MarketStats, Category, TimeFrame
from i18n import get_text


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
        [("🏛️", "cat.politics", "politics"), ("⚽", "cat.sports", "sports")],
        [("🎬", "cat.pop_culture", "pop-culture"), ("💼", "cat.business", "business")],
        [("₿", "cat.crypto", "crypto"), ("🔬", "cat.science", "science")],
        [("🎮", "cat.gaming", "gaming"), ("🎭", "cat.entertainment", "entertainment")],
        [("🌍", "cat.world", "world"), ("💻", "cat.tech", "tech")],
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
            text=f"📊 {get_text('cat.all', lang)}",
            callback_data="intel:cat:all",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn.back_to_menu", lang),
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
            text=get_text("btn.prev_page", lang),
            callback_data=f"intel:p:{category}:{timeframe}:{page - 1}",
        ))
    nav.append(InlineKeyboardButton(
        text=f"📄 {page}/{total_pages}", callback_data="noop",
    ))
    if page < total_pages:
        nav.append(InlineKeyboardButton(
            text=get_text("btn.next_page", lang),
            callback_data=f"intel:p:{category}:{timeframe}:{page + 1}",
        ))
    builder.row(*nav)

    # Refresh
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn.refresh", lang),
            callback_data=f"intel:time:{category}:{timeframe}:{page}",
        )
    )

    # Navigation
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn.back", lang),
            callback_data="intel:back_categories",
        ),
        InlineKeyboardButton(
            text=get_text("btn.back_to_menu", lang),
            callback_data="menu:main",
        ),
    )
    return builder.as_markup()


def get_market_detail_keyboard(
    lang: str, market: MarketStats,
) -> InlineKeyboardMarkup:
    """Keyboard for market detail view — with Watchlist button."""
    builder = InlineKeyboardBuilder()

    # Watchlist button — uses the last cache key for this market
    # We store slug for the watchlist add handler
    cache_key = None
    for k, (m, _) in _market_cache.items():
        if m.condition_id == market.condition_id:
            cache_key = k
            break

    if cache_key:
        builder.row(
            InlineKeyboardButton(
                text=get_text("deep.btn_deep", lang),
                callback_data=f"deep:{cache_key}",
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=get_text("watchlist.btn_add", lang),
                callback_data=f"wl:add:{cache_key}",
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=get_text("intel.link_text", lang),
            url=market.market_url,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn.back", lang),
            callback_data="intel:back_categories",
        ),
        InlineKeyboardButton(
            text=get_text("btn.back_to_menu", lang),
            callback_data="menu:main",
        ),
    )
    return builder.as_markup()
