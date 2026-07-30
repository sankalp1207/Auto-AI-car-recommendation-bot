import sys
from pathlib import Path

# Add backend directory to python path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.database.database import SessionLocal
from app.models.car import Car


def fix_ev_fuel_types():
    db = SessionLocal()
    try:
        # Known pure electric models
        ev_model_patterns = [
            "%Comet EV%",
            "%ZS EV%",
            "%Atto 3%",
            "%Seal%",
            "%eMAX 7%",
            "%EV6%",
            "%BE 6%",
            "%Ioniq%",
            "%Taycan%",
            "%i4%",
            "%iX%",
        ]

        total_fixed = 0

        for pattern in ev_model_patterns:
            cars = db.query(Car).filter(
                Car.model.ilike(pattern),
                Car.fuel_type != "Electric"
            ).all()

            for car in cars:
                print(f"[FIX] Setting fuel_type='Electric' for {car.brand} {car.model} (ID {car.id}), was '{car.fuel_type}'")
                car.fuel_type = "Electric"
                total_fixed += 1

        db.commit()
        print(f"\n[OK] Successfully fixed fuel_type to 'Electric' for {total_fixed} EV car records in database.")
    finally:
        db.close()


if __name__ == "__main__":
    fix_ev_fuel_types()
