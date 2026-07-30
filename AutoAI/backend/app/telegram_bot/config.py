import os
from pathlib import Path
from dotenv import load_dotenv

# Search for .env in potential locations to ensure it's loaded regardless of where it is run
env_locations = [
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent / "backend" / ".env",
    Path.cwd() / ".env",
    Path.cwd() / "backend" / ".env",
]

for loc in env_locations:
    if loc.exists():
        load_dotenv(dotenv_path=loc)
        break
else:
    load_dotenv()  # Fallback to standard dotenv loading

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Settings Defaults
DEFAULT_LANGUAGE = "en"  # "en" or "hi"
DEFAULT_THEME = "dark"   # "dark" or "light"
DEFAULT_NOTIFICATIONS = True
