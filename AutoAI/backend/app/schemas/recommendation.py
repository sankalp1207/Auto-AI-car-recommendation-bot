from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    budget: float | None = None
    fuel: str | None = None
    fuel_type: str | None = None
    transmission: str | None = None
    body_type: str | None = None
    seating: int | None = None
    family_members: int | None = None
    priority: str | None = None
    city_drive: bool | None = None
    highway_drive: bool | None = None
    maintenance_sensitive: bool | None = None