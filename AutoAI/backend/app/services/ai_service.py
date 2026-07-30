import re


def extract_preferences(message: str):

    text = message.lower()

    preferences = {
        "budget": 100000000,
        "fuel_type": None,
        "transmission": None,
        "body_type": None,
        "family_members": 5,
        "priority": "safety",
        "city_drive": False,
        "highway_drive": False,
    }

    # -------------------------
    # Budget
    # -------------------------

    lakh = re.search(r'(\d+)\s*lakh', text)

    if lakh:
        preferences["budget"] = int(lakh.group(1)) * 100000

    crore = re.search(r'(\d+)\s*crore', text)

    if crore:
        preferences["budget"] = int(crore.group(1)) * 10000000

    amount = re.search(r'₹?\s*(\d{6,8})', text)

    if amount:
        preferences["budget"] = int(amount.group(1))

    # -------------------------
    # Fuel
    # -------------------------

    if re.search(r'\b(electric|ev|evs)\b', text):
        preferences["fuel_type"] = "Electric"
    elif re.search(r'\b(diesel)\b', text):
        preferences["fuel_type"] = "Diesel"
    elif re.search(r'\b(petrol)\b', text):
        preferences["fuel_type"] = "Petrol"
    elif re.search(r'\b(hybrid)\b', text):
        preferences["fuel_type"] = "Hybrid"
    elif re.search(r'\b(cng)\b', text):
        preferences["fuel_type"] = "CNG"

    # -------------------------
    # Transmission
    # -------------------------

    if re.search(r'\b(automatic|auto|amt|cvt|dct)\b', text):
        preferences["transmission"] = "Automatic"
    elif re.search(r'\b(manual|mt)\b', text):
        preferences["transmission"] = "Manual"

    # -------------------------
    # Body Type
    # -------------------------

    body_types = {
        r'\bsuv\b': "SUV",
        r'\bsedan\b': "Sedan",
        r'\bhatchback\b': "Hatchback",
        r'\bmpv\b': "MPV",
        r'\bsports?\b': "Sports",
        r'\bcoupe\b': "Coupe",
    }

    for pattern, value in body_types.items():
        if re.search(pattern, text):
            preferences["body_type"] = value
            break


    # -------------------------
    # Family Members
    # -------------------------

    family = re.search(r'(\d+)\s*(members|people|persons)', text)

    if family:
        preferences["family_members"] = int(family.group(1))

    # -------------------------
    # Priority
    # -------------------------

    if "mileage" in text:
        preferences["priority"] = "mileage"

    elif "safety" in text:
        preferences["priority"] = "safety"

    elif "maintenance" in text:
        preferences["priority"] = "maintenance"

    elif "resale" in text:
        preferences["priority"] = "resale"

    # -------------------------
    # Driving
    # -------------------------

    if "city" in text:

        preferences["city_drive"] = True

    if "highway" in text:

        preferences["highway_drive"] = True

    return preferences


def explain_recommendations(message: str, recommendations: list, preferences: dict = None):
    if not recommendations:
        return "I couldn't find any cars in our database matching your exact criteria. Try broadening your budget, fuel, or transmission preferences!"

    text = message.lower()
    
    # Intent Analysis & Direct Question Answering
    intent_intro = ""
    
    # 1. Safety Intent
    if any(k in text for k in ["safe", "safety", "ncap", "5 star", "rating"]):
        top_safety = sorted(recommendations, key=lambda x: x.get("safety_rating", 0), reverse=True)
        best = top_safety[0]
        intent_intro = (
            f"### 🛡️ Safety-Focused Recommendation\n"
            f"You asked for safety. The highest rated safety option matching your request is the **{best['brand']} {best['model']}** "
            f"with a **{best.get('safety_rating', 'N/A')}/5-Star Safety Rating**.\n\n"
        )
    # 2. Mileage / Fuel Efficiency Intent
    elif any(k in text for k in ["mileage", "fuel economy", "kmpl", "average", "efficient"]):
        top_mileage = sorted(recommendations, key=lambda x: x.get("mileage", 0), reverse=True)
        best = top_mileage[0]
        intent_intro = (
            f"### ⛽ High Efficiency & Mileage Focus\n"
            f"If fuel efficiency is your main priority, the **{best['brand']} {best['model']}** leads with an impressive **{best.get('mileage', 'N/A')} km/l**.\n\n"
        )
    # 3. Budget / Price Intent
    elif any(k in text for k in ["budget", "cheap", "under", "lakh", "price", "affordable"]):
        intent_intro = (
            f"### 💰 Budget-Tailored Options\n"
            f"Here are the top value-for-money options filtered strictly within your budget requirements:\n\n"
        )
    # 4. Transmission Intent
    elif any(k in text for k in ["automatic", "auto", "amt", "cvt", "manual"]):
        trans_type = "Automatic" if any(k in text for k in ["automatic", "auto", "amt", "cvt"]) else "Manual"
        intent_intro = (
            f"### 🚗 {trans_type} Transmission Selection\n"
            f"Here are the top-rated **{trans_type}** cars that match your driving profile:\n\n"
        )
    # 5. Body Type Intent
    elif any(k in text for k in ["suv", "sedan", "hatchback", "mpv"]):
        intent_intro = (
            f"### 🚘 Body Style Selection\n"
            f"Based on your request, here are the top options matching your preferred body style:\n\n"
        )
    else:
        intent_intro = "### 🔍 Top Recommended Cars for You\nBased on your specific query and criteria, here are the best matching choices:\n\n"

    # Build structured detailed response
    body = ""
    for i, car in enumerate(recommendations[:5], start=1):
        reasons_str = ", ".join(car.get("reasons", [])) if car.get("reasons") else "Matches your criteria"
        body += (
            f"**{i}. {car['brand']} {car['model']} ({car['variant']})**\n"
            f"• **Price:** ₹{car['price']:,.0f} (Ex-Showroom)\n"
            f"• **Powertrain:** {car['fuel_type']} | {car['transmission']}\n"
            f"• **Specs:** {car.get('mileage', 'N/A')} km/l | {car.get('power', 'N/A')} bhp | {car.get('safety_rating', 'N/A')}/5 ⭐ Safety\n"
            f"• **Why this fits:** {reasons_str}\n\n"
        )

    closing = "💡 *Tip: You can ask me to compare any two models, check maintenance costs, or refine your budget!*"
    return intent_intro + body + closing