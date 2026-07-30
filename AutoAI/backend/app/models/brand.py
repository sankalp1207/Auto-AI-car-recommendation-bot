from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, foreign

from app.database.database import Base


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), unique=True, nullable=False)

    country = Column(String(100))

    logo = Column(String(500))

    cars = relationship("Car", primaryjoin="Brand.name == foreign(Car.brand)")