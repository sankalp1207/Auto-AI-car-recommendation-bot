from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Locate backend/.env if running locally
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)

raw_url = os.getenv("DATABASE_URL")
if not raw_url:
    raise ValueError("DATABASE_URL environment variable is not set. Please provide a valid PostgreSQL connection string.")

# Normalize postgres:// to postgresql:// for SQLAlchemy
if raw_url.startswith("postgres://"):
    DATABASE_URL = raw_url.replace("postgres://", "postgresql://", 1)
else:
    DATABASE_URL = raw_url

# Configure engine with robust connection pooling for production
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()