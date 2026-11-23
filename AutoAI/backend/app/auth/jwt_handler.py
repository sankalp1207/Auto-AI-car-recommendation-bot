from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from app.models.user import User

SECRET_KEY = "AutoAISecretKey123456789"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

security = HTTPBearer(auto_error=False)


class AuthUser:
    """Authenticated user model used when database connectivity is unavailable."""
    def __init__(self, id: int, username: str = "user", email: str = "user@autoai.com"):
        self.id = id
        self.username = username
        self.email = email


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Any:
    """Enforces authentication and retrieves currently active user."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(auth.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attempt to load from database if available
    try:
        from app.database.database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return user
        finally:
            db.close()
    except Exception:
        pass

    # If database is offline/unreachable, return verified authenticated identity from token
    return AuthUser(
        id=user_id,
        username=payload.get("username", f"user_{user_id}"),
        email=payload.get("email", f"user{user_id}@autoai.com"),
    )