import logging
from typing import Dict, Any, List
import math
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from bot.api_client import api_client
from bot.keyboards import (
    get_main_menu_keyboard,
    get_car_pagination_keyboard,
    get_car_detail_keyboard,
    get_wishlist_keyboard,
    get_favorites_keyboard,
    get_rec_budget_keyboard,
    get_rec_fuel_keyboard,
    get_rec_trans_keyboard,
    get_rec_body_keyboard,
    get_rec_priority_keyboard,
)

logger = logging.getLogger("AutoAIBot.Handlers")

# Conversation States
SEARCH_QUERY = 1
COMPARE_CAR1 = 10
COMPARE_CAR2 = 11

import re

PAGE_SIZE = 5
MAX_TG_LEN = 4000
GREETING_PATTERN = re.compile(
    r'^(hi|hello|hey|greetings|hola|start|help|namaste|good\s+(morning|afternoon|evening))\b',
    re.IGNORECASE
)


def split_telegram_text(text: str, max_len: int = MAX_TG_LEN) -> List[str]:
    """Splits long message text safely within Telegram limits without breaking vehicle cards in the middle."""
    if not text or len(text) <= max_len:
        return [text] if text else [""]
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        # First preference: split between vehicle cards / paragraphs (\n\n)
        split_at = remaining.rfind("\n\n", 0, max_len)
        if split_at == -1 or split_at < max_len // 3:
            # Second preference: split at single line break (\n)
            split_at = remaining.rfind("\n", 0, max_len)
        if split_at == -1 or split_at < max_len // 3:
            # Third preference: split at word boundary
            split_at = remaining.rfind(" ", 0, max_len)
        if split_at == -1:
            split_at = max_len

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].strip()
    return chunks


async def safe_reply(target, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN):
    """Safely reply to user, splitting long messages and gracefully falling back if markdown fails."""
    msg_target = target.message if hasattr(target, "message") and target.message else target
    chunks = split_telegram_text(text)
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await msg_target.reply_text(chunk, reply_markup=markup, parse_mode=parse_mode)
        except Exception:
            # Fallback to plain text if markdown formatting failed
            await msg_target.reply_text(chunk, reply_markup=markup, parse_mode=None)


def format_inr(price: float | int | None) -> str:
    """Format numeric price into Indian numbering format (Lakh / Crore)."""
    if price is None or price == 0:
        return "TBD / Unannounced"
    price = float(price)
    if price >= 10000000:
        return f"₹{price / 10000000:.2f} Cr"
    elif price >= 100000:
        return f"₹{price / 100000:.2f} Lakh"
    return f"₹{price:,.0f}"


def format_car_card(car: Dict[str, Any], why_it_matches: str = None) -> str:
    """Format a detailed car specification card for Telegram."""
    brand = car.get("brand", "Unknown")
    model = car.get("model", "")
    variant = car.get("variant", "")
    status = (car.get("status") or "CURRENT").upper()
    is_upcoming = (status == "UPCOMING")

    price = car.get("price") or car.get("ex_showroom_price", 0)
    fuel = car.get("fuel_type") or car.get("fuel", "N/A")
    trans = car.get("transmission", "N/A")
    body = car.get("body_type", "N/A")
    mileage = car.get("mileage")
    power = car.get("power")
    torque = car.get("torque")
    engine = car.get("engine_cc")
    safety = car.get("safety_rating")
    seating = car.get("seating") or car.get("seating_capacity", "N/A")
    boot = car.get("boot_space")
    pros = car.get("pros")
    cons = car.get("cons")
    image_url = car.get("image_url")

    card = [f"🚗 *{brand} {model}* `{variant}`"]

    if is_upcoming:
        card.append("⏳ *UPCOMING VEHICLE — Expected Launch*")
        card.append("⚠️ _Not currently on sale. Specifications and prices are manufacturer estimates._")
        card.append("─" * 28)
        card.append(f"💰 *Expected Price:* {format_inr(price)} (Estimated)")
    else:
        card.append("─" * 28)
        card.append(f"💰 *Price:* {format_inr(price)} (Ex-Showroom)")

    card.append(f"⛽ *Fuel:* {fuel}")
    card.append(f"⚙️ *Transmission:* {trans}")
    card.append(f"👨‍👩‍👧‍👦 *Seating:* {seating} Seats")

    if safety is not None:
        try:
            stars = "⭐" * int(float(safety))
            card.append(f"⭐ *Safety:* {stars} ({safety}/5)")
        except (ValueError, TypeError):
            card.append(f"⭐ *Safety:* {safety}")
    else:
        card.append("⭐ *Safety:* Not Rated / Untested")

    card.append(f"🚘 *Body Type:* {body}")

    if engine or power or torque:
        card.append(f"🏎 *Specs:* {engine or 'N/A'} cc | {power or 'N/A'} bhp | {torque or 'N/A'} Nm")
    if mileage:
        card.append(f"📊 *Mileage:* {mileage} kmpl")
    if boot:
        card.append(f"🧳 *Boot Space:* {boot} Litres")

    if image_url and str(image_url).startswith("http"):
        card.append(f"🔗 [View Vehicle Image/Source]({image_url})")

    if why_it_matches:
        card.append(f"\n💡 *Why it matches:*\n{why_it_matches}")

    if pros and str(pros).strip() and str(pros).lower() != "nan":
        card.append(f"\n✅ *Pros:* {pros}")
    if cons and str(cons).strip() and str(cons).lower() != "nan":
        card.append(f"⚠️ *Cons:* {cons}")

    return "\n".join(card)


# ==========================================
# Command Handlers
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    welcome_text = (
        "👋 *Welcome to AutoAI — Your AI Car Expert* 🚗💨\n\n"
        "I am connected to our live database of *2,245 verified vehicles* from CarWale with intelligent search, recommendations, and AI insights.\n\n"
        "🌟 *What I can do:*\n"
        "• 🔍 *Search Cars:* Filter by budget, brand, fuel, transmission, seating\n"
        "• 🤖 *AI Recommendations:* Tailored suggestions based on your lifestyle\n"
        "• 🚗 *Browse Cars:* Explore our comprehensive catalog\n"
        "• 🔥 *Upcoming Cars:* Track announced & expected car launches\n"
        "• ⚖️ *Compare Cars:* Side-by-side spec comparison + AI insights\n"
        "• ❤️ *Wishlist:* Save your favorite models\n\n"
        "💡 *Try typing queries like:*\n"
        '• _"Find me an SUV under ₹15 lakh"_\n'
        '• _"Show automatic cars under ₹12 lakh"_\n'
        '• _"I need a 7-seater"_\n'
        '• _"Compare Thar and Scorpio"_\n'
        '• _"Which upcoming SUVs are worth waiting for?"_\n\n'
        "Tap a button below or type your question anytime:"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = (
        "🛠 *AutoAI Bot Command Reference:*\n\n"
        "• /start - Restart bot and show main menu\n"
        "• /cars - Browse all cars in the catalog\n"
        "• /search `<query>` - Search cars (e.g., `/search SUV under 15 Lakh`)\n"
        "• /recommend - Start AI recommendation questionnaire\n"
        "• /compare `<car1>` `<car2>` - Compare two cars\n"
        "• /wishlist - View your saved wishlist\n"
        "• /favorites - View your favorite cars\n"
        "• /help - Display this guide\n\n"
        "💡 *Tip:* You can also send natural language messages like:\n"
        '_"What is the best petrol automatic SUV under 20 lakh?"_'
    )
    await update.message.reply_text(
        help_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )


async def cars_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cars or '🚗 Browse Cars' button."""
    try:
        cars = await api_client.get_all_cars()
        if not cars:
            await update.message.reply_text(
                "ℹ️ No cars are currently available in the database.",
                reply_markup=get_main_menu_keyboard()
            )
            return

        total_pages = max(1, math.ceil(len(cars) / PAGE_SIZE))
        current_page = 1
        page_cars = cars[:PAGE_SIZE]

        text = (
            f"🚗 *AutoAI Car Catalog* (Total: {len(cars)} cars)\n\n"
            f"Page *{current_page}* of *{total_pages}*:\n"
            "Select any car below to inspect full specifications:"
        )

        reply_markup = get_car_pagination_keyboard(page_cars, current_page, total_pages)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error in cars_command: {e}")
        await update.message.reply_text("AutoAI is temporarily unavailable. Please try again in a moment.")


async def upcoming_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /upcoming or '🔥 Upcoming Cars' button."""
    try:
        cars = await api_client.search_cars(status="UPCOMING")
        if not cars:
            await update.message.reply_text(
                "ℹ️ No upcoming cars are currently listed in the database.",
                reply_markup=get_main_menu_keyboard()
            )
            return

        total_pages = max(1, math.ceil(len(cars) / PAGE_SIZE))
        current_page = 1
        page_cars = cars[:PAGE_SIZE]

        text = (
            f"🔥 *AutoAI Upcoming Cars & Expected Launches* (Total: {len(cars)} cars)\n\n"
            f"⏳ *Notice:* These vehicles are not yet on sale in India. Specifications and prices are manufacturer estimates.\n\n"
            f"Page *{current_page}* of *{total_pages}*:\n"
            "Select any car below to inspect expected specifications:"
        )

        reply_markup = get_car_pagination_keyboard(page_cars, current_page, total_pages, prefix="upcoming_page")
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

    except RuntimeError as e:
        logger.warning(f"Backend connectivity issue in upcoming_command: {e}")
        await safe_reply(
            update,
            "⚠️ AutoAI backend server is currently unreachable. Please make sure the backend is running and try again in a moment.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in upcoming_command: {e}")
        await update.message.reply_text("AutoAI is temporarily unavailable. Please try again in a moment.")


async def car_details_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /car <name_or_id> or /details <name_or_id>."""
    if not context.args:
        await update.message.reply_text(
            "ℹ️ Please specify a car model name or ID.\nExample: `/car Nexon` or `/car Creta`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    query = " ".join(context.args).strip()
    try:
        car = await api_client.get_car(query)
        if not car:
            # Try search fallback
            results = await api_client.search_cars(model=query)
            if not results:
                results = await api_client.search_cars(brand=query)
            if results:
                car = results[0]

        if car:
            card_text = format_car_card(car)
            reply_markup = get_car_detail_keyboard(int(car["id"]))
            await safe_reply(update, card_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                f"❌ Vehicle matching '_{query}_' was not found in our database.\nUse /search or /cars to browse available models.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
    except RuntimeError as e:
        logger.warning(f"Backend connectivity issue in car_details_command: {e}")
        await safe_reply(
            update,
            "⚠️ AutoAI backend server is currently unreachable. Please try again in a moment.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in car_details_command: {e}")
        await update.message.reply_text("AutoAI is temporarily unavailable. Please try again in a moment.")


# ==========================================
# Search Conversation Flow
# ==========================================

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /search or '🔎 Search Cars' button."""
    # Check if arguments were passed directly (e.g. /search Hyundai)
    if context.args:
        query = " ".join(context.args)
        await execute_search(update, query)
        return ConversationHandler.END

    await update.message.reply_text(
        "🔎 *AutoAI Search*\n\n"
        "What car or specifications are you looking for?\n"
        "_(e.g., 'Hyundai', 'SUV', 'Diesel', 'Automatic', or 'Under 15 Lakh')_\n\n"
        "Type /cancel to cancel search.",
        parse_mode=ParseMode.MARKDOWN
    )
    return SEARCH_QUERY


async def search_query_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process user search query from conversation."""
    query = update.message.text.strip()
    await execute_search(update, query)
    return ConversationHandler.END


async def execute_search(update: Update, query: str) -> None:
    """Execute search query against backend search API or chat parser."""
    try:
        # First attempt keyword matching on backend search endpoint
        cars = await api_client.search_cars(brand=query)
        if not cars:
            cars = await api_client.search_cars(model=query)
        if not cars:
            cars = await api_client.search_cars(fuel=query)
        if not cars:
            cars = await api_client.search_cars(body_type=query)

        # If direct search did not match, fallback to AI chat endpoint to parse & recommend
        if not cars:
            chat_result = await api_client.chat(query, session_id=f"search_{update.effective_user.id}")
            recs = chat_result.get("recommendations", [])
            ai_resp = chat_result.get("ai_response", "")

            if recs:
                msg = f"🔎 *Search Results for:* _{query}_\n\n"
                if ai_resp:
                    msg += f"🤖 {ai_resp}\n\n"
                msg += "Select a car to view details:"
                total_pages = max(1, math.ceil(len(recs) / PAGE_SIZE))
                reply_markup = get_car_pagination_keyboard(recs[:PAGE_SIZE], 1, total_pages)
                await safe_reply(update, msg, reply_markup=reply_markup)
                return
            else:
                await safe_reply(
                    update,
                    f"❌ No cars found matching '_{query}_'.\nTry searching with a brand name (e.g., Hyundai, Tata) or body type (SUV, Sedan).",
                    reply_markup=get_main_menu_keyboard()
                )
                return

        total_pages = max(1, math.ceil(len(cars) / PAGE_SIZE))
        msg = f"🔎 *Found {len(cars)} matching cars for:* _{query}_\n\nSelect a car to view details:"
        reply_markup = get_car_pagination_keyboard(cars[:PAGE_SIZE], 1, total_pages)
        await safe_reply(update, msg, reply_markup=reply_markup)

    except RuntimeError as e:
        logger.warning(f"Backend connectivity issue in execute_search: {e}")
        await safe_reply(
            update,
            "⚠️ AutoAI backend server is currently unreachable. Please make sure the backend is running and try again in a moment.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in execute_search: {e}")
        await safe_reply(update, "AutoAI is temporarily unavailable. Please try again in a moment.", reply_markup=get_main_menu_keyboard())


# ==========================================
# AI Recommendation Wizard
# ==========================================

async def recommend_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /recommend or '🤖 AI Recommendation' button."""
    context.user_data["rec_prefs"] = {}
    text = (
        "🤖 *AutoAI Recommendation Wizard*\n\n"
        "Let's find the perfect car for you in a few quick steps!\n\n"
        "*Step 1/5: What is your maximum budget?*"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=get_rec_budget_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=get_rec_budget_keyboard(), parse_mode=ParseMode.MARKDOWN)


async def handle_rec_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle recommendation wizard callback button presses."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "rec_cancel":
        await query.edit_message_text("❌ Recommendation wizard cancelled.")
        return

    prefs = context.user_data.setdefault("rec_prefs", {})

    # Step 1: Budget
    if data.startswith("rec_budget_"):
        budget_val = float(data.replace("rec_budget_", ""))
        prefs["budget"] = budget_val
        await query.edit_message_text(
            f"✅ Budget set: *{format_inr(budget_val)}*\n\n*Step 2/5: Preferred Fuel Type?*",
            reply_markup=get_rec_fuel_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

    # Step 2: Fuel
    elif data.startswith("rec_fuel_"):
        fuel_val = data.replace("rec_fuel_", "")
        if fuel_val != "any":
            prefs["fuel_type"] = fuel_val
        await query.edit_message_text(
            f"✅ Fuel preference: *{fuel_val.title()}*\n\n*Step 3/5: Preferred Transmission?*",
            reply_markup=get_rec_trans_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

    # Step 3: Transmission
    elif data.startswith("rec_trans_"):
        trans_val = data.replace("rec_trans_", "")
        if trans_val != "any":
            prefs["transmission"] = trans_val
        await query.edit_message_text(
            f"✅ Transmission: *{trans_val.title()}*\n\n*Step 4/5: Preferred Body Type?*",
            reply_markup=get_rec_body_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

    # Step 4: Body Type
    elif data.startswith("rec_body_"):
        body_val = data.replace("rec_body_", "")
        if body_val != "any":
            prefs["body_type"] = body_val
        await query.edit_message_text(
            f"✅ Body Type: *{body_val.title()}*\n\n*Step 5/5: Top Priority?*",
            reply_markup=get_rec_priority_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

    # Step 5: Priority & Calculation
    elif data.startswith("rec_prio_"):
        prio_val = data.replace("rec_prio_", "")
        if prio_val != "none":
            prefs["priority"] = prio_val

        await query.edit_message_text("⚙️ *Analyzing catalog and computing AI matching scores...*", parse_mode=ParseMode.MARKDOWN)

        try:
            recs = await api_client.recommend_cars(prefs)
            if not recs:
                await query.edit_message_text(
                    "❌ No cars found matching your exact filter criteria.\nTry running /recommend again with broader options.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            response_lines = [
                "🤖 *AutoAI Recommendation Results*\n",
                f"Based on your criteria ({format_inr(prefs.get('budget'))}, {prefs.get('fuel_type', 'Any Fuel')}, {prefs.get('transmission', 'Any Gearbox')}):\n"
            ]

            for idx, car in enumerate(recs[:5], 1):
                brand = car.get("brand", "")
                model = car.get("model", "")
                variant = car.get("variant", "")
                price = car.get("price") or car.get("ex_showroom_price", 0)
                score = car.get("score", 0)
                reasons = car.get("reasons", [])

                reasons_str = ", ".join(reasons[:3]) if reasons else "Matches your criteria"
                response_lines.append(f"*{idx}. {brand} {model}* ({variant})")
                response_lines.append(f"   💰 {format_inr(price)} | ⚡ Match Score: *{score:.0f}/100*")
                response_lines.append(f"   💡 _{reasons_str}_\n")

            response_lines.append("Select a car below for full details:")
            text = "\n".join(response_lines)
            total_pages = max(1, math.ceil(len(recs) / PAGE_SIZE))
            reply_markup = get_car_pagination_keyboard(recs[:PAGE_SIZE], 1, total_pages)

            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Error executing recommendation: {e}")
            await query.edit_message_text("AutoAI is temporarily unavailable. Please try again in a moment.")


# ==========================================
# Compare Conversation Flow
# ==========================================

async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /compare or '⚖️ Compare Cars' button."""
    if context.args and len(context.args) >= 2:
        car1 = context.args[0]
        car2 = context.args[1]
        await execute_comparison(update, car1, car2)
        return ConversationHandler.END

    await update.message.reply_text(
        "⚖️ *AutoAI Car Comparison*\n\n"
        "Please enter the name of the *first car* you want to compare:\n"
        "_(e.g., 'Creta', 'Nexon', 'Brezza')_\n\n"
        "Type /cancel to cancel.",
        parse_mode=ParseMode.MARKDOWN
    )
    return COMPARE_CAR1


async def compare_car1_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive first car name for comparison."""
    context.user_data["compare_car1"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ First car: *{context.user_data['compare_car1']}*\n\n"
        "Now enter the name of the *second car* to compare against:",
        parse_mode=ParseMode.MARKDOWN
    )
    return COMPARE_CAR2


async def compare_car2_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive second car name and run comparison."""
    car1 = context.user_data.get("compare_car1")
    car2 = update.message.text.strip()
    await execute_comparison(update, car1, car2)
    return ConversationHandler.END


async def execute_comparison(update: Update, car1_name: str, car2_name: str) -> None:
    """Fetch side-by-side comparison from backend."""
    try:
        result = await api_client.compare_cars(car1_name, car2_name)
        if not result:
            await update.message.reply_text(
                f"❌ Could not find matching cars for *{car1_name}* and/or *{car2_name}*.\nPlease check spellings or browse cars with /cars.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        c1 = result.get("car1", {})
        c2 = result.get("car2", {})
        explanation = result.get("explanation", "")

        def val(c, k, default="N/A"):
            v = c.get(k)
            return default if v is None else str(v)

        msg = (
            f"⚖️ *Comparison: {c1.get('brand', '')} {c1.get('model', '')} vs {c2.get('brand', '')} {c2.get('model', '')}*\n\n"
            f"```\n"
            f"{'Spec':<14} | {c1.get('model', 'Car 1')[:10]:<10} | {c2.get('model', 'Car 2')[:10]:<10}\n"
            f"{'-'*14}-+-{'-'*10}-+-{'-'*10}\n"
            f"{'Price':<14} | {format_inr(c1.get('price') or c1.get('ex_showroom_price')):<10} | {format_inr(c2.get('price') or c2.get('ex_showroom_price')):<10}\n"
            f"{'Fuel':<14} | {val(c1, 'fuel_type') or val(c1, 'fuel'):<10} | {val(c2, 'fuel_type') or val(c2, 'fuel'):<10}\n"
            f"{'Gearbox':<14} | {val(c1, 'transmission')[:10]:<10} | {val(c2, 'transmission')[:10]:<10}\n"
            f"{'Power':<14} | {val(c1, 'power') + ' bhp':<10} | {val(c2, 'power') + ' bhp':<10}\n"
            f"{'Torque':<14} | {val(c1, 'torque') + ' Nm':<10} | {val(c2, 'torque') + ' Nm':<10}\n"
            f"{'Mileage':<14} | {val(c1, 'mileage') + ' kmpl':<10} | {val(c2, 'mileage') + ' kmpl':<10}\n"
            f"{'Safety':<14} | {val(c1, 'safety_rating') + '/5':<10} | {val(c2, 'safety_rating') + '/5':<10}\n"
            f"{'Boot':<14} | {val(c1, 'boot_space') + ' L':<10} | {val(c2, 'boot_space') + ' L':<10}\n"
            f"```\n\n"
        )

        if explanation and explanation != "AI Comparison currently unavailable.":
            msg += f"🤖 *AI Summary & Verdict:*\n{explanation}"

        await update.message.reply_text(
            msg,
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.error(f"Error in execute_comparison: {e}")
        await update.message.reply_text("AutoAI is temporarily unavailable. Please try again in a moment.")


# ==========================================
# Wishlist Handlers
# ==========================================

async def wishlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /wishlist or '❤️ Wishlist' button."""
    try:
        items = await api_client.get_wishlist()
        if not items:
            await update.message.reply_text(
                "❤️ *Your Wishlist is Empty*\n\nBrowse cars with /cars and tap *❤️ Add Wishlist* on any vehicle to save it.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        text = f"❤️ *Your AutoAI Wishlist* ({len(items)} items):\n\n"
        for idx, item in enumerate(items, 1):
            price_str = format_inr(item.get("price"))
            text += f"*{idx}. {item.get('brand', '')} {item.get('model', '')}* `{item.get('variant', '')}`\n   Price: {price_str}\n"

        keyboard = get_wishlist_keyboard(items)
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error in wishlist_command: {e}")
        await update.message.reply_text("AutoAI is temporarily unavailable. Please try again in a moment.")


# ==========================================
# Favorites Handlers
# ==========================================

async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /favorites or '⭐ Favorites' button."""
    user_id = update.effective_user.id
    try:
        favs = await api_client.get_favorites(user_id)
        if not favs:
            await update.message.reply_text(
                "⭐ *Your Favorites is Empty*\n\nBrowse cars with /cars and tap *⭐ Add Favorite* on any car to bookmark it.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        text = f"⭐ *Your Favorite Cars* ({len(favs)} cars):\n\n"
        for idx, car in enumerate(favs, 1):
            price_str = format_inr(car.get("ex_showroom_price") or car.get("price"))
            text += f"*{idx}. {car.get('brand', '')} {car.get('model', '')}* `{car.get('variant', '')}`\n   Price: {price_str}\n"

        keyboard = get_favorites_keyboard(favs)
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error in favorites_command: {e}")
        await update.message.reply_text("AutoAI is temporarily unavailable. Please try again in a moment.")


# ==========================================
# AI Chat Message Handler
# ==========================================

async def chat_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-form text chat messages."""
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    user_id = update.effective_user.id
    msg_id = update.message.message_id

    # Deduplication check
    last_msg_id = context.user_data.get("last_msg_id")
    if last_msg_id and last_msg_id == msg_id:
        return
    context.user_data["last_msg_id"] = msg_id

    # Handle button clicks that match menu options
    if user_text in ("🚗 Browse Cars", "/cars"):
        await cars_command(update, context)
        return
    elif user_text in ("🔍 Search Cars", "🔎 Search Cars", "/search"):
        await search_command(update, context)
        return
    elif user_text in ("🤖 AI Recommendation", "/recommend"):
        await recommend_command(update, context)
        return
    elif user_text in ("🔥 Upcoming Cars", "/upcoming"):
        await upcoming_command(update, context)
        return
    elif user_text in ("⚖️ Compare Cars", "/compare"):
        await compare_command(update, context)
        return
    elif user_text in ("❤️ Wishlist", "/wishlist"):
        await wishlist_command(update, context)
        return
    elif user_text in ("⭐ Favorites", "/favorites"):
        await favorites_command(update, context)
        return
    elif user_text in ("❓ Help", "/help"):
        await help_command(update, context)
        return

    # Check natural language comparison: e.g., "Compare Thar and Scorpio" or "Compare Creta vs Seltos"
    comp_match = re.match(
        r'^(?:compare|comparison\s+(?:of|between)?)\s+([A-Za-z0-9_\s]+?)\s+(?:and|vs|versus)\s+([A-Za-z0-9_\s]+)$',
        user_text,
        re.IGNORECASE
    )
    if comp_match:
        c1 = comp_match.group(1).strip()
        c2 = comp_match.group(2).strip()
        await execute_comparison(update, c1, c2)
        return

    # Handle greetings
    if GREETING_PATTERN.match(user_text) and len(user_text.split()) <= 3:
        welcome_greeting = (
            "👋 *Hello! Welcome to AutoAI* 🚗✨\n\n"
            "I am your AI Car Expert connected to our live database of 2,245 verified vehicles.\n\n"
            "You can ask me questions like:\n"
            "• _'I need an automatic SUV under 15 lakh'_\n"
            "• _'Which one is best for family?'_\n"
            "• _'What about mileage?'_\n"
            "• _'CNG car under 10 lakh'_\n"
            "• _'Show upcoming SUVs'_\n\n"
            "How can I help you find your dream car?"
        )
        await safe_reply(update, welcome_greeting, reply_markup=get_main_menu_keyboard())
        return

    # Send natural language message to FastAPI /chat endpoint
    try:
        await update.message.chat.send_action("typing")
        response = await api_client.chat(user_text, session_id=f"tg_{user_id}")
        ai_reply = response.get("ai_response", "")
        recs = response.get("recommendations", [])

        reply_text = f"🤖 {ai_reply}" if ai_reply else "Here are the top cars matching your inquiry:"

        if recs:
            reply_text += "\n\n*Top Matching Vehicles:*\n"
            for car in recs[:3]:
                brand = car.get("brand", "")
                model = car.get("model", "")
                variant = car.get("variant", "")
                status = (car.get("status") or "CURRENT").upper()
                is_upcoming = (status == "UPCOMING")
                price = car.get("price") or car.get("ex_showroom_price", 0)
                fuel = car.get("fuel_type") or car.get("fuel", "N/A")
                trans = car.get("transmission", "N/A")
                seating = car.get("seating") or car.get("seating_capacity", "N/A")
                safety = car.get("safety_rating")
                safety_str = f"{'⭐' * int(float(safety))} ({safety}/5)" if safety is not None else "Not Rated"
                badge = " `[UPCOMING]`" if is_upcoming else ""

                reply_text += (
                    f"\n🚗 *{brand} {model}* `{variant}`{badge}\n"
                    f"💰 Price: {format_inr(price)}\n"
                    f"⛽ Fuel: {fuel}\n"
                    f"⚙️ Transmission: {trans}\n"
                    f"👨‍👩‍👧‍👦 Seating: {seating} Seats\n"
                    f"⭐ Safety: {safety_str}\n"
                )

            total_pages = max(1, math.ceil(len(recs) / PAGE_SIZE))
            reply_markup = get_car_pagination_keyboard(recs[:PAGE_SIZE], 1, total_pages)
            await safe_reply(update, reply_text, reply_markup=reply_markup)
        else:
            await safe_reply(update, reply_text, reply_markup=get_main_menu_keyboard())

    except RuntimeError as e:
        logger.warning(f"Backend connectivity issue in chat_message_handler: {e}")
        await safe_reply(
            update,
            "⚠️ AutoAI backend server is currently unreachable. Please make sure the backend is running and try again in a moment.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in chat_message_handler: {e}")
        await safe_reply(
            update,
            "AutoAI is temporarily unavailable. Please try again in a moment.",
            reply_markup=get_main_menu_keyboard()
        )


# ==========================================
# Callback Query Handler (Pagination & Actions)
# ==========================================

async def generic_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks (pagination, view, wishlist, favorites)."""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if data == "noop":
        await query.answer()
        return

    # Handle Recommendation Wizard Callbacks
    if data.startswith("rec_"):
        await handle_rec_callbacks(update, context)
        return

    # Handle Pagination (car_page_X)
    if data.startswith("car_page_"):
        await query.answer()
        page_num = int(data.replace("car_page_", ""))
        try:
            cars = await api_client.get_all_cars()
            total_pages = max(1, math.ceil(len(cars) / PAGE_SIZE))
            page_num = max(1, min(page_num, total_pages))

            start_idx = (page_num - 1) * PAGE_SIZE
            page_cars = cars[start_idx:start_idx + PAGE_SIZE]

            text = (
                f"🚗 *AutoAI Car Catalog* (Total: {len(cars)} cars)\n\n"
                f"Page *{page_num}* of *{total_pages}*:\n"
                "Select any car below to inspect full specifications:"
            )
            reply_markup = get_car_pagination_keyboard(page_cars, page_num, total_pages)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Pagination error: {e}")
            await query.answer("Error loading page.", show_alert=True)
        return

    # Handle Upcoming Cars Pagination (upcoming_page_X)
    if data.startswith("upcoming_page_"):
        await query.answer()
        page_num = int(data.replace("upcoming_page_", ""))
        try:
            cars = await api_client.search_cars(status="UPCOMING")
            total_pages = max(1, math.ceil(len(cars) / PAGE_SIZE))
            page_num = max(1, min(page_num, total_pages))

            start_idx = (page_num - 1) * PAGE_SIZE
            page_cars = cars[start_idx:start_idx + PAGE_SIZE]

            text = (
                f"🔥 *AutoAI Upcoming Cars & Expected Launches* (Total: {len(cars)} cars)\n\n"
                f"⏳ *Notice:* These vehicles are not yet on sale in India. Specifications and prices are manufacturer estimates.\n\n"
                f"Page *{page_num}* of *{total_pages}*:\n"
                "Select any car below to inspect expected specifications:"
            )
            reply_markup = get_car_pagination_keyboard(page_cars, page_num, total_pages, prefix="upcoming_page")
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Upcoming pagination error: {e}")
            await query.answer("Error loading page.", show_alert=True)
        return

    # Handle Car Detail View (car_view_X)
    if data.startswith("car_view_"):
        await query.answer()
        car_id = data.replace("car_view_", "")
        try:
            car = await api_client.get_car(car_id)
            if not car:
                await query.answer("Car details not found.", show_alert=True)
                return

            card_text = format_car_card(car)
            reply_markup = get_car_detail_keyboard(int(car_id))
            await query.edit_message_text(card_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Car detail error: {e}")
            await query.answer("Error loading car details.", show_alert=True)
        return

    # Handle Wishlist Add
    if data.startswith("wishlist_add_"):
        car_id = int(data.replace("wishlist_add_", ""))
        try:
            res = await api_client.add_to_wishlist(car_id)
            msg = res.get("message", "Added to wishlist")
            await query.answer(f"❤️ {msg}", show_alert=True)
        except Exception as e:
            logger.error(f"Wishlist add error: {e}")
            await query.answer("Could not add to wishlist.", show_alert=True)
        return

    # Handle Wishlist Remove
    if data.startswith("wishlist_del_"):
        item_id = int(data.replace("wishlist_del_", ""))
        try:
            await api_client.remove_from_wishlist(item_id)
            await query.answer("❌ Removed from wishlist.", show_alert=True)
            # Refresh wishlist view
            items = await api_client.get_wishlist()
            if items:
                text = f"❤️ *Your AutoAI Wishlist* ({len(items)} items):\n\n"
                for idx, item in enumerate(items, 1):
                    price_str = format_inr(item.get("price"))
                    text += f"*{idx}. {item.get('brand', '')} {item.get('model', '')}* `{item.get('variant', '')}`\n   Price: {price_str}\n"
                keyboard = get_wishlist_keyboard(items)
                await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            else:
                await query.edit_message_text("❤️ *Your Wishlist is now empty.*", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Wishlist del error: {e}")
            await query.answer("Error removing item.", show_alert=True)
        return

    # Handle Favorite Add
    if data.startswith("fav_add_"):
        car_id = int(data.replace("fav_add_", ""))
        try:
            res = await api_client.add_favorite(user_id, car_id)
            msg = res.get("message", "Added to favorites")
            await query.answer(f"⭐ {msg}", show_alert=True)
        except Exception as e:
            logger.error(f"Favorite add error: {e}")
            await query.answer("Could not add to favorites.", show_alert=True)
        return

    # Handle Favorite Remove
    if data.startswith("fav_del_"):
        car_id = int(data.replace("fav_del_", ""))
        try:
            await api_client.delete_favorite(user_id, car_id)
            await query.answer("❌ Removed from favorites.", show_alert=True)
            # Refresh favorites view
            favs = await api_client.get_favorites(user_id)
            if favs:
                text = f"⭐ *Your Favorite Cars* ({len(favs)} cars):\n\n"
                for idx, car in enumerate(favs, 1):
                    price_str = format_inr(car.get("ex_showroom_price") or car.get("price"))
                    text += f"*{idx}. {car.get('brand', '')} {car.get('model', '')}* `{car.get('variant', '')}`\n   Price: {price_str}\n"
                keyboard = get_favorites_keyboard(favs)
                await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            else:
                await query.edit_message_text("⭐ *Your Favorites list is now empty.*", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Favorite del error: {e}")
            await query.answer("Error removing favorite.", show_alert=True)
        return

    # Handle Compare Prompt from Car Details
    if data.startswith("compare_prompt_"):
        car_id = data.replace("compare_prompt_", "")
        car = await api_client.get_car(car_id)
        model_name = car.get("model", "") if car else ""
        await query.answer()
        await query.message.reply_text(
            f"⚖️ Selected: *{model_name}*\n\nType `/compare {model_name} <second_car_name>` to run a side-by-side comparison!",
            parse_mode=ParseMode.MARKDOWN
        )
        return


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel any active conversation handler."""
    await update.message.reply_text("❌ Action cancelled.", reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global uncaught exception handler."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "AutoAI is temporarily unavailable. Please try again in a moment."
            )
        except Exception:
            pass
