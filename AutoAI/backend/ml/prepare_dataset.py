import pandas as pd
import numpy as np
from pathlib import Path

INPUT = Path("backend/ml/data/cars_ml_raw.csv")
OUTPUT = Path("backend/ml/data/cars_ml_clean.csv")

df = pd.read_csv(INPUT)

print("=== ORIGINAL DATA ===")
print("Rows:", len(df))
print("Columns:", len(df.columns))

# ------------------------------------------------------------------
# 1. Remove columns that are completely empty
# ------------------------------------------------------------------

empty_columns = [
    column for column in df.columns
    if df[column].isna().all()
]

print("\nCompletely empty columns:")
print(empty_columns)

df = df.drop(columns=empty_columns)

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
