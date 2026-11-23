from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.services.car_data_service import car_data_service

router = APIRouter(
    prefix="/search",
    tags=["Search"],
)


@router.get("")
@router.get("/")
def search(
    make: Optional[str] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    query: Optional[str] = None,
    q: Optional[str] = None,
    search: Optional[str] = None,
    fuel: Optional[str] = None,
    fuel_type: Optional[str] = None,
    transmission: Optional[str] = None,
    body_type: Optional[str] = None,
    budget: Optional[float] = None,
    seating: Optional[int] = None,
    status: Optional[str] = "CURRENT",
    page: Optional[int] = None,
    limit: Optional[int] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = "asc",
    db: Session = Depends(get_db),
):
    if status and status.upper() != "ALL":
        cars = car_data_service.get_all_cars(status=status)
    else:
        cars = car_data_service.get_all_cars()

    actual_make = make or brand
    if actual_make:
        cars = [c for c in cars if actual_make.lower().strip() in str(c.get("brand") or "").lower()]

    search_term = q or query or search
    if search_term:
        term = search_term.lower().strip()
        cars = [
            c for c in cars
            if term in str(c.get("model") or "").lower()
            or term in str(c.get("brand") or "").lower()
            or term in str(c.get("variant") or "").lower()
        ]

    if model:
        cars = [c for c in cars if model.lower().strip() in str(c.get("model") or "").lower()]

    actual_fuel = fuel or fuel_type
    if actual_fuel:
        cars = [c for c in cars if actual_fuel.lower().strip() in str(c.get("fuel_type") or "").lower()]

    if transmission:
        cars = [c for c in cars if transmission.lower().strip() in str(c.get("transmission") or "").lower()]

    if body_type:
        from app.services.score_service import classify_body_type
        req_b = body_type.lower().strip()
        cars = [
            c for c in cars
            if req_b in str(c.get("body_type") or "").lower()
            or req_b in classify_body_type(c.get("model"), c.get("variant"), c.get("brand"), c.get("body_type")).lower()
        ]

    if budget is not None:
        cars = [
            c for c in cars
            if c.get("price") is not None and float(c.get("price") or 0.0) <= budget
        ]

    if seating is not None:
        cars = [
            c for c in cars
            if c.get("seating") is not None and int(c.get("seating") or 0) >= seating
        ]

    if sort_by:
        reverse = (order or "asc").lower() == "desc"
        def _sort_key(c):
            val = c.get(sort_by)
            if val is None:
                return float("-inf") if reverse else float("inf")
            try:
                return float(val)
            except (ValueError, TypeError):
                return str(val).lower()
        cars = sorted(cars, key=_sort_key, reverse=reverse)

    if limit is not None and limit > 0:
        p = max(1, page or 1)
        start = (p - 1) * limit
        end = start + limit
        cars = cars[start:end]

    if not cars:
        raise HTTPException(
            status_code=404,
            detail="No matching vehicles were found. Try increasing your budget or changing your filters."
        )

    return cars


from pydantic import BaseModel, Field
from typing import Dict, Any, List
from app.services.preference_extractor import extract_and_update_preferences
from app.services.score_service import classify_body_type


class NaturalSearchRequest(BaseModel):
    query: str = Field(..., description="Natural language vehicle query, e.g., 'Automatic petrol SUVs under 12 lakh'")
    limit: Optional[int] = Field(20, ge=1, le=100)
    status: Optional[str] = "CURRENT"
    include_new_launches: Optional[bool] = False


class NaturalSearchResponse(BaseModel):
    query: str
    parsed_criteria: Dict[str, Any]
    total_found: int
    items: List[Dict[str, Any]]
    explanation: str


@router.post("/natural", response_model=NaturalSearchResponse)
def natural_language_search(req: NaturalSearchRequest):
    """
    Extracts structured constraints from natural language queries and filters catalog records
    using parameterized logic. Never executes raw LLM-generated SQL.
    """
    prefs = extract_and_update_preferences(req.query)
    all_cars = car_data_service.get_all_cars(status=req.status if req.status != "ALL" else None)

    # Check if query references new launches
    is_launch_query = bool(
        req.include_new_launches or
        any(k in req.query.lower() for k in ["launched recently", "new launch", "latest launch", "newly launched"])
    )

    if is_launch_query:
        import os
        import pandas as pd
        launches_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "ml", "data", "new_launches", "cars_new_launches.csv"
        )
        if os.path.exists(launches_path):
            try:
                launch_df = pd.read_csv(launches_path)
                for r in launch_df.to_dict(orient="records"):
                    all_cars.append(r)
            except Exception:
                pass

    filtered = []
    for c in all_cars:
        # Budget filter
        price = c.get("price") or c.get("ex_showroom_price")
        if price is not None:
            try:
                p_val = float(price)
                if prefs.budget_max is not None and p_val > prefs.budget_max:
                    continue
                if prefs.budget_min is not None and p_val < prefs.budget_min:
                    continue
            except (ValueError, TypeError):
                pass

        # Fuel type filter
        if prefs.fuel_type:
            c_fuel = str(c.get("fuel_type") or c.get("fuel") or "").lower()
            if prefs.fuel_type.lower() not in c_fuel:
                continue

        # Transmission filter
        if prefs.transmission:
            c_trans = str(c.get("transmission") or "").lower()
            if prefs.transmission.lower() not in c_trans:
                continue

        # Body type filter
        if prefs.body_type:
            c_body = str(c.get("body_type") or "").lower()
            inferred = classify_body_type(c.get("model"), c.get("variant"), c.get("brand"), c.get("body_type")).lower()
            if prefs.body_type.lower() not in c_body and prefs.body_type.lower() not in inferred:
                continue

        # Seating filter
        if prefs.minimum_seating:
            c_seat = c.get("seating") or c.get("seating_capacity")
            if c_seat is not None:
                try:
                    if int(c_seat) < prefs.minimum_seating:
                        continue
                except (ValueError, TypeError):
                    pass

        # Brand filter
        if prefs.preferred_brands:
            c_brand = str(c.get("brand") or "").lower()
            if not any(pb.lower() in c_brand for pb in prefs.preferred_brands):
                continue

        # Excluded brands
        if prefs.excluded_brands:
            c_brand = str(c.get("brand") or "").lower()
            if any(eb.lower() in c_brand for eb in prefs.excluded_brands):
                continue

        filtered.append(c)

    # Build clear explanation of applied constraints
    applied_parts = []
    if prefs.budget_max:
        applied_parts.append(f"budget under ₹{prefs.budget_max / 100000:.1f} Lakh")
    if prefs.fuel_type:
        applied_parts.append(f"fuel: {prefs.fuel_type}")
    if prefs.transmission:
        applied_parts.append(f"transmission: {prefs.transmission}")
    if prefs.body_type:
        applied_parts.append(f"body type: {prefs.body_type}")
    if prefs.minimum_seating:
        applied_parts.append(f"seating ≥ {prefs.minimum_seating}")
    if prefs.preferred_brands:
        applied_parts.append(f"brands: {', '.join(prefs.preferred_brands)}")


    explanation = (
        f"Found {len(filtered)} vehicles matching criteria: " + ", ".join(applied_parts)
        if applied_parts else f"Found {len(filtered)} vehicles matching '{req.query}'."
    )

    limit = req.limit or 20
    return NaturalSearchResponse(
        query=req.query,
        parsed_criteria=prefs.model_dump(exclude_none=True),
        total_found=len(filtered),
        items=filtered[:limit],
        explanation=explanation,
    )