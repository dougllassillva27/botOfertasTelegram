import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Mapeamento de diretórios base
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Define o caminho absoluto da sessão dentro da pasta data/
session_env = os.getenv("SESSION_NAME", "userbot_session")
SESSION_NAME = os.path.join(DATA_DIR, session_env)

# Handle the destination for forwarded messages
forward_to_env = os.getenv("FORWARD_TO", "me")
try:
    # Try to convert to integer for chat IDs (groups/channels)
    FORWARD_TO = int(forward_to_env)
except ValueError:
    # If it fails (e.g., it's the string "me"), use the string directly
    FORWARD_TO = forward_to_env