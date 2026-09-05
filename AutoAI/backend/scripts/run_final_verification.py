"""
Comprehensive AutoAI Verification Test Suite
Tests all 10 requirements:
  1. Validator execution
  2. Final CSV row counts
  3. Unique brands
  4. Current / Upcoming / Archive partition counts
  5. Duplicate checks
  6. Idempotent database import
  7. GET /cars endpoint logic
  8. Recommendation endpoint logic
  9. Upcoming cars exclusion from purchasable recommendations
  10. Backend error-free initialization
"""

import sys
from pathlib import Path
import pandas as pd
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.validate_dataset import main as run_validator
from app.services.car_data_service import CarDataService
from app.schemas.recommendation import RecommendationRequest


def main():
    print("=" * 70)
    print("AUTOAI DATA LAYER FINAL VERIFICATION SUITE")
    print("=" * 70)

    # 1. Run validator
    print("\n--- [1] Running Dataset Validator ---")
    val_exit_code = run_validator()
    assert val_exit_code == 0, f"Validator failed with code {val_exit_code}"

    # 2. CSV Row Counts & Partition Counts
    print("\n--- [2, 3, 4, 5] Dataset Metrics & Partitions ---")
    data_dir = BASE_DIR / "data"
    raw_df = pd.read_csv(data_dir / "cars_india_full.csv")
    curr_df = pd.read_csv(data_dir / "cars_current.csv")
    up_df = pd.read_csv(data_dir / "cars_upcoming.csv")
    arch_df = pd.read_csv(data_dir / "cars_archive.csv")

    print(f"Raw Source (cars_india_full.csv): {len(raw_df)} rows")
    print(f"CURRENT Cars (cars_current.csv):    {len(curr_df)} rows")
    print(f"UPCOMING Cars (cars_upcoming.csv):  {len(up_df)} rows")
    print(f"ARCHIVE Cars (cars_archive.csv):    {len(arch_df)} rows")

    unique_brands = sorted(raw_df["brand"].unique().tolist())
    print(f"\nUnique Brands ({len(unique_brands)}):")
    print(", ".join(unique_brands))

    # Duplicate check
    raw_df["_k"] = raw_df["brand"] + "|" + raw_df["model"] + "|" + raw_df["variant"].fillna("")
    dups = raw_df.duplicated(subset=["_k"]).sum()
    print(f"\nDuplicate count across full dataset: {dups}")
    assert dups == 0, f"Found {dups} duplicates!"

    # 6. Check Database Import & Idempotency
    print("\n--- [6] Idempotent Database Synchronization ---")
    svc = CarDataService()
    # First load
    first_load = svc.load_dataset()
    assert len(first_load) == len(curr_df) + len(up_df), f"Expected {len(curr_df) + len(up_df)}, got {len(first_load)}"
    
    # Second load (idempotency check)
    second_load = svc.load_dataset()
    assert len(second_load) == len(first_load), "Idempotent load count mismatch!"
    print(f"Idempotent synchronization verified: {len(second_load)} cars cached & synced.")

    # 7. Verify GET /cars & Status Filtering
    print("\n--- [7] Verify /cars and Status Filtering ---")
    all_cars = svc.get_all_cars()
    current_cars = svc.get_current_cars()
    upcoming_cars = svc.get_upcoming_cars()
    archived_cars = svc.get_archived_cars()

    print(f"get_all_cars():      {len(all_cars)}")
    print(f"get_current_cars():   {len(current_cars)}")
    print(f"get_upcoming_cars():  {len(upcoming_cars)}")
    print(f"get_archived_cars():  {len(archived_cars)}")

    assert len(current_cars) == len(curr_df), "Current cars count mismatch"
    assert len(upcoming_cars) == len(up_df), "Upcoming cars count mismatch"

    # 8 & 9. Recommendation Endpoint Logic & Upcoming Exclusion
    print("\n--- [8 & 9] Recommendation Endpoint & Upcoming Exclusion Test ---")
    test_req = RecommendationRequest(
        budget=2000000.0,
        fuel_type="Petrol",
        transmission="Automatic",
        body_type="SUV",
        seating=5,
        priority="safety"
    )
    recs = svc.recommend_cars(test_req)
    print(f"Top {len(recs)} Recommended Cars for Budget <= 20L (Petrol, Automatic, SUV, Safety):")
    for r in recs:
        print(f"  - [{r['status']}] {r['brand']} {r['model']} {r.get('variant')} | Price: INR {r['price']:,.0f} | Score: {r['score']}%")
        assert r["status"] == "CURRENT", f"ERROR: Non-CURRENT car was recommended: {r['brand']} {r['model']} ({r['status']})"

    # 10. Backend Compilation
    print("\n--- [10] Backend Compilation Check ---")
    import compileall
    compile_ok = compileall.compile_dir(str(BASE_DIR / "app"), force=True, quiet=True)
    compile_ok_bot = compileall.compile_dir(str(BASE_DIR / "bot"), force=True, quiet=True)
    compile_ok_scripts = compileall.compile_dir(str(BASE_DIR / "scripts"), force=True, quiet=True)
    assert compile_ok and compile_ok_bot and compile_ok_scripts, "Compilation failed!"
    print("Backend compilation: [PASS]")

    print("\n" + "=" * 70)
    print("ALL 10 VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
