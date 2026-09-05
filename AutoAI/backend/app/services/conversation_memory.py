from typing import Dict, Any, List, Optional


class ConversationMemory:
    """
    Session memory manager with bounded history and token-efficient caching.
    Stores:
    - User preferences across conversational turns
    - Last recommended vehicles (for comparison / follow-up queries)
    - Bounded chat turn history (sliding window capped at max 6 turns)
    """
    def __init__(self, max_history_turns: int = 6):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.max_history_turns = max_history_turns

    def _ensure_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "preferences": {},
                "last_recommendations": [],
                "turns": []
            }
        return self.sessions[session_id]

    def get(self, session_id: str) -> Dict[str, Any]:
        """Backwards-compatible: returns current accumulated preferences dictionary."""
        sess = self._ensure_session(session_id)
        return sess["preferences"]

    def update(self, session_id: str, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Backwards-compatible: updates preferences and returns updated dict."""
        sess = self._ensure_session(session_id)
        prefs = sess["preferences"]

        for key, value in new_data.items():
            if value not in [None, "", False]:
                prefs[key] = value

        return prefs

    def set_last_recommendations(self, session_id: str, recommendations: List[Dict[str, Any]]) -> None:
        """Stores the top candidate vehicles from the most recent recommendation turn."""
        sess = self._ensure_session(session_id)
        # Store only top 5 cars with essential keys to keep memory minimal
        compact_recs = []
        for r in recommendations[:5]:
            compact_recs.append({
                "id": r.get("id"),
                "brand": r.get("brand"),
                "model": r.get("model"),
                "variant": r.get("variant"),
                "price": r.get("price") or r.get("ex_showroom_price", 0),
                "fuel_type": r.get("fuel_type"),
                "transmission": r.get("transmission"),
                "mileage": r.get("mileage", 0),
                "power": r.get("power", 0),
                "safety_rating": r.get("safety_rating", 0),
                "seating": r.get("seating", 5),
                "maintenance_cost": r.get("maintenance_cost", 0),
                "score": r.get("score", 0),
                "reasons": r.get("reasons", [])[:2],
            })
        sess["last_recommendations"] = compact_recs

    def get_last_recommendations(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves candidates from the most recent recommendation turn."""
        sess = self._ensure_session(session_id)
        return sess.get("last_recommendations", [])

    def add_turn(self, session_id: str, role: str, text: str) -> None:
        """Appends a dialogue turn, bounding history to prevent token explosion."""
        sess = self._ensure_session(session_id)
        turns = sess["turns"]
        turns.append({"role": role, "text": text.strip()})
        if len(turns) > self.max_history_turns:
            sess["turns"] = turns[-self.max_history_turns:]

    def get_recent_turns(self, session_id: str, max_turns: int = 4) -> List[Dict[str, str]]:
        """Returns the most recent N turns for contextual conversational grounding."""
        sess = self._ensure_session(session_id)
        return sess["turns"][-max_turns:]

    def clear(self, session_id: str) -> None:
        """Clears memory for a specific session."""
        if session_id in self.sessions:
            del self.sessions[session_id]


memory = ConversationMemory()