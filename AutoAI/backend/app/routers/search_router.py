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