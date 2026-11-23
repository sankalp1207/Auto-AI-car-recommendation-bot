"""
AutoAI New Launches API Router
Provides read-only access to newly launched vehicles, upcoming vehicles,
and scraping freshness metadata discovered from CarWale.
"""

import math
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
import pandas as pd

logger = logging.getLogger("LaunchesRouter")

router = APIRouter(
    prefix="/launches",
    tags=["New Launches"]
)

BASE_DIR = Path(__file__).resolve().parents[2]
NEW_LAUNCHES_DIR = BASE_DIR / "ml" / "data" / "new_launches"
LAUNCHES_CSV = NEW_LAUNCHES_DIR / "cars_new_launches.csv"
UPCOMING_CSV = NEW_LAUNCHES_DIR / "cars_new_upcoming.csv"
METADATA_JSON = NEW_LAUNCHES_DIR / "scraping_metadata.json"


def _clean_val(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if pd.isna(v):
        return None
    return v


def _load_csv_records(csv_path: Path) -> List[Dict[str, Any]]:
    """Loads CSV file safely into list of dictionaries with clean numeric/null values."""
    if not csv_path.exists():
        return []
    try:
        df = pd.read_csv(csv_path)
        records = df.to_dict(orient="records")
        cleaned_records = []
        for idx, raw_r in enumerate(records):
            r = {k: _clean_val(v) for k, v in raw_r.items()}
            if "id" not in r or not r["id"]:
                r["id"] = f"{csv_path.stem}_{idx + 1}"
            # Ensure price is clean float
            if r.get("price") is not None:
                try:
                    p_val = float(r["price"])
                    r["price"] = None if (math.isnan(p_val) or math.isinf(p_val)) else p_val
                except (ValueError, TypeError):
                    r["price"] = None
            cleaned_records.append(r)
        return cleaned_records
    except Exception as e:
        logger.error(f"Error loading {csv_path}: {e}")
        return []


def _load_metadata() -> Dict[str, Any]:
    """Loads scraping metadata."""
    if not METADATA_JSON.exists():
        return {
            "source_website": "https://www.carwale.com",
            "last_scraped_at": None,
            "actual_date_cutoff": None,
            "status": "No scraping runs recorded yet",
        }
    try:
        with open(METADATA_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "source_website": data.get("source_website", "https://www.carwale.com"),
                "last_scraped_at": data.get("scrape_timestamp"),
                "actual_date_cutoff": data.get("actual_date_cutoff"),
                "scraper_version": data.get("scraper_version", "1.0.0"),
                "listing_pages_examined": data.get("listing_pages_examined", 0),
                "news_articles_examined": data.get("news_articles_examined", 0),
                "detail_pages_examined": data.get("detail_pages_examined", 0),
                "new_models_discovered": data.get("new_models_discovered", 0),
                "new_variants_discovered": data.get("new_variants_discovered", 0),
                "facelifts_discovered": data.get("facelifts_discovered", 0),
                "special_editions_discovered": data.get("special_editions_discovered", 0),
            }
    except Exception as e:
        logger.warning(f"Error reading {METADATA_JSON}: {e}")
        return {"source_website": "https://www.carwale.com", "status": "Error reading metadata"}


@router.get("")
@router.get("/")
def get_launches(
    tab: str = Query("launched", description="Either 'launched' or 'upcoming'"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    body_type: Optional[str] = Query(None, description="Filter by body type"),
    fuel_type: Optional[str] = Query(None, description="Filter by fuel type"),
    transmission: Optional[str] = Query(None, description="Filter by transmission"),
    min_price: Optional[float] = Query(None, description="Minimum price in INR"),
    max_price: Optional[float] = Query(None, description="Maximum price in INR"),
    search: Optional[str] = Query(None, description="Search by brand, model, or variant"),
    sort_by: str = Query("launch_date_desc", description="Sort order: launch_date_desc, launch_date_asc, price_asc, price_desc, brand_asc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
):
    """
    Returns filtered and sorted vehicles from the new launches or upcoming cars datasets.
    Includes data freshness indicator and aggregate filter options.
    """
    is_upcoming = tab.lower() == "upcoming"
    source_file = UPCOMING_CSV if is_upcoming else LAUNCHES_CSV
    all_items = _load_csv_records(source_file)

    # Filter computation for UI sidebar
    unique_brands = sorted(list({r["brand"] for r in all_items if r.get("brand")}))
    unique_body_types = sorted(list({r["body_type"] for r in all_items if r.get("body_type")}))
    unique_fuel_types = sorted(list({r["fuel_type"] for r in all_items if r.get("fuel_type")}))
    unique_transmissions = sorted(list({r["transmission"] for r in all_items if r.get("transmission")}))

    valid_prices = [r["price"] for r in all_items if r.get("price") is not None and r["price"] > 0]
    price_min = min(valid_prices) if valid_prices else 0.0
    price_max = max(valid_prices) if valid_prices else 0.0

    # Apply filters
    filtered = all_items
    if brand:
        filtered = [r for r in filtered if r.get("brand") and r["brand"].lower() == brand.lower()]

    if body_type:
        filtered = [r for r in filtered if r.get("body_type") and r["body_type"].lower() == body_type.lower()]

    if fuel_type:
        filtered = [r for r in filtered if r.get("fuel_type") and r["fuel_type"].lower() == fuel_type.lower()]

    if transmission:
        filtered = [r for r in filtered if r.get("transmission") and r["transmission"].lower() == transmission.lower()]

    if min_price is not None:
        filtered = [r for r in filtered if r.get("price") is not None and r["price"] >= min_price]

    if max_price is not None:
        filtered = [r for r in filtered if r.get("price") is not None and r["price"] <= max_price]

    if search:
        s_lower = search.strip().lower()
        filtered = [
            r for r in filtered
            if s_lower in str(r.get("brand", "")).lower()
            or s_lower in str(r.get("model", "")).lower()
            or s_lower in str(r.get("variant", "")).lower()
        ]

    # Sorting
    if sort_by == "price_asc":
        filtered.sort(key=lambda x: (x.get("price") is None, x.get("price") or 0))
    elif sort_by == "price_desc":
        filtered.sort(key=lambda x: (x.get("price") is None, x.get("price") or 0), reverse=True)
    elif sort_by == "brand_asc":
        filtered.sort(key=lambda x: (str(x.get("brand", "")).lower(), str(x.get("model", "")).lower()))
    elif sort_by == "launch_date_asc":
        filtered.sort(key=lambda x: str(x.get("launch_date") or ""))
    else:  # launch_date_desc (default)
        filtered.sort(key=lambda x: str(x.get("launch_date") or ""), reverse=True)

    total_count = len(filtered)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = filtered[start_idx:end_idx]

    # Quick stats for header badges
    all_launched = _load_csv_records(LAUNCHES_CSV)
    all_upcoming = _load_csv_records(UPCOMING_CSV)

    stats = {
        "total_launched": len(all_launched),
        "total_upcoming": len(all_upcoming),
        "new_variants": sum(1 for r in all_launched if r.get("record_type") == "NEW_VARIANT"),
        "facelifts": sum(1 for r in all_launched if r.get("record_type") == "FACELIFT"),
        "special_editions": sum(1 for r in all_launched if r.get("record_type") == "SPECIAL_EDITION"),
        "new_models": sum(1 for r in all_launched if r.get("record_type") == "NEW_MODEL"),
    }

    freshness = _load_metadata()

    return {
        "tab": "upcoming" if is_upcoming else "launched",
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "items": paginated_items,
        "stats": stats,
        "freshness": freshness,
        "available_filters": {
            "brands": unique_brands,
            "body_types": unique_body_types,
            "fuel_types": unique_fuel_types,
            "transmissions": unique_transmissions,
            "price_range": {"min": price_min, "max": price_max},
        },
    }


@router.get("/stats")
def get_launches_stats():
    """Returns high-level statistics of newly tracked and upcoming vehicles."""
    all_launched = _load_csv_records(LAUNCHES_CSV)
    all_upcoming = _load_csv_records(UPCOMING_CSV)
    freshness = _load_metadata()

    return {
        "total_new_launches": len(all_launched),
        "total_upcoming_vehicles": len(all_upcoming),
        "new_models_count": sum(1 for r in all_launched if r.get("record_type") == "NEW_MODEL"),
        "new_variants_count": sum(1 for r in all_launched if r.get("record_type") == "NEW_VARIANT"),
        "facelifts_count": sum(1 for r in all_launched if r.get("record_type") == "FACELIFT"),
        "special_editions_count": sum(1 for r in all_launched if r.get("record_type") == "SPECIAL_EDITION"),
        "source": "carwale.com",
        "last_scraped_at": freshness.get("last_scraped_at"),
        "actual_date_cutoff": freshness.get("actual_date_cutoff"),
    }


@router.get("/{item_id}")
def get_launch_detail(item_id: str):
    """Retrieves full specification details for a single newly launched or upcoming vehicle."""
    all_items = _load_csv_records(LAUNCHES_CSV) + _load_csv_records(UPCOMING_CSV)
    for r in all_items:
        if str(r.get("id")) == str(item_id) or str(r.get("model", "")).lower() == item_id.lower():
            return r

    raise HTTPException(status_code=404, detail=f"Vehicle '{item_id}' not found in new launches.")


@router.get("/{item_id}/alternatives")
def get_launch_alternatives(item_id: int):
    """
    Identifies relevant established catalog alternatives for a newly launched vehicle,
    comparing price, specifications, safety, practicality, and 5-year TCO.
    """
    from app.services.alternative_analysis_service import alternative_analysis_service
    result = alternative_analysis_service.get_alternatives_for_launch(item_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No alternatives or launch record found for launch ID {item_id}"
        )
    return result
