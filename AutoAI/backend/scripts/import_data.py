import sys
import re
from pathlib import Path
import pandas as pd
from sqlalchemy import text

# Add backend directory to python path if executing directly
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database.database import SessionLocal, Base, engine
from app.models.car import Car


def ensure_table_schema():
    with engine.connect() as conn:
        # Add new columns if missing
        conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS cylinders INTEGER;"))
        conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS fuel_tank_capacity FLOAT;"))
        conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS height INTEGER;"))
        conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS length INTEGER;"))
        conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS width INTEGER;"))
        conn.commit()


# Create tables if they don't exist
Base.metadata.create_all(bind=engine)
try:
    ensure_table_schema()
except Exception as e:
    print(f"Note on schema update: {e}")


def parse_price(val, default=0.0):
    if pd.isna(val) or val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).replace("₹", "").replace(",", "").strip()
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return default


def parse_float(val, default=0.0):
    if pd.isna(val) or val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_int(val, default=0):
    if pd.isna(val) or val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def parse_bool(val, default=True):
    if pd.isna(val) or val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ["true", "1", "t", "yes", "y"]
    return default


def get_column_value(row, candidate_keys, default=None):
    for key in candidate_keys:
        if key in row and not pd.isna(row[key]):
            val = str(row[key]).strip()
            if val != "":
                return row[key]
    return default


def import_cars_dataset(csv_path=None):
    if csv_path is None:
        primary_csv = BASE_DIR / "data" / "cars.csv"
        secondary_csv = BASE_DIR / "data" / "shrey_car_dataset.csv"
        if primary_csv.exists():
            csv_file = primary_csv
        elif secondary_csv.exists():
            csv_file = secondary_csv
        else:
            raise FileNotFoundError(f"Neither {primary_csv} nor {secondary_csv} exists.")
    else:
        csv_file = Path(csv_path)

    print(f"Reading CSV from: {csv_file}")
    df = pd.read_csv(csv_file)

    db = SessionLocal()

    try:
        print("Clearing existing car records...")
        db.query(Car).delete()
        db.commit()

        cars_to_add = []
        for index, row in df.iterrows():
            brand = str(get_column_value(row, ["Make", "brand", "Make_Name"], "Unknown")).strip()
            model = str(get_column_value(row, ["Model", "model"], "Unknown")).strip()
            variant = str(get_column_value(row, ["Variant", "variant"], "Standard")).strip()

            price_raw = get_column_value(row, ["Ex-Showroom_Price", "ex_showroom_price", "price_inr", "price"], 0)
            price = parse_price(price_raw)

            body_type = str(get_column_value(row, ["Body_Type", "body_type"], "Hatchback")).strip()
            fuel_type = str(get_column_value(row, ["Fuel_Type", "fuel_type"], "Petrol")).strip()
            transmission = str(get_column_value(row, ["Type", "transmission"], "Manual")).strip()

            engine_cc = parse_int(get_column_value(row, ["Displacement", "engine_cc"], 0))
            cylinders = parse_int(get_column_value(row, ["Cylinders", "cylinders"], None), default=None)
            fuel_tank_capacity = parse_float(get_column_value(row, ["Fuel_Tank_Capacity", "fuel_tank_capacity"], None), default=None)

            height = parse_int(get_column_value(row, ["Height", "height"], None), default=None)
            length = parse_int(get_column_value(row, ["Length", "length"], None), default=None)
            width = parse_int(get_column_value(row, ["Width", "width"], None), default=None)

            power = parse_int(get_column_value(row, ["Power.1", "power", "Power", "horsepower"], 100))
            torque = parse_int(get_column_value(row, ["Torque.1", "torque", "Torque"], 150))

            seating = parse_int(get_column_value(row, ["Seating_Capacity", "seating", "seats"], 5))

            # Derived / Default fields
            mileage_raw = get_column_value(row, ["mileage", "mileage_or_range"], None)
            if mileage_raw is not None:
                mileage = parse_float(mileage_raw)
            else:
                fuel_lower = fuel_type.lower()
                if "electric" in fuel_lower or "ev" in fuel_lower:
                    mileage = 400.0
                elif "cng" in fuel_lower:
                    mileage = 26.0
                elif "diesel" in fuel_lower:
                    mileage = 20.0
                elif "hybrid" in fuel_lower:
                    mileage = 23.0
                else:
                    mileage = 17.5

            boot_space_raw = get_column_value(row, ["boot_space"], None)
            if boot_space_raw is not None:
                boot_space = parse_int(boot_space_raw)
            else:
                body_lower = body_type.lower()
                if "sedan" in body_lower:
                    boot_space = 480
                elif "suv" in body_lower or "muv" in body_lower or "mpv" in body_lower:
                    boot_space = 420
                else:
                    boot_space = 300

            gc_raw = get_column_value(row, ["ground_clearance"], None)
            if gc_raw is not None:
                ground_clearance = parse_int(gc_raw)
            else:
                body_lower = body_type.lower()
                if "suv" in body_lower or "crossover" in body_lower:
                    ground_clearance = 200
                else:
                    ground_clearance = 165

            safety_rating = parse_float(get_column_value(row, ["safety_rating"], 4.0))
            maint_raw = get_column_value(row, ["maintenance_cost"], None)
            if maint_raw is not None:
                maintenance_cost = parse_int(maint_raw)
            else:
                maintenance_cost = max(6000, min(35000, int(price * 0.015)))

            resale_rating = parse_float(get_column_value(row, ["resale_rating"], 4.2))

            city_use = parse_bool(get_column_value(row, ["city_use"], True))
            highway_use = parse_bool(get_column_value(row, ["highway_use"], True))
            family_friendly = parse_bool(get_column_value(row, ["family_friendly"], True))

            pros = get_column_value(row, ["pros"], f"Comfortable {body_type}, efficient {fuel_type} engine, reliable performance.")
            cons = get_column_value(row, ["cons"], "Standard feature set.")
            image_url = get_column_value(row, ["image_url"], f"https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80")

            car = Car(
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
            cars_to_add.append(car)

        db.bulk_save_objects(cars_to_add)
        db.commit()
        print(f"Successfully imported {len(cars_to_add)} cars into database!")
    except Exception as e:
        db.rollback()
        print(f"Error during import: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    import_cars_dataset(path_arg)