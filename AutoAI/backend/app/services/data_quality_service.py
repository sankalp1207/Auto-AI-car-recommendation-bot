"""
AutoAI Automated Data Quality Checker Service
A reusable, deterministic, non-destructive data quality validation engine
for both active catalog datasets and newly scraped launch datasets.

Performs:
  1. Required fields validation
  2. Numeric plausibility and validity checks
  3. Context-aware missing data analysis (e.g. EV powertrain differences)
  4. Exact, URL, and fuzzy duplicate detection
  5. Date validity, consistency, and temporal plausibility
  6. Source attribution, reachability, and evidence verification
  7. Status vs launch classification consistency
  8. Cross-field engineering and logic consistency
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import urllib.parse

import numpy as np
import pandas as pd

logger = logging.getLogger("DataQualityService")

# Plausibility limits for Indian Passenger Vehicles
# Values outside these bounds generate WARNING severity (or ERROR for physically impossible)
PLAUSIBILITY_LIMITS = {
    "price": {
        "min": 150_000.0,            # INR 1.5 Lakh (e.g., ultra-compact or budget entry)
        "max": 500_000_000.0,        # INR 50 Crore (ultra-luxury / hypercar)
        "unit": "INR",
        "description": "Ex-showroom price in Indian Rupees"
    },
    "engine_cc": {
        "min": 600.0,                # e.g., Maruti Alto / budget micro-car
        "max": 7000.0,               # e.g., Rolls-Royce 6.75L V12
        "unit": "cc",
        "description": "Internal combustion engine displacement"
    },
    "power": {
        "min": 25.0,                 # e.g., entry EV or entry ICE
        "max": 1500.0,               # e.g., high-end hypercar
        "unit": "bhp",
        "description": "Peak engine / motor power output"
    },
    "torque": {
        "min": 40.0,
        "max": 1800.0,
        "unit": "Nm",
        "description": "Peak motor / engine torque"
    },
    "mileage": {
        "min": 5.0,                  # High performance V12 / super-SUV
        "max": 45.0,                 # High efficiency CNG / Strong Hybrid
        "unit": "kmpl or km/kg",
        "description": "Fuel efficiency"
    },
    "seating": {
        "min": 2,
        "max": 10,
        "unit": "seats",
        "description": "Passenger seating capacity"
    },
    "ground_clearance": {
        "min": 100.0,                # Sports cars / low ground clearance
        "max": 320.0,                # Heavy duty off-roaders / 4x4
        "unit": "mm",
        "description": "Unladen ground clearance"
    },
    "boot_space": {
        "min": 50.0,
        "max": 1200.0,
        "unit": "litres",
        "description": "Luggage boot capacity"
    },
    "safety_rating": {
        "min": 0.0,
        "max": 5.0,
        "unit": "stars",
        "description": "Global NCAP / Bharat NCAP star rating"
    },
    "battery_capacity": {
        "min": 10.0,                 # Small city EV (e.g. MG Comet 17.3 kWh)
        "max": 250.0,                # Large commercial / long-range luxury EV
        "unit": "kWh",
        "description": "Electric traction battery capacity"
    },
    "range_km": {
        "min": 50.0,
        "max": 1200.0,
        "unit": "km",
        "description": "Claimed driving range per charge"
    }
}

VALID_STATUSES = {"CURRENT", "UPCOMING", "DISCONTINUED", "ARCHIVED"}
VALID_RECORD_TYPES = {
    "NEW_MODEL", "NEW_VARIANT", "FACELIFT", "MODEL_YEAR_UPDATE",
    "SPECIAL_EDITION", "UPCOMING", "ANNOUNCED_OR_UNVEILED", "UNCERTAIN", "EXISTING",
    "EXISTING_CATALOG"
}
VALID_FUELS = {"Petrol", "Diesel", "Electric", "CNG", "Hybrid", "Plug-in Hybrid", "LPG", "Hydrogen"}


@dataclass
class QualityIssue:
    record_id: Union[int, str]
    brand: str
    model: str
    variant: Optional[str]
    field: str
    issue_type: str
    severity: str  # "ERROR", "WARNING", "INFO"
    observed_value: Any
    recommended_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "brand": self.brand,
            "model": self.model,
            "variant": self.variant or "",
            "field": self.field,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "observed_value": str(self.observed_value) if self.observed_value is not None else "",
            "recommended_action": self.recommended_action,
        }


class DataQualityService:
    """
    Reusable data quality validation engine.
    Works with Pandas DataFrames or CSV file paths without mutating source data.
    """

    def __init__(self, plausibility_limits: Optional[Dict[str, Any]] = None):
        self.limits = plausibility_limits or PLAUSIBILITY_LIMITS

    def validate_dataset(
        self,
        data: Union[pd.DataFrame, Path, str],
        dataset_name: Optional[str] = None,
        is_new_launches: bool = False,
    ) -> Tuple[Dict[str, Any], List[QualityIssue]]:
        """
        Validates an entire dataset and produces:
          1. Structured JSON report dictionary
          2. List of QualityIssue objects for tabular export
        """
        # Load dataset without mutating original
        if isinstance(data, (Path, str)):
            p = Path(data)
            dataset_name = dataset_name or p.name
            if not p.exists():
                raise FileNotFoundError(f"Dataset path does not exist: {p}")
            df = pd.read_csv(p)
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
            dataset_name = dataset_name or "in_memory_dataframe"
        else:
            raise TypeError(f"Unsupported data type for validation: {type(data)}")

        issues: List[QualityIssue] = []
        total_rows = len(df)
        total_cols = len(df.columns)

        # Assign stable synthetic record identifier if not present
        if "id" in df.columns:
            record_ids = df["id"].tolist()
        else:
            record_ids = [f"ROW_{i + 1}" for i in range(total_rows)]

        # --- 1. Required Fields Validation ---
        self._check_required_fields(df, record_ids, issues, is_new_launches)

        # --- 2. Numeric Validation & Plausibility ---
        self._check_numeric_fields(df, record_ids, issues)

        # --- 3. Missing Data Analysis (Context & Powertrain-aware) ---
        missing_stats = self._analyze_missing_data(df)

        # --- 4. Duplicate Detection (Exact, URL, Normalized, Fuzzy) ---
        dup_stats = self._check_duplicates(df, record_ids, issues)

        # --- 5. Date Validation ---
        self._check_dates(df, record_ids, issues)

        # --- 6. Source & URL Validation ---
        self._check_source_and_urls(df, record_ids, issues)

        # --- 7. Status Validation ---
        self._check_status_consistency(df, record_ids, issues)

        # --- 8. Cross-Field Validation ---
        self._check_cross_field_consistency(df, record_ids, issues)

        # Summary Metrics
        severity_counts = {
            "ERROR": sum(1 for i in issues if i.severity == "ERROR"),
            "WARNING": sum(1 for i in issues if i.severity == "WARNING"),
            "INFO": sum(1 for i in issues if i.severity == "INFO"),
        }

        records_needing_review = len({i.record_id for i in issues if i.severity in ("ERROR", "WARNING")})

        # Summary statistics for numeric columns
        summary_stats = self._calculate_summary_statistics(df)

        report = {
            "validation_timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset_name": dataset_name,
            "total_rows": total_rows,
            "total_columns": total_cols,
            "total_issues_count": len(issues),
            "severity_counts": severity_counts,
            "records_requiring_manual_review": records_needing_review,
            "missing_data_analysis": missing_stats,
            "duplicate_analysis": dup_stats,
            "summary_statistics": summary_stats,
            "plausibility_limits_applied": self.limits,
            "review_actions_summary": self._summarize_recommended_actions(issues),
        }

        return report, issues

    def _check_required_fields(
        self, df: pd.DataFrame, record_ids: List[Any], issues: List[QualityIssue], is_new_launches: bool
    ):
        """Validates that indispensable identity columns are populated."""
        for idx, row in df.iterrows():
            rec_id = record_ids[idx]
            brand = row.get("brand")
            model = row.get("model")
            variant = row.get("variant")

            brand_str = str(brand).strip() if pd.notna(brand) else ""
            model_str = str(model).strip() if pd.notna(model) else ""
            variant_str = str(variant).strip() if pd.notna(variant) else ""

            if not brand_str or brand_str.lower() in ("nan", "none", "unknown", ""):
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand="Unknown",
                        model=model_str or "Unknown",
                        variant=variant_str,
                        field="brand",
                        issue_type="MISSING_REQUIRED_FIELD",
                        severity="ERROR",
                        observed_value=brand,
                        recommended_action="Populate canonical manufacturer brand name.",
                    )
                )

            if not model_str or model_str.lower() in ("nan", "none", "unknown", ""):
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand=brand_str or "Unknown",
                        model="Unknown",
                        variant=variant_str,
                        field="model",
                        issue_type="MISSING_REQUIRED_FIELD",
                        severity="ERROR",
                        observed_value=model,
                        recommended_action="Populate vehicle model name.",
                    )
                )

            # Check variant: for launched production cars, variant is expected
            status_val = str(row.get("status") or "").upper()
            if status_val == "CURRENT" and not variant_str:
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand=brand_str or "Unknown",
                        model=model_str or "Unknown",
                        variant=None,
                        field="variant",
                        issue_type="MISSING_EXPECTED_VARIANT",
                        severity="WARNING",
                        observed_value=variant,
                        recommended_action="Production vehicle missing trim/variant name; verify if single-trim or base model.",
                    )
                )

    def _check_numeric_fields(self, df: pd.DataFrame, record_ids: List[Any], issues: List[QualityIssue]):
        """Validates numeric columns for positive values, non-negativity, and plausibility limits."""
        numeric_cols = [
            ("price", True),  # (col, must_be_strictly_positive)
            ("engine_cc", False),
            ("power", False),
            ("torque", False),
            ("mileage", False),
            ("seating", True),
            ("boot_space", False),
            ("ground_clearance", False),
            ("safety_rating", False),
            ("battery_capacity", False),
            ("range_km", False),
        ]

        for col, must_be_positive in numeric_cols:
            if col not in df.columns:
                continue

            for idx, raw_val in df[col].items():
                rec_id = record_ids[idx]
                brand = str(df.at[idx, "brand"]) if pd.notna(df.at[idx, "brand"]) else "Unknown"
                model = str(df.at[idx, "model"]) if pd.notna(df.at[idx, "model"]) else "Unknown"
                variant = str(df.at[idx, "variant"]) if pd.notna(df.at[idx, "variant"]) else None
                fuel = str(df.at[idx, "fuel_type"] if "fuel_type" in df.columns else "").lower()

                if pd.isna(raw_val) or raw_val is None or str(raw_val).strip() in ("", "nan", "None"):
                    continue

                # Check parseability
                try:
                    num_val = float(str(raw_val).replace(",", "").strip())
                except (ValueError, TypeError):
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field=col,
                            issue_type="MALFORMED_NUMERIC_STRING",
                            severity="ERROR",
                            observed_value=raw_val,
                            recommended_action=f"Clean malformed numeric value in '{col}'.",
                        )
                    )
                    continue

                # Strictly positive check (e.g. price, seating)
                if must_be_positive and num_val <= 0:
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field=col,
                            issue_type="NON_POSITIVE_VALUE",
                            severity="ERROR",
                            observed_value=num_val,
                            recommended_action=f"Field '{col}' must be greater than zero.",
                        )
                    )
                    continue

                # Negative value check for other specs
                if not must_be_positive and num_val < 0:
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field=col,
                            issue_type="NEGATIVE_NUMERIC_VALUE",
                            severity="ERROR",
                            observed_value=num_val,
                            recommended_action=f"Field '{col}' cannot be negative.",
                        )
                    )
                    continue

                # Special check: Safety rating must be within 0.0 to 5.0
                if col == "safety_rating":
                    if num_val < 0.0 or num_val > 5.0:
                        issues.append(
                            QualityIssue(
                                record_id=rec_id,
                                brand=brand,
                                model=model,
                                variant=variant,
                                field=col,
                                issue_type="INVALID_SAFETY_RATING",
                                severity="ERROR",
                                observed_value=num_val,
                                recommended_action="Safety rating must be between 0.0 and 5.0 stars.",
                            )
                        )
                        continue

                # Plausibility bounds check (generates WARNING, not ERROR, so luxury/unusual vehicles are flagged but not blocked)
                # Skip engine_cc plausibility if EV
                if col == "engine_cc" and ("electric" in fuel or "ev" in fuel):
                    continue

                if col in self.limits:
                    c_min = self.limits[col]["min"]
                    c_max = self.limits[col]["max"]
                    if num_val < c_min or num_val > c_max:
                        issues.append(
                            QualityIssue(
                                record_id=rec_id,
                                brand=brand,
                                model=model,
                                variant=variant,
                                field=col,
                                issue_type="VALUE_OUTSIDE_PLAUSIBILITY_LIMITS",
                                severity="WARNING",
                                observed_value=num_val,
                                recommended_action=(
                                    f"Value {num_val} is outside standard plausibility [{c_min}, {c_max}] {self.limits[col]['unit']}. "
                                    f"Verify if vehicle is an unusual/high-performance model or data error."
                                ),
                            )
                        )

    def _analyze_missing_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculates missing counts and percentages.
        Crucially distinguishes:
          - Universally missing required fields
          - Universally missing optional fields
          - Legitimate Not-Applicable (N/A) fields for EV vs ICE powertrains
        """
        total = len(df)
        if total == 0:
            return {"total_rows": 0, "fields": {}}

        fuel_series = df["fuel_type"].astype(str).str.lower() if "fuel_type" in df.columns else pd.Series([""] * total)
        is_ev = fuel_series.str.contains("electric|ev", na=False)
        is_ice = fuel_series.str.contains("petrol|diesel|cng", na=False)

        field_breakdown = {}
        for col in df.columns:
            missing_mask = df[col].isna() | (df[col].astype(str).str.strip().isin(["", "nan", "None", "null"]))
            missing_count = int(missing_mask.sum())
            missing_pct = round((missing_count / total) * 100, 2)

            # Powertrain-aware adjustment
            not_applicable_count = 0
            if col == "engine_cc":
                not_applicable_count = int(is_ev.sum())
            elif col in ("battery_capacity", "range_km"):
                not_applicable_count = int(is_ice.sum())

            adjusted_missing_count = max(0, missing_count - not_applicable_count)
            adjusted_pct = round((adjusted_missing_count / total) * 100, 2)

            field_breakdown[col] = {
                "missing_count": missing_count,
                "missing_percentage": missing_pct,
                "not_applicable_count": not_applicable_count,
                "adjusted_missing_count": adjusted_missing_count,
                "adjusted_missing_percentage": adjusted_pct,
            }

        return {
            "total_rows": total,
            "fields": field_breakdown,
            "ev_records_count": int(is_ev.sum()),
            "ice_records_count": int(is_ice.sum()),
        }

    def _check_duplicates(
        self, df: pd.DataFrame, record_ids: List[Any], issues: List[QualityIssue]
    ) -> Dict[str, Any]:
        """
        Identifies:
          1. Exact duplicate rows
          2. Duplicate source URLs
          3. Duplicate normalized (brand, model, variant)
          4. Potential fuzzy duplicates
        """
        total_rows = len(df)
        if total_rows == 0:
            return {"exact_duplicates": 0, "url_duplicates": 0, "normalized_duplicates": 0, "groups": []}

        # 1. Exact duplicate rows
        exact_dups = df.duplicated(keep=False)
        exact_dup_indices = df[exact_dups].index.tolist()
        for idx in exact_dup_indices:
            issues.append(
                QualityIssue(
                    record_id=record_ids[idx],
                    brand=str(df.at[idx, "brand"]),
                    model=str(df.at[idx, "model"]),
                    variant=str(df.at[idx, "variant"]) if pd.notna(df.at[idx, "variant"]) else None,
                    field="entire_row",
                    issue_type="EXACT_DUPLICATE_ROW",
                    severity="ERROR",
                    observed_value="Duplicate Row",
                    recommended_action="Remove duplicate row entry.",
                )
            )

        # 2. Duplicate variant URLs
        url_dup_count = 0
        if "variant_url" in df.columns:
            valid_urls = df["variant_url"].dropna().astype(str).str.strip()
            valid_urls = valid_urls[valid_urls != ""]
            url_dups = valid_urls.duplicated(keep=False)
            url_dup_indices = valid_urls[url_dups].index.tolist()
            url_dup_count = len(url_dup_indices)
            for idx in url_dup_indices:
                issues.append(
                    QualityIssue(
                        record_id=record_ids[idx],
                        brand=str(df.at[idx, "brand"]),
                        model=str(df.at[idx, "model"]),
                        variant=str(df.at[idx, "variant"]) if pd.notna(df.at[idx, "variant"]) else None,
                        field="variant_url",
                        issue_type="DUPLICATE_SOURCE_URL",
                        severity="WARNING",
                        observed_value=df.at[idx, "variant_url"],
                        recommended_action="Inspect shared variant URL; verify whether distinct trim or redundant entry.",
                    )
                )

        # 3. Duplicate normalized (brand + model + variant)
        norm_keys = []
        for idx in range(total_rows):
            b = str(df.at[idx, "brand"]).strip().lower() if pd.notna(df.at[idx, "brand"]) else ""
            m = str(df.at[idx, "model"]).strip().lower() if pd.notna(df.at[idx, "model"]) else ""
            v = str(df.at[idx, "variant"]).strip().lower() if pd.notna(df.at[idx, "variant"]) else ""
            # Strip excessive whitespace
            b = re.sub(r"\s+", " ", b)
            m = re.sub(r"\s+", " ", m)
            v = re.sub(r"\s+", " ", v)
            norm_keys.append(f"{b}|{m}|{v}")

        norm_series = pd.Series(norm_keys)
        norm_dups = norm_series.duplicated(keep=False)
        norm_dup_indices = norm_series[norm_dups].index.tolist()

        duplicate_groups = {}
        for idx in norm_dup_indices:
            key = norm_keys[idx]
            if key not in duplicate_groups:
                duplicate_groups[key] = []
            duplicate_groups[key].append(record_ids[idx])

            # Only add issue if not already flagged as exact duplicate
            if idx not in exact_dup_indices:
                issues.append(
                    QualityIssue(
                        record_id=record_ids[idx],
                        brand=str(df.at[idx, "brand"]),
                        model=str(df.at[idx, "model"]),
                        variant=str(df.at[idx, "variant"]) if pd.notna(df.at[idx, "variant"]) else None,
                        field="brand|model|variant",
                        issue_type="DUPLICATE_NORMALIZED_VARIANT",
                        severity="WARNING",
                        observed_value=key,
                        recommended_action="Review duplicate normalized model/variant. Verify year or trim differentiation.",
                    )
                )

        return {
            "exact_duplicate_rows_count": len(exact_dup_indices),
            "duplicate_urls_count": url_dup_count,
            "normalized_duplicate_count": len(norm_dup_indices),
            "duplicate_groups_sample": [
                {"normalized_key": k, "record_ids": v} for k, v in list(duplicate_groups.items())[:10]
            ],
        }

    def _check_dates(self, df: pd.DataFrame, record_ids: List[Any], issues: List[QualityIssue]):
        """Validates date formats, temporal plausibility, and status consistency."""
        if "launch_date" not in df.columns:
            return

        now_year = datetime.now().year

        for idx, raw_date in df["launch_date"].items():
            rec_id = record_ids[idx]
            brand = str(df.at[idx, "brand"]) if pd.notna(df.at[idx, "brand"]) else "Unknown"
            model = str(df.at[idx, "model"]) if pd.notna(df.at[idx, "model"]) else "Unknown"
            variant = str(df.at[idx, "variant"]) if pd.notna(df.at[idx, "variant"]) else None
            status = str(df.at[idx, "status"] if "status" in df.columns else "").upper()

            if pd.isna(raw_date) or raw_date is None or str(raw_date).strip() in ("", "nan", "None"):
                continue

            date_str = str(raw_date).strip()

            # Recognize historical / pre-cutoff sentinels
            if date_str.lower().startswith("pre-") or date_str.lower().startswith("pre_") or date_str.upper() in ("HISTORICAL", "PRE_CUTOFF"):
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand=brand,
                        model=model,
                        variant=variant,
                        field="launch_date",
                        issue_type="HISTORICAL_PRE_CUTOFF_DATE",
                        severity="INFO",
                        observed_value=date_str,
                        recommended_action="Legacy catalog entry preceding tracking cutoff date.",
                    )
                )
                continue

            parsed_dt = None

            # Attempt standard parsing formats
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%m/%d/%Y %H:%M:%S", "%d/%m/%Y"):
                try:
                    parsed_dt = datetime.strptime(date_str[:19], fmt)
                    break
                except ValueError:
                    pass

            if not parsed_dt:
                try:
                    from dateutil import parser as d_parser
                    parsed_dt = d_parser.parse(date_str)
                except Exception:
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field="launch_date",
                            issue_type="MALFORMED_LAUNCH_DATE",
                            severity="ERROR",
                            observed_value=date_str,
                            recommended_action="Normalize launch_date to ISO-8601 YYYY-MM-DD format.",
                        )
                    )
                    continue

            # Temporal plausibility check: 1980 <= year <= current_year + 5
            if parsed_dt.year < 1980 or parsed_dt.year > now_year + 5:
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand=brand,
                        model=model,
                        variant=variant,
                        field="launch_date",
                        issue_type="IMPOSSIBLE_LAUNCH_YEAR",
                        severity="ERROR",
                        observed_value=date_str,
                        recommended_action=f"Launch year {parsed_dt.year} is outside plausible range [1980, {now_year + 5}].",
                    )
                )

            # Inconsistency: Status CURRENT but launch date is in the far future (> 90 days ahead)
            if status == "CURRENT" and parsed_dt > datetime.now() + pd.Timedelta(days=90):
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand=brand,
                        model=model,
                        variant=variant,
                        field="launch_date",
                        issue_type="FUTURE_LAUNCH_DATE_FOR_CURRENT_STATUS",
                        severity="WARNING",
                        observed_value=date_str,
                        recommended_action="Vehicle has CURRENT status but launch date is in the future. Check if UPCOMING.",
                    )
                )

    def _check_source_and_urls(self, df: pd.DataFrame, record_ids: List[Any], issues: List[QualityIssue]):
        """Validates source attribution, URL syntax, and evidence presence."""
        for idx in range(len(df)):
            rec_id = record_ids[idx]
            brand = str(df.at[idx, "brand"]) if pd.notna(df.at[idx, "brand"]) else "Unknown"
            model = str(df.at[idx, "model"]) if pd.notna(df.at[idx, "model"]) else "Unknown"
            variant = str(df.at[idx, "variant"]) if pd.notna(df.at[idx, "variant"]) else None

            # Source attribution check
            if "source" in df.columns:
                src = df.at[idx, "source"]
                if pd.isna(src) or not str(src).strip():
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field="source",
                            issue_type="MISSING_SOURCE_ATTRIBUTION",
                            severity="WARNING",
                            observed_value=src,
                            recommended_action="Set source attribution (e.g. 'carwale.com').",
                        )
                    )

            # URL formatting checks
            for url_field in ("model_url", "variant_url", "launch_evidence_url"):
                if url_field not in df.columns:
                    continue
                url_val = df.at[idx, url_field]
                if pd.isna(url_val) or not str(url_val).strip():
                    continue

                u_str = str(url_val).strip()
                if not (u_str.startswith("http://") or u_str.startswith("https://")):
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field=url_field,
                            issue_type="INVALID_URL_SCHEME",
                            severity="ERROR",
                            observed_value=u_str,
                            recommended_action="URLs must begin with http:// or https://.",
                        )
                    )
                    continue

                parsed = urllib.parse.urlparse(u_str)
                if not parsed.netloc:
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field=url_field,
                            issue_type="MALFORMED_URL_DOMAIN",
                            severity="ERROR",
                            observed_value=u_str,
                            recommended_action="Provide fully qualified domain name in URL.",
                        )
                    )

    def _check_status_consistency(self, df: pd.DataFrame, record_ids: List[Any], issues: List[QualityIssue]):
        """Checks consistency between status, record_type, and launch evidence."""
        if "status" not in df.columns:
            return

        for idx, raw_status in df["status"].items():
            rec_id = record_ids[idx]
            brand = str(df.at[idx, "brand"]) if pd.notna(df.at[idx, "brand"]) else "Unknown"
            model = str(df.at[idx, "model"]) if pd.notna(df.at[idx, "model"]) else "Unknown"
            variant = str(df.at[idx, "variant"]) if pd.notna(df.at[idx, "variant"]) else None

            st = str(raw_status).strip().upper() if pd.notna(raw_status) else ""
            if st and st not in VALID_STATUSES:
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand=brand,
                        model=model,
                        variant=variant,
                        field="status",
                        issue_type="INVALID_STATUS_VALUE",
                        severity="ERROR",
                        observed_value=raw_status,
                        recommended_action=f"Status must be one of {sorted(list(VALID_STATUSES))}.",
                    )
                )

            # Check status vs record_type if record_type exists
            if "record_type" in df.columns:
                rt = str(df.at[idx, "record_type"]).strip().upper() if pd.notna(df.at[idx, "record_type"]) else ""
                if rt and rt not in VALID_RECORD_TYPES:
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field="record_type",
                            issue_type="INVALID_RECORD_TYPE",
                            severity="ERROR",
                            observed_value=rt,
                            recommended_action=f"record_type must be one of {sorted(list(VALID_RECORD_TYPES))}.",
                        )
                    )

                if st == "CURRENT" and rt in ("UPCOMING", "ANNOUNCED_OR_UNVEILED"):
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field="status_vs_record_type",
                            issue_type="STATUS_RECORD_TYPE_MISMATCH",
                            severity="WARNING",
                            observed_value=f"status={st}, record_type={rt}",
                            recommended_action="Unlaunched vehicle marked with CURRENT status; reclassify status to UPCOMING.",
                        )
                    )

    def _check_cross_field_consistency(self, df: pd.DataFrame, record_ids: List[Any], issues: List[QualityIssue]):
        """
        Cross-field engineering and logic consistency checks:
          - Fuel type vs Engine capacity
          - Electric powertrain vs Battery capacity & Range
          - Transmission vs Fuel type / Powertrain
          - Seating vs Body type
          - Model URL vs Variant URL consistency
        """
        for idx in range(len(df)):
            rec_id = record_ids[idx]
            brand = str(df.at[idx, "brand"]) if pd.notna(df.at[idx, "brand"]) else "Unknown"
            model = str(df.at[idx, "model"]) if pd.notna(df.at[idx, "model"]) else "Unknown"
            variant = str(df.at[idx, "variant"]) if pd.notna(df.at[idx, "variant"]) else None

            fuel = str(df.at[idx, "fuel_type"]).strip() if "fuel_type" in df.columns and pd.notna(df.at[idx, "fuel_type"]) else ""
            fuel_lower = fuel.lower()

            engine_cc = None
            if "engine_cc" in df.columns and pd.notna(df.at[idx, "engine_cc"]):
                try:
                    engine_cc = float(df.at[idx, "engine_cc"])
                except (ValueError, TypeError):
                    pass

            battery_kwh = None
            if "battery_capacity" in df.columns and pd.notna(df.at[idx, "battery_capacity"]):
                try:
                    battery_kwh = float(df.at[idx, "battery_capacity"])
                except (ValueError, TypeError):
                    pass

            range_km = None
            if "range_km" in df.columns and pd.notna(df.at[idx, "range_km"]):
                try:
                    range_km = float(df.at[idx, "range_km"])
                except (ValueError, TypeError):
                    pass

            seating = None
            if "seating" in df.columns and pd.notna(df.at[idx, "seating"]):
                try:
                    seating = float(df.at[idx, "seating"])
                except (ValueError, TypeError):
                    pass

            body_type = str(df.at[idx, "body_type"]).strip().lower() if "body_type" in df.columns and pd.notna(df.at[idx, "body_type"]) else ""

            # 1. Electric vehicle with non-zero engine capacity
            if ("electric" in fuel_lower or fuel_lower == "ev") and engine_cc and engine_cc > 0:
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand=brand,
                        model=model,
                        variant=variant,
                        field="engine_cc_vs_fuel_type",
                        issue_type="ELECTRIC_VEHICLE_HAS_ENGINE_CC",
                        severity="ERROR",
                        observed_value=f"fuel={fuel}, engine_cc={engine_cc}",
                        recommended_action="Electric vehicles do not have displacement. Set engine_cc to None/null.",
                    )
                )

            # 2. ICE vehicle (Petrol/Diesel/CNG) missing engine capacity
            if any(f in fuel_lower for f in ("petrol", "diesel", "cng")) and (engine_cc is None or engine_cc <= 0):
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand=brand,
                        model=model,
                        variant=variant,
                        field="engine_cc",
                        issue_type="ICE_VEHICLE_MISSING_DISPLACEMENT",
                        severity="WARNING",
                        observed_value=f"fuel={fuel}, engine_cc={engine_cc}",
                        recommended_action=f"Combustion powertrain ({fuel}) expected to specify displacement in cc.",
                    )
                )

            # 3. Electric vehicle missing both battery capacity and range
            if ("electric" in fuel_lower or fuel_lower == "ev") and (battery_kwh is None or battery_kwh <= 0) and (range_km is None or range_km <= 0):
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand=brand,
                        model=model,
                        variant=variant,
                        field="battery_or_range",
                        issue_type="ELECTRIC_VEHICLE_MISSING_EV_SPECS",
                        severity="WARNING",
                        observed_value=f"fuel={fuel}, battery={battery_kwh}, range={range_km}",
                        recommended_action="Electric vehicle missing both battery capacity and driving range.",
                    )
                )

            # 4. Pure Petrol/Diesel with large traction battery capacity (> 5 kWh)
            if fuel_lower in ("petrol", "diesel") and battery_kwh and battery_kwh > 5.0:
                issues.append(
                    QualityIssue(
                        record_id=rec_id,
                        brand=brand,
                        model=model,
                        variant=variant,
                        field="battery_vs_fuel_type",
                        issue_type="NON_HYBRID_HAS_TRACTION_BATTERY",
                        severity="WARNING",
                        observed_value=f"fuel={fuel}, battery_capacity={battery_kwh} kWh",
                        recommended_action="Verify if vehicle is a Hybrid or PHEV rather than pure ICE.",
                    )
                )

            # 5. Seating vs Body Type
            if seating:
                if "hatchback" in body_type and seating > 5:
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field="seating_vs_body_type",
                            issue_type="UNUSUAL_HATCHBACK_SEATING",
                            severity="WARNING",
                            observed_value=f"body_type={body_type}, seating={seating}",
                            recommended_action=f"Hatchback listed with {seating} seats. Standard capacity is 4 or 5.",
                        )
                    )
                elif "suv" in body_type and seating < 4:
                    issues.append(
                        QualityIssue(
                            record_id=rec_id,
                            brand=brand,
                            model=model,
                            variant=variant,
                            field="seating_vs_body_type",
                            issue_type="UNUSUAL_SUV_SEATING",
                            severity="INFO",
                            observed_value=f"body_type={body_type}, seating={seating}",
                            recommended_action=f"SUV listed with {seating} seats. Verify if specialized 2-seater or data omission.",
                        )
                    )

            # 6. Model URL vs Variant URL consistency
            if "model_url" in df.columns and "variant_url" in df.columns:
                m_url = str(df.at[idx, "model_url"]).strip() if pd.notna(df.at[idx, "model_url"]) else ""
                v_url = str(df.at[idx, "variant_url"]).strip() if pd.notna(df.at[idx, "variant_url"]) else ""
                if m_url and v_url and m_url != v_url:
                    # Parse paths
                    m_path = urllib.parse.urlparse(m_url).path.rstrip("/")
                    v_path = urllib.parse.urlparse(v_url).path.rstrip("/")
                    if not v_path.startswith(m_path):
                        issues.append(
                            QualityIssue(
                                record_id=rec_id,
                                brand=brand,
                                model=model,
                                variant=variant,
                                field="url_hierarchy",
                                issue_type="VARIANT_URL_NOT_SUBPATH_OF_MODEL",
                                severity="INFO",
                                observed_value=f"model={m_url}, variant={v_url}",
                                recommended_action="Variant URL does not share model path prefix; verify linking.",
                            )
                        )

    def _calculate_summary_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculates robust statistical aggregates for numerical and categorical fields."""
        stats: Dict[str, Any] = {}
        if len(df) == 0:
            return stats

        # Price stats
        if "price" in df.columns:
            prices = pd.to_numeric(df["price"], errors="coerce").dropna()
            if len(prices) > 0:
                stats["price"] = {
                    "count": int(len(prices)),
                    "min": float(prices.min()),
                    "max": float(prices.max()),
                    "mean": round(float(prices.mean()), 2),
                    "median": float(prices.median()),
                }

        # Fuel type distribution
        if "fuel_type" in df.columns:
            stats["fuel_type_distribution"] = {
                str(k): int(v) for k, v in df["fuel_type"].value_counts().items()
            }

        # Transmission distribution
        if "transmission" in df.columns:
            stats["transmission_distribution"] = {
                str(k): int(v) for k, v in df["transmission"].value_counts().items()
            }

        # Body type distribution
        if "body_type" in df.columns:
            stats["body_type_distribution"] = {
                str(k): int(v) for k, v in df["body_type"].value_counts().items()
            }

        stats["unique_brands_count"] = int(df["brand"].nunique()) if "brand" in df.columns else 0
        stats["unique_models_count"] = int(df["model"].nunique()) if "model" in df.columns else 0

        return stats

    def _summarize_recommended_actions(self, issues: List[QualityIssue]) -> Dict[str, int]:
        """Aggregates recommended review actions."""
        summary: Dict[str, int] = {}
        for i in issues:
            act = i.recommended_action
            summary[act] = summary.get(act, 0) + 1
        return summary

    def export_issues_to_csv(self, issues: List[QualityIssue], output_csv_path: Path):
        """Exports quality issues into a clean, structured CSV file."""
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [i.to_dict() for i in issues]
        if not rows:
            # Create empty CSV with headers
            cols = ["record_id", "brand", "model", "variant", "field", "issue_type", "severity", "observed_value", "recommended_action"]
            pd.DataFrame(columns=cols).to_csv(output_csv_path, index=False)
            return

        df_issues = pd.DataFrame(rows)
        # Deterministic sorting: severity (ERROR first, then WARNING, then INFO), then brand, model
        severity_order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
        df_issues["_sort_sev"] = df_issues["severity"].map(lambda x: severity_order.get(x, 99))
        df_issues = df_issues.sort_values(by=["_sort_sev", "brand", "model", "field"]).drop(columns=["_sort_sev"])
        df_issues.to_csv(output_csv_path, index=False)
        logger.info(f"Saved {len(df_issues)} quality issues to {output_csv_path}")

    def export_report_to_json(self, report: Dict[str, Any], output_json_path: Path):
        """Exports quality summary report into a structured JSON file."""
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info(f"Saved quality report to {output_json_path}")


# Singleton instance for convenience
data_quality_service = DataQualityService()
