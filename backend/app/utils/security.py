"""
utils/security.py
─────────────────
JWT token creation, validation, and the get_current_user dependency.

FINAL FIX: Bypasses passlib entirely and uses bcrypt directly.
This eliminates all passlib/bcrypt version compatibility issues permanently.

Password flow:
  plain text → SHA-256 → base64 (44 bytes) → bcrypt → stored hash
  44 bytes is always under bcrypt's 72-byte limit, regardless of version.
"""

import bcrypt
import hashlib
import base64
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, User


# ── Password hashing (bcrypt direct — no passlib) ────────────────────────────

def _prehash(plain: str) -> bytes:
    """
    SHA-256 prehash → base64 → always exactly 44 bytes.
    bcrypt's 72-byte limit can never be hit.
    """
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.b64encode(digest)       # returns bytes, e.g. b'x7Gf...' (44 bytes)


def hash_password(plain: str) -> str:
    """Hash a password using SHA-256 prehash + bcrypt (cost factor 12)."""
    hashed = bcrypt.hashpw(_prehash(plain), bcrypt.gensalt(12))
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed_str: str) -> bool:
    """Verify a plain password against a stored bcrypt hash."""
    return bcrypt.checkpw(_prehash(plain), hashed_str.encode("utf-8"))


# ── Token creation ────────────────────────────────────────────────────────────

def create_access_token(user_id: int, email: str) -> str:
    now     = datetime.utcnow()
    expire  = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "type": "access", "exp": expire, "iat": int(time.time())}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    now     = datetime.utcnow()
    expire  = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire, "iat": int(time.time())}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def token_revoked_by_password_change(user: User, payload: dict) -> bool:
    """
    True if the token was issued BEFORE the user's last password change.
    This is what makes "reset my password" actually log out a thief who already
    has a session — JWTs are otherwise valid until they expire.
    """
    changed = getattr(user, "password_changed_at", None)
    if not changed:
        return False
    # password_changed_at is naive UTC → interpret as UTC when comparing to the token's epoch seconds
    changed_ts = int(changed.replace(tzinfo=timezone.utc).timestamp())
    return int(payload.get("iat", 0)) < changed_ts


# ── FastAPI dependencies ──────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )
    user = db.query(User).filter(
        User.id == int(payload["sub"]),
        User.is_active == True,
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    if token_revoked_by_password_change(user, payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your password was changed. Please log in again.",
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency for every /api/admin route. The frontend hides the panel from
    customers, but THIS is what actually protects it."""
    if (current_user.role or "user") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user
