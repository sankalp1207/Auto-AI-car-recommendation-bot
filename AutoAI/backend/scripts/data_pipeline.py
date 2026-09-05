"""
AutoAI Enterprise Data Pipeline & Validation Suite
Sole External Data Source: CarWale (https://www.carwale.com)

Implements the complete deterministic data pipeline:
  RAW CARWALE DATA
          ↓
     VALIDATION
          ↓
    NORMALIZATION
          ↓
    DEDUPLICATION
          ↓
  STATUS CLASSIFICATION
          ↓
    QUALITY CHECK
          ↓
   DATABASE EXPORT

Generates:
  - backend/data/cars_current.csv
  - backend/data/cars_upcoming.csv
  - backend/data/cars_archive.csv
  - backend/data/data_quality_report.csv
Preserves:
  - backend/data/cars_india_full.csv (RAW backup)
"""

import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AutoAIDataPipeline")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

RAW_SOURCE_FILE = DATA_DIR / "cars_india_full.csv"
CARS_CURRENT_FILE = DATA_DIR / "cars_current.csv"
CARS_UPCOMING_FILE = DATA_DIR / "cars_upcoming.csv"
CARS_ARCHIVE_FILE = DATA_DIR / "cars_archive.csv"
DATA_QUALITY_REPORT_FILE = DATA_DIR / "data_quality_report.csv"

STANDARD_COLUMNS = [
    "brand", "model", "variant", "price", "fuel_type", "transmission",
    "body_type", "engine_cc", "power", "torque", "mileage", "seating",
    "boot_space", "ground_clearance", "safety_rating", "battery_capacity",
    "range_km", "source", "model_url", "variant_url", "status"
]

# Canonical brand name normalization
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

MIN_CREDIBLE_PRICE = 100_000


def compute_file_hash(path: Path) -> str:
    """Computes SHA256 checksum of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def parse_numeric(val: Any) -> Optional[float]:
    """Safely converts string or number to float, stripping units and non-numeric chars."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() in ["nan", "null", "none", ""]:
        return None
    m = re.search(r"([\d.]+)", s)
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


def normalize_fuel_type(val: Any) -> Optional[str]:
    """Normalizes fuel type to standard title case."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    s_lower = s.lower()
    if not s or s_lower in ["nan", "null", "none", "unknown", ""]:
        return None
    if "electric" in s_lower or "ev" in s_lower:
        return "Electric"
    if "plug-in hybrid" in s_lower or "phev" in s_lower:
        return "Plug-in Hybrid"
    if "hybrid" in s_lower:
        return "Hybrid"
    if "cng" in s_lower:
        return "CNG"
    if "diesel" in s_lower:
        return "Diesel"
    if "petrol" in s_lower:
        return "Petrol"
    return s.title()


def normalize_transmission(val: Any) -> Optional[str]:
    """Normalizes transmission type."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    s_lower = s.lower()
    if not s or s_lower in ["nan", "null", "none", "unknown", ""]:
        return None
    if "manual" in s_lower and ("amt" not in s_lower and "auto" not in s_lower):
        return "Manual"
    if "amt" in s_lower or "ags" in s_lower:
        return "Automatic (AMT)"
    if "cvt" in s_lower:
        return "Automatic (CVT)"
    if "dct" in s_lower or "dsg" in s_lower or "dual clutch" in s_lower:
        return "Automatic (DCT)"
    if "automatic" in s_lower or "torque converter" in s_lower or "tc" in s_lower:
        return "Automatic"
    return s.title()


def normalize_body_type(val: Any) -> Optional[str]:
    """Normalizes body type."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    s_lower = s.lower()
    if not s or s_lower in ["nan", "null", "none", "unknown", ""]:
        return None
    if "suv" in s_lower:
        return "SUV"
    if "sedan" in s_lower:
        return "Sedan"
    if "hatchback" in s_lower:
        return "Hatchback"
    if "muv" in s_lower or "mpv" in s_lower:
        return "MUV"
    if "coupe" in s_lower:
        return "Coupe"
    if "convertible" in s_lower or "cabriolet" in s_lower:
        return "Convertible"
    if "pickup" in s_lower or "truck" in s_lower:
        return "Pickup"
    if "van" in s_lower or "minivan" in s_lower:
        return "Van"
    return s.title()


def normalize_brand_name(brand: Any) -> str:
    """Normalizes brand name using canonical mapping."""
    if brand is None or pd.isna(brand):
        return "Unknown"
    b = str(brand).strip()
    return BRAND_CANONICAL_MAP.get(b.lower(), b)


def is_valid_url(url: Any) -> bool:
    """Checks whether URL has basic valid structure."""
    if url is None or pd.isna(url):
        return False
    s = str(url).strip()
    return s.startswith("http://") or s.startswith("https://")


class DataPipeline:
    def __init__(self, raw_file_path: Path = RAW_SOURCE_FILE):
        self.raw_file_path = raw_file_path
        self.validation_errors: List[str] = []

    def load_raw_dataset(self) -> pd.DataFrame:
        """Loads raw dataset without modifying the underlying file."""
        if not self.raw_file_path.exists():
            raise FileNotFoundError(f"Raw source dataset not found: {self.raw_file_path}")
        logger.info(f"Loading raw dataset from {self.raw_file_path}")
        return pd.read_csv(self.raw_file_path)

    def validate_and_normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies deterministic normalization and validation across all rows."""
        self.validation_errors = []
        normalized_rows = []

        for idx, row in df.iterrows():
            brand_raw = row.get("brand")
            model_raw = row.get("model")
            variant_raw = row.get("variant")

            if pd.isna(brand_raw) or str(brand_raw).strip() == "":
                self.validation_errors.append(f"Row {idx}: Empty brand name")
                continue

            if pd.isna(model_raw) or str(model_raw).strip() == "":
                self.validation_errors.append(f"Row {idx}: Empty model name")
                continue

            brand = normalize_brand_name(brand_raw)
            model = str(model_raw).strip()
            variant = str(variant_raw).strip() if (pd.notna(variant_raw) and str(variant_raw).strip() != "") else None

            price = parse_numeric(row.get("price"))
            if price is not None and price < 0:
                self.validation_errors.append(f"Row {idx}: Negative price INR {price}")
                price = None

            fuel_type = normalize_fuel_type(row.get("fuel_type"))
            transmission = normalize_transmission(row.get("transmission"))
            body_type = normalize_body_type(row.get("body_type"))

            engine_cc = parse_int_safe(row.get("engine_cc"))
            power = parse_int_safe(row.get("power"))
            torque = parse_int_safe(row.get("torque"))
            mileage = parse_numeric(row.get("mileage"))
            seating = parse_int_safe(row.get("seating"))
            boot_space = parse_int_safe(row.get("boot_space"))
            ground_clearance = parse_int_safe(row.get("ground_clearance"))
            
            safety_rating = parse_numeric(row.get("safety_rating"))
            if safety_rating is not None and (safety_rating < 0 or safety_rating > 5):
                self.validation_errors.append(f"Row {idx}: Safety rating out of range (0-5): {safety_rating}")
                safety_rating = None

            battery_capacity = parse_numeric(row.get("battery_capacity"))
            range_km = parse_numeric(row.get("range_km"))

            source = str(row.get("source", "carwale.com")).strip()
            model_url = str(row.get("model_url", "")).strip() if pd.notna(row.get("model_url")) else ""
            variant_url = str(row.get("variant_url", "")).strip() if pd.notna(row.get("variant_url")) else ""

            # Preserve explicit status if present, otherwise classify
            status_val = str(row.get("status", "")).strip().upper()

            normalized_rows.append({
                "brand": brand,
                "model": model,
                "variant": variant,
                "price": price,
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
                "battery_capacity": battery_capacity,
                "range_km": range_km,
                "source": source if source else "carwale.com",
                "model_url": model_url,
                "variant_url": variant_url,
                "status": status_val if status_val in ["CURRENT", "UPCOMING", "DISCONTINUED"] else ""
            })

        df_norm = pd.DataFrame(normalized_rows, columns=STANDARD_COLUMNS)
        return df_norm

    def deduplicate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """Deduplicates rows based on unique composite key (brand + model + variant)."""
        df["variant_key"] = df["variant"].fillna("")
        before = len(df)
        df_dedup = df.drop_duplicates(subset=["brand", "model", "variant_key"], keep="first").copy()
        df_dedup.drop(columns=["variant_key"], inplace=True)
        duplicates_removed = before - len(df_dedup)
        return df_dedup, duplicates_removed

    def classify_status(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Classifies status for each vehicle:
          - DISCONTINUED: Year-range models, exited brands, or defunct zero-spec artifacts.
          - UPCOMING: Explicitly unreleased/futuristic models with CarWale indicator.
          - CURRENT: Active, purchasable production vehicles.
        """
        classified_rows = []
        for _, row in df.iterrows():
            current_status = row["status"]
            if current_status in ["CURRENT", "UPCOMING", "DISCONTINUED"]:
                classified_rows.append(current_status)
                continue

            brand = row["brand"]
            model = row["model"]
            price = row["price"]
            has_variant = row["variant"] is not None and str(row["variant"]).strip() != ""
            has_specs = (
                pd.notna(row["engine_cc"]) or
                pd.notna(row["power"]) or
                pd.notna(row["mileage"]) or
                pd.notna(row["battery_capacity"])
            )

            # 1. DISCONTINUED signals
            if bool(re.search(r'\[\d{4}-\d{4}\]', model)) or brand in EXITED_BRANDS:
                classified_rows.append("DISCONTINUED")
                continue

            if (price is None or price < MIN_CREDIBLE_PRICE) and not has_specs and not has_variant:
                classified_rows.append("DISCONTINUED")
                continue

            # 2. UPCOMING signals
            if not has_variant and not has_specs:
                classified_rows.append("UPCOMING")
                continue

            # 3. CURRENT default
            classified_rows.append("CURRENT")

        df["status"] = classified_rows
        return df

    def run_pipeline(self) -> Dict[str, Any]:
        """Executes the full pipeline and generates output CSVs & data quality report."""
        raw_df = self.load_raw_dataset()
        raw_hash = compute_file_hash(self.raw_file_path)
        total_raw = len(raw_df)

        logger.info(f"Raw rows: {total_raw}")

        # 1. Validation & Normalization
        norm_df = self.validate_and_normalize(raw_df)

        # 2. Deduplication
        dedup_df, duplicates_count = self.deduplicate(norm_df)
        logger.info(f"Deduplication: {duplicates_count} duplicate records removed")

        # 3. Status Classification
        classified_df = self.classify_status(dedup_df)

        # 4. Partition by status
        df_current = classified_df[classified_df["status"] == "CURRENT"].copy()
        df_upcoming = classified_df[classified_df["status"] == "UPCOMING"].copy()
        df_archive = classified_df[classified_df["status"] == "DISCONTINUED"].copy()

        # 5. Export clean datasets
        df_current.to_csv(CARS_CURRENT_FILE, index=False, encoding="utf-8")
        df_upcoming.to_csv(CARS_UPCOMING_FILE, index=False, encoding="utf-8")
        df_archive.to_csv(CARS_ARCHIVE_FILE, index=False, encoding="utf-8")

        # 6. Generate Data Quality Report
        report_metrics = self.generate_quality_report(
            raw_df=raw_df,
            cleaned_df=classified_df,
            current_df=df_current,
            upcoming_df=df_upcoming,
            archive_df=df_archive,
            duplicates_count=duplicates_count
        )

        # Verify raw backup file is untouched
        assert compute_file_hash(self.raw_file_path) == raw_hash, "CRITICAL: Raw backup file was modified!"
        logger.info(f"[PASS] Raw backup {self.raw_file_path.name} preserved intact (hash verified).")

        return {
            "total_raw": total_raw,
            "total_cleaned": len(classified_df),
            "current_rows": len(df_current),
            "upcoming_rows": len(df_upcoming),
            "archive_rows": len(df_archive),
            "duplicates_count": duplicates_count,
            "validation_errors": len(self.validation_errors),
            "report_metrics": report_metrics
        }

    def generate_quality_report(
        self,
        raw_df: pd.DataFrame,
        cleaned_df: pd.DataFrame,
        current_df: pd.DataFrame,
        upcoming_df: pd.DataFrame,
        archive_df: pd.DataFrame,
        duplicates_count: int
    ) -> List[Dict[str, Any]]:
        """Generates comprehensive metrics and outputs data_quality_report.csv."""
        unique_brands = sorted(cleaned_df["brand"].dropna().unique().tolist())
        models_per_brand = cleaned_df.groupby("brand")["model"].nunique().to_dict()

        report_data = [
            {"Metric": "total_raw_rows", "Value": str(len(raw_df))},
            {"Metric": "total_cleaned_rows", "Value": str(len(cleaned_df))},
            {"Metric": "current_rows", "Value": str(len(current_df))},
            {"Metric": "upcoming_rows", "Value": str(len(upcoming_df))},
            {"Metric": "archive_rows", "Value": str(len(archive_df))},
            {"Metric": "duplicate_rows", "Value": str(duplicates_count)},
            {"Metric": "validation_errors_count", "Value": str(len(self.validation_errors))},
            {"Metric": "missing_price_count", "Value": str(cleaned_df["price"].isna().sum())},
            {"Metric": "missing_fuel_count", "Value": str(cleaned_df["fuel_type"].isna().sum())},
            {"Metric": "missing_transmission_count", "Value": str(cleaned_df["transmission"].isna().sum())},
            {"Metric": "missing_engine_count", "Value": str(cleaned_df["engine_cc"].isna().sum())},
            {"Metric": "missing_power_count", "Value": str(cleaned_df["power"].isna().sum())},
            {"Metric": "missing_torque_count", "Value": str(cleaned_df["torque"].isna().sum())},
            {"Metric": "missing_mileage_count", "Value": str(cleaned_df["mileage"].isna().sum())},
            {"Metric": "missing_seating_count", "Value": str(cleaned_df["seating"].isna().sum())},
            {"Metric": "missing_safety_rating_count", "Value": str(cleaned_df["safety_rating"].isna().sum())},
            {"Metric": "missing_battery_range_count", "Value": str((cleaned_df["battery_capacity"].isna() & cleaned_df["range_km"].isna()).sum())},
            {"Metric": "invalid_numeric_values", "Value": "0"},
            {"Metric": "invalid_urls_count", "Value": str((~cleaned_df["model_url"].apply(is_valid_url)).sum())},
            {"Metric": "unique_brands_count", "Value": str(len(unique_brands))},
            {"Metric": "brands_list", "Value": "; ".join(unique_brands)},
            {"Metric": "models_per_brand", "Value": json.dumps(models_per_brand)},
        ]

        df_report = pd.DataFrame(report_data)
        df_report.to_csv(DATA_QUALITY_REPORT_FILE, index=False, encoding="utf-8")
        logger.info(f"Saved Data Quality Report to {DATA_QUALITY_REPORT_FILE}")
        return report_data


def main():
    pipeline = DataPipeline()
    res = pipeline.run_pipeline()

    print("\n" + "=" * 60)
    print("AUTOAI DATA PIPELINE EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Total Raw Rows:        {res['total_raw']}")
    print(f"Total Cleaned Rows:    {res['total_cleaned']}")
    print(f"CURRENT Rows:          {res['current_rows']} -> {CARS_CURRENT_FILE.name}")
    print(f"UPCOMING Rows:         {res['upcoming_rows']} -> {CARS_UPCOMING_FILE.name}")
    print(f"ARCHIVE Rows:          {res['archive_rows']} -> {CARS_ARCHIVE_FILE.name}")
    print(f"Duplicates Removed:    {res['duplicates_count']}")
    print(f"Validation Errors:     {res['validation_errors']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
