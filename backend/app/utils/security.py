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
from datetime import datetime, timedelta
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
    expire  = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "type": "access", "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire  = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
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


# ── FastAPI dependency ────────────────────────────────────────────────────────

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
    return user
