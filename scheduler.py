"""
APScheduler-based trade polling and notification system.
"""

import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select
from loguru import logger

from config import get_settings
from polymarket_api import api_client, Trade
from models import User, TrackedWallet
from translations import get_text, get_side_text


@dataclass
class WalletSubscription:
    """Data class for wallet subscription info."""
    wallet_id: int
    wallet_address: str
    nickname: str
    user_telegram_id: int
    user_language: str
    last_trade_timestamp: Optional[int]


class TradeNotificationService:
    """Service for polling trades and sending notifications."""
    
    def __init__(
        self,
        bot: Bot,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self.bot = bot
        self.session_factory = session_factory
        self.settings = get_settings()
        self.scheduler = AsyncIOScheduler()
        
        # Track processed trades to avoid duplicates (tx_hash -> timestamp)
        self._processed_trades: Dict[str, int] = {}
        self._max_processed_cache = 10000
        
        # Lock for concurrent access
        self._lock = asyncio.Lock()
        
        # Flag to check if service is running
        self._running = False
    
    async def start(self) -> None:
        """Start the scheduler."""
        self._running = True
        
        # Add the polling job
        self.scheduler.add_job(
            self._poll_and_notify,
            trigger=IntervalTrigger(seconds=self.settings.polling_interval_seconds),
            id="poll_trades",
            name="Poll trades and send notifications",
            replace_existing=True,
            max_instances=1,
        )
        
        self.scheduler.start()
        logger.info(
            f"Trade polling scheduler started. "
            f"Interval: {self.settings.polling_interval_seconds}s"
        )
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        self.scheduler.shutdown(wait=False)
        logger.info("Trade polling scheduler stopped")
    
    async def _get_all_subscriptions(self) -> List[WalletSubscription]:
        """Get all wallet subscriptions with user info."""
        async with self.session_factory() as session:
            stmt = (
                select(
                    TrackedWallet.id,
                    TrackedWallet.wallet_address,
                    TrackedWallet.nickname,
                    TrackedWallet.last_trade_timestamp,
                    User.telegram_id,
                    User.language,
                )
                .join(User, TrackedWallet.user_id == User.id)
            )
            
            result = await session.execute(stmt)
            rows = result.all()
            
            subscriptions = []
            for row in rows:
                subscriptions.append(WalletSubscription(
                    wallet_id=row[0],
                    wallet_address=row[1],
                    nickname=row[2],
                    last_trade_timestamp=row[3],
                    user_telegram_id=row[4],
                    user_language=row[5],
                ))
            
            return subscriptions
    
    async def _update_last_trade_timestamp(
        self,
        wallet_id: int,
        timestamp: int,
    ) -> None:
        """Update the last processed trade timestamp."""
        try:
            async with self.session_factory() as session:
                stmt = select(TrackedWallet).where(TrackedWallet.id == wallet_id)
                result = await session.execute(stmt)
                wallet = result.scalar_one_or_none()
                
                if wallet:
                    wallet.last_trade_timestamp = timestamp
                    await session.commit()
        except Exception as e:
            logger.error(f"Failed to update timestamp for wallet {wallet_id}: {e}")
    
    async def _poll_and_notify(self) -> None:
        """Main polling job."""
        if not self._running:
            return
            
        async with self._lock:
            logger.debug("Starting trade polling cycle...")
            
            try:
                subscriptions = await self._get_all_subscriptions()
                
                if not subscriptions:
                    logger.debug("No wallets to poll")
                    return
                
                # Group by wallet address
                address_to_subs: Dict[str, List[WalletSubscription]] = {}
                for sub in subscriptions:
                    addr = sub.wallet_address.lower()
                    if addr not in address_to_subs:
                        address_to_subs[addr] = []
                    address_to_subs[addr].append(sub)
                
                logger.info(f"Polling {len(address_to_subs)} unique wallets...")
                
                for wallet_address, subs in address_to_subs.items():
                    if not self._running:
                        break
                    await self._process_wallet(wallet_address, subs)
                    
            except Exception as e:
                logger.exception(f"Error in polling cycle: {e}")
    
    async def _process_wallet(
        self,
        wallet_address: str,
        subscriptions: List[WalletSubscription],
    ) -> None:
        """Process a single wallet."""
        try:
            # Find the latest timestamp among all subscriptions
            # We only want trades AFTER this timestamp
            max_timestamp = None
            for sub in subscriptions:
                if sub.last_trade_timestamp:
                    if max_timestamp is None or sub.last_trade_timestamp > max_timestamp:
                        max_timestamp = sub.last_trade_timestamp
            
            # If no timestamp set, this is a new wallet - don't fetch old trades
            # Just set the current time as starting point
            if max_timestamp is None:
                logger.info(f"New wallet {wallet_address[:10]}... - setting initial timestamp")
                current_ts = int(time.time())
                for sub in subscriptions:
                    await self._update_last_trade_timestamp(sub.wallet_id, current_ts)
                return
            
            # Fetch trades after the last known timestamp
            trades = await api_client.get_new_trades_for_wallet(
                wallet_address=wallet_address,
                since_timestamp=max_timestamp,
            )
            
            if not trades:
                return
            
            # Filter: only trades STRICTLY after max_timestamp
            new_trades = [t for t in trades if t.timestamp > max_timestamp]
            
            if not new_trades:
                return
            
            logger.info(f"Found {len(new_trades)} NEW trades for {wallet_address[:10]}...")
            
            # Filter by minimum amount
            min_amount = self.settings.min_trade_amount_usdc
            new_trades = [t for t in new_trades if t.usdc_size >= min_amount]
            
            if not new_trades:
                return
            
            # Process each new trade
            latest_timestamp = max_timestamp
            
            for trade in new_trades:
                if not self._running:
                    break
                    
                # Skip if already processed (double-check)
                if trade.transaction_hash in self._processed_trades:
                    continue
                
                # Notify all subscribers
                for sub in subscriptions:
                    if not self._running:
                        break
                    await self._send_notification(trade, sub)
                
                # Mark as processed
                self._processed_trades[trade.transaction_hash] = trade.timestamp
                
                # Track latest timestamp
                if trade.timestamp > latest_timestamp:
                    latest_timestamp = trade.timestamp
            
            # Update timestamp for all subscriptions
            if latest_timestamp > max_timestamp:
                for sub in subscriptions:
                    await self._update_last_trade_timestamp(sub.wallet_id, latest_timestamp)
            
            # Cleanup cache
            self._cleanup_processed_cache()
            
        except Exception as e:
            logger.error(f"Error processing wallet {wallet_address[:10]}...: {e}")
    
    async def _send_notification(
        self,
        trade: Trade,
        subscription: WalletSubscription,
    ) -> None:
        """Send notification to a user."""
        if not self._running:
            return
            
        try:
            message = self._format_trade_notification(
                trade=trade,
                wallet_name=subscription.nickname,
                lang=subscription.user_language,
            )
            
            await self.bot.send_message(
                chat_id=subscription.user_telegram_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            
            logger.info(
                f"Sent notification to user {subscription.user_telegram_id} "
                f"for wallet {subscription.nickname}"
            )
            
            # Small delay to avoid Telegram rate limits
            await asyncio.sleep(0.05)
            
        except Exception as e:
            logger.error(
                f"Failed to notify user {subscription.user_telegram_id} "
                f"about trade {trade.transaction_hash[:10]}...: {e}"
            )
    
    def _format_trade_notification(
        self,
        trade: Trade,
        wallet_name: str,
        lang: str,
    ) -> str:
        """Format trade notification message."""
        side_text = get_side_text(trade.side, lang)
        
        return get_text(
            "new_trade",
            lang,
            wallet_name=wallet_name,
            market_title=trade.title,
            side=side_text,
            outcome=trade.outcome,
            size=trade.size,
            usdc_size=trade.usdc_size,
            price=trade.price,
            market_link=trade.market_link,
        )
    
    def _cleanup_processed_cache(self) -> None:
        """Remove old entries from cache."""
        if len(self._processed_trades) > self._max_processed_cache:
            sorted_items = sorted(
                self._processed_trades.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            self._processed_trades = dict(sorted_items[:self._max_processed_cache // 2])
            logger.debug(f"Cleaned cache, now {len(self._processed_trades)} entries")


# Global instance
notification_service: Optional[TradeNotificationService] = None


def get_notification_service() -> Optional[TradeNotificationService]:
    """Get the notification service instance."""
    return notification_service


def init_notification_service(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> TradeNotificationService:
    """Initialize the notification service."""
    global notification_service
    notification_service = TradeNotificationService(bot, session_factory)
    return notification_service
