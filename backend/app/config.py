"""
config.py — UPDATED with JWT settings for auth.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from pathlib import Path


class Settings(BaseSettings):

    # ── App metadata ─────────────────────────────────────────
    APP_NAME: str = "SalesIQ"
    APP_VERSION: str = "2.0.0"
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production")

    # ── Server ────────────────────────────────────────────────
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = Field(default="sqlite:///./salesiq.db")

    # ── JWT Authentication (NEW) ──────────────────────────────
    # Generate a real secret with:
    # python -c "import secrets; print(secrets.token_hex(32))"
    JWT_SECRET_KEY: str = Field(default="change-this-to-a-long-random-secret-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)    # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)       # 7 days

    # ── Stripe billing (Step 2) ───────────────────────────────
    # Leave blank to run the app without billing — checkout endpoints then
    # return a clear "not configured" error instead of crashing.
    STRIPE_SECRET_KEY: str = Field(default="")
    STRIPE_WEBHOOK_SECRET: str = Field(default="")
    STRIPE_STARTER_PRICE_ID: str = Field(default="")
    STRIPE_PRO_PRICE_ID: str = Field(default="")
    # Where Stripe sends people back to after checkout / the billing portal
    FRONTEND_URL: str = Field(default="http://localhost:5173")

    # ── Password reset + email ────────────────────────────────
    PASSWORD_RESET_EXPIRE_MINUTES: int = Field(default=60)
    PASSWORD_RESET_MAX_PER_HOUR: int = Field(default=3)   # per account — stops email-bombing
    # SMTP is optional. If SMTP_HOST is blank, emails are NOT sent; in development
    # the message (including the reset link) is printed in the backend terminal.
    SMTP_HOST: str = Field(default="")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_STARTTLS: bool = Field(default=True)
    EMAIL_FROM: str = Field(default="SalesIQ <no-reply@salesiq.local>")

    # ── File uploads ──────────────────────────────────────────
    UPLOAD_DIR: str = Field(default="uploads")
    MAX_FILE_SIZE_MB: int = Field(default=10)
    ALLOWED_EXTENSIONS: str = Field(default="csv,xlsx")

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:3000")

    # ── Machine Learning ──────────────────────────────────────
    MODEL_DIR: str = Field(default="app/ml/models")
    PREDICTION_DAYS: int = Field(default=30)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def upload_dir_path(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def model_dir_path(self) -> Path:
        path = Path(self.MODEL_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def stripe_configured(self) -> bool:
        return bool(self.STRIPE_SECRET_KEY and self.STRIPE_STARTER_PRICE_ID and self.STRIPE_PRO_PRICE_ID)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
