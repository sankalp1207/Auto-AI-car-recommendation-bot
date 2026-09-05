import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.car import Car
from app.services.car_data_service import car_data_service
from app.services.score_service import (
    classify_body_type,
    is_luxury_brand,
    calculate_recommendation_score,
    rank_and_deduplicate
)

logger = logging.getLogger("autoai.recommendation")


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def recommend_cars(request: Any, db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """
    Deterministic recommendation pipeline where PostgreSQL is the source of truth.
    
    Pipeline Stages:
    1. Preference Extraction & Normalization
    2. Hard Constraint Filtering (Status, Budget, Brand, Fuel, Transmission, Seating, Body Type)
    3. Candidate Cars Gathering
    4. Deterministic Multi-Factor Scoring (Safety, Mileage, Performance, Use Cases, Priorities)
    5. Deduplication by Model (to ensure diverse choices instead of repetitive trims)
    6. Return Top Ranked Matches
    """
    # 1. Normalize Request Parameters
    brand = _get_attr(request, "brand") or _get_attr(request, "make")
    model = _get_attr(request, "model")
    budget = _get_attr(request, "budget")
    min_budget = _get_attr(request, "min_budget")
    fuel = _get_attr(request, "fuel") or _get_attr(request, "fuel_type")
    transmission = _get_attr(request, "transmission")
    body_type = _get_attr(request, "body_type")
    seating = _get_attr(request, "seating") or _get_attr(request, "family_members")
    status = (_get_attr(request, "status") or "CURRENT").strip().upper()
    priority = _get_attr(request, "priority")
    city_drive = bool(_get_attr(request, "city_drive"))
    highway_drive = bool(_get_attr(request, "highway_drive"))
    family_friendly = bool(_get_attr(request, "family_friendly"))
    is_luxury = bool(_get_attr(request, "is_luxury"))

    # Validate numeric budget safely
    budget_val: Optional[float] = None
    if budget is not None:
        try:
            parsed = float(budget)
            if parsed > 0:
                budget_val = parsed
            else:
                # Impossible or zero/negative budget -> guaranteed zero results
                return []
        except (ValueError, TypeError):
            budget_val = None

    min_budget_val: Optional[float] = None
    if min_budget is not None:
        try:
            min_budget_val = float(min_budget)
        except (ValueError, TypeError):
            min_budget_val = None

    seating_val: Optional[int] = None
    if seating is not None:
        try:
            seating_val = int(seating)
        except (ValueError, TypeError):
            seating_val = None

    # 2. Source Candidate Cars from Synchronized Dataset / DB
    # Uses in-memory cache synchronized idempotently with PostgreSQL cars table
    all_cached_cars = car_data_service.get_all_cars()
    if not all_cached_cars:
        # Fallback to direct DB query if cache not initialized yet
        session = db or SessionLocal()
        try:
            db_cars = session.query(Car).all()
            all_cached_cars = [car_data_service._car_to_dict(c) for c in db_cars]
        finally:
            if not db:
                session.close()

    candidates: List[Dict[str, Any]] = []

    for car in all_cached_cars:
        car_status = (car.get("status") or "CURRENT").strip().upper()

        # HARD CONSTRAINT 1: Status Partitioning (CURRENT vs UPCOMING)
        if status in {"CURRENT", "UPCOMING"}:
            if car_status != status:
                continue

        # HARD CONSTRAINT 2: Maximum Budget
        car_price = float(car.get("price") or car.get("ex_showroom_price") or 0.0)
        if budget_val is not None:
            if car_price <= 0 or car_price > budget_val:
                continue

        # Optional Minimum Budget
        if min_budget_val is not None and car_price < min_budget_val:
            continue

        # HARD CONSTRAINT 3: Brand / Make
        if brand:
            b_norm = brand.strip().lower()
            c_brand = (car.get("brand") or "").strip().lower()
            if b_norm not in c_brand and c_brand not in b_norm:
                continue

        # HARD CONSTRAINT 4: Model
        if model:
            m_norm = model.strip().lower()
            c_model = (car.get("model") or "").strip().lower()
            if m_norm not in c_model:
                continue

        # HARD CONSTRAINT 5: Fuel Type
        if fuel:
            f_norm = fuel.strip().lower()
            c_fuel = (car.get("fuel_type") or "").strip().lower()
            # Support aliases like 'ev' -> 'electric'
            if f_norm in {"ev", "evs", "electric"}:
                if "electric" not in c_fuel and "ev" not in c_fuel:
                    continue
            elif f_norm not in c_fuel:
                continue

        # HARD CONSTRAINT 6: Transmission
        if transmission:
            t_norm = transmission.strip().lower()
            c_trans = (car.get("transmission") or "").strip().lower()
            if "auto" in t_norm or "amt" in t_norm or "cvt" in t_norm or "dct" in t_norm:
                if "auto" not in c_trans and "amt" not in c_trans and "cvt" not in c_trans and "dct" not in c_trans:
                    continue
            elif "manual" in t_norm:
                if "manual" not in c_trans:
                    continue
            elif t_norm not in c_trans:
                continue

        # HARD CONSTRAINT 7: Seating Capacity
        if seating_val and seating_val > 0:
            c_seats = int(car.get("seating") or car.get("seating_capacity") or 0)
            if c_seats < seating_val:
                continue

        # HARD CONSTRAINT 8: Body Type
        # Resolves body type via classifier or stored metadata
        inferred_body = classify_body_type(
            car.get("model"),
            car.get("variant"),
            car.get("brand"),
            car.get("body_type")
        )
        # Update car dictionary body_type if it was 'Unknown'
        if not car.get("body_type") or car.get("body_type") == "Unknown":
            car["body_type"] = inferred_body

        if body_type:
            req_body = body_type.strip().lower()
            if req_body not in inferred_body.lower() and req_body not in (car.get("body_type") or "").lower():
                continue

        # HARD CONSTRAINT 9: Luxury Segment
        if is_luxury:
            if not is_luxury_brand(car.get("brand")):
                continue

        candidates.append(car)

    # 3. Handle Zero Matches
    if not candidates:
        return []

    # 4. Score Valid Candidates
    prefs_dict = {
        "budget": budget_val,
        "priority": priority,
        "city_drive": city_drive,
        "highway_drive": highway_drive,
        "family_friendly": family_friendly,
        "model": model,
    }

    scored_candidates = []
    for cand in candidates:
        norm_score, reasons, breakdown = calculate_recommendation_score(cand, prefs_dict)
        scored_candidates.append({
            **cand,
            "score": norm_score,
            "reasons": reasons,
            "score_breakdown": breakdown,
        })

    # 5. Rank and Deduplicate by Model
    top_results = rank_and_deduplicate(scored_candidates, prefs_dict, top_k=5)

    return top_results