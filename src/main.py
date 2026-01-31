import logging
from logging.handlers import RotatingFileHandler
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from telegram.ext import Application, ApplicationBuilder, CommandHandler
from src.config import settings
from src.bot import setup_handlers

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=settings.LOG_LEVEL,
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler("bot.log", maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
    ],
    force=True
)
logger = logging.getLogger(__name__)

# Global variable to hold the Telegram Application
telegram_app: Application = None

async def start_telegram_bot():
    """Starts the Telegram bot in polling mode."""
    global telegram_app
    logger.info("Initializing Telegram Bot...")

    # Initialize the Application
    telegram_app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Register Handlers
    setup_handlers(telegram_app)

    logger.info("Telegram Bot initialized via Polling...")

    # Initialize and start the application
    await telegram_app.initialize()
    await telegram_app.start()

    # In polling mode, we usually use run_polling(), but since we are running
    # inside FastAPI event loop, we might need a background task or just use the updater.
    # For simplicity in this hybrid setup, using updater.start_polling() is often easier
    # but `run_polling` blocks.
    # Modern PTB (v20+) uses `application.run_polling()` which blocks.
    # To run alongside FastAPI, we manually start the updater.

    await telegram_app.updater.start_polling()
    logger.info("Telegram Bot Polling started.")

async def stop_telegram_bot():
    """Stops the Telegram bot."""
    global telegram_app
    if telegram_app:
        logger.info("Stopping Telegram Bot...")
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
        logger.info("Telegram Bot stopped.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Telegram Bot
    # Run the bot in the background or just start polling
    # For PTB v20 with asyncio, we can just await the start methods.

    # IMPORTANT: We need to ensure we don't block the main thread.
    # p-t-b 'start_polling' is non-blocking in the sense that it sets up tasks?
    # Actually, `updater.start_polling()` is non-blocking (it creates a task).

    await start_telegram_bot()

    yield

    # Shutdown: Stop Telegram Bot
    await stop_telegram_bot()

app = FastAPI(title="Telegram AI Bot", lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "running", "bot": "active"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
