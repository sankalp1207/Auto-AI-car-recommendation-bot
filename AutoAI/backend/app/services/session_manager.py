import requests
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

class SessionManager:
    def __init__(self):
        # Maps student_id -> (requests.Session, expiration_time)
        self._sessions: Dict[str, Tuple[requests.Session, datetime]] = {}

    def get_session(self, student_id: str) -> Optional[requests.Session]:
        """Retrieve active requests Session from in-memory cache if not expired."""
        if student_id in self._sessions:
            session, exp = self._sessions[student_id]
            if datetime.utcnow() < exp:
                return session
            else:
                # Session expired in cache
                del self._sessions[student_id]
        return None

    def set_session(self, student_id: str, session: requests.Session, duration_minutes: int = 60):
        """Cache an active requests Session."""
        exp = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self._sessions[student_id] = (session, exp)

    def remove_session(self, student_id: str):
        """Remove a session from in-memory cache."""
        if student_id in self._sessions:
            del self._sessions[student_id]

# Singleton instance
session_manager = SessionManager()
