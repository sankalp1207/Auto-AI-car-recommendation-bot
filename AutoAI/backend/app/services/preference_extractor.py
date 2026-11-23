"""
Preference extraction service for the AI-Powered Personalized Car Finder.

Architecture:
  1. Fast regex-based extraction (always runs, 0ms, 0 tokens)
  2. Gemini LLM extraction if message is complex or regex found nothing (fallback)
  3. Safe merge: only overwrite if new value is non-null
  4. Validation via CarPreferences Pydantic schema

Design rules:
  - "I'm open to any fuel type" → fuel_type = None (NOT filtered)
  - "around ₹12 lakh" → budget_max set, budget_flexible = True
  - "maximum ₹15 lakh" → budget_max set, budget_flexible = False
  - Never execute generated SQL or code from the LLM
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.schemas.finder import CarPreferences

logger = logging.getLogger("autoai.preference_extractor")

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_LAKH_PATTERN = re.compile(r"₹?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lakhs?|l)\b", re.IGNORECASE)
_CRORE_PATTERN = re.compile(r"₹?\s*(\d+(?:\.\d+)?)\s*(?:crore|crores?|cr)\b", re.IGNORECASE)
_RAW_INR_PATTERN = re.compile(r"₹\s*(\d{5,9})")

_BUDGET_FLOOR_WORDS = re.compile(
    r"\b(minimum|at least|starting from|from|above|over)\b", re.IGNORECASE
)
_BUDGET_CEIL_WORDS = re.compile(
    r"\b(maximum|max|up to|under|below|within|budget is|not more than|less than)\b",
    re.IGNORECASE,
)
_BUDGET_APPROX_WORDS = re.compile(
    r"\b(around|about|approximately|roughly|close to|near|~)\b", re.IGNORECASE
)
_BUDGET_FLEX_WORDS = re.compile(
    r"\b(open to|flexible|can stretch|can go up|maybe a bit more|or so)\b",
    re.IGNORECASE,
)

_FUEL_MAP = {
    r"\b(electric|ev|evs|battery)\b": "Electric",
    r"\bcng\b": "CNG",
    r"\bdiesel\b": "Diesel",
    r"\bpetrol\b": "Petrol",
    r"\b(hybrid|mild.hybrid|strong.hybrid|self.charging)\b": "Hybrid",
}
_ANY_FUEL = re.compile(
    r"\b(any fuel|don.t (care|mind) (about )?(fuel|powertrain)|open to (any|all) fuel)\b",
    re.IGNORECASE,
)

_TRANS_MAP = {
    r"\b(automatic|auto|amt|cvt|dct|dual.clutch|torque.converter)\b": "Automatic",
    r"\b(manual|mt|gear|stick.shift)\b": "Manual",
}
_ANY_TRANS = re.compile(
    r"\b(any transmission|don.t (care|mind) (about )?(transmission|gearbox))\b",
    re.IGNORECASE,
)

_BODY_MAP = {
    r"\bsuv\b": "SUV",
    r"\b(sedan|saloon)\b": "Sedan",
    r"\b(hatchback|hatch)\b": "Hatchback",
    r"\b(mpv|muv|minivan|people.mover)\b": "MPV",
    r"\b(sports?|coupe)\b": "Coupe",
    r"\bconvertible\b": "Convertible",
}

_SEATING_PATTERN = re.compile(
    r"(\d+)\s*(?:seater|seat(er)?s?|person|persons|people|members?|passenger)", re.IGNORECASE
)

_FAMILY_PATTERN = re.compile(r"\bfamily\b", re.IGNORECASE)
_UPCOMING_PATTERN = re.compile(
    r"\b(upcoming|future|launching|unreleased|next.gen|expected)\b", re.IGNORECASE
)
_LUXURY_PATTERN = re.compile(r"\b(luxury|premium luxury|supercar|exotic)\b", re.IGNORECASE)

_KNOWN_BRANDS = [
    "maruti suzuki", "maruti", "hyundai", "tata", "mahindra", "kia", "toyota",
    "honda", "volkswagen", "skoda", "mg", "renault", "nissan", "citroen",
    "jeep", "bmw", "mercedes-benz", "mercedes", "audi", "volvo", "land rover",
    "jaguar", "porsche", "byd", "mini", "ferrari", "lamborghini", "rolls-royce",
    "bentley", "maserati", "aston martin", "force", "isuzu", "lexus", "lotus",
]
_BRAND_NORMALIZE = {
    "maruti suzuki": "Maruti Suzuki",
    "maruti": "Maruti Suzuki",
    "mercedes-benz": "Mercedes-Benz",
    "mercedes": "Mercedes-Benz",
}

_PRIORITY_MAP = {
    r"\b(safe|safety|ncap|star.rating|crash.test)\b": "safety",
    r"\b(mileage|fuel.economy|kmpl|efficient|efficiency)\b": "mileage",
    r"\b(performance|power|fast|sporty|bhp)\b": "performance",
    r"\b(maintenance|service.cost|reliable|reliability)\b": "maintenance",
    r"\b(resale|resell|second.hand.value)\b": "resale",
    r"\b(comfort|comfy|comfortable|luxury.feel)\b": "comfort",
    r"\bfamily\b": "family",
}

_CITY_PATTERN = re.compile(r"\b(city|urban|traffic|commute|stop.and.go)\b", re.IGNORECASE)
_HIGHWAY_PATTERN = re.compile(r"\b(highway|long.drive|touring|cruise|road.trip)\b", re.IGNORECASE)

_EXCLUDE_BRAND_PATTERN = re.compile(
    r"\b(not|no|exclude|avoid|without|except)\b.{0,20}\b(" + "|".join(_KNOWN_BRANDS) + r")\b",
    re.IGNORECASE,
)


def _extract_budget(text: str) -> Dict[str, Any]:
    """Extract budget values with proper hard/soft constraint classification."""
    result: Dict[str, Any] = {
        "budget_min": None,
        "budget_max": None,
        "budget_flexible": False,
    }

    # Find all lakh/crore mentions with position
    lakh_matches = list(_LAKH_PATTERN.finditer(text))
    crore_matches = list(_CRORE_PATTERN.finditer(text))
    raw_matches = list(_RAW_INR_PATTERN.finditer(text))

    def _to_inr(m: re.Match, factor: float) -> float:
        return float(m.group(1)) * factor

    amounts = []
    for m in lakh_matches:
        amounts.append((m.start(), _to_inr(m, 100_000)))
    for m in crore_matches:
        amounts.append((m.start(), _to_inr(m, 10_000_000)))
    for m in raw_matches:
        amounts.append((m.start(), float(m.group(1))))

    if not amounts:
        return result

    # Use the most recent amount if multiple are found
    amounts.sort(key=lambda x: x[0])

    is_floor = bool(_BUDGET_FLOOR_WORDS.search(text))
    is_approx = bool(_BUDGET_APPROX_WORDS.search(text))
    is_flex = bool(_BUDGET_FLEX_WORDS.search(text))
    is_ceil = bool(_BUDGET_CEIL_WORDS.search(text)) or not is_floor

    if len(amounts) >= 2:
        # e.g. "between 10 lakh and 15 lakh"
        result["budget_min"] = amounts[0][1]
        result["budget_max"] = amounts[-1][1]
    else:
        amt = amounts[0][1]
        if is_floor:
            result["budget_min"] = amt
        else:
            result["budget_max"] = amt

    if is_approx or is_flex:
        result["budget_flexible"] = True

    return result


def extract_preferences_regex(text: str) -> Dict[str, Any]:
    """Fast, deterministic regex-based preference extraction. Always safe."""
    t = text.lower()
    result: Dict[str, Any] = {}

    # Budget
    result.update(_extract_budget(t))

    # Fuel type — only set if explicitly mentioned and not "any"
    if not _ANY_FUEL.search(t):
        for pattern, value in _FUEL_MAP.items():
            if re.search(pattern, t, re.IGNORECASE):
                result["fuel_type"] = value
                break

    # Transmission — only set if explicitly mentioned
    if not _ANY_TRANS.search(t):
        for pattern, value in _TRANS_MAP.items():
            if re.search(pattern, t, re.IGNORECASE):
                result["transmission"] = value
                break

    # Body type
    for pattern, value in _BODY_MAP.items():
        if re.search(pattern, t, re.IGNORECASE):
            result["body_type"] = value
            break

    # Seating
    seat_m = _SEATING_PATTERN.search(t)
    if seat_m:
        val = int(seat_m.group(1))
        result["minimum_seating"] = val
        result["family_size"] = val

    # Family
    if _FAMILY_PATTERN.search(t):
        result["family_friendly"] = True
        if not result.get("family_size"):
            result["family_size"] = 4

    # Status
    if _UPCOMING_PATTERN.search(t):
        result["vehicle_status"] = "UPCOMING"

    # Luxury
    if _LUXURY_PATTERN.search(t):
        result["is_luxury"] = True

    # Brands — preferred
    preferred = []
    for brand in _KNOWN_BRANDS:
        if re.search(r"\b" + re.escape(brand) + r"\b", t):
            normalized = _BRAND_NORMALIZE.get(brand, brand.title())
            if normalized not in preferred:
                preferred.append(normalized)
    if preferred:
        result["preferred_brands"] = preferred

    # Priorities
    prios: List[str] = []
    for pattern, prio in _PRIORITY_MAP.items():
        if re.search(pattern, t, re.IGNORECASE):
            if prio not in prios:
                prios.append(prio)
    if prios:
        result["priorities"] = prios
        result["priority"] = prios[0]

    # Driving context
    if _CITY_PATTERN.search(t):
        result["city_drive"] = True
        if "city_usage_percentage" not in result:
            result["city_usage_percentage"] = 70.0
    if _HIGHWAY_PATTERN.search(t):
        result["highway_drive"] = True
        if "highway_usage_percentage" not in result:
            result["highway_usage_percentage"] = 60.0

    return result


def extract_preferences_with_llm(message: str) -> Dict[str, Any]:
    """
    Gemini-powered preference extraction.
    Returns empty dict on any failure — never crashes the pipeline.
    """
    try:
        from app.services.llm_services import get_client
        from app.config import GEMINI_MODEL
        from google.genai import types

        client = get_client()
        if not client:
            return {}

        prompt = f"""Extract car-buyer preferences from this message. Return ONLY a valid JSON object.

Message: "{message}"

JSON fields (use ONLY explicitly stated or strongly implied preferences — omit fields that are unknown or "any"):
- budget_min: integer INR (e.g. 500000 for 5 lakh) — only if a minimum is stated
- budget_max: integer INR — maximum budget
- budget_flexible: boolean — true if user says "around", "approximately", "flexible", etc.
- fuel_type: "Petrol" | "Diesel" | "Electric" | "CNG" | "Hybrid" — omit if "any" or not mentioned
- transmission: "Automatic" | "Manual" — omit if not mentioned or "any"
- body_type: "SUV" | "Sedan" | "Hatchback" | "MPV" — omit if not mentioned
- minimum_seating: integer — minimum number of seats required
- family_size: integer — total family members
- daily_distance_km: float — typical daily km
- city_usage_percentage: float 0-100
- highway_usage_percentage: float 0-100
- priorities: array of strings from: safety | mileage | performance | comfort | maintenance | resale | family
- preferred_brands: array of brand name strings
- excluded_brands: array of brand name strings
- is_luxury: boolean
- vehicle_status: "CURRENT" | "UPCOMING" | "ANY"

Return a JSON object with ONLY the fields that apply. Do not include a field if it is not mentioned.
Return ONLY the raw JSON, no markdown, no explanation.
"""
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=400,
            ),
        )
        raw = (response.text or "").strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(raw)
    except Exception as e:
        logger.warning("LLM preference extraction failed: %s", str(e))
        return {}


def merge_preferences(existing: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge new preference updates into existing accumulated preferences.
    Rules:
    - Lists (priorities, preferred_brands, excluded_brands) are replaced not appended
    - Scalar values only overwrite if new value is non-null / non-empty
    - False booleans do NOT overwrite True booleans (city_drive, family_friendly etc.)
    """
    merged = dict(existing)
    for key, new_val in updates.items():
        if new_val is None:
            continue
        if isinstance(new_val, bool):
            if new_val:  # Only update boolean flags from False → True, never True → False
                merged[key] = True
        elif isinstance(new_val, list):
            if new_val:  # Replace only if non-empty list provided
                merged[key] = new_val
        elif isinstance(new_val, (int, float)) and new_val == 0:
            pass  # Don't overwrite with 0
        else:
            merged[key] = new_val
    return merged


def extract_and_update_preferences(
    message: str,
    existing_preferences: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> CarPreferences:
    """
    Full preference extraction pipeline:
    1. Regex extraction (always runs)
    2. LLM extraction if message is complex and regex found little
    3. Merge with existing session preferences
    4. Validate and return CarPreferences

    Args:
        message: The user's natural-language car query
        existing_preferences: Accumulated preferences from previous turns
        use_llm: Whether to attempt Gemini extraction

    Returns:
        Validated CarPreferences object
    """
    # Stage 1: fast regex extraction
    regex_prefs = extract_preferences_regex(message)

    has_constraints = any(
        regex_prefs.get(k)
        for k in ["budget_max", "budget_min", "fuel_type", "transmission",
                  "body_type", "minimum_seating", "is_luxury", "vehicle_status",
                  "preferred_brands"]
    )

    # Stage 2: LLM extraction if complex message with few regex hits
    llm_prefs: Dict[str, Any] = {}
    if use_llm and len(message.split()) > 4 and not has_constraints:
        llm_prefs = extract_preferences_with_llm(message)

    # Combine: regex takes precedence over LLM for numeric fields
    combined_new: Dict[str, Any] = {}
    if llm_prefs:
        combined_new.update(llm_prefs)
    # Regex values override LLM on conflict (more reliable)
    combined_new.update({k: v for k, v in regex_prefs.items() if v is not None})

    # Stage 3: merge with existing session preferences
    base = existing_preferences or {}
    merged = merge_preferences(base, combined_new)

    # Stage 4: validate
    try:
        return CarPreferences(**merged)
    except Exception as e:
        logger.warning("CarPreferences validation error, using partial data: %s", str(e))
        # Return a best-effort object
        safe_merged = {k: v for k, v in merged.items() if k in CarPreferences.model_fields}
        return CarPreferences(**safe_merged)
