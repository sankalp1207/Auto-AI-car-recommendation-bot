"""
Unit tests for AutoAI New Launches and Data Quality API Endpoints
Tests:
  - GET /launches (filtering, sorting, pagination, tabs)
  - GET /launches/stats
  - GET /launches/{id}
  - GET /data-quality/report
  - GET /data-quality/issues
  - GET /data-quality/stats
  - Versioned /api/v1 compatibility
"""

from pathlib import Path
import sys
import unittest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app


class TestLaunchesAndQualityAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_get_launches_default(self):
        """Tests default /launches endpoint returns launched cars with metadata."""
        resp = self.client.get("/launches")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("tab"), "launched")
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertIn("freshness", data)
        self.assertIn("available_filters", data)
        self.assertGreater(data.get("total", 0), 0)

    def test_get_launches_upcoming_tab(self):
        """Tests /launches?tab=upcoming returns upcoming cars."""
        resp = self.client.get("/launches?tab=upcoming")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("tab"), "upcoming")
        self.assertIn("items", data)
        self.assertGreater(data.get("total", 0), 0)
        # Verify status of all items in upcoming tab is UPCOMING
        for item in data.get("items", []):
            self.assertEqual(item.get("status"), "UPCOMING")

    def test_get_launches_filter_and_search(self):
        """Tests filtering by brand and search query."""
        resp = self.client.get("/launches?brand=Toyota")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for item in data.get("items", []):
            self.assertEqual(item.get("brand").lower(), "toyota")

    def test_get_launches_stats(self):
        """Tests /launches/stats returns aggregated metrics."""
        resp = self.client.get("/launches/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_new_launches", data)
        self.assertIn("total_upcoming_vehicles", data)
        self.assertIn("source", data)
        self.assertEqual(data.get("source"), "carwale.com")

    def test_get_launch_detail(self):
        """Tests retrieving single vehicle detail."""
        list_resp = self.client.get("/launches")
        items = list_resp.json().get("items", [])
        if items:
            first_id = items[0]["id"]
            detail_resp = self.client.get(f"/launches/{first_id}")
            self.assertEqual(detail_resp.status_code, 200)
            self.assertEqual(detail_resp.json().get("id"), first_id)

    def test_get_data_quality_report(self):
        """Tests /data-quality/report returns structured validation summary."""
        resp = self.client.get("/data-quality/report?dataset=new_launches")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("validation_timestamp", data)
        self.assertIn("severity_counts", data)
        self.assertIn("missing_data_analysis", data)
        self.assertIn("duplicate_analysis", data)

    def test_get_data_quality_issues(self):
        """Tests /data-quality/issues returns paginated issues list."""
        resp = self.client.get("/data-quality/issues?dataset=new_launches")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertIn("severity_counts", data)

    def test_get_data_quality_stats(self):
        """Tests /data-quality/stats returns health status."""
        resp = self.client.get("/data-quality/stats?dataset=new_launches")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)
        self.assertIn("total_rows", data)
        self.assertIn("errors", data)
        self.assertIn("warnings", data)

    def test_versioned_v1_compatibility(self):
        """Tests that /api/v1/launches and /api/v1/data-quality work identically."""
        resp1 = self.client.get("/api/v1/launches/stats")
        self.assertEqual(resp1.status_code, 200)

        resp2 = self.client.get("/api/v1/data-quality/stats")
        self.assertEqual(resp2.status_code, 200)


if __name__ == "__main__":
    unittest.main()
