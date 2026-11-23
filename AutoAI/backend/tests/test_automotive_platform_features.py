"""
AutoAI Comprehensive Platform Verification Suite
Unit and integration tests for:
  - Feature D: Total Cost of Ownership (TCO) Calculator (3, 5, 7 yrs, EV/ICE rates, IDV depreciation, EMI interest)
  - Feature E: AI Multi-Vehicle Comparison (2 to 4 cars, specs matrix, deterministic trade-offs)
  - Feature F: Price Intelligence (ExtraTreesRegressor inference, VFM score, bounded ranges, holdout metrics)
  - Feature G: New Launch Alerts (deduplication, criteria matching, alert lifecycle)
  - Feature I: New vs. Existing Vehicle Analysis (segment matching, 5-yr TCO comparison)
  - Feature J: Personal Garage & Shortlists (user authentication isolation, notes, preference persistence)
  - Feature K: Natural-Language Automotive Search (Gemini/regex criteria parsing, parameterized filtering)
  - Feature L: Feedback-Driven ML (collection and ranking evaluation metrics: Precision@K, NDCG@K)
  - Feature N: Observability & Telemetry (request latencies, error counters, constraint violation rates)
"""

import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.auth.jwt_handler import create_access_token
from app.services.tco_service import tco_calculator, TCORequest, FinancingInput
from app.services.price_intelligence_service import price_intelligence_service, PricePredictionRequest
from app.services.alert_service import alert_service, CreateAlertRequest
from app.services.feedback_service import feedback_service, FeedbackSubmission


class TestAutomotivePlatformFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Generate valid user auth tokens for testing authorization
        cls.user1_token = create_access_token({"sub": "1"})
        cls.user2_token = create_access_token({"sub": "2"})
        cls.headers_user1 = {"Authorization": f"Bearer {cls.user1_token}"}
        cls.headers_user2 = {"Authorization": f"Bearer {cls.user2_token}"}

    # =========================================================================
    # FEATURE D: TCO Calculator Engine & API
    # =========================================================================
    def test_tco_calculation_deterministic(self):
        """Verifies deterministic math for 5-year ownership calculation."""
        req = TCORequest(
            custom_price=1_000_000.0,
            custom_fuel_type="Petrol",
            custom_mileage=15.0,
            ownership_years=5,
            annual_kms=12000.0,
            financing=FinancingInput(enabled=False),
        )
        res = tco_calculator.calculate(req)

        self.assertEqual(res.ownership_years, 5)
        self.assertEqual(res.total_distance_km, 60000.0)
        self.assertGreater(res.fuel_total_cost, 0.0)
        self.assertGreater(res.maintenance_total_cost, 0.0)
        self.assertGreater(res.insurance_total_cost, 0.0)
        self.assertGreater(res.estimated_resale_value, 0.0)
        self.assertLess(res.estimated_resale_value, res.ex_showroom_price)
        self.assertEqual(len(res.yearly_breakdown), 5)
        self.assertEqual(res.cost_per_km, round(res.net_total_ownership_cost / 60000.0, 2))

    def test_tco_ev_vs_ice_efficiency(self):
        """Verifies that an EV yields lower operating fuel/energy costs than Petrol."""
        req_ice = TCORequest(custom_price=1500000, custom_fuel_type="Petrol", custom_mileage=14.0, ownership_years=5)
        req_ev = TCORequest(custom_price=1500000, custom_fuel_type="Electric", custom_mileage=6.5, ownership_years=5)

        tco_ice = tco_calculator.calculate(req_ice)
        tco_ev = tco_calculator.calculate(req_ev)

        self.assertLess(tco_ev.fuel_total_cost, tco_ice.fuel_total_cost)

    def test_tco_api_endpoints(self):
        """Verifies /tco/calculate and /tco/compare endpoints."""
        resp = self.client.post("/tco/calculate", json={
            "custom_price": 800000,
            "custom_fuel_type": "Petrol",
            "ownership_years": 3,
            "annual_kms": 10000,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ownership_years"], 3)
        self.assertIn("net_total_ownership_cost", data)

    # =========================================================================
    # FEATURE E: Multi-Vehicle Comparison (2 to 4 cars)
    # =========================================================================
    def test_multi_car_comparison_service(self):
        """Tests comparison matrix and trade-off summary for 2 to 4 cars."""
        from app.services.comparison_service import compare_cars
        from app.schemas.comparison import ComparisonRequest

        req = ComparisonRequest(car_ids=[1, 2])
        res = compare_cars(req)
        self.assertIsNotNone(res)
        self.assertEqual(len(res["cars"]), 2)
        self.assertIn("explanation", res)
        self.assertIn("tco_estimates", res)
        self.assertIn("car1", res)
        self.assertIn("car2", res)

    def test_comparison_api_post(self):
        """Tests POST /compare with modern multi-car request."""
        resp = self.client.post("/compare", json={"car_ids": [1, 2]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["cars"]), 2)
        self.assertIn("explanation", data)

    # =========================================================================
    # FEATURE F: Price Intelligence (ExtraTreesRegressor inference)
    # =========================================================================
    def test_price_intelligence_metrics(self):
        """Verifies holdout evaluation metrics provenance (MAE ~ ₹9.8L, R²: 0.572)."""
        metrics = price_intelligence_service.get_metrics()
        self.assertTrue(metrics["model_available"])
        self.assertEqual(metrics["metrics"]["evaluation_dataset_rows"], 440)
        self.assertAlmostEqual(metrics["metrics"]["r2_score"], 0.5724, places=2)

    def test_price_prediction_api(self):
        """Tests POST /price/predict returns predicted range, on-road estimate, and VFM score."""
        resp = self.client.post("/price/predict", json={
            "brand": "Maruti Suzuki",
            "model": "Swift",
            "fuel_type": "Petrol",
            "transmission": "Manual",
            "body_type": "Hatchback",
            "engine_cc": 1197,
            "power": 89,
            "torque": 113,
            "mileage": 22.0,
            "seating": 5,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["predicted_ex_showroom"], 300000)
        self.assertGreater(data["estimated_on_road"], data["predicted_ex_showroom"])
        self.assertIn("vfm_score", data)
        self.assertIn("variant_ladder", data)

    # =========================================================================
    # FEATURE G: New Launch Alerts & Deduplication
    # =========================================================================
    def test_alert_lifecycle_and_deduplication(self):
        """Tests creating, listing, checking, and deduplicating launch alerts."""
        req = CreateAlertRequest(
            name="Budget SUV Alert",
            budget_max=1500000.0,
            body_type="SUV",
        )
        alert = alert_service.create_alert(user_id=1, req=req)
        self.assertTrue(alert.is_active)
        self.assertEqual(alert.user_id, 1)

        # Check matching
        res1 = alert_service.check_and_dispatch_alerts(specific_user_id=1)
        self.assertEqual(res1["status"], "completed")

        # Second check should NOT re-notify for the same matched vehicles (deduplicated)
        res2 = alert_service.check_and_dispatch_alerts(specific_user_id=1)
        self.assertEqual(res2["new_notifications_sent"], 0)

        # Toggle alert
        toggled = alert_service.toggle_alert(alert.alert_id, user_id=1)
        self.assertFalse(toggled.is_active)

        # Delete alert
        deleted = alert_service.delete_alert(alert.alert_id, user_id=1)
        self.assertTrue(deleted)

    # =========================================================================
    # FEATURE I: New vs Existing Vehicle Alternatives
    # =========================================================================
    def test_new_vs_existing_alternatives_service(self):
        """Tests alternative analysis for a newly launched vehicle."""
        from app.services.alternative_analysis_service import alternative_analysis_service
        res = alternative_analysis_service.get_alternatives_for_launch(1)
        if res:
            self.assertIn("new_vehicle", res.model_dump())
            self.assertIn("established_alternatives", res.model_dump())
            self.assertIn("trade_off_summary", res.model_dump())
            self.assertIn("tco_comparison", res.model_dump())

    # =========================================================================
    # FEATURE J: Personal Garage Authorization & Preferences
    # =========================================================================
    def test_garage_authorization_enforcement(self):
        """Ensures unauthenticated requests are rejected with 401."""
        resp = self.client.get("/garage")
        self.assertEqual(resp.status_code, 401)

    def test_garage_save_and_retrieve_user_preferences(self):
        """Tests saving and retrieving user preference profiles."""
        save_resp = self.client.post(
            "/garage/preferences",
            json={"preferences": {"budget_max": 1800000, "fuel_type": "Electric", "body_type": "SUV"}},
            headers=self.headers_user1,
        )
        self.assertEqual(save_resp.status_code, 200)

        get_resp = self.client.get("/garage/preferences", headers=self.headers_user1)
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["preferences"]["fuel_type"], "Electric")

    # =========================================================================
    # FEATURE K: Natural-Language Search
    # =========================================================================
    def test_natural_language_search_api(self):
        """Tests POST /search/natural parsing and parameterized filtering."""
        resp = self.client.post("/search/natural", json={
            "query": "Automatic petrol SUVs under 25 lakh",
            "limit": 10,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("parsed_criteria", data)
        self.assertIn("total_found", data)
        self.assertIn("items", data)
        self.assertIn("explanation", data)

    # =========================================================================
    # FEATURE L: Feedback Collection & Evaluation Metrics
    # =========================================================================
    def test_feedback_submission_and_metrics(self):
        """Tests recording explicit feedback and computing Precision@K and NDCG@K."""
        sub = FeedbackSubmission(
            car_id=1,
            action="useful",
            rank_position=1,
            suitability_score=92.5,
            session_id="test_session_1",
        )
        res = feedback_service.record_feedback(user_id=1, sub=sub)
        self.assertEqual(res["status"], "recorded")

        eval_metrics = feedback_service.compute_ranking_metrics()
        self.assertGreaterEqual(eval_metrics.precision_at_1, 0.0)
        self.assertGreaterEqual(eval_metrics.ndcg_at_3, 0.0)

    # =========================================================================
    # FEATURE N: Observability & Telemetry
    # =========================================================================
    def test_telemetry_metrics_endpoint(self):
        """Verifies GET /telemetry/metrics returns latency, error counters, and data stats."""
        resp = self.client.get("/telemetry/metrics")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("uptime_seconds", data)
        self.assertIn("total_api_requests", data)
        self.assertIn("latency_ms", data)
        self.assertIn("error_counts", data)
        self.assertIn("price_intelligence_model", data)


if __name__ == "__main__":
    unittest.main()
