from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.car_data_service import car_data_service

router = APIRouter(
    prefix="/cars",
    tags=["Cars"]
)


@router.get("")
@router.get("/")
def get_all_cars(status: str = None, db: Session = Depends(get_db)):
    return car_data_service.get_all_cars(status=status)


@router.get("/stats")
def get_cars_stats():
    cars = car_data_service.get_all_cars()
    total = len(cars)
    current = sum(1 for c in cars if c.get("status") == "CURRENT")
    upcoming = sum(1 for c in cars if c.get("status") == "UPCOMING")
    brands = len(set(c.get("brand") for c in cars if c.get("brand")))
    return {
        "total_cars": total,
        "current_cars": current,
        "upcoming_cars": upcoming,
        "total_brands": brands,
    }


@router.get("/{model_or_id}")
def get_car(model_or_id: str, db: Session = Depends(get_db)):
    if model_or_id.isdigit():
        car = car_data_service.get_car_by_id(int(model_or_id))
    else:
        car = car_data_service.get_car_by_model(model_or_id)

    if not car:
        raise HTTPException(
            status_code=404,
            detail="No matching vehicles were found. Try increasing your budget or changing your filters."
        )

    return car