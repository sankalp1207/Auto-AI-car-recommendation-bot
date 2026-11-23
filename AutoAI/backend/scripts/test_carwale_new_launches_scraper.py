"""
AutoAI Incremental Car Launch Scraper Test Suite
Validates:
  1. Normalization (brands, fuels, transmissions, body types, numbers, dates)
  2. Classification & Deduplication (NEW_MODEL, NEW_VARIANT, FACELIFT, SPECIAL_EDITION, UPCOMING, EXISTING)
  3. Validation & Data Quality Reporting
  4. Missing values preservation (no fabricated data)
  5. Safety & Immutability of existing catalogs
  6. Atomic writing and output file integrity
"""

from datetime import datetime, timezone
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.scrapers.carwale_new_launches_scraper import (
    ALL_COLUMNS,
    BASE_COLUMNS,
    TRACKING_COLUMNS,
    RECORD_TYPE_NEW_MODEL,
    RECORD_TYPE_NEW_VARIANT,
    RECORD_TYPE_FACELIFT,
    RECORD_TYPE_SPECIAL_EDITION,
    RECORD_TYPE_UPCOMING,
    RECORD_TYPE_ANNOUNCED,
    RECORD_TYPE_EXISTING,
    CarWaleIncrementalScraper,
    CatalogDeduplicator,
    normalize_brand_name,
    normalize_model_name,
    normalize_variant_name,
    normalize_fuel_type,
    normalize_transmission,
    normalize_body_type,
    parse_numeric,
    parse_carwale_date,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def get_file_hash(path: Path) -> str:
    """Computes SHA256 hash of a file."""
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestCarWaleNormalization(unittest.TestCase):
    """Tests data normalization rules."""

    def test_brand_normalization(self):
        self.assertEqual(normalize_brand_name("tata"), "Tata Motors")
        self.assertEqual(normalize_brand_name("Tata Motors"), "Tata Motors")
        self.assertEqual(normalize_brand_name("mg"), "MG Motor")
        self.assertEqual(normalize_brand_name("maruti"), "Maruti Suzuki")
        self.assertEqual(normalize_brand_name("mercedes"), "Mercedes-Benz")
        self.assertEqual(normalize_brand_name("citroen"), "Citroën")
        self.assertEqual(normalize_brand_name(None), "Unknown")

    def test_model_and_variant_normalization(self):
        self.assertEqual(normalize_model_name("  Glanza   Facelift  "), "Glanza Facelift")
        self.assertEqual(normalize_model_name(None), "")
        self.assertEqual(normalize_variant_name("  E   Petrol Manual "), "E Petrol Manual")
        self.assertEqual(normalize_variant_name(None), None)
        self.assertEqual(normalize_variant_name("nan"), None)

    def test_fuel_type_normalization(self):
        self.assertEqual(normalize_fuel_type("petrol"), "Petrol")
        self.assertEqual(normalize_fuel_type("DIESEL"), "Diesel")
        self.assertEqual(normalize_fuel_type("cng"), "CNG")
        self.assertEqual(normalize_fuel_type("Electric Vehicle"), "Electric")
        self.assertEqual(normalize_fuel_type("Strong Hybrid"), "Hybrid")
        self.assertEqual(normalize_fuel_type("Plug-in Hybrid"), "Plug-in Hybrid")
        self.assertIsNone(normalize_fuel_type(None))
        self.assertIsNone(normalize_fuel_type(""))

    def test_transmission_normalization(self):
        self.assertEqual(normalize_transmission("manual"), "Manual")
        self.assertEqual(normalize_transmission("Automatic (AMT)"), "Automatic (AMT)")
        self.assertEqual(normalize_transmission("amt"), "Automatic (AMT)")
        self.assertEqual(normalize_transmission("ags"), "Automatic (AMT)")
        self.assertEqual(normalize_transmission("cvt"), "Automatic (CVT)")
        self.assertEqual(normalize_transmission("dct"), "Automatic (DCT)")
        self.assertEqual(normalize_transmission("dsg"), "Automatic (DCT)")
        self.assertEqual(normalize_transmission("Automatic"), "Automatic")
        self.assertIsNone(normalize_transmission(None))

    def test_body_type_normalization(self):
        self.assertEqual(normalize_body_type("compact suv"), "SUV")
        self.assertEqual(normalize_body_type("sedan"), "Sedan")
        self.assertEqual(normalize_body_type("hatchback"), "Hatchback")
        self.assertEqual(normalize_body_type("mpv"), "MUV")
        self.assertIsNone(normalize_body_type(None))

    def test_numeric_parsing(self):
        self.assertEqual(parse_numeric("1197 cc"), 1197.0)
        self.assertEqual(parse_numeric("23.8 kmpl"), 23.8)
        self.assertEqual(parse_numeric("5,199,000"), 5199000.0)
        self.assertEqual(parse_numeric("Rs. 51.99 Lakh"), 51.99)
        self.assertIsNone(parse_numeric(None))
        self.assertIsNone(parse_numeric(""))
        self.assertIsNone(parse_numeric("unknown"))

    def test_date_parsing(self):
        d1 = parse_carwale_date("10/16/2026 00:00:00")
        self.assertIsNotNone(d1)
        self.assertEqual(d1.year, 2026)
        self.assertEqual(d1.month, 10)
        self.assertEqual(d1.day, 16)

        d2 = parse_carwale_date("September 25, 2026, 12:00 PM")
        self.assertIsNotNone(d2)
        self.assertEqual(d2.month, 9)
        self.assertEqual(d2.day, 25)

        base_now = datetime(2026, 10, 18, 12, 0, 0)
        d3 = parse_carwale_date("2 days ago", base_time=base_now)
        self.assertIsNotNone(d3)
        self.assertEqual(d3.day, 16)

        self.assertIsNone(parse_carwale_date(None))
        self.assertIsNone(parse_carwale_date("invalid_date_format"))


class TestCatalogDeduplicationAndClassification(unittest.TestCase):
    """Tests catalog deduplication, classification and matching against active catalog."""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = BASE_DIR / "backend" / "data"
        cls.ml_data_dir = BASE_DIR / "backend" / "ml" / "data"
        cls.dedup = CatalogDeduplicator(cls.data_dir, cls.ml_data_dir)
        cls.cutoff_date = datetime(2026, 9, 5, 0, 53, 57)

    def test_new_model_detection(self):
        # Tata Aeris was not in the 2026-09-05 catalog
        # Test a genuinely new model not in catalog
        rec_type, reason, is_new = self.dedup.classify_and_deduplicate(
            brand="VinFast",
            model="VF6",
            variant="Standard Eco",
            launch_date=datetime(2026, 10, 1),
            cutoff_date=self.cutoff_date,
            status="CURRENT",
        )
        self.assertEqual(rec_type, RECORD_TYPE_NEW_MODEL)
        self.assertTrue(is_new)

    def test_new_variant_detection(self):
        # Mahindra XUV 3XO is in catalog, but a new variant e.g. "MX3 Pro CNG" is newly launched
        rec_type, reason, is_new = self.dedup.classify_and_deduplicate(
            brand="Mahindra",
            model="XUV 3XO",
            variant="MX3 Pro CNG Manual Special",
            launch_date=datetime(2026, 10, 15),
            cutoff_date=self.cutoff_date,
            status="CURRENT",
        )
        self.assertEqual(rec_type, RECORD_TYPE_NEW_VARIANT)
        self.assertTrue(is_new)

    def test_existing_record_exclusion(self):
        # Aston Martin Vantage V8 exists in cars_current.csv with launch prior to cutoff
        rec_type, reason, is_new = self.dedup.classify_and_deduplicate(
            brand="Aston Martin",
            model="Vantage",
            variant="V8",
            launch_date=datetime(2024, 1, 1),
            cutoff_date=self.cutoff_date,
            status="CURRENT",
        )
        self.assertEqual(rec_type, RECORD_TYPE_EXISTING)
        self.assertFalse(is_new)

    def test_facelift_classification(self):
        rec_type, reason, is_new = self.dedup.classify_and_deduplicate(
            brand="Toyota",
            model="Glanza",
            variant="E Petrol Manual",
            launch_date=datetime(2026, 10, 14),
            cutoff_date=self.cutoff_date,
            status="CURRENT",
            is_facelift=True,
            article_title="Toyota Glanza Facelift Launched: Base Variant Detailed",
        )
        self.assertEqual(rec_type, RECORD_TYPE_FACELIFT)
        self.assertTrue(is_new)

    def test_special_edition_classification(self):
        rec_type, reason, is_new = self.dedup.classify_and_deduplicate(
            brand="MINI",
            model="Cooper",
            variant="Oxford Edition",
            launch_date=datetime(2026, 10, 16),
            cutoff_date=self.cutoff_date,
            status="CURRENT",
            is_special_edition=True,
            article_title="Mini Cooper Oxford Edition Launched in India at Rs. 55.50 Lakh",
        )
        self.assertEqual(rec_type, RECORD_TYPE_SPECIAL_EDITION)
        self.assertTrue(is_new)

    def test_upcoming_and_announced_exclusion(self):
        # Upcoming car must be excluded from launched dataset
        rec_type_up, _, is_new_up = self.dedup.classify_and_deduplicate(
            brand="Audi",
            model="Q9",
            variant="Base",
            launch_date=None,
            cutoff_date=self.cutoff_date,
            status="UPCOMING",
        )
        self.assertEqual(rec_type_up, RECORD_TYPE_UPCOMING)
        self.assertFalse(is_new_up)

        # Unveiled car must be excluded from launched dataset
        rec_type_an, _, is_new_an = self.dedup.classify_and_deduplicate(
            brand="Ferrari",
            model="Luce",
            variant=None,
            launch_date=None,
            cutoff_date=self.cutoff_date,
            status="CURRENT",
            article_title="Ferrari Luce Officially Unveiled in India",
        )
        self.assertEqual(rec_type_an, RECORD_TYPE_ANNOUNCED)
        self.assertFalse(is_new_an)


class TestDataQualityAndValidation(unittest.TestCase):
    """Tests data validation rules, missing fields preservation, and reporting."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.scraper = CarWaleIncrementalScraper(
            base_dir=BASE_DIR,
            output_dir=self.temp_dir,
            dry_run=False,
            max_pages=1,
            max_articles=1,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_optional_specs_preserved(self):
        """Ensures missing optional specifications are preserved as None/empty, never fabricated."""
        sample_record = {
            "brand": "Tata Motors",
            "model": "Aeris",
            "variant": "Smart Petrol Manual",
            "price": 529990.0,
            "fuel_type": "Petrol",
            "transmission": "Manual",
            "body_type": "Hatchback",
            "engine_cc": 1199.0,
            "power": 85.0,
            "torque": 113.0,
            "mileage": 19.2,
            "seating": 5.0,
            "boot_space": None,       # Unreported in specsSummary
            "ground_clearance": None, # Unreported
            "safety_rating": None,    # No crash test published yet
            "battery_capacity": None, # Non-EV
            "range_km": None,
            "status": "CURRENT",
            "source": "carwale.com",
            "model_url": "https://www.carwale.com/tata-cars/aeris/",
            "variant_url": "https://www.carwale.com/tata-cars/aeris/smart-petrol-manual/",
            "launch_date": "2026-09-25",
            "launch_date_type": "EXACT_DATE",
            "launch_evidence_url": "https://www.carwale.com/new-car-launches/",
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "source_last_verified_at": datetime.now(timezone.utc).isoformat(),
            "record_type": RECORD_TYPE_NEW_MODEL,
            "data_quality_status": "VALID",
        }

        self.scraper.validated_records.append(sample_record)
        self.scraper.raw_records.append(sample_record)

        report = self.scraper._generate_data_quality_report()
        self.assertEqual(report["total_validated_records"], 1)
        self.assertEqual(report["missing_values_by_field"]["boot_space"], 1)
        self.assertEqual(report["missing_values_by_field"]["safety_rating"], 1)
        self.assertEqual(report["missing_values_by_field"]["battery_capacity"], 1)
        self.assertEqual(report["invalid_prices"], 0)

        # Write artifacts to temporary dir and verify CSV output
        self.scraper._save_artifacts(report)

        val_csv = self.temp_dir / "cars_new_launches.csv"
        self.assertTrue(val_csv.exists())
        df = pd.read_csv(val_csv)
        self.assertEqual(len(df), 1)
        # Verify optional fields are NaN / missing, not fabricated
        self.assertTrue(pd.isna(df.loc[0, "boot_space"]))
        self.assertTrue(pd.isna(df.loc[0, "safety_rating"]))
        self.assertEqual(df.loc[0, "price"], 529990.0)
        self.assertEqual(df.loc[0, "launch_date"], "2026-09-25")

    def test_non_positive_price_flagged(self):
        """Ensures vehicles with zero or negative price are flagged for manual review."""
        sample = {
            "brand": "Demo",
            "model": "Car",
            "variant": "Base",
            "price": 0.0,
            "launch_date": "2026-10-01",
            "launch_evidence_url": "https://www.carwale.com",
            "data_quality_status": "NEEDS_MANUAL_REVIEW",
            "record_type": RECORD_TYPE_NEW_MODEL,
        }
        self.scraper.validated_records.append(sample)
        report = self.scraper._generate_data_quality_report()
        self.assertGreaterEqual(report["invalid_prices"], 1)
        self.assertGreaterEqual(report["records_requiring_manual_review"], 1)


class TestCatalogImmutability(unittest.TestCase):
    """Ensures existing datasets are NEVER modified or deleted."""

    def test_existing_catalog_hashes_remain_identical(self):
        data_dir = BASE_DIR / "backend" / "data"
        ml_data_dir = BASE_DIR / "backend" / "ml" / "data"

        files_to_check = [
            data_dir / "cars_current.csv",
            data_dir / "cars_upcoming.csv",
            data_dir / "cars_india_full.csv",
            data_dir / "cars_carwale_raw.csv",
            data_dir / "cars_archive.csv",
            ml_data_dir / "cars_ml_clean.csv",
            ml_data_dir / "cars_ml_raw.csv",
        ]

        initial_hashes = {}
        for p in files_to_check:
            if p.exists():
                initial_hashes[p] = get_file_hash(p)

        # Run deduplicator and scraper initialization
        dedup = CatalogDeduplicator(data_dir, ml_data_dir)
        temp_dir = Path(tempfile.mkdtemp())
        try:
            scraper = CarWaleIncrementalScraper(
                base_dir=BASE_DIR,
                output_dir=temp_dir,
                dry_run=True,
            )
            self.assertIsNotNone(scraper.cutoff_date)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Verify hashes
        for p, orig_hash in initial_hashes.items():
            current_hash = get_file_hash(p)
            self.assertEqual(
                orig_hash, current_hash,
                f"CRITICAL VIOLATION: Existing catalog file {p.name} was modified!"
            )


if __name__ == "__main__":
    unittest.main()
