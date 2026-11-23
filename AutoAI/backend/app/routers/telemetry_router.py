"""
AutoAI Telemetry Router
Observability endpoints for latency distribution, error frequency, and data quality metrics.
"""

from fastapi import APIRouter
from app.services.monitoring_service import monitoring_service

router = APIRouter(
    prefix="/telemetry",
    tags=["Observability & Telemetry"],
)


@router.get("/metrics")
def get_system_metrics():
    """
    Returns live operational metrics: request counts, rolling latency percentiles (avg, p50, p95),
    error rates, hard-constraint violation counts, and ML model performance.
    """
    return monitoring_service.get_metrics_snapshot()
