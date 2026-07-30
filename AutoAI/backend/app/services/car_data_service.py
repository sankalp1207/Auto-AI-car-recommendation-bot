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
CSV_PATH = BASE_DIR / "data" / "AI_Car_Recommendation_Chatbot_Dataset.csv"

# Pre-defined high-quality mappings for specifications not explicitly in the columns
TORQUE_MAPPING = {
    "alto k10": 89,
    "swift": 113,
    "tiago": 113,
    "tiago.ev": 114,
    "i20": 115,
    "nexon": 170,
    "brezza": 137,
    "venue": 172,
    "sonet": 172,
    "xuv3xo": 230,
    "creta": 144,
    "seltos": 253,
    "scorpio-n": 400,
    "xuv700": 450,
    "safari": 350,
    "urban cruiser hyryder": 141,
    "city": 253,
    "virtus": 250,
    "verna": 253,
    "3 series gran limousine": 400,
    "fortuner": 500,
}

AIRBAGS_MAPPING = {
    "alto k10": "2 airbags",
    "swift": "6 airbags",
    "tiago": "2 airbags",
    "tiago.ev": "2 airbags",
    "i20": "6 airbags",
    "nexon": "6 airbags",
    "brezza": "6 airbags",
    "venue": "6 airbags",
    "sonet": "6 airbags",
    "xuv3xo": "6 airbags",
    "creta": "6 airbags",
    "seltos": "6 airbags",
    "scorpio-n": "6 airbags",
    "xuv700": "7 airbags",
    "safari": "7 airbags",
    "urban cruiser hyryder": "6 airbags",
    "city": "6 airbags",
    "virtus": "6 airbags",
    "verna": "6 airbags",
    "3 series gran limousine": "6 airbags",
    "fortuner": "7 airbags",
}

PROS_MAPPING = {
    "alto k10": ["Very low budget", "Exceptionally high mileage (24.39 kmpl)", "Highly compact for easy city parking", "Very low maintenance cost"],
    "swift": ["Outstanding mileage (25.75 kmpl)", "Sporty driving dynamics", "Excellent resale value", "Reliable Maruti service network"],
    "tiago": ["High 4-star safety rating", "Robust build quality", "Premium Harman audio system", "Comfortable ride quality"],
    "tiago.ev": ["Extremely low running costs", "Zero tailpipe emissions", "Quiet electric drive", "Instant torque for city commutes"],
    "i20": ["Premium cabin feel", "Loaded with features (sunroof, Bose sound)", "Smooth CVT option", "Spacious rear seat"],
    "nexon": ["Benchmark 5-star safety rating", "High ground clearance (208mm)", "Voice-assisted sunroof", "Ventilated seats"],
    "brezza": ["Highly reliable smart hybrid engine", "Excellent city drivability", "Good resale value", "Great feature list (sunroof, 360 camera)"],
    "venue": ["Level 1 ADAS capability", "Quick DCT transmission", "Comfortable seats", "Good connected car tech"],
    "sonet": ["Aesthetic sporty styling", "Premium Bose sound system", "Ventilated front seats", "Level 1 ADAS", "High ground clearance"],
    "xuv3xo": ["First-in-segment panoramic sunroof", "Level 2 ADAS features", "Most powerful engine in segment (129 BHP)", "5-star safety rating"],
    "creta": ["Benchmark mid-size SUV comfort", "Panoramic sunroof", "Level 2 ADAS", "Premium Bose audio", "Smooth CVT transmission"],
    "seltos": ["Sporty handling dynamics", "Powerful 158 BHP engine", "Dual curved displays", "Level 2 ADAS", "Panoramic sunroof"],
    "scorpio-n": ["Rugged ladder-frame chassis", "True 4x4 off-road capability", "Command seating position", "5-star safety rating"],
    "xuv700": ["High power (182 BHP) diesel", "Level 2 ADAS safety package", "5-star GNCAP rating", "AWD capability", "Luxurious interior"],
    "safari": ["Luxurious second-row captain seats", "5-star safety rating", "Huge road presence", "12.3-inch Harman display"],
    "urban cruiser hyryder": ["Incredible 27.97 kmpl strong hybrid efficiency", "Toyota reliability", "High ground clearance (210mm)"],
    "city": ["Unmatched rear seat comfort", "27.13 kmpl hybrid mileage", "Honda Sensing ADAS package", "Classic premium sedan ride"],
    "virtus": ["Superb European driving dynamics", "5-star safety rating", "Huge 521L boot space", "Excellent high-speed stability"],
    "verna": ["Very fast acceleration (158 BHP)", "5-star safety rating", "Level 2 ADAS", "Large 528L boot space"],
    "3 series gran limousine": ["Exceptional rear legroom and comfort", "Chauffeur-driven luxury", "High status symbol", "Powerful engine"],
    "fortuner": ["Unmatched resale value", "Extreme rugged reliability", "Off-road dominance", "High street status and presence"],
}

CONS_MAPPING = {
    "alto k10": ["Low build quality", "Poor 2-star safety rating", "Lacks premium features", "Unstable at high speeds"],
    "swift": ["Average 3-star safety rating", "AMT transmission can feel jerky", "Low cabin noise insulation"],
    "tiago": ["3-cylinder engine vibration at idle", "Slightly heavy steering in city", "Average fuel economy under load"],
    "tiago.ev": ["Limited highway range", "Slow public DC charging compared to larger EVs", "Lacks active battery cooling"],
    "i20": ["Average safety rating (3-star)", "Relatively expensive for a hatchback", "Lower mileage compared to Maruti counterparts"],
    "nexon": ["Clunky infotainment system UI", "Average diesel engine refinement", "Stiff ride at low speeds"],
    "brezza": ["4-star safety is good but not 5-star", "Cabin plastic quality is mediocre", "Higher price than rivals"],
    "venue": ["Tight rear legroom", "3-star safety rating", "Small boot space"],
    "sonet": ["Stiff suspension ride", "3-star safety rating", "Expensive top-spec variants"],
    "xuv3xo": ["Small boot space", "Polarized exterior styling", "High waiting periods"],
    "creta": ["Average 3-star safety rating", "Highly common on roads", "Diesel engine can feel sluggish"],
    "seltos": ["Firm ride quality over bad roads", "3-star safety rating", "Lower fuel mileage"],
    "scorpio-n": ["Bumpy ride on bad roads", "Heavy steering in tight spaces", "Poor fuel economy in city traffic"],
    "xuv700": ["Very long waiting periods", "Heavy vehicle dynamics", "Expensive top-end variants"],
    "safari": ["No AWD option", "Heavy to steer in city traffic", "Minor software glitches in screen"],
    "urban cruiser hyryder": ["Small boot space due to battery", "Low headroom in rear seat", "Engine noise when accelerating hard"],
    "city": ["Low ground clearance (165mm)", "Expensive price tag", "Rubbery CVT drone at high RPM"],
    "virtus": ["Firm ride quality", "Higher maintenance costs", "DSG transmission has long-term reliability concerns"],
    "verna": ["Futuristic design is controversial", "Low headroom", "Low ground clearance (170mm)"],
    "3 series gran limousine": ["Very expensive", "Low ground clearance (135mm)", "High maintenance cost"],
    "fortuner": ["Very basic features for the price", "Bumpy ride quality", "Noisy engine cabin"],
}

IMAGE_MAPPING = {
    "alto k10": "https://images.unsplash.com/photo-1605559424843-9e4c228bf1c2?auto=format&fit=crop&w=800&q=80",
    "swift": "https://images.unsplash.com/photo-1525609004556-c46c7d6cf0a3?auto=format&fit=crop&w=800&q=80",
    "tiago": "https://images.unsplash.com/photo-1617788138017-80ad40651399?auto=format&fit=crop&w=800&q=80",
    "tiago.ev": "https://images.unsplash.com/photo-1563720223185-11003d516935?auto=format&fit=crop&w=800&q=80",
    "i20": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "nexon": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "brezza": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "venue": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "sonet": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "xuv3xo": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "creta": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "seltos": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "scorpio-n": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "xuv700": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "safari": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "urban cruiser hyryder": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
    "city": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80",
    "virtus": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80",
    "verna": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80",
    "3 series gran limousine": "https://images.unsplash.com/photo-1555215695-3004980ad54e?auto=format&fit=crop&w=800&q=80",
    "fortuner": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
}

class CarDataService:
    def __init__(self):
        self._cars_cache: List[Dict[str, Any]] = []

    def load_dataset(self) -> List[Dict[str, Any]]:
        """Loads and processes the CSV once, caching it in memory and seeding the DB."""
        if not CSV_PATH.exists():
            print(f"Dataset CSV not found at {CSV_PATH}")
            return []

        print(f"Loading CSV dataset from: {CSV_PATH}")
        df = pd.read_csv(CSV_PATH)
        self._cars_cache = []

        db = SessionLocal()
        try:
            # Ensure schema matches what's configured
            self._ensure_table_schema()

            print("Clearing existing car records for dataset synchronization...")
            db.query(Car).delete()
            db.commit()

            cars_to_add = []

            for idx, row in df.iterrows():
                brand = str(row.get("Make", "Unknown")).strip()
                model = str(row.get("Model", "Unknown")).strip()
                variant = str(row.get("Variant", "Standard")).strip()
                
                # Ex_Showroom_Price_Lakh conversion
                price_lakh = float(row.get("Ex_Showroom_Price_Lakh", 0.0))
                price_inr = price_lakh * 100000.0

                body_type = str(row.get("Body_Type", "Hatchback")).strip()
                fuel_type = str(row.get("Fuel_Type", "Petrol")).strip()
                transmission = str(row.get("Transmission", "Manual")).strip()

                engine_cc = int(row.get("Engine_cc", 0))
                power = int(row.get("BHP", 0))
                seating = int(row.get("Seating_Capacity", 5))
                boot_space = int(row.get("Boot_Space_L", 300))
                ground_clearance = int(row.get("Ground_Clearance_mm", 165))
                safety_rating = float(row.get("NCAP_Safety_Rating", 0.0))
                mileage = float(row.get("Mileage_kmpl", 15.0))

                # Sunroof, ADAS, CarPlay_AndroidAuto
                sunroof = bool(row.get("Sunroof", False))
                adas = bool(row.get("ADAS", False))
                
                touchscreen_val = row.get("Touchscreen_Inches", 0.0)
                touchscreen_inches = float(touchscreen_val) if pd.notna(touchscreen_val) else 0.0
                
                carplay_androidauto = bool(row.get("CarPlay_AndroidAuto", False))
                ideal_for = str(row.get("Ideal_For", "")).strip()
                summary_text = str(row.get("Summary_Embedding_Text", "")).strip()
                year = int(row.get("Year", 2024))

                # Normalize keys for lookup maps
                norm_key = model.lower().strip()
                
                # Additional specs mappings
                torque = TORQUE_MAPPING.get(norm_key, int(power * 1.3) if power > 0 else 150)
                airbags_str = AIRBAGS_MAPPING.get(norm_key, "6 airbags" if safety_rating >= 4 else "2 airbags")
                pros = PROS_MAPPING.get(norm_key, ["Comfortable driving", "Reliable performance"])
                cons = CONS_MAPPING.get(norm_key, ["Standard maintenance costs"])
                image_url = IMAGE_MAPPING.get(norm_key, "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80")

                # Derive maintenance_cost
                maintenance_cost = int(price_inr * 0.012)
                maintenance_cost = max(5000, min(40000, maintenance_cost))
                if "alto" in norm_key:
                    maintenance_cost = 4500
                elif "bmw" in norm_key:
                    maintenance_cost = 35000

                # Derive resale_rating
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

                # Derive city_use / highway_use / family_friendly
                city_use = True
                if "fortuner" in norm_key or "scorpio" in norm_key:
                    city_use = False
                
                highway_use = True
                if "alto" in norm_key:
                    highway_use = False

                family_friendly = seating >= 5 or "family" in ideal_for.lower()

                # Save as structured dict
                car_dict = {
                    "id": idx + 1,
                    "brand": brand,
                    "model": model,
                    "variant": variant,
                    "year": year,
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
                    "sunroof": sunroof,
                    "adas": adas,
                    "touchscreen_inches": touchscreen_inches,
                    "touchscreen": f"{touchscreen_inches} inches" if touchscreen_inches > 0 else "No",
                    "carplay_androidauto": carplay_androidauto,
                    "wireless_android_auto": "Yes" if carplay_androidauto else "No",
                    "wireless_apple_carplay": "Yes" if carplay_androidauto else "No",
                    "airbags": airbags_str,
                    "ideal_for": ideal_for,
                    "summary": summary_text,
                    "summary_embedding_text": summary_text,
                    "maintenance_cost": maintenance_cost,
                    "resale_rating": resale_rating,
                    "city_use": city_use,
                    "highway_use": highway_use,
                    "family_friendly": family_friendly,
                    "pros": ", ".join(pros),
                    "cons": ", ".join(cons),
                    "pros_list": pros,
                    "cons_list": cons,
                    "image_url": image_url,
                    "image": image_url
                }
                self._cars_cache.append(car_dict)

                # Store in DB
                db_car = Car(
                    id=idx + 1,
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
                    pros=", ".join(pros),
                    cons=", ".join(cons),
                    image_url=image_url,
                    year=year,
                    sunroof=sunroof,
                    adas=adas,
                    touchscreen_inches=touchscreen_inches,
                    carplay_androidauto=carplay_androidauto,
                    ideal_for=ideal_for,
                    summary_embedding_text=summary_text
                )
                cars_to_add.append(db_car)

            db.bulk_save_objects(cars_to_add)
            db.commit()
            print(f"Successfully loaded {len(self._cars_cache)} cars from dataset CSV and seeded database!")
        except Exception as e:
            db.rollback()
            print(f"Error seeding database during CSV load: {e}")
        finally:
            db.close()

        return self._cars_cache

    def _ensure_table_schema(self):
        """Ensures all new columns exist in the postgres database."""
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS year INTEGER;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS sunroof BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS adas BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS touchscreen_inches FLOAT;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS carplay_androidauto BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS ideal_for VARCHAR;"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS summary_embedding_text VARCHAR;"))
            conn.commit()

    def get_all_cars(self) -> List[Dict[str, Any]]:
        if not self._cars_cache:
            self.load_dataset()
        return self._cars_cache

    def get_car_by_id(self, car_id: int) -> Optional[Dict[str, Any]]:
        for car in self.get_all_cars():
            if car["id"] == car_id:
                return car
        return None

    def get_car_by_model(self, model: str) -> Optional[Dict[str, Any]]:
        model_clean = model.lower().strip()
        for car in self.get_all_cars():
            # Exact model match or substring matching
            if model_clean in car["model"].lower() or car["model"].lower() in model_clean:
                return car
        return None

    def search_by_make(self, make: str) -> List[Dict[str, Any]]:
        make_clean = make.lower().strip()
        return [c for c in self.get_all_cars() if make_clean in c["brand"].lower()]

    def search_by_budget(self, budget: float) -> List[Dict[str, Any]]:
        return [c for c in self.get_all_cars() if c["price"] <= budget]

    def search_by_fuel(self, fuel: str) -> List[Dict[str, Any]]:
        fuel_clean = fuel.lower().strip()
        return [c for c in self.get_all_cars() if fuel_clean in c["fuel_type"].lower()]

    def search_by_body_type(self, body_type: str) -> List[Dict[str, Any]]:
        bt_clean = body_type.lower().strip()
        return [c for c in self.get_all_cars() if bt_clean in c["body_type"].lower()]

    def search_by_transmission(self, transmission: str) -> List[Dict[str, Any]]:
        t_clean = transmission.lower().strip()
        return [c for c in self.get_all_cars() if t_clean in c["transmission"].lower()]

    def search_by_seating(self, seating: int) -> List[Dict[str, Any]]:
        return [c for c in self.get_all_cars() if c["seating"] >= seating]

    def compare_cars(self, model1: str, model2: str) -> Dict[str, Any]:
        c1 = self.get_car_by_model(model1)
        c2 = self.get_car_by_model(model2)
        if not c1 or not c2:
            return {"error": f"One or both cars not found. Search query: '{model1}' vs '{model2}'"}
        return {"car1": c1, "car2": c2}

    def recommend_cars(self, request_data: Any) -> List[Dict[str, Any]]:
        """Rank and recommend Top 5 matches based on filters and weights."""
        cars = self.get_all_cars()
        scored_cars = []

        budget = getattr(request_data, "budget", None)
        fuel = getattr(request_data, "fuel", None) or getattr(request_data, "fuel_type", None)
        transmission = getattr(request_data, "transmission", None)
        body_type = getattr(request_data, "body_type", None)
        seating = getattr(request_data, "seating", None) or getattr(request_data, "family_members", None)
        priority = getattr(request_data, "priority", None)
        city_drive = getattr(request_data, "city_drive", None)
        highway_drive = getattr(request_data, "highway_drive", None)

        for car in cars:
            score = 0
            reasons = []

            # 1. Budget Match
            if budget is not None and budget > 0:
                if car["price"] <= budget:
                    score += 30
                    reasons.append("Within budget limit")
                else:
                    # Ignore cars over budget if filter is strict, or apply a penalty
                    continue

            # 2. Fuel Preference
            if fuel:
                if fuel.lower().strip() in car["fuel_type"].lower():
                    score += 20
                    reasons.append("Preferred fuel type")
                else:
                    continue  # Strict matching on fuel if provided

            # 3. Transmission Preference
            if transmission:
                if transmission.lower().strip() in car["transmission"].lower():
                    score += 15
                    reasons.append("Preferred transmission")
                else:
                    continue  # Strict matching on transmission if provided

            # 4. Body Type Preference
            if body_type:
                if body_type.lower().strip() in car["body_type"].lower():
                    score += 15
                    reasons.append("Preferred body style")

            # 5. Seating Capacity
            if seating:
                if car["seating"] >= seating:
                    score += 10
                    reasons.append(f"Comfortable seating for {seating}+")
                else:
                    continue  # Strict seating match

            # 6. Safety Rating
            safety_pts = car["safety_rating"] * 5
            score += safety_pts

            # 7. Mileage
            mileage_pts = min(15, car["mileage"] * 0.6)
            score += mileage_pts

            # 8. Boot Space
            boot_pts = min(10, car["boot_space"] / 50.0)
            score += boot_pts

            # 9. Maintenance Cost
            maint_pts = max(0, 15 - (car["maintenance_cost"] / 2000.0))
            score += maint_pts

            # 10. Resale Value
            resale_pts = car["resale_rating"] * 3
            score += resale_pts

            # 11. Family Friendliness
            if car["family_friendly"]:
                score += 5

            # 12. City Drive Use
            if city_drive and car["city_use"]:
                score += 10
                reasons.append("Ideal for city driving")

            # 13. Highway Cruiser
            if highway_drive and car["highway_use"]:
                score += 10
                reasons.append("Great for highway stability")

            # 14. Priorities Multipliers
            if priority:
                priority_lower = priority.lower().strip()
                if "safety" in priority_lower:
                    score += car["safety_rating"] * 6
                    reasons.append("Top-tier safety choice")
                elif "mileage" in priority_lower:
                    score += car["mileage"] * 0.8
                    reasons.append("Extremely fuel efficient")
                elif "maintenance" in priority_lower:
                    score += max(0, 20 - (car["maintenance_cost"] / 1500.0))
                    reasons.append("Low maintenance costs")
                elif "resale" in priority_lower:
                    score += car["resale_rating"] * 5
                    reasons.append("Outstanding resale value")

            # Normalize Score to a nice percentage out of 100
            max_possible = 180.0
            norm_score = min(100.0, round((score / max_possible) * 100, 1))

            scored_cars.append({
                **car,
                "score": norm_score,
                "reasons": reasons if reasons else ["Matches your preferences"]
            })

        # Sort by score descending
        scored_cars.sort(key=lambda x: x["score"], reverse=True)
        return scored_cars[:5]

car_data_service = CarDataService()
