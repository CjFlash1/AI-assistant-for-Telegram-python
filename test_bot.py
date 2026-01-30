import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"RECEIVED: {update.message.text}")
    await update.message.reply_text(f"Echo: {update.message.text}")

async def main():
    print("Testing bot connectivity...")
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, echo))

    print("Pre-start getMe:")
    me = await app.bot.get_me()
    print(f"Bot info: {me.username}")

    print("Starting polling (Press Ctrl+C to stop)...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Stay alive
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
