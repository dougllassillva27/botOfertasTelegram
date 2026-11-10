import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Mapeamento de diretórios base
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Define o caminho absoluto da sessão dentro da pasta data/
session_env = os.getenv("SESSION_NAME", "userbot_session")
SESSION_NAME = os.path.join(DATA_DIR, session_env)

# Watchdog: reinicia o servico (via NSSM) se o bot ficar sem atividade.
# O Telethon gera logs de heartbeat a cada ~15 min quando saudavel,
# entao o default de 40 min tolera ate 2 heartbeats perdidos.
WATCHDOG_TIMEOUT_MIN = int(os.getenv("WATCHDOG_TIMEOUT_MIN", "40"))
WATCHDOG_CHECK_INTERVAL_MIN = int(os.getenv("WATCHDOG_CHECK_INTERVAL_MIN", "5"))

# Catch-up: varredura de seguranca dos grupos monitorados. Cobre o caso em que
# o Telegram corta a fila de updates de um canal e o push so chega no timeout
# interno de 15 min do Telethon (causou oferta de BUG com 11 min de atraso).
CATCHUP_ENABLED = os.getenv("CATCHUP_ENABLED", "1").lower() not in (
    "0",
    "false",
    "no",
    "off",
)
# Pausa entre um grupo e outro dentro da mesma volta (53 grupos ~ 53s por volta).
CATCHUP_INTERVAL = float(os.getenv("CATCHUP_INTERVAL", "1.0"))
# Quantas mensagens recentes reler por grupo em cada varredura.
CATCHUP_LIMIT = int(os.getenv("CATCHUP_LIMIT", "20"))
# Espera antes do primeiro prime, para o client estar conectado.
CATCHUP_PRIME_DELAY = int(os.getenv("CATCHUP_PRIME_DELAY", "60"))

# Handle the destination for forwarded messages
forward_to_env = os.getenv("FORWARD_TO", "me")
try:
    # Try to convert to integer for chat IDs (groups/channels)
    FORWARD_TO = int(forward_to_env)
except ValueError:
    # If it fails (e.g., it's the string "me"), use the string directly
    FORWARD_TO = forward_to_env
