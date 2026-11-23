"""
AutoAI Automated Car Dataset Quality Validator CLI
Validates vehicle catalog data or new launch datasets without mutating source files.

Usage examples:
  # Validate newly scraped launch dataset
  python backend/ml/validate_car_dataset.py --input backend/ml/data/new_launches/cars_new_launches.csv

  # Validate main active vehicle catalog
  python backend/ml/validate_car_dataset.py --input backend/data/cars_main.csv

  # Custom output paths
  python backend/ml/validate_car_dataset.py --input backend/ml/data/new_launches/cars_new_launches.csv \
      --output-json backend/ml/data/new_launches/data_quality_report.json \
      --output-csv backend/ml/data/new_launches/data_quality_issues.csv
"""

import argparse
import json
import logging
from pathlib import Path
import sys

# Ensure repository root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.app.services.data_quality_service import DataQualityService, PLAUSIBILITY_LIMITS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ValidateCarDatasetCLI")


def parse_args():
    parser = argparse.ArgumentParser(
        description="AutoAI Automated Data Quality Checker (Non-destructive validation)"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=None,
        help="Path to CSV dataset to validate (defaults to cars_new_launches.csv or cars_main.csv)",
    )
    parser.add_argument(
        "--output-json",
        "-j",
        type=str,
        default=None,
        help="Path to write structured JSON quality report. Defaults to data_quality_report.json alongside input.",
    )
    parser.add_argument(
        "--output-csv",
        "-c",
        type=str,
        default=None,
        help="Path to write detailed CSV quality issues. Defaults to data_quality_issues.csv alongside input.",
    )
    parser.add_argument(
        "--is-new-launches",
        action="store_true",
        help="Flag indicating this dataset is a newly scraped launches file with launch tracking columns.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Determine input path
    if args.input:
        input_path = Path(args.input)
    else:
        # Check standard default locations
        new_launches_p = BASE_DIR / "backend" / "ml" / "data" / "new_launches" / "cars_new_launches.csv"
        main_p = BASE_DIR / "backend" / "data" / "cars_main.csv"
        if new_launches_p.exists():
            input_path = new_launches_p
        elif main_p.exists():
            input_path = main_p
        else:
            logger.error("No input dataset specified and no default datasets found.")
            sys.exit(1)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    logger.info("=" * 70)
    logger.info(f"AutoAI Automated Data Quality Checker")
    logger.info(f"Input Dataset: {input_path}")
    logger.info("=" * 70)

    # Determine output paths
    out_dir = input_path.parent
    output_json = Path(args.output_json) if args.output_json else (out_dir / "data_quality_report.json")
    output_csv = Path(args.output_csv) if args.output_csv else (out_dir / "data_quality_issues.csv")

    checker = DataQualityService()
    is_new = args.is_new_launches or "new_launches" in str(input_path).lower()

    report, issues = checker.validate_dataset(
        data=input_path,
        dataset_name=input_path.name,
        is_new_launches=is_new,
    )

    # Save outputs
    checker.export_report_to_json(report, output_json)
    checker.export_issues_to_csv(issues, output_csv)

    # Console Summary
    sev = report["severity_counts"]
    print("\n" + "=" * 70)
    print("DATA QUALITY AUDIT SUMMARY")
    print(f"Dataset:                  {report['dataset_name']}")
    print(f"Total Rows Examined:      {report['total_rows']}")
    print(f"Total Columns Examined:   {report['total_columns']}")
    print(f"Total Issues Flagged:     {report['total_issues_count']}")
    print(f"  - ERRORS:               {sev['ERROR']}")
    print(f"  - WARNINGS:             {sev['WARNING']}")
    print(f"  - INFO:                 {sev['INFO']}")
    print(f"Records Needing Review:   {report['records_requiring_manual_review']}")
    print(f"Duplicate Rows Count:     {report['duplicate_analysis']['exact_duplicate_rows_count']}")
    print(f"Report JSON:              {output_json}")
    print(f"Issues CSV:               {output_csv}")
    print("=" * 70)

    # Return exit code: 0 if 0 ERRORS, 1 if ERRORS detected
    if sev["ERROR"] > 0:
        print(f"\n[ALERT] {sev['ERROR']} ERROR-level integrity issues found. Review {output_csv.name}.")
        return 1
    else:
        print("\n[SUCCESS] No critical integrity errors found. Dataset passes required validations.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
