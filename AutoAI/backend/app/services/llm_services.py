import os
import json
import logging
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TIMEOUT
from app.services.ai_service import explain_recommendations

logger = logging.getLogger("autoai.llm")

# Initialize client lazily and safely
_client = None
if GEMINI_API_KEY:
    try:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.warning("Could not initialize Google GenAI Client: %s", str(e))


def get_client() -> Optional[genai.Client]:
    global _client
    if _client is None and GEMINI_API_KEY:
        try:
            _client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            logger.warning("Could not initialize Google GenAI Client: %s", str(e))
    return _client


SYSTEM_THINKING_PROMPT = """You are AutoAI, an expert, objective, and intelligent automotive AI advisor.
Your knowledge is strictly grounded in and limited to the verified cars provided in the system context.
You must NEVER invent, assume, extrapolate, or hallucinate any specifications, features, prices, or details that are not explicitly present in the context.

Strict Rules:
1. Always base all recommendations, details, rankings, and comparisons ONLY on the retrieved car details.
2. If the user asks about a car or specification that is not explicitly present in the provided context, you MUST reply: "Specification not available in the current database."
3. Do not mention any cars or brands that are not listed in the retrieved context.
4. If no cars are found in the context, clearly explain that no vehicles match in the current database. Never invent or hallucinate any car.
5. Keep your answers concise, informative, structured in clean Markdown, and under 250 words.
"""


def format_compact_specs(recommendations: List[Dict[str, Any]]) -> str:
    """
    Ultra token-efficient car spec formatting.
    Sends only the top 5 relevant cars in a compact structured format.
    """
    if not recommendations:
        return "No matching cars found in the database."

    specs_list = []
    for i, c in enumerate(recommendations[:5], start=1):
        brand = c.get("brand", "Unknown")
        model = c.get("model", "Unknown")
        variant = c.get("variant", "Standard")
        price = float(c.get("price") or c.get("ex_showroom_price") or 0.0)
        fuel = c.get("fuel_type") or "N/A"
        trans = c.get("transmission") or "N/A"
        mileage = c.get("mileage", 0)
        power = c.get("power", 0)
        safety = c.get("safety_rating", 0)
        seating = c.get("seating", 5)
        maint = c.get("maintenance_cost", 0)
        score = c.get("score", 0)
        reasons = "; ".join(c.get("reasons", [])[:2]) if c.get("reasons") else "Matches criteria"

        entry = (
            f"{i}. **{brand} {model} ({variant})**\n"
            f"   - Price: Rs. {price:,.0f} Ex-Showroom | Fuel: {fuel} | Trans: {trans}\n"
            f"   - Specs: {mileage} km/l | {power} bhp | {seating} Seater | Safety: {safety}/5 Stars\n"
            f"   - Maintenance: Rs. {maint:,.0f}/yr | Match Score: {score}/100\n"
            f"   - Match Reasons: {reasons}"
        )
        specs_list.append(entry)

    return "\n\n".join(specs_list)


def extract_preferences_llm(message: str) -> Dict[str, Any]:
    """
    Extracts structured preferences using Gemini if needed.
    Falls back to empty dict on failure without crashing.
    """
    client = get_client()
    if not client:
        raise RuntimeError("Gemini client is not initialized.")

    prompt = f"""Extract the user's car preferences from the message.
Return ONLY valid JSON with ONLY the fields explicitly mentioned or strongly implied.

Possible JSON keys:
"brand" (string), "budget" (integer in INR), "status" ("CURRENT" or "UPCOMING"),
"fuel_type" (Petrol/Diesel/Electric/CNG/Hybrid), "transmission" (Automatic/Manual),
"body_type" (SUV/Sedan/Hatchback/MPV), "seating" (integer), "family_friendly" (boolean),
"is_luxury" (boolean), "priority" (Safety/Mileage/Maintenance/Resale/Performance),
"city_drive" (boolean), "highway_drive" (boolean).

User Message: "{message}"
"""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=250,
            ),
        )
        text = response.text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        return json.loads(text)
    except Exception as e:
        logger.warning("LLM preference extraction error: %s", str(e))
        raise e


def generate_ai_chat_response(
    user_message: str,
    recommendations: List[Dict[str, Any]],
    preferences: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Generates an objective, fact-grounded response from Gemini.
    - Grounded strictly on retrieved database cars
    - Token-efficient candidate formatting
    - Multi-turn conversational context aware
    - Graceful fallback on API failure or missing client
    """
    client = get_client()
    if not client:
        logger.info("Gemini client unavailable, using deterministic explanation.")
        return explain_recommendations(user_message, recommendations, preferences)

    rec_summary = format_compact_specs(recommendations)

    # Build concise conversation history block if available
    history_block = ""
    if conversation_history:
        history_lines = []
        for turn in conversation_history[-4:]:
            role = "User" if turn.get("role") == "user" else "AutoAI"
            history_lines.append(f"{role}: {turn.get('text', '')}")
        if history_lines:
            history_block = "Recent Conversation Context:\n" + "\n".join(history_lines) + "\n\n"

    prompt = f"""{history_block}Current User Query: "{user_message}"

Active Search Preferences:
{json.dumps(preferences or {}, indent=2)}

Verified Matching Cars in Database:
{rec_summary}

Instructions:
Answer the user's query directly and objectively using only the matching cars and specs above.
If the user asks a follow-up comparison (e.g. mileage, maintenance, features), compare the verified cars listed above.
If no matching cars are found, explain clearly that no vehicles match in the database.
NEVER invent or hallucinate any vehicles. Follow system instructions strictly.
"""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_THINKING_PROMPT,
                temperature=0.2,
                max_output_tokens=450,
            ),
        )
        if response.text and response.text.strip():
            return response.text.strip()
        raise ValueError("Empty response received from Gemini.")
    except Exception as e:
        logger.warning("Gemini chat generation failed: %s. Using deterministic fallback.", str(e))
        return explain_recommendations(user_message, recommendations, preferences)


def compare_cars_llm(car1: Any, car2: Any) -> str:
    """Compares two specific cars using Gemini, grounded on database records."""
    client = get_client()

    def _val(c, attr, default="N/A"):
        if isinstance(c, dict):
            return c.get(attr, default)
        return getattr(c, attr, default)

    c1_str = (
        f"{_val(car1, 'brand')} {_val(car1, 'model')} ({_val(car1, 'variant')}): "
        f"Price: Rs. {float(_val(car1, 'price') or _val(car1, 'ex_showroom_price') or 0):,.0f}, "
        f"Fuel: {_val(car1, 'fuel_type')}, Trans: {_val(car1, 'transmission')}, "
        f"Mileage: {_val(car1, 'mileage')} kmpl, Power: {_val(car1, 'power')} bhp, "
        f"Safety: {_val(car1, 'safety_rating')}/5"
    )
    c2_str = (
        f"{_val(car2, 'brand')} {_val(car2, 'model')} ({_val(car2, 'variant')}): "
        f"Price: Rs. {float(_val(car2, 'price') or _val(car2, 'ex_showroom_price') or 0):,.0f}, "
        f"Fuel: {_val(car2, 'fuel_type')}, Trans: {_val(car2, 'transmission')}, "
        f"Mileage: {_val(car2, 'mileage')} kmpl, Power: {_val(car2, 'power')} bhp, "
        f"Safety: {_val(car2, 'safety_rating')}/5"
    )

    if not client:
        return f"### Comparison\n- **Car 1:** {c1_str}\n- **Car 2:** {c2_str}"

    prompt = f"""Compare these two cars based strictly on their verified specifications:
Car 1: {c1_str}
Car 2: {c2_str}

Provide a concise, objective comparison highlighting differences in price, power, mileage, and safety, followed by a recommendation on who should buy which car. Under 200 words.
"""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_THINKING_PROMPT,
                temperature=0.2,
                max_output_tokens=350,
            ),
        )
        return response.text.strip()
    except Exception as e:
        logger.warning("Gemini compare failed: %s", str(e))
        return f"### Comparison\n- **Car 1:** {c1_str}\n- **Car 2:** {c2_str}"