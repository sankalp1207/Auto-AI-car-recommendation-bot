from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.car import Car
from app.models.wishlist import Wishlist
from app.models.user import User

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db)):

    total_cars = db.query(Car).count()
    total_users = db.query(User).count()
    total_wishlist = db.query(Wishlist).count()

    return {
        "cars": total_cars,
        "total_cars": total_cars,
        "users": total_users,
        "active_users": total_users,
        "wishlist": total_wishlist,
        "wishlisted_cars": total_wishlist,
        "ai_chats": 0
    }