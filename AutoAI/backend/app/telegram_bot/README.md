# AutoAI Telegram Bot Client 🚗

This is the production-ready Telegram Bot client for the **AutoAI** platform. It communicates with the AutoAI FastAPI backend to provide AI-powered car recommendations, car search, side-by-side comparison, wishlist, profile statistics, and AI chat memory.

## Folder Structure

```text
telegram_bot/
│
├── logs/                   # Bot runtime log files (created automatically)
│   └── bot.log
│
├── __init__.py
├── api.py                  # Backend REST API Client layer (asynchronous)
├── bot.py                  # Entrypoint: sets up ApplicationBuilder and polling
├── config.py               # Config loader (.env file parser)
├── handlers.py             # Event, text, and command callback handlers
├── keyboards.py            # Main Menu and Inline UI keyboards
├── logger.py               # Custom activity and error logging setup
├── states.py               # State constants for Recommendation Flow
└── utils.py                # Formatting helpers (HTML parser, Budget parser, JWT decoder)
```

## Requirements

The bot is designed to run using Python 3.10+ and requires the following libraries:
- `python-telegram-bot==21.*`
- `python-dotenv`
- `requests`
- `httpx`

## Installation

1. Make sure your Python virtual environment is activated.
2. Install the required dependencies:
   ```bash
   pip install python-telegram-bot==21.* python-dotenv requests httpx
   ```

## Environment Variables

Ensure your backend's `.env` file (located in `backend/.env`) contains the following configuration variables:

```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
BACKEND_URL="http://127.0.0.1:8000"
```

*Note: The bot automatically searches for `.env` files in parent directories or backend folders, so you don't need to copy it.*

## Running the Application

To run the full stack, you need to launch both the FastAPI backend and the Telegram bot:

### 1. Start the FastAPI Backend
From the `backend/` directory:
```bash
python -m uvicorn app.main:app --reload
```

### 2. Start the Telegram Bot
From the `AutoAI/` directory:
```bash
python telegram_bot/bot.py
```

## Bot Features & Commands

Once started, click the bot's menu buttons or send the following commands to interact with it:

- `/start` - Start the bot, sync/register your account, and show the home reply keyboard.
- `/help` - View usage guide, commands, and formatting rules.
- `/profile` - View your profile, including your database user ID, saved cars list, wishlist, and recent recommendation search history.
- `/wishlist` - View your saved wishlist items in an interactive card interface.
- `/settings` - Access the settings panel to change language (English/Hindi), theme (Dark/Light), or notification preferences.
- `Search <car name>` - Search matching cars (e.g. `Search Creta`) to display photo, price, specs, and pros/cons summary.
- `Compare <car1> and <car2>` - Compare two models side-by-side with an AI-generated explanation (e.g. `Compare Creta and Seltos`).
- *Free Text Input* - Any other message automatically forwards to the AI Assistant router for interactive chat.
