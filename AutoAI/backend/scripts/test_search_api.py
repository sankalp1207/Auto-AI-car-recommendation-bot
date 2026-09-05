import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.database.database import SessionLocal
from app.models.car import Car
import app.services.search_service as search_service

client = TestClient(app)

# Load DB vehicles for ground-truth verification and close session immediately
with SessionLocal() as db:
    db_cars = {c.id: {"id": c.id, "brand": c.brand, "model": c.model, "status": c.status, "price": c.ex_showroom_price} for c in db.query(Car).all()}

total_db = len(db_cars)
curr_db = sum(1 for c in db_cars.values() if c["status"] == "CURRENT")
up_db = sum(1 for c in db_cars.values() if c["status"] == "UPCOMING")
print(f"PostgreSQL Ground Truth -> Total: {total_db}, CURRENT: {curr_db}, UPCOMING: {up_db}")

def verify_db_consistency(cars_list, expected_status=None):
    for c in cars_list:
        cid = c.get("id") if isinstance(c, dict) else c.id
        assert cid in db_cars, f"Car ID {cid} does not exist in PostgreSQL!"
        db_car = db_cars[cid]
        c_brand = c.get("brand") if isinstance(c, dict) else c.brand
        c_model = c.get("model") if isinstance(c, dict) else c.model
        c_status = c.get("status") if isinstance(c, dict) else c.status
        assert db_car["brand"] == c_brand, f"Brand mismatch for ID {cid}"
        assert db_car["model"] == c_model, f"Model mismatch for ID {cid}"
        if expected_status:
            assert c_status == expected_status, f"Expected status {expected_status}, got {c_status} for ID {cid}"

print("\n" + "=" * 70)
print("1. INDIVIDUAL FILTERS TEST")
print("=" * 70)

# 1.1 Brand filter
res_brand = client.get("/search/?brand=Hyundai")
assert res_brand.status_code == 200
cars_brand = res_brand.json()
assert len(cars_brand) > 0 and all("hyundai" in c["brand"].lower() for c in cars_brand)
verify_db_consistency(cars_brand, "CURRENT")
print(f"[PASS] Brand filter ('Hyundai'): {len(cars_brand)} vehicles returned (verified in DB)")

# 1.2 Make alias filter
res_make = client.get("/search/?make=Tata")
assert res_make.status_code == 200
cars_make = res_make.json()
assert len(cars_make) > 0 and all("tata" in c["brand"].lower() for c in cars_make)
verify_db_consistency(cars_make, "CURRENT")
print(f"[PASS] Make alias filter ('Tata'): {len(cars_make)} vehicles returned (verified in DB)")

# 1.3 Budget filter
budget_val = 1500000.0
res_budget = client.get(f"/search/?budget={budget_val}")
assert res_budget.status_code == 200
cars_budget = res_budget.json()
assert len(cars_budget) > 0 and all(c["price"] <= budget_val for c in cars_budget)
verify_db_consistency(cars_budget, "CURRENT")
print(f"[PASS] Budget filter (<= 15L): {len(cars_budget)} vehicles returned (verified in DB)")

# 1.4 Fuel filter
res_fuel = client.get("/search/?fuel=Petrol")
assert res_fuel.status_code == 200
cars_fuel = res_fuel.json()
assert len(cars_fuel) > 0 and all("petrol" in c["fuel_type"].lower() for c in cars_fuel)
verify_db_consistency(cars_fuel, "CURRENT")
print(f"[PASS] Fuel filter ('Petrol'): {len(cars_fuel)} vehicles returned (verified in DB)")

# 1.5 Fuel_type alias filter
res_fuel_type = client.get("/search/?fuel_type=Diesel")
assert res_fuel_type.status_code == 200
cars_fuel_type = res_fuel_type.json()
assert len(cars_fuel_type) > 0 and all("diesel" in c["fuel_type"].lower() for c in cars_fuel_type)
verify_db_consistency(cars_fuel_type, "CURRENT")
print(f"[PASS] Fuel_type alias filter ('Diesel'): {len(cars_fuel_type)} vehicles returned (verified in DB)")

# 1.6 Transmission filter
res_trans = client.get("/search/?transmission=Automatic")
assert res_trans.status_code == 200
cars_trans = res_trans.json()
assert len(cars_trans) > 0 and all("automatic" in c["transmission"].lower() for c in cars_trans)
verify_db_consistency(cars_trans, "CURRENT")
print(f"[PASS] Transmission filter ('Automatic'): {len(cars_trans)} vehicles returned (verified in DB)")

# 1.7 Seating filter
res_seat = client.get("/search/?seating=7")
assert res_seat.status_code == 200
cars_seat = res_seat.json()
assert len(cars_seat) > 0 and all(c["seating"] >= 7 for c in cars_seat)
verify_db_consistency(cars_seat, "CURRENT")
print(f"[PASS] Seating filter (>= 7 seats): {len(cars_seat)} vehicles returned (verified in DB)")

# 1.8 Body_type filter
res_body_unknown = client.get("/search/?body_type=Unknown")
assert res_body_unknown.status_code == 200
cars_body_unknown = res_body_unknown.json()
assert len(cars_body_unknown) > 0 and all("unknown" in c["body_type"].lower() for c in cars_body_unknown)
verify_db_consistency(cars_body_unknown, "CURRENT")
print(f"[PASS] Body_type filter ('Unknown'): {len(cars_body_unknown)} vehicles returned (verified in DB)")

# 1.9 Status filter
res_curr = client.get("/search/?status=CURRENT")
assert res_curr.status_code == 200
assert len(res_curr.json()) == curr_db
verify_db_consistency(res_curr.json(), "CURRENT")
print(f"[PASS] Status 'CURRENT' filter: {len(res_curr.json())} vehicles returned (matches DB {curr_db})")

res_up = client.get("/search/?status=UPCOMING")
assert res_up.status_code == 200
assert len(res_up.json()) == up_db
verify_db_consistency(res_up.json(), "UPCOMING")
print(f"[PASS] Status 'UPCOMING' filter: {len(res_up.json())} vehicles returned (matches DB {up_db})")

res_all = client.get("/search/?status=ALL")
assert res_all.status_code == 200
assert len(res_all.json()) == total_db
print(f"[PASS] Status 'ALL' filter: {len(res_all.json())} vehicles returned (matches DB {total_db})")

# 1.10 Model / Search text filter
res_model = client.get("/search/?model=Creta")
assert res_model.status_code == 200
cars_model = res_model.json()
assert len(cars_model) > 0 and all("creta" in c["model"].lower() for c in cars_model)
verify_db_consistency(cars_model, "CURRENT")
print(f"[PASS] Model filter ('Creta'): {len(cars_model)} vehicles returned (verified in DB)")

res_q = client.get("/search/?q=Nexon")
assert res_q.status_code == 200
cars_q = res_q.json()
assert len(cars_q) > 0 and all("nexon" in (c["model"] + " " + c["brand"] + " " + c["variant"]).lower() for c in cars_q)
verify_db_consistency(cars_q, "CURRENT")
print(f"[PASS] Search text filter (q='Nexon'): {len(cars_q)} vehicles returned (verified in DB)")

# 1.11 Pagination & Sorting
p1 = client.get("/search/?brand=Hyundai&limit=10&page=1").json()
p2 = client.get("/search/?brand=Hyundai&limit=10&page=2").json()
assert len(p1) == 10
assert len(p2) == 10
p1_ids = set(c["id"] for c in p1)
p2_ids = set(c["id"] for c in p2)
assert p1_ids.isdisjoint(p2_ids), "Pagination duplicated records across pages!"
print(f"[PASS] Pagination (page=1,2 limit=10): {len(p1)} and {len(p2)} mutually exclusive items without duplicate/loss")

sort_asc = client.get("/search/?brand=Hyundai&sort_by=price&order=asc&limit=5").json()
prices_asc = [c["price"] for c in sort_asc]
assert prices_asc == sorted(prices_asc), "Sorting by price asc failed!"
print(f"[PASS] Sorting (sort_by=price order=asc): verified ascending prices: {prices_asc}")

print("\n" + "=" * 70)
print("2. COMBINATION TESTS")
print("=" * 70)

# 2.1 Brand + Budget
res_c1 = client.get("/search/?brand=Tata&budget=1500000")
assert res_c1.status_code == 200
c1 = res_c1.json()
assert len(c1) > 0 and all("tata" in x["brand"].lower() and x["price"] <= 1500000 for x in c1)
verify_db_consistency(c1, "CURRENT")
print(f"[PASS] Brand + Budget (Tata <= 15L): {len(c1)} vehicles returned")

# 2.2 Fuel + Budget
res_c2 = client.get("/search/?fuel=Diesel&budget=1200000")
assert res_c2.status_code == 200
c2 = res_c2.json()
assert len(c2) > 0 and all("diesel" in x["fuel_type"].lower() and x["price"] <= 1200000 for x in c2)
verify_db_consistency(c2, "CURRENT")
print(f"[PASS] Fuel + Budget (Diesel <= 12L): {len(c2)} vehicles returned")

# 2.3 Body_type + Budget
res_c3 = client.get("/search/?body_type=Unknown&budget=2000000")
assert res_c3.status_code == 200
c3 = res_c3.json()
assert len(c3) > 0 and all("unknown" in x["body_type"].lower() and x["price"] <= 2000000 for x in c3)
verify_db_consistency(c3, "CURRENT")
print(f"[PASS] Body_type + Budget (Unknown <= 20L): {len(c3)} vehicles returned")

# 2.4 Transmission + Seating
res_c4 = client.get("/search/?transmission=Automatic&seating=7")
assert res_c4.status_code == 200
c4 = res_c4.json()
assert len(c4) > 0 and all("automatic" in x["transmission"].lower() and x["seating"] >= 7 for x in c4)
verify_db_consistency(c4, "CURRENT")
print(f"[PASS] Transmission + Seating (Automatic & >= 7 seats): {len(c4)} vehicles returned")

# 2.5 Brand + Fuel + Budget
res_c5 = client.get("/search/?brand=Hyundai&fuel=Petrol&budget=1800000")
assert res_c5.status_code == 200
c5 = res_c5.json()
assert len(c5) > 0 and all("hyundai" in x["brand"].lower() and "petrol" in x["fuel_type"].lower() and x["price"] <= 1800000 for x in c5)
verify_db_consistency(c5, "CURRENT")
print(f"[PASS] Brand + Fuel + Budget (Hyundai + Petrol <= 18L): {len(c5)} vehicles returned")

print("\n" + "=" * 70)
print("3. EDGE CASES")
print("=" * 70)

# 3.1 Nonexistent brand
res_e1 = client.get("/search/?brand=NonExistentBrand12345")
assert res_e1.status_code == 404
print(f"[PASS] Nonexistent brand -> 404 Not Found")

# 3.2 Impossible budget
res_e2 = client.get("/search/?budget=-1000")
assert res_e2.status_code == 404
res_e2b = client.get("/search/?budget=0")
assert res_e2b.status_code == 404
print(f"[PASS] Impossible budget (-1000 and 0) -> 404 Not Found")

# 3.3 Invalid fuel
res_e3 = client.get("/search/?fuel=Nuclear")
assert res_e3.status_code == 404
print(f"[PASS] Invalid fuel ('Nuclear') -> 404 Not Found")

# 3.4 Invalid transmission
res_e4 = client.get("/search/?transmission=Hovercraft")
assert res_e4.status_code == 404
print(f"[PASS] Invalid transmission ('Hovercraft') -> 404 Not Found")

# 3.5 Invalid seating
res_e5 = client.get("/search/?seating=50")
assert res_e5.status_code == 404
print(f"[PASS] Invalid seating (50 seats) -> 404 Not Found")

# 3.6 Empty search (default parameters)
res_e6 = client.get("/search/")
assert res_e6.status_code == 200
assert len(res_e6.json()) == curr_db
print(f"[PASS] Empty search (default parameters) -> returns all {curr_db} CURRENT cars")

# 3.7 Missing optional fields / null queries / empty strings
res_e7 = client.get("/search/?brand=&fuel=&model=")
assert res_e7.status_code == 200
assert len(res_e7.json()) == curr_db
print(f"[PASS] Empty string parameters handled without crashing: {len(res_e7.json())} cars returned")

# 3.8 CURRENT vs UPCOMING separation
res_e8_curr = client.get("/search/?model=Creta&status=CURRENT")
assert res_e8_curr.status_code == 200
assert all(c["status"] == "CURRENT" for c in res_e8_curr.json())
res_e8_up = client.get("/search/?status=UPCOMING")
assert res_e8_up.status_code == 200
assert all(c["status"] == "UPCOMING" for c in res_e8_up.json())
print(f"[PASS] CURRENT vs UPCOMING partition separation: 100% accurate")

print("\n" + "=" * 70)
print("4. TESTING search_service.py (Direct DB)")
print("=" * 70)
with SessionLocal() as db_sess:
    s_brand = search_service.search_cars(db_sess, brand="Hyundai", status="CURRENT")
    assert len(s_brand) == 234
    print(f"[PASS] search_service(brand='Hyundai', status='CURRENT'): {len(s_brand)} cars")

    s_fuel_lower = search_service.search_cars(db_sess, fuel="petrol", status="CURRENT")
    assert len(s_fuel_lower) == 1092
    print(f"[PASS] search_service(fuel='petrol' case-insensitive): {len(s_fuel_lower)} cars")

    s_trans_lower = search_service.search_cars(db_sess, transmission="automatic", status="CURRENT")
    assert len(s_trans_lower) == 1258
    print(f"[PASS] search_service(transmission='automatic' case-insensitive): {len(s_trans_lower)} cars")

    s_model = search_service.search_cars(db_sess, model="Creta", status="CURRENT")
    assert len(s_model) == 61
    print(f"[PASS] search_service(model='Creta'): {len(s_model)} cars")

    s_seat = search_service.search_cars(db_sess, seating=7, status="CURRENT")
    assert len(s_seat) == 372
    print(f"[PASS] search_service(seating=7): {len(s_seat)} cars")

    s_comb = search_service.search_cars(db_sess, brand="Tata", budget=1500000, status="CURRENT")
    assert len(s_comb) == 217
    print(f"[PASS] search_service(Tata <= 15L): {len(s_comb)} cars")

    s_page = search_service.search_cars(db_sess, brand="Hyundai", limit=10, page=1, status="CURRENT")
    assert len(s_page) == 10
    print(f"[PASS] search_service pagination (limit=10, page=1): {len(s_page)} cars")

print("\n" + "=" * 70)
print("ALL TESTS PASSED WITH 100% SUCCESS!")
print("=" * 70)
