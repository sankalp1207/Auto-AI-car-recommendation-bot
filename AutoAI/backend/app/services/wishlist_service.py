from sqlalchemy.orm import Session

from app.models.wishlist import Wishlist
from app.models.car import Car


def add_to_wishlist(request, db: Session):

    existing = (
        db.query(Wishlist)
        .filter(Wishlist.car_id == request.car_id)
        .first()
    )

    if existing:
        return {
            "message": "Already in wishlist"
        }

    item = Wishlist(
        car_id=request.car_id
    )

    db.add(item)
    db.commit()

    return {
        "message": "Added Successfully"
    }


def get_wishlist(db: Session):

    wishlist = db.query(Wishlist).all()

    result = []

    for item in wishlist:

        car = (
            db.query(Car)
            .filter(Car.id == item.car_id)
            .first()
        )

        if car:
            result.append({
                "id": item.id,
                "car_id": car.id,
                "brand": car.brand,
                "model": car.model,
                "variant": car.variant,
                "price": car.ex_showroom_price,
                "image": car.image_url,
            })

    return result


def remove_from_wishlist(id: int, db: Session):

    item = (
        db.query(Wishlist)
        .filter(Wishlist.id == id)
        .first()
    )

    if not item:
        return {
            "message": "Not Found"
        }

    db.delete(item)
    db.commit()

    return {
        "message": "Removed Successfully"
    }