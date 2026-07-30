from sqlalchemy.orm import Session

from app.models.user import User

from app.auth.password import (
    hash_password,
    verify_password,
)

from app.auth.jwt_handler import (
    create_access_token,
)


def register_user(request, db: Session):

    existing_email = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if existing_email:
        return {
            "message": "Email already exists"
        }

    existing_username = (
        db.query(User)
        .filter(User.username == request.username)
        .first()
    )

    if existing_username:
        return {
            "message": "Username already exists"
        }

    user = User(
        username=request.username,
        email=request.email,
        password=hash_password(request.password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "User Registered Successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }
    }


def login_user(request, db: Session):

    user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if not user:
        return {
            "message": "Invalid Email or Password"
        }

    if not verify_password(
        request.password,
        user.password
    ):
        return {
            "message": "Invalid Email or Password"
        }

    token = create_access_token(
        {
            "sub": str(user.id)
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "email": user.email,
    }