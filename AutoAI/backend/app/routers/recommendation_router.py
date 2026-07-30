from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.recommendation import RecommendationRequest
from app.services.recommendation_service import recommend_cars

router = APIRouter(
    prefix="/recommend",
    tags=["Recommendation"]
)


@router.post("/")
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