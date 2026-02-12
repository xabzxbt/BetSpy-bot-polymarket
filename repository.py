"""
Repository pattern for database operations.
"""

import time
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from models import User, TrackedWallet


class UserRepository:
    """Repository for User operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
    ) -> User:
        """Get existing user or create new one."""
        user = await self.get_by_telegram_id(telegram_id)
        
        if user:
            # Update user info if changed
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            return user
        
        # Create new user
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )
        self.session.add(user)
        await self.session.flush()
        
        logger.info(f"Created new user: telegram_id={telegram_id}")
        return user


class WalletRepository:
    """Repository for TrackedWallet operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_user_and_address(
        self,
        user_id: int,
        wallet_address: str,
    ) -> Optional[TrackedWallet]:
        """Get wallet by user ID and address."""
        stmt = select(TrackedWallet).where(
            TrackedWallet.user_id == user_id,
            func.lower(TrackedWallet.wallet_address) == wallet_address.lower()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_wallets(self, user_id: int) -> List[TrackedWallet]:
        """Get all wallets for a user."""
        stmt = (
            select(TrackedWallet)
            .where(TrackedWallet.user_id == user_id)
            .order_by(TrackedWallet.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def count_user_wallets(self, user_id: int) -> int:
        """Count wallets for a user."""
        stmt = (
            select(func.count(TrackedWallet.id))
            .where(TrackedWallet.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
    
    async def create(
        self,
        user_id: int,
        wallet_address: str,
        nickname: str,
    ) -> TrackedWallet:
        """Create a new tracked wallet with current timestamp."""
        # Set last_trade_timestamp to NOW so we don't spam old trades
        current_timestamp = int(time.time())
        
        wallet = TrackedWallet(
            user_id=user_id,
            wallet_address=wallet_address.lower(),
            nickname=nickname,
            last_trade_timestamp=current_timestamp,
        )
        self.session.add(wallet)
        await self.session.flush()
        
        logger.info(f"Created tracked wallet: {wallet_address[:10]}... for user {user_id}")
        return wallet
    
    async def delete(self, wallet: TrackedWallet) -> None:
        """Delete a tracked wallet."""
        await self.session.delete(wallet)
        await self.session.flush()
        logger.info(f"Deleted tracked wallet: {wallet.wallet_address[:10]}...")
    
    async def delete_by_user_and_address(
        self,
        user_id: int,
        wallet_address: str,
    ) -> bool:
        """Delete wallet by user ID and address. Returns True if deleted."""
        wallet = await self.get_by_user_and_address(user_id, wallet_address)
        if wallet:
            await self.delete(wallet)
            return True
        return False
    
    async def update_last_trade_timestamp(
        self,
        wallet_id: int,
        timestamp: int,
    ) -> None:
        """Update the last processed trade timestamp for a wallet."""
        stmt = select(TrackedWallet).where(TrackedWallet.id == wallet_id)
        result = await self.session.execute(stmt)
        wallet = result.scalar_one_or_none()
        
        if wallet:
            wallet.last_trade_timestamp = timestamp
            await self.session.flush()
