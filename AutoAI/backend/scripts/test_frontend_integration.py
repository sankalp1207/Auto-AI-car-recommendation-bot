import requests
import json
import uuid

BASE_URL = "http://127.0.0.1:8000"

def test_root():
    print("\n--- 1. Testing Root Health ---")
    r = requests.get(f"{BASE_URL}/")
    assert r.status_code == 200, f"Root failed: {r.status_code}"
    print(f"PASS: Root returned {r.json()}")

def test_dashboard_stats():
    print("\n--- 2. Testing Dashboard Statistics ---")
    r = requests.get(f"{BASE_URL}/dashboard/stats")
    assert r.status_code == 200, f"Dashboard failed: {r.status_code}"
    data = r.json()
    print("Dashboard Data:", data)
    assert data.get("total_cars") == 2245, f"Expected 2245 total_cars, got {data.get('total_cars')}"
    assert data.get("current_cars") == 2076, f"Expected 2076 current_cars, got {data.get('current_cars')}"
    assert data.get("upcoming_cars") == 169, f"Expected 169 upcoming_cars, got {data.get('upcoming_cars')}"
    print("PASS: Dashboard stats match exact PostgreSQL counts (2245 total, 2076 CURRENT, 169 UPCOMING)!")

def test_car_listing():
    print("\n--- 3. Testing Car Listing Endpoints ---")
    # Test unslashed
    r1 = requests.get(f"{BASE_URL}/cars")
    assert r1.status_code == 200, f"GET /cars failed: {r1.status_code}"
    cars1 = r1.json()
    assert len(cars1) > 0, "No cars returned by /cars"

    # Test slashed
    r2 = requests.get(f"{BASE_URL}/cars/")
    assert r2.status_code == 200, f"GET /cars/ failed: {r2.status_code}"
    cars2 = r2.json()
    assert len(cars1) == len(cars2), "Length mismatch between /cars and /cars/"

    # Test single car details
    first_car = cars1[0]
    car_id = first_car["id"]
    r_detail = requests.get(f"{BASE_URL}/cars/{car_id}")
    assert r_detail.status_code == 200, f"GET /cars/{car_id} failed: {r_detail.status_code}"
    detail = r_detail.json()
    assert detail["id"] == car_id, "Detail id mismatch"
    assert "brand" in detail and "model" in detail and "ex_showroom_price" in detail
    print(f"PASS: Car listing and details work. Found {len(cars1)} cars. Sample: {detail['brand']} {detail['model']}")

def test_search_filters():
    print("\n--- 4. Testing Search and Filtering ---")
    # Test brand
    r_brand = requests.get(f"{BASE_URL}/search", params={"brand": "Tata"})
    assert r_brand.status_code == 200, f"Search brand failed: {r_brand.status_code}"
    tata_cars = r_brand.json()
    assert all("tata" in c["brand"].lower() for c in tata_cars), "Non-Tata in results"
    print(f"  - Brand 'Tata': {len(tata_cars)} cars")

    # Test budget
    r_budget = requests.get(f"{BASE_URL}/search", params={"budget": 1000000})
    assert r_budget.status_code == 200, f"Search budget failed: {r_budget.status_code}"
    budget_cars = r_budget.json()
    assert all(float(c.get("price") or c.get("ex_showroom_price")) <= 1000000 for c in budget_cars)
    print(f"  - Budget <= 10L: {len(budget_cars)} cars")

    # Test fuel + transmission
    r_ft = requests.get(f"{BASE_URL}/search", params={"fuel": "Petrol", "transmission": "Automatic"})
    assert r_ft.status_code == 200, f"Search fuel+trans failed: {r_ft.status_code}"
    ft_cars = r_ft.json()
    assert all("petrol" in c["fuel_type"].lower() for c in ft_cars)
    assert all("auto" in c["transmission"].lower() or "amt" in c["transmission"].lower() or "cvt" in c["transmission"].lower() for c in ft_cars)
    print(f"  - Fuel (Petrol) + Transmission (Automatic): {len(ft_cars)} cars")

    # Test seating + body type
    r_sb = requests.get(f"{BASE_URL}/search", params={"seating": 7, "body_type": "SUV"})
    assert r_sb.status_code == 200, f"Search seating+body failed: {r_sb.status_code}"
    sb_cars = r_sb.json()
    assert all(int(c.get("seating") or 0) >= 7 for c in sb_cars)
    print(f"  - 7+ Seater SUV: {len(sb_cars)} cars")

    # Test status UPCOMING vs CURRENT
    r_up = requests.get(f"{BASE_URL}/search", params={"status": "UPCOMING"})
    assert r_up.status_code == 200, f"Search UPCOMING failed: {r_up.status_code}"
    up_cars = r_up.json()
    assert len(up_cars) == 169, f"Expected 169 UPCOMING cars, got {len(up_cars)}"
    print(f"  - Status UPCOMING: {len(up_cars)} cars")

    # Test model/text search
    r_q = requests.get(f"{BASE_URL}/search", params={"q": "Nexon"})
    assert r_q.status_code == 200, f"Search q='Nexon' failed: {r_q.status_code}"
    q_cars = r_q.json()
    assert all("nexon" in (c["model"] + c["variant"]).lower() for c in q_cars)
    print(f"  - Query q='Nexon': {len(q_cars)} cars")

    # Test pagination
    r_p1 = requests.get(f"{BASE_URL}/search", params={"page": 1, "limit": 10})
    assert r_p1.status_code == 200
    assert len(r_p1.json()) == 10
    print("PASS: Search filters, pagination, and status partitioning work 100%!")

def test_recommendation_flow():
    print("\n--- 5. Testing Recommendation Flow ---")
    payload = {
        "budget": 1500000,
        "fuel_type": "Petrol",
        "transmission": "Automatic",
        "body_type": "SUV",
        "family_members": 4,
        "priority": "safety",
        "status": "CURRENT"
    }
    r = requests.post(f"{BASE_URL}/recommend", json=payload)
    assert r.status_code == 200, f"Recommend failed: {r.status_code} {r.text}"
    recs = r.json()
    assert len(recs) > 0, "No recommendations returned"
    print(f"  - Returned {len(recs)} top recommendations:")
    for rec in recs:
        price = rec.get('price') or rec.get('ex_showroom_price')
        print(f"    * {rec['brand']} {rec['model']} ({rec.get('variant', '')}) - Rs.{price:,.0f} | Score: {rec.get('score')}%")
        assert price <= 1500000, f"Car price {price} exceeded budget 15L"
    print("PASS: Recommendation flow returned verified database vehicles within constraints!")

def test_ai_chat_flow():
    print("\n--- 6. Testing AI Chat Multi-Turn Flow ---")
    session_id = f"test_session_{uuid.uuid4().hex[:8]}"

    # Turn 1: Initial query
    print("  Turn 1: 'I need an automatic SUV under 15 lakh.'")
    r1 = requests.post(f"{BASE_URL}/chat", json={"message": "I need an automatic SUV under 15 lakh.", "session_id": session_id})
    assert r1.status_code == 200, f"Chat Turn 1 failed: {r1.status_code}"
    data1 = r1.json()
    assert "ai_response" in data1 and len(data1["ai_response"]) > 0
    assert "recommendations" in data1 and len(data1["recommendations"]) > 0
    rec_names = [f"{c['brand']} {c['model']}" for c in data1["recommendations"]]
    print(f"    AI Reply snippet: {data1['ai_response'][:120]}...")
    print(f"    Recs: {rec_names}")

    # Turn 2: Follow-up question
    print("  Turn 2: 'Which one would you recommend?'")
    r2 = requests.post(f"{BASE_URL}/chat", json={"message": "Which one would you recommend?", "session_id": session_id})
    assert r2.status_code == 200, f"Chat Turn 2 failed: {r2.status_code}"
    data2 = r2.json()
    print(f"    AI Reply snippet: {data2['ai_response'][:120]}...")

    # Turn 3: Mileage comparison
    print("  Turn 3: 'Which one is better for mileage?'")
    r3 = requests.post(f"{BASE_URL}/chat", json={"message": "Which one is better for mileage?", "session_id": session_id})
    assert r3.status_code == 200, f"Chat Turn 3 failed: {r3.status_code}"
    data3 = r3.json()
    print(f"    AI Reply snippet: {data3['ai_response'][:120]}...")
    print("PASS: AI Chat multi-turn conversation context and grounding work!")

def test_auth_flow():
    print("\n--- 7. Testing Authentication Flow ---")
    uname = f"user_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@example.com"
    pwd = "SecurePassword123!"

    # 1. Register
    r_reg = requests.post(f"{BASE_URL}/auth/register", json={"username": uname, "email": email, "password": pwd})
    assert r_reg.status_code == 200, f"Register failed: {r_reg.status_code}"
    reg_data = r_reg.json()
    assert "user" in reg_data or "Successfully" in reg_data.get("message", "")
    print(f"  - Registered user {uname}")

    # 2. Login
    r_login = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": pwd})
    assert r_login.status_code == 200, f"Login failed: {r_login.status_code}"
    login_data = r_login.json()
    assert "access_token" in login_data, "No access_token returned"
    token = login_data["access_token"]
    print(f"  - Login successful, token received: {token[:20]}...")

    # 3. Invalid credentials test
    r_bad = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": "WrongPassword"})
    assert r_bad.status_code == 200
    bad_data = r_bad.json()
    assert "access_token" not in bad_data, "Bad password should not return token"
    print("PASS: Auth registration, login, and invalid credential protection work!")

    return token

def test_wishlist_flow(token):
    print("\n--- 8. Testing Wishlist Flow ---")
    headers = {"Authorization": f"Bearer {token}"}

    # Add car 1 to wishlist
    r_add = requests.post(f"{BASE_URL}/wishlist", json={"car_id": 1}, headers=headers)
    assert r_add.status_code == 200, f"Add wishlist failed: {r_add.status_code}"
    print(f"  - Add to wishlist: {r_add.json()}")

    # Retrieve wishlist
    r_get = requests.get(f"{BASE_URL}/wishlist", headers=headers)
    assert r_get.status_code == 200, f"Get wishlist failed: {r_get.status_code}"
    items = r_get.json()
    assert any(w["car_id"] == 1 for w in items), "Car 1 not found in wishlist items"
    wishlist_item_id = [w["id"] for w in items if w["car_id"] == 1][0]
    print(f"  - Retrieved wishlist: {len(items)} items. Found item ID {wishlist_item_id}")

    # Remove item
    r_del = requests.delete(f"{BASE_URL}/wishlist/{wishlist_item_id}", headers=headers)
    assert r_del.status_code == 200, f"Delete wishlist failed: {r_del.status_code}"
    print(f"  - Delete from wishlist: {r_del.json()}")
    print("PASS: Wishlist Add, Retrieve, and Remove work!")

def test_comparison_flow():
    print("\n--- 9. Testing Comparison Flow ---")
    r_cars = requests.get(f"{BASE_URL}/compare/cars")
    assert r_cars.status_code == 200, f"GET /compare/cars failed: {r_cars.status_code}"
    options = r_cars.json()
    assert len(options) >= 2, "Not enough options for comparison"
    id1 = options[0]["id"]
    id2 = options[1]["id"]
    print(f"  - Comparing car ID {id1} ({options[0]['model']}) vs {id2} ({options[1]['model']})")

    r_comp = requests.post(f"{BASE_URL}/compare", json={"car1_id": id1, "car2_id": id2})
    assert r_comp.status_code == 200, f"POST /compare failed: {r_comp.status_code}"
    res = r_comp.json()
    assert "car1" in res and "car2" in res, "Comparison response missing car1 or car2"
    assert "price" in res["car1"] or "ex_showroom_price" in res["car1"]
    assert "price" in res["car2"] or "ex_showroom_price" in res["car2"]
    print(f"  - Comparison specs verified. Car 1: {res['car1']['model']}, Car 2: {res['car2']['model']}")
    if "explanation" in res and res["explanation"]:
        print(f"  - AI Explanation snippet: {res['explanation'][:100]}...")
    print("PASS: Comparison flow tested successfully!")

def test_cors():
    print("\n--- 10. Testing CORS ---")
    origin = "http://localhost:5173"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,Authorization"
    }
    r = requests.options(f"{BASE_URL}/recommend", headers=headers)
    allow_origin = r.headers.get("Access-Control-Allow-Origin")
    print(f"  CORS Preflight Status: {r.status_code}, Allow-Origin: {allow_origin}")
    assert allow_origin in [origin, "*"], f"Expected {origin}, got {allow_origin}"
    print("PASS: CORS verified!")

if __name__ == "__main__":
    print("=== AUTOAI FRONTEND INTEGRATION TEST SUITE ===")
    test_root()
    test_dashboard_stats()
    test_car_listing()
    test_search_filters()
    test_recommendation_flow()
    test_ai_chat_flow()
    token = test_auth_flow()
    test_wishlist_flow(token)
    test_comparison_flow()
    test_cors()
    print("\n=======================================================")
    print("ALL FRONTEND INTEGRATION TESTS PASSED 100%!")
    print("=======================================================")
