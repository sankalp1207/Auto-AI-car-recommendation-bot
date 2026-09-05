import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env
BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def validate_config() -> bool:
    """Validates required bot configuration without revealing secret values."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your-telegram-bot-token-here":
        print("\n" + "=" * 60, file=sys.stderr)
        print("[ERROR] TELEGRAM_BOT_TOKEN is not configured in backend/.env.", file=sys.stderr)
        print("Please add a valid token to backend/.env:", file=sys.stderr)
        print("TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)
        return False
    return True
