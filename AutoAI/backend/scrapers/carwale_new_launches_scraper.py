"""
AutoAI Incremental Car Launch Scraper
Sole External Data Source: CarWale (https://www.carwale.com)

Discovers newly launched cars, variants, facelifts, and special editions in India
post-dating the previous AutoAI catalog collection.
Outputs all artifacts to: backend/ml/data/new_launches/
"""

import argparse
import copy
import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import json
import logging
import math
import os
from pathlib import Path
import random
import re
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# Setup structured logger
logger = logging.getLogger("AutoAIIncrementalScraper")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)

# Version & Source Constants
SCRAPER_VERSION = "1.0.0"
SOURCE_DOMAIN = "carwale.com"
BASE_CARWALE_URL = "https://www.carwale.com"
LAUNCHES_START_URL = "https://www.carwale.com/new-car-launches/"
NEWS_START_URL = "https://www.carwale.com/news/"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
    "Safari/537.36 AutoAI-Incremental-Bot/1.0 (+https://github.com/sankalp1207/Auto-AI-car-recommendation-bot)"
)

# Standard Output Schema Columns
BASE_COLUMNS = [
    "brand", "model", "variant", "price", "fuel_type", "transmission",
    "body_type", "engine_cc", "power", "torque", "mileage", "seating",
    "boot_space", "ground_clearance", "safety_rating", "battery_capacity",
    "range_km", "status", "source", "model_url", "variant_url"
]

TRACKING_COLUMNS = [
    "launch_date", "launch_date_type", "launch_evidence_url",
    "discovered_at", "source_last_verified_at", "record_type", "data_quality_status"
]

ALL_COLUMNS = BASE_COLUMNS + TRACKING_COLUMNS

# Classification Categories
RECORD_TYPE_NEW_MODEL = "NEW_MODEL"
RECORD_TYPE_NEW_VARIANT = "NEW_VARIANT"
RECORD_TYPE_FACELIFT = "FACELIFT"
RECORD_TYPE_MODEL_YEAR_UPDATE = "MODEL_YEAR_UPDATE"
RECORD_TYPE_SPECIAL_EDITION = "SPECIAL_EDITION"
RECORD_TYPE_UPCOMING = "UPCOMING"
RECORD_TYPE_ANNOUNCED = "ANNOUNCED_OR_UNVEILED"
RECORD_TYPE_UNCERTAIN = "UNCERTAIN"
RECORD_TYPE_EXISTING = "EXISTING"

# Credible Price Range for Passenger Cars in India (INR)
MIN_CREDIBLE_PRICE = 100_000
MAX_CREDIBLE_PRICE = 500_000_000

# Canonical Brand Mapping
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
    "denza": "Denza",
    "ssangyong": "SsangYong",
}


def normalize_brand_name(brand: Any) -> str:
    """Normalizes vehicle brand name to canonical format."""
    if brand is None or pd.isna(brand):
        return "Unknown"
    s = str(brand).strip()
    return BRAND_CANONICAL_MAP.get(s.lower(), s)


def normalize_model_name(model: Any) -> str:
    """Normalizes vehicle model name for consistent comparison."""
    if model is None or pd.isna(model):
        return ""
    s = str(model).strip()
    # Normalize common spacing/punctuation artifacts
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_variant_name(variant: Any) -> Optional[str]:
    """Normalizes vehicle variant string."""
    if variant is None or pd.isna(variant):
        return None
    s = str(variant).strip()
    if not s or s.lower() in ["none", "nan", "null"]:
        return None
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_fuel_type(val: Any) -> Optional[str]:
    """Normalizes fuel type to standardized title case."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    s_lower = s.lower()
    if not s or s_lower in ["nan", "null", "none", "unknown", ""]:
        return None
    if "plug-in hybrid" in s_lower or "phev" in s_lower:
        return "Plug-in Hybrid"
    if "hybrid" in s_lower:
        return "Hybrid"
    if "electric" in s_lower or "ev" in s_lower:
        return "Electric"
    if "cng" in s_lower:
        return "CNG"
    if "diesel" in s_lower:
        return "Diesel"
    if "petrol" in s_lower:
        return "Petrol"
    return s.title()


def normalize_transmission(val: Any) -> Optional[str]:
    """Normalizes transmission type into AutoAI standard categories."""
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
    """Normalizes body type to standard AutoAI classification."""
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
    if "station wagon" in s_lower or "wagon" in s_lower or "estate" in s_lower:
        return "Station Wagon"
    return s.title()


def parse_numeric(val: Any) -> Optional[float]:
    """Safely extracts a floating point number from strings or numbers."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip().replace(",", "")
    if not s or s.lower() in ["nan", "null", "none", "unknown", ""]:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def parse_carwale_date(date_str: Any, base_time: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parses various CarWale date formats including:
      - 'MM/DD/YYYY HH:MM:SS' (from __INITIAL_STATE__)
      - 'Month DD, YYYY, HH:MM AM/PM' (from news publishedDate)
      - 'X hours/days ago' (from relative displayDate)
      - 'YYYY-MM-DD' / ISO strings
    """
    if date_str is None or pd.isna(date_str):
        return None
    s = str(date_str).strip()
    if not s or s.lower() in ["none", "nan", "null", "unknown"]:
        return None

    if base_time is None:
        base_time = datetime.now()

    # Relative date handling
    m_rel = re.match(r"(\d+)\s+(hour|minute|day|week|month)s?\s+ago", s, re.IGNORECASE)
    if m_rel:
        qty = int(m_rel.group(1))
        unit = m_rel.group(2).lower()
        if unit == "minute":
            return base_time - timedelta(minutes=qty)
        elif unit == "hour":
            return base_time - timedelta(hours=qty)
        elif unit == "day":
            return base_time - timedelta(days=qty)
        elif unit == "week":
            return base_time - timedelta(weeks=qty)
        elif unit == "month":
            return base_time - timedelta(days=qty * 30)

    # Standard formats
    for fmt in [
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y, %I:%M %p",
        "%B %d, %Y",
        "%d %B %Y",
    ]:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass

    try:
        return date_parser.parse(s)
    except Exception:
        return None


def extract_spec_val(specs_summary: List[Dict[str, Any]], key_patterns: List[str]) -> Optional[str]:
    """Helper to extract a specification value from CarWale specsSummary list."""
    if not specs_summary:
        return None
    for sp in specs_summary:
        item_name = sp.get("itemName", "").lower()
        for pat in key_patterns:
            if pat in item_name:
                val = sp.get("value")
                if val is not None and str(val).strip():
                    return str(val).strip()
    return None


def extract_feature_val(feature_specs: List[Dict[str, Any]], key_patterns: List[str]) -> Optional[str]:
    """Helper to extract a feature value from featureSpecs list."""
    if not feature_specs:
        return None
    for fs in feature_specs:
        f_name = str(fs.get("featureName") or fs.get("itemName") or "").lower()
        for pat in key_patterns:
            if pat in f_name:
                val = fs.get("value")
                if val is not None and str(val).strip():
                    return str(val).strip()
    return None


class CarWaleClient:
    """
    HTTP Client with polite delays, timeouts, retries with exponential backoff,
    and structured error tracking.
    """

    def __init__(
        self,
        request_delay: float = 0.6,
        timeout: int = 15,
        max_retries: int = 3,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.errors: List[Dict[str, Any]] = []
        self.visited_urls: Set[str] = set()

    def get(self, url: str, operation: str = "fetch_page") -> Optional[str]:
        """Fetches a URL with rate limiting, timeouts, and bounded retries."""
        if url in self.visited_urls:
            logger.debug(f"Skipping already visited URL: {url}")

        for attempt in range(1, self.max_retries + 1):
            try:
                time.sleep(self.request_delay + random.uniform(0.05, 0.15))
                resp = self.session.get(url, timeout=self.timeout)

                if resp.status_code == 200:
                    self.visited_urls.add(url)
                    return resp.text

                # Check for anti-bot or access blocking
                if resp.status_code in [401, 403]:
                    err_msg = f"Access blocked or forbidden (HTTP {resp.status_code})"
                    logger.error(f"{err_msg} on {url}. Stopping affected operation.")
                    self.log_error(url, operation, "ACCESS_BLOCKED", err_msg)
                    return None

                if resp.status_code == 404:
                    self.log_error(url, operation, "NOT_FOUND", f"Page not found (HTTP 404)")
                    return None

                if resp.status_code == 410:
                    self.log_error(url, operation, "GONE", f"Page gone (HTTP 410)")
                    return None

                # Transient server errors: retry with backoff
                if resp.status_code in [429, 500, 502, 503, 504]:
                    backoff = (2 ** attempt) + random.uniform(0.1, 0.5)
                    logger.warning(f"HTTP {resp.status_code} on {url}, retrying in {backoff:.1f}s (attempt {attempt}/{self.max_retries})")
                    time.sleep(backoff)
                    continue

                self.log_error(url, operation, f"HTTP_{resp.status_code}", f"Unexpected HTTP status {resp.status_code}")
                return None

            except requests.exceptions.Timeout as e:
                backoff = (2 ** attempt) + random.uniform(0.1, 0.5)
                logger.warning(f"Timeout on {url}, retrying in {backoff:.1f}s: {e}")
                if attempt == self.max_retries:
                    self.log_error(url, operation, "TIMEOUT", str(e))
                time.sleep(backoff)
            except requests.exceptions.RequestException as e:
                backoff = (2 ** attempt) + random.uniform(0.1, 0.5)
                logger.warning(f"Request exception on {url}, retrying: {e}")
                if attempt == self.max_retries:
                    self.log_error(url, operation, "REQUEST_EXCEPTION", str(e))
                time.sleep(backoff)
            except Exception as e:
                self.log_error(url, operation, "UNEXPECTED_ERROR", str(e))
                return None

        return None

    def log_error(self, url: str, operation: str, error_category: str, error_message: str):
        """Records an error to the structured error log."""
        self.errors.append({
            "url": url,
            "operation": operation,
            "error_category": error_category,
            "error_message": error_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


class CatalogDeduplicator:
    """
    Loads existing AutoAI datasets (current, upcoming, raw, archive, ML)
    and classifies candidate records as NEW_MODEL, NEW_VARIANT, FACELIFT,
    SPECIAL_EDITION, UPCOMING, ANNOUNCED, or EXISTING.
    """

    def __init__(self, data_dir: Path, ml_data_dir: Path):
        self.data_dir = data_dir
        self.ml_data_dir = ml_data_dir
        self.existing_models: Set[Tuple[str, str]] = set()
        self.existing_variants: Set[Tuple[str, str, str]] = set()
        self.upcoming_models: Set[Tuple[str, str]] = set()
        self.existing_urls: Set[str] = set()
        self.catalog_stats = {
            "current_records": 0,
            "upcoming_records": 0,
            "archive_records": 0,
            "raw_records": 0,
            "ml_records": 0,
        }
        self.load_catalogs()

    def _normalize_key(self, brand: Any, model: Any, variant: Any = None) -> Tuple[str, ...]:
        b = normalize_brand_name(brand).lower()
        m = normalize_model_name(model).lower()
        if variant is not None:
            v = (normalize_variant_name(variant) or "").lower()
            return (b, m, v)
        return (b, m)

    def load_catalogs(self):
        """Loads and indexes all existing catalog files."""
        # 1. cars_main.csv / cars_current.csv
        p_main = self.data_dir / "cars_main.csv"
        p_current = p_main if p_main.exists() else (self.data_dir / "cars_current.csv")
        if p_current.exists():
            try:
                df = pd.read_csv(p_current)
                self.catalog_stats["current_records"] = len(df)
                for _, r in df.iterrows():
                    m_key = self._normalize_key(r.get("brand"), r.get("model"))
                    self.existing_models.add(m_key)
                    v_key = self._normalize_key(r.get("brand"), r.get("model"), r.get("variant"))
                    self.existing_variants.add(v_key)
                    if pd.notna(r.get("model_url")):
                        self.existing_urls.add(str(r.get("model_url")).strip().rstrip("/"))
                    if pd.notna(r.get("variant_url")):
                        self.existing_urls.add(str(r.get("variant_url")).strip().rstrip("/"))
                logger.info(f"Loaded {len(df)} current records from {p_current.name}")
            except Exception as e:
                logger.warning(f"Error loading {p_current}: {e}")

        # 2. cars_upcoming.csv
        p_upcoming = self.data_dir / "cars_upcoming.csv"
        if p_upcoming.exists():
            try:
                df = pd.read_csv(p_upcoming)
                self.catalog_stats["upcoming_records"] = len(df)
                for _, r in df.iterrows():
                    m_key = self._normalize_key(r.get("brand"), r.get("model"))
                    self.upcoming_models.add(m_key)
                    if pd.notna(r.get("variant")) and str(r.get("variant")).strip():
                        v_key = self._normalize_key(r.get("brand"), r.get("model"), r.get("variant"))
                        self.existing_variants.add(v_key)
                logger.info(f"Loaded {len(df)} upcoming records from {p_upcoming.name}")
            except Exception as e:
                logger.warning(f"Error loading {p_upcoming}: {e}")

        # 3. cars_india_full.csv / cars_carwale_raw.csv
        p_raw = self.data_dir / "cars_carwale_raw.csv"
        if p_raw.exists():
            try:
                df = pd.read_csv(p_raw)
                self.catalog_stats["raw_records"] = len(df)
                for _, r in df.iterrows():
                    m_key = self._normalize_key(r.get("brand"), r.get("model"))
                    self.existing_models.add(m_key)
                    v_key = self._normalize_key(r.get("brand"), r.get("model"), r.get("variant"))
                    self.existing_variants.add(v_key)
            except Exception as e:
                logger.warning(f"Error loading {p_raw}: {e}")

        # 4. cars_ml_clean.csv
        p_ml = self.ml_data_dir / "cars_ml_clean.csv"
        if p_ml.exists():
            try:
                df = pd.read_csv(p_ml)
                self.catalog_stats["ml_records"] = len(df)
                for _, r in df.iterrows():
                    m_key = self._normalize_key(r.get("brand"), r.get("model"))
                    self.existing_models.add(m_key)
                    v_key = self._normalize_key(r.get("brand"), r.get("model"), r.get("variant"))
                    self.existing_variants.add(v_key)
            except Exception as e:
                logger.warning(f"Error loading {p_ml}: {e}")

    def classify_and_deduplicate(
        self,
        brand: str,
        model: str,
        variant: Optional[str],
        launch_date: Optional[datetime],
        cutoff_date: Optional[datetime],
        status: str,
        is_facelift: bool = False,
        is_special_edition: bool = False,
        model_url: Optional[str] = None,
        variant_url: Optional[str] = None,
        article_title: Optional[str] = None,
    ) -> Tuple[str, str, bool]:
        """
        Classifies discovery and checks for duplication against the existing catalog.
        Returns: (record_type, explanation, is_new_entry)
        """
        norm_brand = normalize_brand_name(brand)
        norm_model = normalize_model_name(model)
        norm_variant = normalize_variant_name(variant)

        m_key = self._normalize_key(norm_brand, norm_model)
        v_key = self._normalize_key(norm_brand, norm_model, norm_variant)

        title_lower = (article_title or "").lower()

        # Check for upcoming or unlaunched indications
        if status.upper() in ["UPCOMING", "UNVEILED"] or "unveiled" in title_lower or "to debut" in title_lower or "to be launched" in title_lower:
            if "officially unveiled" in title_lower or "unveiled" in title_lower:
                return (RECORD_TYPE_ANNOUNCED, "Vehicle unveiled without confirmed production market launch", False)
            return (RECORD_TYPE_UPCOMING, "Vehicle listed as upcoming or unlaunched", False)

        # Check for special edition
        if is_special_edition or "special edition" in title_lower or "edition launched" in title_lower:
            return (RECORD_TYPE_SPECIAL_EDITION, f"Special edition launch for {norm_brand} {norm_model}", True)

        # Check for facelift
        if is_facelift or "facelift" in title_lower or "facelift" in norm_model.lower():
            return (RECORD_TYPE_FACELIFT, f"Facelift release for {norm_brand} {norm_model}", True)

        # Check for Model Year Update
        if any(my in title_lower for my in ["my26", "my27", "2026 update", "2027 update", "model year"]):
            return (RECORD_TYPE_MODEL_YEAR_UPDATE, f"Model-year update for {norm_brand} {norm_model}", True)

        # Check if model is entirely new
        if m_key not in self.existing_models:
            if m_key in self.upcoming_models:
                return (RECORD_TYPE_NEW_MODEL, f"Formerly upcoming model now officially launched in India", True)
            return (RECORD_TYPE_NEW_MODEL, f"Genuinely new model not present in existing AutoAI catalog", True)

        # Model exists in catalog. Check variant.
        if norm_variant and v_key not in self.existing_variants:
            return (RECORD_TYPE_NEW_VARIANT, f"Newly launched variant for existing model {norm_brand} {norm_model}", True)

        # Variant already existed in catalog.
        # If it was launched strictly after cutoff_date, it may be a revised edition or refreshed release.
        if launch_date and cutoff_date and launch_date > cutoff_date:
            return (RECORD_TYPE_NEW_VARIANT, f"Refreshed release with launch date {launch_date.strftime('%Y-%m-%d')} post-dating catalog cutoff", True)

        # Otherwise, this is a duplicate of an existing record from before the cutoff date.
        return (RECORD_TYPE_EXISTING, f"Matches existing catalog entry ({norm_brand} {norm_model} {norm_variant})", False)


class CarWaleIncrementalScraper:
    """
    Main incremental scraper engine orchestrating discovery, extraction,
    normalization, deduplication, validation, and reporting.
    """

    def __init__(
        self,
        base_dir: Path,
        output_dir: Optional[Path] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        dry_run: bool = False,
        max_pages: int = 10,
        max_articles: int = 30,
        request_delay: float = 0.6,
    ):
        self.base_dir = base_dir
        self.data_dir = base_dir / "backend" / "data"
        self.ml_data_dir = base_dir / "backend" / "ml" / "data"
        self.output_dir = output_dir or (self.ml_data_dir / "new_launches")
        self.dry_run = dry_run
        self.max_pages = max_pages
        self.max_articles = max_articles

        self.client = CarWaleClient(request_delay=request_delay)
        self.deduplicator = CatalogDeduplicator(self.data_dir, self.ml_data_dir)

        # Establish date range
        self.cutoff_date, self.cutoff_established = self._resolve_start_date(start_date)
        self.end_date = self._resolve_end_date(end_date)

        # Metrics & reporting containers
        self.metrics = {
            "scrape_timestamp": datetime.now(timezone.utc).isoformat(),
            "requested_date_range": {
                "start": start_date,
                "end": end_date,
            },
            "actual_date_cutoff": self.cutoff_date.isoformat() if self.cutoff_date else None,
            "cutoff_date_established": self.cutoff_established,
            "source_website": "https://www.carwale.com",
            "scraper_version": SCRAPER_VERSION,
            "listing_pages_examined": 0,
            "news_articles_examined": 0,
            "detail_pages_examined": 0,
            "total_discovered_records": 0,
            "total_validated_records": 0,
            "new_models_discovered": 0,
            "new_variants_discovered": 0,
            "facelifts_discovered": 0,
            "special_editions_discovered": 0,
            "existing_records_matched": 0,
            "duplicates_removed": 0,
            "records_excluded": 0,
            "failed_requests": 0,
            "output_filenames": {
                "raw_dataset": "cars_new_launches_raw.csv",
                "validated_dataset": "cars_new_launches.csv",
                "upcoming_dataset": "cars_new_upcoming.csv",
                "metadata": "scraping_metadata.json",
                "errors": "scraping_errors.csv",
                "quality_report": "data_quality_report.json",
                "quality_issues": "data_quality_issues.csv",
            },
        }

        self.raw_records: List[Dict[str, Any]] = []
        self.validated_records: List[Dict[str, Any]] = []
        self.upcoming_records: List[Dict[str, Any]] = []
        self.excluded_records: List[Dict[str, Any]] = []
        self.discovered_model_urls: Set[str] = set()

    def _resolve_start_date(self, start_date_arg: Optional[str]) -> Tuple[Optional[datetime], bool]:
        """Resolves the initial cutoff date from argument or import metadata."""
        if start_date_arg:
            try:
                parsed = parse_carwale_date(start_date_arg)
                if parsed:
                    logger.info(f"Using user-specified start date: {parsed.isoformat()}")
                    return (parsed, True)
            except Exception as e:
                logger.warning(f"Could not parse specified start date '{start_date_arg}': {e}")

        # Look up last successful collection date from import_metadata.json
        meta_file = self.data_dir / "import_metadata.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                last_import = meta.get("last_successful_import")
                if last_import:
                    parsed = parse_carwale_date(last_import)
                    if parsed:
                        logger.info(f"Established cutoff date from import_metadata.json: {parsed.isoformat()}")
                        return (parsed, True)
            except Exception as e:
                logger.warning(f"Error reading {meta_file}: {e}")

        # Fallback check in data_quality_report.json
        dqr_file = self.data_dir / "data_quality_report.json"
        if dqr_file.exists():
            try:
                dqr = json.loads(dqr_file.read_text(encoding="utf-8"))
                last_sync = dqr.get("last_sync_timestamp")
                if last_sync:
                    parsed = parse_carwale_date(last_sync)
                    if parsed:
                        logger.info(f"Established cutoff date from data_quality_report.json: {parsed.isoformat()}")
                        return (parsed, True)
            except Exception as e:
                logger.warning(f"Error reading {dqr_file}: {e}")

        logger.warning("LIMITATION: Previous collection date could not be established from existing metadata. Will compare records against catalog.")
        return (None, False)

    def _resolve_end_date(self, end_date_arg: Optional[str]) -> datetime:
        """Resolves end date boundary."""
        if end_date_arg:
            parsed = parse_carwale_date(end_date_arg)
            if parsed:
                return parsed
        return datetime.now()

    def _extract_initial_state(self, html: str) -> Optional[Dict[str, Any]]:
        """Safely parses window.__INITIAL_STATE__ JSON from CarWale HTML."""
        if not html:
            return None
        # 1. Check modern CarWale script id="initial-state"
        m_tag = re.search(r'<script[^>]*id=["\']initial-state["\'][^>]*>(.*?)</script>', html, re.DOTALL)
        if m_tag:
            try:
                return json.loads(m_tag.group(1))
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error in script#initial-state: {e}")
        # 2. Check legacy window.__INITIAL_STATE__ = {...}
        m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*(?:window|\n|</script>|$)", html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error in __INITIAL_STATE__: {e}")
        return None

    def discover_launch_listings(self) -> List[Dict[str, Any]]:
        """
        Discovers vehicles listed on CarWale's /new-car-launches/ section.
        Pages are reverse chronological.
        """
        discovered_launches = []
        logger.info(f"Starting launch listing discovery from {LAUNCHES_START_URL}")

        for page_num in range(1, self.max_pages + 1):
            url = f"{LAUNCHES_START_URL}page/{page_num}/" if page_num > 1 else LAUNCHES_START_URL
            logger.info(f"Examining launch listings page {page_num}: {url}")
            html = self.client.get(url, operation="discover_launch_listings")
            if not html:
                break

            self.metrics["listing_pages_examined"] += 1
            state = self._extract_initial_state(html)
            if not state:
                logger.warning(f"No __INITIAL_STATE__ found on {url}")
                break

            ncl = state.get("newCarLaunches", {})
            recent = ncl.get("recentLaunches", [])
            if not recent:
                logger.info(f"No more launches found on page {page_num}. Ending listing discovery.")
                break

            page_candidates = 0
            stop_early = False

            for item in recent:
                make_mask = item.get("makeMaskingName")
                model_mask = item.get("modelMaskingName")
                make_name = item.get("makeName")
                model_name = item.get("modelName")
                launched_on_str = item.get("launchedOn")
                launch_date = parse_carwale_date(launched_on_str)

                # Check if launch date is older than our cutoff
                if launch_date and self.cutoff_date and launch_date < self.cutoff_date:
                    logger.info(f"Encountered launch date {launch_date.strftime('%Y-%m-%d')} before cutoff {self.cutoff_date.strftime('%Y-%m-%d')}. Ending pagination.")
                    stop_early = True
                    break

                if make_mask and model_mask:
                    model_url = f"{BASE_CARWALE_URL}/{make_mask}-cars/{model_mask}/"
                    discovered_launches.append({
                        "brand": make_name,
                        "model": model_name,
                        "make_mask": make_mask,
                        "model_mask": model_mask,
                        "model_url": model_url,
                        "launch_date": launch_date.isoformat() if launch_date else None,
                        "launch_date_obj": launch_date,
                        "launch_date_type": "EXACT_DATE" if launch_date else "UNKNOWN",
                        "launch_evidence_url": url,
                        "status": "CURRENT" if item.get("status") == 2 else "UPCOMING",
                        "price_overview": item.get("priceOverview", {}),
                        "is_facelift": bool(item.get("faceliftContext") or item.get("faceliftContextPills")),
                        "is_special_edition": bool(item.get("isSpecialVersion")),
                    })
                    page_candidates += 1

            # Capture upcoming cars from page 1 into dedicated upcoming collection
            if page_num == 1:
                upcoming_list = ncl.get("upcomingCars", [])
                for u_item in upcoming_list:
                    u_make = u_item.get("makeName")
                    u_model = u_item.get("modelName")
                    u_make_mask = u_item.get("makeMaskingName")
                    u_model_mask = u_item.get("modelMaskingName")
                    u_date = parse_carwale_date(u_item.get("launchedOn"))
                    u_price_obj = u_item.get("priceOverview", {}) or {}
                    u_price = u_price_obj.get("price")
                    if not u_price or u_price == 0:
                        fmt_p = str(u_price_obj.get("formattedPrice") or "")
                        u_price = parse_numeric(fmt_p)
                        if u_price:
                            fmt_p_lower = fmt_p.lower()
                            if "crore" in fmt_p_lower:
                                u_price = float(u_price) * 10_000_000
                            elif "lakh" in fmt_p_lower or u_price < 1000:
                                u_price = float(u_price) * 100_000

                    if u_make and u_model:
                        u_url = f"{BASE_CARWALE_URL}/{u_make_mask}-cars/{u_model_mask}/" if (u_make_mask and u_model_mask) else url
                        self.upcoming_records.append({
                            "brand": normalize_brand_name(u_make),
                            "model": normalize_model_name(u_model),
                            "variant": u_item.get("rootName") or "Base",
                            "price": u_price,
                            "fuel_type": "Electric" if u_item.get("isElectricVehicle") else None,
                            "transmission": None,
                            "body_type": None,
                            "engine_cc": None,
                            "power": None,
                            "torque": None,
                            "mileage": None,
                            "seating": None,
                            "boot_space": None,
                            "ground_clearance": None,
                            "safety_rating": None,
                            "battery_capacity": None,
                            "range_km": None,
                            "status": "UPCOMING",
                            "source": SOURCE_DOMAIN,
                            "model_url": u_url,
                            "variant_url": u_url,
                            "launch_date": u_date.strftime("%Y-%m-%d") if u_date else None,
                            "launch_date_type": "EXPECTED_DATE",
                            "launch_evidence_url": url,
                            "discovered_at": datetime.now(timezone.utc).isoformat(),
                            "source_last_verified_at": datetime.now(timezone.utc).isoformat(),
                            "record_type": RECORD_TYPE_UPCOMING,
                            "data_quality_status": "VALID_UPCOMING",
                        })
                logger.info(f"Discovered {len(self.upcoming_records)} confirmed upcoming cars from CarWale listings")

            logger.info(f"Found {page_candidates} candidates on listing page {page_num}")
            if stop_early:
                break

        return discovered_launches

    def discover_launch_news(self) -> List[Dict[str, Any]]:
        """
        Discovers vehicle launch announcements, special editions, and variant introductions
        from CarWale's /news/ section.
        """
        news_discoveries = []
        logger.info(f"Starting launch news discovery from {NEWS_START_URL}")

        articles_checked = 0
        pages_to_check = max(1, math.ceil(self.max_articles / 18))

        for page_num in range(1, pages_to_check + 1):
            url = f"{NEWS_START_URL}page/{page_num}/" if page_num > 1 else NEWS_START_URL
            html = self.client.get(url, operation="discover_launch_news")
            if not html:
                break

            state = self._extract_initial_state(html)
            if not state:
                break

            ed = state.get("editorialListing", {})
            articles = ed.get("contentData", [])
            if not articles:
                break

            for a in articles:
                articles_checked += 1
                self.metrics["news_articles_examined"] += 1
                title = a.get("title", "")
                t_lower = title.lower()
                art_rel_url = a.get("url", "")
                art_url = f"{BASE_CARWALE_URL}{art_rel_url}" if art_rel_url.startswith("/") else art_rel_url
                pub_date = parse_carwale_date(a.get("displayDate") or a.get("publishedDate"))

                # Strict filtering: Exclude previews, price hikes, concepts, comparisons
                if any(neg in t_lower for neg in [
                    "to be launched", "to launch", "set to launch", "to debut", "debut in",
                    "officially unveiled", "unveiled in", "unveiled ahead", "spied", "scoop",
                    "vs ", "spec comparison", "first drive", "review", "what is", "why can it fly",
                    "prices hiked", "prices increased", "price hike", "concept", "platform?"
                ]):
                    continue

                # Check if this article signals a verified launch
                is_launch = any(pos in t_lower for pos in [
                    "launched", "launched at", "launched in india", "variant launched",
                    "cng launched", "hybrid launched", "edition launched", "launches"
                ])

                if is_launch:
                    # Fetch article detail to get linked models and exact published date
                    art_html = self.client.get(art_url, operation="fetch_article_detail")
                    if art_html:
                        art_state = self._extract_initial_state(art_html)
                        if art_state:
                            art_det = art_state.get("editorialDetails", {})
                            make_name = art_det.get("makeName")
                            model_name = art_det.get("modelName")
                            make_mask = art_det.get("makeMaskingName")
                            model_mask = art_det.get("modelMaskingName")
                            full_pub_date = parse_carwale_date(art_det.get("publishedDate")) or pub_date

                            if make_name and model_name and make_mask and model_mask:
                                model_url = f"{BASE_CARWALE_URL}/{make_mask}-cars/{model_mask}/"
                                news_discoveries.append({
                                    "brand": make_name,
                                    "model": model_name,
                                    "make_mask": make_mask,
                                    "model_mask": model_mask,
                                    "model_url": model_url,
                                    "launch_date": full_pub_date.isoformat() if full_pub_date else None,
                                    "launch_date_obj": full_pub_date,
                                    "launch_date_type": "EXACT_DATE" if full_pub_date else "ESTIMATED",
                                    "launch_evidence_url": art_url,
                                    "status": "CURRENT",
                                    "price_overview": art_det.get("priceOverview", {}),
                                    "is_facelift": "facelift" in t_lower,
                                    "is_special_edition": "edition" in t_lower,
                                    "article_title": title,
                                })

                if articles_checked >= self.max_articles:
                    break

            if articles_checked >= self.max_articles:
                break

        logger.info(f"Found {len(news_discoveries)} launch-related articles")
        return news_discoveries

    def fetch_model_and_variants(self, discovery: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetches the model detail page for a discovered vehicle, extracting all versions
        and detailed specifications.
        """
        model_url = discovery.get("model_url")
        if not model_url:
            return []

        logger.info(f"Fetching vehicle specifications for {discovery.get('brand')} {discovery.get('model')} at {model_url}")
        html = self.client.get(model_url, operation="fetch_model_specs")
        if not html:
            return []

        self.metrics["detail_pages_examined"] += 1
        state = self._extract_initial_state(html)
        if not state:
            logger.warning(f"No __INITIAL_STATE__ found for model {model_url}")
            return []

        mp = state.get("modelPage", {})
        md = mp.get("modelDetails", {})
        
        # Enhanced body style resolution with multiple fallbacks
        body_type = (
            mp.get("bodyStyleDetail", {}).get("name")
            or (mp.get("bodyStyleSlug", {}).get("name") if isinstance(mp.get("bodyStyleSlug"), dict) else mp.get("bodyStyleSlug"))
            or md.get("bodyStyleName")
            or mp.get("similarBodyStyleCars", {}).get("bodyStyleName")
            or mp.get("bodyStyle")
        )
        if not body_type and html:
            for s_match in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
                try:
                    jd = json.loads(s_match.group(1))
                    for node in jd.get("@graph", []):
                        if node.get("@type") == "Car" and node.get("bodyType"):
                            body_type = node.get("bodyType")
                            break
                    if body_type:
                        break
                except Exception:
                    pass

        versions = mp.get("versions", [])

        make_name = discovery.get("brand") or md.get("makeName")
        model_name = discovery.get("model") or md.get("modelName")
        make_mask = discovery.get("make_mask") or md.get("makeMaskingName")
        model_mask = discovery.get("model_mask") or md.get("modelMaskingName")

        is_facelift = discovery.get("is_facelift", False) or bool(mp.get("isDiscontinuedWithFaceliftModel")) or bool(mp.get("faceliftContext"))
        is_special = discovery.get("is_special_edition", False)

        extracted_variants = []

        if versions:
            for v in versions:
                v_name = v.get("versionName") or v.get("trimName") or v.get("displayName")
                v_mask = v.get("versionMaskingName") or ""
                v_url = f"{BASE_CARWALE_URL}/{make_mask}-cars/{model_mask}/{v_mask}/" if v_mask else model_url

                # Price extraction
                price_overview = v.get("priceOverview", {}) or {}
                price_val = price_overview.get("price")
                if not price_val or price_val == 0:
                    price_val = v.get("price") or v.get("priceNumeric")

                specs = v.get("specsSummary", []) or []
                features = v.get("featureSpecs", []) or []

                engine_cc = extract_spec_val(specs, ["displacement", "engine capacity"])
                power = extract_spec_val(specs, ["power", "max engine power", "max power"])
                torque = extract_spec_val(specs, ["torque", "max engine torque", "max torque"])
                mileage = extract_spec_val(specs, ["mileage"])
                fuel = extract_spec_val(specs, ["fuel type", "fuel"]) or v.get("fuelName")
                transmission = extract_spec_val(specs, ["transmission type", "transmission"]) or v.get("transmissionName")
                seating = extract_spec_val(specs, ["seating capacity", "seating"]) or extract_feature_val(features, ["seating capacity", "seating"])
                boot = extract_spec_val(specs, ["boot space", "boot", "trunk"]) or extract_feature_val(features, ["boot space", "boot"])
                gc = extract_spec_val(specs, ["ground clearance", "clearance"]) or extract_feature_val(features, ["ground clearance"])
                battery = extract_spec_val(specs, ["battery capacity", "battery"])
                range_km = extract_spec_val(specs, ["driving range", "range"])

                safety = extract_spec_val(specs, ["ncap", "safety"]) or extract_feature_val(features, ["ncap rating", "safety rating"])
                safety_clean = None
                if safety:
                    m_star = re.search(r"(\d+(?:\.\d+)?)\s*Star", str(safety), re.IGNORECASE)
                    if m_star:
                        safety_clean = float(m_star.group(1))
                    else:
                        m_num = re.search(r"(\d+(?:\.\d+)?)", str(safety))
                        if m_num:
                            safety_clean = float(m_num.group(1))

                # Variant-level launch date
                v_launched_on = v.get("launchedOn")
                v_launch_date = parse_carwale_date(v_launched_on) if v_launched_on else discovery.get("launch_date_obj")

                fuel_norm = normalize_fuel_type(fuel)
                if v_name and (not fuel_norm or fuel_norm == "Electric"):
                    v_lower = v_name.lower()
                    if "plug-in hybrid" in v_lower or "phev" in v_lower:
                        fuel_norm = "Plug-in Hybrid"
                    elif "hybrid" in v_lower:
                        fuel_norm = "Hybrid"

                extracted_variants.append({
                    "brand": make_name,
                    "model": model_name,
                    "variant": v_name,
                    "price": parse_numeric(price_val),
                    "fuel_type": fuel_norm,
                    "transmission": normalize_transmission(transmission),
                    "body_type": normalize_body_type(body_type),
                    "engine_cc": parse_numeric(engine_cc),
                    "power": parse_numeric(power),
                    "torque": parse_numeric(torque),
                    "mileage": parse_numeric(mileage),
                    "seating": parse_numeric(seating),
                    "boot_space": parse_numeric(boot),
                    "ground_clearance": parse_numeric(gc),
                    "safety_rating": safety_clean,
                    "battery_capacity": parse_numeric(battery),
                    "range_km": parse_numeric(range_km),
                    "status": "CURRENT",
                    "source": SOURCE_DOMAIN,
                    "model_url": model_url,
                    "variant_url": v_url,
                    "launch_date": v_launch_date.strftime("%Y-%m-%d") if v_launch_date else discovery.get("launch_date"),
                    "launch_date_obj": v_launch_date,
                    "launch_date_type": "EXACT_DATE" if v_launch_date else discovery.get("launch_date_type", "UNKNOWN"),
                    "launch_evidence_url": discovery.get("launch_evidence_url", model_url),
                    "is_facelift": is_facelift,
                    "is_special_edition": is_special or bool(v.get("isSpecialVersion")),
                    "article_title": discovery.get("article_title"),
                    "raw_extracted": {
                        "brand": make_name,
                        "model": model_name,
                        "variant": v_name,
                        "price": price_val,
                        "fuel_type": fuel,
                        "transmission": transmission,
                        "body_type": body_type,
                        "engine_cc": engine_cc,
                        "power": power,
                        "torque": torque,
                        "mileage": mileage,
                        "seating": seating,
                        "boot_space": boot,
                        "ground_clearance": gc,
                        "safety_rating": safety,
                        "battery_capacity": battery,
                        "range_km": range_km,
                        "launchedOn": v_launched_on or discovery.get("launch_date"),
                    }
                })
        else:
            # Model without separate versions (single trim or concept)
            price_val = md.get("basePriceOverview", {}).get("price") or mp.get("minPrice")
            extracted_variants.append({
                "brand": make_name,
                "model": model_name,
                "variant": None,
                "price": parse_numeric(price_val),
                "fuel_type": None,
                "transmission": None,
                "body_type": normalize_body_type(body_type),
                "engine_cc": None,
                "power": None,
                "torque": None,
                "mileage": None,
                "seating": None,
                "boot_space": None,
                "ground_clearance": None,
                "safety_rating": None,
                "battery_capacity": None,
                "range_km": None,
                "status": discovery.get("status", "CURRENT"),
                "source": SOURCE_DOMAIN,
                "model_url": model_url,
                "variant_url": model_url,
                "launch_date": discovery.get("launch_date"),
                "launch_date_obj": discovery.get("launch_date_obj"),
                "launch_date_type": discovery.get("launch_date_type", "UNKNOWN"),
                "launch_evidence_url": discovery.get("launch_evidence_url", model_url),
                "is_facelift": is_facelift,
                "is_special_edition": is_special,
                "article_title": discovery.get("article_title"),
                "raw_extracted": {
                    "brand": make_name,
                    "model": model_name,
                    "variant": None,
                    "price": price_val,
                    "body_type": body_type,
                    "launchedOn": discovery.get("launch_date"),
                }
            })

        return extracted_variants

    def enrich_dimensions(self, record: Dict[str, Any]):
        """
        Optionally enriches boot space and ground clearance by fetching the variant trim page.
        """
        v_url = record.get("variant_url")
        if not v_url or v_url == record.get("model_url") or record.get("boot_space") is not None:
            return

        html = self.client.get(v_url, operation="enrich_variant_dimensions")
        if not html:
            return

        state = self._extract_initial_state(html)
        if not state:
            return

        tp = state.get("trimPage", {})
        sfm = tp.get("specsFeaturesMaster", [])
        for group in sfm:
            for sc in group.get("subCategories", []):
                for item in sc.get("items", []):
                    iname = str(item.get("name") or item.get("title") or item.get("itemName") or "").lower()
                    ival = item.get("value")
                    if not ival:
                        continue
                    if "boot space" in iname or "bootspace" in iname or "boot" in iname:
                        if record.get("boot_space") is None:
                            record["boot_space"] = parse_numeric(ival)
                    elif "ground clearance" in iname or "clearance" in iname:
                        if record.get("ground_clearance") is None:
                            record["ground_clearance"] = parse_numeric(ival)

    def run(self):
        """Executes the complete incremental scraping and validation run."""
        logger.info("=" * 70)
        logger.info(f"Starting AutoAI Incremental Car Launch Scraper v{SCRAPER_VERSION}")
        logger.info(f"Cutoff Date: {self.cutoff_date.isoformat() if self.cutoff_date else 'Not established'}")
        logger.info(f"End Date: {self.end_date.isoformat()}")
        logger.info(f"Dry Run Mode: {self.dry_run}")
        logger.info("=" * 70)

        # Step 1: Discover listing pages
        listing_discoveries = self.discover_launch_listings()

        # Step 2: Discover news launch articles
        news_discoveries = self.discover_launch_news()

        # Combine model discoveries avoiding redundant model URLs
        combined_discoveries: Dict[str, Dict[str, Any]] = {}
        for d in listing_discoveries:
            url = d["model_url"]
            combined_discoveries[url] = d

        for d in news_discoveries:
            url = d["model_url"]
            if url not in combined_discoveries:
                combined_discoveries[url] = d
            else:
                # Merge details (e.g. news might highlight special edition or facelift)
                if d.get("is_special_edition"):
                    combined_discoveries[url]["is_special_edition"] = True
                if d.get("is_facelift"):
                    combined_discoveries[url]["is_facelift"] = True
                if d.get("article_title"):
                    combined_discoveries[url]["article_title"] = d["article_title"]

        logger.info(f"Total unique models to inspect: {len(combined_discoveries)}")

        # Step 3: Fetch model pages and variants
        candidate_records: List[Dict[str, Any]] = []
        for model_url, disc in combined_discoveries.items():
            variants = self.fetch_model_and_variants(disc)
            for v in variants:
                candidate_records.append(v)

        logger.info(f"Extracted {len(candidate_records)} candidate records across {len(combined_discoveries)} models")
        self.metrics["total_discovered_records"] = len(candidate_records)

        # Step 4: Normalization, Deduplication against existing catalog, Classification, and Validation
        now_iso = datetime.now(timezone.utc).isoformat()
        seen_in_batch: Set[Tuple[str, str, str]] = set()

        for rec in candidate_records:
            brand = rec["brand"]
            model = rec["model"]
            variant = rec.get("variant")
            price = rec.get("price")
            status = rec.get("status", "CURRENT")
            launch_date_obj = rec.get("launch_date_obj")

            # Store in raw collection
            raw_entry = copy.deepcopy(rec.get("raw_extracted", {}))
            raw_entry["model_url"] = rec["model_url"]
            raw_entry["variant_url"] = rec["variant_url"]
            raw_entry["discovered_at"] = now_iso
            self.raw_records.append(raw_entry)

            # Check batch deduplication
            batch_key = (
                normalize_brand_name(brand).lower(),
                normalize_model_name(model).lower(),
                (normalize_variant_name(variant) or "").lower(),
            )
            if batch_key in seen_in_batch:
                self.metrics["duplicates_removed"] += 1
                logger.debug(f"Duplicate within current batch removed: {brand} {model} {variant}")
                continue
            seen_in_batch.add(batch_key)

            # Classify against existing catalog
            record_type, explanation, is_new = self.deduplicator.classify_and_deduplicate(
                brand=brand,
                model=model,
                variant=variant,
                launch_date=launch_date_obj,
                cutoff_date=self.cutoff_date,
                status=status,
                is_facelift=rec.get("is_facelift", False),
                is_special_edition=rec.get("is_special_edition", False),
                model_url=rec.get("model_url"),
                variant_url=rec.get("variant_url"),
                article_title=rec.get("article_title"),
            )

            # Populate metadata tracking fields
            rec["record_type"] = record_type
            rec["discovered_at"] = now_iso
            rec["source_last_verified_at"] = now_iso

            # Check if this record should enter final launched dataset
            if not is_new:
                if record_type == RECORD_TYPE_EXISTING:
                    self.metrics["existing_records_matched"] += 1
                else:
                    self.metrics["records_excluded"] += 1
                rec["data_quality_status"] = "EXCLUDED_EXISTING_OR_UPCOMING"
                self.excluded_records.append(rec)
                continue

            if record_type in [RECORD_TYPE_UPCOMING, RECORD_TYPE_ANNOUNCED]:
                self.metrics["records_excluded"] += 1
                rec["data_quality_status"] = "EXCLUDED_UNLAUNCHED"
                self.excluded_records.append(rec)
                continue

            # Validation checks
            data_quality_status = "VALID"

            # Price check
            if price is None or price <= 0:
                data_quality_status = "NEEDS_MANUAL_REVIEW"
            elif price < MIN_CREDIBLE_PRICE or price > MAX_CREDIBLE_PRICE:
                data_quality_status = "SUSPICIOUS_SPECS"

            # Check launch date presence
            if not rec.get("launch_date"):
                if data_quality_status == "VALID":
                    data_quality_status = "NEEDS_MANUAL_REVIEW"

            rec["data_quality_status"] = data_quality_status

            # Count classification metrics
            if record_type == RECORD_TYPE_NEW_MODEL:
                self.metrics["new_models_discovered"] += 1
            elif record_type == RECORD_TYPE_NEW_VARIANT:
                self.metrics["new_variants_discovered"] += 1
            elif record_type == RECORD_TYPE_FACELIFT:
                self.metrics["facelifts_discovered"] += 1
            elif record_type == RECORD_TYPE_SPECIAL_EDITION:
                self.metrics["special_editions_discovered"] += 1

            self.validated_records.append(rec)

        self.metrics["total_validated_records"] = len(self.validated_records)
        self.metrics["failed_requests"] = len(self.client.errors)

        # Generate Data Quality Report
        quality_report = self._generate_data_quality_report()

        # Step 5: Save outputs safely
        if not self.dry_run:
            self._save_artifacts(quality_report)
        else:
            logger.info("DRY-RUN mode enabled: skipping writing to disk.")

        self._print_execution_summary(quality_report)
        return self.validated_records

    def _generate_data_quality_report(self) -> Dict[str, Any]:
        """Builds a comprehensive data quality report."""
        total = len(self.validated_records)
        missing_counts: Dict[str, int] = {}
        for col in BASE_COLUMNS:
            missing_counts[col] = sum(1 for r in self.validated_records if r.get(col) is None or pd.isna(r.get(col)))

        invalid_prices = sum(
            1 for r in self.validated_records
            if r.get("price") is None or r.get("price") <= 0 or r.get("price") < MIN_CREDIBLE_PRICE
        )

        missing_launch_evidence = sum(
            1 for r in self.validated_records
            if not r.get("launch_evidence_url") or not r.get("launch_date")
        )

        suspicious_specs = sum(
            1 for r in self.validated_records
            if r.get("data_quality_status") == "SUSPICIOUS_SPECS"
        )

        needs_review = sum(
            1 for r in self.validated_records
            if r.get("data_quality_status") == "NEEDS_MANUAL_REVIEW"
        )

        return {
            "total_validated_records": total,
            "total_raw_records": len(self.raw_records),
            "total_excluded_records": len(self.excluded_records),
            "missing_values_by_field": missing_counts,
            "duplicate_records_removed": self.metrics["duplicates_removed"],
            "existing_catalog_matches": self.metrics["existing_records_matched"],
            "invalid_prices": invalid_prices,
            "invalid_or_missing_dates": sum(1 for r in self.validated_records if not r.get("launch_date")),
            "missing_launch_evidence": missing_launch_evidence,
            "records_with_uncertain_launch_status": sum(1 for r in self.validated_records if r.get("record_type") == RECORD_TYPE_UNCERTAIN),
            "records_with_suspicious_specifications": suspicious_specs,
            "records_requiring_manual_review": needs_review,
            "excluded_unlaunched_records_count": len(self.excluded_records),
        }

    def _save_artifacts(self, quality_report: Dict[str, Any]):
        """Safely writes all 5 required artifacts using temporary files."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 1. cars_new_launches_raw.csv
        raw_path = self.output_dir / "cars_new_launches_raw.csv"
        raw_tmp = self.output_dir / "cars_new_launches_raw.csv.tmp"
        if self.raw_records:
            keys = list(self.raw_records[0].keys())
            with open(raw_tmp, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(self.raw_records)
            raw_tmp.replace(raw_path)
            logger.info(f"Saved {len(self.raw_records)} raw records to {raw_path}")

        # 2. cars_new_launches.csv
        val_path = self.output_dir / "cars_new_launches.csv"
        val_tmp = self.output_dir / "cars_new_launches.csv.tmp"
        with open(val_tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ALL_COLUMNS)
            writer.writeheader()
            for r in self.validated_records:
                row_dict = {col: ("" if r.get(col) is None else r.get(col)) for col in ALL_COLUMNS}
                writer.writerow(row_dict)
        val_tmp.replace(val_path)
        logger.info(f"Saved {len(self.validated_records)} validated records to {val_path}")

        # 3. scraping_metadata.json
        meta_path = self.output_dir / "scraping_metadata.json"
        meta_tmp = self.output_dir / "scraping_metadata.json.tmp"
        meta_tmp.write_text(json.dumps(self.metrics, indent=2), encoding="utf-8")
        meta_tmp.replace(meta_path)
        logger.info(f"Saved scraping metadata to {meta_path}")

        # 4. scraping_errors.csv
        err_path = self.output_dir / "scraping_errors.csv"
        err_tmp = self.output_dir / "scraping_errors.csv.tmp"
        err_keys = ["url", "operation", "error_category", "error_message", "timestamp"]
        with open(err_tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=err_keys)
            writer.writeheader()
            writer.writerows(self.client.errors)
        err_tmp.replace(err_path)
        logger.info(f"Saved {len(self.client.errors)} scraping errors to {err_path}")

        # 5. cars_new_upcoming.csv (separate upcoming cars dataset)
        up_path = self.output_dir / "cars_new_upcoming.csv"
        up_tmp = self.output_dir / "cars_new_upcoming.csv.tmp"
        with open(up_tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ALL_COLUMNS)
            writer.writeheader()
            for r in self.upcoming_records:
                row_dict = {col: ("" if r.get(col) is None else r.get(col)) for col in ALL_COLUMNS}
                writer.writerow(row_dict)
        up_tmp.replace(up_path)
        logger.info(f"Saved {len(self.upcoming_records)} upcoming records to {up_path}")

        # 6. data_quality_report.json & data_quality_issues.csv
        qr_path = self.output_dir / "data_quality_report.json"
        qr_tmp = self.output_dir / "data_quality_report.json.tmp"
        qr_tmp.write_text(json.dumps(quality_report, indent=2), encoding="utf-8")
        qr_tmp.replace(qr_path)
        logger.info(f"Saved data quality report to {qr_path}")

        # Generate data_quality_issues.csv via DataQualityService if available
        try:
            b_dir = self.base_dir / "backend"
            if str(b_dir) not in sys.path:
                sys.path.insert(0, str(b_dir))
            from app.services.data_quality_service import DataQualityService
            checker = DataQualityService()
            df_val = pd.read_csv(val_path) if val_path.exists() else pd.DataFrame(self.validated_records)
            full_report, issues = checker.validate_dataset(
                df_val,
                dataset_name="cars_new_launches.csv",
                is_new_launches=True,
            )
            issues_path = self.output_dir / "data_quality_issues.csv"
            checker.export_issues_to_csv(issues, issues_path)
            # Merge enhanced metrics into quality report
            full_report["summary_extracted_metrics"] = quality_report
            checker.export_report_to_json(full_report, qr_path)
            logger.info(f"Exported detailed data quality issues to {issues_path}")
        except Exception as e:
            logger.warning(f"DataQualityService export skipped/failed: {e}")

    def _print_execution_summary(self, quality_report: Dict[str, Any]):
        """Prints formatted execution summary to console."""
        logger.info("=" * 70)
        logger.info("INCREMENTAL SCRAPE SUMMARY")
        logger.info(f"Listing pages examined: {self.metrics['listing_pages_examined']}")
        logger.info(f"News articles examined: {self.metrics['news_articles_examined']}")
        logger.info(f"Detail pages examined:  {self.metrics['detail_pages_examined']}")
        logger.info(f"Total discovered records: {self.metrics['total_discovered_records']}")
        logger.info(f"Validated new launches:   {self.metrics['total_validated_records']}")
        logger.info(f"  - New models:          {self.metrics['new_models_discovered']}")
        logger.info(f"  - New variants:        {self.metrics['new_variants_discovered']}")
        logger.info(f"  - Facelifts:           {self.metrics['facelifts_discovered']}")
        logger.info(f"  - Special editions:    {self.metrics['special_editions_discovered']}")
        logger.info(f"Existing catalog matches: {self.metrics['existing_records_matched']}")
        logger.info(f"Duplicates removed:       {self.metrics['duplicates_removed']}")
        logger.info(f"Excluded unlaunched:      {self.metrics['records_excluded']}")
        logger.info(f"Failed HTTP requests:     {self.metrics['failed_requests']}")
        logger.info("=" * 70)


def parse_args():
    parser = argparse.ArgumentParser(
        description="AutoAI Incremental Car Launch Scraper (CarWale Exclusive)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date for launch collection (YYYY-MM-DD). Defaults to last collection date in metadata.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date for launch collection (YYYY-MM-DD). Defaults to current date.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run discovery and validation without writing files to disk.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum number of launch listing pages to examine (default: 5).",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=25,
        help="Maximum number of news articles to examine (default: 25).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom output directory. Defaults to backend/ml/data/new_launches.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    base_dir = Path(__file__).resolve().parent.parent.parent

    output_dir = Path(args.output_dir) if args.output_dir else None

    scraper = CarWaleIncrementalScraper(
        base_dir=base_dir,
        output_dir=output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=args.dry_run,
        max_pages=args.max_pages,
        max_articles=args.max_articles,
    )
    scraper.run()


if __name__ == "__main__":
    main()
