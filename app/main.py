import asyncio
import io
import logging
import sys
from pathlib import Path

from telethon import TelegramClient, events

from app.config import (
    API_HASH,
    API_ID,
    CATCHUP_ENABLED,
    CATCHUP_INTERVAL,
    CATCHUP_LIMIT,
    CATCHUP_PRIME_DELAY,
    FORWARD_TO,
    SESSION_NAME,
    WATCHDOG_CHECK_INTERVAL_MIN,
    WATCHDOG_TIMEOUT_MIN,
)
from app.handlers.callback_handler import CallbackHandler
from app.handlers.command_handler import CommandHandler
from app.handlers.message_handler import MessageHandler
from app.services.catchup_poller import CatchupPoller
from app.services.offer_service import OfferService
from app.services.watchdog import ActivityLoggingHandler, ActivityTracker, watchdog_loop
from app.storage import load_data

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Configuração de logging unificado em Logs.txt
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "Logs.txt", encoding="utf-8"),
        logging.StreamHandler()  # mantém output no console
    ]
)
logger = logging.getLogger(__name__)

# Watchdog: qualquer log emitido conta como atividade
_tracker = ActivityTracker()
logging.getLogger().addHandler(ActivityLoggingHandler(_tracker))

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

        # Handler principal de mensagens — processa em task própria para não
        # segurar o despacho de updates (o Telethon aguarda o handler antes de
        # entregar a próxima mensagem, de qualquer grupo).
        @client.on(events.NewMessage())
        async def handle_message(event):
            message_handler.dispatch(event)

        # Varredura de segurança: recupera ofertas que o push do Telegram
        # atrasou/perdeu (gap de updates) — ver app/services/catchup_poller.py
        if CATCHUP_ENABLED:
            catchup = CatchupPoller(
                client,
                message_handler,
                offer_service,
                interval=CATCHUP_INTERVAL,
                limit=CATCHUP_LIMIT,
                prime_delay=CATCHUP_PRIME_DELAY,
            )
            asyncio.create_task(catchup.run())
            logger.info(
                f"Catch-up ativo: {len(offer_service.state['grupos'])} grupos, "
                f"1 a cada {CATCHUP_INTERVAL}s (volta completa ~"
                f"{int(len(offer_service.state['grupos']) * CATCHUP_INTERVAL)}s)"
            )
        else:
            logger.info("Catch-up desativado (CATCHUP_ENABLED=0)")

        logger.info("Bot is running and listening for offers! Press Ctrl+C to stop.")
        asyncio.create_task(
            watchdog_loop(
                _tracker,
                timeout_seconds=WATCHDOG_TIMEOUT_MIN * 60,
                check_interval_seconds=WATCHDOG_CHECK_INTERVAL_MIN * 60,
            )
        )
        logger.info(
            f"Watchdog ativo: timeout={WATCHDOG_TIMEOUT_MIN}min, "
            f"check={WATCHDOG_CHECK_INTERVAL_MIN}min"
        )
        await client.run_until_disconnected()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
