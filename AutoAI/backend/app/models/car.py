from sqlalchemy import Column, Integer, String, Float, Boolean
from app.database.database import Base

class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)

    brand = Column(String(50), nullable=False)

    model = Column(String(100), nullable=False)

    variant = Column(String(100), nullable=False)

    ex_showroom_price = Column(Float, nullable=False)

    body_type = Column(String(30))
    fuel_type = Column(String(30))
    transmission = Column(String(30))

    engine_cc = Column(Integer)
    cylinders = Column(Integer, nullable=True)
    fuel_tank_capacity = Column(Float, nullable=True)
    height = Column(Integer, nullable=True)
    length = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    power = Column(Integer)
    torque = Column(Integer)

    mileage = Column(Float)

    seating = Column(Integer)

    boot_space = Column(Integer)

    ground_clearance = Column(Integer)

    safety_rating = Column(Float)

    maintenance_cost = Column(Integer)

    resale_rating = Column(Float)

    city_use = Column(Boolean)

    highway_use = Column(Boolean)

    family_friendly = Column(Boolean)

    pros = Column(String)

    cons = Column(String)

    image_url = Column(String)

    year = Column(Integer, nullable=True)
    sunroof = Column(Boolean, default=False)
    adas = Column(Boolean, default=False)
    touchscreen_inches = Column(Float, nullable=True)
    carplay_androidauto = Column(Boolean, default=False)
    ideal_for = Column(String, nullable=True)
    summary_embedding_text = Column(String, nullable=True)