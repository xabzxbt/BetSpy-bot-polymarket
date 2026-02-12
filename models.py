"""
SQLAlchemy models for BetSpy bot.
"""

from datetime import datetime
from sqlalchemy import (
    Integer, String, Boolean, Float, BigInteger, DateTime, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """Telegram user model."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class TrackedWallet(Base):
    """Wallet subscription model."""
    __tablename__ = "tracked_wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_trade_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_check_timestamp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_user_wallet', 'user_id', 'wallet_address', unique=True),
    )

    def __repr__(self) -> str:
        return f"<TrackedWallet(id={self.id}, nickname={self.nickname}, wallet={self.wallet_address[:10]}...)>"


class OpenPosition(Base):
    """Track open positions for PnL notifications."""
    __tablename__ = "open_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False, index=True)
    condition_id: Mapped[str] = mapped_column(String(66), nullable=False)
    outcome_index: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    initial_value: Mapped[float] = mapped_column(Float, nullable=False)
    last_notified_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_wallet_position', 'wallet_address', 'condition_id', 'outcome_index', unique=True),
    )

    def __repr__(self) -> str:
        return f"<OpenPosition(wallet={self.wallet_address[:10]}..., condition={self.condition_id[:10]}...)>"
