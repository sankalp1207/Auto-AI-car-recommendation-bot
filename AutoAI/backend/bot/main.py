import logging
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from telegram.error import InvalidToken, Conflict, NetworkError, TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

from bot.config import TELEGRAM_BOT_TOKEN, BACKEND_URL, validate_config
from bot.handlers import (
    start_command,
    help_command,
    cars_command,
    upcoming_command,
    car_details_command,
    search_command,
    search_query_received,
    recommend_command,
    compare_command,
    compare_car1_received,
    compare_car2_received,
    wishlist_command,
    favorites_command,
    chat_message_handler,
    generic_callback_handler,
    cancel_conversation,
    error_handler,
    SEARCH_QUERY,
    COMPARE_CAR1,
    COMPARE_CAR2,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("AutoAIBot")


def build_bot_application():
    """Build and assemble the Telegram bot application with all handlers."""
    if not validate_config():
        sys.exit(1)

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # 1. Search Conversation Handler
    search_conv = ConversationHandler(
        entry_points=[
            CommandHandler("search", search_command),
        ],
        states={
            SEARCH_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_query_received),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
        ],
    )

    # 2. Compare Conversation Handler
    compare_conv = ConversationHandler(
        entry_points=[
            CommandHandler("compare", compare_command),
        ],
        states={
            COMPARE_CAR1: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, compare_car1_received),
            ],
            COMPARE_CAR2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, compare_car2_received),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
        ],
    )

    # Register Conversation Handlers first
    app.add_handler(search_conv)
    app.add_handler(compare_conv)

    # Register Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cars", cars_command))
    app.add_handler(CommandHandler("upcoming", upcoming_command))
    app.add_handler(CommandHandler("car", car_details_command))
    app.add_handler(CommandHandler("details", car_details_command))
    app.add_handler(CommandHandler("recommend", recommend_command))
    app.add_handler(CommandHandler("wishlist", wishlist_command))
    app.add_handler(CommandHandler("favorites", favorites_command))

    # Register Callback Query Handler for inline keyboards
    app.add_handler(CallbackQueryHandler(generic_callback_handler))

    # Register Text Message Handler for free-form AI chat
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message_handler))

    # Register Global Error Handler
    app.add_error_handler(error_handler)

    return app


def main():
    """Entry point for the standalone AutoAI Telegram Bot."""
    print("=" * 60)
    print("       AutoAI Telegram Bot starting...")
    print(f"       Backend API Target: {BACKEND_URL}")
    print("=" * 60)

    if not validate_config():
        sys.exit(1)

    try:
        app = build_bot_application()
        print("Telegram bot polling started. Bot is active and listening for messages.")
        app.run_polling(drop_pending_updates=True)
    except InvalidToken:
        print("\n[ERROR] The provided TELEGRAM_BOT_TOKEN is invalid.", file=sys.stderr)
        print("Please verify the token with @BotFather in Telegram and update backend/.env.", file=sys.stderr)
        sys.exit(1)
    except Conflict:
        print("\n[ERROR] Telegram Conflict: Another instance of this bot is already running.", file=sys.stderr)
        print("Please terminate any other active bot polling processes before starting.", file=sys.stderr)
        sys.exit(1)
    except NetworkError as e:
        print(f"\n[ERROR] Network error while connecting to Telegram API: {e}", file=sys.stderr)
        print("Please check your internet connection and proxy settings.", file=sys.stderr)
        sys.exit(1)
    except TelegramError as e:
        print(f"\n[ERROR] Telegram API error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAutoAI Telegram Bot stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error running Telegram bot: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
