"""
CarWale Car Data Collector for AutoAI
Sole External Data Source: CarWale (https://www.carwale.com)

Collects all active and upcoming Indian cars, variant-level specifications, and URLs from CarWale.
Produces:
  - backend/data/cars_carwale_raw.csv (Raw collected dataset backup)
  - backend/data/cars_current.csv     (Current active vehicles)
  - backend/data/cars_upcoming.csv    (Upcoming / unreleased vehicles)
  - backend/data/cars_archive.csv     (Discontinued vehicles)
  - backend/data/cars_india_full.csv  (Complete consolidated dataset)
"""

import argparse
import concurrent.futures
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CarWaleCollector")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

RAW_BACKUP_FILE = DATA_DIR / "cars_carwale_raw.csv"
CARS_FULL_FILE = DATA_DIR / "cars_india_full.csv"
CARS_CURRENT_FILE = DATA_DIR / "cars_current.csv"
CARS_UPCOMING_FILE = DATA_DIR / "cars_upcoming.csv"
CARS_ARCHIVE_FILE = DATA_DIR / "cars_archive.csv"

COLUMNS = [
    "brand", "model", "variant", "price", "fuel_type", "transmission",
    "body_type", "engine_cc", "power", "torque", "mileage", "seating",
    "boot_space", "ground_clearance", "safety_rating", "battery_capacity",
    "range_km", "source", "model_url", "variant_url", "status"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BRAND_NAME_MAP = {
    "Tata": "Tata Motors",
    "MG": "MG Motor",
    "Mini": "MINI",
    "Citroen": "Citroën",
    "Ssangyong": "SsangYong",
}


def extract_spec_val(specs_summary: List[Dict[str, Any]], key_patterns: List[str]) -> Optional[str]:
    """Helper to extract specification value from CarWale specsSummary list."""
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
    """Helper to extract feature specification value from featureSpecs."""
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


def clean_numeric_str(val: Any) -> Optional[float]:
    """Extract float from numeric string or return None."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    m = re.search(r"([\d.]+)", s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def fetch_model_variants(make_item: Dict[str, Any], model_item: Dict[str, Any], status_label: str) -> List[Dict[str, Any]]:
    """Fetches a CarWale model page and extracts all individual variants and specs."""
    make_name = make_item.get("makeName", "")
    brand = BRAND_NAME_MAP.get(make_name, make_name)
    
    make_mask = make_item.get("maskingName", "")
    model_mask = model_item.get("maskingName", "")
    model_name = model_item.get("modelName", "")
    
    model_url = f"https://www.carwale.com/{make_mask}-cars/{model_mask}/"
    records = []
    
    try:
        r = requests.get(model_url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            logger.warning(f"Failed to fetch model page: {model_url} (HTTP {r.status_code})")
            return records
            
        soup = BeautifulSoup(r.text, "html.parser")
        state = None
        for s in soup.find_all("script"):
            txt = s.string or s.text or ""
            if "window.__INITIAL_STATE__" in txt:
                m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*(?:window|\n|</script>|$)", txt, re.DOTALL)
                if m:
                    try:
                        state = json.loads(m.group(1))
                    except Exception:
                        pass
                    break
                    
        if not state:
            return records
            
        mp = state.get("modelPage", {})
        md = mp.get("modelDetails", {})
        body_type = md.get("bodyStyleName") or mp.get("bodyStyleDetail", {}).get("bodyStyleName")
        
        versions = mp.get("versions", [])
        if versions:
            for v in versions:
                v_name = v.get("versionName") or v.get("trimName")
                v_mask = v.get("versionMaskingName") or ""
                v_url = f"https://www.carwale.com/{make_mask}-cars/{model_mask}/{v_mask}/" if v_mask else model_url
                
                # Price (INR)
                price_overview = v.get("priceOverview", {}) or {}
                price = price_overview.get("price")
                if not price or price == 0:
                    price = v.get("price") or v.get("priceNumeric")
                    
                specs = v.get("specsSummary", []) or []
                features = v.get("featureSpecs", []) or []
                
                engine_cc = extract_spec_val(specs, ["displacement", "engine capacity"])
                power = extract_spec_val(specs, ["power", "max power"])
                torque = extract_spec_val(specs, ["torque", "max torque"])
                mileage = extract_spec_val(specs, ["mileage"])
                fuel = extract_spec_val(specs, ["fuel type", "fuel"]) or v.get("fuelName")
                transmission = extract_spec_val(specs, ["transmission"]) or v.get("transmissionName")
                seating = extract_spec_val(specs, ["seating capacity", "seating"]) or extract_feature_val(features, ["seating capacity", "seating"])
                boot = extract_spec_val(specs, ["boot space", "boot", "trunk"]) or extract_feature_val(features, ["boot space", "boot"])
                gc = extract_spec_val(specs, ["ground clearance", "clearance"]) or extract_feature_val(features, ["ground clearance"])
                safety = extract_spec_val(specs, ["ncap", "safety"]) or extract_feature_val(features, ["ncap rating", "safety rating"])
                battery = extract_spec_val(specs, ["battery capacity", "battery"])
                range_km = extract_spec_val(specs, ["range", "driving range"])
                
                # Format safety rating cleanly (e.g. '5 Star' -> 5.0)
                safety_clean = None
                if safety:
                    m_star = re.search(r"(\d+(?:\.\d+)?)\s*Star", str(safety), re.IGNORECASE)
                    if m_star:
                        safety_clean = float(m_star.group(1))
                    else:
                        m_num = re.search(r"(\d+(?:\.\d+)?)", str(safety))
                        if m_num:
                            safety_clean = float(m_num.group(1))

                records.append({
                    "brand": brand,
                    "model": model_name,
                    "variant": v_name,
                    "price": clean_numeric_str(price),
                    "fuel_type": fuel.strip() if fuel else None,
                    "transmission": transmission.strip() if transmission else None,
                    "body_type": body_type.strip() if body_type else None,
                    "engine_cc": clean_numeric_str(engine_cc),
                    "power": clean_numeric_str(power),
                    "torque": clean_numeric_str(torque),
                    "mileage": clean_numeric_str(mileage),
                    "seating": clean_numeric_str(seating),
                    "boot_space": clean_numeric_str(boot),
                    "ground_clearance": clean_numeric_str(gc),
                    "safety_rating": safety_clean,
                    "battery_capacity": clean_numeric_str(battery),
                    "range_km": clean_numeric_str(range_km),
                    "source": "carwale.com",
                    "model_url": model_url,
                    "variant_url": v_url,
                    "status": status_label,
                })
        else:
            # Model without individual versions (e.g. upcoming concept or unreleased vehicle)
            price_val = md.get("basePriceOverview", {}).get("price") or mp.get("minPrice")
            records.append({
                "brand": brand,
                "model": model_name,
                "variant": None,
                "price": clean_numeric_str(price_val),
                "fuel_type": None,
                "transmission": None,
                "body_type": body_type.strip() if body_type else None,
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
                "source": "carwale.com",
                "model_url": model_url,
                "variant_url": model_url,
                "status": status_label,
            })
            
    except Exception as e:
        logger.error(f"Error scraping model {model_name} ({model_url}): {e}")
        
    return records


class CarWaleCollector:
    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers
        self.stats = {
            "total_models": 0,
            "total_variants": 0,
            "current_cars": 0,
            "upcoming_cars": 0,
            "discontinued_cars": 0,
            "duplicates_removed": 0,
        }

    def get_all_makes(self) -> List[Dict[str, Any]]:
        """Fetches all vehicle manufacturers from CarWale."""
        logger.info("Fetching all makes from CarWale API...")
        res = requests.get("https://www.carwale.com/api/v1/makes/?isNew=true", headers=HEADERS, timeout=10)
        res.raise_for_status()
        makes = res.json()
        logger.info(f"Found {len(makes)} makes on CarWale.")
        return makes

    def get_models_for_make(self, make_id: int) -> List[Dict[str, Any]]:
        """Fetches all models for a specific make from CarWale."""
        url = f"https://www.carwale.com/api/v1/models/?makeId={make_id}&isNew=true"
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            return res.json()
        return []

    def collect(self, target_brand: Optional[str] = None, include_discontinued: bool = False) -> pd.DataFrame:
        makes = self.get_all_makes()
        if target_brand:
            makes = [m for m in makes if target_brand.lower() in m.get("makeName", "").lower()]
            if not makes:
                logger.error(f"Brand '{target_brand}' not found on CarWale.")
                return pd.DataFrame(columns=COLUMNS)

        tasks = []
        for make in makes:
            make_id = make["makeId"]
            make_name = make["makeName"]
            models = self.get_models_for_make(make_id)
            for m in models:
                st = m.get("status")
                if st == "New":
                    status_label = "CURRENT"
                elif st == "Futuristic":
                    status_label = "UPCOMING"
                elif st == "Discontinued":
                    status_label = "DISCONTINUED"
                else:
                    status_label = "DISCONTINUED"
                
                # By default, collect CURRENT and UPCOMING cars
                if status_label in ["CURRENT", "UPCOMING"] or include_discontinued:
                    tasks.append((make, m, status_label))

        self.stats["total_models"] = len(tasks)
        logger.info(f"Starting extraction for {len(tasks)} models across {len(makes)} brands using {self.max_workers} threads...")

        all_records = []
        completed = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_model = {
                executor.submit(fetch_model_variants, make_item, model_item, st_label): (make_item, model_item)
                for make_item, model_item, st_label in tasks
            }
            
            for future in concurrent.futures.as_completed(future_to_model):
                make_item, model_item = future_to_model[future]
                completed += 1
                try:
                    recs = future.result()
                    if recs:
                        all_records.extend(recs)
                    if completed % 25 == 0 or completed == len(tasks):
                        logger.info(f"Progress: {completed}/{len(tasks)} models processed ({len(all_records)} variants gathered)")
                except Exception as exc:
                    logger.error(f"Model {model_item.get('modelName')} generated exception: {exc}")

        if not all_records:
            logger.warning("No records collected.")
            return pd.DataFrame(columns=COLUMNS)

        df = pd.DataFrame(all_records, columns=COLUMNS)
        
        # Deduplication using (brand, model, variant)
        df["variant_clean"] = df["variant"].fillna("")
        before_dedup = len(df)
        df = df.drop_duplicates(subset=["brand", "model", "variant_clean"], keep="first")
        df = df.drop(columns=["variant_clean"])
        self.stats["duplicates_removed"] = before_dedup - len(df)
        
        self.stats["total_variants"] = len(df)
        self.stats["current_cars"] = len(df[df["status"] == "CURRENT"])
        self.stats["upcoming_cars"] = len(df[df["status"] == "UPCOMING"])
        self.stats["discontinued_cars"] = len(df[df["status"] == "DISCONTINUED"])

        # Save Raw Backup
        df.to_csv(RAW_BACKUP_FILE, index=False, encoding="utf-8")
        logger.info(f"Saved raw backup to {RAW_BACKUP_FILE}")

        # Split into status files
        df_current = df[df["status"] == "CURRENT"].copy()
        df_upcoming = df[df["status"] == "UPCOMING"].copy()
        df_archive = df[df["status"] == "DISCONTINUED"].copy()

        df_current.to_csv(CARS_CURRENT_FILE, index=False, encoding="utf-8")
        df_upcoming.to_csv(CARS_UPCOMING_FILE, index=False, encoding="utf-8")
        df_archive.to_csv(CARS_ARCHIVE_FILE, index=False, encoding="utf-8")
        
        # Save consolidated clean dataset for AutoAI
        df.to_csv(CARS_FULL_FILE, index=False, encoding="utf-8")

        logger.info(f"Generated {CARS_CURRENT_FILE.name} ({len(df_current)} rows)")
        logger.info(f"Generated {CARS_UPCOMING_FILE.name} ({len(df_upcoming)} rows)")
        logger.info(f"Generated {CARS_ARCHIVE_FILE.name} ({len(df_archive)} rows)")
        logger.info(f"Generated {CARS_FULL_FILE.name} ({len(df)} rows)")

        return df


def main():
    parser = argparse.ArgumentParser(description="CarWale Vehicle Dataset Collector")
    parser.add_argument("--brand", type=str, help="Specific brand to scrape (e.g. 'Maruti Suzuki')")
    parser.add_argument("--workers", type=int, default=8, help="Number of concurrent workers")
    parser.add_argument("--all", action="store_true", help="Scrape all active Indian brands")
    args = parser.parse_args()

    collector = CarWaleCollector(max_workers=args.workers)
    start_time = time.time()
    
    df = collector.collect(target_brand=args.brand)
    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("CARWALE COLLECTION SUMMARY")
    print("=" * 60)
    print(f"Total Models Processed:   {collector.stats['total_models']}")
    print(f"Total Variants Preserved: {collector.stats['total_variants']}")
    print(f"CURRENT Cars:             {collector.stats['current_cars']}")
    print(f"UPCOMING Cars:            {collector.stats['upcoming_cars']}")
    print(f"Duplicates Removed:       {collector.stats['duplicates_removed']}")
    print(f"Elapsed Time:             {elapsed:.2f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()