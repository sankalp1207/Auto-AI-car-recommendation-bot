"""
Schemas for the AI-Powered Personalized Car Finder.

Preference fields use three sentinel values:
  - None  → user has not mentioned this preference (unknown)
  - field value → explicit user preference
  - flexible flags distinguish hard constraints from soft hints
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Preference object — produced by preference extraction, stored in session
# ---------------------------------------------------------------------------

class CarPreferences(BaseModel):
    """Structured representation of a car-buyer's stated preferences."""

    # Budget
    budget_min: Optional[float] = Field(None, ge=0, description="Minimum budget in INR (ex-showroom)")
    budget_max: Optional[float] = Field(None, ge=0, description="Maximum budget in INR (ex-showroom)")
    budget_flexible: bool = Field(False, description="True when user indicated budget is negotiable")

    # Powertrain
    fuel_type: Optional[str] = Field(None, description="Petrol | Diesel | Electric | CNG | Hybrid | None=unknown")
    transmission: Optional[str] = Field(None, description="Automatic | Manual | None=unknown")

    # Body & Usage
    body_type: Optional[str] = Field(None, description="SUV | Sedan | Hatchback | MPV | None=unknown")
    family_size: Optional[int] = Field(None, ge=1, le=15, description="Number of family members")
    minimum_seating: Optional[int] = Field(None, ge=2, le=9, description="Hard minimum seat count")

    # Driving context
    daily_distance_km: Optional[float] = Field(None, ge=0, description="Typical daily distance in km")
    city_usage_percentage: Optional[float] = Field(None, ge=0, le=100, description="% of city driving")
    highway_usage_percentage: Optional[float] = Field(None, ge=0, le=100, description="% of highway driving")

    # Priorities (ordered list of strings)
    priorities: List[str] = Field(
        default_factory=list,
        description="Ordered soft priorities: safety | mileage | performance | comfort | maintenance | resale | family"
    )

    # Brand preferences
    preferred_brands: List[str] = Field(default_factory=list, description="Brands the user prefers")
    excluded_brands: List[str] = Field(default_factory=list, description="Brands the user wants to exclude")
    excluded_models: List[str] = Field(default_factory=list, description="Specific models to exclude")

    # Segment / luxury
    is_luxury: bool = Field(False)

    # Status filter
    vehicle_status: str = Field("CURRENT", description="CURRENT | UPCOMING | ANY")

    # Derived booleans for quick filter access
    city_drive: bool = Field(False)
    highway_drive: bool = Field(False)
    family_friendly: bool = Field(False)

    # Raw legacy priority string (used by score_service)
    priority: Optional[str] = Field(None, description="Top single priority key")

    @field_validator("fuel_type")
    @classmethod
    def normalize_fuel(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        mapping = {
            "ev": "Electric", "electric": "Electric",
            "petrol": "Petrol", "gasoline": "Petrol",
            "diesel": "Diesel",
            "cng": "CNG",
            "hybrid": "Hybrid", "mild hybrid": "Hybrid", "strong hybrid": "Hybrid",
        }
        return mapping.get(v.lower().strip(), v.strip().title())

    @field_validator("transmission")
    @classmethod
    def normalize_transmission(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_lower = v.lower().strip()
        if any(k in v_lower for k in ["auto", "amt", "cvt", "dct", "at"]):
            return "Automatic"
        if "manual" in v_lower or v_lower == "mt":
            return "Manual"
        return v.strip().title()

    @field_validator("vehicle_status")
    @classmethod
    def normalize_status(cls, v: str) -> str:
        upper = v.upper().strip()
        if upper not in {"CURRENT", "UPCOMING", "ANY"}:
            return "CURRENT"
        return upper

    @model_validator(mode="after")
    def derive_booleans(self) -> "CarPreferences":
        """Derive city/highway/family booleans from percentage fields."""
        if self.city_usage_percentage is not None and self.city_usage_percentage >= 50:
            self.city_drive = True
        if self.highway_usage_percentage is not None and self.highway_usage_percentage >= 50:
            self.highway_drive = True
        if self.family_size is not None and self.family_size >= 4:
            self.family_friendly = True
        if self.minimum_seating is not None and self.minimum_seating >= 6:
            self.family_friendly = True
        # Sync priority from priorities list
        if self.priorities and not self.priority:
            self.priority = self.priorities[0]
        return self

    def to_recommendation_dict(self) -> Dict[str, Any]:
        """Convert to the format expected by recommend_cars()."""
        return {
            "budget": self.budget_max,
            "min_budget": self.budget_min,
            "brand": self.preferred_brands[0] if len(self.preferred_brands) == 1 else None,
            "fuel_type": self.fuel_type,
            "fuel": self.fuel_type,
            "transmission": self.transmission,
            "body_type": self.body_type,
            "seating": self.minimum_seating or self.family_size,
            "family_members": self.family_size,
            "status": "CURRENT" if self.vehicle_status == "ANY" else self.vehicle_status,
            "priority": self.priority,
            "city_drive": self.city_drive,
            "highway_drive": self.highway_drive,
            "family_friendly": self.family_friendly,
            "is_luxury": self.is_luxury,
        }


# ---------------------------------------------------------------------------
# API request / response
# ---------------------------------------------------------------------------

class FinderRequest(BaseModel):
    """Request body for the /finder endpoint."""
    message: str = Field(..., min_length=1, max_length=2000, description="User's natural-language car query")
    session_id: Optional[str] = Field(None, description="Session identifier for preference continuity")
    reset_session: bool = Field(False, description="Clear accumulated preferences and start fresh")


class ScoreBreakdown(BaseModel):
    """Per-dimension scoring breakdown for a recommendation."""
    value: Optional[float] = None
    safety: Optional[float] = None
    efficiency: Optional[float] = None
    performance: Optional[float] = None
    practicality: Optional[float] = None
    reliability: Optional[float] = None


class CarRecommendation(BaseModel):
    """A single car recommendation with scores and explanations."""
    id: int
    brand: str
    model: str
    variant: str
    price: float
    price_basis: str = "Ex-Showroom"
    status: str
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    seating_capacity: Optional[int] = None
    mileage: Optional[float] = None
    power: Optional[float] = None
    safety_rating: Optional[float] = None
    engine_cc: Optional[int] = None
    boot_space: Optional[int] = None
    ground_clearance: Optional[int] = None
    sunroof: Optional[bool] = None
    adas: Optional[bool] = None
    touchscreen_inches: Optional[float] = None
    carplay_androidauto: Optional[bool] = None
    image: Optional[str] = None
    ideal_for: Optional[str] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    source_url: str = "https://www.carwale.com"

    # Scoring
    suitability_score: float = Field(..., ge=0, le=100)
    matched_requirements: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    trade_offs: List[str] = Field(default_factory=list)
    missing_data: List[str] = Field(default_factory=list)
    score_breakdown: Optional[Dict[str, float]] = None

    model_config = {"from_attributes": True}


class FinderResponse(BaseModel):
    """Response from the /finder endpoint."""
    session_id: str
    preferences: Dict[str, Any]
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    recommendations: List[CarRecommendation] = Field(default_factory=list)
    total_matched: int = 0
    ai_response: str = ""
    no_results_reason: Optional[str] = None
    alternative_suggestions: List[str] = Field(default_factory=list)
