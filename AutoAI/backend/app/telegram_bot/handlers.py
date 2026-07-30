import re
import traceback
from typing import Optional
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import TelegramError

from . import api, keyboards, states, utils
from .logger import log_activity, logger

# ----------------------------------------------------------------------
# Helper to get db_user_id and handle token
# ----------------------------------------------------------------------
async def get_or_sync_db_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """
    Ensure the user is synced with the backend and return their database user ID.
    """
    telegram_id = update.effective_user.id
    db_user_id = context.user_data.get("db_user_id")
    
    if db_user_id:
        return db_user_id
        
    try:
        res = await api.sync_user(telegram_id)
        token = res.get("access_token")
        if token:
            context.user_data["access_token"] = token
            db_user_id = utils.decode_user_id_from_token(token)
            context.user_data["db_user_id"] = db_user_id
            return db_user_id
    except Exception as e:
        logger.error(f"Error syncing user {telegram_id}: {e}")
        
    return None

# ----------------------------------------------------------------------
# Start & General Commands
# ----------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start command handler: Registers user and displays the welcome message and main menu.
    """
    await utils.send_typing_action(update, context)
    telegram_id = update.effective_user.id
    
    # Trigger user sync in background
    db_user_id = await get_or_sync_db_user(update, context)
    
    # Set default settings if not exists
    if "lang" not in context.user_data:
        context.user_data["lang"] = "en"
        context.user_data["theme"] = "dark"
        context.user_data["notify"] = True
        context.user_data["recommendation_history"] = []
    
    welcome_text = (
        "Welcome to <b>AutoAI</b> 🚗\n"
        "Your Personal AI Car Buying Assistant\n\n"
        "I can help you search, compare, wishlist, and get AI recommendations for your next car purchase!\n\n"
        "Use the buttons below to begin."
    )
    
    await update.message.reply_html(
        welcome_text,
        reply_markup=keyboards.get_home_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Help command handler.
    """
    help_text = (
        "❓ <b>How to use AutoAI Bot:</b>\n\n"
        "🚗 <b>Recommend Car</b>: Start a multi-step recommendation questionnaire to find the best car matching your criteria.\n"
        "🔍 <b>Search Car</b>: Click the button and type <code>Search Creta</code> (or search from anywhere by typing the command directly) to search details, specs, and AI summaries.\n"
        "⚖ <b>Compare Cars</b>: Type <code>Compare Creta and Seltos</code> to compare two cars head-to-head.\n"
        "❤️ <b>Wishlist</b>: View your saved cars or remove items.\n"
        "🤖 <b>AI Assistant</b>: Chat naturally with the AI regarding specifications, reviews, or recommendations.\n"
        "👤 <b>My Profile</b>: View your information, wishlist, saved cars, and recommendation history.\n"
        "⚙ <b>Settings</b>: Toggle interface language, theme, and notification preferences.\n\n"
        "<i>Simply type any text to speak with the AI Chat assistant at any time!</i>"
    )
    await update.message.reply_html(help_text)

# ----------------------------------------------------------------------
# Settings Handler
# ----------------------------------------------------------------------
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Settings command or menu click.
    """
    lang = context.user_data.get("lang", "en")
    theme = context.user_data.get("theme", "dark")
    notify = context.user_data.get("notify", True)
    
    await update.message.reply_html(
        "⚙ <b>AutoAI Settings Panel</b>\n\nConfigure your preferences below:",
        reply_markup=keyboards.get_settings_keyboard(lang, theme, notify)
    )

async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles inline callback settings changes.
    """
    query = update.callback_query
    await query.answer()
    
    data = query.data
    lang = context.user_data.get("lang", "en")
    theme = context.user_data.get("theme", "dark")
    notify = context.user_data.get("notify", True)
    
    if data == "settings_toggle_lang":
        context.user_data["lang"] = "hi" if lang == "en" else "en"
    elif data == "settings_toggle_theme":
        context.user_data["theme"] = "light" if theme == "dark" else "dark"
    elif data == "settings_toggle_notify":
        context.user_data["notify"] = not notify
    elif data == "settings_back_home":
        await query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Returned to Home Menu.",
            reply_markup=keyboards.get_home_keyboard()
        )
        return
        
    # Re-read and update settings UI
    lang = context.user_data.get("lang", "en")
    theme = context.user_data.get("theme", "dark")
    notify = context.user_data.get("notify", True)
    
    await query.edit_message_reply_markup(
        reply_markup=keyboards.get_settings_keyboard(lang, theme, notify)
    )

# ----------------------------------------------------------------------
# Profile Handler
# ----------------------------------------------------------------------
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays user profile metadata, favorites, wishlist, and search history.
    """
    await utils.send_typing_action(update, context)
    telegram_id = update.effective_user.id
    
    db_user_id = await get_or_sync_db_user(update, context)
    if not db_user_id:
        await update.message.reply_html("⚠ Backend unavailable. Could not fetch profile.")
        return
        
    try:
        # Fetch Favorites/Saved Cars
        favs = await api.get_favorites(telegram_id, db_user_id)
        fav_names = [f"• {car['brand']} {car['model']}" for car in favs] if favs else ["No saved cars yet."]
        
        # Fetch Wishlist
        wishlist = await api.get_wishlist(telegram_id)
        wishlist_names = [f"• {car['brand']} {car['model']}" for car in wishlist] if wishlist else ["Wishlist is empty."]
        
        # Recommendation History from local state
        rec_history = context.user_data.get("recommendation_history", [])
        history_names = [f"• {item}" for item in rec_history[-5:]] if rec_history else ["No recommendation history."]
        
        profile_text = (
            f"👤 <b>My Profile (ID: telegram_{telegram_id})</b>\n\n"
            f"🚗 <b>Saved Cars (Favorites):</b>\n" + "\n".join(fav_names) + "\n\n"
            f"❤️ <b>Wishlist:</b>\n" + "\n".join(wishlist_names) + "\n\n"
            f"📜 <b>Recent Recommendations:</b>\n" + "\n".join(history_names)
        )
        await update.message.reply_html(profile_text)
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        await update.message.reply_html("⚠ Server unavailable. Please try again later.")

# ----------------------------------------------------------------------
# Wishlist Handlers
# ----------------------------------------------------------------------
async def wishlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the user's wishlist from `/wishlist/`.
    """
    await utils.send_typing_action(update, context)
    telegram_id = update.effective_user.id
    
    try:
        wishlist = await api.get_wishlist(telegram_id)
        if not wishlist:
            await update.message.reply_html("❤️ <b>Your Wishlist</b> is currently empty.")
            return
            
        await update.message.reply_html(f"❤️ <b>Your Wishlist ({len(wishlist)} items):</b>")
        for item in wishlist:
            price_lakhs = item['price'] / 100_000.0
            wishlist_id = item['id']
            car_id = item['car_id']
            
            caption = (
                f"🚗 <b>{item['brand']} {item['model']}</b>\n"
                f"Variant: {item['variant']}\n"
                f"💰 Price: ₹{price_lakhs:.2f} Lakh"
            )
            
            # Send photo for each wishlist item
            if item.get("image"):
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=item["image"],
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=keyboards.get_wishlist_card_keyboard(wishlist_id, car_id)
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=keyboards.get_wishlist_card_keyboard(wishlist_id, car_id)
                )
    except Exception as e:
        logger.error(f"Error loading wishlist: {e}")
        await update.message.reply_html("⚠ Server unavailable. Please try again later.")

async def wishlist_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles adding/removing wishlist items from inline clicks.
    """
    query = update.callback_query
    await query.answer()
    
    data = query.data
    telegram_id = update.effective_user.id
    db_user_id = await get_or_sync_db_user(update, context)
    
    if data.startswith("wishlist_add_"):
        car_id = int(data.split("_")[2])
        try:
            # 1. Add to wishlist
            await api.add_to_wishlist(telegram_id, car_id)
            # 2. Add to backend Favorites / Saved Cars table as well
            if db_user_id:
                await api.add_favorite(telegram_id, db_user_id, car_id)
                
            # Find the new wishlist ID to update button
            wishlist = await api.get_wishlist(telegram_id)
            wishlist_id = None
            for item in wishlist:
                if item['car_id'] == car_id:
                    wishlist_id = item['id']
                    break
                    
            await query.edit_message_reply_markup(
                reply_markup=keyboards.get_recommendation_card_keyboard(car_id, wishlist_id)
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❤️ Car added to your Wishlist & Saved Cars!"
            )
        except Exception as e:
            logger.error(f"Error adding to wishlist: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠ Failed to save car to wishlist."
            )
            
    elif data.startswith("wishlist_rem_"):
        parts = data.split("_")
        wishlist_id = int(parts[2])
        car_id = int(parts[3])
        try:
            # 1. Remove from wishlist
            await api.remove_from_wishlist(telegram_id, wishlist_id)
            # 2. Remove from backend Favorites / Saved Cars table
            if db_user_id:
                await api.delete_favorite(telegram_id, db_user_id, car_id)
                
            # Check if this was clicked from a recommendation card or wishlist screen
            if "rec_next" in str(query.message.reply_markup):
                await query.edit_message_reply_markup(
                    reply_markup=keyboards.get_recommendation_card_keyboard(car_id, None)
                )
            else:
                # If clicked from wishlist screen, delete the message card
                await query.message.delete()
                
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="💔 Car removed from wishlist."
            )
        except Exception as e:
            logger.error(f"Error removing from wishlist: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠ Failed to remove car from wishlist."
            )

# ----------------------------------------------------------------------
# Comparison Flow Handler
# ----------------------------------------------------------------------
async def compare_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggers comparison setup from the recommendation card inline button.
    """
    query = update.callback_query
    await query.answer()
    
    car_id = int(query.data.split("_")[2])
    
    # Store recommendation lists to find car model
    recs = context.user_data.get("recommendations", [])
    car_model = None
    for car in recs:
        if car['id'] == car_id:
            car_model = f"{car['brand']} {car['model']}"
            break
            
    if not car_model:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠ Could not find car details. Please type <code>Compare &lt;Car1&gt; and &lt;Car2&gt;</code> to compare manually."
        )
        return
        
    context.user_data["compare_first_car"] = car_model
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"⚖ Comparing <b>{car_model}</b>.\n\nWhich car would you like to compare it with?\n<i>(Type the name of the second car, e.g. Seltos)</i>",
        parse_mode="HTML"
    )
    
    # Save the target comparison state
    context.user_data["bot_state"] = states.STATE_COMPARE_WAITING

async def handle_comparison_second_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receives the second car name text in comparison flow.
    """
    await utils.send_typing_action(update, context)
    telegram_id = update.effective_user.id
    car1 = context.user_data.get("compare_first_car")
    car2 = update.message.text.strip()
    
    # Reset comparison state
    context.user_data["bot_state"] = None
    
    if not car1:
        await update.message.reply_html("⚠ No initial car found to compare. Please try comparison from a car card.")
        return
        
    try:
        res = await api.compare_cars(telegram_id, car1, car2)
        c1 = res["car1"]
        c2 = res["car2"]
        explanation = res["explanation"]
        
        comparison_html = (
            f"⚖ <b>Comparison Card: {c1['brand']} {c1['model']} vs {c2['brand']} {c2['model']}</b>\n\n"
            f"🚘 <b>{c1['brand']} {c1['model']} ({c1['variant']})</b>\n"
            f"• 💰 Price: ₹{c1['ex_showroom_price']/100000.0:.2f} Lakh\n"
            f"• ⛽ Fuel: {c1['fuel_type']} | ⚙ Trans: {c1['transmission']}\n"
            f"• 🛣 Mileage: {c1['mileage']} km/l | ⭐ Safety: {c1['safety_rating']}/5\n\n"
            f"🚘 <b>{c2['brand']} {c2['model']} ({c2['variant']})</b>\n"
            f"• 💰 Price: ₹{c2['ex_showroom_price']/100000.0:.2f} Lakh\n"
            f"• ⛽ Fuel: {c2['fuel_type']} | ⚙ Trans: {c2['transmission']}\n"
            f"• 🛣 Mileage: {c2['mileage']} km/l | ⭐ Safety: {c2['safety_rating']}/5\n\n"
            f"🤖 <b>AI Comparison Summary:</b>\n"
            f"{utils.markdown_to_html(explanation)}"
        )
        
        await update.message.reply_html(comparison_html)
    except Exception as e:
        logger.error(f"Error comparing cars: {e}")
        await update.message.reply_html("⚠ Car comparison failed. One or both car models could not be found.")

async def compare_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles regex matched compare commands like 'Compare Creta and Seltos'.
    """
    await utils.send_typing_action(update, context)
    telegram_id = update.effective_user.id
    
    text = update.message.text.strip()
    match = re.search(r'(?i)^compare\s+(.+?)\s+and\s+(.+)$', text)
    if not match:
        await update.message.reply_html("⚠ Invalid format. Please use: <code>Compare Creta and Seltos</code>")
        return
        
    car1, car2 = match.group(1).strip(), match.group(2).strip()
    try:
        res = await api.compare_cars(telegram_id, car1, car2)
        c1 = res["car1"]
        c2 = res["car2"]
        explanation = res["explanation"]
        
        comparison_html = (
            f"⚖ <b>Comparison Card: {c1['brand']} {c1['model']} vs {c2['brand']} {c2['model']}</b>\n\n"
            f"🚘 <b>{c1['brand']} {c1['model']} ({c1['variant']})</b>\n"
            f"• 💰 Price: ₹{c1['ex_showroom_price']/100000.0:.2f} Lakh\n"
            f"• ⛽ Fuel: {c1['fuel_type']} | ⚙ Trans: {c1['transmission']}\n"
            f"• 🛣 Mileage: {c1['mileage']} km/l | ⭐ Safety: {c1['safety_rating']}/5\n\n"
            f"🚘 <b>{c2['brand']} {c2['model']} ({c2['variant']})</b>\n"
            f"• 💰 Price: ₹{c2['ex_showroom_price']/100000.0:.2f} Lakh\n"
            f"• ⛽ Fuel: {c2['fuel_type']} | ⚙ Trans: {c2['transmission']}\n"
            f"• 🛣 Mileage: {c2['mileage']} km/l | ⭐ Safety: {c2['safety_rating']}/5\n\n"
            f"🤖 <b>AI Comparison Summary:</b>\n"
            f"{utils.markdown_to_html(explanation)}"
        )
        await update.message.reply_html(comparison_html)
    except Exception as e:
        logger.error(f"Compare failed: {e}")
        await update.message.reply_html("⚠ Compare failed. Make sure both cars exist in the database.")

# ----------------------------------------------------------------------
# Search Car Handler
# ----------------------------------------------------------------------
async def search_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles regex matched search commands like 'Search Creta'.
    """
    await utils.send_typing_action(update, context)
    telegram_id = update.effective_user.id
    
    text = update.message.text.strip()
    match = re.search(r'(?i)^search\s+(.+)$', text)
    if not match:
        await update.message.reply_html("🔍 Search help: Please type <code>Search Creta</code> to search for a car.")
        return
        
    query_str = match.group(1).strip()
    try:
        cars = await api.search(telegram_id, query_str)
        if not cars:
            await update.message.reply_html(f"🔍 No cars found matching '<b>{query_str}</b>'.")
            return
            
        # Display the top 3 matching cars to avoid spamming the user
        await update.message.reply_html(f"🔍 <b>Top {min(len(cars), 3)} search results for '{query_str}':</b>")
        
        for car in cars[:3]:
            price_lakhs = car['ex_showroom_price'] / 100_000.0
            
            # Format Pros & Cons
            pros_str = car.get("pros", "Comfortable, premium features.")
            cons_str = car.get("cons", "Higher price on upper variants.")
            
            caption = (
                f"🚗 <b>{car['brand']} {car['model']}</b>\n"
                f"Variant: {car['variant']} | Body: {car.get('body_type', 'N/A')}\n"
                f"💰 Price: ₹{price_lakhs:.2f} Lakh (Ex-Showroom)\n"
                f"⛽ Fuel: {car['fuel_type']} | ⚙ Trans: {car['transmission']}\n"
                f"🛣 Mileage: {car['mileage']} km/l | ⭐ Safety: {car['safety_rating']}/5\n\n"
                f"🤖 <b>AI Summary:</b>\n"
                f"👍 <b>Pros:</b> {pros_str}\n"
                f"👎 <b>Cons:</b> {cons_str}"
            )
            
            # Check if this car is already wishlisted
            wishlist = await api.get_wishlist(telegram_id)
            wishlist_id = None
            for item in wishlist:
                if item['car_id'] == car['id']:
                    wishlist_id = item['id']
                    break
                    
            if car.get("image_url"):
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=car["image_url"],
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=keyboards.get_recommendation_card_keyboard(car["id"], wishlist_id)
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=keyboards.get_recommendation_card_keyboard(car["id"], wishlist_id)
                )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        await update.message.reply_html("⚠ Search request failed. Please try again later.")

# ----------------------------------------------------------------------
# Recommendation Questionnaire Conversation Flow
# ----------------------------------------------------------------------
async def recommend_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point of the recommendation flow.
    """
    await utils.send_typing_action(update, context)
    context.user_data["recommendation_setup"] = {}
    
    await update.message.reply_html(
        "🚗 <b>AutoAI Recommendation Engine</b>\n\n"
        "Let's find the best car for you! I will ask you a few questions.\n\n"
        "💰 <b>1. What is your maximum budget?</b>\n"
        "(Examples: <code>15 Lakhs</code>, <code>12.5L</code>, <code>850000</code>)",
        reply_markup=ReplyKeyboardRemove()
    )
    return states.STATE_BUDGET

async def recommend_budget_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Captures budget value.
    """
    text = update.message.text.strip()
    try:
        budget = utils.parse_budget(text)
        context.user_data["recommendation_setup"]["budget"] = budget
        
        budget_lakhs = budget / 100_000.0
        await update.message.reply_html(
            f"Budget set to: <b>₹{budget_lakhs:.2f} Lakh</b>\n\n"
            f"⛽ <b>2. Choose your preferred fuel type:</b>",
            reply_markup=keyboards.get_fuel_keyboard()
        )
        return states.STATE_FUEL
    except ValueError as e:
        await update.message.reply_html(
            f"⚠ <i>{e}</i>\n\n"
            f"Please enter your budget as a valid number (e.g. 12 Lakhs)."
        )
        return states.STATE_BUDGET

async def recommend_fuel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Captures fuel selection callback.
    """
    query = update.callback_query
    await query.answer()
    
    fuel_map = {
        "fuel_petrol": "Petrol",
        "fuel_diesel": "Diesel",
        "fuel_cng": "CNG",
        "fuel_electric": "Electric"
    }
    fuel = fuel_map.get(query.data, "Petrol")
    context.user_data["recommendation_setup"]["fuel_type"] = fuel
    
    await query.edit_message_text(
        text=f"Fuel Preference: <b>{fuel}</b>",
        parse_mode="HTML"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⚙ <b>3. Choose your preferred transmission:</b>",
        reply_markup=keyboards.get_transmission_keyboard()
    )
    return states.STATE_TRANSMISSION

async def recommend_transmission_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Captures transmission selection callback.
    """
    query = update.callback_query
    await query.answer()
    
    trans_map = {
        "trans_manual": "Manual",
        "trans_automatic": "Automatic"
    }
    trans = trans_map.get(query.data, "Manual")
    context.user_data["recommendation_setup"]["transmission"] = trans
    
    await query.edit_message_text(
        text=f"Transmission Preference: <b>{trans}</b>",
        parse_mode="HTML"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🚗 <b>4. Choose your preferred body type:</b>",
        reply_markup=keyboards.get_body_type_keyboard()
    )
    return states.STATE_BODY_TYPE

async def recommend_body_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Captures body type callback.
    """
    query = update.callback_query
    await query.answer()
    
    body_map = {
        "body_hatchback": "Hatchback",
        "body_suv": "SUV",
        "body_sedan": "Sedan",
        "body_muv": "MUV",
        "body_any": None
    }
    body = body_map.get(query.data)
    context.user_data["recommendation_setup"]["body_type"] = body
    
    body_label = body if body else "Any"
    await query.edit_message_text(
        text=f"Body Style: <b>{body_label}</b>",
        parse_mode="HTML"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👥 <b>5. How many family members (seating capacity)?</b>",
        reply_markup=keyboards.get_family_keyboard()
    )
    return states.STATE_FAMILY_MEMBERS

async def recommend_family_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Captures family seating callback.
    """
    query = update.callback_query
    await query.answer()
    
    seats_map = {
        "seating_4": 4,
        "seating_5": 5,
        "seating_7": 7,
        "seating_8": 8
    }
    seats = seats_map.get(query.data, 5)
    context.user_data["recommendation_setup"]["family_members"] = seats
    
    await query.edit_message_text(
        text=f"Seating Capacity: <b>{seats} Seats</b>",
        parse_mode="HTML"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🛣 <b>6. Where will you drive the car the most?</b>",
        reply_markup=keyboards.get_city_highway_keyboard()
    )
    return states.STATE_CITY_HIGHWAY

async def recommend_city_highway_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Finalizes the inputs and requests recommendations from backend.
    """
    query = update.callback_query
    await query.answer()
    
    drive_data = query.data
    city_drive = True
    highway_drive = False
    
    if drive_data == "drive_city":
        city_drive = True
        highway_drive = False
        drive_label = "City Drive Only"
    elif drive_data == "drive_highway":
        city_drive = False
        highway_drive = True
        drive_label = "Highway Drive Only"
    else:
        city_drive = True
        highway_drive = True
        drive_label = "Both City & Highway"
        
    await query.edit_message_text(
        text=f"Usage Preference: <b>{drive_label}</b>",
        parse_mode="HTML"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔄 <i>Calculating best car recommendations...</i>",
        parse_mode="HTML"
    )
    
    # Run recommendation fetch
    telegram_id = update.effective_user.id
    setup = context.user_data["recommendation_setup"]
    
    try:
        recs = await api.recommend(
            user_id=telegram_id,
            budget=setup["budget"],
            fuel_type=setup["fuel_type"],
            transmission=setup["transmission"],
            family_members=setup["family_members"],
            body_type=setup["body_type"],
            city_drive=city_drive,
            highway_drive=highway_drive
        )
        
        if not recs:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ No cars matched your criteria. Please start again with a higher budget or different selections.",
                reply_markup=keyboards.get_home_keyboard()
            )
            return ConversationHandler.END
            
        context.user_data["recommendations"] = recs
        context.user_data["rec_index"] = 0
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🚗 <b>Found {len(recs)} matching recommendations!</b>",
            parse_mode="HTML"
        )
        
        # Display the first recommended car
        await display_recommendation(update, context)
    except Exception as e:
        logger.error(f"Recommendation API request failed: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠ Server unavailable.\nPlease try again later.",
            reply_markup=keyboards.get_home_keyboard()
        )
        
    return ConversationHandler.END

async def display_recommendation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Renders the current recommended car card using the list and current index.
    """
    chat_id = update.effective_chat.id
    recs = context.user_data.get("recommendations", [])
    idx = context.user_data.get("rec_index", 0)
    telegram_id = update.effective_user.id
    
    if idx >= len(recs):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🏁 <b>No more recommendations!</b>\n\nStart a new search or recommend flow to find more cars.",
            parse_mode="HTML",
            reply_markup=keyboards.get_home_keyboard()
        )
        return
        
    car = recs[idx]
    
    # Store this car model into local recommendation history list (max 5 items)
    car_name = f"{car['brand']} {car['model']}"
    history = context.user_data.get("recommendation_history", [])
    if car_name not in history:
        history.append(car_name)
        if len(history) > 5:
            history.pop(0)
        context.user_data["recommendation_history"] = history
        
    # Check if the car is currently in user's wishlist
    wishlist_id = None
    try:
        wishlist = await api.get_wishlist(telegram_id)
        for item in wishlist:
            if item['car_id'] == car['id']:
                wishlist_id = item['id']
                break
    except Exception as e:
        logger.error(f"Wishlist check failed: {e}")
        
    price_lakhs = car['price'] / 100_000.0
    reasons_bullet = "\n".join([f"• {r}" for r in car.get("reasons", [])])
    
    card_html = (
        f"🚗 <b>{car['brand']} {car['model']}</b>\n"
        f"Variant: {car['variant']}\n"
        f"💰 Price: ₹{price_lakhs:.2f} Lakh\n"
        f"⛽ Fuel: {car['fuel_type']} | ⚙ Trans: {car['transmission']}\n"
        f"🛣 Mileage: {car['mileage']} km/l | ⭐ Safety: {car['safety_rating']}/5\n"
        f"🔌 Specs: {car['engine_cc']} cc | {car['power']} bhp\n\n"
        f"🤖 <b>AI recommendation reasons:</b>\n"
        f"{reasons_bullet}"
    )
    
    image = car.get("image")
    if image:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=image,
            caption=card_html,
            parse_mode="HTML",
            reply_markup=keyboards.get_recommendation_card_keyboard(car['id'], wishlist_id)
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=card_html,
            parse_mode="HTML",
            reply_markup=keyboards.get_recommendation_card_keyboard(car['id'], wishlist_id)
        )

async def recommend_next_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles recommendation card 'Next Car' button click.
    """
    query = update.callback_query
    await query.answer()
    
    idx = context.user_data.get("rec_index", 0)
    context.user_data["rec_index"] = idx + 1
    
    # Delete the previous photo/message card to keep chat clean
    try:
        await query.message.delete()
    except TelegramError:
        pass
        
    await display_recommendation(update, context)

# ----------------------------------------------------------------------
# AI Chat Fallback Handler
# ----------------------------------------------------------------------
async def ai_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles any free text message. If the user is in a state, delegates to that state.
    Otherwise, forwards the message as free text to the AI Assistant API (`/chat/`).
    """
    # 1. State check
    bot_state = context.user_data.get("bot_state")
    if bot_state == states.STATE_COMPARE_WAITING:
        await handle_comparison_second_car(update, context)
        return
        
    # Standard text query to AI chat
    await utils.send_typing_action(update, context)
    telegram_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # Handle home button click simulations
    if message_text == "🚗 Recommend Car":
        # Simulate conversation trigger
        await recommend_start_handler(update, context)
        return
    elif message_text == "🔍 Search Car":
        await update.message.reply_html(
            "🔍 <b>AutoAI Car Search</b>\n\n"
            "Please type <code>Search &lt;car model name&gt;</code> to look up a car details.\n\n"
            "Example:\n<code>Search Creta</code>"
        )
        return
    elif message_text == "⚖ Compare Cars":
        await update.message.reply_html(
            "⚖ <b>AutoAI Car Comparison</b>\n\n"
            "Type <code>Compare &lt;Car1&gt; and &lt;Car2&gt;</code> to run an AI side-by-side comparison.\n\n"
            "Example:\n<code>Compare Creta and Seltos</code>"
        )
        return
    elif message_text == "❤️ Wishlist":
        await wishlist_command(update, context)
        return
    elif message_text == "🤖 AI Assistant":
        await update.message.reply_html(
            "🤖 <b>AI Assistant Mode</b>\n\n"
            "Ask me anything about car specifications, features, or buying suggestions. I am listening!"
        )
        return
    elif message_text == "👤 My Profile":
        await profile_command(update, context)
        return
    elif message_text == "⚙ Settings":
        await settings_command(update, context)
        return
    elif message_text == "❓ Help":
        await help_command(update, context)
        return

    # Call AI chat service
    try:
        session_id = f"telegram_{telegram_id}"
        res = await api.chat(telegram_id, message_text, session_id)
        ai_reply = res.get("ai_response", "AI response empty.")
        
        # Render markdown converted safe HTML
        await update.message.reply_html(utils.markdown_to_html(ai_reply))
    except Exception as e:
        logger.error(f"AI chat request failed: {e}")
        await update.message.reply_html("⚠ Server unavailable. Please try again later.")

# ----------------------------------------------------------------------
# Cancel Conversation Handler
# ----------------------------------------------------------------------
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Cancels the recommendation survey and displays the home menu.
    """
    await update.message.reply_html(
        "❌ Recommendation flow cancelled.",
        reply_markup=keyboards.get_home_keyboard()
    )
    return ConversationHandler.END

async def rec_home_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles recommendation card 'Home' button click.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        await query.message.delete()
    except Exception:
        pass
        
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Returned to Home Menu.",
        reply_markup=keyboards.get_home_keyboard()
    )
