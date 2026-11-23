"""
AutoAI Launch Alerts Router
Endpoints for creating, managing, toggling, and checking automotive launch alerts.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.auth.jwt_handler import get_current_user
from app.services.alert_service import (
    alert_service,
    CreateAlertRequest,
    AlertResponse,
)

router = APIRouter(
    prefix="/alerts",
    tags=["Launch Alerts"],
)


@router.post("", response_model=AlertResponse)
@router.post("/", response_model=AlertResponse)
def create_alert(
    req: CreateAlertRequest,
    current_user: User = Depends(get_current_user),
):
    """Creates a new vehicle launch alert subscription for the current authenticated user."""
    return alert_service.create_alert(current_user.id, req)


@router.get("", response_model=List[AlertResponse])
@router.get("/", response_model=List[AlertResponse])
def get_alerts(
    current_user: User = Depends(get_current_user),
):
    """Retrieves all launch alerts created by the current user."""
    return alert_service.get_user_alerts(current_user.id)


@router.patch("/{alert_id}/toggle", response_model=AlertResponse)
def toggle_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
):
    """Enables or disables an existing launch alert."""
    result = alert_service.toggle_alert(alert_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found or unauthorized.")
    return result


@router.delete("/{alert_id}")
def delete_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
):
    """Deletes an existing launch alert."""
    success = alert_service.delete_alert(alert_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found or unauthorized.")
    return {"message": "Alert deleted successfully", "alert_id": alert_id}


@router.post("/check")
def check_launch_alerts(
    current_user: User = Depends(get_current_user),
):
    """
    Triggers deterministic alert matching against newly validated launch records.
    Deduplicates strictly to prevent duplicate notifications.
    """
    return alert_service.check_and_dispatch_alerts(specific_user_id=current_user.id)


@router.get("/notifications")
def get_alert_notifications(
    current_user: User = Depends(get_current_user),
):
    """Returns the delivery history of notifications dispatched to the current user."""
    return alert_service.get_user_notifications(current_user.id)
