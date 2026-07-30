import os
import json
from openai import OpenAI

# Dynamic client initialization: Use real OpenAI if key is present, otherwise fallback to local LM Studio
openai_key = os.getenv("OPENAI_API_KEY")
lm_studio_url = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
lm_studio_key = os.getenv("LM_STUDIO_API_KEY", "lm-studio")

if openai_key and not openai_key.startswith("your-") and openai_key.strip() != "":
    client = OpenAI(api_key=openai_key)
    model_name = "gpt-4o-mini"
else:
    client = OpenAI(
        base_url=lm_studio_url,
        api_key=lm_studio_key,
        timeout=10.0,
        max_retries=1,
    )
    model_name = "local-model"

SYSTEM_THINKING_PROMPT = """You are AutoAI, an expert, objective, and intelligent automotive AI advisor.
Your knowledge is strictly limited to the cars provided in the system context.
You must NEVER invent, assume, or extrapolate any specifications, features, prices, or details that are not explicitly present in the context.

Rules:
1. Always base all recommendations, details, and comparisons ONLY on the retrieved car details.
2. If the user asks about a car or specification (such as torque, airbags, or anything else) that is not explicitly present in the provided context, you MUST reply: "Specification not available in the current database."
3. Do not mention any cars or brands that are not listed in the retrieved context.
4. Keep your answers concise, informative, structured in clean Markdown, and under 350 words.
"""

def extract_preferences_llm(message):
    prompt = f"""
Extract the user's car preferences from the message.
Return ONLY valid JSON with ONLY the fields explicitly mentioned or strongly implied by the user.

Possible JSON keys:
"budget" (integer in INR), "fuel_type" (Petrol/Diesel/Electric/CNG/Hybrid), "transmission" (Automatic/Manual), "body_type" (SUV/Sedan/Hatchback/MPV), "family_members" (integer), "priority" (Safety/Mileage/Maintenance/Resale), "city_drive" (boolean), "highway_drive" (boolean).

User Message:
"{message}"
"""
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            timeout=3.0,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        return json.loads(text)
    except Exception as e:
        # Fallback to empty preferences if model call fails
        print(f"LLM Preference Extraction failed: {e}. Falling back to empty preference dict.")
        raise e

def generate_ai_chat_response(user_message: str, recommendations: list, preferences: dict = None):
    rec_summary = ""
    if recommendations:
        rec_summary_list = []
        for c in recommendations[:5]:
            # Convert model object to dictionary if it's not already
            def get_val(obj, attr, default=None):
                if isinstance(obj, dict):
                    return obj.get(attr, default)
                return getattr(obj, attr, default)

            brand = get_val(c, 'brand')
            model = get_val(c, 'model')
            variant = get_val(c, 'variant')
            price = get_val(c, 'price') or get_val(c, 'ex_showroom_price', 0)
            fuel = get_val(c, 'fuel_type') or get_val(c, 'fuel')
            trans = get_val(c, 'transmission')
            mileage = get_val(c, 'mileage')
            engine = get_val(c, 'engine_cc') or get_val(c, 'engine')
            power = get_val(c, 'power')
            torque = get_val(c, 'torque') or "Specification not available in the current database."
            seating = get_val(c, 'seating') or get_val(c, 'seating_capacity')
            boot = get_val(c, 'boot_space')
            gc = get_val(c, 'ground_clearance')
            safety = get_val(c, 'safety_rating')
            sunroof = get_val(c, 'sunroof')
            sunroof_str = "Yes" if sunroof else "No" if sunroof is not None else "Specification not available in the current database."
            adas = get_val(c, 'adas')
            adas_str = "Yes" if adas else "No" if adas is not None else "Specification not available in the current database."
            touchscreen = get_val(c, 'touchscreen_inches')
            touchscreen_str = f"{touchscreen} inches" if touchscreen else "No" if touchscreen is not None else "Specification not available in the current database."
            carplay = get_val(c, 'carplay_androidauto')
            carplay_str = "Yes" if carplay else "No" if carplay is not None else "Specification not available in the current database."
            airbags = get_val(c, 'airbags') or "Specification not available in the current database."
            ideal = get_val(c, 'ideal_for')
            pros = get_val(c, 'pros')
            cons = get_val(c, 'cons')

            specs = (
                f"- **{brand} {model} ({variant})**:\n"
                f"  - Price: ₹{price:,.0f} Ex-Showroom\n"
                f"  - Fuel & Transmission: {fuel} | {trans}\n"
                f"  - Mileage: {mileage} kmpl\n"
                f"  - Engine & Power: {engine} cc | {power} BHP\n"
                f"  - Torque: {torque} Nm\n"
                f"  - Seating & Boot Space: {seating} seater | {boot} L\n"
                f"  - Ground Clearance: {gc} mm\n"
                f"  - Safety Rating & Airbags: {safety}/5 GNCAP stars | {airbags}\n"
                f"  - Sunroof & ADAS: Sunroof={sunroof_str} | ADAS={adas_str}\n"
                f"  - Touchscreen & CarPlay/Android Auto: Screen={touchscreen_str} | CarPlay={carplay_str}\n"
                f"  - Ideal For: {ideal}\n"
                f"  - Pros: {pros}\n"
                f"  - Cons: {cons}\n"
            )
            rec_summary_list.append(specs)
        rec_summary = "\n".join(rec_summary_list)
    else:
        rec_summary = "No matching cars found in the database."

    prompt = f"""
User Query: "{user_message}"

Active User Preferences Context:
{json.dumps(preferences or {}, indent=2)}

Matching Cars Available in Database Context:
{rec_summary}

Instructions: Answer the user's query directly and objectively using only the matching cars and specs above. Follow the System rules closely.
"""
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM_THINKING_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        timeout=8.0,
    )
    return response.choices[0].message.content

def compare_cars_llm(car1, car2):
    def get_val(obj, attr, default=None):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    def format_car(c):
        brand = get_val(c, 'brand')
        model = get_val(c, 'model')
        variant = get_val(c, 'variant')
        price = get_val(c, 'price') or get_val(c, 'ex_showroom_price', 0)
        fuel = get_val(c, 'fuel_type') or get_val(c, 'fuel')
        trans = get_val(c, 'transmission')
        eng = get_val(c, 'engine_cc') or get_val(c, 'engine')
        pwr = get_val(c, 'power')
        trq = get_val(c, 'torque') or "Specification not available in the current database."
        mil = get_val(c, 'mileage')
        seats = get_val(c, 'seating') or get_val(c, 'seating_capacity')
        boot = get_val(c, 'boot_space')
        gc = get_val(c, 'ground_clearance')
        safe = get_val(c, 'safety_rating')
        bags = get_val(c, 'airbags') or "Specification not available in the current database."
        
        sun = get_val(c, 'sunroof')
        sun_str = "Yes" if sun else "No" if sun is not None else "Specification not available in the current database."
        
        adas_val = get_val(c, 'adas')
        adas_str = "Yes" if adas_val else "No" if adas_val is not None else "Specification not available in the current database."
        
        ts_val = get_val(c, 'touchscreen_inches')
        ts_str = f"{ts_val} inches" if ts_val else "Specification not available in the current database."
        
        cp = get_val(c, 'carplay_androidauto')
        cp_str = "Yes" if cp else "No" if cp is not None else "Specification not available in the current database."
        
        pros = get_val(c, 'pros')
        cons = get_val(c, 'cons')
        return (
            f"Car: {brand} {model} {variant}\n"
            f"- Price: ₹{price:,.0f}\n"
            f"- Engine: {eng} cc\n"
            f"- Power: {pwr} bhp\n"
            f"- Torque: {trq} Nm\n"
            f"- Mileage: {mil} km/l\n"
            f"- Transmission: {trans}\n"
            f"- Fuel Type: {fuel}\n"
            f"- Seating: {seats} seats\n"
            f"- Boot Space: {boot} L\n"
            f"- Ground Clearance: {gc} mm\n"
            f"- Airbags: {bags}\n"
            f"- Safety Rating: {safe}/5 Stars\n"
            f"- ADAS: {adas_str}\n"
            f"- Sunroof: {sun_str}\n"
            f"- Touchscreen: {ts_str}\n"
            f"- CarPlay & Android Auto: {cp_str}\n"
            f"- Pros: {pros}\n"
            f"- Cons: {cons}\n"
        )

    prompt = f"""
Compare these two cars thoroughly and summarize the differences objectively:

{format_car(car1)}

---

{format_car(car2)}

Provide a direct, helpful breakdown covering:
1. Verdict & Key Differences
2. Recommendation on who should buy which car based strictly on these specs
"""

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM_THINKING_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        timeout=8.0,
    )
    return response.choices[0].message.content