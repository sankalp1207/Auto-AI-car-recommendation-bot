"""
AutoAI Price Intelligence Router
Exposes ML-backed price prediction, Value-for-Money assessment, and verified model metrics.
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.price_intelligence_service import (
    price_intelligence_service,
    PricePredictionRequest,
    PriceIntelligenceResponse,
)

router = APIRouter(
    prefix="/price",
    tags=["Price Intelligence"],
)


@router.get("/metrics")
def get_price_model_metrics():
    """Returns verified holdout metrics (MAE, RMSE, R²) and provenance for the price model."""
    return price_intelligence_service.get_metrics()


@router.post("/predict", response_model=PriceIntelligenceResponse)
def predict_price_range(req: PricePredictionRequest):
    """
    Predicts ex-showroom price, bounded range, estimated on-road pricing,
    and calculates Value-For-Money (VFM) score based on technical equipment.
    """
    try:
        return price_intelligence_service.predict_price(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Price intelligence error: {str(e)}")


@router.get("/car/{car_id}", response_model=PriceIntelligenceResponse)
def get_car_price_intelligence(car_id: int):
    """Fetches ML price prediction, VFM rating, and segment benchmarks for a catalog vehicle."""
    try:
        req = PricePredictionRequest(car_id=car_id)
        return price_intelligence_service.predict_price(req)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Car not found or prediction failed: {str(e)}")
