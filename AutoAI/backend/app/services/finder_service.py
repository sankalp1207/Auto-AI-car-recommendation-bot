"""
Finder service — the core pipeline for the AI-Powered Personalized Car Finder.

Pipeline:
  1. Extract & validate preferences (from message + session context)
  2. Run recommendation engine (hard constraints + ranking)
  3. Build CarRecommendation objects with grounded explanations
  4. Generate conversational AI response (Gemini or deterministic fallback)
  5. Return structured FinderResponse
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.schemas.finder import (
    CarPreferences,
    CarRecommendation,
    FinderResponse,
)
from app.services.preference_extractor import (
    extract_and_update_preferences,
    merge_preferences,
)
from app.services.recommendation_service import recommend_cars
from app.services.conversation_memory import memory

logger = logging.getLogger("autoai.finder")

# Fields that are missing when they are 0 or None
_OPTIONAL_SPEC_FIELDS = {
    "safety_rating": "Safety rating",
    "mileage": "Fuel efficiency (km/l)",
    "power": "Engine power",
    "boot_space": "Boot space",
    "ground_clearance": "Ground clearance",
}


def _build_car_recommendation(raw: Dict[str, Any]) -> CarRecommendation:
    """Convert a raw dict from recommend_cars() into a validated CarRecommendation."""
    missing_data: List[str] = []
    for field, label in _OPTIONAL_SPEC_FIELDS.items():
        if not raw.get(field):
            missing_data.append(label)

    # Strengths from reasons produced by the score_service
    strengths = list(raw.get("reasons", []))
    if not strengths:
        strengths = ["Matches your core requirements"]

    # Trade-offs from cons or missing data
    trade_offs: List[str] = []
    cons_text = raw.get("cons", "")
    if cons_text:
        # Take first two sentences from cons string
        parts = [p.strip() for p in cons_text.replace(";", ".").split(".") if p.strip()]
        trade_offs = parts[:2]

    price = float(raw.get("price") or raw.get("ex_showroom_price") or 0.0)

    return CarRecommendation(
        id=raw.get("id", 0),
        brand=raw.get("brand", "Unknown"),
        model=raw.get("model", "Unknown"),
        variant=raw.get("variant", ""),
        price=price,
        price_basis="Ex-Showroom",
        status=raw.get("status", "CURRENT"),
        fuel_type=raw.get("fuel_type") or raw.get("fuel"),
        transmission=raw.get("transmission"),
        seating_capacity=raw.get("seating") or raw.get("seating_capacity"),
        mileage=raw.get("mileage") or None,
        power=raw.get("power") or None,
        safety_rating=raw.get("safety_rating") or None,
        engine_cc=raw.get("engine_cc") or None,
        boot_space=raw.get("boot_space") or None,
        ground_clearance=raw.get("ground_clearance") or None,
        sunroof=bool(raw.get("sunroof")) if raw.get("sunroof") is not None else None,
        adas=bool(raw.get("adas")) if raw.get("adas") is not None else None,
        touchscreen_inches=raw.get("touchscreen_inches") or None,
        carplay_androidauto=bool(raw.get("carplay_androidauto")) if raw.get("carplay_androidauto") is not None else None,
        image=raw.get("image") or raw.get("image_url"),
        ideal_for=raw.get("ideal_for"),
        pros=raw.get("pros"),
        cons=raw.get("cons"),
        suitability_score=float(raw.get("score", 70.0)),
        matched_requirements=[r for r in strengths if r],
        strengths=strengths,
        trade_offs=trade_offs,
        missing_data=missing_data,
        score_breakdown=raw.get("score_breakdown"),
    )


def _build_no_results_response(
    prefs: CarPreferences,
    session_id: str,
) -> FinderResponse:
    """Build a helpful no-results response with alternative suggestions."""
    alternatives: List[str] = []
    reason_parts: List[str] = []

    if prefs.budget_max and prefs.budget_max < 500_000:
        reason_parts.append(f"budget of ₹{prefs.budget_max:,.0f} is below the entry-level car price")
        alternatives.append("Try increasing your budget to at least ₹5 lakh (₹500,000)")
    if prefs.fuel_type:
        alternatives.append(f"Remove the {prefs.fuel_type} fuel filter to see more options")
    if prefs.transmission:
        alternatives.append(f"Try any transmission instead of {prefs.transmission} only")
    if prefs.body_type:
        alternatives.append(f"Consider other body types besides {prefs.body_type}")
    if prefs.minimum_seating and prefs.minimum_seating > 7:
        alternatives.append("Reduce the minimum seat requirement — 7-seaters cover most family needs")
    if prefs.preferred_brands:
        alternatives.append("Expand to include other brands alongside your preferred ones")

    if not alternatives:
        alternatives = [
            "Try relaxing one filter at a time",
            "Increase your budget range",
            "Ask for upcoming models to see future launches",
        ]

    no_results_msg = "No vehicles found matching all your requirements. " + (
        f"Possible reason: {reason_parts[0]}." if reason_parts else ""
    )

    return FinderResponse(
        session_id=session_id,
        preferences=prefs.model_dump(exclude_none=False),
        needs_clarification=False,
        recommendations=[],
        total_matched=0,
        ai_response=no_results_msg,
        no_results_reason=no_results_msg,
        alternative_suggestions=alternatives,
    )


def _generate_conversational_response(
    message: str,
    recommendations: List[Dict[str, Any]],
    preferences: CarPreferences,
    session_id: str,
) -> str:
    """Generate a Gemini-powered or deterministic conversational response."""
    try:
        from app.services.llm_services import generate_ai_chat_response
        recent_turns = memory.get_recent_turns(session_id, max_turns=4)
        return generate_ai_chat_response(
            message,
            recommendations,
            preferences.model_dump(exclude_none=True),
            conversation_history=recent_turns,
        )
    except Exception as e:
        logger.warning("Gemini response generation failed: %s. Using deterministic fallback.", str(e))

    # Deterministic fallback
    from app.services.ai_service import explain_recommendations
    return explain_recommendations(
        message,
        recommendations,
        preferences.model_dump(exclude_none=True),
    )


def run_finder(
    message: str,
    session_id: str,
    db: Optional[Session] = None,
    existing_preferences: Optional[Dict[str, Any]] = None,
    reset_session: bool = False,
) -> FinderResponse:
    """
    Main finder pipeline entry point.

    Args:
        message: User's natural-language query
        session_id: Session key for preference accumulation
        db: Optional DB session (used by recommendation service)
        existing_preferences: Pre-loaded session preferences dict
        reset_session: If True, clears accumulated preferences first

    Returns:
        FinderResponse with recommendations and AI explanation
    """
    if reset_session:
        memory.clear(session_id)

    # Load accumulated session preferences
    session_prefs_dict = existing_preferences or memory.get(session_id)

    # ── Stage 1: Extract preferences ──────────────────────────────────────
    prefs = extract_and_update_preferences(
        message,
        existing_preferences=session_prefs_dict,
        use_llm=True,
    )

    # Persist updated preferences
    memory.update(session_id, prefs.model_dump(exclude_none=True))

    # ── Stage 2: Build recommendation request ─────────────────────────────
    rec_dict = prefs.to_recommendation_dict()

    class _RecReq:
        """Thin adapter so recommend_cars() works with attribute access."""
        def __init__(self, d: Dict[str, Any]):
            for k, v in d.items():
                setattr(self, k, v)

    rec_req = _RecReq(rec_dict)

    # ── Stage 3: Get raw recommendations ──────────────────────────────────
    raw_recs = recommend_cars(rec_req, db)

    # ── Stage 4: Constraint relaxation on zero results ────────────────────
    relaxations_tried: List[str] = []
    if not raw_recs:
        # Try relaxing soft constraints in priority order
        if prefs.preferred_brands and len(prefs.preferred_brands) > 0:
            rec_req_copy = dict(rec_dict)
            rec_req_copy["brand"] = None
            raw_recs = recommend_cars(_RecReq(rec_req_copy), db)
            if raw_recs:
                relaxations_tried.append("brand filter relaxed")

        if not raw_recs and prefs.body_type:
            rec_req_copy = dict(rec_dict)
            rec_req_copy["brand"] = None
            rec_req_copy["body_type"] = None
            raw_recs = recommend_cars(_RecReq(rec_req_copy), db)
            if raw_recs:
                relaxations_tried.append("body type filter relaxed")

        if not raw_recs and prefs.fuel_type:
            rec_req_copy = dict(rec_dict)
            rec_req_copy["brand"] = None
            rec_req_copy["body_type"] = None
            rec_req_copy["fuel_type"] = None
            rec_req_copy["fuel"] = None
            raw_recs = recommend_cars(_RecReq(rec_req_copy), db)
            if raw_recs:
                relaxations_tried.append("fuel type filter relaxed")

    # ── Stage 5: Handle zero results ──────────────────────────────────────
    if not raw_recs:
        memory.add_turn(session_id, "user", message)
        memory.add_turn(session_id, "model", "No vehicles matched your requirements.")
        return _build_no_results_response(prefs, session_id)

    # Store recommendations in session memory for follow-up queries
    memory.set_last_recommendations(session_id, raw_recs)

    # ── Stage 6: Build structured recommendation list ─────────────────────
    car_recs: List[CarRecommendation] = []
    for raw in raw_recs[:5]:
        try:
            car_recs.append(_build_car_recommendation(raw))
        except Exception as e:
            logger.warning("Failed to build CarRecommendation for id=%s: %s", raw.get("id"), str(e))

    # ── Stage 7: Generate AI response ─────────────────────────────────────
    relaxation_note = ""
    if relaxations_tried:
        relaxation_note = (
            f" (Note: I broadened your search slightly — {', '.join(relaxations_tried)} — "
            f"to find matches.)"
        )

    ai_response = _generate_conversational_response(message, raw_recs, prefs, session_id)
    if relaxation_note:
        ai_response = ai_response + "\n\n" + relaxation_note.strip()

    # Save turns
    memory.add_turn(session_id, "user", message)
    memory.add_turn(session_id, "model", ai_response)

    return FinderResponse(
        session_id=session_id,
        preferences=prefs.model_dump(exclude_none=True),
        needs_clarification=False,
        recommendations=car_recs,
        total_matched=len(raw_recs),
        ai_response=ai_response,
        alternative_suggestions=[],
    )
