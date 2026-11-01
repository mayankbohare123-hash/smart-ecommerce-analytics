"""
routes/auth.py
──────────────
Authentication endpoints.

POST /api/auth/signup   — Register a new account
POST /api/auth/login    — Log in, receive JWT tokens
GET  /api/auth/me       — Get current user info (protected)
POST /api/auth/refresh  — Refresh access token
POST /api/auth/logout   — Logout (client clears tokens)
POST /api/auth/forgot-password — Email a one-time reset link
POST /api/auth/reset-password  — Set a new password using that link
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, User, PasswordResetToken
from app.services.email_service import send_password_reset_email
from app.utils.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user, token_revoked_by_password_change,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Request schemas ───────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    name:     str = Field(..., min_length=2, max_length=100)
    email:    str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8)
    organization: Optional[str] = Field(default=None, max_length=255)

class LoginRequest(BaseModel):
    email:    str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=8)

FORGOT_PASSWORD_MESSAGE = "If an account exists for that email, we've sent a link to reset the password."
RESET_LINK_INVALID = "This reset link is invalid or has expired. Please request a new one."


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
            "role":      user.role or "user",
            "organization": user.organization,
        },
    }


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Login must take the same time whether or not the email exists, otherwise response
# time reveals which emails are registered. We verify against this dummy hash instead.
_DUMMY_HASH = None

def _burn_password_check(password: str) -> None:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("not-a-real-password")
    verify_password(password, _DUMMY_HASH)


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
        organization=(body.organization or "").strip() or None,
        role="user",
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
    if not user:
        _burn_password_check(body.password)
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your account has been deactivated.")

    user.last_login_at = datetime.utcnow()
    db.commit()

    return _build_auth_response(user)


@router.get("/me", summary="Get current user profile")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns the authenticated user's profile, plan and live usage."""
    from app.services.billing_service import BillingService
    billing = BillingService(db).status(current_user)
    return {
        "success": True,
        "user": {
            "id":            current_user.id,
            "email":         current_user.email,
            "name":          current_user.name,
            "role":          current_user.role or "user",
            "organization":  current_user.organization,
            "plan":          billing["plan"],
            "upload_count":  billing["uploads_used"],     # kept for backwards compatibility
            "uploads_used":  billing["uploads_used"],
            "upload_limit":  billing["upload_limit"],     # null = unlimited
            "subscription_status":  billing["subscription_status"],
            "cancel_at_period_end": billing["cancel_at_period_end"],
            "current_period_end":   billing["current_period_end"],
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
    if token_revoked_by_password_change(user, payload):
        raise HTTPException(status_code=401, detail="Your password was changed. Please log in again.")
    return {"success": True, "access_token": create_access_token(user.id, user.email), "token_type": "bearer"}


@router.post("/logout", summary="Logout")
def logout(current_user: User = Depends(get_current_user)):
    """Logout — real logout happens on client by deleting stored tokens."""
    return {"success": True, "message": f"Goodbye, {current_user.name}!"}


@router.post("/forgot-password", summary="Email a password-reset link")
def forgot_password(body: ForgotPasswordRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Always answers the same way, whether or not the email is registered, so this
    endpoint can't be used to discover who has an account. The email itself is sent
    in the background so the response time doesn't leak it either.
    """
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email, User.is_active == True).first()  # noqa: E712
    if user:
        recent = (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == user.id,
                    PasswordResetToken.created_at >= datetime.utcnow() - timedelta(hours=1))
            .count()
        )
        if recent < settings.PASSWORD_RESET_MAX_PER_HOUR:        # stops someone email-bombing a user
            raw = secrets.token_urlsafe(32)
            db.add(PasswordResetToken(
                user_id=user.id,
                token_hash=_hash_token(raw),
                expires_at=datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
            ))
            db.commit()
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw}"
            background.add_task(send_password_reset_email, user.email, user.name,
                                reset_url, settings.PASSWORD_RESET_EXPIRE_MINUTES)
    return {"success": True, "message": FORGOT_PASSWORD_MESSAGE}


@router.post("/reset-password", summary="Set a new password using an emailed token")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    The token is single-use and time-limited, and only its hash is stored.
    Resetting also signs the account out everywhere: every token issued before this
    moment stops working (so a thief who already had a session is locked out).
    """
    now = datetime.utcnow()
    row = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == _hash_token(body.token)).first()
    if not row or row.used_at is not None or row.expires_at < now:
        raise HTTPException(status_code=400, detail=RESET_LINK_INVALID)
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail=RESET_LINK_INVALID)

    user.hashed_password = hash_password(body.password)
    user.password_changed_at = now
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
    ).update({"used_at": now})                                  # every outstanding link dies, not just this one
    db.commit()
    return {"success": True, "message": "Password updated. You can now log in."}
