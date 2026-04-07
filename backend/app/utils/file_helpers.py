"""
utils/file_helpers.py
─────────────────────
Shared utility functions for file handling.
Used by the upload service to validate and manage files.
"""

import os
import hashlib
import uuid
from pathlib import Path
from typing import Tuple

from app.config import settings


def generate_unique_filename(original_filename: str) -> str:
    """
    Generate a collision-safe filename by prepending a UUID prefix.
    Preserves the original extension for readability.

    Example: "sales_q1.csv" → "a3f7b2c1_sales_q1.csv"
    """
    ext = Path(original_filename).suffix.lower()
    prefix = uuid.uuid4().hex[:8]
    safe_stem = Path(original_filename).stem.replace(" ", "_")
    return f"{prefix}_{safe_stem}{ext}"


def get_file_extension(filename: str) -> str:
    """Return the lowercase file extension without the dot."""
    return Path(filename).suffix.lstrip(".").lower()


def is_allowed_extension(filename: str) -> bool:
    """Check if the file extension is in the allowed list from config."""
    ext = get_file_extension(filename)
    return ext in settings.allowed_extensions_list


def get_file_size_mb(file_path: Path) -> float:
    """Return the size of a file in megabytes."""
    return file_path.stat().st_size / (1024 * 1024)


def compute_md5(file_path: Path, chunk_size: int = 8192) -> str:
    """
    Compute the MD5 hash of a file for duplicate detection.
    Reads in chunks to handle large files without memory issues.
    """
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            md5.update(chunk)
    return md5.hexdigest()


def safe_delete(file_path: Path) -> bool:
    """
    Delete a file safely. Returns True if deleted, False if it didn't exist.
    Never raises — logs errors silently for cleanup operations.
    """
    try:
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    except OSError:
        return False


def build_upload_path(filename: str) -> Path:
    """Return the full path where an uploaded file should be stored."""
    return settings.upload_dir_path / filename
