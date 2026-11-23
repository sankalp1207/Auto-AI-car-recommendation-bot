"""
Finder API router — AI-Powered Personalized Car Finder endpoint.

POST /finder
  - Accepts natural-language message + optional session_id
  - Returns structured recommendations with suitability scores and explanations
  - Maintains conversation state across turns via session_id

GET /finder/session/{session_id}
  - Returns current accumulated preferences for a session

DELETE /finder/session/{session_id}
  - Clears accumulated preferences for a session
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Any, Dict

from app.database.database import get_db
from app.schemas.finder import FinderRequest, FinderResponse
from app.services.finder_service import run_finder
from app.services.conversation_memory import memory

logger = logging.getLogger("autoai.finder_router")

router = APIRouter(
    prefix="/finder",
    tags=["AI Car Finder"],
)


@router.post("", response_model=FinderResponse)
@router.post("/", response_model=FinderResponse)
def find_cars(
    request: FinderRequest,
    db: Session = Depends(get_db),
) -> FinderResponse:
    """
    AI-Powered Personalized Car Finder.

    Accepts a natural-language car-buying query and returns ranked recommendations
    with suitability scores, matched requirements, strengths, and trade-offs.

    **Session continuity**: Pass the same `session_id` across multiple messages
    to refine your search conversationally. The system accumulates your preferences
    across turns and only updates preferences you explicitly change.

    **Example messages**:
    - "Safe family SUV under 15 lakhs with automatic transmission"
    - "Show me electric cars"
    - "Increase budget to 20 lakhs"
    - "Compare the top three choices"
    - "I prefer Tata or Hyundai"
    """
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    session_id = (request.session_id or "").strip() or _generate_session_id()

    try:
        response = run_finder(
            message=request.message.strip(),
            session_id=session_id,
            db=db,
            reset_session=request.reset_session,
        )
        return response
    except Exception as e:
        logger.error("Finder pipeline error for session %s: %s", session_id, str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request. Please try again.",
        )


@router.get("/session/{session_id}", response_model=Dict[str, Any])
def get_session_preferences(
    session_id: str = Path(..., description="Session identifier"),
) -> Dict[str, Any]:
    """
    Returns the current accumulated preferences for a session.
    Useful for displaying active filter chips in the frontend.
    """
    prefs = memory.get(session_id)
    return {
        "session_id": session_id,
        "preferences": prefs,
        "last_recommendations": memory.get_last_recommendations(session_id),
    }


@router.delete("/session/{session_id}")
def clear_session(
    session_id: str = Path(..., description="Session identifier"),
) -> Dict[str, str]:
    """Clears accumulated preferences for a session to start fresh."""
    memory.clear(session_id)
    return {"status": "cleared", "session_id": session_id}


def _generate_session_id() -> str:
    """Generate a random session ID when none is provided."""
    import uuid
    return f"finder_{uuid.uuid4().hex[:12]}"
