import logging
import time
from pathlib import Path

# Create a logs directory inside the telegram_bot folder
log_dir = Path(__file__).resolve().parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "bot.log"

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("AutoAIBot")

def log_activity(user_id: int | str, action: str, response_time_ms: float | None = None, error: Exception | str | None = None):
    """
    Log bot activity details including user, action, backend response time, and errors.
    """
    msg = f"User: {user_id} | Action: {action}"
    if response_time_ms is not None:
        msg += f" | ResponseTime: {response_time_ms:.2f}ms"
    if error is not None:
        msg += f" | Error: {error}"
        logger.error(msg)
    else:
        logger.info(msg)
