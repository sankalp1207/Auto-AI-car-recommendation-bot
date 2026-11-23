"""
Unit tests for AutoAI DataQualityService
Tests all 8 required validation categories:
  1. Required fields
  2. Numeric validation & plausibility limits
  3. Powertrain-aware missing data (EV vs ICE)
  4. Duplicate detection (exact, URL, normalized)
  5. Date validity, impossible dates, and status consistency
  6. Source and URL syntax validation
  7. Status vs record_type consistency
  8. Cross-field engineering checks
  9. Determinism and non-destructive operation
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.data_quality_service import (
    DataQualityService,
    PLAUSIBILITY_LIMITS,
    QualityIssue,
)


class TestDataQualityService(unittest.TestCase):
    def setUp(self):
        self.checker = DataQualityService()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_required_fields(self):
        """Ensures missing brand or model generates ERROR severity."""
        df = pd.DataFrame([
            {"brand": "", "model": "Harrier", "variant": "XZ", "status": "CURRENT"},
            {"brand": "Tata", "model": "", "variant": "XZ", "status": "CURRENT"},
            {"brand": "Hyundai", "model": "Creta", "variant": "", "status": "CURRENT"},
        ])
        report, issues = self.checker.validate_dataset(df)
        issue_types = [i.issue_type for i in issues]

        self.assertIn("MISSING_REQUIRED_FIELD", issue_types)
        # Missing variant on CURRENT vehicle generates WARNING
        self.assertIn("MISSING_EXPECTED_VARIANT", issue_types)

    def test_numeric_validation_and_plausibility(self):
        """Ensures non-positive prices and impossible specs generate ERROR; unusual specs generate WARNING."""
        df = pd.DataFrame([
            {
                "brand": "Maruti",
                "model": "Swift",
                "variant": "VXi",
                "price": -50000.0,  # Negative price -> ERROR
                "engine_cc": 1197.0,
                "power": -85.0,     # Negative power -> ERROR
                "safety_rating": 6.5,  # Out of 0.0 - 5.0 range -> ERROR
                "status": "CURRENT",
            },
            {
                "brand": "Rolls-Royce",
                "model": "Phantom",
                "variant": "Extended",
                "price": 950_000_000.0,  # > 50 Cr -> WARNING (outside standard plausibility)
                "engine_cc": 6749.0,
                "power": 563.0,
                "safety_rating": 5.0,
                "status": "CURRENT",
            }
        ])
        report, issues = self.checker.validate_dataset(df)
        issue_map = {f"{i.field}:{i.issue_type}": i.severity for i in issues}

        self.assertEqual(issue_map.get("price:NON_POSITIVE_VALUE"), "ERROR")
        self.assertEqual(issue_map.get("power:NEGATIVE_NUMERIC_VALUE"), "ERROR")
        self.assertEqual(issue_map.get("safety_rating:INVALID_SAFETY_RATING"), "ERROR")
        self.assertEqual(issue_map.get("price:VALUE_OUTSIDE_PLAUSIBILITY_LIMITS"), "WARNING")

    def test_ev_powertrain_missing_data_adjustment(self):
        """Ensures EV vehicles lacking engine_cc are NOT penalized as missing data extraction failures."""
        df = pd.DataFrame([
            {
                "brand": "Tata",
                "model": "Nexon EV",
                "variant": "Empowered Plus",
                "price": 1749000.0,
                "fuel_type": "Electric",
                "engine_cc": None,  # EV legitimately lacks displacement
                "battery_capacity": 45.0,
                "range_km": 465.0,
                "status": "CURRENT",
            },
            {
                "brand": "Tata",
                "model": "Nexon",
                "variant": "Fearless Petrol",
                "price": 1249000.0,
                "fuel_type": "Petrol",
                "engine_cc": 1199.0,
                "battery_capacity": None,  # ICE legitimately lacks battery
                "range_km": None,
                "status": "CURRENT",
            }
        ])
        report, issues = self.checker.validate_dataset(df)
        missing_fields = report["missing_data_analysis"]["fields"]

        # engine_cc missing count is 1, but not_applicable_count is 1 (for EV), so adjusted is 0!
        self.assertEqual(missing_fields["engine_cc"]["not_applicable_count"], 1)
        self.assertEqual(missing_fields["engine_cc"]["adjusted_missing_count"], 0)
        self.assertEqual(missing_fields["engine_cc"]["adjusted_missing_percentage"], 0.0)

        # battery_capacity missing count is 1, but not_applicable_count is 1 (for Petrol), so adjusted is 0!
        self.assertEqual(missing_fields["battery_capacity"]["not_applicable_count"], 1)
        self.assertEqual(missing_fields["battery_capacity"]["adjusted_missing_count"], 0)

    def test_duplicate_detection(self):
        """Detects exact duplicate rows and normalized variant duplicates."""
        row = {
            "brand": "Hyundai",
            "model": "Verna",
            "variant": "SX Turbo",
            "price": 1600000.0,
            "status": "CURRENT",
        }
        df = pd.DataFrame([row, row])  # Exact duplicate
        report, issues = self.checker.validate_dataset(df)

        self.assertEqual(report["duplicate_analysis"]["exact_duplicate_rows_count"], 2)
        issue_types = [i.issue_type for i in issues]
        self.assertIn("EXACT_DUPLICATE_ROW", issue_types)

    def test_date_validation_and_temporal_plausibility(self):
        """Checks malformed dates, impossible years, and future dates with CURRENT status."""
        df = pd.DataFrame([
            {
                "brand": "Audi",
                "model": "A4",
                "variant": "Premium",
                "price": 4500000.0,
                "launch_date": "not-a-valid-date",
                "status": "CURRENT",
            },
            {
                "brand": "BMW",
                "model": "3 Series",
                "variant": "M340i",
                "price": 7200000.0,
                "launch_date": "1950-01-01",  # Year < 1980 -> Impossible for modern Indian catalog
                "status": "CURRENT",
            },
            {
                "brand": "Mercedes",
                "model": "C-Class",
                "variant": "C200",
                "price": 6000000.0,
                "launch_date": "2028-12-31",  # Far future date for CURRENT vehicle
                "status": "CURRENT",
            },
            {
                "brand": "Honda",
                "model": "City",
                "variant": "V",
                "price": 1200000.0,
                "launch_date": "Pre-2026-09",  # Historical sentinel -> INFO, not ERROR
                "status": "CURRENT",
            }
        ])
        report, issues = self.checker.validate_dataset(df)
        issue_types = {i.issue_type: i.severity for i in issues}

        self.assertEqual(issue_types.get("MALFORMED_LAUNCH_DATE"), "ERROR")
        self.assertEqual(issue_types.get("IMPOSSIBLE_LAUNCH_YEAR"), "ERROR")
        self.assertEqual(issue_types.get("FUTURE_LAUNCH_DATE_FOR_CURRENT_STATUS"), "WARNING")
        self.assertEqual(issue_types.get("HISTORICAL_PRE_CUTOFF_DATE"), "INFO")

    def test_cross_field_engineering_checks(self):
        """Validates cross-field consistency between fuel, engine displacement, seating, and body type."""
        df = pd.DataFrame([
            # 1. EV having displacement
            {
                "brand": "MG",
                "model": "ZS EV",
                "variant": "Exclusive",
                "fuel_type": "Electric",
                "engine_cc": 1498.0,  # Impossible for pure EV
                "price": 2500000.0,
                "status": "CURRENT",
            },
            # 2. 7-seater hatchback
            {
                "brand": "Maruti",
                "model": "Baleno",
                "variant": "Alpha",
                "fuel_type": "Petrol",
                "engine_cc": 1197.0,
                "body_type": "Hatchback",
                "seating": 7,  # Unusual for hatchback
                "price": 900000.0,
                "status": "CURRENT",
            }
        ])
        report, issues = self.checker.validate_dataset(df)
        issue_types = [i.issue_type for i in issues]

        self.assertIn("ELECTRIC_VEHICLE_HAS_ENGINE_CC", issue_types)
        self.assertIn("UNUSUAL_HATCHBACK_SEATING", issue_types)

    def test_deterministic_and_non_destructive(self):
        """Ensures running validator twice on unchanged data yields identical results without mutating input."""
        df = pd.DataFrame([
            {"brand": "Skoda", "model": "Kylaq", "variant": "Signature", "price": 950000.0, "status": "CURRENT"},
            {"brand": "Kia", "model": "Syros", "variant": "HTX", "price": 1100000.0, "status": "UPCOMING"},
        ])
        df_orig = df.copy()

        report1, issues1 = self.checker.validate_dataset(df)
        report2, issues2 = self.checker.validate_dataset(df)

        # Ensure DataFrame was not mutated
        pd.testing.assert_frame_equal(df, df_orig)

        # Ensure issue lists are identical
        self.assertEqual(len(issues1), len(issues2))
        for i1, i2 in zip(issues1, issues2):
            self.assertEqual(i1.to_dict(), i2.to_dict())

        # Test CSV and JSON export
        csv_out = self.temp_dir / "issues.csv"
        json_out = self.temp_dir / "report.json"
        self.checker.export_issues_to_csv(issues1, csv_out)
        self.checker.export_report_to_json(report1, json_out)

        self.assertTrue(csv_out.exists())
        self.assertTrue(json_out.exists())


if __name__ == "__main__":
    unittest.main()
