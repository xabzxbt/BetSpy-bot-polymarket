"""
BetSpy Polymarket Bot — Main Entry Point
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
from polymarket_api import api_client
from handlers import setup_handlers
from handlers_reply import setup_reply_handlers
from scheduler import init_notification_service


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

    # 1. Database
    logger.info("Initializing database...")
    await db.init()
    logger.info("Database initialized")

    # 2. Create database tables
    try:
        from models import Base, OpenPosition  # Ensure OpenPosition table is created
        async with db._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB tables synced")
    except Exception as e:
        logger.warning(f"Table sync warning (non-fatal): {e}")

    # 3. Bot + Dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 4. Register handlers
    # ORDER MATTERS: specific handlers first, catch-all last
    setup_reply_handlers(dp)
    setup_handlers(dp)

    # 5. Scheduler (notifications)
    notification_service = init_notification_service(bot, db._session_factory)
    await notification_service.start()

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down...")
        if notification_service:
            await notification_service.stop()
        await api_client.close()
        await db.close()
        await bot.session.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
