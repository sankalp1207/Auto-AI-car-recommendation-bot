from pydantic import BaseModel
from typing import Optional


class CarCreate(BaseModel):
    brand: str
    model: str
    variant: str
    ex_showroom_price: float
    body_type: Optional[str] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    engine_cc: Optional[int] = None
    cylinders: Optional[int] = None
    fuel_tank_capacity: Optional[float] = None
    height: Optional[int] = None
    length: Optional[int] = None
    width: Optional[int] = None
    power: Optional[int] = None
    torque: Optional[int] = None
    mileage: Optional[float] = None
    seating: Optional[int] = None
    boot_space: Optional[int] = None
    ground_clearance: Optional[int] = None
    safety_rating: Optional[float] = None
    maintenance_cost: Optional[int] = None
    resale_rating: Optional[float] = None
    city_use: Optional[bool] = None
    highway_use: Optional[bool] = None
    family_friendly: Optional[bool] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    image_url: Optional[str] = None


class CarUpdate(CarCreate):
    pass


class VariantUpdate(BaseModel):
    variant: str


class BulkVariantUpdate(BaseModel):
    brand: str
    model: str
    old_variant: str
    new_variant: str