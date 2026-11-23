"""
AutoAI New Launch Alerts Service
Matches user alert criteria (budget, brand, fuel, transmission, body type, classification)
against newly validated CarWale launches. Enforces strict deduplication and dispatches to
Telegram or in-app inbox.
"""

import os
import time
import math
import logging
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("autoai.alerts")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAUNCHES_CSV = os.path.join(BASE_DIR, "ml", "data", "new_launches", "cars_new_launches.csv")

# In-memory alert registries (persisted in session)
_ALERTS_REGISTRY: Dict[str, Dict[str, Any]] = {}
_DELIVERED_NOTIFICATIONS: Dict[str, List[Dict[str, Any]]] = {}  # alert_id -> list of notification records
_SEEN_LAUNCH_KEYS: set = set()  # set of (alert_id, launch_id) tuples to prevent duplicate alerts


class CreateAlertRequest(BaseModel):
    name: Optional[str] = "My Launch Alert"
    budget_max: Optional[float] = Field(None, description="Maximum budget in INR (e.g. 1500000 for ₹15 Lakh)")
    brand: Optional[str] = Field(None, description="Preferred brand")
    fuel_type: Optional[str] = Field(None, description="Preferred fuel type (Petrol, Diesel, Electric, CNG, Hybrid)")
    transmission: Optional[str] = Field(None, description="Preferred transmission (Automatic, Manual)")
    body_type: Optional[str] = Field(None, description="Body type (SUV, Sedan, Hatchback, etc.)")
    launch_classification: Optional[str] = Field(None, description="Filter: NEW_MODEL, FACELIFT, NEW_VARIANT, SPECIAL_EDITION")
    telegram_chat_id: Optional[str] = Field(None, description="Optional Telegram Chat ID for direct Telegram alert delivery")


class AlertResponse(BaseModel):
    alert_id: str
    user_id: int
    name: str
    criteria: Dict[str, Any]
    is_active: bool
    created_at: str
    telegram_chat_id: Optional[str]
    matches_count: int


class AlertService:
    def __init__(self):
        self._counter = 1

    def create_alert(self, user_id: int, req: CreateAlertRequest) -> AlertResponse:
        alert_id = f"alt_{user_id}_{self._counter}_{int(time.time())}"
        self._counter += 1

        criteria = {
            "budget_max": req.budget_max,
            "brand": req.brand.strip() if req.brand else None,
            "fuel_type": req.fuel_type.strip() if req.fuel_type else None,
            "transmission": req.transmission.strip() if req.transmission else None,
            "body_type": req.body_type.strip() if req.body_type else None,
            "launch_classification": req.launch_classification.strip() if req.launch_classification else None,
        }

        # Filter out None criteria
        criteria = {k: v for k, v in criteria.items() if v is not None}

        record = {
            "alert_id": alert_id,
            "user_id": user_id,
            "name": req.name or "My Launch Alert",
            "criteria": criteria,
            "is_active": True,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "telegram_chat_id": req.telegram_chat_id,
        }

        _ALERTS_REGISTRY[alert_id] = record
        _DELIVERED_NOTIFICATIONS[alert_id] = []

        return AlertResponse(
            alert_id=alert_id,
            user_id=user_id,
            name=record["name"],
            criteria=criteria,
            is_active=True,
            created_at=record["created_at"],
            telegram_chat_id=req.telegram_chat_id,
            matches_count=0,
        )

    def get_user_alerts(self, user_id: int) -> List[AlertResponse]:
        results = []
        for aid, a in _ALERTS_REGISTRY.items():
            if a["user_id"] == user_id:
                history = _DELIVERED_NOTIFICATIONS.get(aid, [])
                results.append(
                    AlertResponse(
                        alert_id=aid,
                        user_id=user_id,
                        name=a["name"],
                        criteria=a["criteria"],
                        is_active=a["is_active"],
                        created_at=a["created_at"],
                        telegram_chat_id=a.get("telegram_chat_id"),
                        matches_count=len(history),
                    )
                )
        return results

    def toggle_alert(self, alert_id: str, user_id: int) -> Optional[AlertResponse]:
        alert = _ALERTS_REGISTRY.get(alert_id)
        if not alert or alert["user_id"] != user_id:
            return None
        alert["is_active"] = not alert["is_active"]
        history = _DELIVERED_NOTIFICATIONS.get(alert_id, [])
        return AlertResponse(
            alert_id=alert_id,
            user_id=user_id,
            name=alert["name"],
            criteria=alert["criteria"],
            is_active=alert["is_active"],
            created_at=alert["created_at"],
            telegram_chat_id=alert.get("telegram_chat_id"),
            matches_count=len(history),
        )

    def delete_alert(self, alert_id: str, user_id: int) -> bool:
        alert = _ALERTS_REGISTRY.get(alert_id)
        if not alert or alert["user_id"] != user_id:
            return False
        _ALERTS_REGISTRY.pop(alert_id, None)
        _DELIVERED_NOTIFICATIONS.pop(alert_id, None)
        return True

    def check_and_dispatch_alerts(self, specific_user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Scans existing validated launches against active alerts.
        Ensures strict deduplication: no alert receives the same vehicle twice.
        Dispatches via Telegram if configured or logs into in-app notification center.
        """
        if not os.path.exists(LAUNCHES_CSV):
            return {"status": "skipped", "reason": "No launch records available"}

        try:
            df = pd.read_csv(LAUNCHES_CSV)
        except Exception as e:
            return {"status": "error", "message": str(e)}

        dispatched_count = 0
        new_notifications = []

        active_alerts = [
            a for a in _ALERTS_REGISTRY.values()
            if a["is_active"] and (specific_user_id is None or a["user_id"] == specific_user_id)
        ]

        for alert in active_alerts:
            aid = alert["alert_id"]
            crit = alert["criteria"]
            user_id = alert["user_id"]
            chat_id = alert.get("telegram_chat_id")

            for _, car in df.iterrows():
                cid = car.get("id")
                dedup_key = (aid, cid)
                if dedup_key in _SEEN_LAUNCH_KEYS:
                    continue  # Already notified for this exact launch and alert

                # Filter checks
                price = car.get("price") or car.get("ex_showroom_price")
                if crit.get("budget_max") is not None:
                    if pd.isna(price) or float(price) > float(crit["budget_max"]):
                        continue

                if crit.get("brand"):
                    c_brand = str(car.get("brand", "")).lower()
                    if crit["brand"].lower() not in c_brand:
                        continue

                if crit.get("fuel_type"):
                    c_fuel = str(car.get("fuel_type", "") or car.get("fuel", "")).lower()
                    if crit["fuel_type"].lower() not in c_fuel:
                        continue

                if crit.get("transmission"):
                    c_trans = str(car.get("transmission", "")).lower()
                    if crit["transmission"].lower() not in c_trans:
                        continue

                if crit.get("body_type"):
                    c_body = str(car.get("body_type", "")).lower()
                    if crit["body_type"].lower() not in c_body:
                        continue

                if crit.get("launch_classification"):
                    c_class = str(car.get("record_type", "") or car.get("launch_classification", "")).upper()
                    if crit["launch_classification"].upper() != c_class:
                        continue

                # Matched! Record notification
                _SEEN_LAUNCH_KEYS.add(dedup_key)
                notif = {
                    "alert_id": aid,
                    "alert_name": alert["name"],
                    "car_id": cid,
                    "car_name": f"{car.get('brand')} {car.get('model')} {car.get('variant', '')}".strip(),
                    "price": float(price) if not pd.isna(price) else None,
                    "launch_classification": car.get("record_type"),
                    "launch_date": car.get("launch_date"),
                    "source_url": car.get("source_url"),
                    "dispatched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }

                _DELIVERED_NOTIFICATIONS.setdefault(aid, []).append(notif)
                new_notifications.append(notif)
                dispatched_count += 1

                # If Telegram token & chat_id provided, attempt direct Telegram send
                if chat_id:
                    self._send_telegram_notification(chat_id, notif)

        return {
            "status": "completed",
            "active_alerts_checked": len(active_alerts),
            "new_notifications_sent": dispatched_count,
            "notifications": new_notifications,
        }

    def _send_telegram_notification(self, chat_id: str, notif: Dict[str, Any]):
        """Dispatches an alert message to Telegram Bot API if configured."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token or token == "your-telegram-bot-token-here":
            return  # Telegram not configured in env, skip external call

        import urllib.request
        import urllib.parse
        import json

        price_str = f"₹{notif['price']:,.0f}" if notif.get("price") else "Price to be announced"
        msg = (
            f"🔔 *AutoAI New Launch Alert: {notif['alert_name']}*\n\n"
            f"🚗 *{notif['car_name']}*\n"
            f"🏷 Type: `{notif.get('launch_classification', 'NEW_MODEL')}`\n"
            f"💰 Ex-Showroom: {price_str}\n"
            f"📅 Date: {notif.get('launch_date', 'Recently Launched')}\n"
            f"🔗 [CarWale Details]({notif.get('source_url', 'https://www.carwale.com')})"
        )

        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "Markdown",
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=5) as resp:
                pass
        except Exception as e:
            logger.warning("Telegram alert dispatch to chat %s failed: %s", chat_id, e)

    def get_user_notifications(self, user_id: int) -> List[Dict[str, Any]]:
        notifs = []
        for aid, a in _ALERTS_REGISTRY.items():
            if a["user_id"] == user_id:
                notifs.extend(_DELIVERED_NOTIFICATIONS.get(aid, []))
        notifs.sort(key=lambda x: x["dispatched_at"], reverse=True)
        return notifs


alert_service = AlertService()
