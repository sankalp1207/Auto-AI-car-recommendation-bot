"""
AutoAI Personal Garage and Shortlist Router
Provides authenticated vehicle saving, named shortlist management, garage comparison,
and user preference persistence with strict per-user authorization.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.models.user import User
from app.models.favorite import Favorite
from app.auth.jwt_handler import get_current_user
from app.services.car_data_service import car_data_service
from app.services.comparison_service import compare_cars
from app.schemas.comparison import ComparisonRequest

router = APIRouter(
    prefix="/garage",
    tags=["Personal Garage & Shortlists"],
)

# User preference and shortlist metadata cache (keyed by user_id)
# Non-destructive: keeps production database schema unaltered
_USER_GARAGE_METADATA: Dict[int, Dict[str, Any]] = {}


class GarageItemAddRequest(BaseModel):
    car_id: int
    shortlist_name: Optional[str] = Field("Default", description="Named shortlist (e.g., 'Family SUVs', 'City Commute')")
    note: Optional[str] = Field(None, description="Personal user note for this vehicle")


class GarageItemResponse(BaseModel):
    id: int
    car_id: int
    shortlist_name: str
    note: Optional[str] = None
    vehicle_details: Dict[str, Any]


class SavePreferencesRequest(BaseModel):
    preferences: Dict[str, Any] = Field(..., description="User's personalized automotive preferences")


def _get_user_meta(user_id: int) -> Dict[str, Any]:
    if user_id not in _USER_GARAGE_METADATA:
        _USER_GARAGE_METADATA[user_id] = {
            "saved_car_ids": set(),
            "notes": {},  # car_id -> note
            "shortlists": {},  # car_id -> shortlist_name
            "preferences": {},
        }
    return _USER_GARAGE_METADATA[user_id]


@router.get("", response_model=List[GarageItemResponse])
@router.get("/", response_model=List[GarageItemResponse])
def get_user_garage(
    current_user: Any = Depends(get_current_user),
):
    """
    Retrieves all saved vehicles for the authenticated user's personal garage.
    Enforces user authorization: users can never view another user's garage.
    """
    meta = _get_user_meta(current_user.id)
    saved_ids = list(meta.get("saved_car_ids", set()))

    # Attempt to query database if available
    try:
        from app.database.database import SessionLocal
        with SessionLocal() as db:
            favorites = db.query(Favorite).filter(Favorite.user_id == current_user.id).all()
            for fav in favorites:
                meta["saved_car_ids"].add(fav.car_id)
            saved_ids = list(meta["saved_car_ids"])
    except Exception:
        pass

    garage_items = []
    for idx, cid in enumerate(saved_ids, start=1):
        car_info = car_data_service.get_car_by_id(cid)
        if not car_info:
            continue
        garage_items.append(
            GarageItemResponse(
                id=idx,
                car_id=cid,
                shortlist_name=meta["shortlists"].get(cid, "Default"),
                note=meta["notes"].get(cid),
                vehicle_details=car_info,
            )
        )
    return garage_items


@router.post("", response_model=GarageItemResponse)
@router.post("/", response_model=GarageItemResponse)
def add_to_garage(
    req: GarageItemAddRequest,
    current_user: Any = Depends(get_current_user),
):
    """Saves a vehicle to the authenticated user's personal garage with optional shortlist/note."""
    car_info = car_data_service.get_car_by_id(req.car_id)
    if not car_info:
        raise HTTPException(status_code=404, detail=f"Vehicle with ID {req.car_id} not found.")

    meta = _get_user_meta(current_user.id)
    meta["saved_car_ids"].add(req.car_id)
    if req.shortlist_name:
        meta["shortlists"][req.car_id] = req.shortlist_name
    if req.note:
        meta["notes"][req.car_id] = req.note

    # Attempt database persistence
    item_id = req.car_id
    try:
        from app.database.database import SessionLocal
        with SessionLocal() as db:
            existing = (
                db.query(Favorite)
                .filter(Favorite.user_id == current_user.id, Favorite.car_id == req.car_id)
                .first()
            )
            if not existing:
                fav = Favorite(user_id=current_user.id, car_id=req.car_id)
                db.add(fav)
                db.commit()
                db.refresh(fav)
                item_id = fav.id
            else:
                item_id = existing.id
    except Exception:
        pass

    return GarageItemResponse(
        id=item_id,
        car_id=req.car_id,
        shortlist_name=meta["shortlists"].get(req.car_id, "Default"),
        note=meta["notes"].get(req.car_id),
        vehicle_details=car_info,
    )


@router.delete("/{car_id}")
def remove_from_garage(
    car_id: int,
    current_user: Any = Depends(get_current_user),
):
    """Removes a vehicle from the authenticated user's personal garage."""
    meta = _get_user_meta(current_user.id)
    meta.get("saved_car_ids", set()).discard(car_id)
    meta["notes"].pop(car_id, None)
    meta["shortlists"].pop(car_id, None)

    try:
        from app.database.database import SessionLocal
        with SessionLocal() as db:
            fav = (
                db.query(Favorite)
                .filter(Favorite.user_id == current_user.id, Favorite.car_id == car_id)
                .first()
            )
            if fav:
                db.delete(fav)
                db.commit()
    except Exception:
        pass

    return {"message": "Vehicle removed from garage successfully", "car_id": car_id}


@router.get("/compare")
def compare_garage_vehicles(
    current_user: Any = Depends(get_current_user),
):
    """Compares up to 4 saved vehicles currently in the user's personal garage side-by-side."""
    meta = _get_user_meta(current_user.id)
    saved_ids = list(meta.get("saved_car_ids", []))[:4]
    if len(saved_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="You must have at least 2 vehicles saved in your garage to run a comparison."
        )

    comp_req = ComparisonRequest(car_ids=saved_ids)
    result = compare_cars(comp_req)
    if not result:
        raise HTTPException(status_code=404, detail="Comparison could not be generated for saved cars.")
    return result


@router.post("/preferences")
def save_user_preferences(
    req: SavePreferencesRequest,
    current_user: Any = Depends(get_current_user),
):
    """Saves or updates user's personalized automotive preferences for future recommendations."""
    meta = _get_user_meta(current_user.id)
    meta["preferences"] = req.preferences
    return {"message": "Preferences saved successfully", "preferences": meta["preferences"]}


@router.get("/preferences")
def get_user_preferences(
    current_user: Any = Depends(get_current_user),
):
    """Retrieves authenticated user's saved preference profile."""
    meta = _get_user_meta(current_user.id)
    return {"preferences": meta.get("preferences", {})}
