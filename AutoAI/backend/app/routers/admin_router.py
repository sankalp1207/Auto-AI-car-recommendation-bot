from io import StringIO
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.admin_schema import CarCreate, CarUpdate, VariantUpdate, BulkVariantUpdate
from app.services.admin_service import (
    get_all_cars,
    add_car,
    update_car,
    delete_car,
    search_cars,
    update_car_variant,
    bulk_update_variants,
    get_variants_summary,
)
from scripts.merge_csv_data import merge_csv


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.get("/cars")
def all_cars(db: Session = Depends(get_db)):
    return get_all_cars(db)


@router.get("/cars/search")
def search_cars_endpoint(
    query: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    variant: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return search_cars(db, query=query, brand=brand, model=model, variant=variant)


@router.get("/cars/variants-summary")
def variants_summary_endpoint(db: Session = Depends(get_db)):
    return get_variants_summary(db)


@router.post("/cars")
def create_car(
    car: CarCreate,
    db: Session = Depends(get_db),
):
    return add_car(db, car)


@router.put("/cars/{car_id}")
def edit_car(
    car_id: int,
    car: CarUpdate,
    db: Session = Depends(get_db),
):
    updated = update_car(db, car_id, car)

    if not updated:
        raise HTTPException(404, "Car not found")

    return updated


@router.patch("/cars/{car_id}/variant")
def edit_car_variant(
    car_id: int,
    data: VariantUpdate,
    db: Session = Depends(get_db),
):
    updated = update_car_variant(db, car_id, data.variant)

    if not updated:
        raise HTTPException(404, "Car not found")

    return updated


@router.post("/cars/bulk-update-variants")
def bulk_update_car_variants(
    data: BulkVariantUpdate,
    db: Session = Depends(get_db),
):
    count = bulk_update_variants(
        db,
        brand=data.brand,
        model=data.model,
        old_variant=data.old_variant,
        new_variant=data.new_variant,
    )
    return {
        "message": f"Successfully updated {count} car variant(s)",
        "updated_count": count,
        "brand": data.brand,
        "model": data.model,
        "old_variant": data.old_variant,
        "new_variant": data.new_variant,
    }


@router.post("/cars/import-csv")
async def import_csv_file(
    file: UploadFile = File(...),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are allowed")

    # Save temporary file inside data directory and merge
    save_path = f"data/temp_{file.filename}"
    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    try:
        merge_csv(save_path)
        return {"message": f"Successfully merged CSV '{file.filename}' into database"}
    finally:
        import os
        if os.path.exists(save_path):
            os.remove(save_path)


@router.delete("/cars/{car_id}")
def remove_car(
    car_id: int,
    db: Session = Depends(get_db),
):
    deleted = delete_car(db, car_id)

    if not deleted:
        raise HTTPException(404, "Car not found")

    return {"message": "Car deleted successfully"}


    