from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.chat import ChatRequest

from app.services.ai_service import (
    extract_preferences,
    explain_recommendations,
)

from app.services.recommendation_service import recommend_cars


router = APIRouter(
    prefix="/chat",
    tags=["AI Chat"]
)


@router.post("/")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    from app.services.llm_services import extract_preferences_llm, generate_ai_chat_response
    from app.services.conversation_memory import memory

    session_id = request.session_id or "default_session"

    try:
        prefs = extract_preferences_llm(request.message)
    except Exception:
        # Fallback to local regex-based parser if LM-Studio is offline/unavailable
        prefs = extract_preferences(request.message)

    preferences = memory.update(
        session_id,
        prefs
    )

    # Create recommendation object
    class RecommendationRequest:
        pass

    recommendation_request = RecommendationRequest()

    # Only apply constraints if explicitly set in preferences
    recommendation_request.budget = preferences.get("budget", None)
    recommendation_request.fuel_type = preferences.get("fuel_type", None)
    recommendation_request.transmission = preferences.get("transmission", None)
    recommendation_request.body_type = preferences.get("body_type", None)
    recommendation_request.family_members = preferences.get("family_members", None)
    recommendation_request.priority = preferences.get("priority", None)
    recommendation_request.city_drive = preferences.get("city_drive", False)
    recommendation_request.highway_drive = preferences.get("highway_drive", False)

    # Get recommendations
    recommendations = recommend_cars(
        recommendation_request,
        db
    )

    # Generate AI explanation with Structured Thinking Prompt & Fallback
    try:
        reply = generate_ai_chat_response(
            request.message,
            recommendations,
            preferences
        )
    except Exception:
        reply = explain_recommendations(
            request.message,
            recommendations,
            preferences
        )

    return {
        "recommendations": recommendations,
        "ai_response": reply
    }