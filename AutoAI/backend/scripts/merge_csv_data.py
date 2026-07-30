import sys
import csv
from pathlib import Path

# Add backend directory to python path
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database.database import SessionLocal, Base, engine
from app.models.car import Car


def parse_bool(val, default=True):
    if val is None or val == "":
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ["true", "1", "t", "yes", "y"]
    return default


def parse_float(val, default=0.0):
    if val is None or val == "":
        return default
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).replace("₹", "").replace(",", "").strip()
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return default


def parse_int(val, default=0):
    if val is None or val == "":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def get_column_value(row, keys, default=""):
    for k in keys:
        if k in row and row[k] is not None and str(row[k]).strip() != "":
            return str(row[k]).strip()
    return default


def merge_csv(csv_path):
    path = Path(csv_path)
    if not path.is_absolute():
        path = BASE_DIR / path

    if not path.exists():
        print(f"[ERROR] CSV file not found: {path}")
        return

    print(f"[CSV] Merging CSV data from: {path}")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    inserted_count = 0
    updated_count = 0

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                brand = get_column_value(row, ["brand", "Make", "Make_Name"], "").strip()
                model = get_column_value(row, ["model", "Model"], "").strip()
                variant = get_column_value(row, ["variant", "Variant"], "Standard").strip()

                if not brand or not model:
                    continue

                existing = db.query(Car).filter(
                    Car.brand.ilike(brand),
                    Car.model.ilike(model),
                    Car.variant.ilike(variant)
                ).first()

                price_str = get_column_value(row, ["ex_showroom_price", "Ex-Showroom_Price", "price_inr", "price"], "0")
                price = parse_float(price_str)

                body_type = get_column_value(row, ["body_type", "Body_Type"], "Hatchback")
                fuel_type = get_column_value(row, ["fuel_type", "Fuel_Type"], "Petrol")
                transmission = get_column_value(row, ["transmission", "Type"], "Manual")

                engine_cc = parse_int(get_column_value(row, ["engine_cc", "Displacement"], "0"))
                cylinders = parse_int(get_column_value(row, ["cylinders", "Cylinders"], ""), default=None)
                fuel_tank_capacity = parse_float(get_column_value(row, ["fuel_tank_capacity", "Fuel_Tank_Capacity"], ""), default=None)

                height = parse_int(get_column_value(row, ["height", "Height"], ""), default=None)
                length = parse_int(get_column_value(row, ["length", "Length"], ""), default=None)
                width = parse_int(get_column_value(row, ["width", "Width"], ""), default=None)

                power = parse_int(get_column_value(row, ["power", "Power.1", "Power", "horsepower"], "100"))
                torque = parse_int(get_column_value(row, ["torque", "Torque.1", "Torque"], "150"))

                mileage_val = get_column_value(row, ["mileage", "mileage_or_range"], "")
                if mileage_val:
                    mileage = parse_float(mileage_val)
                else:
                    fuel_lower = fuel_type.lower()
                    if "electric" in fuel_lower or "ev" in fuel_lower:
                        mileage = 400.0
                    elif "cng" in fuel_lower:
                        mileage = 26.0
                    elif "diesel" in fuel_lower:
                        mileage = 20.0
                    else:
                        mileage = 17.5

                seating = parse_int(get_column_value(row, ["seating", "Seating_Capacity", "seats"], "5"))

                boot_val = get_column_value(row, ["boot_space"], "")
                boot_space = parse_int(boot_val) if boot_val else (480 if "sedan" in body_type.lower() else 350)

                gc_val = get_column_value(row, ["ground_clearance"], "")
                ground_clearance = parse_int(gc_val) if gc_val else (200 if "suv" in body_type.lower() else 165)

                safety_rating = parse_float(get_column_value(row, ["safety_rating"], "4.0"))
                maint_val = get_column_value(row, ["maintenance_cost"], "")
                maintenance_cost = parse_int(maint_val) if maint_val else max(6000, int(price * 0.015))

                resale_rating = parse_float(get_column_value(row, ["resale_rating"], "4.2"))
                city_use = parse_bool(get_column_value(row, ["city_use"], True))
                highway_use = parse_bool(get_column_value(row, ["highway_use"], True))
                family_friendly = parse_bool(get_column_value(row, ["family_friendly"], True))

                pros = get_column_value(row, ["pros"], f"Comfortable {body_type}, efficient performance.")
                cons = get_column_value(row, ["cons"], "Standard maintenance required.")
                image_url = get_column_value(row, ["image_url"], f"https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80")

                if existing:
                    existing.brand = brand
                    existing.model = model
                    existing.variant = variant
                    existing.ex_showroom_price = price
                    existing.body_type = body_type
                    existing.fuel_type = fuel_type
                    existing.transmission = transmission
                    existing.engine_cc = engine_cc
                    existing.cylinders = cylinders
                    existing.fuel_tank_capacity = fuel_tank_capacity
                    existing.height = height
                    existing.length = length
                    existing.width = width
                    existing.power = power
                    existing.torque = torque
                    existing.mileage = mileage
                    existing.seating = seating
                    existing.boot_space = boot_space
                    existing.ground_clearance = ground_clearance
                    existing.safety_rating = safety_rating
                    existing.maintenance_cost = maintenance_cost
                    existing.resale_rating = resale_rating
                    existing.city_use = city_use
                    existing.highway_use = highway_use
                    existing.family_friendly = family_friendly
                    existing.pros = pros
                    existing.cons = cons
                    if image_url and not existing.image_url:
                        existing.image_url = image_url
                    updated_count += 1
                else:
                    new_car = Car(
                        brand=brand,
                        model=model,
                        variant=variant,
                        ex_showroom_price=price,
                        body_type=body_type,
                        fuel_type=fuel_type,
                        transmission=transmission,
                        engine_cc=engine_cc,
                        cylinders=cylinders,
                        fuel_tank_capacity=fuel_tank_capacity,
                        height=height,
                        length=length,
                        width=width,
                        power=power,
                        torque=torque,
                        mileage=mileage,
                        seating=seating,
                        boot_space=boot_space,
                        ground_clearance=ground_clearance,
                        safety_rating=safety_rating,
                        maintenance_cost=maintenance_cost,
                        resale_rating=resale_rating,
                        city_use=city_use,
                        highway_use=highway_use,
                        family_friendly=family_friendly,
                        pros=pros,
                        cons=cons,
                        image_url=image_url,
                    )
                    db.add(new_car)
                    inserted_count += 1

        db.commit()
        print(f"\n[OK] Merge complete! Inserted: {inserted_count} new car(s), Updated: {updated_count} car(s).")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error merging CSV: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "data/cars.csv"
    merge_csv(csv_file)
