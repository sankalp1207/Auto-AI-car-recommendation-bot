"""
AutoAI Telemetry & Observability Service
Collects structured operational metrics, API latencies, error counters,
data freshness, and ML model performance without external monitoring dependencies.
"""

import time
import os
import json
import logging
from typing import Dict, Any, List
from collections import deque

logger = logging.getLogger("autoai.monitoring")


class MonitoringService:
    def __init__(self):
        self._start_time = time.time()
        self._latencies: deque = deque(maxlen=500)  # rolling window of last 500 requests
        self._total_requests = 0
        self._error_counts = {
            "database_errors": 0,
            "gemini_fallback_events": 0,
            "scraper_errors": 0,
            "recommendation_errors": 0,
            "http_5xx_errors": 0,
        }
        self._constraint_violations = 0  # Hard constraint violations in recommendations

    def record_request(self, duration_ms: float, is_error: bool = False):
        self._total_requests += 1
        self._latencies.append(duration_ms)
        if is_error:
            self._error_counts["http_5xx_errors"] += 1

    def record_error(self, category: str):
        if category in self._error_counts:
            self._error_counts[category] += 1
        else:
            self._error_counts[category] = 1

    def record_constraint_violation(self):
        self._constraint_violations += 1

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        uptime_sec = round(time.time() - self._start_time, 1)

        lat_list = list(self._latencies)
        if lat_list:
            sorted_lat = sorted(lat_list)
            avg_lat = round(sum(lat_list) / len(lat_list), 2)
            p50_lat = round(sorted_lat[len(sorted_lat) // 2], 2)
            p95_idx = int(len(sorted_lat) * 0.95)
            p95_lat = round(sorted_lat[min(p95_idx, len(sorted_lat) - 1)], 2)
        else:
            avg_lat = p50_lat = p95_lat = 0.0

        # Check data freshness
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        launches_meta = os.path.join(base_dir, "ml", "data", "new_launches", "scraping_metadata.json")
        launches_csv = os.path.join(base_dir, "ml", "data", "new_launches", "cars_new_launches.csv")
        data_quality_report = os.path.join(base_dir, "data", "data_quality_report.json")

        freshness_info = {}
        if os.path.exists(launches_meta):
            try:
                with open(launches_meta, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    freshness_info["launches_last_scraped_at"] = meta.get("last_scraped_at")
                    freshness_info["launches_cutoff_date"] = meta.get("actual_date_cutoff")
            except Exception:
                pass

        # Data quality stats
        dq_stats = {}
        if os.path.exists(data_quality_report):
            try:
                with open(data_quality_report, "r", encoding="utf-8") as f:
                    dqr = json.load(f)
                    dq_stats["total_records_audited"] = dqr.get("total_records")
                    dq_stats["critical_errors_count"] = dqr.get("critical_errors_count")
                    dq_stats["warnings_count"] = dqr.get("warnings_count")
                    dq_stats["overall_health"] = dqr.get("overall_health")
            except Exception:
                pass

        return {
            "uptime_seconds": uptime_sec,
            "total_api_requests": self._total_requests,
            "latency_ms": {
                "average": avg_lat,
                "p50": p50_lat,
                "p95": p95_lat,
                "sample_size": len(lat_list),
            },
            "error_counts": self._error_counts,
            "recommendation_engine": {
                "hard_constraint_violations": self._constraint_violations,
                "violation_rate_pct": 0.0 if self._total_requests == 0 else round((self._constraint_violations / self._total_requests) * 100, 2),
                "active_model_version": "two_tower_v1",
            },
            "price_intelligence_model": {
                "model_name": "ExtraTreesRegressor Pipeline",
                "evaluated_rows": 440,
                "mean_absolute_error_inr": 979877.50,
                "r2_score": 0.5724,
            },
            "data_freshness": freshness_info,
            "data_quality": dq_stats,
        }


monitoring_service = MonitoringService()
