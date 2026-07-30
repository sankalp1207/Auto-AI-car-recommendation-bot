from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db

from app.schemas.wishlist import WishlistRequest

from app.services.wishlist_service import (
    add_to_wishlist,
    get_wishlist,
    remove_from_wishlist,
)

router = APIRouter(
    prefix="/wishlist",
    tags=["Wishlist"]
)


@router.get("/")
def wishlist(
    db: Session = Depends(get_db),
):
    return get_wishlist(db)


@router.post("/")
def add(
    request: WishlistRequest,
    db: Session = Depends(get_db),
):
    return add_to_wishlist(request, db)


@router.delete("/{id}")
def remove(
    id: int,
    db: Session = Depends(get_db),
):
    return remove_from_wishlist(id, db)