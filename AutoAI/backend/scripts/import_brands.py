import sys
from pathlib import Path
import pandas as pd

# Add backend directory to python path
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database.database import SessionLocal, Base, engine
from app.models.brand import Brand
from app.models.car import Car

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    # 1. Read existing brands.csv if present
    brands_csv = BASE_DIR / "data" / "brands.csv"
    existing_brands = {}
    if brands_csv.exists():
        df_b = pd.read_csv(brands_csv)
        for _, row in df_b.iterrows():
            name = str(row["name"]).strip()
            country = str(row.get("country", "Unknown")).strip()
            existing_brands[name.lower()] = (name, country)

    # 2. Extract brands from cars dataset
    cars_csv = BASE_DIR / "data" / "cars.csv"
    if not cars_csv.exists():
        cars_csv = BASE_DIR / "data" / "shrey_car_dataset.csv"

    if cars_csv.exists():
        df_c = pd.read_csv(cars_csv)
        brand_col = "brand" if "brand" in df_c.columns else ("Make" if "Make" in df_c.columns else None)
        if brand_col:
            unique_makes = df_c[brand_col].dropna().unique()
            for make in unique_makes:
                m_str = str(make).strip()
                if m_str and m_str.lower() not in existing_brands:
                    existing_brands[m_str.lower()] = (m_str, "International")

    # 3. Save brands to DB
    inserted = 0
    for key, (b_name, b_country) in existing_brands.items():
        exists = db.query(Brand).filter(Brand.name.ilike(b_name)).first()
        if not exists:
            db.add(Brand(name=b_name, country=b_country))
            inserted += 1

    db.commit()
    print(f"Brands imported successfully! ({inserted} new brand(s) added).")
finally:
    db.close()