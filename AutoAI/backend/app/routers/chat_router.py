import re
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database.database import get_db
from app.schemas.chat import ChatRequest
from app.services.ai_service import (
    extract_preferences,
    explain_recommendations,
)
from app.services.recommendation_service import recommend_cars
from app.services.conversation_memory import memory
from app.services.llm_services import extract_preferences_llm, generate_ai_chat_response

logger = logging.getLogger("autoai.chat")

router = APIRouter(
    prefix="/chat",
    tags=["AI Chat"]
)

FOLLOW_UP_PATTERN = re.compile(
    r'\b(compare|comparison|which one|which is|better|best between|what about|versus|vs|first one|second one|difference|mileage|maintenance|safety|price|family)\b',
    re.IGNORECASE
)


@router.post("")
@router.post("/")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    session_id = request.session_id or "default_session"
    msg_text = request.message.strip()

    # Check for active existing recommendations in this session
    last_recs = memory.get_last_recommendations(session_id)
    accumulated_prefs = memory.get(session_id)

    # 1. Detect if this is a follow-up or comparison query about previous recommendations
    has_follow_up_keyword = bool(FOLLOW_UP_PATTERN.search(msg_text))
    # Check if user message explicitly introduces fresh primary constraints (e.g. new budget, new brand)
    has_fresh_budget = bool(re.search(r'(\d+)\s*(lakh|crore|l|cr)\b|₹?\s*(\d{5,9})', msg_text.lower()))
    has_fresh_body = bool(re.search(r'\b(suv|sedan|hatchback|mpv)\b', msg_text.lower()))
    has_fresh_brand = bool(re.search(r'\b(hyundai|tata|maruti|mahindra|kia|toyota|honda|bmw|mercedes|audi)\b', msg_text.lower()))

    is_pure_follow_up = last_recs and has_follow_up_keyword and not (has_fresh_budget or has_fresh_body or has_fresh_brand)

    if is_pure_follow_up:
        # Ground question on the previously recommended vehicles
        recommendations = last_recs
        preferences = accumulated_prefs
    else:
        # 2. Extract preferences deterministically first (0ms, 0 tokens, high precision)
        prefs = extract_preferences(msg_text)

        # If deterministic extraction found no specific constraints and message is complex, try LLM fallback
        has_extracted_constraints = any([
            prefs.get("budget"),
            prefs.get("brand"),
            prefs.get("model"),
            prefs.get("fuel_type"),
            prefs.get("transmission"),
            prefs.get("body_type"),
            prefs.get("seating"),
            prefs.get("is_luxury"),
            prefs.get("status") == "UPCOMING"
        ])

        if not has_extracted_constraints and len(msg_text.split()) > 3:
            try:
                llm_prefs = extract_preferences_llm(msg_text)
                if llm_prefs:
                    prefs.update(llm_prefs)
            except Exception as e:
                logger.debug("LLM preference extraction fallback: %s", str(e))

        preferences = memory.update(session_id, prefs)

        # 3. Formulate RecommendationRequest
        class RecommendationRequestObj:
            pass

        rec_req = RecommendationRequestObj()
        rec_req.budget = preferences.get("budget")
        rec_req.brand = preferences.get("brand")
        rec_req.model = preferences.get("model")
        rec_req.status = preferences.get("status", "CURRENT")
        rec_req.fuel_type = preferences.get("fuel_type")
        rec_req.transmission = preferences.get("transmission")
        rec_req.body_type = preferences.get("body_type")
        rec_req.seating = preferences.get("seating") or preferences.get("family_members")
        rec_req.family_members = preferences.get("family_members")
        rec_req.priority = preferences.get("priority")
        rec_req.city_drive = preferences.get("city_drive", False)
        rec_req.highway_drive = preferences.get("highway_drive", False)
        rec_req.family_friendly = preferences.get("family_friendly", False)
        rec_req.is_luxury = preferences.get("is_luxury", False)

        # 4. Get deterministic recommendations strictly from PostgreSQL
        recommendations = recommend_cars(rec_req, db)

        # If zero matches found, relax accumulated constraints that were not explicitly mentioned in current query
        if not recommendations and preferences.get("brand") and not has_fresh_brand:
            rec_req.brand = None
            recommendations = recommend_cars(rec_req, db)
            if recommendations:
                preferences.pop("brand", None)

        if not recommendations and preferences.get("body_type") and not has_fresh_body:
            rec_req.body_type = None
            recommendations = recommend_cars(rec_req, db)
            if recommendations:
                preferences.pop("body_type", None)

        if not recommendations and preferences.get("fuel_type") and not (re.search(r'\b(petrol|diesel|cng|electric|ev|hybrid)\b', msg_text.lower())):
            rec_req.fuel_type = None
            recommendations = recommend_cars(rec_req, db)
            if recommendations:
                preferences.pop("fuel_type", None)

        if not recommendations and preferences.get("budget") and not has_fresh_budget:
            rec_req.budget = None
            recommendations = recommend_cars(rec_req, db)
            if recommendations:
                preferences.pop("budget", None)

        # Update last recommendations in session memory
        memory.set_last_recommendations(session_id, recommendations)

    # 5. Generate fact-grounded response using Gemini with bounded history
    recent_turns = memory.get_recent_turns(session_id, max_turns=4)

    try:
        reply = generate_ai_chat_response(
            msg_text,
            recommendations,
            preferences,
            conversation_history=recent_turns
        )
    except Exception as e:
        logger.warning("Gemini generation failed: %s. Falling back to rule-based explanation.", str(e))
        reply = explain_recommendations(
            msg_text,
            recommendations,
            preferences
        )

    # 6. Save dialogue turns in sliding memory window
    memory.add_turn(session_id, "user", msg_text)
    memory.add_turn(session_id, "model", reply)

    return {
        "recommendations": recommendations,
        "ai_response": reply
    }