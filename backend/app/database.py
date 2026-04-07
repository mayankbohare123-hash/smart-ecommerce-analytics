"""
database.py
───────────
SQLAlchemy database engine, session factory, and base model class.

Supports both SQLite (local dev) and PostgreSQL (production)
based on the DATABASE_URL setting in config.py.

Usage:
    # In route handlers (via FastAPI dependency injection):
    from app.database import get_db
    def my_route(db: Session = Depends(get_db)): ...

    # For table creation at startup:
    from app.database import create_tables
    create_tables()
"""

from sqlalchemy import create_engine, event, Column, Integer, String, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from datetime import datetime
from typing import Generator

from app.config import settings


# ── Engine configuration ─────────────────────────────────────────────────────

def _build_engine():
    """
    Create the SQLAlchemy engine with settings appropriate
    for the current DATABASE_URL (SQLite vs PostgreSQL).
    """
    url = settings.DATABASE_URL

    if url.startswith("sqlite"):
        # SQLite-specific: disable same-thread check (needed for FastAPI),
        # use StaticPool so tests don't open multiple connections to :memory:
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.DEBUG,  # log SQL in dev mode
        )

        # Enable WAL mode for better concurrent read performance on SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    else:
        # PostgreSQL / other — standard connection pool
        engine = create_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,   # test connections before using them
            echo=settings.DEBUG,
        )

    return engine


engine = _build_engine()

# ── Session factory ──────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ── Declarative base ─────────────────────────────────────────────────────────
# All ORM models inherit from this Base
Base = declarative_base()


# ── ORM Models ───────────────────────────────────────────────────────────────

class UploadedFile(Base):
    """
    Tracks every CSV file uploaded by users.
    Stores file metadata and processing status.
    """
    __tablename__ = "uploaded_files"

    id           = Column(Integer, primary_key=True, index=True)
    filename     = Column(String(255), nullable=False)
    original_name= Column(String(255), nullable=False)
    file_path    = Column(String(500), nullable=False)
    file_size    = Column(Integer)                   # bytes
    row_count    = Column(Integer)
    column_count = Column(Integer)
    status       = Column(String(50), default="pending")  # pending|processed|error
    error_message= Column(Text, nullable=True)
    uploaded_at  = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)


class PredictionResult(Base):
    """
    Caches ML prediction results so we don't re-train on every request.
    Keyed by the source file's unique identifier.
    """
    __tablename__ = "prediction_results"

    id            = Column(Integer, primary_key=True, index=True)
    file_id       = Column(Integer, nullable=False)         # FK to UploadedFile
    model_type    = Column(String(100))                      # e.g. "random_forest"
    mae           = Column(Float)                            # mean absolute error
    r2_score      = Column(Float)
    prediction_json = Column(Text)                           # JSON array of predictions
    created_at    = Column(DateTime, default=datetime.utcnow)


# ── Utility functions ────────────────────────────────────────────────────────

def create_tables() -> None:
    """Create all database tables. Called once at app startup."""
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """Drop all tables. Used in testing only."""
    Base.metadata.drop_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.
    Always closes the session after the request finishes (even on error).

    Usage in route:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
