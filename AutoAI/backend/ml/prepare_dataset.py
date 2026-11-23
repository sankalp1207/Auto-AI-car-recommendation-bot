import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MAIN_DATA_PATH = BASE_DIR.parent / "data" / "cars_main.csv"
RAW_DATA_PATH = DATA_DIR / "cars_ml_raw.csv"
OUTPUT = DATA_DIR / "cars_ml_clean.csv"

if MAIN_DATA_PATH.exists():
    INPUT = MAIN_DATA_PATH
elif RAW_DATA_PATH.exists():
    INPUT = RAW_DATA_PATH
elif Path("backend/ml/data/cars_ml_raw.csv").exists():
    INPUT = Path("backend/ml/data/cars_ml_raw.csv")
else:
    raise FileNotFoundError("Source dataset not found.")

df = pd.read_csv(INPUT)

if "ex_showroom_price" not in df.columns and "price" in df.columns:
    df["ex_showroom_price"] = df["price"]

if "id" not in df.columns:
    df["id"] = range(1, len(df) + 1)

# Default synthetic/lifestyle features if not in catalog
if "city_use" not in df.columns:
    df["city_use"] = (df["mileage"].fillna(15) >= 14) | (df["fuel_type"].astype(str).str.contains("Electric|CNG", case=False, na=False)) | (df["seating"].fillna(5) <= 5)
if "highway_use" not in df.columns:
    df["highway_use"] = (df["power"].fillna(100) >= 90) | (df["body_type"].astype(str).str.contains("SUV|Sedan", case=False, na=False))
if "family_friendly" not in df.columns:
    df["family_friendly"] = (df["seating"].fillna(5) >= 5) & (df["boot_space"].fillna(350) >= 280)
if "sunroof" not in df.columns:
    df["sunroof"] = df["ex_showroom_price"].fillna(0) >= 1500000
if "adas" not in df.columns:
    df["adas"] = df["ex_showroom_price"].fillna(0) >= 2000000
if "carplay_androidauto" not in df.columns:
    df["carplay_androidauto"] = True
if "maintenance_cost" not in df.columns:
    df["maintenance_cost"] = np.clip(df["ex_showroom_price"].fillna(1000000) * 0.015, 15000, 75000)
if "resale_rating" not in df.columns:
    reliable_brands = ["Maruti Suzuki", "Toyota", "Honda", "Hyundai"]
    df["resale_rating"] = np.where(df["brand"].isin(reliable_brands), 4.5, 4.0)
if "touchscreen_inches" not in df.columns:
    df["touchscreen_inches"] = np.where(df["ex_showroom_price"].fillna(0) >= 3000000, 12.3, 10.25)
if "year" not in df.columns:
    df["year"] = 2026

print("=== ORIGINAL DATA ===")
print("Rows:", len(df))
print("Columns:", len(df.columns))

# ------------------------------------------------------------------
# 1. Remove non-essential columns that are completely empty
# ------------------------------------------------------------------

essential_columns = set([
    "brand", "model", "variant", "body_type", "fuel_type", "transmission", "status",
    "ex_showroom_price", "price", "engine_cc", "power", "torque", "mileage",
    "seating", "boot_space", "ground_clearance", "safety_rating", "maintenance_cost",
    "resale_rating", "touchscreen_inches", "year", "city_use", "highway_use",
    "family_friendly", "sunroof", "adas", "carplay_androidauto", "id"
])

empty_columns = [
    column for column in df.columns
    if df[column].isna().all() and column not in essential_columns
]

print("\nCompletely empty non-essential columns dropped:")
print(empty_columns)

df = df.drop(columns=empty_columns)

# If essential columns are empty, supply initial baseline before median imputation
if "boot_space" in df.columns and (df["boot_space"].isna().all() or df["boot_space"].nunique() <= 1):
    df["boot_space"] = np.where(df["body_type"].astype(str).str.contains("SUV", case=False), 420.0,
                        np.where(df["body_type"].astype(str).str.contains("Sedan", case=False), 480.0, 300.0))

if "ground_clearance" in df.columns and (df["ground_clearance"].isna().all() or df["ground_clearance"].nunique() <= 1):
    df["ground_clearance"] = np.where(df["body_type"].astype(str).str.contains("SUV", case=False), 190.0,
                             np.where(df["body_type"].astype(str).str.contains("Sedan", case=False), 165.0, 160.0))

# ------------------------------------------------------------------
# 2. Normalize categorical values
# ------------------------------------------------------------------

for column in ["brand", "model", "variant", "body_type", "fuel_type",
               "transmission", "status"]:
    df[column] = df[column].fillna("Unknown").astype(str).str.strip()

# Normalize transmission names into useful categories
def normalize_transmission(value):
    value = value.lower()

    if "manual" in value and "clutchless" not in value:
        return "Manual"

    if "imt" in value or "clutchless" in value:
        return "IMT"

    if "automatic" in value:
        return "Automatic"

    return "Unknown"

df["transmission_group"] = df["transmission"].apply(
    normalize_transmission
)

# Normalize fuel categories
def normalize_fuel(value):
    value = value.lower()

    if "electric" in value and "hybrid" not in value:
        return "Electric"

    if "cng" in value:
        return "CNG"

    if "diesel" in value and "hybrid" not in value:
        return "Diesel"

    if "hybrid" in value:
        return "Hybrid"

    if "petrol" in value:
        return "Petrol"

    return "Unknown"

df["fuel_group"] = df["fuel_type"].apply(normalize_fuel)

# ------------------------------------------------------------------
# 3. Numeric columns
# ------------------------------------------------------------------

numeric_columns = [
    "ex_showroom_price",
    "engine_cc",
    "power",
    "torque",
    "mileage",
    "seating",
    "boot_space",
    "ground_clearance",
    "safety_rating",
    "maintenance_cost",
    "resale_rating",
    "touchscreen_inches",
    "year"
]

for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

# ------------------------------------------------------------------
# 4. Boolean columns
# ------------------------------------------------------------------

boolean_columns = [
    "city_use",
    "highway_use",
    "family_friendly",
    "sunroof",
    "adas",
    "carplay_androidauto"
]

for column in boolean_columns:
    if column in df.columns:
        df[column] = df[column].fillna(False).astype(bool)

# ------------------------------------------------------------------
# 5. Derived features
# ------------------------------------------------------------------

# Price in lakhs makes the feature easier to interpret
df["price_lakh"] = df["ex_showroom_price"] / 100000

# Power-to-engine-size relationship
df["power_per_litre"] = np.where(
    df["engine_cc"] > 0,
    df["power"] / (df["engine_cc"] / 1000),
    np.nan
)

# Torque relative to engine size
df["torque_per_litre"] = np.where(
    df["engine_cc"] > 0,
    df["torque"] / (df["engine_cc"] / 1000),
    np.nan
)

# Practicality score
df["practicality_score"] = (
    df["boot_space"].fillna(df["boot_space"].median()) * 0.4
    + df["seating"].fillna(df["seating"].median()) * 10 * 0.2
    + df["ground_clearance"].fillna(df["ground_clearance"].median()) * 0.4
)

# ------------------------------------------------------------------
# 6. Missing numeric values
# ------------------------------------------------------------------

for column in numeric_columns + [
    "price_lakh",
    "power_per_litre",
    "torque_per_litre",
    "practicality_score"
]:
    if column in df.columns:
        df[column] = df[column].fillna(df[column].median())

# ------------------------------------------------------------------
# 7. Remove impossible values
# ------------------------------------------------------------------

if "ex_showroom_price" in df.columns:
    df = df[df["ex_showroom_price"] > 0]

if "engine_cc" in df.columns:
    df.loc[df["engine_cc"] < 0, "engine_cc"] = np.nan

if "mileage" in df.columns:
    df.loc[df["mileage"] <= 0, "mileage"] = np.nan

# Refill values after cleaning
for column in numeric_columns:
    if column in df.columns:
        df[column] = df[column].fillna(df[column].median())

# ------------------------------------------------------------------
# 8. Save
# ------------------------------------------------------------------

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT, index=False)

print("\n=== CLEAN DATA ===")
print("Rows:", len(df))
print("Columns:", len(df.columns))
print("Saved:", OUTPUT)

print("\nFuel groups:")
print(df["fuel_group"].value_counts())

print("\nTransmission groups:")
print(df["transmission_group"].value_counts())

print("\nRemaining missing values:")
print(df.isna().sum().sort_values(ascending=False).head(15))
