from sqlalchemy.orm import Session
from app.models.car import Car


def search_cars(
    db: Session,
    brand=None,
    fuel=None,
    transmission=None,
    body_type=None,
    budget=None,
):

    query = db.query(Car)

    if brand:
        query = query.filter(Car.brand.ilike(f"%{brand}%"))

    if fuel:
        query = query.filter(Car.fuel_type == fuel)

    if transmission:
        query = query.filter(Car.transmission == transmission)

    if body_type:
        query = query.filter(Car.body_type == body_type)

    if budget:
        query = query.filter(Car.ex_showroom_price <= budget)

    return query.all()