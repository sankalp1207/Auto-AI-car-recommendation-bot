import re
from typing import Dict, Any, List

KNOWN_BRANDS = [
    "maruti suzuki", "maruti", "hyundai", "tata", "mahindra", "kia", "toyota",
    "honda", "volkswagen", "vw", "skoda", "mg", "renault", "nissan", "citroen",
    "jeep", "bmw", "mercedes-benz", "mercedes", "audi", "volvo", "land rover",
    "jaguar", "porsche", "byd", "mini", "ferrari", "lamborghini", "rolls-royce",
    "bentley", "maserati", "aston martin", "force", "isuzu", "lexus", "lotus"
]


def extract_preferences(message: str) -> Dict[str, Any]:
    text = message.lower()

    preferences: Dict[str, Any] = {
        "budget": None,
        "brand": None,
        "model": None,
        "fuel_type": None,
        "transmission": None,
        "body_type": None,
        "seating": None,
        "family_members": None,
        "status": "CURRENT",
        "priority": "safety",
        "city_drive": False,
        "highway_drive": False,
        "family_friendly": False,
        "is_luxury": False,
    }

    # -------------------------
    # Status (CURRENT vs UPCOMING)
    # -------------------------
    if re.search(r'\b(upcoming|future|launching|unreleased|next-gen|next gen|expected)\b', text):
        preferences["status"] = "UPCOMING"

    # -------------------------
    # Luxury Segment
    # -------------------------
    if re.search(r'\b(luxury|supercar|exotic|premium luxury)\b', text):
        preferences["is_luxury"] = True

    # -------------------------
    # Brand
    # -------------------------
    for b in KNOWN_BRANDS:
        pattern = r'\b' + re.escape(b) + r'\b'
        if re.search(pattern, text):
            # Normalize display name
            if b in {"maruti suzuki", "maruti"}:
                preferences["brand"] = "Maruti Suzuki"
            elif b in {"mercedes-benz", "mercedes"}:
                preferences["brand"] = "Mercedes-Benz"
            elif b == "vw":
                preferences["brand"] = "Volkswagen"
            else:
                preferences["brand"] = b.title()
            break

    # -------------------------
    # Budget
    # -------------------------
    # Matches: 15 lakh, 15.5 lakhs, ₹15 lakh, 15l, 15 l
    lakh = re.search(r'₹?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|l)\b', text)
    if lakh:
        preferences["budget"] = float(lakh.group(1)) * 100000.0

    # Matches: 1.5 crore, 1 crore, ₹2 crore, 1cr
    crore = re.search(r'₹?\s*(\d+(?:\.\d+)?)\s*(?:crore|crores|cr)\b', text)
    if crore:
        preferences["budget"] = float(crore.group(1)) * 10000000.0

    # Matches raw INR amounts like ₹1200000, 1500000, ₹2,00,000
    if not preferences["budget"]:
        clean_amount_text = text.replace(",", "")
        amount = re.search(r'₹\s*(\d{5,9})', clean_amount_text) or re.search(r'\b(\d{6,9})\b', clean_amount_text)
        if amount:
            preferences["budget"] = float(amount.group(1))

    # -------------------------
    # Fuel
    # -------------------------
    if re.search(r'\b(electric|ev|evs)\b', text):
        preferences["fuel_type"] = "Electric"
    elif re.search(r'\b(cng)\b', text):
        preferences["fuel_type"] = "CNG"
    elif re.search(r'\b(diesel)\b', text):
        preferences["fuel_type"] = "Diesel"
    elif re.search(r'\b(petrol)\b', text):
        preferences["fuel_type"] = "Petrol"
    elif re.search(r'\b(hybrid)\b', text):
        preferences["fuel_type"] = "Hybrid"

    # -------------------------
    # Transmission
    # -------------------------
    if re.search(r'\b(automatic|auto|amt|cvt|dct|at)\b', text):
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
        r'\b(mpv|muv)\b': "MPV",
        r'\bsports?\b': "Sports",
        r'\bcoupe\b': "Coupe",
        r'\bconvertible\b': "Convertible",
    }
    for pattern, value in body_types.items():
        if re.search(pattern, text):
            preferences["body_type"] = value
            break

    # -------------------------
    # Seating Capacity
    # -------------------------
    seating = re.search(r'(\d+)\s*(?:seater|seat|seats|person|persons|people|members)', text)
    if seating:
        val = int(seating.group(1))
        preferences["seating"] = val
        preferences["family_members"] = val

    # -------------------------
    # Family Friendly
    # -------------------------
    if re.search(r'\bfamily\b', text):
        preferences["family_friendly"] = True
        if not preferences["family_members"]:
            preferences["family_members"] = 5

    # -------------------------
    # Driving Context
    # -------------------------
    if re.search(r'\b(city|commute|traffic|urban)\b', text):
        preferences["city_drive"] = True

    if re.search(r'\b(highway|touring|long drive|cruiser)\b', text):
        preferences["highway_drive"] = True

    # -------------------------
    # Priorities
    # -------------------------
    if "mileage" in text or "efficiency" in text or "average" in text:
        preferences["priority"] = "mileage"
    elif "safety" in text or "ncap" in text:
        preferences["priority"] = "safety"
    elif "maintenance" in text:
        preferences["priority"] = "maintenance"
    elif "resale" in text:
        preferences["priority"] = "resale"
    elif "performance" in text or "power" in text:
        preferences["priority"] = "performance"
    elif preferences["family_friendly"]:
        preferences["priority"] = "family"

    return preferences


def explain_recommendations(message: str, recommendations: list, preferences: dict = None) -> str:
    prefs = preferences or {}
    budget = prefs.get("budget")

    if not recommendations:
        if prefs.get("is_luxury") and budget and budget < 2000000:
            return (
                f"### No Luxury Cars Matching Budget\n\n"
                f"No luxury vehicles were found under **Rs. {budget:,.0f}** in our database.\n\n"
                f"In the Indian automotive market, genuine luxury brand models (such as the BMW 2 Series, "
                f"Mercedes-Benz A-Class, or Audi A4) start at approximately **Rs. 45-50 Lakh** ex-showroom. "
                f"The entry-level passenger cars in our database begin around Rs. 3.5 Lakh. "
                f"Please consider revising your budget target or browsing standard non-luxury alternatives."
            )
        return (
            "### No Matching Vehicles Found\n\n"
            "I couldn't find any vehicles in our database matching all your exact constraints. "
            "Try adjusting your budget limit, relaxing fuel/transmission requirements, or changing the body style."
        )

    text = message.lower()
    intent_intro = ""

    # Intent Analysis
    if any(k in text for k in ["safe", "safety", "ncap", "5 star", "rating"]):
        top_safety = sorted(recommendations, key=lambda x: x.get("safety_rating", 0), reverse=True)
        best = top_safety[0]
        intent_intro = (
            f"### Safety-Focused Recommendation\n"
            f"You asked for safety. The top safety performer is the **{best['brand']} {best['model']}** "
            f"with a **{best.get('safety_rating', 'N/A')}/5-Star Safety Rating**.\n\n"
        )
    elif any(k in text for k in ["mileage", "fuel economy", "kmpl", "average", "efficient"]):
        top_mileage = sorted(recommendations, key=lambda x: x.get("mileage", 0), reverse=True)
        best = top_mileage[0]
        intent_intro = (
            f"### High Efficiency & Mileage Focus\n"
            f"If fuel efficiency is your top consideration, the **{best['brand']} {best['model']}** leads "
            f"with an impressive **{best.get('mileage', 'N/A')} km/l**.\n\n"
        )
    elif any(k in text for k in ["upcoming", "future", "launching"]):
        intent_intro = (
            f"### Upcoming Vehicles in Pipeline\n"
            f"Here are the most anticipated upcoming models matching your requirements:\n\n"
        )
    elif any(k in text for k in ["suv", "sedan", "hatchback", "mpv"]):
        style = prefs.get("body_type") or "selected"
        intent_intro = (
            f"### Top {style} Selections\n"
            f"Here are the top-scoring {style} models matching your specifications:\n\n"
        )
    else:
        intent_intro = "### Top Recommended Cars for You\nBased on your specific query and criteria, here are the best matching choices:\n\n"

    body = ""
    for i, car in enumerate(recommendations[:5], start=1):
        reasons_list = car.get("reasons", [])
        reasons_str = "; ".join(reasons_list[:2]) if reasons_list else "Matches your specified requirements"
        price_val = float(car.get("price") or car.get("ex_showroom_price") or 0.0)
        status_label = f" *({car.get('status')})*" if car.get("status") == "UPCOMING" else ""

        body += (
            f"**{i}. {car['brand']} {car['model']} ({car['variant']})**{status_label}\n"
            f"- Price: Rs. {price_val:,.0f} (Ex-Showroom)\n"
            f"- Powertrain: {car.get('fuel_type')} | {car.get('transmission')}\n"
            f"- Key Specs: {car.get('mileage', 0):.1f} km/l | {car.get('power', 0)} bhp | {car.get('seating', 5)} Seater | {car.get('safety_rating', 0):.0f}/5 Stars Safety\n"
            f"- Match Score: {car.get('score', 85):.1f}/100 -- *{reasons_str}*\n\n"
        )

    closing = "*Tip: You can ask me to compare any two models, check maintenance costs, or refine your budget!*"
    return intent_intro + body + closing