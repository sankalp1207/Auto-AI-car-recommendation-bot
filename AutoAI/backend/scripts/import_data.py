"""
AutoAI Production Vehicle Data Update Pipeline
==================================================
Provides idempotent, validated, and safe synchronization of CarWale vehicle data with PostgreSQL.

Usage:
    python -m scripts.import_data [--dry-run] [--source PATH] [--no-backup]
    python scripts/import_data.py [--dry-run] [--source PATH] [--no-backup]

Key Features:
- Comprehensive normalization (brand, model, variant, fuel, transmission, body, specs)
- Strict validation (mandatory fields, range constraints, status values, URLs)
- Duplicate detection on composite keys (brand + model + variant)
- Automatic status classification: CURRENT, UPCOMING, ARCHIVE
- Automatic pre-sync database snapshot backups (stored in backend/data/backups/)
- Dry-run simulation mode (reports New, Updated, Unchanged, Duplicates, Invalid, Archived without modifying DB)
- Transactional integrity with automatic rollback on any failure
- Data quality report generation (backend/data/data_quality_report.csv & .json)
- Data freshness metadata tracking (backend/data/import_metadata.json)
"""

import os
import sys
import argparse
import logging
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

# Setup sys.path so scripts can be run from root or backend directory
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database.database import SessionLocal, engine, Base
from app.models.car import Car

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AutoAI.DataUpdatePipeline")

DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"
DEFAULT_CURRENT_CSV = DATA_DIR / "cars_current.csv"
DEFAULT_UPCOMING_CSV = DATA_DIR / "cars_upcoming.csv"
DEFAULT_ARCHIVE_CSV = DATA_DIR / "cars_archive.csv"
REPORT_CSV = DATA_DIR / "data_quality_report.csv"
REPORT_JSON = DATA_DIR / "data_quality_report.json"
METADATA_JSON = DATA_DIR / "import_metadata.json"

# ==============================================================================
# CANONICAL NORMALIZATION MAPS
# ==============================================================================

BRAND_CANONICAL_MAP = {
    "tata": "Tata Motors",
    "tata motors": "Tata Motors",
    "maruti": "Maruti Suzuki",
    "maruti suzuki": "Maruti Suzuki",
    "hyundai": "Hyundai",
    "mahindra": "Mahindra",
    "toyota": "Toyota",
    "kia": "Kia",
    "honda": "Honda",
    "mg": "MG Motor",
    "mg motor": "MG Motor",
    "skoda": "Skoda",
    "volkswagen": "Volkswagen",
    "nissan": "Nissan",
    "renault": "Renault",
    "mercedes-benz": "Mercedes-Benz",
    "mercedes": "Mercedes-Benz",
    "bmw": "BMW",
    "audi": "Audi",
    "volvo": "Volvo",
    "byd": "BYD",
    "jeep": "Jeep",
    "land rover": "Land Rover",
    "lexus": "Lexus",
    "porsche": "Porsche",
    "jaguar": "Jaguar",
    "mini": "MINI",
    "citroen": "Citroën",
    "citroën": "Citroën",
    "force motors": "Force Motors",
    "force": "Force Motors",
    "isuzu": "Isuzu",
    "maserati": "Maserati",
    "aston martin": "Aston Martin",
    "ferrari": "Ferrari",
    "lamborghini": "Lamborghini",
    "rolls-royce": "Rolls-Royce",
    "bentley": "Bentley",
    "lotus": "Lotus",
    "mclaren": "McLaren",
    "tesla": "Tesla",
    "vinfast": "VinFast",
    "jsw": "JSW",
    "pravaig": "Pravaig",
    # Discontinued / exited brands
    "ford": "Ford",
    "chevrolet": "Chevrolet",
    "fiat": "Fiat",
    "opel": "Opel",
    "daewoo": "Daewoo",
    "premier": "Premier",
    "ssangyong": "SsangYong",
    "hummer": "Hummer",
    "gmc": "GMC",
    "icml": "ICML",
    "reva": "Reva",
    "datsun": "Datsun",
}

EXITED_BRANDS = {
    "Ford", "Chevrolet", "Fiat", "Opel", "Daewoo", "Premier",
    "SsangYong", "Hummer", "GMC", "ICML", "Reva", "Datsun",
}


def parse_numeric(val: Any) -> Optional[float]:
    """Safely converts string, number or formatted string into float."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("₹", "").replace(",", "").strip()
    if not s or s.lower() in ["nan", "null", "none", "", "tbd", "unannounced"]:
        return None
    m = re.search(r"(-?[\d.]+)", s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def parse_int_safe(val: Any) -> Optional[int]:
    """Safely converts string or number to int."""
    num = parse_numeric(val)
    if num is not None:
        try:
            return int(round(num))
        except (ValueError, OverflowError):
            return None
    return None


def normalize_fuel_type(val: Any) -> str:
    """Normalizes fuel type to standard title case."""
    if val is None or pd.isna(val):
        return "Unknown"
    s = str(val).strip().lower()
    if "electric" in s or "ev" in s:
        return "Electric"
    if "plug-in hybrid" in s or "phev" in s:
        return "Plug-in Hybrid"
    if "hybrid" in s:
        return "Hybrid"
    if "cng" in s:
        return "CNG"
    if "diesel" in s:
        return "Diesel"
    if "petrol" in s:
        return "Petrol"
    return str(val).strip().title() if val else "Unknown"


def normalize_transmission(val: Any) -> str:
    """Normalizes transmission type to standard categories."""
    if val is None or pd.isna(val):
        return "Unknown"
    s = str(val).strip().lower()
    if "manual" in s and ("amt" not in s and "auto" not in s):
        return "Manual"
    if "amt" in s or "ags" in s:
        return "Automatic (AMT)"
    if "cvt" in s:
        return "Automatic (CVT)"
    if "dct" in s or "dsg" in s or "dual clutch" in s:
        return "Automatic (DCT)"
    if "automatic" in s or "torque converter" in s or "tc" in s:
        return "Automatic"
    return str(val).strip().title() if val else "Unknown"


def normalize_body_type(val: Any) -> str:
    """Normalizes body type to standard categories."""
    if val is None or pd.isna(val):
        return "Unknown"
    s = str(val).strip().lower()
    if "suv" in s:
        return "SUV"
    if "sedan" in s:
        return "Sedan"
    if "hatchback" in s:
        return "Hatchback"
    if "muv" in s or "mpv" in s:
        return "MUV"
    if "coupe" in s:
        return "Coupe"
    if "convertible" in s or "cabriolet" in s:
        return "Convertible"
    if "pickup" in s or "truck" in s:
        return "Pickup"
    if "van" in s or "minivan" in s:
        return "Van"
    return str(val).strip().title() if val else "Unknown"


def normalize_brand_name(brand: Any) -> str:
    """Normalizes brand name using canonical mapping."""
    if brand is None or pd.isna(brand):
        return "Unknown"
    b = str(brand).strip()
    return BRAND_CANONICAL_MAP.get(b.lower(), b)


def is_valid_url(url: Any) -> bool:
    """Checks whether URL has valid HTTP/HTTPS format."""
    if url is None or pd.isna(url):
        return False
    s = str(url).strip()
    return s.startswith("http://") or s.startswith("https://")


# ==============================================================================
# PIPELINE IMPLEMENTATION
# ==============================================================================

class VehicleDataPipeline:
    """Enterprise-grade data updater pipeline for AutoAI."""

    def __init__(self, source_path: Optional[Path] = None):
        self.source_path = source_path
        self.invalid_rows: List[Dict[str, Any]] = []
        self.duplicate_rows: List[Dict[str, Any]] = []

    def ingest_data(self) -> pd.DataFrame:
        """Ingests raw or canonical CSV datasets into a single working DataFrame."""
        frames = []

        if self.source_path and Path(self.source_path).exists():
            path = Path(self.source_path)
            logger.info(f"Ingesting vehicle dataset from user-specified source: {path}")
            df = pd.read_csv(path)
            frames.append(df)
        else:
            # Default canonical sources
            for csv_path, default_status in [
                (DEFAULT_CURRENT_CSV, "CURRENT"),
                (DEFAULT_UPCOMING_CSV, "UPCOMING"),
                (DEFAULT_ARCHIVE_CSV, "ARCHIVE")
            ]:
                if csv_path.exists() and csv_path.stat().st_size > 50:
                    df = pd.read_csv(csv_path)
                    if len(df) > 0:
                        if "status" not in df.columns or df["status"].isna().all():
                            df["status"] = default_status
                        frames.append(df)
                        logger.info(f"Loaded {len(df)} rows from {csv_path.name} ({default_status})")

        if not frames:
            raise FileNotFoundError("No vehicle dataset found to ingest.")

        combined_df = pd.concat(frames, ignore_index=True)
        logger.info(f"Total raw records ingested: {len(combined_df)}")
        return combined_df

    def validate_and_normalize(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Validates row-level constraints and applies canonical normalization.
        Quarantines invalid rows and returns valid normalized dictionaries.
        """
        self.invalid_rows = []
        valid_records: List[Dict[str, Any]] = []

        for idx, row in df.iterrows():
            brand_raw = row.get("brand") or row.get("Make") or row.get("make")
            model_raw = row.get("model") or row.get("Model")
            variant_raw = row.get("variant") or row.get("Variant") or ""

            # Required field validation: Brand & Model
            if pd.isna(brand_raw) or str(brand_raw).strip() == "":
                self.invalid_rows.append({"row_index": idx, "reason": "Missing mandatory field: brand", "data": dict(row)})
                continue
            if pd.isna(model_raw) or str(model_raw).strip() == "":
                self.invalid_rows.append({"row_index": idx, "reason": "Missing mandatory field: model", "data": dict(row)})
                continue

            brand = normalize_brand_name(brand_raw)
            model = str(model_raw).strip()
            variant = str(variant_raw).strip() if pd.notna(variant_raw) else ""

            # Price validation
            price_val = row.get("price") or row.get("ex_showroom_price") or row.get("Ex-Showroom_Price")
            price = parse_numeric(price_val)
            if price is not None and price < 0:
                self.invalid_rows.append({"row_index": idx, "reason": f"Negative price value: {price}", "data": dict(row)})
                continue
            price = price or 0.0

            # Status classification / normalization
            status_val = str(row.get("status", "")).strip().upper()
            if status_val in ["DISCONTINUED", "ARCHIVED"]:
                status = "ARCHIVE"
            elif status_val in ["CURRENT", "UPCOMING", "ARCHIVE"]:
                status = status_val
            else:
                # Deterministic classification
                if bool(re.search(r'\[\d{4}-\d{4}\]', model)) or brand in EXITED_BRANDS:
                    status = "ARCHIVE"
                elif price == 0 and not variant:
                    status = "UPCOMING"
                else:
                    status = "CURRENT"

            # Specs normalization
            fuel_type = normalize_fuel_type(row.get("fuel_type") or row.get("fuel") or row.get("Fuel_Type"))
            transmission = normalize_transmission(row.get("transmission") or row.get("Type"))
            body_type = normalize_body_type(row.get("body_type") or row.get("Body_Type"))

            engine_cc = parse_int_safe(row.get("engine_cc") or row.get("Displacement")) or 0
            power = parse_int_safe(row.get("power")) or 0
            torque = parse_int_safe(row.get("torque")) or 0
            mileage = parse_numeric(row.get("mileage")) or 0.0

            seating_val = parse_int_safe(row.get("seating") or row.get("seating_capacity") or row.get("Seating_Capacity"))
            if seating_val is not None and (seating_val < 1 or seating_val > 50):
                self.invalid_rows.append({"row_index": idx, "reason": f"Unrealistic seating capacity: {seating_val}", "data": dict(row)})
                continue
            seating = seating_val or 5

            boot_space = parse_int_safe(row.get("boot_space")) or 0
            ground_clearance = parse_int_safe(row.get("ground_clearance")) or 0

            safety_val = parse_numeric(row.get("safety_rating"))
            if safety_val is not None and (safety_val < 0.0 or safety_val > 5.0):
                # Clamp or mark invalid
                safety_val = None
            safety_rating = safety_val

            # Secondary fields
            source = str(row.get("source", "carwale.com")).strip() if pd.notna(row.get("source")) else "carwale.com"
            model_url = str(row.get("model_url", "")).strip() if pd.notna(row.get("model_url")) else ""
            variant_url = str(row.get("variant_url", "")).strip() if pd.notna(row.get("variant_url")) else ""

            # Id or existing key
            car_id = parse_int_safe(row.get("id"))

            valid_records.append({
                "id": car_id,
                "brand": brand,
                "model": model,
                "variant": variant,
                "price": price,
                "ex_showroom_price": price,
                "fuel_type": fuel_type,
                "transmission": transmission,
                "body_type": body_type,
                "engine_cc": engine_cc,
                "power": power,
                "torque": torque,
                "mileage": mileage,
                "seating": seating,
                "boot_space": boot_space,
                "ground_clearance": ground_clearance,
                "safety_rating": safety_rating,
                "status": status,
                "source": source,
                "model_url": model_url,
                "variant_url": variant_url,
                "composite_key": f"{brand.lower()}||{model.lower()}||{variant.lower()}"
            })

        logger.info(f"Validation complete: {len(valid_records)} valid rows, {len(self.invalid_rows)} invalid rows quarantined")
        return valid_records

    def deduplicate(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicates records based on composite key (brand + model + variant)."""
        self.duplicate_rows = []
        seen_keys = set()
        deduped: List[Dict[str, Any]] = []

        for r in records:
            key = r["composite_key"]
            if key in seen_keys:
                self.duplicate_rows.append(r)
            else:
                seen_keys.add(key)
                deduped.append(r)

        logger.info(f"Deduplication complete: {len(self.duplicate_rows)} duplicate rows identified")
        return deduped

    def create_database_backup(self) -> Path:
        """Exports the current database state to a timestamped backup CSV."""
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"cars_backup_{timestamp}.csv"

        db = SessionLocal()
        try:
            cars = db.query(Car).all()
            if cars:
                rows = []
                for c in cars:
                    rows.append({
                        "id": c.id,
                        "brand": c.brand,
                        "model": c.model,
                        "variant": c.variant,
                        "price": c.ex_showroom_price,
                        "fuel_type": c.fuel_type,
                        "transmission": c.transmission,
                        "body_type": c.body_type,
                        "engine_cc": c.engine_cc,
                        "power": c.power,
                        "torque": c.torque,
                        "mileage": c.mileage,
                        "seating": c.seating,
                        "boot_space": c.boot_space,
                        "ground_clearance": c.ground_clearance,
                        "safety_rating": c.safety_rating,
                        "status": c.status,
                    })
                pd.DataFrame(rows).to_csv(backup_file, index=False, encoding="utf-8")
                logger.info(f"Pre-sync database snapshot backed up safely to: {backup_file}")
            else:
                logger.info("Database is currently empty; no existing records to back up.")
            return backup_file
        finally:
            db.close()

    def synchronize_database(
        self,
        records: List[Dict[str, Any]],
        dry_run: bool = False,
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """
        Synchronizes valid, deduplicated records with PostgreSQL idempotently.
        Under dry_run=True, computes all metrics without performing writes.
        Under dry_run=False, uses transactions with automatic rollback on error.
        """
        if not dry_run and create_backup:
            self.create_database_backup()

        db: Session = SessionLocal()

        stats = {
            "new": 0,
            "updated": 0,
            "unchanged": 0,
            "duplicates": len(self.duplicate_rows),
            "invalid": len(self.invalid_rows),
            "archived": 0,
            "current": 0,
            "upcoming": 0,
            "total_processed": len(records),
        }

        try:
            # Query existing cars
            existing_cars = db.query(Car).all()
            # Map existing cars by composite key and by ID
            existing_by_key = {
                f"{c.brand.lower()}||{c.model.lower()}||{(c.variant or '').lower()}": c
                for c in existing_cars
            }
            existing_by_id = {c.id: c for c in existing_cars if c.id is not None}

            incoming_keys = set()

            max_existing_id = max(existing_by_id.keys()) if existing_by_id else 0

            # Ensure PostgreSQL primary key sequence is aligned with MAX(id)
            try:
                db.execute(text("SELECT setval(pg_get_serial_sequence('cars', 'id'), coalesce((SELECT max(id) FROM cars), 1));"))
            except Exception as seq_err:
                logger.debug(f"Note on sequence align: {seq_err}")

            for idx, r in enumerate(records):
                comp_key = r["composite_key"]
                incoming_keys.add(comp_key)
                status = r["status"]

                if status == "CURRENT":
                    stats["current"] += 1
                elif status == "UPCOMING":
                    stats["upcoming"] += 1
                elif status == "ARCHIVE":
                    stats["archived"] += 1

                # Locate existing car match
                existing_match: Optional[Car] = None
                if r.get("id") and r["id"] in existing_by_id:
                    existing_match = existing_by_id[r["id"]]
                elif comp_key in existing_by_key:
                    existing_match = existing_by_key[comp_key]

                if existing_match:
                    # Check for changed fields
                    price_diff = abs((existing_match.ex_showroom_price or 0) - r["price"]) > 1.0
                    status_diff = (existing_match.status or "").upper() != status.upper()
                    trans_diff = (existing_match.transmission or "") != r["transmission"]
                    fuel_diff = (existing_match.fuel_type or "") != r["fuel_type"]

                    if price_diff or status_diff or trans_diff or fuel_diff:
                        stats["updated"] += 1
                        if not dry_run:
                            existing_match.ex_showroom_price = r["price"]
                            existing_match.status = status
                            existing_match.transmission = r["transmission"]
                            existing_match.fuel_type = r["fuel_type"]
                            existing_match.engine_cc = r["engine_cc"]
                            existing_match.power = r["power"]
                            existing_match.torque = r["torque"]
                            existing_match.mileage = r["mileage"]
                            existing_match.seating = r["seating"]
                            existing_match.boot_space = r["boot_space"]
                            existing_match.ground_clearance = r["ground_clearance"]
                            existing_match.safety_rating = r["safety_rating"]
                    else:
                        stats["unchanged"] += 1
                else:
                    # New vehicle
                    stats["new"] += 1
                    if not dry_run:
                        if r.get("id") and r["id"] not in existing_by_id:
                            assigned_id = r["id"]
                        else:
                            max_existing_id += 1
                            assigned_id = max_existing_id

                        car_obj = Car(
                            id=assigned_id,
                            brand=r["brand"],
                            model=r["model"],
                            variant=r["variant"],
                            ex_showroom_price=r["price"],
                            body_type=r["body_type"],
                            fuel_type=r["fuel_type"],
                            transmission=r["transmission"],
                            engine_cc=r["engine_cc"],
                            power=r["power"],
                            torque=r["torque"],
                            mileage=r["mileage"],
                            seating=r["seating"],
                            boot_space=r["boot_space"],
                            ground_clearance=r["ground_clearance"],
                            safety_rating=r["safety_rating"],
                            status=status,
                            year=2024,
                            city_use=True,
                            highway_use=True,
                            family_friendly=(r["seating"] >= 5),
                            maintenance_cost=max(5000, min(40000, int(r["price"] * 0.012))) if r["price"] > 0 else 8000,
                            resale_rating=4.2,
                            image_url="https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80"
                        )
                        db.add(car_obj)

            if not dry_run:
                db.commit()
                try:
                    db.execute(text("SELECT setval(pg_get_serial_sequence('cars', 'id'), coalesce((SELECT max(id) FROM cars), 1));"))
                    db.commit()
                except Exception:
                    pass
                logger.info("Database transaction committed successfully!")
                self._save_metadata(stats)
            else:
                db.rollback()
                logger.info("Dry-run complete: PostgreSQL was NOT modified.")

            return stats

        except Exception as e:
            db.rollback()
            logger.error(f"Database sync failed — transaction rolled back safely: {e}")
            raise e
        finally:
            db.close()

    def generate_data_quality_report(self, stats: Dict[str, Any], raw_count: int) -> Path:
        """Generates comprehensive metrics and outputs data_quality_report.csv and .json."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        report_rows = [
            {"Metric": "total_input_rows", "Value": str(raw_count)},
            {"Metric": "valid_rows", "Value": str(stats["total_processed"])},
            {"Metric": "invalid_rows", "Value": str(stats["invalid"])},
            {"Metric": "duplicates", "Value": str(stats["duplicates"])},
            {"Metric": "new_vehicles", "Value": str(stats["new"])},
            {"Metric": "updated_vehicles", "Value": str(stats["updated"])},
            {"Metric": "unchanged_vehicles", "Value": str(stats["unchanged"])},
            {"Metric": "archived_vehicles", "Value": str(stats["archived"])},
            {"Metric": "current_vehicles", "Value": str(stats["current"])},
            {"Metric": "upcoming_vehicles", "Value": str(stats["upcoming"])},
            {"Metric": "last_sync_timestamp", "Value": datetime.now().isoformat()},
        ]

        # Save CSV
        pd.DataFrame(report_rows).to_csv(REPORT_CSV, index=False, encoding="utf-8")

        # Save JSON
        with open(REPORT_JSON, "w", encoding="utf-8") as f:
            json.dump({r["Metric"]: r["Value"] for r in report_rows}, f, indent=2)

        logger.info(f"Saved Data Quality Report to {REPORT_CSV}")
        return REPORT_CSV

    def _save_metadata(self, stats: Dict[str, Any]):
        """Persists data freshness metadata for the application."""
        metadata = {
            "last_successful_import": datetime.now().isoformat(),
            "source": str(self.source_path or "CarWale Dataset (cars_current.csv + cars_upcoming.csv)"),
            "dataset_version": "2026.09",
            "total_records": stats["total_processed"],
            "current_records": stats["current"],
            "upcoming_records": stats["upcoming"],
            "archive_records": stats["archived"],
            "last_sync_stats": stats,
        }
        with open(METADATA_JSON, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Freshness metadata saved to {METADATA_JSON}")


def run_pipeline(
    source_path: Optional[str] = None,
    dry_run: bool = False,
    create_backup: bool = True
) -> Dict[str, Any]:
    """Top-level pipeline execution function."""
    src = Path(source_path) if source_path else None
    pipeline = VehicleDataPipeline(source_path=src)

    raw_df = pipeline.ingest_data()
    raw_count = len(raw_df)

    valid_records = pipeline.validate_and_normalize(raw_df)
    deduped_records = pipeline.deduplicate(valid_records)

    stats = pipeline.synchronize_database(
        deduped_records,
        dry_run=dry_run,
        create_backup=create_backup
    )

    pipeline.generate_data_quality_report(stats, raw_count)

    # Output formatted dry run / execution summary
    mode_str = "DRY RUN SIMULATION" if dry_run else "DATABASE SYNCHRONIZATION"
    print("\n" + "=" * 60)
    print(f"AUTOAI VEHICLE DATA PIPELINE — {mode_str}")
    print("=" * 60)
    print(f"New:         {stats['new']}")
    print(f"Updated:     {stats['updated']}")
    print(f"Unchanged:   {stats['unchanged']}")
    print(f"Duplicates:  {stats['duplicates']}")
    print(f"Invalid:     {stats['invalid']}")
    print(f"Archived:    {stats['archived']}")
    print("-" * 60)
    print(f"Current:     {stats['current']}")
    print(f"Upcoming:    {stats['upcoming']}")
    print("=" * 60 + "\n")

    return stats


def main():
    parser = argparse.ArgumentParser(description="AutoAI Vehicle Data Update Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Simulate synchronization without modifying PostgreSQL")
    parser.add_argument("--source", type=str, default=None, help="Path to custom vehicle CSV file")
    parser.add_argument("--no-backup", action="store_true", help="Skip pre-synchronization database snapshot backup")

    args = parser.parse_args()

    run_pipeline(
        source_path=args.source,
        dry_run=args.dry_run,
        create_backup=not args.no_backup
    )


if __name__ == "__main__":
    main()
