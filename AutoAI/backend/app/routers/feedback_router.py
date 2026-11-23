"""
AutoAI Feedback Router
Endpoints to submit user recommendation feedback and retrieve ranking evaluation metrics.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header
from app.services.feedback_service import (
    feedback_service,
    FeedbackSubmission,
    FeedbackStatsResponse,
    RankingEvaluationMetrics,
)
from app.auth.jwt_handler import decode_access_token

router = APIRouter(
    prefix="/feedback",
    tags=["Feedback & Evaluation"],
)


@router.post("")
@router.post("/")
def submit_feedback(
    sub: FeedbackSubmission,
    authorization: Optional[str] = Header(None),
):
    """
    Submits explicit user feedback on a recommendation candidate
    (useful, not_interested, show_cheaper, saved, compared).
    """
    user_id = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            try:
                user_id = int(payload["sub"])
            except Exception:
                pass

    return feedback_service.record_feedback(user_id, sub)


@router.get("/stats", response_model=FeedbackStatsResponse)
def get_feedback_stats():
    """Returns aggregated feedback counts by interaction type."""
    return feedback_service.get_stats()


@router.get("/evaluation", response_model=RankingEvaluationMetrics)
def get_ranking_evaluation():
    """
    Computes and returns ranking evaluation metrics (Precision@1, Precision@3,
    Precision@5, NDCG@3, NDCG@5, Constraint Violation Rate, and Catalog Coverage).
    """
    return feedback_service.compute_ranking_metrics()
