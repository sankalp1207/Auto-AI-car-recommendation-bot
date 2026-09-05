import os
import sys
from pathlib import Path

# Setup paths
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.database.database import SessionLocal
from app.models.car import Car
from app.schemas.recommendation import RecommendationRequest
from app.services.recommendation_service import recommend_cars
from app.services.score_service import classify_body_type, is_luxury_brand
from app.services.ai_service import extract_preferences, explain_recommendations

client = TestClient(app)

print("=" * 70)
print("AUTOAI RECOMMENDATION ENGINE COMPREHENSIVE VALIDATION SUITE")
print("=" * 70)

# Verify DB connection and counts
with SessionLocal() as db:
    total_pg = db.query(Car).count()
    current_pg = db.query(Car).filter(Car.status == "CURRENT").count()
    upcoming_pg = db.query(Car).filter(Car.status == "UPCOMING").count()
    print(f"PostgreSQL Ground Truth -> Total: {total_pg}, CURRENT: {current_pg}, UPCOMING: {upcoming_pg}")
    assert total_pg == 2245
    assert current_pg == 2076
    assert upcoming_pg == 169

# Helper to verify DB presence
def verify_in_db(car_dict):
    with SessionLocal() as db:
        c = db.query(Car).filter(Car.id == car_dict["id"]).first()
        assert c is not None, f"Car {car_dict['id']} not found in DB!"
        assert c.brand == car_dict["brand"]
        assert c.model == car_dict["model"]
        assert c.status == car_dict["status"]

print("\n" + "=" * 70)
print("TESTING 9 MANDATORY USER CASES")
print("=" * 70)

# CASE 1: "Best SUV under 15 lakh"
print("\n--- CASE 1: 'Best SUV under 15 lakh' ---")
prefs1 = extract_preferences("Best SUV under 15 lakh")
assert prefs1["budget"] == 1500000.0, f"Budget mismatch: {prefs1['budget']}"
assert prefs1["body_type"] == "SUV", f"Body type mismatch: {prefs1['body_type']}"
req1 = RecommendationRequest(**prefs1)
recs1 = recommend_cars(req1)
assert len(recs1) > 0, "Expected recommendations for SUV under 15 lakh"
for r in recs1:
    verify_in_db(r)
    assert r["price"] <= 1500000.0, f"Hard constraint violation: price {r['price']} > 15L"
    assert r["body_type"] == "SUV" or classify_body_type(r["model"]) == "SUV"
    assert r["status"] == "CURRENT"
# Verify model deduplication (distinct models)
models1 = [r["model"] for r in recs1]
assert len(models1) == len(set(models1)), f"Duplicate models detected: {models1}"
print(f"[PASS] Case 1 returned {len(recs1)} distinct SUVs under 15L: {', '.join(models1)}")

# CASE 2: "Automatic family car under 12 lakh"
print("\n--- CASE 2: 'Automatic family car under 12 lakh' ---")
prefs2 = extract_preferences("Automatic family car under 12 lakh")
assert prefs2["budget"] == 1200000.0
assert prefs2["transmission"] == "Automatic"
assert prefs2["family_friendly"] is True
req2 = RecommendationRequest(**prefs2)
recs2 = recommend_cars(req2)
assert len(recs2) > 0
for r in recs2:
    verify_in_db(r)
    assert r["price"] <= 1200000.0
    assert "auto" in r["transmission"].lower() or "amt" in r["transmission"].lower() or "cvt" in r["transmission"].lower()
    assert r["status"] == "CURRENT"
models2 = [r["model"] for r in recs2]
assert len(models2) == len(set(models2))
print(f"[PASS] Case 2 returned {len(recs2)} automatic family cars under 12L: {', '.join(models2)}")

# CASE 3: "7 seater under 20 lakh"
print("\n--- CASE 3: '7 seater under 20 lakh' ---")
prefs3 = extract_preferences("7 seater under 20 lakh")
assert prefs3["budget"] == 2000000.0
assert prefs3["seating"] == 7
req3 = RecommendationRequest(**prefs3)
recs3 = recommend_cars(req3)
assert len(recs3) > 0
for r in recs3:
    verify_in_db(r)
    assert r["price"] <= 2000000.0
    assert r["seating"] >= 7, f"Hard constraint violation: seating {r['seating']} < 7"
    assert r["status"] == "CURRENT"
models3 = [f"{r['brand']} {r['model']} ({r['seating']}s)" for r in recs3]
print(f"[PASS] Case 3 returned {len(recs3)} 7-seaters under 20L: {', '.join(models3)}")

# CASE 4: "CNG car under 10 lakh"
print("\n--- CASE 4: 'CNG car under 10 lakh' ---")
prefs4 = extract_preferences("CNG car under 10 lakh")
assert prefs4["budget"] == 1000000.0
assert prefs4["fuel_type"] == "CNG"
req4 = RecommendationRequest(**prefs4)
recs4 = recommend_cars(req4)
assert len(recs4) > 0
for r in recs4:
    verify_in_db(r)
    assert r["price"] <= 1000000.0
    assert "cng" in r["fuel_type"].lower(), f"Fuel mismatch: {r['fuel_type']}"
    assert r["status"] == "CURRENT"
models4 = [f"{r['brand']} {r['model']}" for r in recs4]
print(f"[PASS] Case 4 returned {len(recs4)} CNG cars under 10L: {', '.join(models4)}")

# CASE 5: "Electric car for city use"
print("\n--- CASE 5: 'Electric car for city use' ---")
prefs5 = extract_preferences("Electric car for city use")
assert prefs5["fuel_type"] == "Electric"
assert prefs5["city_drive"] is True
req5 = RecommendationRequest(**prefs5)
recs5 = recommend_cars(req5)
assert len(recs5) > 0
for r in recs5:
    verify_in_db(r)
    assert "electric" in r["fuel_type"].lower() or "ev" in r["fuel_type"].lower()
    assert r["status"] == "CURRENT"
models5 = [f"{r['brand']} {r['model']}" for r in recs5]
print(f"[PASS] Case 5 returned {len(recs5)} Electric city cars: {', '.join(models5)}")

# CASE 6: "Hyundai automatic under 15 lakh"
print("\n--- CASE 6: 'Hyundai automatic under 15 lakh' ---")
prefs6 = extract_preferences("Hyundai automatic under 15 lakh")
assert prefs6["brand"] == "Hyundai"
assert prefs6["transmission"] == "Automatic"
assert prefs6["budget"] == 1500000.0
req6 = RecommendationRequest(**prefs6)
recs6 = recommend_cars(req6)
assert len(recs6) > 0
for r in recs6:
    verify_in_db(r)
    assert r["brand"] == "Hyundai", f"Brand violation: {r['brand']}"
    assert r["price"] <= 1500000.0
    assert "auto" in r["transmission"].lower() or "amt" in r["transmission"].lower() or "cvt" in r["transmission"].lower() or "ivt" in r["variant"].lower() or "dct" in r["transmission"].lower()
    assert r["status"] == "CURRENT"
models6 = [f"{r['brand']} {r['model']} {r['variant']}" for r in recs6]
print(f"[PASS] Case 6 returned {len(recs6)} Hyundai automatics under 15L: {', '.join(models6)}")

# CASE 7: "Upcoming SUV under 25 lakh"
print("\n--- CASE 7: 'Upcoming SUV under 25 lakh' ---")
prefs7 = extract_preferences("Upcoming SUV under 25 lakh")
assert prefs7["status"] == "UPCOMING", f"Status should be UPCOMING, got {prefs7['status']}"
assert prefs7["body_type"] == "SUV"
assert prefs7["budget"] == 2500000.0
req7 = RecommendationRequest(**prefs7)
recs7 = recommend_cars(req7)
assert len(recs7) > 0
for r in recs7:
    verify_in_db(r)
    assert r["status"] == "UPCOMING", f"Status violation: {r['status']}"
    assert r["price"] <= 2500000.0
models7 = [f"{r['brand']} {r['model']}" for r in recs7]
print(f"[PASS] Case 7 returned {len(recs7)} Upcoming SUVs under 25L: {', '.join(models7)}")

# CASE 8: "Luxury car under Rs.2 lakh"
print("\n--- CASE 8: 'Luxury car under Rs.2 lakh' ---")
prefs8 = extract_preferences("Luxury car under Rs.2 lakh")
assert prefs8["is_luxury"] is True
assert prefs8["budget"] == 200000.0
req8 = RecommendationRequest(**prefs8)
recs8 = recommend_cars(req8)
assert len(recs8) == 0, f"Expected 0 results for luxury car under 2L, got {len(recs8)}"
explanation8 = explain_recommendations("Luxury car under Rs.2 lakh", recs8, prefs8)
assert "No luxury" in explanation8 or "database" in explanation8
print("[PASS] Case 8 handled gracefully with zero false recommendations and clear explanation:")
print(f"       -> Explanation snippet: {explanation8.splitlines()[0]}")

# CASE 9: "Give me the best car"
print("\n--- CASE 9: 'Give me the best car' ---")
prefs9 = extract_preferences("Give me the best car")
req9 = RecommendationRequest(**prefs9)
recs9 = recommend_cars(req9)
assert len(recs9) > 0
for r in recs9:
    verify_in_db(r)
    assert r["status"] == "CURRENT"
models9 = [f"{r['brand']} {r['model']} ({r['score']}/100)" for r in recs9]
print(f"[PASS] Case 9 returned sensible defaults without crashing: {', '.join(models9)}")

print("\n" + "=" * 70)
print("TESTING HARD CONSTRAINT ENFORCEMENT")
print("=" * 70)

# Hard constraint: Maximum Budget
req_budget = RecommendationRequest(budget=800000.0)
recs_budget = recommend_cars(req_budget)
for r in recs_budget:
    assert r["price"] <= 800000.0
print("[PASS] Hard constraint: Maximum budget (<= 8 Lakh) strictly respected by all candidates")

# Hard constraint: Fuel type
req_fuel = RecommendationRequest(fuel="Diesel")
recs_fuel = recommend_cars(req_fuel)
for r in recs_fuel:
    assert "diesel" in r["fuel_type"].lower()
print("[PASS] Hard constraint: Fuel type (Diesel) strictly respected by all candidates")

# Hard constraint: Transmission
req_trans = RecommendationRequest(transmission="Manual")
recs_trans = recommend_cars(req_trans)
for r in recs_trans:
    assert "manual" in r["transmission"].lower()
print("[PASS] Hard constraint: Transmission (Manual) strictly respected by all candidates")

# Hard constraint: Status isolation
req_upcoming = RecommendationRequest(status="UPCOMING")
recs_upcoming = recommend_cars(req_upcoming)
for r in recs_upcoming:
    assert r["status"] == "UPCOMING"
print("[PASS] Hard constraint: UPCOMING status completely isolated from CURRENT")

print("\n" + "=" * 70)
print("TESTING SCORING DETERMINISM & MISSING DATA SAFETY")
print("=" * 70)

req_det = RecommendationRequest(budget=1500000, body_type="SUV")
res_run1 = recommend_cars(req_det)
res_run2 = recommend_cars(req_det)
assert [c["id"] for c in res_run1] == [c["id"] for c in res_run2], "Scoring order must be strictly deterministic!"
assert [c["score"] for c in res_run1] == [c["score"] for c in res_run2], "Scores must be strictly identical across runs!"
print("[PASS] Determinism verified: 100% identical ranking and scores on multiple runs")

# Missing data test on car object with all None/missing optional fields
empty_car = {
    "id": 99999,
    "brand": "TestBrand",
    "model": "TestModel",
    "variant": "Base",
    "price": 500000.0,
    "ex_showroom_price": 500000.0,
    "fuel_type": "Petrol",
    "transmission": "Manual",
    "safety_rating": None,
    "mileage": None,
    "power": None,
    "torque": None,
    "boot_space": None,
    "maintenance_cost": None,
    "resale_rating": None,
    "city_use": None,
    "highway_use": None,
    "family_friendly": None,
    "adas": None,
    "sunroof": None,
    "status": "CURRENT"
}
from app.services.score_service import calculate_recommendation_score
score, reasons, breakdown = calculate_recommendation_score(empty_car, {"budget": 1000000})
assert 50.0 <= score <= 100.0
assert len(reasons) > 0
print("[PASS] Missing data safety verified: calculate_recommendation_score handles None safely without crashing")

print("\n" + "=" * 70)
print("TESTING FASTAPI HTTP ENDPOINTS (/recommend and /chat)")
print("=" * 70)

# HTTP POST /recommend
res_post = client.post("/recommend/", json={"budget": 1200000, "transmission": "Automatic"})
assert res_post.status_code == 200
data_post = res_post.json()
assert len(data_post) > 0
print(f"[PASS] HTTP POST /recommend -> 200 OK with {len(data_post)} items")

# HTTP GET /recommend
res_get = client.get("/recommend/?budget=1500000&body_type=SUV")
assert res_get.status_code == 200
data_get = res_get.json()
assert len(data_get) > 0
print(f"[PASS] HTTP GET /recommend -> 200 OK with {len(data_get)} items")

# HTTP POST /recommend 404 on impossible criteria
res_404 = client.post("/recommend/", json={"budget": 100000, "is_luxury": True})
assert res_404.status_code == 404
print(f"[PASS] HTTP POST /recommend impossible criteria -> 404 Not Found as expected")

# HTTP POST /chat with Case 1
res_chat1 = client.post("/chat/", json={"message": "Best SUV under 15 lakh"})
assert res_chat1.status_code == 200
chat_data1 = res_chat1.json()
assert "recommendations" in chat_data1
assert len(chat_data1["recommendations"]) > 0
assert "ai_response" in chat_data1
print(f"[PASS] HTTP POST /chat ('Best SUV under 15 lakh') -> 200 OK with {len(chat_data1['recommendations'])} recs and AI response")

# HTTP POST /chat with Case 8
res_chat8 = client.post("/chat/", json={"message": "Luxury car under Rs.2 lakh"})
assert res_chat8.status_code == 200
chat_data8 = res_chat8.json()
assert chat_data8["recommendations"] == []
assert len(chat_data8["ai_response"]) > 0
print(f"[PASS] HTTP POST /chat ('Luxury car under Rs.2 lakh') -> 200 OK with 0 fake recs and clean explanation")

print("\n" + "=" * 70)
print("ALL RECOMMENDATION ENGINE TESTS PASSED 100% SUCCESSFULLY!")
print("=" * 70)
