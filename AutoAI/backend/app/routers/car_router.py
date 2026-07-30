from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.car_data_service import car_data_service

router = APIRouter(
    prefix="/cars",
    tags=["Cars"]
)


@router.get("/")
def get_all_cars(db: Session = Depends(get_db)):
    return car_data_service.get_all_cars()


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