from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.database.database import get_db
from app.schemas.recommendation import RecommendationRequest
from app.services.recommendation_service import recommend_cars

router = APIRouter(
    prefix="/recommend",
    tags=["Recommendation"]
)


@router.post("", response_model=List[Dict[str, Any]])
@router.post("/", response_model=List[Dict[str, Any]])
def recommend(
    request: RecommendationRequest,
    db: Session = Depends(get_db),
):
    recs = recommend_cars(request, db)
    if not recs:
        raise HTTPException(
            status_code=404,
            detail="No matching vehicles were found. Try increasing your budget or changing your filters."
        )
    return recs


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def recommend_get(
    brand: Optional[str] = Query(None, description="Brand/Make filter"),
    model: Optional[str] = Query(None, description="Model filter"),
    budget: Optional[float] = Query(None, description="Maximum price in INR"),
    fuel: Optional[str] = Query(None, description="Fuel type (Petrol, Diesel, Electric, CNG, Hybrid)"),
    transmission: Optional[str] = Query(None, description="Transmission (Manual, Automatic)"),
    body_type: Optional[str] = Query(None, description="Body style (SUV, Sedan, Hatchback, MPV)"),
    seating: Optional[int] = Query(None, description="Minimum seating capacity"),
    status: Optional[str] = Query("CURRENT", description="Vehicle status (CURRENT, UPCOMING)"),
    priority: Optional[str] = Query(None, description="User priority: safety, mileage, performance, family"),
    city_drive: Optional[bool] = Query(False, description="City driving orientation"),
    highway_drive: Optional[bool] = Query(False, description="Highway driving orientation"),
    family_friendly: Optional[bool] = Query(False, description="Family suitability priority"),
    db: Session = Depends(get_db),
):
    req = RecommendationRequest(
        brand=brand,
        model=model,
        budget=budget,
        fuel=fuel,
        transmission=transmission,
        body_type=body_type,
        seating=seating,
        status=status,
        priority=priority,
        city_drive=city_drive,
        highway_drive=highway_drive,
        family_friendly=family_friendly
    )
    recs = recommend_cars(req, db)
    if not recs:
        raise HTTPException(
            status_code=404,
            detail="No matching vehicles were found. Try increasing your budget or changing your filters."
        )
    return recs