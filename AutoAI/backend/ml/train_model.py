import os
import time
import warnings
import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import (
    train_test_split,
    KFold,
    cross_val_score,
    RandomizedSearchCV
)
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)
from sklearn.ensemble import (
    RandomForestRegressor,
    ExtraTreesRegressor,
    HistGradientBoostingRegressor

)

warnings.filterwarnings("ignore")


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.join(
    BASE_DIR,
    "data",
    "cars_ml_clean.csv"
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "models"
)

os.makedirs(MODEL_DIR, exist_ok=True)


# ============================================================
# CONFIG
# ============================================================

TARGET = "ex_showroom_price"

RANDOM_STATE = 42

TEST_SIZE = 0.20

CV_FOLDS = 5


# ============================================================
# HEADER
# ============================================================

print("=" * 70)
print("AUTOAI ML MODEL TRAINING - V2")
print("=" * 70)

start_time = time.time()


# ============================================================
# LOAD DATA
# ============================================================

print("\n[1/8] Loading dataset...")

df = pd.read_csv(DATA_PATH)

print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")


# ============================================================
# FEATURES
# ============================================================

numeric_features = [
    "engine_cc",
    "power",
    "torque",
    "mileage",
    "seating",
    "boot_space",
    "ground_clearance",
    "safety_rating",
]

categorical_features = [
    "brand",
    "model",
    "fuel_type",
    "transmission",
    "body_type",
    "status",
]


numeric_features = [
    col for col in numeric_features
    if col in df.columns
]

categorical_features = [
    col for col in categorical_features
    if col in df.columns
]

features = numeric_features + categorical_features


print("\nFeatures:")

for feature in features:
    print(" -", feature)

print("\nTarget:")
print(" -", TARGET)


# ============================================================
# CLEAN DATA
# ============================================================

print("\n[2/8] Cleaning dataset...")

df = df.dropna(subset=[TARGET]).copy()

# Remove impossible target values
df = df[df[TARGET] > 0].copy()

X = df[features]
y = df[TARGET]

print(f"Usable rows: {len(df)}")


# ============================================================
# TRAIN / TEST SPLIT
# ============================================================

print("\n[3/8] Creating train/test split...")

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=TEST_SIZE,
    random_state=RANDOM_STATE
)

print(f"Training rows: {len(X_train)}")
print(f"Testing rows:  {len(X_test)}")


# ============================================================
# PREPROCESSOR FOR TREE MODELS
# ============================================================

numeric_transformer = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="median")
        )
    ]
)


categorical_transformer = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="most_frequent")
        ),
        (
            "encoder",
            OneHotEncoder(
                handle_unknown="ignore"
            )
        )
    ]
)


preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            numeric_transformer,
            numeric_features
        ),
        (
            "categorical",
            categorical_transformer,
            categorical_features
        )
    ]
)


# ============================================================
# MODEL 1 - RANDOM FOREST
# ============================================================

print("\n[4/8] Testing Random Forest...")

rf_pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "model",
            RandomForestRegressor(
                n_estimators=500,
                max_depth=None,
                min_samples_split=2,
                min_samples_leaf=1,
                max_features=0.8,
                random_state=RANDOM_STATE,
                n_jobs=-1
            )
        )
    ]
)


cv = KFold(
    n_splits=CV_FOLDS,
    shuffle=True,
    random_state=RANDOM_STATE
)


rf_scores = cross_val_score(
    rf_pipeline,
    X_train,
    y_train,
    cv=cv,
    scoring="neg_mean_absolute_error",
    n_jobs=1
)

rf_mae = -rf_scores.mean()

print(
    f"Random Forest 5-Fold CV MAE: "
    f"₹{rf_mae:,.2f}"
)


# ============================================================
# MODEL 2 - EXTRA TREES
# ============================================================

print("\n[5/8] Testing Extra Trees...")

et_pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "model",
            ExtraTreesRegressor(
                n_estimators=500,
                max_depth=None,
                min_samples_split=2,
                min_samples_leaf=1,
                max_features=0.9,
                random_state=RANDOM_STATE,
                n_jobs=-1
            )
        )
    ]
)


et_scores = cross_val_score(
    et_pipeline,
    X_train,
    y_train,
    cv=cv,
    scoring="neg_mean_absolute_error",
    n_jobs=1
)

et_mae = -et_scores.mean()

print(
    f"Extra Trees 5-Fold CV MAE: "
    f"₹{et_mae:,.2f}"
)


# ============================================================
# MODEL 3 - HISTOGRAM GRADIENT BOOSTING
# ============================================================

print("\n[6/8] Testing HistGradientBoosting...")

# HistGradientBoosting needs dense numeric input.
# We therefore use ordinal encoding for categorical features.

hgb_numeric_transformer = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="median")
        )
    ]
)


hgb_categorical_transformer = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="most_frequent")
        ),
        (
            "encoder",
            OrdinalEncoder(
                handle_unknown="use_encoded_value",
                unknown_value=-1
            )
        )
    ]
)


hgb_preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            hgb_numeric_transformer,
            numeric_features
        ),
        (
            "categorical",
            hgb_categorical_transformer,
            categorical_features
        )
    ]
)


hgb_pipeline = Pipeline(
    steps=[
        (
            "preprocessor",
            hgb_preprocessor
        ),
        (
            "model",
            HistGradientBoostingRegressor(
                max_iter=400,
                learning_rate=0.05,
                max_leaf_nodes=31,
                l2_regularization=1.0,
                random_state=RANDOM_STATE
            )
        )
    ]
)


hgb_scores = cross_val_score(
    hgb_pipeline,
    X_train,
    y_train,
    cv=cv,
    scoring="neg_mean_absolute_error",
    n_jobs=1
)

hgb_mae = -hgb_scores.mean()

print(
    f"HistGradientBoosting 5-Fold CV MAE: "
    f"₹{hgb_mae:,.2f}"
)


# ============================================================
# MODEL COMPARISON
# ============================================================

print("\n" + "=" * 70)
print("MODEL COMPARISON")
print("=" * 70)

results = pd.DataFrame(
    {
        "Model": [
            "Random Forest",
            "Extra Trees",
            "HistGradientBoosting"
        ],
        "CV_MAE": [
            rf_mae,
            et_mae,
            hgb_mae
        ]
    }
)

results = results.sort_values(
    "CV_MAE"
).reset_index(drop=True)

print(
    results.to_string(
        index=False,
        formatters={
            "CV_MAE": lambda x: f"₹{x:,.2f}"
        }
    )
)


# ============================================================
# SELECT TOP MODELS FOR TUNING
# ============================================================

best_model_name = results.iloc[0]["Model"]

print(
    f"\nBest baseline model: {best_model_name}"
)


# ============================================================
# HYPERPARAMETER TUNING
# ============================================================

print("\n[7/8] Hyperparameter tuning...")

if best_model_name == "Random Forest":

    base_pipeline = rf_pipeline

    param_distributions = {
        "model__n_estimators": [
            400,
            600,
            800,
            1000
        ],
        "model__max_depth": [
            None,
            15,
            25,
            35
        ],
        "model__min_samples_split": [
            2,
            4,
            8
        ],
        "model__min_samples_leaf": [
            1,
            2,
            4
        ],
        "model__max_features": [
            0.5,
            0.7,
            0.8,
            1.0
        ]
    }

elif best_model_name == "Extra Trees":

    base_pipeline = et_pipeline

    param_distributions = {
        "model__n_estimators": [
            400,
            600,
            800,
            1000
        ],
        "model__max_depth": [
            None,
            15,
            25,
            35
        ],
        "model__min_samples_split": [
            2,
            4,
            8
        ],
        "model__min_samples_leaf": [
            1,
            2,
            4
        ],
        "model__max_features": [
            0.5,
            0.7,
            0.9,
            1.0
        ]
    }

else:

    base_pipeline = hgb_pipeline

    param_distributions = {
        "model__max_iter": [
            200,
            400,
            600,
            800
        ],
        "model__learning_rate": [
            0.02,
            0.03,
            0.05,
            0.08,
            0.1
        ],
        "model__max_leaf_nodes": [
            15,
            31,
            63,
            127
        ],
        "model__min_samples_leaf": [
            10,
            20,
            30,
            50
        ],
        "model__l2_regularization": [
            0.0,
            0.1,
            1.0,
            5.0
        ]
    }


search = RandomizedSearchCV(
    estimator=base_pipeline,
    param_distributions=param_distributions,
    n_iter=20,
    scoring="neg_mean_absolute_error",
    cv=3,
    random_state=RANDOM_STATE,
    n_jobs=1,
    verbose=2
)


print("\nStarting hyperparameter search...")
print("20 configurations × 3-fold CV")
print("This is the part that may take some time.\n")

search_start = time.time()

search.fit(
    X_train,
    y_train
)

search_time = time.time() - search_start

best_pipeline = search.best_estimator_

print(
    f"\nHyperparameter tuning completed "
    f"in {search_time / 60:.2f} minutes."
)

print("\nBest parameters:")

for key, value in search.best_params_.items():
    print(f" - {key}: {value}")


# ============================================================
# FINAL TEST EVALUATION
# ============================================================

print("\n[8/8] Evaluating final model on unseen test data...")

predictions = best_pipeline.predict(X_test)


mae = mean_absolute_error(
    y_test,
    predictions
)

rmse = np.sqrt(
    mean_squared_error(
        y_test,
        predictions
    )
)

r2 = r2_score(
    y_test,
    predictions
)


# ============================================================
# RESULTS
# ============================================================

print("\n" + "=" * 70)
print("FINAL AUTOAI MODEL RESULTS")
print("=" * 70)

print(f"Model: {best_model_name}")

print(f"\nMAE:")
print(f"₹{mae:,.2f}")

print(f"\nRMSE:")
print(f"₹{rmse:,.2f}")

print(f"\nR² Score:")
print(f"{r2:.4f}")

print(
    f"\nAverage actual price: "
    f"₹{y_test.mean():,.2f}"
)


# ============================================================
# SAVE MODEL
# ============================================================

model_path = os.path.join(
    MODEL_DIR,
    "autoai_price_model.joblib"
)

joblib.dump(
    best_pipeline,
    model_path
)


# Save experiment results
results_path = os.path.join(
    MODEL_DIR,
    "training_results.csv"
)

final_results = pd.DataFrame(
    [
        {
            "model": best_model_name,
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "training_rows": len(X_train),
            "testing_rows": len(X_test),
            "cv_folds": CV_FOLDS,
            "tuning_iterations": 20
        }
    ]
)

final_results.to_csv(
    results_path,
    index=False
)


# ============================================================
# COMPLETE
# ============================================================

total_time = time.time() - start_time

print("\nModel saved to:")
print(model_path)

print("\nTraining results saved to:")
print(results_path)

print(
    f"\nTotal training time: "
    f"{total_time / 60:.2f} minutes"
)

print("\n" + "=" * 70)
print("AUTOAI ML TRAINING COMPLETE")
print("=" * 70)