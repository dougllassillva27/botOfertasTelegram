import logging
from telethon import TelegramClient, events
from app.config import API_ID, API_HASH, SESSION_NAME, FORWARD_TO
from app.storage import load_data
from app.services.offer_service import OfferService
from app.handlers.command_handler import CommandHandler
from app.handlers.message_handler import MessageHandler
from app.handlers.callback_handler import CallbackHandler

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

state = load_data()
state.setdefault("forward_to", FORWARD_TO)


async def main():
    if not API_ID or not API_HASH:
        logger.error("API_ID and API_HASH must be set in the .env file.")
        return

    logger.info("Initializing Telegram Client...")
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        logger.info("Client created successfully.")

        # Inicializa serviços e handlers
        offer_service = OfferService(state)
        command_handler = CommandHandler(client, offer_service)
        message_handler = MessageHandler(client, offer_service)
        callback_handler = CallbackHandler(client, offer_service)

        # Registra comandos
        command_handler.register(FORWARD_TO)
        callback_handler.register()

        logger.info(f"Commands will be monitored in chat ID: {FORWARD_TO}")

        # Handler principal de mensagens
        @client.on(events.NewMessage())
        async def handle_message(event):
            await message_handler.handle_message(event)

        logger.info("Bot is running and listening for offers! Press Ctrl+C to stop.")
        await client.run_until_disconnected()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
