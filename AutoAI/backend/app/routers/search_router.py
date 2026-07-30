from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.services.car_data_service import car_data_service

router = APIRouter(
    prefix="/search",
    tags=["Search"],
)


@router.get("/")
def search(
    make: str = None,
    brand: str = None,
    model: str = None,
    fuel: str = None,
    fuel_type: str = None,
    transmission: str = None,
    body_type: str = None,
    budget: float = None,
    seating: int = None,
    db: Session = Depends(get_db),
):
    cars = car_data_service.get_all_cars()

    actual_make = make or brand
    if actual_make:
        cars = [c for c in cars if actual_make.lower().strip() in c["brand"].lower()]

    if model:
        cars = [c for c in cars if model.lower().strip() in c["model"].lower()]

    actual_fuel = fuel or fuel_type
    if actual_fuel:
        cars = [c for c in cars if actual_fuel.lower().strip() in c["fuel_type"].lower()]

    if transmission:
        cars = [c for c in cars if transmission.lower().strip() in c["transmission"].lower()]

    if body_type:
        cars = [c for c in cars if body_type.lower().strip() in c["body_type"].lower()]

    if budget:
        cars = [c for c in cars if c["price"] <= budget]

    if seating:
        cars = [c for c in cars if c["seating"] >= seating]

    if not cars:
        raise HTTPException(
            status_code=404,
            detail="No matching vehicles were found. Try increasing your budget or changing your filters."
        )

    return cars