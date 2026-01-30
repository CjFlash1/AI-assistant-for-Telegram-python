import logging
import asyncio
from telegram.ext import ApplicationBuilder
from src.config import settings
from src.bot import setup_handlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting bot directly...")
    application = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    setup_handlers(application)

    # run_polling() is blocking, so we use it here
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    logger.info("Bot is polling. Press Ctrl+C to stop.")
    # Keep running manually since we are in a direct script
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
