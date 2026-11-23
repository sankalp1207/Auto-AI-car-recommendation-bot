"""
AutoAI TCO (Total Cost of Ownership) Router
Exposes deterministic automotive cost calculation endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.tco_service import (
    tco_calculator,
    TCORequest,
    TCOResponse,
    FinancingInput,
)
from app.services.car_data_service import car_data_service

router = APIRouter(
    prefix="/tco",
    tags=["Total Cost of Ownership"],
)


class TCOComparisonRequest(BaseModel):
    car_ids: List[int] = Field(..., min_length=2, max_length=4, description="2 to 4 car IDs to compare TCO")
    ownership_years: int = Field(5, ge=1, le=10, description="Ownership period in years")
    annual_kms: float = Field(12000.0, ge=1000.0, le=100000.0, description="Estimated km per year")
    financing_enabled: bool = Field(False, description="Whether to include loan interest in TCO")


class TCOComparisonResponse(BaseModel):
    ownership_years: int
    annual_kms: float
    vehicles: List[TCOResponse]
    summary: dict


@router.post("/calculate", response_model=TCOResponse)
def calculate_tco(req: TCORequest):
    """
    Calculates deterministic total cost of ownership for a car or custom configuration.
    Supports 3, 5, 7 year tenures, fuel/EV electricity costs, IDV-based insurance,
    maintenance escalation, and optional financing interest.
    """
    try:
        return tco_calculator.calculate(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to calculate TCO: {str(e)}")


@router.get("/car/{car_id}", response_model=TCOResponse)
def get_car_tco(
    car_id: int,
    years: int = Query(5, ge=1, le=10, description="Ownership duration: 3, 5, or 7 years"),
    annual_kms: float = Query(12000.0, ge=1000.0, le=100000.0, description="Annual driving distance in km"),
    financing: bool = Query(False, description="Include financing interest estimate"),
):
    """Quick TCO calculation for a catalog car using default or query parameters."""
    car = car_data_service.get_car_by_id(car_id)
    if not car:
        raise HTTPException(status_code=404, detail=f"Car with ID {car_id} not found.")

    req = TCORequest(
        car_id=car_id,
        ownership_years=years,
        annual_kms=annual_kms,
        financing=FinancingInput(enabled=financing),
    )
    return tco_calculator.calculate(req)


@router.post("/compare", response_model=TCOComparisonResponse)
def compare_tco(req: TCOComparisonRequest):
    """Side-by-side TCO calculation for 2 to 4 cars with comparative trade-off summary."""
    results: List[TCOResponse] = []
    for cid in req.car_ids:
        car = car_data_service.get_car_by_id(cid)
        if not car:
            raise HTTPException(status_code=404, detail=f"Car with ID {cid} not found.")
        c_req = TCORequest(
            car_id=cid,
            ownership_years=req.ownership_years,
            annual_kms=req.annual_kms,
            financing=FinancingInput(enabled=req.financing_enabled),
        )
        results.append(tco_calculator.calculate(c_req))

    # Determine winners across dimensions
    lowest_net = min(results, key=lambda x: x.net_total_ownership_cost)
    lowest_fuel = min(results, key=lambda x: x.fuel_total_cost)
    lowest_depr = min(results, key=lambda x: x.total_depreciation)

    summary = {
        "most_economical_overall": lowest_net.vehicle_name,
        "lowest_net_cost": lowest_net.net_total_ownership_cost,
        "lowest_fuel_cost_car": lowest_fuel.vehicle_name,
        "lowest_depreciation_car": lowest_depr.vehicle_name,
        "ownership_period_years": req.ownership_years,
        "annual_distance_km": req.annual_kms,
    }

    return TCOComparisonResponse(
        ownership_years=req.ownership_years,
        annual_kms=req.annual_kms,
        vehicles=results,
        summary=summary,
    )
