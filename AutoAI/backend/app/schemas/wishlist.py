from pydantic import BaseModel


class WishlistRequest(BaseModel):
    car_id: int