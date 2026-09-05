import re
from typing import Dict, Any, List, Tuple

# Comprehensive luxury brand lookup (Indian market)
LUXURY_BRANDS = {
    "mercedes-benz", "mercedes", "bmw", "audi", "porsche",
    "land rover", "jaguar", "volvo", "lexus", "bentley",
    "rolls-royce", "ferrari", "lamborghini", "maserati",
    "aston martin", "mclaren", "lotus", "maybach"
}

# Body type classification heuristics based on Indian vehicle models
KNOWN_HATCHBACKS = {
    "swift", "baleno", "alto", "alto k10", "altroz", "i20", "i20 n line",
    "tiago", "tiago ev", "celerio", "wagon r", "kwid", "glanza", "ignis",
    "s-presso", "comet ev", "cooper", "cooper se", "cooper s convertible",
    "amg a45 s", "golf gti", "ec3 x", "grand i10 nios"
}

KNOWN_SEDANS = {
    "city", "verna", "virtus", "slavia", "ciaz", "amaze", "amaze 2nd gen",
    "aura", "dzire", "camry", "tigor", "tigor ev", "a4", "a6", "a8 l",
    "3 series lwb", "5 series", "7 series", "2 series gran coupe", "m340i",
    "m5", "i5", "i7", "c-class", "e-class", "s-class", "maybach s-class",
    "amg c 43", "amg c 63 s e performance", "amg s 63 e performance",
    "amg eqs", "eqs", "es", "es 350h", "seal", "panamera", "taycan",
    "quattroporte", "ghibli", "phantom", "octavia rs", "new superb"
}

KNOWN_MPVS = {
    "ertiga", "xl6", "carens", "carens clavis", "carens clavis ev",
    "innova", "innova crysta", "innova hycross", "rumion", "carnival",
    "triber", "eeco", "invicto", "vellfire", "v-class", "emax 7",
    "trax cruiser", "marazzo", "vf mpv 7", "lm"
}

KNOWN_SUVS = {
    "brezza", "creta", "creta electric", "creta n line", "nexon", "nexon ev",
    "punch", "punch ev", "venue", "venue n line", "seltos", "scorpio",
    "scorpio n", "thar", "thar roxx", "xuv 7xo", "xuv 3xo", "xuv 3xo ev",
    "xuv400", "harrier", "harrier ev", "safari", "safari ev", "grand vitara",
    "fronx", "elevate", "kushaq", "taigun", "sonet", "kiger", "magnite",
    "astor", "hector", "hector plus", "fortuner", "fortuner legender",
    "jimny", "curvv", "curvv ev", "kodiaq", "kodiaq rs", "compass",
    "meridian", "wrangler", "defender", "discovery", "discovery sport",
    "range rover", "range rover velar", "range rover sport",
    "range rover evoque", "x1", "x1 lwb", "x3", "x5", "x6", "x7", "xm",
    "ix", "ix1 lwb", "q3", "q3 sportback", "q5", "q7", "q8", "sq8",
    "rs q8 performance", "q8 e-tron", "gla", "glc", "gle", "gls", "g-class",
    "amg g-class", "amg gla35", "amg glc43 coupe", "amg gle coupe",
    "maybach gls", "maybach eqs suv", "eqe suv", "eqs suv", "urus se",
    "bentayga", "cullinan", "dbx", "cayenne", "cayenne coupe", "cayenne ev",
    "macan", "macan turbo ev", "atto 3", "ioniq 5", "ev6", "ev9", "exter",
    "bolero", "bolero neo", "bolero neo plus", "basalt x", "aircross x",
    "c3 x", "c5 aircross", "victoris", "urban cruiser taisor",
    "urban cruiser hyryder", "land cruiser", "hilux", "tiguan r-line",
    "tayron", "xc60", "xc90", "ex30", "ec40", "eletre", "emira", "duster",
    "kylaq", "tekton", "countryman", "countryman c", "countryman electric",
    "alcazar", "gurkha", "mu-x", "v-cross", "f-pace", "lx", "nx", "rx",
    "grecale", "levante", "windsor ev", "zs ev", "sealion 7", "sierra",
    "sierra ev", "model y"
}


def is_luxury_brand(brand: str | None) -> bool:
    """Check if the given brand belongs to the luxury automotive segment."""
    if not brand:
        return False
    return brand.strip().lower() in LUXURY_BRANDS


def classify_body_type(model: str | None, variant: str | None = None, brand: str | None = None, stored_body_type: str | None = None) -> str:
    """
    Deterministic body type resolution:
    1. Uses stored body type if known and not 'Unknown'.
    2. Uses curated Indian automotive model dictionary.
    3. Uses keyword heuristics on model/variant text.
    """
    if stored_body_type and stored_body_type.strip().lower() not in {"unknown", "", "none"}:
        s = stored_body_type.strip().title()
        if s in {"Suv", "Sedan", "Hatchback", "Mpv", "Coupe", "Convertible", "Pickup"}:
            return "SUV" if s == "Suv" else "MPV" if s == "Mpv" else s

    m_lower = (model or "").strip().lower()
    v_lower = (variant or "").strip().lower()
    text = f"{m_lower} {v_lower}"

    # Exact model match checks
    if m_lower in KNOWN_HATCHBACKS or any(h in m_lower for h in ["alto", "wagon r", "celerio", "kwid", "glanza", "ignis", "s-presso"]):
        return "Hatchback"
    if m_lower in KNOWN_SEDANS or any(s in m_lower for s in ["amaze", "aura", "dzire", "verna", "virtus", "slavia", "ciaz"]):
        return "Sedan"
    if m_lower in KNOWN_MPVS or any(mp in m_lower for mp in ["ertiga", "xl6", "innova", "carens", "triber", "rumion"]):
        return "MPV"
    if m_lower in KNOWN_SUVS or any(su in m_lower for su in ["suv", "brezza", "creta", "nexon", "punch", "venue", "seltos", "scorpio", "thar", "xuv", "harrier", "safari"]):
        return "SUV"

    # Token and keyword heuristics
    if re.search(r'\bsuv\b', text):
        return "SUV"
    if re.search(r'\b(sedan|saloon|limousine)\b', text):
        return "Sedan"
    if re.search(r'\b(hatchback|hatch)\b', text):
        return "Hatchback"
    if re.search(r'\b(mpv|muv|minivan|van)\b', text):
        return "MPV"
    if re.search(r'\b(coupe|gran coupe)\b', text):
        return "Coupe"
    if re.search(r'\b(convertible|cabriolet|roadster|spider)\b', text):
        return "Convertible"

    return "SUV" if any(k in text for k in ["cross", "aircross", "4x4", "all-wheel", "awd"]) else "Hatchback"


def calculate_match_score(car: Any, prefs: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    """
    Legacy backwards-compatible scoring function.
    Accepts both dict and SQLAlchemy Car model objects.
    """
    def _val(attr, default=0.0):
        if isinstance(car, dict):
            return car.get(attr, default)
        return getattr(car, attr, default)

    score = 0.0
    breakdown = {}

    price = float(_val("price") or _val("ex_showroom_price") or 0.0)
    budget = float(prefs.get("budget") or 0.0)

    # Budget
    if budget > 0 and price <= budget:
        score += 25.0
        breakdown["Budget"] = 25.0
    else:
        breakdown["Budget"] = 0.0

    # Fuel
    pref_fuel = prefs.get("fuel_type") or prefs.get("fuel")
    car_fuel = str(_val("fuel_type") or _val("fuel") or "")
    if pref_fuel:
        if pref_fuel.lower().strip() in car_fuel.lower():
            score += 15.0
            breakdown["Fuel"] = 15.0
        else:
            breakdown["Fuel"] = 0.0

    # Transmission
    pref_trans = prefs.get("transmission")
    car_trans = str(_val("transmission") or "")
    if pref_trans:
        if pref_trans.lower().strip() in car_trans.lower():
            score += 15.0
            breakdown["Transmission"] = 15.0
        else:
            breakdown["Transmission"] = 0.0

    # Safety
    safety = float(_val("safety_rating") or 0.0)
    safety_pts = min(safety * 4.0, 20.0)
    score += safety_pts
    breakdown["Safety"] = safety_pts

    # Seating
    seating = int(_val("seating") or _val("seating_capacity") or 5)
    family_members = int(prefs.get("family_members") or prefs.get("seating") or 5)
    if seating >= family_members:
        score += 10.0
        breakdown["Family"] = 10.0
    else:
        breakdown["Family"] = 0.0

    # Mileage
    mileage = float(_val("mileage") or 0.0)
    mileage_pts = min(mileage, 15.0)
    score += mileage_pts
    breakdown["Mileage"] = mileage_pts

    return score, breakdown


def calculate_recommendation_score(car: Dict[str, Any], prefs: Dict[str, Any]) -> Tuple[float, List[str], Dict[str, float]]:
    """
    Production-grade deterministic scoring function for valid candidates.
    Assumes hard constraints have already been verified by database filtering.
    Scores soft preferences, safety, efficiency, use case fit, and specifications.
    Guarantees no crashes on missing/null fields and deterministic score generation.
    """
    score = 0.0
    reasons: List[str] = []
    breakdown: Dict[str, float] = {}

    price = float(car.get("price") or car.get("ex_showroom_price") or 0.0)
    budget = float(prefs.get("budget") or 0.0)

    # 1. Budget Value & Efficiency (up to 20 pts)
    if budget > 0 and price > 0:
        ratio = price / budget
        val_pts = 10.0 + max(0.0, 10.0 * (1.0 - ratio))
        score += val_pts
        breakdown["Value"] = round(val_pts, 1)
        reasons.append(f"Comfortably within budget (₹{price:,.0f} vs limit ₹{budget:,.0f})")
    else:
        score += 15.0
        breakdown["Value"] = 15.0

    # 2. Safety Rating (up to 20 pts)
    safety = float(car.get("safety_rating") or 0.0)
    if safety > 0:
        safety_pts = min(20.0, safety * 4.0)
        score += safety_pts
        breakdown["Safety"] = round(safety_pts, 1)
        if safety >= 4.0:
            reasons.append(f"{safety:,.0f}/5-Star Safety Rating")
    else:
        score += 5.0
        breakdown["Safety"] = 5.0

    # 3. Fuel Efficiency / Mileage (up to 15 pts)
    mileage = float(car.get("mileage") or 0.0)
    fuel_type = str(car.get("fuel_type") or "").lower()
    if "electric" in fuel_type:
        # Electric vehicles get top efficiency score
        score += 15.0
        breakdown["Efficiency"] = 15.0
        reasons.append("Zero emissions electric powertrain")
    elif mileage > 0:
        mileage_pts = min(15.0, mileage * 0.6)
        score += mileage_pts
        breakdown["Efficiency"] = round(mileage_pts, 1)
        if mileage >= 18.0:
            reasons.append(f"High fuel economy ({mileage:,.1f} km/l)")
    else:
        score += 5.0
        breakdown["Efficiency"] = 5.0

    # 4. Engine Power & Performance (up to 10 pts)
    power = float(car.get("power") or 0.0)
    if power > 0:
        power_pts = min(10.0, power / 15.0)
        score += power_pts
        breakdown["Performance"] = round(power_pts, 1)
        if power >= 120.0:
            reasons.append(f"Strong engine output ({power:,.0f} bhp)")
    else:
        score += 3.0
        breakdown["Performance"] = 3.0

    # 5. Seating & Practicality (up to 10 pts)
    seating = int(car.get("seating") or car.get("seating_capacity") or 5)
    boot = float(car.get("boot_space") or 0.0)
    if seating >= 7:
        score += 10.0
        breakdown["Practicality"] = 10.0
        reasons.append(f"Spacious {seating}-seater layout")
    elif boot >= 350:
        score += 8.0
        breakdown["Practicality"] = 8.0
        reasons.append(f"Generous {boot:,.0f}L luggage boot space")
    else:
        score += 5.0
        breakdown["Practicality"] = 5.0

    # 6. Maintenance & Reliability (up to 10 pts)
    maint = float(car.get("maintenance_cost") or 0.0)
    resale = float(car.get("resale_rating") or 0.0)
    maint_pts = 5.0
    if maint > 0:
        maint_pts = max(0.0, min(5.0, 10.0 - (maint / 2500.0)))
    resale_pts = min(5.0, resale * 1.1) if resale > 0 else 3.0
    rel_total = maint_pts + resale_pts
    score += rel_total
    breakdown["Reliability"] = round(rel_total, 1)

    # 7. Driving Context Boosters (up to 15 pts)
    if prefs.get("city_drive") and car.get("city_use"):
        score += 8.0
        reasons.append("Ideal for agile city commuting")
    if prefs.get("highway_drive") and car.get("highway_use"):
        score += 8.0
        reasons.append("High-speed highway stability")
    if (prefs.get("family_friendly") or prefs.get("priority") == "family") and car.get("family_friendly"):
        score += 7.0
        reasons.append("Family-friendly comfort and cabin room")

    # 8. Modern Features & Equipment (up to 10 pts)
    if car.get("adas"):
        score += 4.0
        reasons.append("Advanced ADAS safety assistance")
    if car.get("sunroof"):
        score += 3.0
        reasons.append("Electric sunroof equipped")
    if car.get("carplay_androidauto"):
        score += 3.0

    # 9. User Priority Multipliers
    priority = (prefs.get("priority") or "").lower().strip()
    if "safety" in priority:
        score += safety * 3.0
        reasons.append("Prioritized for top crash safety")
    elif "mileage" in priority or "efficiency" in priority:
        score += mileage * 0.5
        reasons.append("Optimized for maximum fuel savings")
    elif "maintenance" in priority:
        score += maint_pts * 2.0
        reasons.append("Low periodic maintenance burden")
    elif "resale" in priority:
        score += resale_pts * 2.0
        reasons.append("Strong market resale retention")
    elif "performance" in priority:
        score += power_pts * 2.0
        reasons.append("Tuned for performance driving")

    # Normalize score strictly to 60.0 - 99.0 for clear presentation
    max_raw_score = 130.0
    normalized_score = min(99.0, max(60.0, round((score / max_raw_score) * 100.0, 1)))

    if not reasons:
        reasons.append("Matches your core preferences")

    return normalized_score, reasons, breakdown


def rank_and_deduplicate(cars: List[Dict[str, Any]], prefs: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Ranks scored cars and deduplicates by (brand, model).
    Returns the single best variant for each distinct vehicle model unless
    the user explicitly requested a single specific model.
    """
    if not cars:
        return []

    # Check if user explicitly asked for a specific model
    specific_model = prefs.get("model")

    # Sort primarily by score descending, then safety descending, then price ascending
    sorted_cars = sorted(
        cars,
        key=lambda c: (
            float(c.get("score") or 0.0),
            float(c.get("safety_rating") or 0.0),
            -float(c.get("price") or c.get("ex_showroom_price") or 0.0)
        ),
        reverse=True
    )

    if specific_model:
        return sorted_cars[:top_k]

    seen_models = set()
    unique_results = []
    for car in sorted_cars:
        model_key = (car.get("brand", "").lower().strip(), car.get("model", "").lower().strip())
        if model_key not in seen_models:
            seen_models.add(model_key)
            unique_results.append(car)
            if len(unique_results) == top_k:
                break

    # If diverse models were fewer than top_k, fill remaining with other high-scoring variants
    if len(unique_results) < top_k and len(sorted_cars) > len(unique_results):
        added_ids = {c["id"] for c in unique_results if "id" in c}
        for car in sorted_cars:
            if car.get("id") not in added_ids:
                unique_results.append(car)
                added_ids.add(car.get("id"))
                if len(unique_results) == top_k:
                    break

    return unique_results