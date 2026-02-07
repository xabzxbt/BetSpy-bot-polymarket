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
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select, update
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
    user_id: int
    user_telegram_id: int
    user_language: str
    last_trade_timestamp: Optional[int]
    min_trade_amount: float
    is_paused: bool


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
        """Get all wallet subscriptions with user info (excluding blocked users)."""
        async with self.session_factory() as session:
            stmt = (
                select(
                    TrackedWallet.id,
                    TrackedWallet.wallet_address,
                    TrackedWallet.nickname,
                    TrackedWallet.last_trade_timestamp,
                    TrackedWallet.min_trade_amount,
                    TrackedWallet.is_paused,
                    User.id.label("user_id"),
                    User.telegram_id,
                    User.language,
                )
                .join(User, TrackedWallet.user_id == User.id)
                .where(User.is_blocked == False)  # Exclude blocked users
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
                    min_trade_amount=row[4] or 0.0,
                    is_paused=row[5] or False,
                    user_id=row[6],
                    user_telegram_id=row[7],
                    user_language=row[8],
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
    
    async def _mark_user_blocked(self, user_id: int) -> None:
        """Mark user as blocked when they block the bot."""
        try:
            async with self.session_factory() as session:
                stmt = update(User).where(User.id == user_id).values(is_blocked=True)
                await session.execute(stmt)
                await session.commit()
                logger.info(f"Marked user {user_id} as blocked")
        except Exception as e:
            logger.error(f"Failed to mark user {user_id} as blocked: {e}")
    
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
            
            # Group trades by subscription to batch notifications
            latest_timestamp = max_timestamp
            
            # Prepare notifications for each subscription
            subscription_notifications = {}
            for trade in new_trades:
                if not self._running:
                    break
                    
                # Skip if already processed (double-check)
                if trade.transaction_hash in self._processed_trades:
                    continue
                
                # Check each subscription to see if they should be notified
                for sub in subscriptions:
                    if not self._running:
                        break
                    
                    # Skip if wallet is paused
                    if sub.is_paused:
                        continue
                    
                    # Check per-wallet min amount, fallback to global setting
                    min_amount = sub.min_trade_amount
                    if min_amount <= 0:
                        min_amount = self.settings.min_trade_amount_usdc
                    
                    # Skip if trade is below minimum
                    if trade.usdc_size < min_amount:
                        continue
                    
                    # Add trade to this subscription's notifications
                    if sub.user_telegram_id not in subscription_notifications:
                        subscription_notifications[sub.user_telegram_id] = {'sub': sub, 'trades': []}
                    subscription_notifications[sub.user_telegram_id]['trades'].append(trade)
                
                # Mark as processed
                self._processed_trades[trade.transaction_hash] = trade.timestamp
                
                # Track latest timestamp
                if trade.timestamp > latest_timestamp:
                    latest_timestamp = trade.timestamp
            
            # Send batched notifications
            for user_id, notification_data in subscription_notifications.items():
                sub = notification_data['sub']
                trades = notification_data['trades']
                
                # Sort trades by timestamp to show in chronological order
                trades.sort(key=lambda x: x.timestamp)
                
                await self._send_batch_notification(trades, sub)
                
                # Small delay between batch notifications to avoid rate limits
                await asyncio.sleep(0.1)
            
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
            
        except TelegramForbiddenError:
            # User blocked the bot
            logger.warning(
                f"User {subscription.user_telegram_id} blocked the bot. "
                f"Marking as blocked."
            )
            await self._mark_user_blocked(subscription.user_id)
            
        except TelegramBadRequest as e:
            # Handle other Telegram errors
            if "chat not found" in str(e).lower():
                logger.warning(
                    f"Chat not found for user {subscription.user_telegram_id}. "
                    f"Marking as blocked."
                )
                await self._mark_user_blocked(subscription.user_id)
            else:
                logger.error(
                    f"Telegram error for user {subscription.user_telegram_id}: {e}"
                )
                
        except Exception as e:
            logger.error(
                f"Failed to notify user {subscription.user_telegram_id} "
                f"about trade {trade.transaction_hash[:10]}...: {e}"
            )

    async def _send_batch_notification(
        self,
        trades: List[Trade],
        subscription: WalletSubscription,
    ) -> None:
        """Send batch notification to a user for multiple trades."""
        if not self._running or not trades:
            return
            
        try:
            message = self._format_batch_trade_notification(
                trades=trades,
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
                f"Sent batch notification to user {subscription.user_telegram_id} "
                f"for wallet {subscription.nickname} with {len(trades)} trades"
            )
            
        except TelegramForbiddenError:
            # User blocked the bot
            logger.warning(
                f"User {subscription.user_telegram_id} blocked the bot. "
                f"Marking as blocked."
            )
            await self._mark_user_blocked(subscription.user_id)
            
        except TelegramBadRequest as e:
            # Handle other Telegram errors
            if "chat not found" in str(e).lower():
                logger.warning(
                    f"Chat not found for user {subscription.user_telegram_id}. "
                    f"Marking as blocked."
                )
                await self._mark_user_blocked(subscription.user_id)
            else:
                logger.error(
                    f"Telegram error for user {subscription.user_telegram_id}: {e}"
                )
                
        except Exception as e:
            logger.error(
                f"Failed to send batch notification to user {subscription.user_telegram_id} "
                f"for {len(trades)} trades: {e}"
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

    def _format_batch_trade_notification(
        self,
        trades: List[Trade],
        wallet_name: str,
        lang: str,
    ) -> str:
        """Format batch trade notification message."""
        if not trades:
            return ""
        
        # Get the first trade to use as the base for the message
        first_trade = trades[0]
        side_text = get_side_text(first_trade.side, lang)
        
        # Calculate total USDC amount and number of trades
        total_usdc = sum(trade.usdc_size for trade in trades)
        trade_count = len(trades)
        
        # Get the most recent trade timestamp for the header
        latest_timestamp = max(trade.timestamp for trade in trades)
        import datetime
        latest_time = datetime.datetime.fromtimestamp(latest_timestamp).strftime('%H:%M')
        
        # Create the header with summary
        header = f"🐋 <b>НОВІ УГОДИ ({trade_count})</b>\n"
        header += f"├ <b>{wallet_name}</b>\n"
        header += f"├ Угода: {latest_time}\n"
        header += f"├ Всього: ${total_usdc:.2f} USDC\n"
        header += f"└ Трейди: {trade_count}\n\n"
        
        # Add individual trades (limit to 5 to avoid too long messages)
        body = "<b>ДЕТАЛІ:</b>\n"
        for i, trade in enumerate(trades[:5]):  # Limit to first 5 trades in the message
            side_text = get_side_text(trade.side, lang)
            body += f"├ {side_text} {trade.title[:30]}{'...' if len(trade.title) > 30 else ''}\n"
            body += f"├ Сума: ${trade.usdc_size:.2f} USDC\n"
            body += f"└ Ціна: {trade.price:.4f}\n\n"
        
        # If there are more than 5 trades, add a note
        if len(trades) > 5:
            body += f"<i>+ще {len(trades) - 5} угод(и)...</i>\n\n"
        
        footer = "💡 Перевір свій кабінет для детального аналізу"
        
        return header + body + footer
    
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
