import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.database import SessionLocal, Base, engine
from app.models.car import Car

BASE_DIR = Path(__file__).resolve().parents[2]
CSV_CURRENT_PATH = BASE_DIR / "data" / "cars_current.csv"
CSV_UPCOMING_PATH = BASE_DIR / "data" / "cars_upcoming.csv"


def _parse_numeric(value, cast=int, default=0):
    """Extract leading number from strings like '116 bhp' or '141 Nm'."""
    if pd.isna(value):
        return default
    if isinstance(value, (int, float)):
        return cast(value)
    m = re.match(r'([\d.]+)', str(value).strip())
    if m:
        return cast(float(m.group(1)))
    return default


class CarDataService:
    def __init__(self):
        self._cars_cache: List[Dict[str, Any]] = []

    def _car_to_dict(self, c: Any) -> Dict[str, Any]:
        """Convert a Car SQLAlchemy model or dictionary into standardized cache dictionary."""
        if isinstance(c, dict):
            return c
        safety = getattr(c, "safety_rating", None) or 0.0
        touchscreen_val = getattr(c, "touchscreen_inches", None)
        has_touchscreen = "Yes" if (touchscreen_val and touchscreen_val > 0) else "No"
        carplay = bool(getattr(c, "carplay_androidauto", False))
        price = getattr(c, "ex_showroom_price", None) or 0.0

        return {
            "id": getattr(c, "id", 0),
            "brand": getattr(c, "brand", "Unknown"),
            "model": getattr(c, "model", "Unknown"),
            "variant": getattr(c, "variant", "") or "",
            "year": getattr(c, "year", None) or 2024,
            "ex_showroom_price": price,
            "price": price,
            "body_type": getattr(c, "body_type", None) or "Unknown",
            "fuel_type": getattr(c, "fuel_type", None) or "Unknown",
            "fuel": getattr(c, "fuel_type", None) or "Unknown",
            "transmission": getattr(c, "transmission", None) or "Unknown",
            "engine_cc": getattr(c, "engine_cc", None) or 0,
            "engine": getattr(c, "engine_cc", None) or 0,
            "power": getattr(c, "power", None) or 0,
            "torque": getattr(c, "torque", None) or 0,
            "mileage": getattr(c, "mileage", None) or 0.0,
            "seating": getattr(c, "seating", None) or 5,
            "seating_capacity": getattr(c, "seating", None) or 5,
            "boot_space": getattr(c, "boot_space", None) or 0,
            "ground_clearance": getattr(c, "ground_clearance", None) or 0,
            "safety_rating": safety,
            "sunroof": bool(getattr(c, "sunroof", False)),
            "adas": bool(getattr(c, "adas", False)),
            "touchscreen_inches": touchscreen_val or 0.0,
            "touchscreen": has_touchscreen,
            "carplay_androidauto": carplay,
            "wireless_android_auto": "Yes" if carplay else "No",
            "wireless_apple_carplay": "Yes" if carplay else "No",
            "airbags": "6 airbags" if safety >= 4 else "2 airbags",
            "ideal_for": getattr(c, "ideal_for", "") or "",
            "summary": getattr(c, "summary", "") or "",
            "summary_embedding_text": getattr(c, "summary_embedding_text", "") or "",
            "status": getattr(c, "status", None) or "CURRENT",
            "maintenance_cost": getattr(c, "maintenance_cost", None) or 0,
            "resale_rating": getattr(c, "resale_rating", None) or 0.0,
            "city_use": bool(getattr(c, "city_use", False)),
            "highway_use": bool(getattr(c, "highway_use", False)),
            "family_friendly": bool(getattr(c, "family_friendly", False)),
            "pros": getattr(c, "pros", "") or "",
            "cons": getattr(c, "cons", "") or "",
            "pros_list": [],
            "cons_list": [],
            "image_url": getattr(c, "image_url", None) or "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80",
            "image": getattr(c, "image_url", None) or "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80",
            "source": "carwale.com",
            "model_url": "",
            "variant_url": "",
        }

    def load_dataset(self) -> List[Dict[str, Any]]:
        """Loads current + upcoming CSVs, caching in memory and seeding the DB."""
        frames = []
        for csv_path, label in [(CSV_CURRENT_PATH, "CURRENT"), (CSV_UPCOMING_PATH, "UPCOMING")]:
            if not csv_path.exists():
                print(f"[CarDataService] WARNING: {label} CSV not found at {csv_path}")
                continue
            part = pd.read_csv(csv_path)
            print(f"[CarDataService] Loaded {len(part)} rows from {csv_path.name} ({label})")
            frames.append(part)

        if not frames:
            print(f"[CarDataService] ERROR: No dataset CSVs found")
            return []

        df = pd.concat(frames, ignore_index=True)
        csv_row_count = len(df)
        print(f"[CarDataService] Total CSV rows to import: {csv_row_count}")
        self._cars_cache = []

        db = SessionLocal()
        try:
            # Ensure schema matches what's configured
            self._ensure_table_schema()

            existing_count = db.query(Car).count()
            # Fast path: if the database is already fully populated, load cache directly from database
            if existing_count >= csv_row_count and csv_row_count > 0:
                print(f"[AutoAI] DATABASE CACHE LOADING: {existing_count} records detected in database. Loading in-memory cache...")
                cars = db.query(Car).order_by(Car.id).all()
                self._cars_cache = [self._car_to_dict(c) for c in cars]
                current_count = sum(1 for c in self._cars_cache if c.get('status') == 'CURRENT')
                upcoming_count = sum(1 for c in self._cars_cache if c.get('status') == 'UPCOMING')
                print(f"[AutoAI] DATABASE CACHE LOADED: {len(self._cars_cache)} vehicles (CURRENT: {current_count}, UPCOMING: {upcoming_count})")
                return self._cars_cache

            if existing_count == 0:
                print(f"[AutoAI] DATABASE INITIALIZING: Empty database detected, importing {csv_row_count} records from dataset CSVs...")
            else:
                print(f"[AutoAI] DATASET SYNCHRONIZING: Partial database ({existing_count} records) detected, syncing to full {csv_row_count} records...")

            existing_cars = {c.id: c for c in db.query(Car).all()}

            inserted_count = 0
            updated_count = 0
            skipped_count = 0
            cache_rows = []

            for idx, row in df.iterrows():
                try:
                    car_id = idx + 1
                    brand = str(row.get("brand", "Unknown")).strip()
                    model = str(row.get("model", "Unknown")).strip()

                    variant_val = row.get("variant")
                    variant = str(variant_val).strip() if pd.notna(variant_val) else ""

                    price_val = row.get("price")
                    price_inr = float(price_val) if pd.notna(price_val) else 0.0

                    body_type_val = row.get("body_type")
                    body_type = str(body_type_val).strip() if pd.notna(body_type_val) else "Unknown"

                    fuel_type_val = row.get("fuel_type")
                    fuel_type = str(fuel_type_val).strip() if pd.notna(fuel_type_val) else "Unknown"

                    transmission_val = row.get("transmission")
                    transmission = str(transmission_val).strip() if pd.notna(transmission_val) else "Unknown"

                    engine_cc = _parse_numeric(row.get("engine_cc"), int, 0)
                    power = _parse_numeric(row.get("power"), int, 0)
                    torque = _parse_numeric(row.get("torque"), int, 0)

                    mileage = float(row["mileage"]) if pd.notna(row.get("mileage")) else 0.0
                    seating = int(row["seating"]) if pd.notna(row.get("seating")) else 5

                    boot_space_val = row.get("boot_space")
                    boot_space = int(boot_space_val) if pd.notna(boot_space_val) else 0

                    gc_val = row.get("ground_clearance")
                    ground_clearance = int(gc_val) if pd.notna(gc_val) else 0

                    safety_val = row.get("safety_rating")
                    safety_rating = float(safety_val) if pd.notna(safety_val) else 0.0

                    source_val = row.get("source", "carwale.com")
                    model_url_val = row.get("model_url", "")
                    variant_url_val = row.get("variant_url", "")
                    status = str(row.get("status", "CURRENT")).strip()

                    maintenance_cost = int(price_inr * 0.012) if price_inr > 0 else 8000
                    maintenance_cost = max(5000, min(40000, maintenance_cost))

                    resale_rating = 4.0
                    brand_lower = brand.lower()
                    if "toyota" in brand_lower:
                        resale_rating = 4.9
                    elif "maruti" in brand_lower:
                        resale_rating = 4.8
                    elif "hyundai" in brand_lower:
                        resale_rating = 4.5
                    elif "honda" in brand_lower:
                        resale_rating = 4.4
                    elif "kia" in brand_lower:
                        resale_rating = 4.3
                    elif "mahindra" in brand_lower:
                        resale_rating = 4.2
                    elif "tata" in brand_lower:
                        resale_rating = 4.1

                    city_use = True
                    highway_use = True
                    family_friendly = seating >= 5
                    image_url = "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80"

                    car_dict = {
                        "id": car_id,
                        "brand": brand,
                        "model": model,
                        "variant": variant,
                        "year": 2024,
                        "ex_showroom_price": price_inr,
                        "price": price_inr,
                        "body_type": body_type,
                        "fuel_type": fuel_type,
                        "fuel": fuel_type,
                        "transmission": transmission,
                        "engine_cc": engine_cc,
                        "engine": engine_cc,
                        "power": power,
                        "torque": torque,
                        "mileage": mileage,
                        "seating": seating,
                        "seating_capacity": seating,
                        "boot_space": boot_space,
                        "ground_clearance": ground_clearance,
                        "safety_rating": safety_rating,
                        "sunroof": False,
                        "adas": False,
                        "touchscreen_inches": 0.0,
                        "touchscreen": "No",
                        "carplay_androidauto": False,
                        "wireless_android_auto": "No",
                        "wireless_apple_carplay": "No",
                        "airbags": "6 airbags" if safety_rating >= 4 else "2 airbags",
                        "ideal_for": "",
                        "summary": "",
                        "summary_embedding_text": "",
                        "status": status,
                        "maintenance_cost": maintenance_cost,
                        "resale_rating": resale_rating,
                        "city_use": city_use,
                        "highway_use": highway_use,
                        "family_friendly": family_friendly,
                        "pros": "",
                        "cons": "",
                        "pros_list": [],
                        "cons_list": [],
                        "image_url": image_url,
                        "image": image_url,
                        "source": str(source_val) if pd.notna(source_val) else "carwale.com",
                        "model_url": str(model_url_val) if pd.notna(model_url_val) else "",
                        "variant_url": str(variant_url_val) if pd.notna(variant_url_val) else "",
                    }
                    cache_rows.append(car_dict)

                    if car_id in existing_cars:
                        db_car = existing_cars[car_id]
                        db_car.brand = brand
                        db_car.model = model
                        db_car.variant = variant
                        db_car.ex_showroom_price = price_inr
                        db_car.body_type = body_type
                        db_car.fuel_type = fuel_type
                        db_car.transmission = transmission
                        db_car.engine_cc = engine_cc
                        db_car.power = power
                        db_car.torque = torque
                        db_car.mileage = mileage
                        db_car.seating = seating
                        db_car.boot_space = boot_space
                        db_car.ground_clearance = ground_clearance
                        db_car.safety_rating = safety_rating
                        db_car.maintenance_cost = maintenance_cost
                        db_car.resale_rating = resale_rating
                        db_car.city_use = city_use
                        db_car.highway_use = highway_use
                        db_car.family_friendly = family_friendly
                        db_car.status = status
                        updated_count += 1
                    else:
                        new_car = Car(
                            id=car_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            ex_showroom_price=price_inr,
                            body_type=body_type,
                            fuel_type=fuel_type,
                            transmission=transmission,
                            engine_cc=engine_cc,
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
                            pros="",
                            cons="",
                            image_url=image_url,
                            year=2024,
                            sunroof=False,
                            adas=False,
                            touchscreen_inches=0.0,
                            carplay_androidauto=False,
                            ideal_for="",
                            summary_embedding_text="",
                            status=status
                        )
                        db.add(new_car)
                        inserted_count += 1

                except Exception as row_err:
                    skipped_count += 1
                    print(f"[CarDataService] Skipped row {idx}: {row_err}")
                    continue

            db.commit()
            self._cars_cache = cache_rows
            current_count = sum(1 for c in cache_rows if c.get('status') == 'CURRENT')
            upcoming_count = sum(1 for c in cache_rows if c.get('status') == 'UPCOMING')
            print(f"[AutoAI] DATASET SYNCHRONIZED: {len(self._cars_cache)} cached ({inserted_count} inserted, {updated_count} updated, {skipped_count} skipped) — {current_count} CURRENT, {upcoming_count} UPCOMING")
        except Exception as e:
            db.rollback()
            self._cars_cache = []
            print(f"[AutoAI] FAILED to synchronize database: {e}")
        finally:
            db.close()

        return self._cars_cache

    def _ensure_table_schema(self):
        """Ensures all new columns exist and column sizes are sufficient in the postgres database."""
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS year INTEGER;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS sunroof BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS adas BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS touchscreen_inches FLOAT;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS carplay_androidauto BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS ideal_for VARCHAR;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS summary_embedding_text VARCHAR;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'CURRENT';"))
            # Widen columns to fit full dataset values
            conn.execute(text("ALTER TABLE cars ALTER COLUMN variant TYPE VARCHAR(255);"))
            conn.execute(text("ALTER TABLE cars ALTER COLUMN fuel_type TYPE VARCHAR(50);"))
            conn.commit()

    def get_all_cars(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._cars_cache:
            self.load_dataset()
        if status:
            st = status.upper().strip()
            return [c for c in self._cars_cache if c.get("status") == st]
        return self._cars_cache

    def get_current_cars(self) -> List[Dict[str, Any]]:
        return self.get_all_cars(status="CURRENT")

    def get_upcoming_cars(self) -> List[Dict[str, Any]]:
        return self.get_all_cars(status="UPCOMING")

    def get_archived_cars(self) -> List[Dict[str, Any]]:
        return self.get_all_cars(status="DISCONTINUED")

    def get_car_by_id(self, car_id: int) -> Optional[Dict[str, Any]]:
        for car in self.get_all_cars():
            if car["id"] == car_id:
                return car
        return None

    def get_car_by_model(self, model: str) -> Optional[Dict[str, Any]]:
        model_clean = model.lower().strip()
        for car in self.get_all_cars():
            if model_clean in car["model"].lower() or car["model"].lower() in model_clean:
                return car
        return None

    def search_by_make(self, make: str, status: Optional[str] = "CURRENT") -> List[Dict[str, Any]]:
        make_clean = make.lower().strip()
        cars = self.get_all_cars(status=status)
        return [c for c in cars if make_clean in c["brand"].lower()]

    def search_by_budget(self, budget: float, status: Optional[str] = "CURRENT") -> List[Dict[str, Any]]:
        cars = self.get_all_cars(status=status)
        return [c for c in cars if c["price"] <= budget]

    def search_by_fuel(self, fuel: str, status: Optional[str] = "CURRENT") -> List[Dict[str, Any]]:
        fuel_clean = fuel.lower().strip()
        cars = self.get_all_cars(status=status)
        return [c for c in cars if fuel_clean in c["fuel_type"].lower()]

    def search_by_body_type(self, body_type: str, status: Optional[str] = "CURRENT") -> List[Dict[str, Any]]:
        bt_clean = body_type.lower().strip()
        cars = self.get_all_cars(status=status)
        return [c for c in cars if bt_clean in c["body_type"].lower()]

    def search_by_transmission(self, transmission: str, status: Optional[str] = "CURRENT") -> List[Dict[str, Any]]:
        t_clean = transmission.lower().strip()
        cars = self.get_all_cars(status=status)
        return [c for c in cars if t_clean in c["transmission"].lower()]

    def search_by_seating(self, seating: int, status: Optional[str] = "CURRENT") -> List[Dict[str, Any]]:
        cars = self.get_all_cars(status=status)
        return [c for c in cars if c["seating"] >= seating]

    def compare_cars(self, model1: str, model2: str) -> Dict[str, Any]:
        c1 = self.get_car_by_model(model1)
        c2 = self.get_car_by_model(model2)
        if not c1 or not c2:
            return {"error": f"One or both cars not found. Search query: '{model1}' vs '{model2}'"}
        return {"car1": c1, "car2": c2}

    def recommend_cars(self, request_data: Any) -> List[Dict[str, Any]]:
        """Rank and recommend Top 5 matches using the deterministic recommendation pipeline."""
        from app.services.recommendation_service import recommend_cars as _recommend_cars
        return _recommend_cars(request_data)


car_data_service = CarDataService()
