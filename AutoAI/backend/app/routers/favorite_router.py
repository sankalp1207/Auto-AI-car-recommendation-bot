from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.favorite import Favorite
from app.models.car import Car

router = APIRouter(
    prefix="/favorites",
    tags=["Favorites"]
)


@router.post("/")
def add_favorite(user_id: int, car_id: int, db: Session = Depends(get_db)):

    fav = Favorite(
        user_id=user_id,
        car_id=car_id
    )

    db.add(fav)
    db.commit()

    return {"message": "Added to favorites"}


@router.get("/{user_id}")
def get_favorites(user_id: int, db: Session = Depends(get_db)):

    favorites = (
        db.query(Car)
        .join(Favorite, Favorite.car_id == Car.id)
        .filter(Favorite.user_id == user_id)
        .all()
    )

    return favorites


@router.delete("/")
def delete_favorite(user_id: int, car_id: int, db: Session = Depends(get_db)):

    fav = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == user_id,
            Favorite.car_id == car_id
        )
        .first()
    )

    if fav:
        db.delete(fav)
        db.commit()

    return {"message": "Removed"}