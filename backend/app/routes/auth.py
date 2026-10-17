"""
routes/auth.py
──────────────
Authentication endpoints.

POST /api/auth/signup   — Register a new account
POST /api/auth/login    — Log in, receive JWT tokens
GET  /api/auth/me       — Get current user info (protected)
POST /api/auth/refresh  — Refresh access token
POST /api/auth/logout   — Logout (client clears tokens)
"""

import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db, User
from app.utils.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Request schemas ───────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    name:     str = Field(..., min_length=2, max_length=100)
    email:    str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8)

class LoginRequest(BaseModel):
    email:    str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str


# ── Helpers ───────────────────────────────────────────────────────────────────
def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))

def _build_auth_response(user: User) -> dict:
    return {
        "success":       True,
        "access_token":  create_access_token(user.id, user.email),
        "refresh_token": create_refresh_token(user.id),
        "token_type":    "bearer",
        "user": {
            "id":        user.id,
            "email":     user.email,
            "name":      user.name,
            "plan":      user.plan,
        },
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/signup", summary="Create a new account")
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    """
    Register a new SalesIQ account.
    Returns access token, refresh token, and user profile.
    New accounts start on the Free plan (1 upload limit).
    """
    email = body.email.strip().lower()

    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Please provide a valid email address.")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists. Please log in.")

    user = User(
        name=body.name.strip(),
        email=email,
        hashed_password=hash_password(body.password),
        plan="free",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _build_auth_response(user)


@router.post("/login", summary="Log in and receive tokens")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email and password.
    Returns access token (1 hour) and refresh token (7 days).
    """
    email = body.email.strip().lower()
    user  = db.query(User).filter(User.email == email).first()

    # Generic error prevents email enumeration attacks
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your account has been deactivated.")

    user.last_login_at = datetime.utcnow()
    db.commit()

    return _build_auth_response(user)


@router.get("/me", summary="Get current user profile")
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile and plan info."""
    return {
        "success": True,
        "user": {
            "id":            current_user.id,
            "email":         current_user.email,
            "name":          current_user.name,
            "plan":          current_user.plan,
            "upload_count":  current_user.upload_count,
            "upload_limit":  {"free": 1, "starter": 5, "pro": 999}.get(current_user.plan, 1),
            "created_at":    current_user.created_at.isoformat(),
        },
    }


@router.post("/refresh", summary="Get new access token using refresh token")
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token.")
    user = db.query(User).filter(User.id == int(payload["sub"]), User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return {"success": True, "access_token": create_access_token(user.id, user.email), "token_type": "bearer"}


@router.post("/logout", summary="Logout")
def logout(current_user: User = Depends(get_current_user)):
    """Logout — real logout happens on client by deleting stored tokens."""
    return {"success": True, "message": f"Goodbye, {current_user.name}!"}
