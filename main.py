"""
BetSpy Polymarket Bot — Main Entry Point (v3)

Changes from v2:
- i18n initialized from JSON locale files
- Reply keyboard handlers for persistent navigation
- Watchlist + Hot Today features
- WatchlistItem table auto-created
"""

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from config import get_settings
from database import db
from i18n import i18n
from polymarket_api import api_client
from handlers import setup_handlers
from handlers_intelligence import setup_intelligence_handlers
from handlers_reply import setup_reply_handlers
from handlers_watchlist import setup_watchlist_handlers
from handlers_hot import setup_hot_handlers
from scheduler import init_notification_service
from market_intelligence import market_intelligence


def setup_logging() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level.upper(),
    )
    logger.info(f"Logging configured at level: {settings.log_level}")


async def main() -> None:
    setup_logging()
    settings = get_settings()

    # 1. i18n — load JSON locale files
    i18n.load()

    # 2. Database
    logger.info("Initializing database...")
    await db.init()
    logger.info("Database initialized")

    # 3. Create WatchlistItem table if not exists
    try:
        from services.watchlist_service import WatchlistItem  # noqa
        async with db.engine.begin() as conn:
            from models import Base
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB tables synced (including watchlist)")
    except Exception as e:
        logger.warning(f"Table sync warning (non-fatal): {e}")

    # 4. Bot + Dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 5. Register handlers (order matters — reply first, then inline)
    setup_reply_handlers(dp)
    setup_handlers(dp)
    setup_intelligence_handlers(dp)
    setup_watchlist_handlers(dp)
    setup_hot_handlers(dp)

    # 6. Scheduler (notifications)
    notification_service = init_notification_service(bot)

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down...")
        if notification_service:
            notification_service.stop()
        await api_client.close()
        await db.close()
        await bot.session.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
