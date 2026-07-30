from sqlalchemy.orm import Session
from app.models.car import Car


def get_all_cars(db: Session):
    return db.query(Car).all()


def add_car(db: Session, car_data):
    car = Car(**car_data.dict())
    db.add(car)
    db.commit()
    db.refresh(car)
    return car


def update_car(db: Session, car_id: int, car_data):
    car = db.query(Car).filter(Car.id == car_id).first()

    if not car:
        return None

    for key, value in car_data.dict().items():
        setattr(car, key, value)

    db.commit()
    db.refresh(car)

    return car


def delete_car(db: Session, car_id: int):
    car = db.query(Car).filter(Car.id == car_id).first()

    if not car:
        return False

    db.delete(car)
    db.commit()

    return True


def search_cars(db: Session, query: str = None, brand: str = None, model: str = None, variant: str = None):
    q = db.query(Car)

    if query:
        pattern = f"%{query}%"
        q = q.filter(
            (Car.brand.ilike(pattern)) |
            (Car.model.ilike(pattern)) |
            (Car.variant.ilike(pattern))
        )

    if brand:
        q = q.filter(Car.brand.ilike(f"%{brand}%"))
    if model:
        q = q.filter(Car.model.ilike(f"%{model}%"))
    if variant:
        q = q.filter(Car.variant.ilike(f"%{variant}%"))

    return q.all()


def update_car_variant(db: Session, car_id: int, new_variant: str):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        return None

    car.variant = new_variant
    db.commit()
    db.refresh(car)
    return car


def bulk_update_variants(db: Session, brand: str, model: str, old_variant: str, new_variant: str):
    cars = db.query(Car).filter(
        Car.brand.ilike(brand),
        Car.model.ilike(model),
        Car.variant.ilike(old_variant)
    ).all()

    updated_count = len(cars)
    for car in cars:
        car.variant = new_variant

    db.commit()
    return updated_count


def get_variants_summary(db: Session):
    cars = db.query(Car.brand, Car.model, Car.variant).all()
    summary = {}

    for brand, model, variant in cars:
        if brand not in summary:
            summary[brand] = {}
        if model not in summary[brand]:
            summary[brand][model] = {}
        summary[brand][model][variant] = summary[brand][model].get(variant, 0) + 1

    return summary