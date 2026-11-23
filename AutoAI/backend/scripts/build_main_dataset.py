"""
AutoAI Main Dataset Consolidator
Combines active vehicle catalog (cars_current.csv) and validated new launches (cars_new_launches.csv)
into a single, unified main dataset of all cars available in India.

Outputs:
  - backend/data/cars_main.csv (Primary unified dataset of all currently available cars)
  - backend/data/main_dataset_metadata.json (Consolidation metadata and quality report)
  - Optionally syncs backend/data/cars_current.csv (with automatic backup)
"""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("BuildMainDataset")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "backend" / "data"
NEW_LAUNCHES_DIR = BASE_DIR / "backend" / "ml" / "data" / "new_launches"

DEFAULT_CURRENT_CSV = DATA_DIR / "cars_main.csv" if (DATA_DIR / "cars_main.csv").exists() and not (DATA_DIR / "cars_current.csv").exists() else DATA_DIR / "cars_current.csv"
DEFAULT_NEW_LAUNCHES_CSV = NEW_LAUNCHES_DIR / "cars_new_launches.csv"
DEFAULT_UPCOMING_CSV = DATA_DIR / "cars_upcoming.csv"
DEFAULT_MAIN_CSV = DATA_DIR / "cars_main.csv"
METADATA_JSON_PATH = DATA_DIR / "main_dataset_metadata.json"

STANDARD_COLUMNS = [
    "brand", "model", "variant", "price", "fuel_type", "transmission",
    "body_type", "engine_cc", "power", "torque", "mileage", "seating",
    "boot_space", "ground_clearance", "safety_rating", "battery_capacity",
    "range_km", "status", "source", "model_url", "variant_url",
    "launch_date", "record_type"
]


def norm_str(s: Any) -> str:
    """Normalizes string for robust key comparison."""
    if s is None or pd.isna(s):
        return ""
    val = str(s).strip().lower()
    return " ".join(val.split())


def create_key(row: pd.Series) -> str:
    """Creates normalized composite key (brand|model|variant)."""
    b = norm_str(row.get("brand"))
    m = norm_str(row.get("model"))
    v = norm_str(row.get("variant"))
    return f"{b}|{m}|{v}"


class MainDatasetBuilder:
    def __init__(
        self,
        current_csv: Path = DEFAULT_CURRENT_CSV,
        new_launches_csv: Path = DEFAULT_NEW_LAUNCHES_CSV,
        upcoming_csv: Path = DEFAULT_UPCOMING_CSV,
        output_main_csv: Path = DEFAULT_MAIN_CSV,
        sync_current_csv: bool = False,
        include_upcoming: bool = False,
    ):
        self.current_csv = current_csv
        self.new_launches_csv = new_launches_csv
        self.upcoming_csv = upcoming_csv
        self.output_main_csv = output_main_csv
        self.sync_current_csv = sync_current_csv
        self.include_upcoming = include_upcoming

    def build(self) -> pd.DataFrame:
        logger.info("=" * 65)
        logger.info("Building Consolidated Main Car Dataset for AutoAI")
        logger.info(f"Source Current Cars:  {self.current_csv}")
        logger.info(f"Source New Launches:  {self.new_launches_csv}")
        logger.info(f"Output Main Dataset:  {self.output_main_csv}")
        logger.info("=" * 65)

        if not self.current_csv.exists():
            raise FileNotFoundError(f"Base catalog not found: {self.current_csv}")
        if not self.new_launches_csv.exists():
            raise FileNotFoundError(f"New launches dataset not found: {self.new_launches_csv}")

        df_curr = pd.read_csv(self.current_csv)
        df_new = pd.read_csv(self.new_launches_csv)

        logger.info(f"Loaded {len(df_curr)} existing current vehicles.")
        logger.info(f"Loaded {len(df_new)} validated new launch vehicles.")

        # Ensure provenance columns exist on current dataframe
        if "launch_date" not in df_curr.columns:
            df_curr["launch_date"] = "Pre-2026-09"
        else:
            df_curr["launch_date"] = df_curr["launch_date"].fillna("Pre-2026-09")

        if "record_type" not in df_curr.columns:
            df_curr["record_type"] = "EXISTING_CATALOG"
        else:
            df_curr["record_type"] = df_curr["record_type"].fillna("EXISTING_CATALOG")

        # Create composite comparison keys
        df_curr["_key"] = df_curr.apply(create_key, axis=1)
        df_new["_key"] = df_new.apply(create_key, axis=1)

        curr_keys_set = set(df_curr["_key"])
        new_keys_set = set(df_new["_key"])

        # Identify overlaps and new additions
        updated_keys = curr_keys_set.intersection(new_keys_set)
        brand_new_keys = new_keys_set - curr_keys_set

        logger.info(f"Existing records updated with latest 2026 launch specs: {len(updated_keys)}")
        logger.info(f"Brand-new records added to active catalog:               {len(brand_new_keys)}")

        # Retain current records that were NOT superseded by a new launch
        df_curr_retained = df_curr[~df_curr["_key"].isin(new_keys_set)].copy()

        # Combine retained current records with all new launch records (which include the updated ones)
        combined_df = pd.concat([df_curr_retained, df_new], ignore_index=True)
        combined_df.drop(columns=["_key"], inplace=True)

        # Standardize status to CURRENT for all available vehicles
        combined_df["status"] = "CURRENT"

        # If requested, also append upcoming vehicles
        upcoming_count = 0
        if self.include_upcoming and self.upcoming_csv.exists():
            df_up = pd.read_csv(self.upcoming_csv)
            df_up["_key"] = df_up.apply(create_key, axis=1)
            # Exclude upcoming vehicles that have now launched
            df_up_remaining = df_up[~df_up["_key"].isin(new_keys_set)].copy()
            df_up_remaining.drop(columns=["_key"], inplace=True)
            if "launch_date" not in df_up_remaining.columns:
                df_up_remaining["launch_date"] = "UPCOMING"
            if "record_type" not in df_up_remaining.columns:
                df_up_remaining["record_type"] = "UPCOMING"
            upcoming_count = len(df_up_remaining)
            combined_df = pd.concat([combined_df, df_up_remaining], ignore_index=True)
            logger.info(f"Included {upcoming_count} upcoming vehicles.")

        # Ensure all standard columns are present
        for col in STANDARD_COLUMNS:
            if col not in combined_df.columns:
                combined_df[col] = None

        # Reorder to standard columns
        ordered_cols = [c for c in STANDARD_COLUMNS if c in combined_df.columns]
        extra_cols = [c for c in combined_df.columns if c not in STANDARD_COLUMNS]
        final_df = combined_df[ordered_cols + extra_cols].copy()

        # Sort deterministically by brand, model, price
        final_df.sort_values(
            by=["brand", "model", "price"],
            ascending=[True, True, True],
            na_position="last",
            inplace=True
        )
        final_df.reset_index(drop=True, inplace=True)

        # Save primary main dataset with automatic safety backup
        self.output_main_csv.parent.mkdir(parents=True, exist_ok=True)
        if self.output_main_csv.exists():
            backup_dir = DATA_DIR / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"cars_main_backup_{timestamp_str}.csv"
            shutil.copy2(self.output_main_csv, backup_file)
            logger.info(f"Created backup of previous main catalog at: {backup_file.name}")

        final_df.to_csv(self.output_main_csv, index=False, encoding="utf-8")
        logger.info(f"[SUCCESS] Saved main dataset ({len(final_df)} vehicles) to: {self.output_main_csv}")

        # Optionally update cars_current.csv with automatic backup
        if self.sync_current_csv:
            backup_dir = DATA_DIR / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"cars_current_backup_{timestamp_str}.csv"
            shutil.copy2(self.current_csv, backup_file)
            logger.info(f"Created backup of previous current catalog at: {backup_file.name}")

            # Filter for CURRENT vehicles and export
            current_available_df = final_df[final_df["status"] == "CURRENT"].copy()
            # Standard base columns for backwards compatibility with backend services
            base_cols_only = [
                "brand", "model", "variant", "price", "fuel_type", "transmission",
                "body_type", "engine_cc", "power", "torque", "mileage", "seating",
                "boot_space", "ground_clearance", "safety_rating", "battery_capacity",
                "range_km", "source", "model_url", "variant_url", "status"
            ]
            current_available_df[base_cols_only].to_csv(self.current_csv, index=False, encoding="utf-8")
            logger.info(f"Updated {self.current_csv.name} with all {len(current_available_df)} available vehicles.")

        # Generate metadata report
        metadata = {
            "consolidated_at": datetime.now(timezone.utc).isoformat(),
            "output_file": str(self.output_main_csv.name),
            "total_available_vehicles": len(final_df[final_df["status"] == "CURRENT"]),
            "total_records": len(final_df),
            "base_catalog_records": len(df_curr),
            "new_launches_integrated": len(df_new),
            "records_updated_with_2026_specs": len(updated_keys),
            "brand_new_records_added": len(brand_new_keys),
            "upcoming_records_included": upcoming_count,
            "unique_brands": int(final_df["brand"].nunique()),
            "unique_models": int(final_df["model"].nunique()),
            "price_min": float(final_df["price"].min()),
            "price_max": float(final_df["price"].max()),
            "price_median": float(final_df["price"].median()),
            "fuel_type_breakdown": final_df["fuel_type"].value_counts().to_dict(),
            "transmission_breakdown": final_df["transmission"].value_counts().to_dict(),
            "body_type_breakdown": final_df["body_type"].value_counts().to_dict(),
        }

        with open(METADATA_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved consolidation metadata report to: {METADATA_JSON_PATH.name}")

        self._print_summary(metadata)
        return final_df

    def _print_summary(self, meta: Dict[str, Any]):
        print("\n" + "=" * 65)
        print("CONSOLIDATED MAIN CAR DATASET SUMMARY")
        print("=" * 65)
        print(f"Total Available Cars:     {meta['total_available_vehicles']}")
        print(f"Base Catalog Records:     {meta['base_catalog_records']}")
        print(f"New Launches Integrated:  {meta['new_launches_integrated']}")
        print(f"  - Updated with 2026 Specs: {meta['records_updated_with_2026_specs']}")
        print(f"  - Brand-New Additions:     {meta['brand_new_records_added']}")
        print(f"Unique Brands:            {meta['unique_brands']}")
        print(f"Unique Models:            {meta['unique_models']}")
        print(f"Price Range (INR):        Rs. {meta['price_min']:,.0f} - Rs. {meta['price_max']:,.0f}")
        print(f"Primary Output File:      {self.output_main_csv}")
        print("=" * 65 + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Build AutoAI Main Consolidated Car Dataset")
    parser.add_argument("--current-csv", type=str, default=str(DEFAULT_CURRENT_CSV))
    parser.add_argument("--new-launches-csv", type=str, default=str(DEFAULT_NEW_LAUNCHES_CSV))
    parser.add_argument("--output", type=str, default=str(DEFAULT_MAIN_CSV))
    parser.add_argument("--sync-current", action="store_true", help="Also sync and update cars_current.csv with automatic backup")
    parser.add_argument("--include-upcoming", action="store_true", help="Include upcoming cars in the dataset")
    return parser.parse_args()


def main():
    args = parse_args()
    builder = MainDatasetBuilder(
        current_csv=Path(args.current_csv),
        new_launches_csv=Path(args.new_launches_csv),
        output_main_csv=Path(args.output),
        sync_current_csv=args.sync_current,
        include_upcoming=args.include_upcoming,
    )
    builder.build()


if __name__ == "__main__":
    main()
