from pathlib import Path
import pandas as pd

from app.database.database import SessionLocal
from app.models.car import Car

BASE_DIR = Path(__file__).resolve().parents[1]
EXCEL_FILE = BASE_DIR / "data" / "AutoAI_1000_Cars_Dataset.xlsx"

print("Reading:", EXCEL_FILE)

df = pd.read_excel(EXCEL_FILE)

db = SessionLocal()

# Optional: remove existing cars first
# db.query(Car).delete()
# db.commit()

for _, row in df.iterrows():

    fuel = row.get("fuel_type", "Petrol")
    body = row.get("body_type", "SUV")

    car = Car(
        brand=str(row.get("brand", "")),
        model=str(row.get("model", "")),
        variant=str(row.get("variant", "")),

        ex_showroom_price=float(row.get("price_inr", 0)),

        body_type=body,
        fuel_type=fuel,
        transmission=str(row.get("transmission", "Manual")),

        engine_cc=int(row.get("engine_cc", 0)),
        power=int(row.get("horsepower", 100)),

        torque=250,

        mileage=float(row.get("mileage_or_range", 0)),

        seating=int(row.get("seats", 5)),

        boot_space=400,

        ground_clearance=190,

        safety_rating=float(row.get("safety_rating", 4)),

        maintenance_cost=8000,

        resale_rating=4.2,

        city_use=True,

        highway_use=True,

        family_friendly=True,

        pros="Good performance, Comfortable, Reliable",

        cons="Average boot space",

        image_url=str(row.get("image_url", "")),
    )

    db.add(car)

db.commit()

print(f"Imported {len(df)} cars successfully.")

db.close()