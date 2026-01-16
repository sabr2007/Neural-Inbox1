# neural-inbox1/src/main.py
"""
Neural Inbox - Main entry point.
Runs both Telegram bot and FastAPI server.
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
from src.bot.jobs import init_scheduler, get_scheduler

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

    scheduler = init_scheduler(bot)
    scheduler.start()
    logger.info("Reminder scheduler started")

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

    scheduler = get_scheduler()
    if scheduler:
        scheduler.stop()
        logger.info("Reminder scheduler stopped")

    await close_db()
    logger.info("Bot stopped")


async def run_bot() -> None:
    """Run the Telegram bot."""
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


async def run_api() -> None:
    """Run the FastAPI server."""
    import uvicorn
    from src.api.app import app
    from fastapi.staticfiles import StaticFiles

    # Serve React build if it exists
    webapp_dist = Path(__file__).parent.parent / "webapp" / "dist"
    if webapp_dist.exists():
        # Mount static files AFTER API routes (app already has routes)
        app.mount("/", StaticFiles(directory=str(webapp_dist), html=True), name="webapp")
        logger.info(f"Serving webapp from {webapp_dist}")
    else:
        logger.warning(f"Webapp dist not found at {webapp_dist}")

    # Get port from environment or default
    import os
    port = int(os.getenv("PORT", "8000"))

    config_uvicorn = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config_uvicorn)
    await server.serve()


async def main() -> None:
    """Run both bot and API server concurrently."""
    import os
    mode = os.getenv("RUN_MODE", "both")  # "bot", "api", or "both"

    if mode == "bot":
        await run_bot()
    elif mode == "api":
        await run_api()
    else:
        # Run both concurrently
        await asyncio.gather(
            run_bot(),
            run_api()
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
