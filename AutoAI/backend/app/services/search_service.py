from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from app.models.car import Car


def search_cars(
    db: Session,
    brand: Optional[str] = None,
    make: Optional[str] = None,
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
) -> List[Car]:

    db_query = db.query(Car)

    if status and status.upper() != "ALL":
        db_query = db_query.filter(Car.status == status.upper().strip())

    actual_brand = make or brand
    if actual_brand:
        db_query = db_query.filter(Car.brand.ilike(f"%{actual_brand.strip()}%"))

    search_term = q or query or search
    if search_term:
        term = f"%{search_term.strip()}%"
        db_query = db_query.filter(
            (Car.brand.ilike(term)) |
            (Car.model.ilike(term)) |
            (Car.variant.ilike(term))
        )

    if model:
        db_query = db_query.filter(Car.model.ilike(f"%{model.strip()}%"))

    actual_fuel = fuel or fuel_type
    if actual_fuel:
        db_query = db_query.filter(Car.fuel_type.ilike(f"%{actual_fuel.strip()}%"))

    if transmission:
        db_query = db_query.filter(Car.transmission.ilike(f"%{transmission.strip()}%"))

    if body_type:
        db_query = db_query.filter(Car.body_type.ilike(f"%{body_type.strip()}%"))

    if budget is not None:
        db_query = db_query.filter(Car.ex_showroom_price <= budget)

    if seating is not None:
        db_query = db_query.filter(Car.seating >= seating)

    if sort_by and hasattr(Car, sort_by):
        col = getattr(Car, sort_by)
        if order and order.lower() == "desc":
            db_query = db_query.order_by(desc(col))
        else:
            db_query = db_query.order_by(asc(col))

    if limit is not None and limit > 0:
        p = max(1, page or 1)
        offset = (p - 1) * limit
        db_query = db_query.offset(offset).limit(limit)

    return db_query.all()