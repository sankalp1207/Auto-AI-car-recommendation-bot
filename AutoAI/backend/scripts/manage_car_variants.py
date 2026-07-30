import sys
import json
import csv
import argparse
from pathlib import Path

# Add backend directory to python path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.database.database import SessionLocal
from app.models.car import Car
from app.services.admin_service import (
    get_variants_summary,
    search_cars,
    update_car_variant,
    bulk_update_variants,
)


def print_summary(db):
    summary = get_variants_summary(db)
    print("\n" + "=" * 60)
    print("CAR VARIANTS SUMMARY IN DATABASE")
    print("=" * 60)
    
    total_cars = db.query(Car).count()
    print(f"Total Car Records: {total_cars}")
    print(f"Total Brands: {len(summary)}\n")
    
    for brand in sorted(summary.keys()):
        print(f"[*] {brand}")
        for model in sorted(summary[brand].keys()):
            variants_str = ", ".join([f"{v} ({c})" for v, c in summary[brand][model].items()])
            print(f"   |- {model}: {variants_str}")
    print("=" * 60 + "\n")


def do_search(db, query, brand=None, model=None, variant=None):
    results = search_cars(db, query=query, brand=brand, model=model, variant=variant)
    print(f"\nFound {len(results)} matching car(s):")
    print("-" * 75)
    print(f"{'ID':<6} | {'Brand':<18} | {'Model':<15} | {'Variant':<18} | {'Price (INR)':<10}")
    print("-" * 75)
    for car in results:
        print(f"{car.id:<6} | {car.brand:<18} | {car.model:<15} | {car.variant:<18} | Rs.{car.ex_showroom_price:,.0f}")
    print("-" * 75 + "\n")


def do_single_update(db, car_id, new_variant):
    updated = update_car_variant(db, car_id, new_variant)
    if updated:
        print(f"[OK] Successfully updated Car ID {car_id} ({updated.brand} {updated.model}) to variant: '{new_variant}'")
    else:
        print(f"[ERROR] Car ID {car_id} not found in database.")


def do_bulk_update(db, brand, model, old_variant, new_variant):
    count = bulk_update_variants(db, brand, model, old_variant, new_variant)
    print(f"[OK] Successfully updated {count} car record(s) for {brand} {model} from '{old_variant}' -> '{new_variant}'")


def do_import_map(db, filepath):
    path = Path(filepath)
    if not path.exists():
        print(f"[ERROR] File not found: {filepath}")
        return

    updated_total = 0

    if path.suffix.lower() == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                if "car_id" in item and "variant" in item:
                    if update_car_variant(db, item["car_id"], item["variant"]):
                        updated_total += 1
                elif all(k in item for k in ["brand", "model", "old_variant", "new_variant"]):
                    updated_total += bulk_update_variants(
                        db, item["brand"], item["model"], item["old_variant"], item["new_variant"]
                    )
    elif path.suffix.lower() == ".csv":
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "car_id" in row and "variant" in row:
                    if update_car_variant(db, int(row["car_id"]), row["variant"]):
                        updated_total += 1
                elif all(k in row for k in ["brand", "model", "old_variant", "new_variant"]):
                    updated_total += bulk_update_variants(
                        db, row["brand"], row["model"], row["old_variant"], row["new_variant"]
                    )
    
    print(f"[OK] Batch import finished! Total records updated: {updated_total}")



def main():
    parser = argparse.ArgumentParser(description="AutoAI Car Variant Database Management CLI")
    parser.add_argument("--summary", action="store_true", help="Print summary of all brands, models, and variants in DB")
    parser.add_argument("--search", type=str, help="Search cars by brand, model, or variant keyword")
    parser.add_argument("--brand", type=str, help="Filter by brand name")
    parser.add_argument("--model", type=str, help="Filter by model name")
    parser.add_argument("--variant", type=str, help="Filter by variant name")
    
    parser.add_argument("--update-id", type=int, help="Car ID to update variant for")
    parser.add_argument("--old-variant", type=str, help="Old variant name for bulk update")
    parser.add_argument("--new-variant", type=str, help="New variant name to set")
    
    parser.add_argument("--bulk-update", action="store_true", help="Perform bulk update (requires --brand, --model, --old-variant, --new-variant)")
    parser.add_argument("--import-map", type=str, help="Path to JSON or CSV file containing variant mappings to apply")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.summary:
            print_summary(db)
        elif args.bulk_update:
            if not all([args.brand, args.model, args.old_variant, args.new_variant]):
                print("[ERROR] Bulk update requires --brand, --model, --old-variant, and --new-variant parameters.")
            else:
                do_bulk_update(db, args.brand, args.model, args.old_variant, args.new_variant)
        elif args.update_id and args.new_variant:
            do_single_update(db, args.update_id, args.new_variant)
        elif args.import_map:
            do_import_map(db, args.import_map)
        elif args.search or args.brand or args.model or args.variant:
            do_search(db, query=args.search, brand=args.brand, model=args.model, variant=args.variant)
        else:
            parser.print_help()

    finally:
        db.close()


if __name__ == "__main__":
    main()
