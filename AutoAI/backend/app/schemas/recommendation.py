from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    brand: str | None = None
    make: str | None = None
    model: str | None = None
    budget: float | None = None
    min_budget: float | None = None
    fuel: str | None = None
    fuel_type: str | None = None
    transmission: str | None = None
    body_type: str | None = None
    seating: int | None = None
    family_members: int | None = None
    status: str | None = "CURRENT"
    priority: str | None = None
    city_drive: bool | None = None
    highway_drive: bool | None = None
    family_friendly: bool | None = None
    is_luxury: bool | None = None
    maintenance_sensitive: bool | None = None