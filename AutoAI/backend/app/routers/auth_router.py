from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import jwt, JWTError

from app.database.database import get_db

from app.schemas.auth import (
    UserRegister,
    UserLogin,
)

from app.services.auth_service import (
    register_user,
    login_user,
)

from app.auth.jwt_handler import (
    SECRET_KEY,
    ALGORITHM,
    create_access_token,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/register")
def register(
    request: UserRegister,
    db: Session = Depends(get_db),
):
    return register_user(request, db)


@router.post("/login")
def login(
    request: UserLogin,
    db: Session = Depends(get_db),
):
    return login_user(request, db)


class TokenRefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
def refresh(request: TokenRefreshRequest):
    try:
        payload = jwt.decode(request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        student_id: str = payload.get("sub")
        if student_id is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Issue new access token valid for 60 minutes
        new_access_token = create_access_token({"sub": student_id})
        return {"access_token": new_access_token}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")