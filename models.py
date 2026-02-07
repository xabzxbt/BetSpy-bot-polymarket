"""
SQLAlchemy 2.0 async models for the Polymarket Whale Tracker.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, BigInteger, DateTime, ForeignKey, Index, UniqueConstraint, func,
    Float, Boolean
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship
)


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """Telegram user who uses the bot."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    
    # Flag to track if user blocked the bot
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    wallets: Mapped[List["TrackedWallet"]] = relationship(
        "TrackedWallet",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"


class TrackedWallet(Base):
    """A wallet being tracked by a user."""
    
    __tablename__ = "tracked_wallets"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False, index=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Per-wallet settings
    min_trade_amount: Mapped[float] = mapped_column(
        Float, 
        default=0.0, 
        nullable=False,
        comment="Minimum trade amount in USDC to notify (0 = use global setting)"
    )
    is_paused: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Pause notifications for this wallet"
    )
    
    last_trade_timestamp: Mapped[Optional[int]] = mapped_column(
        BigInteger, 
        nullable=True,
        comment="Unix timestamp of the last processed trade"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="wallets")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "wallet_address", name="uq_user_wallet"),
        Index("ix_tracked_wallets_address_lower", func.lower(wallet_address)),
    )
    
    def __repr__(self) -> str:
        return f"<TrackedWallet(address={self.wallet_address}, nickname={self.nickname})>"
    
    @property
    def short_address(self) -> str:
        """Return shortened wallet address (0x1234...abcd)."""
        if len(self.wallet_address) > 10:
            return f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"
        return self.wallet_address
