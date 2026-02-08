"""
Watchlist feature — save markets to personal watchlist.

UX Flow:
1. User browses market signals → sees market detail
2. Taps ⭐ Add to Watchlist → market slug saved to DB
3. User taps ⭐ Watchlist from main menu → sees saved markets with fresh data
4. Can remove markets from watchlist

Storage: simple DB table (user_id, market_slug, event_slug, question, added_at)
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, BigInteger, DateTime, ForeignKey, func, select, delete
from sqlalchemy.orm import Mapped, mapped_column
from loguru import logger

from models import Base


# =====================================================================
# MODEL — add to models.py (or import from here)
# =====================================================================

class WatchlistItem(Base):
    """A market saved to user's watchlist."""
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    market_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    event_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    condition_id: Mapped[str] = mapped_column(String(100), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# =====================================================================
# SERVICE
# =====================================================================

class WatchlistService:
    """CRUD for watchlist items."""

    @staticmethod
    async def add(session, user_id: int, market_slug: str, event_slug: str, question: str, condition_id: str = None) -> bool:
        """Add market to watchlist. Returns True if added, False if already exists."""
        existing = await session.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == user_id,
                WatchlistItem.market_slug == market_slug,
            )
        )
        if existing.scalar_one_or_none():
            return False

        item = WatchlistItem(
            user_id=user_id,
            market_slug=market_slug,
            event_slug=event_slug,
            question=question,
            condition_id=condition_id,
        )
        session.add(item)
        await session.flush()
        logger.info(f"Watchlist: user {user_id} added {market_slug}")
        return True

    @staticmethod
    async def remove(session, user_id: int, market_slug: str) -> bool:
        """Remove market from watchlist."""
        result = await session.execute(
            delete(WatchlistItem).where(
                WatchlistItem.user_id == user_id,
                WatchlistItem.market_slug == market_slug,
            )
        )
        if result.rowcount > 0:
            logger.info(f"Watchlist: user {user_id} removed {market_slug}")
            return True
        return False

    @staticmethod
    async def get_all(session, user_id: int) -> List[WatchlistItem]:
        """Get all watchlist items for a user."""
        result = await session.execute(
            select(WatchlistItem)
            .where(WatchlistItem.user_id == user_id)
            .order_by(WatchlistItem.added_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def is_in_watchlist(session, user_id: int, market_slug: str) -> bool:
        """Check if market is in user's watchlist."""
        result = await session.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == user_id,
                WatchlistItem.market_slug == market_slug,
            )
        )
        return result.scalar_one_or_none() is not None
