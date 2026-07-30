from sqlalchemy import Column, Integer, ForeignKey

from app.database.database import Base


class Wishlist(Base):
    __tablename__ = "wishlist"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))

    car_id = Column(Integer, ForeignKey("cars.id"))