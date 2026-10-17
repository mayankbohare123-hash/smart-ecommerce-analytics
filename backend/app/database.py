"""
database.py — UPDATED with User model for auth.
"""

from sqlalchemy import (
    create_engine, event, Column, Integer, String,
    DateTime, Float, Text, Boolean, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from datetime import datetime
from typing import Generator

from app.config import settings


def _build_engine():
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        engine = create_engine(
            url, connect_args={"check_same_thread": False},
            poolclass=StaticPool, echo=settings.DEBUG,
        )
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    else:
        engine = create_engine(url, pool_size=10, max_overflow=20, pool_pre_ping=True, echo=settings.DEBUG)
    return engine


engine       = _build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base         = declarative_base()


# ── NEW: User model ───────────────────────────────────────────────────────────
class User(Base):
    """Registered user account — every uploaded file is linked to a User."""
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name            = Column(String(255), nullable=True)

    # Subscription plan: 'free' | 'starter' | 'pro'
    plan            = Column(String(50), default="free", nullable=False)
    upload_count    = Column(Integer, default=0)
    is_active       = Column(Boolean, default=True)

    # Stripe (for Phase 2)
    stripe_customer_id = Column(String(255), nullable=True)

    created_at    = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


# ── Existing models — updated with optional user_id FK ───────────────────────
class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    filename      = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_path     = Column(String(500), nullable=False)
    file_size     = Column(Integer)
    row_count     = Column(Integer)
    column_count  = Column(Integer)
    status        = Column(String(50), default="pending")
    error_message = Column(Text, nullable=True)
    uploaded_at   = Column(DateTime, default=datetime.utcnow)
    processed_at  = Column(DateTime, nullable=True)


class PredictionResult(Base):
    __tablename__ = "prediction_results"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    file_id         = Column(Integer, nullable=False)
    model_type      = Column(String(100))
    mae             = Column(Float)
    r2_score        = Column(Float)
    prediction_json = Column(Text)
    created_at      = Column(DateTime, default=datetime.utcnow)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)

def drop_tables() -> None:
    Base.metadata.drop_all(bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
