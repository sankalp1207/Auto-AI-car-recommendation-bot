"""
AutoAI Total Cost of Ownership (TCO) Calculator Engine
Deterministic, mathematically sound automotive cost modeling for India.

Key Calculations:
  - Fuel / Electricity Expenditure (based on fuel efficiency or EV battery/range)
  - Scheduled Maintenance (based on manufacturer schedules and car age)
  - Comprehensive & Third-Party Insurance (following Indian IDV depreciation rules)
  - Financing Interest Cost (without double-counting purchase price and loan repayments)
  - Estimated Resale Value & Depreciation (governed by market resale ratings)
  - Net Total Ownership Cost, Cost per Kilometre, and Monthly Equivalent Cost
"""

import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.services.car_data_service import car_data_service

# Standard Fuel & Energy Rates in India (INR)
DEFAULT_PETROL_PRICE_PER_LITRE = 104.0
DEFAULT_DIESEL_PRICE_PER_LITRE = 93.0
DEFAULT_CNG_PRICE_PER_KG = 85.0
DEFAULT_EV_ELECTRICITY_PER_KWH = 9.5

# IRDAI standard vehicle depreciation scale for Insured Declared Value (IDV)
IDV_DEPRECIATION_SCALE = {
    1: 0.95,  # Up to 6 months to 1 yr
    2: 0.80,  # 1-2 yrs
    3: 0.70,  # 2-3 yrs
    4: 0.60,  # 3-4 yrs
    5: 0.50,  # 4-5 yrs
    6: 0.45,  # 5-6 yrs
    7: 0.40,  # 6-7 yrs
}


class FinancingInput(BaseModel):
    enabled: bool = False
    down_payment_pct: float = Field(20.0, ge=0.0, le=90.0, description="Down payment percentage")
    loan_tenure_years: int = Field(5, ge=1, le=7, description="Loan tenure in years")
    annual_interest_rate_pct: float = Field(9.0, ge=4.0, le=20.0, description="Annual loan interest rate %")


class TCORequest(BaseModel):
    car_id: Optional[int] = None
    custom_price: Optional[float] = None
    custom_fuel_type: Optional[str] = None
    custom_mileage: Optional[float] = None
    custom_maintenance_cost: Optional[float] = None
    custom_resale_rating: Optional[float] = None
    ownership_years: int = Field(5, ge=1, le=10, description="Ownership duration: 3, 5, or 7 years")
    annual_kms: float = Field(12000.0, ge=1000.0, le=100000.0, description="Estimated distance driven per year")
    custom_fuel_price: Optional[float] = None
    financing: FinancingInput = Field(default_factory=FinancingInput)


class TCOYearlyBreakdown(BaseModel):
    year: int
    fuel_cost: float
    maintenance_cost: float
    insurance_cost: float
    financing_interest: float
    depreciation_loss: float
    cumulative_net_cost: float


class TCOResponse(BaseModel):
    vehicle_name: str
    ex_showroom_price: float
    on_road_estimated_price: float
    ownership_years: int
    total_distance_km: float
    fuel_total_cost: float
    maintenance_total_cost: float
    insurance_total_cost: float
    financing_interest_total: float
    estimated_resale_value: float
    total_depreciation: float
    net_total_ownership_cost: float
    cost_per_km: float
    monthly_equivalent_cost: float
    yearly_breakdown: List[TCOYearlyBreakdown]
    assumptions: Dict[str, Any]


class TCOCalculator:
    """Deterministic, transparent automotive ownership cost calculator."""

    def calculate(self, req: TCORequest) -> TCOResponse:
        # 1. Resolve vehicle specifications
        car = None
        if req.car_id:
            car = car_data_service.get_car_by_id(req.car_id)

        brand = car.get("brand", "Vehicle") if car else "Custom Vehicle"
        model = car.get("model", "") if car else ""
        variant = car.get("variant", "") if car else ""
        vehicle_name = f"{brand} {model} {variant}".strip()

        # Price
        price = req.custom_price or (car.get("price") if car else None) or (car.get("ex_showroom_price") if car else None) or 1_000_000.0

        # Fuel type
        fuel = (req.custom_fuel_type or (car.get("fuel_type") if car else None) or (car.get("fuel") if car else None) or "Petrol").strip()

        # Mileage / Energy consumption
        mileage = req.custom_mileage or (car.get("mileage") if car else None)
        if not mileage or mileage <= 0:
            if "electric" in fuel.lower():
                mileage = 6.0  # ~6 km per kWh equivalent
            elif "diesel" in fuel.lower():
                mileage = 18.0
            elif "cng" in fuel.lower():
                mileage = 24.0
            else:
                mileage = 15.0

        # Annual maintenance baseline
        base_annual_maintenance = req.custom_maintenance_cost or (car.get("maintenance_cost") if car else None)
        if not base_annual_maintenance or base_annual_maintenance <= 0:
            # Standard heuristic for passenger vehicles: ~1.2% of car value annually
            base_annual_maintenance = max(6000.0, price * 0.012)

        # Resale rating
        resale_rating = req.custom_resale_rating or (car.get("resale_rating") if car else None) or 3.8

        years = req.ownership_years
        annual_kms = req.annual_kms
        total_kms = annual_kms * years

        # Road tax & Registration (RTO in India is roughly 9% to 12% depending on price/fuel)
        rto_rate = 0.04 if "electric" in fuel.lower() else (0.12 if price > 2_000_000 else 0.09)
        one_time_rto_tax = price * rto_rate
        on_road_estimated_price = price + one_time_rto_tax

        # Fuel price per unit
        if req.custom_fuel_price and req.custom_fuel_price > 0:
            unit_price = req.custom_fuel_price
        else:
            if "electric" in fuel.lower():
                unit_price = DEFAULT_EV_ELECTRICITY_PER_KWH
            elif "diesel" in fuel.lower():
                unit_price = DEFAULT_DIESEL_PRICE_PER_LITRE
            elif "cng" in fuel.lower():
                unit_price = DEFAULT_CNG_PRICE_PER_KG
            else:
                unit_price = DEFAULT_PETROL_PRICE_PER_LITRE

        # Annual fuel expenditure
        annual_fuel_units = annual_kms / mileage
        annual_fuel_cost = annual_fuel_units * unit_price

        # Financing EMI & Interest
        financing_interest_total = 0.0
        yearly_interest_distribution = [0.0] * years
        if req.financing and req.financing.enabled:
            down_payment = price * (req.financing.down_payment_pct / 100.0)
            principal = price - down_payment
            tenure_months = min(years, req.financing.loan_tenure_years) * 12
            monthly_rate = (req.financing.annual_interest_rate_pct / 100.0) / 12.0

            if monthly_rate > 0 and tenure_months > 0:
                emi = principal * monthly_rate * ((1 + monthly_rate) ** tenure_months) / (((1 + monthly_rate) ** tenure_months) - 1)
                total_loan_payments = emi * tenure_months
                financing_interest_total = max(0.0, total_loan_payments - principal)

                # Distribute interest front-loaded over loan years
                remaining_principal = principal
                loan_years = min(years, req.financing.loan_tenure_years)
                for y in range(loan_years):
                    year_interest = 0.0
                    for _ in range(12):
                        m_interest = remaining_principal * monthly_rate
                        m_principal = emi - m_interest
                        year_interest += m_interest
                        remaining_principal -= m_principal
                    yearly_interest_distribution[y] = max(0.0, year_interest)

        # Yearly breakdown simulation
        yearly_breakdown: List[TCOYearlyBreakdown] = []
        cumulative_fuel = 0.0
        cumulative_maint = 0.0
        cumulative_ins = 0.0
        cumulative_interest = 0.0

        # Resale value curve calculation based on resale rating
        # Rating 5.0 -> 5-year retention ~54%, Rating 3.0 -> ~40%, Rating 1.0 -> ~28%
        retention_multiplier = 0.85 + (resale_rating - 3.5) * 0.06

        prev_car_val = price
        for y in range(1, years + 1):
            # Inflation on fuel (~3% annual drift)
            y_fuel = annual_fuel_cost * ((1.03) ** (y - 1))
            cumulative_fuel += y_fuel

            # Maintenance increases with vehicle aging (~8% per year)
            y_maint = base_annual_maintenance * ((1.08) ** (y - 1))
            cumulative_maint += y_maint

            # Insurance on depreciating IDV
            idv_factor = IDV_DEPRECIATION_SCALE.get(y, max(0.20, 0.40 - (y - 7) * 0.05))
            current_idv = price * idv_factor
            y_ins = max(3500.0, current_idv * 0.032)
            cumulative_ins += y_ins

            y_interest = yearly_interest_distribution[y - 1] if y - 1 < len(yearly_interest_distribution) else 0.0
            cumulative_interest += y_interest

            # Depreciation for this year
            cur_car_val = price * (idv_factor * retention_multiplier)
            y_depr = max(0.0, prev_car_val - cur_car_val)
            prev_car_val = cur_car_val

            cum_net = (price - cur_car_val) + cumulative_fuel + cumulative_maint + cumulative_ins + cumulative_interest + one_time_rto_tax

            yearly_breakdown.append(
                TCOYearlyBreakdown(
                    year=y,
                    fuel_cost=round(y_fuel, 2),
                    maintenance_cost=round(y_maint, 2),
                    insurance_cost=round(y_ins, 2),
                    financing_interest=round(y_interest, 2),
                    depreciation_loss=round(y_depr, 2),
                    cumulative_net_cost=round(cum_net, 2),
                )
            )

        # Final end-of-tenure valuations
        final_idv_factor = IDV_DEPRECIATION_SCALE.get(years, max(0.20, 0.40 - (years - 7) * 0.05))
        estimated_resale_value = round(price * final_idv_factor * retention_multiplier, 2)
        total_depreciation = round(price - estimated_resale_value, 2)

        net_total = round(
            total_depreciation + cumulative_fuel + cumulative_maint + cumulative_ins + cumulative_interest + one_time_rto_tax,
            2,
        )
        cost_per_km = round(net_total / total_kms, 2)
        monthly_cost = round(net_total / (years * 12), 2)

        return TCOResponse(
            vehicle_name=vehicle_name,
            ex_showroom_price=round(price, 2),
            on_road_estimated_price=round(on_road_estimated_price, 2),
            ownership_years=years,
            total_distance_km=round(total_kms, 1),
            fuel_total_cost=round(cumulative_fuel, 2),
            maintenance_total_cost=round(cumulative_maint, 2),
            insurance_total_cost=round(cumulative_ins, 2),
            financing_interest_total=round(cumulative_interest, 2),
            estimated_resale_value=estimated_resale_value,
            total_depreciation=total_depreciation,
            net_total_ownership_cost=net_total,
            cost_per_km=cost_per_km,
            monthly_equivalent_cost=monthly_cost,
            yearly_breakdown=yearly_breakdown,
            assumptions={
                "fuel_type": fuel,
                "efficiency": f"{mileage} km/l or km/kWh",
                "unit_fuel_price": f"₹{unit_price} per unit",
                "annual_distance": f"{annual_kms:,.0f} km/year",
                "resale_rating": f"{resale_rating}/5.0",
                "rto_registration_estimate": f"₹{one_time_rto_tax:,.0f}",
                "financing_enabled": req.financing.enabled if req.financing else False,
            },
        )


tco_calculator = TCOCalculator()
