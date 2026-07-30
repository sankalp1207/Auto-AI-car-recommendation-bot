from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.car_data_service import car_data_service
from app.schemas.comparison import ComparisonRequest
from app.services.comparison_service import compare_cars
from app.services.llm_services import compare_cars_llm

router = APIRouter(
    prefix="/compare",
    tags=["Comparison"]
)


@router.get("/cars")
def get_all_cars(db: Session = Depends(get_db)):
    cars = car_data_service.get_all_cars()
    return [
        {
            "id": car["id"],
            "brand": car["brand"],
            "model": car["model"],
            "variant": car["variant"],
        }
        for car in cars
    ]


@router.post("/")
def compare_by_ids(
    request: ComparisonRequest,
    db: Session = Depends(get_db),
):
    result = compare_cars(request, db)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No matching vehicles were found. Try increasing your budget or changing your filters."
        )
    return result


@router.get("/")
def compare_by_names(
    car1: str,
    car2: str,
    db: Session = Depends(get_db)
):
    first = car_data_service.get_car_by_model(car1)
    second = car_data_service.get_car_by_model(car2)

    if not first or not second:
        raise HTTPException(
            status_code=404,
            detail="No matching vehicles were found. Try increasing your budget or changing your filters."
        )

    try:
        explanation = compare_cars_llm(first, second)
    except Exception:
        explanation = "AI Comparison currently unavailable."

    return {
        "car1": first,
        "car2": second,
        "explanation": explanation
    }