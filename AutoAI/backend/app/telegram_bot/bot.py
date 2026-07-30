import sys
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

from . import config, handlers, states
from .logger import logger

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a friendly warning to the user."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠ An unexpected error occurred. Please try again later."
            )
        except Exception:
            pass

def main():
    """Start the bot."""
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not configured in environment variables or .env!")
        print("CRITICAL ERROR: TELEGRAM_BOT_TOKEN is missing. Please set it in your .env file.")
        sys.exit(1)
        
    logger.info("Initializing AutoAI Telegram Bot...")
    
    # Build Application
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # 1. Recommendation flow Conversation Handler
    recommend_conv = ConversationHandler(
        entry_points=[
            CommandHandler("recommend", handlers.recommend_start_handler),
            MessageHandler(filters.Regex(r'^🚗 Recommend Car$'), handlers.recommend_start_handler)
        ],
        states={
            states.STATE_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.recommend_budget_handler)],
            states.STATE_FUEL: [CallbackQueryHandler(handlers.recommend_fuel_handler, pattern=r'^fuel_')],
            states.STATE_TRANSMISSION: [CallbackQueryHandler(handlers.recommend_transmission_handler, pattern=r'^trans_')],
            states.STATE_BODY_TYPE: [CallbackQueryHandler(handlers.recommend_body_type_handler, pattern=r'^body_')],
            states.STATE_FAMILY_MEMBERS: [CallbackQueryHandler(handlers.recommend_family_handler, pattern=r'^seating_')],
            states.STATE_CITY_HIGHWAY: [CallbackQueryHandler(handlers.recommend_city_highway_handler, pattern=r'^drive_')]
        },
        fallbacks=[
            CommandHandler("cancel", handlers.cancel_handler),
            MessageHandler(filters.Regex(r'^cancel$'), handlers.cancel_handler)
        ],
        allow_reentry=True
    )
    
    # 2. Add handlers in logical order
    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("settings", handlers.settings_command))
    app.add_handler(CommandHandler("profile", handlers.profile_command))
    app.add_handler(CommandHandler("wishlist", handlers.wishlist_command))
    
    # Register Conversation Handler
    app.add_handler(recommend_conv)
    
    # Callback query handlers for UI buttons
    app.add_handler(CallbackQueryHandler(handlers.settings_callback_handler, pattern=r'^settings_'))
    app.add_handler(CallbackQueryHandler(handlers.wishlist_callback_handler, pattern=r'^wishlist_'))
    app.add_handler(CallbackQueryHandler(handlers.compare_callback_handler, pattern=r'^compare_start_'))
    app.add_handler(CallbackQueryHandler(handlers.recommend_next_callback_handler, pattern=r'^rec_next$'))
    app.add_handler(CallbackQueryHandler(handlers.rec_home_callback_handler, pattern=r'^rec_home$'))
    
    # Regex command pattern handlers
    app.add_handler(MessageHandler(filters.Regex(r'(?i)^search\s+(.+)$'), handlers.search_command_handler))
    app.add_handler(MessageHandler(filters.Regex(r'(?i)^compare\s+(.+?)\s+and\s+(.+)$'), handlers.compare_command_handler))
    
    # Fallback to AI chat for any other text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.ai_chat_handler))
    
    # Global error handler
    app.add_error_handler(error_handler)
    
    # Start long polling
    logger.info("AutoAI Bot is polling for updates...")
    app.run_polling()

if __name__ == "__main__":
    main()
