"""
config.py
─────────
Centralized application settings loaded from environment variables.
Uses Pydantic Settings for automatic type casting and validation.

Usage:
    from app.config import settings
    print(settings.DATABASE_URL)
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    """
    All application configuration in one place.
    Values are read from environment variables (or .env file).
    """

    # ── App metadata ────────────────────────────────────────
    APP_NAME: str = "Smart E-Commerce Analytics"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production")

    # ── Server ───────────────────────────────────────────────
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = Field(default="sqlite:///./ecommerce.db")

    # ── File uploads ─────────────────────────────────────────
    UPLOAD_DIR: str = Field(default="uploads")
    MAX_FILE_SIZE_MB: int = Field(default=10)
    ALLOWED_EXTENSIONS: str = Field(default="csv,xlsx")

    # ── CORS ─────────────────────────────────────────────────
    # Stored as comma-separated string, parsed into a list below
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:3000"
    )

    # ── Machine Learning ─────────────────────────────────────
    MODEL_DIR: str = Field(default="app/ml/models")
    PREDICTION_DAYS: int = Field(default=30)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    # ── Derived properties (not from env) ────────────────────

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into a Python list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def upload_dir_path(self) -> Path:
        """Return upload directory as a resolved Path object."""
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)  # auto-create if missing
        return path

    @property
    def model_dir_path(self) -> Path:
        """Return ML model directory as a resolved Path object."""
        path = Path(self.MODEL_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_file_size_bytes(self) -> int:
        """Convert MB limit to bytes for file size comparisons."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Parse allowed extensions into a list."""
        return [ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


# ── Singleton instance ───────────────────────────────────────────────────────
# Import this single instance throughout the app: `from app.config import settings`
settings = Settings()
