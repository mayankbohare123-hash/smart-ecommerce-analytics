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

    # Access level: 'user' (customer) or 'admin' (you, the founder).
  # NULL (rows created before this column existed) is treated as 'user'.
  # Admins are NEVER created through signup — see scripts/manage_users.py.
    role            = Column(String(20), default="user", nullable=True)
    organization    = Column(String(255), nullable=True)   # customer's company / org name (optional)
    # Set when the password is reset/changed; any token issued before it is rejected.
    password_changed_at = Column(DateTime, nullable=True)

    # Subscription plan: 'free' | 'starter' | 'pro'
    plan            = Column(String(50), default="free", nullable=False)
    upload_count    = Column(Integer, default=0)
    is_active       = Column(Boolean, default=True)

    # ── Stripe billing (Step 2) ───────────────────────────────────────────────
    # Stripe is the source of truth; these columns are a local mirror kept in
    # sync by webhooks so the API never has to call Stripe to answer "what plan
    # is this user on?".
    stripe_customer_id      = Column(String(255), nullable=True, index=True)
    stripe_subscription_id  = Column(String(255), nullable=True)
    subscription_status     = Column(String(50), nullable=True)   # active | past_due | canceled ...
    current_period_end      = Column(DateTime, nullable=True)     # renewal / expiry date
    cancel_at_period_end    = Column(Boolean, nullable=True, default=False)
    stripe_synced_at        = Column(Integer, nullable=True)      # ts of newest applied Stripe event (ignores stale ones)

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


class BillingInvoice(Base):
    """One row per Stripe invoice → powers the 'billing history' table."""
    __tablename__ = "billing_invoices"

    id                = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_invoice_id = Column(String(255), unique=True, nullable=False, index=True)
    plan              = Column(String(50), nullable=True)
    amount_cents      = Column(Integer, default=0)
    currency          = Column(String(10), default="usd")
    status            = Column(String(50), nullable=False)        # paid | failed
    hosted_invoice_url= Column(String(1000), nullable=True)
    invoice_pdf       = Column(String(1000), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow)


class StripeEvent(Base):
    """
    Webhook idempotency log. Stripe delivers events at-least-once, so the same
    event id can arrive twice. We record each processed id and skip repeats.
    """
    __tablename__ = "stripe_events"

    id              = Column(Integer, primary_key=True, index=True)
    stripe_event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type      = Column(String(100))
    processed_at    = Column(DateTime, default=datetime.utcnow)


class PasswordResetToken(Base):
    """
    One-time "forgot password" tokens. Only the SHA-256 HASH is stored, so a leaked
    database can't be used to take over accounts. Tokens expire and work once.
    """
    __tablename__ = "password_reset_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at    = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AdminAuditLog(Base):
    """
    What the admin did to whom. Deliberately has NO foreign keys, so the history
    survives after a user is deleted (email/ids are copied in).
    """
    __tablename__ = "admin_audit_log"

    id             = Column(Integer, primary_key=True, index=True)
    admin_id       = Column(Integer, nullable=False)
    admin_email    = Column(String(255), nullable=False)
    action         = Column(String(50), nullable=False, index=True)   # suspend | restore | delete_user | set_plan
    target_user_id = Column(Integer, nullable=True)
    target_email   = Column(String(255), nullable=True)
    detail         = Column(String(500), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow, index=True)


def ensure_schema() -> None:
    """
    Lightweight auto-migration: add any *nullable* columns that exist in the
    models but not yet in the database.

    `create_all()` only creates missing TABLES — it never alters existing ones.
    Without this, upgrading a database that already has users would crash with
    "no such column: users.stripe_subscription_id". (A fuller setup would use
    Alembic; this keeps the project dependency-free.)
    """
    from sqlalchemy import inspect, text
    from loguru import logger

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                if not col.nullable and col.default is None and col.server_default is None:
                    logger.warning(f"Cannot auto-add NOT NULL column {table.name}.{col.name}; migrate manually.")
                    continue
                col_type = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}'))
                logger.info(f"Migrated: added column {table.name}.{col.name}")


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema()

def drop_tables() -> None:
    Base.metadata.drop_all(bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
