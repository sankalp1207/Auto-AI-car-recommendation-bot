"""
AutoAI Price Intelligence Service
Integrates verified ExtraTreesRegressor ML model (Holdout MAE: ₹9,79,877, R²: 0.5724),
providing estimated ex-showroom ranges, on-road breakdowns, Value-for-Money (VFM) assessments,
and variant price ladders.
"""

import os
import logging
import joblib
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.services.car_data_service import car_data_service

logger = logging.getLogger("autoai.price_intelligence")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(BASE_DIR, "ml", "models", "autoai_price_model.joblib")

# Verified measured holdout metrics from backend/ml/models/training_results.csv
VERIFIED_METRICS = {
    "model_name": "ExtraTreesRegressor Pipeline",
    "evaluation_dataset_rows": 440,
    "training_rows": 1758,
    "cv_folds": 5,
    "mean_absolute_error_inr": 979877.50,
    "root_mean_squared_error_inr": 9932500.11,
    "r2_score": 0.5724,
    "metrics_source": "Holdout Test Split (20% random_state=42)",
}


class PricePredictionRequest(BaseModel):
    car_id: Optional[int] = None
    brand: Optional[str] = "Maruti Suzuki"
    model: Optional[str] = "Swift"
    fuel_type: Optional[str] = "Petrol"
    transmission: Optional[str] = "Manual"
    body_type: Optional[str] = "Hatchback"
    status: Optional[str] = "CURRENT"
    engine_cc: Optional[float] = 1197.0
    power: Optional[float] = 89.0
    torque: Optional[float] = 113.0
    mileage: Optional[float] = 22.0
    seating: Optional[int] = 5
    boot_space: Optional[float] = 318.0
    ground_clearance: Optional[float] = 163.0
    safety_rating: Optional[float] = 4.0


class PriceIntelligenceResponse(BaseModel):
    vehicle_identifier: str
    predicted_ex_showroom: float
    ex_showroom_range_min: float
    ex_showroom_range_max: float
    estimated_on_road: float
    actual_ex_showroom: Optional[float] = None
    price_difference_vs_model: Optional[float] = None
    vfm_score: float = Field(..., description="Value-For-Money score out of 10.0")
    vfm_verdict: str
    variant_ladder: List[Dict[str, Any]]
    segment_benchmarks: List[Dict[str, Any]]
    model_provenance: Dict[str, Any]


class PriceIntelligenceService:
    def __init__(self):
        self._model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(MODEL_PATH):
            try:
                self._model = joblib.load(MODEL_PATH)
                logger.info("Successfully loaded autoai_price_model.joblib")
            except Exception as e:
                logger.error("Failed to load price prediction model: %s", e)
                self._model = None
        else:
            logger.warning("Price model artifact not found at %s", MODEL_PATH)

    def is_available(self) -> bool:
        return self._model is not None

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "model_available": self.is_available(),
            "metrics": VERIFIED_METRICS,
        }

    def predict_price(self, req: PricePredictionRequest) -> PriceIntelligenceResponse:
        actual_price = None
        vehicle_name = f"{req.brand} {req.model}".strip()

        # If car_id provided, hydrate from catalog
        if req.car_id:
            car = car_data_service.get_car_by_id(req.car_id)
            if car:
                req.brand = car.get("brand", req.brand)
                req.model = car.get("model", req.model)
                req.fuel_type = car.get("fuel_type") or car.get("fuel") or req.fuel_type
                req.transmission = car.get("transmission", req.transmission)
                req.body_type = car.get("body_type", req.body_type)
                req.engine_cc = car.get("engine_cc") or req.engine_cc
                req.power = car.get("power") or req.power
                req.torque = car.get("torque") or req.torque
                req.mileage = car.get("mileage") or req.mileage
                req.seating = car.get("seating") or req.seating
                req.boot_space = car.get("boot_space") or req.boot_space
                req.ground_clearance = car.get("ground_clearance") or req.ground_clearance
                req.safety_rating = car.get("safety_rating") or req.safety_rating
                actual_price = car.get("price") or car.get("ex_showroom_price")
                vehicle_name = f"{req.brand} {req.model} {car.get('variant', '')}".strip()

        input_df = pd.DataFrame([{
            "engine_cc": req.engine_cc,
            "power": req.power,
            "torque": req.torque,
            "mileage": req.mileage,
            "seating": req.seating,
            "boot_space": req.boot_space,
            "ground_clearance": req.ground_clearance,
            "safety_rating": req.safety_rating,
            "brand": req.brand,
            "model": req.model,
            "fuel_type": req.fuel_type,
            "transmission": req.transmission,
            "body_type": req.body_type,
            "status": req.status or "CURRENT",
        }])

        if not self._model:
            raise RuntimeError("Price prediction model artifact is unavailable.")

        predicted_val = float(self._model.predict(input_df)[0])
        mae = VERIFIED_METRICS["mean_absolute_error_inr"]

        # Bound predicted range using measured model MAE
        range_min = max(200000.0, round(predicted_val - (mae * 0.5), -3))
        range_max = round(predicted_val + (mae * 0.5), -3)
        predicted_ex_showroom = round(predicted_val, -3)

        # Indian On-Road Calculation estimate: Ex-showroom + RTO (~10%) + Insurance (~3.5%) + TCS/Registration
        fuel_lower = (req.fuel_type or "").lower()
        rto_pct = 0.04 if "electric" in fuel_lower else (0.12 if predicted_ex_showroom > 2000000 else 0.10)
        estimated_on_road = round(predicted_ex_showroom * (1.0 + rto_pct + 0.035), -3)

        # Value-for-Money (VFM) calculation
        diff_vs_model = None
        if actual_price and actual_price > 0:
            diff_vs_model = round(predicted_ex_showroom - actual_price, 2)
            pct_diff = (predicted_ex_showroom - actual_price) / actual_price
            # If actual price is significantly lower than predicted, VFM is high
            vfm_raw = 5.0 + (pct_diff * 15.0)
            vfm_score = round(max(1.0, min(9.9, vfm_raw)), 1)

            if vfm_score >= 7.5:
                vfm_verdict = "Exceptional Value for Money: Actual pricing is lower than predicted feature value."
            elif vfm_score >= 5.0:
                vfm_verdict = "Fair Market Price: Vehicle is priced in line with its mechanical specifications and features."
            else:
                vfm_verdict = "Premium Pricing: Higher market cost compared to baseline technical equipment."
        else:
            vfm_score = 6.5
            vfm_verdict = "Estimated Market Value: Based on Extra Trees regression over 14 technical features."

        # Find variant ladder for same model in catalog
        variant_ladder = []
        all_cars = car_data_service.get_all_cars()
        same_model_cars = [
            c for c in all_cars
            if str(c.get("brand", "")).lower() == str(req.brand).lower()
            and str(c.get("model", "")).lower() == str(req.model).lower()
        ]
        same_model_cars.sort(key=lambda x: float(x.get("price") or x.get("ex_showroom_price") or 0))
        for c in same_model_cars[:6]:
            p = float(c.get("price") or c.get("ex_showroom_price") or 0)
            variant_ladder.append({
                "id": c.get("id"),
                "variant": c.get("variant", "Standard"),
                "fuel_type": c.get("fuel_type") or c.get("fuel"),
                "transmission": c.get("transmission"),
                "ex_showroom_price": p,
            })

        # Segment benchmarks (same body_type, similar price segment)
        segment_benchmarks = []
        target_p = actual_price or predicted_ex_showroom
        comp_cars = [
            c for c in all_cars
            if str(c.get("body_type", "")).lower() == str(req.body_type).lower()
            and str(c.get("brand", "")).lower() != str(req.brand).lower()
            and float(c.get("price") or c.get("ex_showroom_price") or 0) > 0
        ]
        # Sort by price closeness
        comp_cars.sort(key=lambda x: abs(float(x.get("price") or x.get("ex_showroom_price") or 0) - target_p))
        for c in comp_cars[:4]:
            segment_benchmarks.append({
                "id": c.get("id"),
                "name": f"{c.get('brand')} {c.get('model')} {c.get('variant', '')}".strip(),
                "price": float(c.get("price") or c.get("ex_showroom_price") or 0),
                "mileage": c.get("mileage"),
                "safety_rating": c.get("safety_rating"),
                "power": c.get("power"),
            })

        return PriceIntelligenceResponse(
            vehicle_identifier=vehicle_name,
            predicted_ex_showroom=predicted_ex_showroom,
            ex_showroom_range_min=range_min,
            ex_showroom_range_max=range_max,
            estimated_on_road=estimated_on_road,
            actual_ex_showroom=actual_price,
            price_difference_vs_model=diff_vs_model,
            vfm_score=vfm_score,
            vfm_verdict=vfm_verdict,
            variant_ladder=variant_ladder,
            segment_benchmarks=segment_benchmarks,
            model_provenance=VERIFIED_METRICS,
        )


price_intelligence_service = PriceIntelligenceService()
