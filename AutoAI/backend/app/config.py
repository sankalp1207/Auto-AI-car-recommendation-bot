from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
# Load .env if present (for local dev), without overwriting existing environment variables
load_dotenv(BASE_DIR / ".env", override=False)

# Database
raw_db_url = os.getenv("DATABASE_URL")
if raw_db_url and raw_db_url.startswith("postgres://"):
    # SQLAlchemy requires postgresql:// instead of postgres://
    DATABASE_URL = raw_db_url.replace("postgres://", "postgresql://", 1)
else:
    DATABASE_URL = raw_db_url

# Security & Secrets
SECRET_KEY = os.getenv("SECRET_KEY")

# AI / Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "10"))

# Server Network & Runtime Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# CORS Configuration
raw_cors = os.getenv("CORS_ORIGINS", "")
if raw_cors.strip():
    CORS_ORIGINS = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]
else:
    CORS_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]