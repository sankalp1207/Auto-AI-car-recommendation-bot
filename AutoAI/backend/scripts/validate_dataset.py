"""
AutoAI Dataset Pre-Import Validator
Single command to validate CSV datasets prior to database import.

Usage:
  python backend/scripts/validate_dataset.py
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Any
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CURRENT_CSV = DATA_DIR / "cars_current.csv"
UPCOMING_CSV = DATA_DIR / "cars_upcoming.csv"
ARCHIVE_CSV = DATA_DIR / "cars_archive.csv"
FULL_CSV = DATA_DIR / "cars_india_full.csv"

VALID_STATUSES = {"CURRENT", "UPCOMING", "DISCONTINUED"}
VALID_FUELS = {"Petrol", "Diesel", "Electric", "CNG", "Hybrid", "Plug-in Hybrid", "LPG", "Hydrogen"}


def validate_file(csv_path: Path, expected_status: str = None) -> Dict[str, Any]:
    issues = []
    if not csv_path.exists():
        return {"file": csv_path.name, "exists": False, "rows": 0, "issues": [f"File not found: {csv_path}"]}

    df = pd.read_csv(csv_path)
    total_rows = len(df)

    if total_rows == 0:
        # If it's the archive file, 0 rows is acceptable if no discontinued cars exist
        if expected_status == "DISCONTINUED":
            return {"file": csv_path.name, "exists": True, "rows": 0, "issues": [], "unique_brands": 0, "unique_models": 0}
        return {"file": csv_path.name, "exists": True, "rows": 0, "issues": ["File is empty"]}

    # 1. Check required columns
    required_cols = ["brand", "model", "variant", "price", "fuel_type", "transmission", "body_type", "status", "source", "model_url"]
    for col in required_cols:
        if col not in df.columns:
            issues.append(f"Missing required column: '{col}'")

    # 2. Check empty brand or model
    empty_brand = df["brand"].isna() | (df["brand"].astype(str).str.strip() == "")
    if empty_brand.any():
        issues.append(f"{empty_brand.sum()} rows have empty 'brand'")

    empty_model = df["model"].isna() | (df["model"].astype(str).str.strip() == "")
    if empty_model.any():
        issues.append(f"{empty_model.sum()} rows have empty 'model'")

    # 3. Check duplicates
    df["_key"] = df["brand"].astype(str).str.strip() + "|" + df["model"].astype(str).str.strip() + "|" + df["variant"].fillna("").astype(str).str.strip()
    dup_count = df.duplicated(subset=["_key"]).sum()
    if dup_count > 0:
        issues.append(f"{dup_count} duplicate records (brand + model + variant)")

    # 4. Check status values
    if "status" in df.columns:
        invalid_status = ~df["status"].isin(VALID_STATUSES)
        if invalid_status.any():
            issues.append(f"{invalid_status.sum()} rows with invalid status values")
        if expected_status:
            mismatched = df["status"] != expected_status
            if mismatched.any():
                issues.append(f"{mismatched.sum()} rows with status != '{expected_status}' in {csv_path.name}")

    # 5. Check numeric fields for impossible negative values
    numeric_cols = ["price", "engine_cc", "power", "torque", "mileage", "seating", "boot_space", "ground_clearance", "safety_rating", "battery_capacity", "range_km"]
    for ncol in numeric_cols:
        if ncol in df.columns:
            numeric_vals = pd.to_numeric(df[ncol], errors="coerce")
            negatives = numeric_vals < 0
            if negatives.any():
                issues.append(f"{negatives.sum()} negative values in '{ncol}'")

    # 6. Check safety rating range (0 to 5)
    if "safety_rating" in df.columns:
        safety_vals = pd.to_numeric(df["safety_rating"], errors="coerce")
        out_of_range = (safety_vals < 0) | (safety_vals > 5)
        if out_of_range.any():
            issues.append(f"{out_of_range.sum()} safety ratings outside 0.0 - 5.0 range")

    # 7. Check URLs
    if "model_url" in df.columns:
        non_empty_urls = df["model_url"].dropna().astype(str).str.strip()
        malformed = ~non_empty_urls.str.startswith("http")
        if malformed.any():
            issues.append(f"{malformed.sum()} malformed URLs in 'model_url'")

    # 8. Check source attribution
    if "source" in df.columns:
        missing_source = df["source"].isna() | (df["source"].astype(str).str.strip() == "")
        if missing_source.any():
            issues.append(f"{missing_source.sum()} rows missing 'source' attribution")

    return {
        "file": csv_path.name,
        "exists": True,
        "rows": total_rows,
        "issues": issues,
        "unique_brands": df["brand"].nunique() if "brand" in df.columns else 0,
        "unique_models": df["model"].nunique() if "model" in df.columns else 0,
    }


def main():
    print("=" * 65)
    print("AUTOAI DATASET PRE-IMPORT VALIDATOR")
    print("=" * 65)

    all_passed = True
    files_to_check = [
        (FULL_CSV, None),
        (CURRENT_CSV, "CURRENT"),
        (UPCOMING_CSV, "UPCOMING"),
        (ARCHIVE_CSV, "DISCONTINUED"),
    ]

    for path, expected_st in files_to_check:
        res = validate_file(path, expected_st)
        status_label = "[PASS]" if not res["issues"] else "[FAIL]"
        if res["issues"]:
            all_passed = False
        print(f"\n{status_label} {res['file']}")
        print(f"       Rows: {res['rows']} | Brands: {res.get('unique_brands', 0)} | Models: {res.get('unique_models', 0)}")
        if res["issues"]:
            print("       Issues Found:")
            for issue in res["issues"]:
                print(f"         - {issue}")
        else:
            print("       All integrity checks passed cleanly.")

    print("\n" + "=" * 65)
    if all_passed:
        print("OVERALL VALIDATION RESULT: [PASS] All datasets are ready for import.")
    else:
        print("OVERALL VALIDATION RESULT: [FAIL] Issues detected. Please review above.")
    print("=" * 65)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
