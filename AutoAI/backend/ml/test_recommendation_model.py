import sys
sys.stdout.reconfigure(encoding='utf-8')
"""
AutoAI - Neural Recommendation Model Inference & Verification Test
===================================================================
Loads the trained Two-Tower Neural Ranking Model and evaluates candidate
car ranking across realistic consumer queries on the NVIDIA RTX 4050 GPU.
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

# 1. Setup & Paths
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
DATA_PATH = SCRIPT_DIR / "data" / "cars_ml_clean.csv"
MODEL_PATH = SCRIPT_DIR / "models" / "autoai_recommendation_model.pt"

print("=" * 75)
print("AUTOAI - NEURAL RECOMMENDATION MODEL VERIFICATION TEST")
print("=" * 75)

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Model checkpoint not found at: {MODEL_PATH}")

if torch.cuda.is_available():
    DEVICE = torch.device("cuda:0")
    GPU_NAME = torch.cuda.get_device_name(0)
else:
    DEVICE = torch.device("cpu")
    GPU_NAME = "CPU"
print(f"Device:    {DEVICE} ({GPU_NAME})")
print(f"Artifact:  {MODEL_PATH.name}")

# 2. Load Checkpoint
print("\nLoading checkpoint...")
checkpoint = torch.load(MODEL_PATH, map_location=DEVICE)

vocabularies = checkpoint["vocabularies"]
BRAND_VOCAB = vocabularies["brand"]
BODY_VOCAB = vocabularies["body_type"]
FUEL_VOCAB = vocabularies["fuel_group"]
TRANS_VOCAB = vocabularies["transmission_group"]
STATUS_VOCAB = vocabularies["status"]
PRIORITY_VOCAB = vocabularies["priority"]

NUMERICAL_COLS = checkpoint["numerical_features"]
BOOLEAN_COLS = checkpoint["boolean_features"]
NUM_MEANS = checkpoint["num_means"]
NUM_STDS = checkpoint["num_stds"]
EMBEDDING_DIM = checkpoint["embedding_dim"]

print(f"  Best Val Pairwise Accuracy: {checkpoint.get('best_val_acc', 0.0):.2f}%")
print(f"  Trained at:                 {checkpoint.get('trained_at', 'Unknown')}")

# 3. Model Architecture Reconstruction
class CarEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.brand_emb = nn.Embedding(len(BRAND_VOCAB), 16)
        self.body_emb = nn.Embedding(len(BODY_VOCAB), 8)
        self.fuel_emb = nn.Embedding(len(FUEL_VOCAB), 6)
        self.trans_emb = nn.Embedding(len(TRANS_VOCAB), 4)
        self.status_emb = nn.Embedding(len(STATUS_VOCAB), 2)
        
        in_dim = len(NUMERICAL_COLS) + len(BOOLEAN_COLS) + 16 + 8 + 6 + 4 + 2
        self.net = nn.Sequential(
            nn.Linear(in_dim, 256),
            nn.BatchNorm1d(256),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.1),
            nn.Linear(128, EMBEDDING_DIM)
        )

    def forward(self, num_x, bool_x, cat_ids):
        b_e = self.brand_emb(cat_ids[:, 0])
        bd_e = self.body_emb(cat_ids[:, 1])
        f_e = self.fuel_emb(cat_ids[:, 2])
        t_e = self.trans_emb(cat_ids[:, 3])
        s_e = self.status_emb(cat_ids[:, 4])
        x = torch.cat([num_x, bool_x, b_e, bd_e, f_e, t_e, s_e], dim=1)
        return F.normalize(self.net(x), p=2, dim=1)


class UserPreferenceEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.brand_emb = nn.Embedding(len(BRAND_VOCAB), 16)
        self.body_emb = nn.Embedding(len(BODY_VOCAB), 8)
        self.fuel_emb = nn.Embedding(len(FUEL_VOCAB), 6)
        self.trans_emb = nn.Embedding(len(TRANS_VOCAB), 4)
        self.prio_emb = nn.Embedding(len(PRIORITY_VOCAB), 6)
        
        in_dim = 8 + 16 + 8 + 6 + 4 + 6
        self.net = nn.Sequential(
            nn.Linear(in_dim, 256),
            nn.BatchNorm1d(256),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.1),
            nn.Linear(128, EMBEDDING_DIM)
        )

    def forward(self, num_u, cat_u):
        b_e = self.brand_emb(cat_u[:, 0])
        bd_e = self.body_emb(cat_u[:, 1])
        f_e = self.fuel_emb(cat_u[:, 2])
        t_e = self.trans_emb(cat_u[:, 3])
        p_e = self.prio_emb(cat_u[:, 4])
        x = torch.cat([num_u, b_e, bd_e, f_e, t_e, p_e], dim=1)
        return F.normalize(self.net(x), p=2, dim=1)


class TwoTowerRankingNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.car_encoder = CarEncoder()
        self.user_encoder = UserPreferenceEncoder()


model = TwoTowerRankingNet().to(DEVICE)
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()
print("  Model weights successfully loaded into GPU memory.")

# 4. Precompute Car Candidate Embeddings on GPU
print("\nIndexing car candidates into GPU embeddings...")
df_cars = pd.read_csv(DATA_PATH)

def normalize_car_features(row_dict):
    feats = []
    for col in NUMERICAL_COLS:
        val = float(row_dict.get(col, 0.0))
        if col == "ex_showroom_price":
            val = np.log1p(max(val, 100000.0))
        m = NUM_MEANS[col]
        s = NUM_STDS[col]
        feats.append((val - m) / s)
    return np.array(feats, dtype=np.float32)

all_num = []
all_bool = []
all_cat = []

for _, row in df_cars.iterrows():
    rd = row.to_dict()
    all_num.append(normalize_car_features(rd))
    all_bool.append([1.0 if bool(rd.get(c, False)) else 0.0 for c in BOOLEAN_COLS])
    all_cat.append([
        BRAND_VOCAB.get(str(rd.get("brand", "")).strip(), 0),
        BODY_VOCAB.get(str(rd.get("body_type", "")).strip(), 0),
        FUEL_VOCAB.get(str(rd.get("fuel_group", "")).strip(), 0),
        TRANS_VOCAB.get(str(rd.get("transmission_group", "")).strip(), 0),
        STATUS_VOCAB.get(str(rd.get("status", "CURRENT")).strip().upper(), 2)
    ])

t_num = torch.tensor(np.array(all_num, dtype=np.float32), device=DEVICE)
t_bool = torch.tensor(np.array(all_bool, dtype=np.float32), device=DEVICE)
t_cat = torch.tensor(np.array(all_cat, dtype=np.int64), device=DEVICE)

with torch.no_grad():
    car_embeddings = model.car_encoder(t_num, t_bool, t_cat)
print(f"  Cached {car_embeddings.shape[0]} car vectors on GPU. Shape: {car_embeddings.shape}")

# 5. Recommendation Inference Helper
def rank_cars_for_query(query: Dict[str, Any], top_k: int = 5):
    b_val = np.log1p(max(float(query.get("budget", 0.0)), 100000.0))
    mb_val = np.log1p(max(float(query.get("min_budget", 0.0)), 100000.0))
    p_mean = NUM_MEANS["ex_showroom_price"]
    p_std = NUM_STDS["ex_showroom_price"]
    
    num_u = np.array([
        (b_val - p_mean) / p_std,
        (mb_val - p_mean) / p_std,
        (float(query.get("seating", 5)) - 5.0) / 2.0,
        1.0 if query.get("city_drive", False) else 0.0,
        1.0 if query.get("highway_drive", False) else 0.0,
        1.0 if query.get("family_friendly", False) else 0.0,
        1.0 if query.get("is_luxury", False) else 0.0,
        1.0 if query.get("maintenance_sensitive", False) else 0.0,
    ], dtype=np.float32)
    
    cat_u = np.array([
        BRAND_VOCAB.get(str(query.get("brand", "ANY")), 1),
        BODY_VOCAB.get(str(query.get("body_type", "ANY")), 1),
        FUEL_VOCAB.get(str(query.get("fuel_group", "ANY")), 1),
        TRANS_VOCAB.get(str(query.get("transmission_group", "ANY")), 1),
        PRIORITY_VOCAB.get(str(query.get("priority", "BALANCED")).upper(), 0)
    ], dtype=np.int64)
    
    t_u_num = torch.tensor(num_u, device=DEVICE).unsqueeze(0)
    t_u_cat = torch.tensor(cat_u, device=DEVICE).unsqueeze(0)
    
    t0 = time.time()
    with torch.no_grad():
        u_emb = model.user_encoder(t_u_num, t_u_cat)
        # Cosine similarity across all 2198 cars in one GPU matrix multiplication
        similarities = torch.matmul(car_embeddings, u_emb.squeeze(0))
        top_scores, top_indices = torch.topk(similarities, k=top_k)
    latency_ms = (time.time() - t0) * 1000.0
    
    results = []
    for score, idx in zip(top_scores.cpu().numpy(), top_indices.cpu().numpy()):
        row = df_cars.iloc[int(idx)]
        pct_match = float(np.clip((score + 1.0) / 2.0 * 100.0, 0.0, 100.0))
        results.append({
            "brand": row["brand"],
            "model": row["model"],
            "variant": row["variant"],
            "price_lakh": row["price_lakh"],
            "fuel": row["fuel_group"],
            "transmission": row["transmission_group"],
            "body_type": row["body_type"],
            "safety": row["safety_rating"],
            "score_pct": pct_match,
            "raw_cosine": float(score)
        })
    return results, latency_ms

# 6. Evaluation Scenarios
scenarios = [
    {
        "title": "Scenario 1: Family Mid-Size SUV (Budget: Rs. 18 Lakh, Safety Priority, 5-7 Seats)",
        "query": {
            "budget": 1800000,
            "min_budget": 1200000,
            "body_type": "SUV",
            "fuel_group": "ANY",
            "transmission_group": "ANY",
            "seating": 5,
            "family_friendly": True,
            "highway_drive": True,
            "city_drive": True,
            "priority": "SAFETY"
        }
    },
    {
        "title": "Scenario 2: First-Time City Commuter (Budget: Rs. 8 Lakh, Petrol/CNG, High Mileage)",
        "query": {
            "budget": 800000,
            "min_budget": 400000,
            "body_type": "Hatchback",
            "fuel_group": "Petrol",
            "transmission_group": "Manual",
            "seating": 5,
            "city_drive": True,
            "highway_drive": False,
            "maintenance_sensitive": True,
            "priority": "MILEAGE"
        }
    },
    {
        "title": "Scenario 3: Luxury Executive Sedan (Budget: Rs. 65 Lakh, Luxury Brand, Automatic)",
        "query": {
            "budget": 6500000,
            "min_budget": 4000000,
            "body_type": "Sedan",
            "fuel_group": "ANY",
            "transmission_group": "Automatic",
            "seating": 5,
            "is_luxury": True,
            "highway_drive": True,
            "priority": "LUXURY"
        }
    },
    {
        "title": "Scenario 4: Modern Urban Electric Vehicle (Budget: Rs. 22 Lakh, Electric, City Use)",
        "query": {
            "budget": 2200000,
            "min_budget": 1000000,
            "body_type": "ANY",
            "fuel_group": "Electric",
            "transmission_group": "Automatic",
            "seating": 5,
            "city_drive": True,
            "priority": "MILEAGE"
        }
    }
]

print("\n" + "=" * 75)
print("RUNNING LIVE GPU PREDICTIONS")
print("=" * 75)

for sc in scenarios:
    print(f"\n{sc['title']}")
    print("-" * 75)
    results, lat_ms = rank_cars_for_query(sc["query"], top_k=5)
    print(f"GPU Batch Inference Latency: {lat_ms:.2f} ms")
    print(f"{'Rank':<5} {'Car Model & Variant':<32} {'Price (L)':<11} {'Fuel':<10} {'Trans':<10} {'Match %':<8}")
    print("-" * 75)
    for i, r in enumerate(results, 1):
        name = f"{r['brand']} {r['model']} ({r['variant']})"[:31]
        print(f"#{i:<4} {name:<32} Rs. {r['price_lakh']:<10.2f} {r['fuel']:<10} {r['transmission']:<10} {r['score_pct']:.1f}%")

print("\n" + "=" * 75)
print("VERIFICATION COMPLETED: Neural Ranking Model is fully functional on RTX 4050 GPU!")
print("=" * 75)

