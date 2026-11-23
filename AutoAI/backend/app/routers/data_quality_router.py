"""
AutoAI Data Quality API Router
Provides read-only access to automated data quality audit reports,
field-by-field integrity metrics, and individual flagged issues.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query
import pandas as pd

from app.services.data_quality_service import data_quality_service

logger = logging.getLogger("DataQualityRouter")

router = APIRouter(
    prefix="/data-quality",
    tags=["Data Quality"]
)

BASE_DIR = Path(__file__).resolve().parents[2]
NEW_LAUNCHES_DIR = BASE_DIR / "ml" / "data" / "new_launches"
NEW_LAUNCHES_REPORT = NEW_LAUNCHES_DIR / "data_quality_report.json"
NEW_LAUNCHES_ISSUES = NEW_LAUNCHES_DIR / "data_quality_issues.csv"
NEW_LAUNCHES_CSV = NEW_LAUNCHES_DIR / "cars_new_launches.csv"

DATA_DIR = BASE_DIR / "data"
CATALOG_REPORT = DATA_DIR / "data_quality_report.json"
CATALOG_ISSUES = DATA_DIR / "data_quality_issues.csv"
CATALOG_CSV = DATA_DIR / "cars_main.csv"


def _get_target_paths(dataset: str) -> Tuple[Path, Path, Path]:
    """Returns (csv_path, report_path, issues_path) for requested dataset."""
    if dataset.lower() in ("catalog", "main", "cars_main"):
        return CATALOG_CSV, CATALOG_REPORT, CATALOG_ISSUES
    return NEW_LAUNCHES_CSV, NEW_LAUNCHES_REPORT, NEW_LAUNCHES_ISSUES


@router.get("/report")
def get_quality_report(
    dataset: str = Query("new_launches", description="Dataset to inspect: 'new_launches' or 'catalog'")
):
    """
    Returns the comprehensive data quality validation JSON report.
    If cached report is not present, runs on-demand non-destructive validation.
    """
    csv_path, report_path, issues_path = _get_target_paths(dataset)

    if report_path.exists():
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading cached report {report_path}: {e}")

    # Fallback: run on-demand validation safely
    if csv_path.exists():
        report, issues = data_quality_service.validate_dataset(
            csv_path,
            dataset_name=csv_path.name,
            is_new_launches="new_launches" in str(csv_path).lower(),
        )
        return report

    raise HTTPException(status_code=404, detail=f"No dataset found for '{dataset}'.")


@router.get("/issues")
def get_quality_issues(
    dataset: str = Query("new_launches", description="Dataset: 'new_launches' or 'catalog'"),
    severity: Optional[str] = Query(None, description="Filter by severity: ERROR, WARNING, or INFO"),
    field: Optional[str] = Query(None, description="Filter by column field name"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    search: Optional[str] = Query(None, description="Search issue description, observed value, or action"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """
    Returns filterable, paginated data quality issues.
    """
    csv_path, report_path, issues_path = _get_target_paths(dataset)

    issues: List[Dict[str, Any]] = []
    if issues_path.exists():
        try:
            df_issues = pd.read_csv(issues_path)
            raw_records = df_issues.to_dict(orient="records")
            issues = [
                {k: (None if (pd.isna(v) or v == "nan") else v) for k, v in r.items()}
                for r in raw_records
            ]
        except Exception as e:
            logger.warning(f"Error loading issues from {issues_path}: {e}")

    if not issues and csv_path.exists():
        _, issue_objs = data_quality_service.validate_dataset(
            csv_path,
            dataset_name=csv_path.name,
            is_new_launches="new_launches" in str(csv_path).lower(),
        )
        issues = [i.to_dict() for i in issue_objs]

    # Calculate overall counts before filtering
    severity_counts = {
        "ERROR": sum(1 for i in issues if str(i.get("severity")).upper() == "ERROR"),
        "WARNING": sum(1 for i in issues if str(i.get("severity")).upper() == "WARNING"),
        "INFO": sum(1 for i in issues if str(i.get("severity")).upper() == "INFO"),
    }

    # Filtering
    filtered = issues
    if severity:
        sev_target = severity.strip().upper()
        filtered = [i for i in filtered if str(i.get("severity")).upper() == sev_target]

    if field:
        f_target = field.strip().lower()
        filtered = [i for i in filtered if str(i.get("field", "")).lower() == f_target]

    if brand:
        b_target = brand.strip().lower()
        filtered = [i for i in filtered if str(i.get("brand", "")).lower() == b_target]

    if search:
        s_lower = search.strip().lower()
        filtered = [
            i for i in filtered
            if s_lower in str(i.get("issue_type", "")).lower()
            or s_lower in str(i.get("recommended_action", "")).lower()
            or s_lower in str(i.get("observed_value", "")).lower()
            or s_lower in str(i.get("model", "")).lower()
            or s_lower in str(i.get("brand", "")).lower()
        ]

    total_count = len(filtered)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = filtered[start_idx:end_idx]

    return {
        "dataset": dataset,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "severity_counts": severity_counts,
        "items": paginated_items,
    }


@router.get("/stats")
def get_quality_stats(
    dataset: str = Query("new_launches", description="Dataset: 'new_launches' or 'catalog'")
):
    """
    Returns concise summary statistics and health status of the dataset.
    """
    report = get_quality_report(dataset=dataset)
    sev = report.get("severity_counts", {})
    missing_analysis = report.get("missing_data_analysis", {})
    dup_analysis = report.get("duplicate_analysis", {})

    status = "HEALTHY"
    if sev.get("ERROR", 0) > 0:
        status = "NEEDS_ATTENTION"
    elif sev.get("WARNING", 0) > 0:
        status = "WARNINGS_PRESENT"

    return {
        "status": status,
        "dataset_name": report.get("dataset_name"),
        "total_rows": report.get("total_rows", 0),
        "total_columns": report.get("total_columns", 0),
        "total_issues": report.get("total_issues_count", 0),
        "errors": sev.get("ERROR", 0),
        "warnings": sev.get("WARNING", 0),
        "info": sev.get("INFO", 0),
        "records_requiring_manual_review": report.get("records_requiring_manual_review", 0),
        "exact_duplicates": dup_analysis.get("exact_duplicate_rows_count", 0),
        "validation_timestamp": report.get("validation_timestamp"),
    }
