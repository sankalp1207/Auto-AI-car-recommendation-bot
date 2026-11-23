from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ComparisonRequest(BaseModel):
    # Support 2 to 4 car IDs (modern interface)
    car_ids: Optional[List[int]] = Field(None, min_length=2, max_length=4, description="List of 2 to 4 car IDs")

    # Legacy 2-car compatibility fields
    car1_id: Optional[int] = None
    car2_id: Optional[int] = None
    model1: Optional[str] = None
    model2: Optional[str] = None
    car1: Optional[str] = None
    car2: Optional[str] = None

    # Optional TCO and personalization parameters
    ownership_years: int = Field(5, ge=1, le=10, description="Ownership years for TCO estimation")
    annual_kms: float = Field(12000.0, ge=1000.0, le=100000.0, description="Annual distance driven in km")
    preferences: Optional[Dict[str, Any]] = Field(None, description="Optional user preferences profile for personalized suitability scoring")