from typing import List, Dict, Any, Optional
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Return persistent bottom reply keyboard with main AutoAI options."""
    keyboard = [
        ["🔍 Search Cars", "🤖 AI Recommendation"],
        ["🚗 Browse Cars", "🔥 Upcoming Cars"],
        ["⚖️ Compare Cars", "❤️ Wishlist"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_car_pagination_keyboard(
    cars: List[Dict[str, Any]],
    current_page: int,
    total_pages: int,
    prefix: str = "car_page"
) -> InlineKeyboardMarkup:
    """Build inline keyboard for a list of cars with pagination controls."""
    keyboard = []

    # Add buttons for individual cars on this page
    for car in cars:
        car_id = car.get("id")
        brand = car.get("brand", "")
        model = car.get("model", "")
        price = car.get("price") or car.get("ex_showroom_price", 0)
        
        if price >= 10000000:
            price_str = f"₹{price/10000000:.2f} Cr"
        elif price >= 100000:
            price_str = f"₹{price/100000:.2f} L"
        else:
            price_str = f"₹{price:,.0f}"

        btn_text = f"🚗 {brand} {model} ({price_str})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"car_view_{car_id}")])

    # Navigation buttons row
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"{prefix}_{current_page - 1}"))
    
    nav_row.append(InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="noop"))
    
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"{prefix}_{current_page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    return InlineKeyboardMarkup(keyboard)


def get_car_detail_keyboard(car_id: int) -> InlineKeyboardMarkup:
    """Action buttons for a single car detail view."""
    keyboard = [
        [
            InlineKeyboardButton("❤️ Add Wishlist", callback_data=f"wishlist_add_{car_id}"),
            InlineKeyboardButton("⭐ Add Favorite", callback_data=f"fav_add_{car_id}"),
        ],
        [
            InlineKeyboardButton("⚖️ Compare with another", callback_data=f"compare_prompt_{car_id}"),
            InlineKeyboardButton("🔙 Back to Cars", callback_data="car_page_1"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_wishlist_keyboard(items: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Inline buttons to remove individual wishlist items or view car details."""
    keyboard = []
    for item in items:
        item_id = item.get("id")
        car_id = item.get("car_id")
        brand = item.get("brand", "")
        model = item.get("model", "")
        keyboard.append([
            InlineKeyboardButton(f"🚗 {brand} {model}", callback_data=f"car_view_{car_id}"),
            InlineKeyboardButton("❌ Remove", callback_data=f"wishlist_del_{item_id}"),
        ])
    return InlineKeyboardMarkup(keyboard) if keyboard else None


def get_favorites_keyboard(favorites: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Inline buttons to view or remove favorites."""
    keyboard = []
    for car in favorites:
        car_id = car.get("id")
        brand = car.get("brand", "")
        model = car.get("model", "")
        keyboard.append([
            InlineKeyboardButton(f"🚗 {brand} {model}", callback_data=f"car_view_{car_id}"),
            InlineKeyboardButton("❌ Remove", callback_data=f"fav_del_{car_id}"),
        ])
    return InlineKeyboardMarkup(keyboard) if keyboard else None


# Recommendation Wizard Keyboards
def get_rec_budget_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Under ₹10 Lakh", callback_data="rec_budget_1000000")],
        [InlineKeyboardButton("₹10 - ₹15 Lakh", callback_data="rec_budget_1500000")],
        [InlineKeyboardButton("₹15 - ₹25 Lakh", callback_data="rec_budget_2500000")],
        [InlineKeyboardButton("₹25 - ₹40 Lakh", callback_data="rec_budget_4000000")],
        [InlineKeyboardButton("₹40+ Lakh (Any)", callback_data="rec_budget_100000000")],
        [InlineKeyboardButton("❌ Cancel", callback_data="rec_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_rec_fuel_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Petrol", callback_data="rec_fuel_Petrol"), InlineKeyboardButton("Diesel", callback_data="rec_fuel_Diesel")],
        [InlineKeyboardButton("Electric", callback_data="rec_fuel_Electric"), InlineKeyboardButton("CNG", callback_data="rec_fuel_CNG")],
        [InlineKeyboardButton("Any Fuel", callback_data="rec_fuel_any")],
        [InlineKeyboardButton("❌ Cancel", callback_data="rec_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_rec_trans_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Automatic", callback_data="rec_trans_Automatic"), InlineKeyboardButton("Manual", callback_data="rec_trans_Manual")],
        [InlineKeyboardButton("Any Transmission", callback_data="rec_trans_any")],
        [InlineKeyboardButton("❌ Cancel", callback_data="rec_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_rec_body_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("SUV", callback_data="rec_body_SUV"), InlineKeyboardButton("Sedan", callback_data="rec_body_Sedan")],
        [InlineKeyboardButton("Hatchback", callback_data="rec_body_Hatchback"), InlineKeyboardButton("Any Body", callback_data="rec_body_any")],
        [InlineKeyboardButton("❌ Cancel", callback_data="rec_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_rec_priority_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🛡️ Safety", callback_data="rec_prio_safety"), InlineKeyboardButton("⛽ Mileage", callback_data="rec_prio_mileage")],
        [InlineKeyboardButton("🔧 Maintenance", callback_data="rec_prio_maintenance"), InlineKeyboardButton("📈 Resale Value", callback_data="rec_prio_resale")],
        [InlineKeyboardButton("⚡ Balanced / None", callback_data="rec_prio_none")],
        [InlineKeyboardButton("❌ Cancel", callback_data="rec_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)
