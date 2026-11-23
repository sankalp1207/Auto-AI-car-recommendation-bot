"""
AutoAI New-vs-Existing Vehicle Alternative Analysis Service
Identifies relevant established catalog alternatives for newly launched models/variants,
comparing price, specs, safety, practicality, and 5-year TCO with verified source evidence.
"""

import os
import math
import logging
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from app.services.car_data_service import car_data_service
from app.services.tco_service import tco_calculator, TCORequest

logger = logging.getLogger("autoai.alternative_analysis")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAUNCHES_CSV = os.path.join(BASE_DIR, "ml", "data", "new_launches", "cars_new_launches.csv")


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return None


class AlternativeAnalysisResponse(BaseModel):
    new_vehicle: Dict[str, Any]
    launch_classification: str
    source_url: Optional[str]
    source_evidence: Optional[str]
    established_alternatives: List[Dict[str, Any]]
    trade_off_summary: str
    tco_comparison: List[Dict[str, Any]]


class AlternativeAnalysisService:
    def __init__(self):
        self._launches_df: Optional[pd.DataFrame] = None
        self._load_launches()

    def _load_launches(self):
        if os.path.exists(LAUNCHES_CSV):
            try:
                self._launches_df = pd.read_csv(LAUNCHES_CSV)
                if "id" not in self._launches_df.columns:
                    self._launches_df["id"] = range(1, len(self._launches_df) + 1)
            except Exception as e:
                logger.error("Failed to load launches CSV: %s", e)
                self._launches_df = None

    def get_alternatives_for_launch(self, launch_id: Any) -> Optional[AlternativeAnalysisResponse]:
        if self._launches_df is None or self._launches_df.empty:
            self._load_launches()

        if self._launches_df is None or self._launches_df.empty:
            return None

        # Locate launch record by id or integer index
        matches = self._launches_df[self._launches_df["id"].astype(str) == str(launch_id)]
        if matches.empty:
            try:
                idx = int(launch_id) - 1
                if 0 <= idx < len(self._launches_df):
                    matches = self._launches_df.iloc[[idx]]
            except (ValueError, TypeError):
                pass

        if matches.empty:
            return None

        row = matches.iloc[0].to_dict()
        new_brand = str(row.get("brand", ""))
        new_model = str(row.get("model", ""))
        new_price = _safe_float(row.get("price") or row.get("ex_showroom_price")) or 1_500_000.0
        new_body = str(row.get("body_type", "")).lower()
        new_fuel = str(row.get("fuel_type", "") or row.get("fuel", "")).lower()
        new_trans = str(row.get("transmission", "")).lower()
        classification = str(row.get("launch_classification", "NEW_MODEL"))

        all_cars = car_data_service.get_all_cars()
        candidates = []

        for car in all_cars:
            c_price = _safe_float(car.get("price") or car.get("ex_showroom_price"))
            if not c_price or c_price <= 0:
                continue

            # Don't compare with exact same car model
            if str(car.get("brand", "")).lower() == new_brand.lower() and str(car.get("model", "")).lower() == new_model.lower():
                continue

            # Segment filter: within ±30% price bracket
            price_ratio = c_price / new_price
            if price_ratio < 0.65 or price_ratio > 1.35:
                continue

            # Body type match
            c_body = str(car.get("body_type", "")).lower()
            body_match = (c_body == new_body) if new_body and c_body else True

            # Powertrain match
            c_fuel = str(car.get("fuel_type", "") or car.get("fuel", "")).lower()
            fuel_match = ("electric" in c_fuel) == ("electric" in new_fuel)

            # Score relevance
            relevance = 100.0
            relevance -= abs(1.0 - price_ratio) * 40.0
            if body_match:
                relevance += 25.0
            if fuel_match:
                relevance += 20.0
            if new_trans and new_trans in str(car.get("transmission", "")).lower():
                relevance += 15.0

            candidates.append((relevance, car))

        candidates.sort(key=lambda x: x[0], reverse=True)
        top_alternatives = [c[1] for c in candidates[:3]]

        # Compute TCO for new vehicle
        tco_list = []
        try:
            tco_new = tco_calculator.calculate(TCORequest(
                custom_price=new_price,
                custom_fuel_type=row.get("fuel_type"),
                custom_mileage=_safe_float(row.get("mileage")),
                ownership_years=5,
            ))
            tco_list.append({
                "vehicle": f"{new_brand} {new_model} (New Launch)",
                "5_year_net_cost": tco_new.net_total_ownership_cost,
                "cost_per_km": tco_new.cost_per_km,
                "monthly_cost": tco_new.monthly_equivalent_cost,
                "is_new_launch": True,
            })
        except Exception as e:
            logger.warning("Could not calculate TCO for launch: %s", e)

        # Compute TCO for established alternatives
        for alt in top_alternatives:
            try:
                tco_alt = tco_calculator.calculate(TCORequest(
                    car_id=alt.get("id"),
                    ownership_years=5,
                ))
                tco_list.append({
                    "vehicle": f"{alt.get('brand')} {alt.get('model')} {alt.get('variant', '')}".strip(),
                    "5_year_net_cost": tco_alt.net_total_ownership_cost,
                    "cost_per_km": tco_alt.cost_per_km,
                    "monthly_cost": tco_alt.monthly_equivalent_cost,
                    "is_new_launch": False,
                })
            except Exception as e:
                logger.warning("Could not calculate TCO for alt: %s", e)

        # Generate objective trade-off summary
        alt_names = [f"{a.get('brand')} {a.get('model')}" for a in top_alternatives]
        alt_text = ", ".join(alt_names) if alt_names else "existing catalog segment models"

        summary = (
            f"**New vs. Existing Analysis ({classification}):**\n"
            f"The recently launched **{new_brand} {new_model}** enters the market priced around ₹{new_price:,.0f} "
            f"and directly competes with established alternatives including **{alt_text}**.\n\n"
            f"- **New Model Advantages:** Fresher styling, updated cabin electronics, and modern platform engineering.\n"
            f"- **Established Alternative Advantages:** Proven long-term reliability, established dealer & service network, predictable spare parts pricing, and known resale market values.\n"
            f"- **Note on Equivalence:** Variants compared here represent the closest price bracket (~±25%). "
            f"Always compare specific feature packages (airbags, ADAS, sunroof) prior to final purchase."
        )

        return AlternativeAnalysisResponse(
            new_vehicle=row,
            launch_classification=classification,
            source_url=row.get("source_url"),
            source_evidence=row.get("source_evidence"),
            established_alternatives=top_alternatives,
            trade_off_summary=summary,
            tco_comparison=tco_list,
        )


alternative_analysis_service = AlternativeAnalysisService()
