from typing import Optional
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_home_keyboard() -> ReplyKeyboardMarkup:
    """
    Returns the beautiful Home Menu reply keyboard with grid layout.
    """
    keyboard = [
        [KeyboardButton("🚗 Recommend Car"), KeyboardButton("🔍 Search Car")],
        [KeyboardButton("⚖ Compare Cars"), KeyboardButton("❤️ Wishlist")],
        [KeyboardButton("🤖 AI Assistant"), KeyboardButton("👤 My Profile")],
        [KeyboardButton("⚙ Settings"), KeyboardButton("❓ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_fuel_keyboard() -> InlineKeyboardMarkup:
    """
    Inline keyboard for fuel type selection.
    """
    keyboard = [
        [InlineKeyboardButton("⛽ Petrol", callback_data="fuel_petrol"),
         InlineKeyboardButton("⛽ Diesel", callback_data="fuel_diesel")],
        [InlineKeyboardButton("🔋 CNG", callback_data="fuel_cng"),
         InlineKeyboardButton("⚡ Electric", callback_data="fuel_electric")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_transmission_keyboard() -> InlineKeyboardMarkup:
    """
    Inline keyboard for transmission selection.
    """
    keyboard = [
        [InlineKeyboardButton("⚙ Manual", callback_data="trans_manual"),
         InlineKeyboardButton("⚙ Automatic", callback_data="trans_automatic")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_body_type_keyboard() -> InlineKeyboardMarkup:
    """
    Inline keyboard for body type selection.
    """
    keyboard = [
        [InlineKeyboardButton("🚗 Hatchback", callback_data="body_hatchback"),
         InlineKeyboardButton("🚙 SUV", callback_data="body_suv")],
        [InlineKeyboardButton("🏎 Sedan", callback_data="body_sedan"),
         InlineKeyboardButton("🚐 MUV / MPV", callback_data="body_muv")],
        [InlineKeyboardButton("✨ Skip/Any", callback_data="body_any")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_family_keyboard() -> InlineKeyboardMarkup:
    """
    Inline keyboard for family members/seating capacity.
    """
    keyboard = [
        [InlineKeyboardButton("👥 4 Seats", callback_data="seating_4"),
         InlineKeyboardButton("👥 5 Seats", callback_data="seating_5")],
        [InlineKeyboardButton("👥 7 Seats", callback_data="seating_7"),
         InlineKeyboardButton("👥 8 Seats", callback_data="seating_8")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_city_highway_keyboard() -> InlineKeyboardMarkup:
    """
    Inline keyboard for driving usage.
    """
    keyboard = [
        [InlineKeyboardButton("🌆 City Use", callback_data="drive_city"),
         InlineKeyboardButton("🛣 Highway Use", callback_data="drive_highway")],
        [InlineKeyboardButton("🔄 Both (City & Highway)", callback_data="drive_both")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_recommendation_card_keyboard(car_id: int, wishlist_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """
    Inline action buttons shown under a recommendation car card.
    If wishlist_id is provided, show 'Remove from Wishlist' instead of 'Add'.
    """
    wish_text = "💔 Remove Wishlist" if wishlist_id is not None else "❤️ Wishlist"
    wish_callback = f"wishlist_rem_{wishlist_id}_{car_id}" if wishlist_id is not None else f"wishlist_add_{car_id}"
    
    keyboard = [
        [
            InlineKeyboardButton(wish_text, callback_data=wish_callback),
            InlineKeyboardButton("⚖ Compare", callback_data=f"compare_start_{car_id}")
        ],
        [
            InlineKeyboardButton("➡ Next Car", callback_data="rec_next"),
            InlineKeyboardButton("🏠 Home", callback_data="rec_home")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_wishlist_card_keyboard(wishlist_id: int, car_id: int) -> InlineKeyboardMarkup:
    """
    Keyboard shown for wishlist entries.
    """
    keyboard = [
        [
            InlineKeyboardButton("💔 Remove", callback_data=f"wishlist_rem_{wishlist_id}_{car_id}"),
            InlineKeyboardButton("⚖ Compare", callback_data=f"compare_start_{car_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard(lang: str, theme: str, notify: bool) -> InlineKeyboardMarkup:
    """
    Inline settings customization panel.
    """
    lang_label = "🌐 Language: English" if lang == "en" else "🌐 Language: Hindi"
    theme_label = "🎨 Theme: Dark" if theme == "dark" else "🎨 Theme: Light"
    notify_label = "🔔 Notifications: Enabled" if notify else "🔕 Notifications: Disabled"
    
    keyboard = [
        [InlineKeyboardButton(lang_label, callback_data="settings_toggle_lang")],
        [InlineKeyboardButton(theme_label, callback_data="settings_toggle_theme")],
        [InlineKeyboardButton(notify_label, callback_data="settings_toggle_notify")],
        [InlineKeyboardButton("🏠 Back to Home", callback_data="settings_back_home")]
    ]
    return InlineKeyboardMarkup(keyboard)
