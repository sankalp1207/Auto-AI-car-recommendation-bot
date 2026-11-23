"""
AutoAI - Two-Tower Neural Recommendation & Ranking Model
=========================================================
Architecture: Dual-Encoder (User Preference Tower & Car Specification Tower)
Learning Strategy: Two-Tower Metric Learning with Contrastive Pairwise Ranking
Hardware Acceleration: NVIDIA GeForce RTX 4050 Laptop GPU (CUDA)

This model learns a shared 64-dimensional latent embedding space where:
1. User preferences (budget, segment, fuel, transmission, use case, priority)
   are mapped to a user preference vector u in R^64.
2. Car specifications (power, torque, mileage, price, dimensions, ratings, features)
   are mapped to a car representation vector c in R^64.
3. Candidate ranking is computed via cosine similarity cos(u, c) in [-1, 1],
   calibrated to [0, 100]% match score.
"""

import os
import sys
import json
import time
import random
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# ============================================================
# 1. HARDWARE CONFIGURATION & CUDA ENFORCEMENT
# ============================================================

print("=" * 75)
print("AUTOAI - NEURAL RECOMMENDATION & RANKING MODEL TRAINING")
print("=" * 75)

if torch.cuda.is_available():
    DEVICE = torch.device("cuda:0")
    GPU_NAME = torch.cuda.get_device_name(0)
    CUDA_VERSION = torch.version.cuda
    TOTAL_VRAM_GB = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    print(f"\n[HARDWARE ACCELERATION]")
    print(f"  Device:           {DEVICE}")
    print(f"  GPU Detected:     {GPU_NAME}")
    print(f"  Total VRAM:       {TOTAL_VRAM_GB:.2f} GB")
    print(f"  CUDA Version:     {CUDA_VERSION}")
    print(f"  PyTorch Version:  {torch.__version__}")
    print(f"  Status:           NVIDIA GPU Acceleration ACTIVE\n")
else:
    DEVICE = torch.device("cpu")
    GPU_NAME = "CPU"
    CUDA_VERSION = "N/A"
    TOTAL_VRAM_GB = 0.0
    print(f"\n[HARDWARE ACCELERATION]")
    print(f"  Device:           {DEVICE}")
    print(f"  PyTorch Version:  {torch.__version__}")
    print(f"  Status:           CPU Optimization ACTIVE\n")

# Seed everything for reproducibility
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
torch.manual_seed(RANDOM_SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(RANDOM_SEED)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_PATH = SCRIPT_DIR / "data" / "cars_ml_clean.csv"
MODEL_DIR = SCRIPT_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_SAVE_PATH = MODEL_DIR / "autoai_recommendation_model.pt"
METADATA_SAVE_PATH = MODEL_DIR / "recommendation_metadata.json"

# ============================================================
# 2. FEATURE DEFINITIONS & DATA PREPROCESSING
# ============================================================

print("[1/6] Loading and indexing car dataset...")
df_cars = pd.read_csv(DATA_PATH)
print(f"  Loaded {len(df_cars)} car variants from {DATA_PATH.name}")

NUMERICAL_COLS = [
    "ex_showroom_price", "engine_cc", "power", "torque", "mileage",
    "seating", "boot_space", "ground_clearance", "safety_rating",
    "maintenance_cost", "resale_rating", "touchscreen_inches",
    "power_per_litre", "torque_per_litre", "practicality_score"
]

BOOLEAN_COLS = [
    "city_use", "highway_use", "family_friendly",
    "sunroof", "adas", "carplay_androidauto"
]

# Build Categorical Vocabularies
def build_vocab(series: pd.Series, add_any: bool = True) -> Dict[str, int]:
    unique_vals = sorted(series.astype(str).str.strip().unique().tolist())
    vocab = {"<UNK>": 0}
    if add_any:
        vocab["ANY"] = 1
    idx = len(vocab)
    for v in unique_vals:
        if v not in vocab:
            vocab[v] = idx
            idx += 1
    return vocab

BRAND_VOCAB = build_vocab(df_cars["brand"], add_any=True)
BODY_VOCAB = build_vocab(df_cars["body_type"], add_any=True)
FUEL_VOCAB = build_vocab(df_cars["fuel_group"], add_any=True)
TRANS_VOCAB = build_vocab(df_cars["transmission_group"], add_any=True)
STATUS_VOCAB = {"CURRENT": 0, "UPCOMING": 1, "<UNK>": 2}
PRIORITY_VOCAB = {
    "BALANCED": 0, "BUDGET": 1, "MILEAGE": 2, "SAFETY": 3,
    "PERFORMANCE": 4, "LUXURY": 5, "FAMILY": 6
}

# Luxury Brand Set for utility scoring
LUXURY_BRANDS = {
    "mercedes-benz", "mercedes", "bmw", "audi", "porsche",
    "land rover", "jaguar", "volvo", "lexus", "bentley",
    "rolls-royce", "ferrari", "lamborghini", "maserati",
    "aston martin", "mclaren", "lotus", "maybach"
}

# Standardize Numerical Features
num_df = df_cars[NUMERICAL_COLS].copy()
# Price is log1p transformed to handle high skew across economy vs supercars
num_df["ex_showroom_price"] = np.log1p(num_df["ex_showroom_price"].clip(lower=100000))

NUM_MEANS = num_df.mean().to_dict()
NUM_STDS = num_df.std().replace(0, 1.0).to_dict()

def normalize_numerical(row_dict: Dict[str, Any]) -> np.ndarray:
    feats = []
    for col in NUMERICAL_COLS:
        val = float(row_dict.get(col, 0.0))
        if col == "ex_showroom_price":
            val = np.log1p(max(val, 100000.0))
        m = NUM_MEANS[col]
        s = NUM_STDS[col]
        feats.append((val - m) / s)
    return np.array(feats, dtype=np.float32)

# Encode all cars in memory
print("  Vectorizing car specifications into structured tensors...")
encoded_cars = []
for idx, row in df_cars.iterrows():
    r_dict = row.to_dict()
    num_vec = normalize_numerical(r_dict)
    bool_vec = np.array([1.0 if bool(r_dict.get(c, False)) else 0.0 for c in BOOLEAN_COLS], dtype=np.float32)
    cat_ids = [
        BRAND_VOCAB.get(str(r_dict.get("brand", "")).strip(), 0),
        BODY_VOCAB.get(str(r_dict.get("body_type", "")).strip(), 0),
        FUEL_VOCAB.get(str(r_dict.get("fuel_group", "")).strip(), 0),
        TRANS_VOCAB.get(str(r_dict.get("transmission_group", "")).strip(), 0),
        STATUS_VOCAB.get(str(r_dict.get("status", "CURRENT")).strip().upper(), 2)
    ]
    encoded_cars.append({
        "id": int(r_dict.get("id", idx)),
        "brand": str(r_dict.get("brand", "")),
        "model": str(r_dict.get("model", "")),
        "variant": str(r_dict.get("variant", "")),
        "price": float(r_dict.get("ex_showroom_price", 0.0)),
        "seating": int(r_dict.get("seating", 5)),
        "body_type": str(r_dict.get("body_type", "")),
        "fuel_group": str(r_dict.get("fuel_group", "")),
        "transmission_group": str(r_dict.get("transmission_group", "")),
        "safety_rating": float(r_dict.get("safety_rating", 0.0)),
        "mileage": float(r_dict.get("mileage", 0.0)),
        "power": float(r_dict.get("power", 0.0)),
        "num_vec": num_vec,
        "bool_vec": bool_vec,
        "cat_ids": np.array(cat_ids, dtype=np.int64)
    })

# Train / Validation Split of Cars (80% / 20%)
car_indices = list(range(len(encoded_cars)))
random.shuffle(car_indices)
split_idx = int(len(car_indices) * 0.8)
train_car_indices = car_indices[:split_idx]
val_car_indices = car_indices[split_idx:]

train_cars = [encoded_cars[i] for i in train_car_indices]
val_cars = [encoded_cars[i] for i in val_car_indices]
print(f"  Split: {len(train_cars)} Train Cars | {len(val_cars)} Validation Cars")

# ============================================================
# 3. DOMAIN UTILITY FUNCTION & PREFERENCE SIMULATION
# ============================================================

def compute_ground_truth_utility(user: Dict[str, Any], car: Dict[str, Any]) -> float:
    """
    Computes a deterministic clinical/domain utility score in [0, 100]
    based on AutoAI's explicit business rules (score_service.py).
    This serves as ground-truth preference ordering for contrastive training.
    """
    score = 0.0
    budget = user.get("budget", 0.0)
    min_budget = user.get("min_budget", 0.0)
    price = car["price"]

    # 1. Budget Fit (up to 30 pts)
    if budget > 0:
        if price <= budget:
            if min_budget > 0 and price < min_budget:
                score += 10.0
            else:
                # Closer to sweet spot budget without exceeding
                ratio = price / budget
                score += 20.0 + 10.0 * (1.0 - abs(ratio - 0.85))
        else:
            # Penalty proportional to budget overrun
            over = (price - budget) / budget
            score += max(0.0, 20.0 - over * 40.0)
    else:
        score += 20.0

    # 2. Body Type Match (up to 15 pts)
    pref_body = user.get("body_type", "ANY")
    if pref_body != "ANY":
        if pref_body.lower() in car["body_type"].lower():
            score += 15.0
    else:
        score += 8.0

    # 3. Fuel Match (up to 15 pts)
    pref_fuel = user.get("fuel_group", "ANY")
    if pref_fuel != "ANY":
        if pref_fuel.lower() in car["fuel_group"].lower():
            score += 15.0
    else:
        score += 8.0

    # 4. Transmission Match (up to 12 pts)
    pref_trans = user.get("transmission_group", "ANY")
    if pref_trans != "ANY":
        if pref_trans.lower() in car["transmission_group"].lower():
            score += 12.0
    else:
        score += 6.0

    # 5. Seating Match (up to 10 pts)
    pref_seating = user.get("seating", 5)
    if car["seating"] >= pref_seating:
        score += 10.0
    else:
        score += max(0.0, 10.0 - (pref_seating - car["seating"]) * 5.0)

    # 6. Safety Fit (up to 10 pts)
    safety = car["safety_rating"]
    score += min(10.0, safety * 2.0)

    # 7. Priority Alignment (up to 8 pts)
    prio = user.get("priority", "BALANCED")
    if prio == "MILEAGE" and car["mileage"] >= 18.0:
        score += 8.0
    elif prio == "PERFORMANCE" and car["power"] >= 140.0:
        score += 8.0
    elif prio == "SAFETY" and safety >= 4.0:
        score += 8.0
    elif prio == "BUDGET" and budget > 0 and price <= budget * 0.8:
        score += 8.0
    elif prio == "LUXURY" and car["brand"].lower() in LUXURY_BRANDS:
        score += 8.0
    else:
        score += 4.0

    return float(np.clip(score, 0.0, 100.0))

print("\n[2/6] Generating balanced consumer preference pairs...")

def sample_random_user() -> Dict[str, Any]:
    archetypes = ["budget_hatch", "family_suv", "highway_cruiser", "luxury_sedan", "ev_urban", "performance"]
    arch = random.choice(archetypes)
    
    if arch == "budget_hatch":
        budget = random.choice([500000, 650000, 800000, 950000, 1100000])
        return {
            "budget": float(budget),
            "min_budget": float(budget * 0.5),
            "brand": "ANY",
            "body_type": random.choice(["Hatchback", "SUV", "ANY"]),
            "fuel_group": random.choice(["Petrol", "CNG", "ANY"]),
            "transmission_group": random.choice(["Manual", "ANY"]),
            "seating": 5,
            "city_drive": True,
            "highway_drive": False,
            "family_friendly": False,
            "is_luxury": False,
            "maintenance_sensitive": True,
            "priority": "MILEAGE" if random.random() > 0.4 else "BUDGET"
        }
    elif arch == "family_suv":
        budget = random.choice([1200000, 1500000, 1800000, 2200000, 2800000])
        return {
            "budget": float(budget),
            "min_budget": float(budget * 0.6),
            "brand": "ANY",
            "body_type": "SUV",
            "fuel_group": random.choice(["Diesel", "Petrol", "Hybrid", "ANY"]),
            "transmission_group": random.choice(["Automatic", "Manual", "ANY"]),
            "seating": random.choice([5, 7]),
            "city_drive": True,
            "highway_drive": True,
            "family_friendly": True,
            "is_luxury": False,
            "maintenance_sensitive": False,
            "priority": "SAFETY" if random.random() > 0.5 else "FAMILY"
        }
    elif arch == "luxury_sedan":
        budget = random.choice([4500000, 6000000, 8500000, 12000000])
        return {
            "budget": float(budget),
            "min_budget": float(budget * 0.7),
            "brand": "ANY",
            "body_type": random.choice(["Sedan", "SUV", "ANY"]),
            "fuel_group": random.choice(["Petrol", "Electric", "ANY"]),
            "transmission_group": "Automatic",
            "seating": 5,
            "city_drive": True,
            "highway_drive": True,
            "family_friendly": False,
            "is_luxury": True,
            "maintenance_sensitive": False,
            "priority": "LUXURY"
        }
    elif arch == "ev_urban":
        budget = random.choice([1000000, 1500000, 2000000, 2500000])
        return {
            "budget": float(budget),
            "min_budget": 0.0,
            "brand": "ANY",
            "body_type": "ANY",
            "fuel_group": "Electric",
            "transmission_group": "Automatic",
            "seating": 5,
            "city_drive": True,
            "highway_drive": False,
            "family_friendly": False,
            "is_luxury": False,
            "maintenance_sensitive": True,
            "priority": "MILEAGE"
        }
    else:  # performance / highway
        budget = random.choice([2500000, 3500000, 5000000])
        return {
            "budget": float(budget),
            "min_budget": float(budget * 0.5),
            "brand": "ANY",
            "body_type": random.choice(["Sedan", "SUV"]),
            "fuel_group": random.choice(["Petrol", "Diesel"]),
            "transmission_group": "Automatic",
            "seating": 5,
            "city_drive": False,
            "highway_drive": True,
            "family_friendly": False,
            "is_luxury": False,
            "maintenance_sensitive": False,
            "priority": "PERFORMANCE"
        }

def encode_user_vector(u: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """Encodes a user dictionary into continuous numerical & categorical ID vectors."""
    b_val = np.log1p(max(float(u.get("budget", 0.0)), 100000.0))
    mb_val = np.log1p(max(float(u.get("min_budget", 0.0)), 100000.0))
    
    # Scale with price mean/std
    p_mean = NUM_MEANS["ex_showroom_price"]
    p_std = NUM_STDS["ex_showroom_price"]
    
    num_u = [
        (b_val - p_mean) / p_std,
        (mb_val - p_mean) / p_std,
        (float(u.get("seating", 5)) - 5.0) / 2.0,
        1.0 if u.get("city_drive", False) else 0.0,
        1.0 if u.get("highway_drive", False) else 0.0,
        1.0 if u.get("family_friendly", False) else 0.0,
        1.0 if u.get("is_luxury", False) else 0.0,
        1.0 if u.get("maintenance_sensitive", False) else 0.0,
    ]
    
    cat_u = [
        BRAND_VOCAB.get(str(u.get("brand", "ANY")), 1),
        BODY_VOCAB.get(str(u.get("body_type", "ANY")), 1),
        FUEL_VOCAB.get(str(u.get("fuel_group", "ANY")), 1),
        TRANS_VOCAB.get(str(u.get("transmission_group", "ANY")), 1),
        PRIORITY_VOCAB.get(str(u.get("priority", "BALANCED")).upper(), 0)
    ]
    return np.array(num_u, dtype=np.float32), np.array(cat_u, dtype=np.int64)

# Generate Triplet Dataset (User, Positive Car, Negative Car, Utility Margin)
class TripletRankingDataset(Dataset):
    def __init__(self, cars_pool: List[Dict[str, Any]], num_samples: int = 15000):
        self.samples = []
        n_cars = len(cars_pool)
        
        for _ in range(num_samples):
            user = sample_random_user()
            num_u, cat_u = encode_user_vector(user)
            
            # Candidate evaluation across a random sub-pool
            candidate_indices = random.sample(range(n_cars), min(25, n_cars))
            scored = []
            for ci in candidate_indices:
                car = cars_pool[ci]
                util = compute_ground_truth_utility(user, car)
                scored.append((util, car))
            
            scored.sort(key=lambda x: x[0], reverse=True)
            pos_util, pos_car = scored[0]
            neg_util, neg_car = scored[-1]
            
            # Meaningful contrast margin gap
            margin_gap = (pos_util - neg_util) / 100.0
            if margin_gap >= 0.15:  # At least 15 points utility difference
                self.samples.append({
                    "u_num": num_u,
                    "u_cat": cat_u,
                    "pos_num": pos_car["num_vec"],
                    "pos_bool": pos_car["bool_vec"],
                    "pos_cat": pos_car["cat_ids"],
                    "neg_num": neg_car["num_vec"],
                    "neg_bool": neg_car["bool_vec"],
                    "neg_cat": neg_car["cat_ids"],
                    "pos_score": float(pos_util / 100.0),
                    "neg_score": float(neg_util / 100.0),
                    "margin": float(margin_gap)
                })

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        return (
            torch.tensor(s["u_num"], dtype=torch.float32),
            torch.tensor(s["u_cat"], dtype=torch.long),
            torch.tensor(s["pos_num"], dtype=torch.float32),
            torch.tensor(s["pos_bool"], dtype=torch.float32),
            torch.tensor(s["pos_cat"], dtype=torch.long),
            torch.tensor(s["neg_num"], dtype=torch.float32),
            torch.tensor(s["neg_bool"], dtype=torch.float32),
            torch.tensor(s["neg_cat"], dtype=torch.long),
            torch.tensor(s["pos_score"], dtype=torch.float32),
            torch.tensor(s["margin"], dtype=torch.float32)
        )

train_dataset = TripletRankingDataset(train_cars, num_samples=16000)
val_dataset = TripletRankingDataset(val_cars, num_samples=3200)

BATCH_SIZE = 128
pin_mem = torch.cuda.is_available()
train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, pin_memory=pin_mem)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, pin_memory=pin_mem)

print(f"  Training Triplets:   {len(train_dataset)} pairs ({len(train_loader)} batches)")
print(f"  Validation Triplets: {len(val_dataset)} pairs ({len(val_loader)} batches)")

# ============================================================
# 4. NEURAL NETWORK ARCHITECTURE: TWO-TOWER RANKING NET
# ============================================================

print("\n[3/6] Initializing Two-Tower Neural Network architecture...")

EMBEDDING_DIM = 64

class CarEncoder(nn.Module):
    """Encodes rich multi-modal car specifications into unit-normalized R^64 embedding."""
    def __init__(self):
        super().__init__()
        # Categorical Embeddings
        self.brand_emb = nn.Embedding(len(BRAND_VOCAB), 16)
        self.body_emb = nn.Embedding(len(BODY_VOCAB), 8)
        self.fuel_emb = nn.Embedding(len(FUEL_VOCAB), 6)
        self.trans_emb = nn.Embedding(len(TRANS_VOCAB), 4)
        self.status_emb = nn.Embedding(len(STATUS_VOCAB), 2)
        
        total_cat_dim = 16 + 8 + 6 + 4 + 2  # 36
        in_dim = len(NUMERICAL_COLS) + len(BOOLEAN_COLS) + total_cat_dim
        
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
        # cat_ids shape: [B, 5] -> brand, body, fuel, trans, status
        b_e = self.brand_emb(cat_ids[:, 0])
        bd_e = self.body_emb(cat_ids[:, 1])
        f_e = self.fuel_emb(cat_ids[:, 2])
        t_e = self.trans_emb(cat_ids[:, 3])
        s_e = self.status_emb(cat_ids[:, 4])
        
        x = torch.cat([num_x, bool_x, b_e, bd_e, f_e, t_e, s_e], dim=1)
        raw_emb = self.net(x)
        # Unit L2 Normalization
        return F.normalize(raw_emb, p=2, dim=1)


class UserPreferenceEncoder(nn.Module):
    """Encodes arbitrary user queries & preference constraints into unit-normalized R^64 embedding."""
    def __init__(self):
        super().__init__()
        self.brand_emb = nn.Embedding(len(BRAND_VOCAB), 16)
        self.body_emb = nn.Embedding(len(BODY_VOCAB), 8)
        self.fuel_emb = nn.Embedding(len(FUEL_VOCAB), 6)
        self.trans_emb = nn.Embedding(len(TRANS_VOCAB), 4)
        self.prio_emb = nn.Embedding(len(PRIORITY_VOCAB), 6)
        
        total_cat_dim = 16 + 8 + 6 + 4 + 6  # 40
        in_dim = 8 + total_cat_dim  # 8 continuous/boolean features + 40
        
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
        # cat_u shape: [B, 5] -> brand, body, fuel, trans, priority
        b_e = self.brand_emb(cat_u[:, 0])
        bd_e = self.body_emb(cat_u[:, 1])
        f_e = self.fuel_emb(cat_u[:, 2])
        t_e = self.trans_emb(cat_u[:, 3])
        p_e = self.prio_emb(cat_u[:, 4])
        
        x = torch.cat([num_u, b_e, bd_e, f_e, t_e, p_e], dim=1)
        raw_emb = self.net(x)
        # Unit L2 Normalization
        return F.normalize(raw_emb, p=2, dim=1)


class TwoTowerRankingNet(nn.Module):
    """Complete Two-Tower Metric Learning Network."""
    def __init__(self):
        super().__init__()
        self.car_encoder = CarEncoder()
        self.user_encoder = UserPreferenceEncoder()

    def forward(self, u_num, u_cat, c_num, c_bool, c_cat):
        u_emb = self.user_encoder(u_num, u_cat)
        c_emb = self.car_encoder(c_num, c_bool, c_cat)
        # Cosine similarity between unit normalized vectors is dot product
        similarity = torch.sum(u_emb * c_emb, dim=1)
        return similarity, u_emb, c_emb


model = TwoTowerRankingNet().to(DEVICE)
total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"  Model Parameters:    {total_params:,}")
print(f"  Embedding Dimension: {EMBEDDING_DIM}")
print(f"  Model Location:      {DEVICE} ({GPU_NAME})")

# ============================================================
# 5. LOSS FUNCTION & OPTIMIZER
# ============================================================

optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
NUM_EPOCHS = 25
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS, eta_min=1e-5)

MARGIN = 0.25  # Minimum desired cosine similarity margin between positive & negative candidates

def compute_loss(u_emb, pos_emb, neg_emb, pos_target, margin_target):
    # Cosine similarities
    sim_pos = torch.sum(u_emb * pos_emb, dim=1)
    sim_neg = torch.sum(u_emb * neg_emb, dim=1)
    
    # Pairwise Ranking Margin Loss: max(0, margin - (sim_pos - sim_neg))
    dynamic_margin = torch.clamp(margin_target * 0.5, min=0.15, max=0.40)
    ranking_loss = torch.mean(F.relu(dynamic_margin - (sim_pos - sim_neg)))
    
    # Soft Alignment Loss: Encourages positive match cosine to match target utility (mapped to [-0.2, 1.0])
    target_cos = (pos_target * 1.2) - 0.2
    align_loss = F.mse_loss(sim_pos, target_cos)
    
    total_loss = ranking_loss + 0.3 * align_loss
    return total_loss, sim_pos, sim_neg

# ============================================================
# 6. TRAINING & EVALUATION LOOP WITH GPU MONITORING
# ============================================================

print("\n[4/6] Commencing GPU training loop on NVIDIA RTX 4050...")
print("-" * 75)
print(f"{'Epoch':<8} {'Train Loss':<12} {'Val Loss':<11} {'Pair Acc (%)':<14} {'Mean Margin':<13} {'VRAM Used':<10}")
print("-" * 75)

best_val_acc = 0.0
best_val_loss = float("inf")
training_history = []
start_train_time = time.time()

for epoch in range(1, NUM_EPOCHS + 1):
    model.train()
    total_train_loss = 0.0
    
    for batch in train_loader:
        (u_num, u_cat, pos_num, pos_bool, pos_cat,
         neg_num, neg_bool, neg_cat, pos_score, margin_target) = [t.to(DEVICE) for t in batch]
        
        optimizer.zero_grad()
        
        u_emb = model.user_encoder(u_num, u_cat)
        pos_emb = model.car_encoder(pos_num, pos_bool, pos_cat)
        neg_emb = model.car_encoder(neg_num, neg_bool, neg_cat)
        
        loss, _, _ = compute_loss(u_emb, pos_emb, neg_emb, pos_score, margin_target)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
        optimizer.step()
        
        total_train_loss += loss.item() * u_num.size(0)
        
    scheduler.step()
    avg_train_loss = total_train_loss / len(train_dataset)
    
    # Validation
    model.eval()
    total_val_loss = 0.0
    correct_pairs = 0
    total_pairs = 0
    margin_diffs = []
    
    with torch.no_grad():
        for batch in val_loader:
            (u_num, u_cat, pos_num, pos_bool, pos_cat,
             neg_num, neg_bool, neg_cat, pos_score, margin_target) = [t.to(DEVICE) for t in batch]
            
            u_emb = model.user_encoder(u_num, u_cat)
            pos_emb = model.car_encoder(pos_num, pos_bool, pos_cat)
            neg_emb = model.car_encoder(neg_num, neg_bool, neg_cat)
            
            loss, sim_pos, sim_neg = compute_loss(u_emb, pos_emb, neg_emb, pos_score, margin_target)
            total_val_loss += loss.item() * u_num.size(0)
            
            correct_pairs += torch.sum(sim_pos > sim_neg).item()
            total_pairs += u_num.size(0)
            margin_diffs.extend((sim_pos - sim_neg).cpu().numpy().tolist())
            
    avg_val_loss = total_val_loss / len(val_dataset)
    pairwise_acc = (correct_pairs / total_pairs) * 100.0
    mean_margin = float(np.mean(margin_diffs))
    
    # GPU VRAM Monitoring
    if torch.cuda.is_available():
        allocated_mb = torch.cuda.memory_allocated(0) / (1024 ** 2)
        reserved_mb = torch.cuda.memory_reserved(0) / (1024 ** 2)
        mem_str = f"{allocated_mb:.1f} MB"
    else:
        allocated_mb = 0.0
        reserved_mb = 0.0
        mem_str = "CPU"
    
    print(f"{epoch:<8} {avg_train_loss:<12.4f} {avg_val_loss:<11.4f} {pairwise_acc:<14.2f} {mean_margin:<13.3f} {mem_str:<10}")
    
    training_history.append({
        "epoch": epoch,
        "train_loss": round(avg_train_loss, 4),
        "val_loss": round(avg_val_loss, 4),
        "pairwise_accuracy": round(pairwise_acc, 2),
        "mean_margin": round(mean_margin, 4),
        "gpu_allocated_mb": round(allocated_mb, 1),
        "gpu_reserved_mb": round(reserved_mb, 1)
    })
    
    # Save Best Model Checkpoint
    if pairwise_acc > best_val_acc or (pairwise_acc == best_val_acc and avg_val_loss < best_val_loss):
        best_val_acc = pairwise_acc
        best_val_loss = avg_val_loss
        
        checkpoint = {
            "model_state_dict": model.state_dict(),
            "embedding_dim": EMBEDDING_DIM,
            "vocabularies": {
                "brand": BRAND_VOCAB,
                "body_type": BODY_VOCAB,
                "fuel_group": FUEL_VOCAB,
                "transmission_group": TRANS_VOCAB,
                "status": STATUS_VOCAB,
                "priority": PRIORITY_VOCAB
            },
            "numerical_features": NUMERICAL_COLS,
            "boolean_features": BOOLEAN_COLS,
            "num_means": NUM_MEANS,
            "num_stds": NUM_STDS,
            "best_val_acc": best_val_acc,
            "best_val_loss": best_val_loss,
            "device": str(DEVICE),
            "gpu_name": GPU_NAME,
            "trained_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        torch.save(checkpoint, MODEL_SAVE_PATH)

total_time_min = (time.time() - start_train_time) / 60.0
print("-" * 75)
print(f"\nTraining completed in {total_time_min:.2f} minutes.")
print(f"Best Validation Pairwise Ranking Accuracy: {best_val_acc:.2f}%")
print(f"Best Validation Loss:                     {best_val_loss:.4f}")

# ============================================================
# 7. METADATA EXPORT & MODEL AUDIT
# ============================================================

print("\n[5/6] Exporting training metadata & model artifacts...")
metadata = {
    "model_name": "AutoAI Two-Tower Neural Recommendation & Ranking Network",
    "architecture": "TwoTowerRankingNet (UserPreferenceEncoder + CarEncoder)",
    "learning_strategy": "Metric Learning with Contrastive Pairwise Margin Ranking",
    "hardware": {
        "device": str(DEVICE),
        "gpu_name": GPU_NAME,
        "cuda_version": CUDA_VERSION,
        "pytorch_version": torch.__version__,
        "vram_total_gb": round(TOTAL_VRAM_GB, 2)
    },
    "dataset": {
        "path": str(DATA_PATH),
        "total_cars": len(df_cars),
        "train_cars": len(train_cars),
        "val_cars": len(val_cars),
        "train_triplets": len(train_dataset),
        "val_triplets": len(val_dataset)
    },
    "metrics": {
        "best_pairwise_accuracy_percent": round(best_val_acc, 2),
        "best_validation_loss": round(best_val_loss, 4),
        "total_training_time_minutes": round(total_time_min, 2)
    },
    "history": training_history,
    "model_path": str(MODEL_SAVE_PATH)
}

with open(METADATA_SAVE_PATH, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=4)

print(f"  Artifact saved: {MODEL_SAVE_PATH}")
print(f"  Metadata saved: {METADATA_SAVE_PATH}")

print("\n[6/6] MODEL TRAINING & VALIDATION PIPELINE COMPLETED SUCCESSFULLY!")
print("=" * 75)
