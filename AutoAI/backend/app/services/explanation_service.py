import logging
from typing import Any
from google import genai

from app.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("autoai.explanation")

_client = None
if GEMINI_API_KEY:
    try:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.warning("Could not initialize Gemini client: %s", str(e))


def get_client():
    global _client
    if _client is None and GEMINI_API_KEY:
        try:
            _client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            logger.warning("Could not initialize Gemini client: %s", str(e))
    return _client


def _get_val(obj: Any, attr: str, default: Any = "N/A") -> Any:
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def explain_car(car: Any, user_preferences: Any) -> str:
    """
    Explain why a specific database-selected car is suitable for the user.
    Gemini is used ONLY to explain the database-sourced vehicle.
    If Gemini is unavailable, a deterministic fallback explanation is provided.
    """
    brand = _get_val(car, "brand")
    model = _get_val(car, "model")
    variant = _get_val(car, "variant")
    price = _get_val(car, "price", _get_val(car, "ex_showroom_price", 0))
    fuel = _get_val(car, "fuel_type", _get_val(car, "fuel"))
    trans = _get_val(car, "transmission")
    mileage = _get_val(car, "mileage")
    power = _get_val(car, "power")
    safety = _get_val(car, "safety_rating")
    maintenance = _get_val(car, "maintenance_cost")
    resale = _get_val(car, "resale_rating")
    reasons = _get_val(car, "reasons", [])

    client = get_client()
    if client:
        prompt = f"""
You are an expert, objective automobile advisor for AutoAI.
You MUST strictly use only the vehicle specifications provided below. Do NOT invent, assume, or alter any vehicle data.

User Preferences:
{user_preferences}

Verified Car from Database:
Brand: {brand}
Model: {model}
Variant: {variant}
Price: Rs. {price:,.0f} Ex-Showroom
Fuel: {fuel}
Transmission: {trans}
Mileage: {mileage} km/l
Power: {power} bhp
Safety Rating: {safety}/5 Stars
Maintenance Cost: Rs. {maintenance} / year
Resale Rating: {resale}/5

Key Strengths / Match Reasons:
{', '.join(reasons) if reasons else 'Matches criteria'}

Explain in concise, professional English:
1. Why this car matches the user's requirements.
2. Key pros based strictly on specs above.
3. Realistic considerations / cons.
4. Who should buy it.

Maximum 150 words.
"""
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=300,
                ),
            )
            return response.text.strip()
        except Exception as e:
            logger.warning("Gemini explain_car call failed: %s. Using deterministic explanation.", str(e))

    # High-quality deterministic fallback explanation
    reasons_text = "; ".join(reasons) if reasons else "Matches your core requirements"
    return (
        f"### {brand} {model} ({variant})\n"
        f"**Why it matches:** {reasons_text}.\n"
        f"**Key Specs:** Rs. {price:,.0f} | {fuel} | {trans} | {mileage} km/l | {safety}/5 Stars Safety.\n"
        f"**Ideal Buyer:** Drivers seeking proven reliability, segment-leading comfort, and strong value within this budget range."
    )