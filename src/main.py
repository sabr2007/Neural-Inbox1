# neural-inbox1/src/main.py
"""
Neural Inbox - Main entry point.
A Telegram bot that acts as your second brain.
"""
import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.db.database import init_db, close_db
from src.bot.handlers.message import message_router
from src.bot.handlers.callbacks import callback_router

logging.basicConfig(
    level=logging.DEBUG if config.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    logger.info("Starting Neural Inbox bot...")
    await init_db()
    logger.info("Database initialized")

    if config.telegram.webapp_url:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть",
                    web_app=WebAppInfo(url=config.telegram.webapp_url)
                )
            )
            logger.info(f"WebApp menu button set: {config.telegram.webapp_url}")
        except Exception as e:
            logger.warning(f"Failed to set WebApp menu button: {e}")

    logger.info("Bot started successfully!")


async def on_shutdown(bot: Bot) -> None:
    logger.info("Shutting down Neural Inbox bot...")
    await close_db()
    logger.info("Bot stopped")


async def main() -> None:
    if not config.telegram.bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        sys.exit(1)

    if not config.openai.api_key:
        logger.error("OPENAI_API_KEY is not set!")
        sys.exit(1)

    bot = Bot(
        token=config.telegram.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()
    dp.include_router(message_router)
    dp.include_router(callback_router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
