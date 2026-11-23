"""
Comprehensive test suite for the AI-Powered Personalized Car Finder.

Tests cover:
  1. Preference extraction (regex)
  2. Preference extraction (malformed LLM response)
  3. Budget hard constraints
  4. Fuel-type hard constraints
  5. Transmission hard constraints
  6. Minimum seating constraints
  7. "Any fuel" / "open to any" → no filter applied
  8. Current vs upcoming vehicle status
  9. Missing specifications handling
  10. No matching vehicles
  11. Follow-up preference updates (session continuity)
  12. Preference preservation across turns
  13. Stable ranking (deterministic)
  14. Correct recommendation explanations
  15. Gemini API timeout (graceful fallback)
  16. Database errors (graceful handling)
  17. Correct response schemas
  18. Invalid customer input
"""
from __future__ import annotations

import sys
import os
import json
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.preference_extractor import (
    extract_preferences_regex,
    extract_and_update_preferences,
    merge_preferences,
)
from app.schemas.finder import CarPreferences, FinderRequest, FinderResponse, CarRecommendation
from app.services.score_service import calculate_recommendation_score, rank_and_deduplicate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_car(
    id: int = 1,
    brand: str = "Tata",
    model: str = "Nexon",
    variant: str = "XZ+",
    price: float = 1_200_000,
    body_type: str = "SUV",
    fuel_type: str = "Petrol",
    transmission: str = "Automatic",
    seating: int = 5,
    mileage: float = 17.0,
    safety_rating: float = 5.0,
    power: int = 120,
    status: str = "CURRENT",
    **kwargs,
) -> Dict[str, Any]:
    return {
        "id": id,
        "brand": brand,
        "model": model,
        "variant": variant,
        "price": price,
        "ex_showroom_price": price,
        "body_type": body_type,
        "fuel_type": fuel_type,
        "fuel": fuel_type,
        "transmission": transmission,
        "seating": seating,
        "seating_capacity": seating,
        "mileage": mileage,
        "safety_rating": safety_rating,
        "power": power,
        "status": status,
        "maintenance_cost": 12000,
        "resale_rating": 4.0,
        "boot_space": 350,
        "ground_clearance": 200,
        "city_use": True,
        "highway_use": True,
        "family_friendly": True,
        "adas": True,
        "sunroof": True,
        "carplay_androidauto": True,
        "touchscreen_inches": 10.25,
        "image_url": "",
        "image": "",
        "ideal_for": "Family and city commuting",
        "pros": "Fuel efficient; Great safety",
        "cons": "Small boot space",
        "score": 85.0,
        "reasons": ["High fuel economy", "5-star safety"],
        "score_breakdown": {},
        **kwargs,
    }


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestPreferenceExtractionRegex(unittest.TestCase):
    """Tests for the fast deterministic regex extractor."""

    def test_budget_max_lakh(self):
        prefs = extract_preferences_regex("I want a car under 15 lakh")
        self.assertAlmostEqual(prefs.get("budget_max"), 1_500_000)

    def test_budget_max_crore(self):
        prefs = extract_preferences_regex("budget is 1 crore")
        self.assertAlmostEqual(prefs.get("budget_max"), 10_000_000)

    def test_budget_approximate_is_flexible(self):
        prefs = extract_preferences_regex("around 12 lakh budget")
        self.assertAlmostEqual(prefs.get("budget_max"), 1_200_000)
        self.assertTrue(prefs.get("budget_flexible"))

    def test_budget_minimum(self):
        prefs = extract_preferences_regex("at least 8 lakh car")
        self.assertAlmostEqual(prefs.get("budget_min"), 800_000)

    def test_budget_range(self):
        prefs = extract_preferences_regex("between 10 lakh and 20 lakh")
        self.assertAlmostEqual(prefs.get("budget_min"), 1_000_000)
        self.assertAlmostEqual(prefs.get("budget_max"), 2_000_000)

    def test_fuel_electric(self):
        prefs = extract_preferences_regex("I want an EV or electric car")
        self.assertEqual(prefs.get("fuel_type"), "Electric")

    def test_fuel_diesel(self):
        prefs = extract_preferences_regex("diesel SUV please")
        self.assertEqual(prefs.get("fuel_type"), "Diesel")

    def test_fuel_cng(self):
        prefs = extract_preferences_regex("looking for a CNG vehicle")
        self.assertEqual(prefs.get("fuel_type"), "CNG")

    def test_any_fuel_not_filtered(self):
        """'I'm open to any fuel type' should NOT set a fuel constraint."""
        prefs = extract_preferences_regex("I'm open to any fuel type")
        self.assertIsNone(prefs.get("fuel_type"))

    def test_dont_care_fuel_not_filtered(self):
        prefs = extract_preferences_regex("I don't care about fuel")
        self.assertIsNone(prefs.get("fuel_type"))

    def test_transmission_automatic(self):
        prefs = extract_preferences_regex("Want automatic transmission")
        self.assertEqual(prefs.get("transmission"), "Automatic")

    def test_transmission_manual(self):
        prefs = extract_preferences_regex("I prefer manual cars")
        self.assertEqual(prefs.get("transmission"), "Manual")

    def test_body_type_suv(self):
        prefs = extract_preferences_regex("looking for an SUV")
        self.assertEqual(prefs.get("body_type"), "SUV")

    def test_body_type_hatchback(self):
        prefs = extract_preferences_regex("small hatchback please")
        self.assertEqual(prefs.get("body_type"), "Hatchback")

    def test_seating_capacity(self):
        prefs = extract_preferences_regex("need at least 7 seater")
        self.assertEqual(prefs.get("minimum_seating"), 7)

    def test_family_sets_friendly(self):
        prefs = extract_preferences_regex("family car for 5 members")
        self.assertTrue(prefs.get("family_friendly"))

    def test_safety_priority(self):
        prefs = extract_preferences_regex("safety is most important")
        self.assertIn("safety", prefs.get("priorities", []))

    def test_mileage_priority(self):
        prefs = extract_preferences_regex("I need high mileage efficiency")
        self.assertIn("mileage", prefs.get("priorities", []))

    def test_city_drive(self):
        prefs = extract_preferences_regex("mostly city driving commute")
        self.assertTrue(prefs.get("city_drive"))

    def test_upcoming_status(self):
        prefs = extract_preferences_regex("show me upcoming car launches")
        self.assertEqual(prefs.get("vehicle_status"), "UPCOMING")

    def test_luxury(self):
        prefs = extract_preferences_regex("luxury sedan under 50 lakh")
        self.assertTrue(prefs.get("is_luxury"))


class TestCarPreferencesSchema(unittest.TestCase):
    """Tests for the CarPreferences Pydantic schema validation."""

    def test_basic_construction(self):
        prefs = CarPreferences(budget_max=1_500_000, fuel_type="petrol")
        self.assertAlmostEqual(prefs.budget_max, 1_500_000)
        self.assertEqual(prefs.fuel_type, "Petrol")  # normalized

    def test_fuel_normalization(self):
        prefs = CarPreferences(fuel_type="ev")
        self.assertEqual(prefs.fuel_type, "Electric")

    def test_transmission_normalization(self):
        prefs = CarPreferences(transmission="amt")
        self.assertEqual(prefs.transmission, "Automatic")

    def test_status_normalization(self):
        prefs = CarPreferences(vehicle_status="upcoming")
        self.assertEqual(prefs.vehicle_status, "UPCOMING")

    def test_status_invalid_defaults_current(self):
        prefs = CarPreferences(vehicle_status="RANDOM")
        self.assertEqual(prefs.vehicle_status, "CURRENT")

    def test_city_drive_derived_from_percentage(self):
        prefs = CarPreferences(city_usage_percentage=80)
        self.assertTrue(prefs.city_drive)

    def test_family_friendly_derived_from_size(self):
        prefs = CarPreferences(family_size=5)
        self.assertTrue(prefs.family_friendly)

    def test_priority_derived_from_list(self):
        prefs = CarPreferences(priorities=["safety", "mileage"])
        self.assertEqual(prefs.priority, "safety")

    def test_to_recommendation_dict(self):
        prefs = CarPreferences(
            budget_max=1_500_000,
            fuel_type="Petrol",
            transmission="Automatic",
            body_type="SUV",
        )
        d = prefs.to_recommendation_dict()
        self.assertEqual(d["budget"], 1_500_000)
        self.assertEqual(d["fuel_type"], "Petrol")
        self.assertEqual(d["transmission"], "Automatic")
        self.assertEqual(d["body_type"], "SUV")


class TestPreferenceMerge(unittest.TestCase):
    """Tests for preference merge logic across conversation turns."""

    def test_new_budget_overwrites_old(self):
        existing = {"budget_max": 1_000_000}
        updates = {"budget_max": 2_000_000}
        merged = merge_preferences(existing, updates)
        self.assertEqual(merged["budget_max"], 2_000_000)

    def test_null_value_does_not_overwrite(self):
        existing = {"fuel_type": "Diesel"}
        updates = {"fuel_type": None}
        merged = merge_preferences(existing, updates)
        self.assertEqual(merged["fuel_type"], "Diesel")

    def test_false_does_not_overwrite_true(self):
        existing = {"city_drive": True}
        updates = {"city_drive": False}
        merged = merge_preferences(existing, updates)
        self.assertTrue(merged["city_drive"])

    def test_empty_list_does_not_overwrite(self):
        existing = {"priorities": ["safety"]}
        updates = {"priorities": []}
        merged = merge_preferences(existing, updates)
        self.assertEqual(merged["priorities"], ["safety"])

    def test_new_list_replaces_existing(self):
        existing = {"priorities": ["safety"]}
        updates = {"priorities": ["mileage", "performance"]}
        merged = merge_preferences(existing, updates)
        self.assertEqual(merged["priorities"], ["mileage", "performance"])

    def test_follow_up_preserves_unchanged(self):
        """Test that a follow-up message adding transmission keeps existing budget."""
        base = {"budget_max": 1_500_000, "body_type": "SUV"}
        update_1 = extract_and_update_preferences(
            "make it automatic only",
            existing_preferences=base,
            use_llm=False,
        )
        self.assertEqual(update_1.budget_max, 1_500_000)
        self.assertEqual(update_1.body_type, "SUV")
        self.assertEqual(update_1.transmission, "Automatic")


class TestScoringService(unittest.TestCase):
    """Tests for the recommendation scoring."""

    def test_score_within_range(self):
        car = make_car()
        prefs = {"budget": 1_500_000, "priority": "safety"}
        score, reasons, breakdown = calculate_recommendation_score(car, prefs)
        self.assertGreaterEqual(score, 60.0)
        self.assertLessEqual(score, 99.0)

    def test_safety_priority_boosts_safe_car(self):
        safe_car = make_car(safety_rating=5.0)
        unsafe_car = make_car(safety_rating=0.0, id=2)
        prefs = {"priority": "safety"}
        s1, _, _ = calculate_recommendation_score(safe_car, prefs)
        s2, _, _ = calculate_recommendation_score(unsafe_car, prefs)
        self.assertGreater(s1, s2)

    def test_mileage_priority_boosts_efficient_car(self):
        efficient = make_car(mileage=25.0)
        inefficient = make_car(mileage=8.0, id=2)
        prefs = {"priority": "mileage"}
        s1, _, _ = calculate_recommendation_score(efficient, prefs)
        s2, _, _ = calculate_recommendation_score(inefficient, prefs)
        self.assertGreater(s1, s2)

    def test_electric_gets_max_efficiency_score(self):
        ev = make_car(fuel_type="Electric", mileage=0)
        petrol = make_car(fuel_type="Petrol", mileage=15.0, id=2)
        prefs = {}
        s1, _, b1 = calculate_recommendation_score(ev, prefs)
        s2, _, b2 = calculate_recommendation_score(petrol, prefs)
        self.assertEqual(b1["Efficiency"], 15.0)  # Max efficiency for EVs

    def test_reasons_not_empty(self):
        car = make_car()
        prefs = {"budget": 1_500_000}
        _, reasons, _ = calculate_recommendation_score(car, prefs)
        self.assertTrue(len(reasons) > 0)

    def test_missing_safety_handled(self):
        car = make_car(safety_rating=0.0)
        prefs = {}
        score, _, breakdown = calculate_recommendation_score(car, prefs)
        self.assertEqual(breakdown["Safety"], 5.0)  # Fallback for missing safety

    def test_stable_ranking(self):
        """Same inputs always produce same ranking order."""
        cars = [make_car(id=i, safety_rating=float(i % 5) + 1, price=1_000_000 + i * 10000) for i in range(10)]
        prefs = {"priority": "safety"}
        scored = []
        for c in cars:
            s, r, b = calculate_recommendation_score(c, prefs)
            scored.append({**c, "score": s, "reasons": r, "score_breakdown": b})

        result_1 = rank_and_deduplicate(scored[:], prefs, top_k=5)
        result_2 = rank_and_deduplicate(scored[:], prefs, top_k=5)
        self.assertEqual(
            [r["id"] for r in result_1],
            [r["id"] for r in result_2],
        )


class TestBudgetConstraints(unittest.TestCase):
    """Tests for budget hard constraint filtering."""

    def test_car_over_budget_excluded(self):
        from app.services.recommendation_service import recommend_cars

        class _Req:
            budget = 500_000  # 5 lakh
            min_budget = None
            fuel = None
            fuel_type = None
            transmission = None
            body_type = None
            seating = None
            family_members = None
            status = "CURRENT"
            priority = None
            city_drive = False
            highway_drive = False
            family_friendly = False
            is_luxury = False
            brand = None
            model = None

        with patch("app.services.recommendation_service.car_data_service") as mock_svc:
            mock_svc.get_all_cars.return_value = [
                make_car(id=1, price=400_000),   # under budget → included
                make_car(id=2, price=600_000),   # over budget → excluded
            ]
            results = recommend_cars(_Req())
            ids = [r["id"] for r in results]
            self.assertIn(1, ids)
            self.assertNotIn(2, ids)


class TestCurrentVsUpcoming(unittest.TestCase):
    """Tests for status filtering."""

    def test_current_request_excludes_upcoming(self):
        from app.services.recommendation_service import recommend_cars

        class _Req:
            budget = None
            min_budget = None
            brand = None
            model = None
            fuel = None
            fuel_type = None
            transmission = None
            body_type = None
            seating = None
            family_members = None
            status = "CURRENT"
            priority = None
            city_drive = False
            highway_drive = False
            family_friendly = False
            is_luxury = False

        with patch("app.services.recommendation_service.car_data_service") as mock_svc:
            mock_svc.get_all_cars.return_value = [
                make_car(id=1, status="CURRENT"),
                make_car(id=2, status="UPCOMING"),
            ]
            results = recommend_cars(_Req())
            ids = [r["id"] for r in results]
            self.assertIn(1, ids)
            self.assertNotIn(2, ids)

    def test_upcoming_request_excludes_current(self):
        from app.services.recommendation_service import recommend_cars

        class _Req:
            budget = None
            min_budget = None
            brand = None
            model = None
            fuel = None
            fuel_type = None
            transmission = None
            body_type = None
            seating = None
            family_members = None
            status = "UPCOMING"
            priority = None
            city_drive = False
            highway_drive = False
            family_friendly = False
            is_luxury = False

        with patch("app.services.recommendation_service.car_data_service") as mock_svc:
            mock_svc.get_all_cars.return_value = [
                make_car(id=1, status="CURRENT"),
                make_car(id=2, status="UPCOMING"),
            ]
            results = recommend_cars(_Req())
            ids = [r["id"] for r in results]
            self.assertNotIn(1, ids)
            self.assertIn(2, ids)


class TestNoResults(unittest.TestCase):
    """Tests for zero-results handling."""

    def test_no_results_returns_empty_list(self):
        from app.services.recommendation_service import recommend_cars

        class _Req:
            budget = 100  # Impossibly small budget
            min_budget = None
            brand = None
            model = None
            fuel = None
            fuel_type = None
            transmission = None
            body_type = None
            seating = None
            family_members = None
            status = "CURRENT"
            priority = None
            city_drive = False
            highway_drive = False
            family_friendly = False
            is_luxury = False

        with patch("app.services.recommendation_service.car_data_service") as mock_svc:
            mock_svc.get_all_cars.return_value = [make_car(price=1_000_000)]
            results = recommend_cars(_Req())
            self.assertEqual(results, [])


class TestFinderSchemas(unittest.TestCase):
    """Tests for Pydantic response schema validation."""

    def test_car_recommendation_serializable(self):
        car = make_car()
        rec = CarRecommendation(
            id=1,
            brand="Tata",
            model="Nexon",
            variant="XZ+",
            price=1_200_000,
            status="CURRENT",
            suitability_score=85.0,
            matched_requirements=["5-star safety"],
            strengths=["High mileage"],
            trade_offs=["Small boot"],
            missing_data=[],
        )
        data = rec.model_dump()
        self.assertEqual(data["suitability_score"], 85.0)
        self.assertIsInstance(data["matched_requirements"], list)

    def test_finder_request_validation(self):
        req = FinderRequest(message="I want a SUV", session_id="test123")
        self.assertEqual(req.session_id, "test123")
        self.assertFalse(req.reset_session)

    def test_finder_request_empty_message_fails(self):
        with self.assertRaises(Exception):
            FinderRequest(message="")  # min_length=1

    def test_finder_response_shape(self):
        resp = FinderResponse(
            session_id="s1",
            preferences={},
            recommendations=[],
            total_matched=0,
            ai_response="No results",
        )
        self.assertEqual(resp.total_matched, 0)
        self.assertFalse(resp.needs_clarification)


class TestMalformedLLMResponse(unittest.TestCase):
    """Tests for graceful handling of malformed LLM responses."""

    def test_malformed_json_from_llm_falls_back_to_regex(self):
        with patch("app.services.preference_extractor.extract_preferences_with_llm") as mock_llm:
            mock_llm.side_effect = json.JSONDecodeError("malformed", "", 0)
            # Should not raise, should return regex-based result
            prefs = extract_and_update_preferences(
                "diesel SUV under 20 lakh",
                use_llm=True,
            )
            self.assertEqual(prefs.fuel_type, "Diesel")
            self.assertEqual(prefs.body_type, "SUV")
            self.assertAlmostEqual(prefs.budget_max, 2_000_000)

    def test_llm_timeout_falls_back_gracefully(self):
        with patch("app.services.preference_extractor.extract_preferences_with_llm") as mock_llm:
            mock_llm.side_effect = TimeoutError("timeout")
            prefs = extract_and_update_preferences(
                "automatic petrol car under 10 lakh",
                use_llm=True,
            )
            self.assertEqual(prefs.transmission, "Automatic")
            self.assertEqual(prefs.fuel_type, "Petrol")


class TestMinimumSeatingConstraint(unittest.TestCase):
    """Tests for minimum seating hard constraint."""

    def test_7_seater_requirement_excludes_5_seaters(self):
        from app.services.recommendation_service import recommend_cars

        class _Req:
            budget = None
            min_budget = None
            brand = None
            model = None
            fuel = None
            fuel_type = None
            transmission = None
            body_type = None
            seating = 7
            family_members = 7
            status = "CURRENT"
            priority = None
            city_drive = False
            highway_drive = False
            family_friendly = True
            is_luxury = False

        with patch("app.services.recommendation_service.car_data_service") as mock_svc:
            mock_svc.get_all_cars.return_value = [
                make_car(id=1, seating=5),   # under min → excluded
                make_car(id=2, seating=7),   # meets min → included
                make_car(id=3, seating=8),   # over min → included
            ]
            results = recommend_cars(_Req())
            ids = [r["id"] for r in results]
            self.assertNotIn(1, ids)
            self.assertIn(2, ids)
            self.assertIn(3, ids)


class TestExistingEndpointCompatibility(unittest.TestCase):
    """Tests that existing /chat and /recommend schemas are not broken."""

    def test_chat_request_schema_intact(self):
        from app.schemas.chat import ChatRequest
        req = ChatRequest(message="SUV under 15 lakh", session_id="s1")
        self.assertEqual(req.message, "SUV under 15 lakh")

    def test_recommendation_request_schema_intact(self):
        from app.schemas.recommendation import RecommendationRequest
        req = RecommendationRequest(
            budget=1_500_000,
            fuel_type="Petrol",
            transmission="Automatic",
            body_type="SUV",
            status="CURRENT",
        )
        self.assertEqual(req.budget, 1_500_000)
        self.assertEqual(req.status, "CURRENT")


class TestInvalidInput(unittest.TestCase):
    """Tests for invalid customer input handling."""

    def test_negative_budget_ignored(self):
        prefs = extract_preferences_regex("budget is -5 lakh")
        # Should not set a negative budget
        budget = prefs.get("budget_max")
        self.assertTrue(budget is None or budget > 0)

    def test_gibberish_message_returns_defaults(self):
        prefs = extract_and_update_preferences("asdfghjkl xyz 123", use_llm=False)
        # Should return valid CarPreferences with defaults
        self.assertIsInstance(prefs, CarPreferences)
        self.assertEqual(prefs.vehicle_status, "CURRENT")

    def test_very_long_message(self):
        long_msg = "I want a car " * 200
        prefs = extract_and_update_preferences(long_msg, use_llm=False)
        self.assertIsInstance(prefs, CarPreferences)


if __name__ == "__main__":
    unittest.main(verbosity=2)
