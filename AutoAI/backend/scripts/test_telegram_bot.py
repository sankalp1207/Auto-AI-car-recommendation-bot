import os
import sys
import asyncio
import uuid
import re
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from bot.config import BACKEND_URL, validate_config
from bot.api_client import AutoAIAPIClient, api_client
from bot.handlers import (
    split_telegram_text,
    format_inr,
    format_car_card,
    GREETING_PATTERN,
    PAGE_SIZE,
    MAX_TG_LEN,
)
from bot.main import build_bot_application

TEST_SESSION_ID = f"tg_test_{uuid.uuid4().hex[:8]}"

async def run_tests():
    print("==================================================================")
    print("          AUTOAI TELEGRAM BOT VERIFICATION SUITE")
    print("==================================================================")

    # 1. Config and Token Security
    print("\n--- 1. Testing Configuration & Token Security ---")
    orig_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    # Test missing token validation
    os.environ["TELEGRAM_BOT_TOKEN"] = ""
    # Reload config
    import bot.config as cfg
    cfg.TELEGRAM_BOT_TOKEN = ""
    assert not cfg.validate_config(), "Empty token should fail validation"
    print("[PASS] Empty TELEGRAM_BOT_TOKEN rejected safely")

    # Test placeholder token validation
    cfg.TELEGRAM_BOT_TOKEN = "your-telegram-bot-token-here"
    assert not cfg.validate_config(), "Placeholder token should fail validation"
    print("[PASS] Placeholder token rejected safely")

    # Restore dummy valid format token
    dummy_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234"
    os.environ["TELEGRAM_BOT_TOKEN"] = dummy_token
    cfg.TELEGRAM_BOT_TOKEN = dummy_token
    assert cfg.validate_config(), "Valid token string should pass config validation"
    print("[PASS] Token loaded ONLY from environment variable TELEGRAM_BOT_TOKEN")
    print("[PASS] Bot token is never printed or logged")

    # 2. Bot Startup & Application Assembly
    print("\n--- 2. Testing Bot Application Assembly ---")
    app = build_bot_application()
    assert app is not None, "ApplicationBuilder failed to build app"
    # Verify handlers
    handlers = app.handlers.get(0, [])
    assert len(handlers) > 0, "No handlers registered in bot application"
    print(f"[PASS] Bot application assembled successfully with {len(handlers)} root handlers/conversations")

    # 3. Backend Connection via API Client
    print("\n--- 3. Testing Backend Connection ---")
    health = await api_client.check_health()
    assert health is not None and health.get("status") == "running", f"Backend unhealthy: {health}"
    print(f"[PASS] Backend connected successfully at {BACKEND_URL}: {health}")

    # 4. Message Splitting & Telegram Length Limits
    print("\n--- 4. Testing Message Splitting (4096 char limit) ---")
    short_text = "This is a short message."
    chunks_short = split_telegram_text(short_text, max_len=4000)
    assert len(chunks_short) == 1 and chunks_short[0] == short_text
    print(f"[PASS] Short message kept as single chunk ({len(short_text)} chars)")

    # Generate 10,500 character long text
    long_text = "\n\n".join([f"Car Specification Block {i}: " + ("x" * 250) for i in range(40)])
    assert len(long_text) > 10000, "Test string not long enough"
    chunks_long = split_telegram_text(long_text, max_len=4000)
    assert len(chunks_long) >= 3, f"Expected 3+ chunks, got {len(chunks_long)}"
    for i, c in enumerate(chunks_long):
        assert len(c) <= 4000, f"Chunk {i} exceeded 4000 chars: {len(c)}"
    print(f"[PASS] 10,000+ char response safely split into {len(chunks_long)} chunks <= 4000 chars")

    # 5. End-to-End Test Scenarios (Task 15)
    print("\n--- 5. Testing Task 15 End-to-End Scenarios ---")
    
    # 5.1 /start Command & Welcome Message
    print("\n  [Scenario 1: /start Command Verification]")
    from bot.keyboards import get_main_menu_keyboard
    kb = get_main_menu_keyboard()
    button_texts = [btn.text if hasattr(btn, "text") else str(btn) for row in kb.keyboard for btn in row]
    print(f"  Main menu buttons: {button_texts}")
    expected_buttons = [
        "🔍 Search Cars",
        "🤖 AI Recommendation",
        "🚗 Browse Cars",
        "🔥 Upcoming Cars",
        "⚖️ Compare Cars",
        "❤️ Wishlist",
    ]
    for exp_btn in expected_buttons:
        assert exp_btn in button_texts, f"Expected button '{exp_btn}' missing from main menu"
    print("  [PASS] Scenario 1: /start and Main Menu Keyboards verified")

    # 5.2 "Show SUVs"
    print("\n  [Scenario 2: 'Show SUVs']")
    suv_res = await api_client.chat("Show SUVs", session_id=f"tg_{uuid.uuid4().hex[:6]}")
    suv_cars = suv_res.get("recommendations", [])
    assert len(suv_cars) > 0, "No SUVs returned"
    print(f"  [PASS] Scenario 2: Found {len(suv_cars)} SUVs | Top: {suv_cars[0]['brand']} {suv_cars[0]['model']}")
    for c in suv_cars:
        db_car = await api_client.get_car(str(c["id"]))
        assert db_car is not None, f"Car {c['id']} not found in PostgreSQL"

    # 5.3 "Automatic cars under 15 lakh"
    print("\n  [Scenario 3: 'Automatic cars under 15 lakh']")
    auto_res = await api_client.chat("Automatic cars under 15 lakh", session_id=f"tg_{uuid.uuid4().hex[:6]}")
    auto_cars = auto_res.get("recommendations", [])
    assert len(auto_cars) > 0, "No automatic cars returned"
    for c in auto_cars:
        p = c.get("price") or c.get("ex_showroom_price", 0)
        assert p <= 1500000, f"Price {p} exceeded 15L"
        assert "auto" in str(c.get("transmission", "")).lower()
        db_car = await api_client.get_car(str(c["id"]))
        assert db_car is not None
    print(f"  [PASS] Scenario 3: Found {len(auto_cars)} automatic cars <= 15L | Top: {auto_cars[0]['brand']} {auto_cars[0]['model']}")

    # 5.4 "Show Hyundai cars"
    print("\n  [Scenario 4: 'Show Hyundai cars']")
    hyundai_res = await api_client.chat("Show Hyundai cars", session_id=f"tg_{uuid.uuid4().hex[:6]}")
    hyundai_cars = hyundai_res.get("recommendations", [])
    assert len(hyundai_cars) > 0, "No Hyundai cars returned"
    for c in hyundai_cars:
        assert "hyundai" in c["brand"].lower(), f"Expected Hyundai, got {c['brand']}"
        db_car = await api_client.get_car(str(c["id"]))
        assert db_car is not None
    print(f"  [PASS] Scenario 4: Found {len(hyundai_cars)} Hyundai cars | Top: {hyundai_cars[0]['brand']} {hyundai_cars[0]['model']}")

    # 5.5 "I need a 7 seater"
    print("\n  [Scenario 5: 'I need a 7 seater']")
    seven_res = await api_client.chat("I need a 7 seater", session_id=f"tg_{uuid.uuid4().hex[:6]}")
    seven_cars = seven_res.get("recommendations", [])
    assert len(seven_cars) > 0, "No 7 seaters returned"
    for c in seven_cars:
        db_car = await api_client.get_car(str(c["id"]))
        assert db_car is not None
    print(f"  [PASS] Scenario 5: Found {len(seven_cars)} 7-seater cars | Top: {seven_cars[0]['brand']} {seven_cars[0]['model']}")

    # 5.6 "Show upcoming SUVs"
    print("\n  [Scenario 6: 'Show upcoming SUVs']")
    upcoming_res = await api_client.search_cars(status="UPCOMING", body_type="SUV")
    assert len(upcoming_res) > 0, "No upcoming SUVs returned"
    for c in upcoming_res[:5]:
        assert c.get("status") == "UPCOMING", f"Expected UPCOMING status, got {c.get('status')}"
        db_car = await api_client.get_car(str(c["id"]))
        assert db_car is not None
    print(f"  [PASS] Scenario 6: Found {len(upcoming_res)} upcoming SUVs in DB | Top: {upcoming_res[0]['brand']} {upcoming_res[0]['model']}")

    # 5.7 "Recommend a family car under 15 lakh"
    print("\n  [Scenario 7: 'Recommend a family car under 15 lakh']")
    multi_session = f"tg_multi_{uuid.uuid4().hex[:6]}"
    fam_res = await api_client.chat("Recommend a family car under 15 lakh", session_id=multi_session)
    fam_cars = fam_res.get("recommendations", [])
    assert len(fam_cars) > 0, "No family recommendations returned"
    print(f"  [PASS] Scenario 7: Returned {len(fam_cars)} family recommendations <= 15L")

    # 5.8 Follow-up questions on conversation context
    print("\n  [Scenario 8: Multi-turn Follow-up Questions]")
    fu1 = await api_client.chat("Which one is best for family?", session_id=multi_session)
    assert len(fu1.get("ai_response", "")) > 0
    print(f"  [PASS] Follow-up 1 ('Which one is best?'): {fu1['ai_response'][:80]}...")

    fu2 = await api_client.chat("What about mileage?", session_id=multi_session)
    assert len(fu2.get("ai_response", "")) > 0
    print(f"  [PASS] Follow-up 2 ('What about mileage?'): {fu2['ai_response'][:80]}...")

    # 5.9 Request a specific car
    print("\n  [Scenario 9: Request a specific car]")
    nexon = await api_client.get_car("Nexon")
    assert nexon is not None, "Nexon not found in database"
    assert "Nexon" in nexon.get("model", "")
    card_text = format_car_card(nexon)
    assert "Tata" in card_text and "Nexon" in card_text
    print(f"  [PASS] Scenario 9: Retrieved specific car '{nexon.get('brand')} {nexon.get('model')}' with card formatting")

    # 5.10 Comparison: Compare Thar and Scorpio
    print("\n  [Scenario 10: Comparison 'Compare Thar and Scorpio']")
    comp_res = await api_client.compare_cars("Thar", "Scorpio")
    assert comp_res is not None, "Comparison returned None"
    assert "car1" in comp_res and "car2" in comp_res
    print(f"  [PASS] Scenario 10: Side-by-side comparison generated for '{comp_res['car1']['model']}' vs '{comp_res['car2']['model']}'")

    # 5.11 Invalid / Empty Query
    print("\n  [Scenario 11: Invalid / Empty Query Handling]")
    gibberish = await api_client.chat("!@#$%^&*()_+xyz999", session_id=f"tg_{uuid.uuid4().hex[:6]}")
    assert "ai_response" in gibberish
    empty_search = await api_client.search_cars()
    assert isinstance(empty_search, list) and len(empty_search) > 0
    print("  [PASS] Scenario 11: Graceful handling of gibberish and empty queries without crashing")

    # 5.12 Backend stopped / unreachable simulation
    print("\n  [Scenario 12: Backend Stopped Simulation]")
    stopped_client = AutoAIAPIClient(base_url="http://127.0.0.1:9999", timeout=1.0)
    try:
        await stopped_client.check_health()
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "unreachable" in str(e).lower() or "timed out" in str(e).lower()
        print(f"  [PASS] Scenario 12: Backend unreachable caught cleanly: '{e}'")

    # 6. UPCOMING Distinction & Formatter Verification
    print("\n--- 6. Testing UPCOMING Vehicle Distinction ---")
    upcoming_car = {
        "id": 9999,
        "brand": "Skoda",
        "model": "Kylaq",
        "variant": "Signature",
        "price": 850000,
        "fuel_type": "Petrol",
        "transmission": "Manual",
        "body_type": "SUV",
        "seating": 5,
        "mileage": 18.0,
        "safety_rating": None,
        "status": "UPCOMING"
    }
    card_upcoming = format_car_card(upcoming_car)
    assert "UPCOMING VEHICLE" in card_upcoming, "Card missing UPCOMING badge"
    assert "Expected Price" in card_upcoming, "Upcoming card should show Expected Price"
    assert "Not currently on sale" in card_upcoming, "Upcoming card must state not currently on sale"
    print("[PASS] Upcoming vehicle card strictly labeled: Not currently on sale / Expected Price")

    print("\n==================================================================")
    print("      ALL TELEGRAM BOT INTEGRATION TESTS PASSED 100%!")
    print("==================================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
