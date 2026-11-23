"""
AutoAI Multi-Vehicle Comparison Service
Supports 2 to 4 vehicle comparisons with grounded specs, deterministic TCO calculations,
personalized suitability analysis, and AI or deterministic trade-off explanations.
"""

import logging
from typing import Any, Dict, List, Optional
from app.services.car_data_service import car_data_service
from app.services.tco_service import tco_calculator, TCORequest
from app.services.llm_services import get_client, SYSTEM_THINKING_PROMPT, GEMINI_MODEL
from google.genai import types

logger = logging.getLogger("autoai.comparison")


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        import math
        return None if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return None


def _format_car_specs_text(car: Dict[str, Any]) -> str:
    brand = car.get("brand", "")
    model = car.get("model", "")
    variant = car.get("variant", "")
    price = _safe_float(car.get("price") or car.get("ex_showroom_price")) or 0.0
    fuel = car.get("fuel_type") or car.get("fuel") or "N/A"
    trans = car.get("transmission") or "N/A"
    mileage = car.get("mileage")
    power = car.get("power")
    safety = car.get("safety_rating")
    boot = car.get("boot_space")
    seating = car.get("seating") or car.get("seating_capacity")

    return (
        f"- {brand} {model} {variant}: Price: ₹{price:,.0f} | Fuel: {fuel} | Trans: {trans} | "
        f"Mileage: {mileage if mileage is not None else 'N/A'} km/l | Power: {power if power is not None else 'N/A'} bhp | "
        f"Safety: {safety if safety is not None else 'N/A'}/5 Stars | Boot: {boot if boot is not None else 'N/A'}L | Seating: {seating if seating is not None else 'N/A'}"
    )


def generate_deterministic_tradeoffs(cars: List[Dict[str, Any]], tco_list: List[Dict[str, Any]]) -> str:
    """Generates an objective, factual trade-off summary when Gemini is offline or unavailable."""
    if not cars:
        return "No vehicles available for comparison."

    lines = ["### Multi-Vehicle Trade-Off Analysis\n"]

    # Compare prices
    valid_prices = [(c, _safe_float(c.get("price") or c.get("ex_showroom_price"))) for c in cars]
    valid_prices = [(c, p) for c, p in valid_prices if p is not None]
    if valid_prices:
        cheapest = min(valid_prices, key=lambda x: x[1])
        priciest = max(valid_prices, key=lambda x: x[1])
        if cheapest[0]["id"] != priciest[0]["id"]:
            lines.append(f"- **Purchase Price Advantage:** **{cheapest[0]['brand']} {cheapest[0]['model']}** starts lower at ₹{cheapest[1]:,.0f}, while **{priciest[0]['brand']} {priciest[0]['model']}** is priced at ₹{priciest[1]:,.0f}.")

    # Compare TCO
    if tco_list and len(tco_list) >= 2:
        lowest_tco = min(tco_list, key=lambda x: x.get("net_total_ownership_cost", float("inf")))
        lines.append(f"- **5-Year Ownership Economy:** **{lowest_tco.get('vehicle_name')}** yields the lowest estimated net cost of ownership (₹{lowest_tco.get('net_total_ownership_cost', 0):,.0f}) over 5 years.")

    # Compare Mileage
    valid_mileage = [(c, _safe_float(c.get("mileage"))) for c in cars]
    valid_mileage = [(c, m) for c, m in valid_mileage if m is not None and m > 0]
    if valid_mileage:
        best_mileage = max(valid_mileage, key=lambda x: x[1])
        lines.append(f"- **Fuel / Energy Efficiency:** **{best_mileage[0]['brand']} {best_mileage[0]['model']}** leads with {best_mileage[1]} km/l or equivalent efficiency.")

    # Compare Power
    valid_power = [(c, _safe_float(c.get("power"))) for c in cars]
    valid_power = [(c, p) for c, p in valid_power if p is not None and p > 0]
    if valid_power:
        best_power = max(valid_power, key=lambda x: x[1])
        lines.append(f"- **Performance & Powertrain:** **{best_power[0]['brand']} {best_power[0]['model']}** delivers the highest power output at {best_power[1]} bhp.")

    # Compare Safety
    valid_safety = [(c, _safe_float(c.get("safety_rating"))) for c in cars]
    valid_safety = [(c, s) for c, s in valid_safety if s is not None and s > 0]
    if valid_safety:
        best_safety = max(valid_safety, key=lambda x: x[1])
        lines.append(f"- **Safety Rating:** **{best_safety[0]['brand']} {best_safety[0]['model']}** boasts a {best_safety[1]}/5 crash test rating.")

    lines.append("\n**Buyer Recommendation Summary:**")
    for c in cars:
        b = c.get("brand", "")
        m = c.get("model", "")
        v = c.get("variant", "")
        fuel = c.get("fuel_type") or c.get("fuel") or "Standard"
        lines.append(f"- Choose **{b} {m} ({v})** if your primary focus is {fuel}-powertrain reliability and brand-specific driving dynamics.")

    return "\n".join(lines)


def compare_cars(request, db=None) -> Optional[Dict[str, Any]]:
    """
    Main comparison handler supporting 2 to 4 cars.
    Preserves backward compatibility with 2-car requests while adding TCO,
    multi-vehicle comparison matrix, and transparent trade-offs.
    """
    car_objs: List[Dict[str, Any]] = []

    # 1. Resolve car IDs from request
    car_ids = getattr(request, "car_ids", None)
    if car_ids and isinstance(car_ids, list):
        for cid in car_ids:
            c = car_data_service.get_car_by_id(cid)
            if c and c not in car_objs:
                car_objs.append(c)
    else:
        # Legacy fallback
        c1_id = getattr(request, "car1_id", None)
        c2_id = getattr(request, "car2_id", None)
        m1 = getattr(request, "model1", None) or getattr(request, "car1", None)
        m2 = getattr(request, "model2", None) or getattr(request, "car2", None)

        c1 = car_data_service.get_car_by_id(c1_id) if c1_id else (car_data_service.get_car_by_model(m1) if m1 else None)
        c2 = car_data_service.get_car_by_id(c2_id) if c2_id else (car_data_service.get_car_by_model(m2) if m2 else None)

        if c1:
            car_objs.append(c1)
        if c2:
            car_objs.append(c2)

    if len(car_objs) < 2:
        return None

    # Limit to maximum 4 cars
    car_objs = car_objs[:4]

    # 2. Compute TCO for each car
    years = getattr(request, "ownership_years", 5) or 5
    annual_kms = getattr(request, "annual_kms", 12000.0) or 12000.0

    tco_results = []
    for car in car_objs:
        try:
            tco_req = TCORequest(
                car_id=car.get("id"),
                ownership_years=years,
                annual_kms=annual_kms,
            )
            tco_resp = tco_calculator.calculate(tco_req)
            tco_results.append(tco_resp.model_dump())
        except Exception as e:
            logger.warning("Failed TCO for car %s: %s", car.get("id"), e)
            tco_results.append({
                "vehicle_name": f"{car.get('brand')} {car.get('model')}",
                "error": "TCO calculation unavailable for this specification."
            })

    # 3. Generate trade-off summary via Gemini or deterministic engine
    explanation = None
    client = get_client()
    if client:
        car_specs_text = "\n".join([_format_car_specs_text(c) for c in car_objs])
        prompt = f"""Compare these {len(car_objs)} vehicles objectively based strictly on their verified specifications:
{car_specs_text}

Provide a structured, unbiased comparison highlighting:
1. Pricing & Value Proposition
2. Performance & Fuel Efficiency
3. Cabin Space, Safety & Practicality
4. Target Buyer Verdict: Which buyer profile should choose which vehicle?

Keep it concise, factual, under 250 words. Do not invent any unverified specifications."""
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_THINKING_PROMPT,
                    temperature=0.2,
                    max_output_tokens=400,
                ),
            )
            if resp.text and resp.text.strip():
                explanation = resp.text.strip()
        except Exception as e:
            logger.warning("Gemini comparison failed: %s. Using deterministic trade-offs.", e)

    if not explanation:
        explanation = generate_deterministic_tradeoffs(car_objs, tco_results)

    # 4. Construct comprehensive comparison payload
    response = {
        "cars": car_objs,
        "tco_estimates": tco_results,
        "explanation": explanation,
        # Backward compatibility fields for legacy frontend callers expecting car1/car2
        "car1": car_objs[0],
        "car2": car_objs[1],
    }

    if len(car_objs) > 2:
        response["car3"] = car_objs[2]
    if len(car_objs) > 3:
        response["car4"] = car_objs[3]

    return response