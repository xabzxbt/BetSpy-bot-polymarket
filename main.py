"""
Main entry point for the Polymarket Whale Tracker bot.
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
from scheduler import init_notification_service


def setup_logging() -> None:
    """Configure loguru logging."""
    settings = get_settings()
    
    # Remove default handler
    logger.remove()
    
    # Add console handler with appropriate level
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.log_level,
        colorize=True,
    )
    
    # Add file handler for errors
    logger.add(
        "logs/error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )
    
    # Add file handler for all logs
    logger.add(
        "logs/bot.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level=settings.log_level,
        rotation="50 MB",
        retention="3 days",
        compression="zip",
    )
    
    logger.info(f"Logging configured. Level: {settings.log_level}")


async def on_startup(bot: Bot) -> None:
    """Called when bot starts."""
    me = await bot.get_me()
    logger.info(f"Bot started: @{me.username} (ID: {me.id})")


async def on_shutdown(bot: Bot) -> None:
    """Called when bot shuts down."""
    logger.info("Bot shutting down...")


async def main() -> None:
    """Main function to run the bot."""
    # Setup logging
    setup_logging()
    
    # Load settings
    settings = get_settings()
    logger.info("Settings loaded")
    
    # Initialize database
    await db.init()
    await db.create_tables()
    
    # Initialize API client
    await api_client.init()
    
    # Create bot instance
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )
    
    # Create dispatcher with FSM storage
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Setup handlers
    setup_handlers(dp)
    
    # Initialize notification service
    notification_service = init_notification_service(
        bot=bot,
        session_factory=db.session_factory,
    )
    await notification_service.start()
    
    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        logger.info("Starting bot polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        # Cleanup
        logger.info("Cleaning up...")
        await notification_service.stop()
        await api_client.close()
        await db.close()
        await bot.session.close()
        logger.info("Cleanup complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
