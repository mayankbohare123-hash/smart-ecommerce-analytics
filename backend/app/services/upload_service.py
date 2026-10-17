"""
services/upload_service.py — UPDATED: all queries now filter by user_id for data isolation.
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from loguru import logger

from app.config import settings
from app.database import UploadedFile
from app.models.schemas import UploadResponse
from app.utils.file_helpers import (
    generate_unique_filename, get_file_extension,
    is_allowed_extension, safe_delete,
)
from app.utils.validators import (
    validate_required_columns, validate_dataframe, get_csv_summary,
)


class UploadService:

    def __init__(self, db: Session):
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    async def process_upload(self, file: UploadFile, user_id: int) -> UploadResponse:
        """Upload pipeline — now requires user_id for ownership tracking."""
        logger.info(f"Processing upload: {file.filename} for user_id={user_id}")

        self._validate_extension(file.filename)
        file_bytes = await file.read()
        self._validate_size(len(file_bytes), file.filename)

        temp_path = self._save_temp_file(file_bytes, file.filename)
        try:
            df = self._parse_csv(temp_path, file.filename)
            self._validate_csv_structure(df, file.filename)
            final_path = self._finalize_file(temp_path, file.filename)
            db_record = self._save_to_db(
                original_name=file.filename,
                final_path=final_path,
                file_size=len(file_bytes),
                df=df,
                user_id=user_id,
            )
            summary = get_csv_summary(df)
            logger.info(f"Upload complete: file_id={db_record.id}, user_id={user_id}")
            return UploadResponse(
                success=True,
                file_id=db_record.id,
                filename=db_record.filename,
                row_count=db_record.row_count,
                column_count=db_record.column_count,
                columns=summary["columns"],
                message=f"Successfully uploaded '{file.filename}' with {db_record.row_count:,} rows.",
            )
        except HTTPException:
            safe_delete(temp_path)
            raise
        except Exception as e:
            safe_delete(temp_path)
            logger.error(f"Upload failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

    def get_all_files(self, user_id: int) -> list:
        """Return only files belonging to this user."""
        return (
            self.db.query(UploadedFile)
            .filter(UploadedFile.user_id == user_id)
            .order_by(UploadedFile.uploaded_at.desc())
            .all()
        )

    def get_file_by_id(self, file_id: int, user_id: int) -> UploadedFile:
        """Get a file — only if it belongs to this user."""
        record = (
            self.db.query(UploadedFile)
            .filter(UploadedFile.id == file_id, UploadedFile.user_id == user_id)
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail=f"File #{file_id} not found.")
        return record

    def delete_file(self, file_id: int, user_id: int) -> dict:
        """Delete a file — only if it belongs to this user."""
        record = self.get_file_by_id(file_id, user_id)
        safe_delete(Path(record.file_path))
        self.db.delete(record)
        self.db.commit()
        logger.info(f"Deleted file_id={file_id} for user_id={user_id}")
        return {"success": True, "file_id": file_id, "message": "File deleted."}

    def load_dataframe(self, file_id: int, user_id: int) -> pd.DataFrame:
        """Load CSV into DataFrame — verifies ownership before reading."""
        record = self.get_file_by_id(file_id, user_id)
        file_path = Path(record.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File data not found for file #{file_id}.")
        return self._parse_csv(file_path, record.original_name)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _validate_extension(self, filename: str) -> None:
        if not filename:
            raise HTTPException(status_code=400, detail="Filename is required.")
        if not is_allowed_extension(filename):
            ext = get_file_extension(filename)
            raise HTTPException(status_code=400, detail=f"File type '.{ext}' not allowed. Use CSV or Excel.")

    def _validate_size(self, byte_count: int, filename: str) -> None:
        if byte_count == 0:
            raise HTTPException(status_code=400, detail=f"'{filename}' is empty.")
        if byte_count > settings.max_file_size_bytes:
            mb = byte_count / (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"File is {mb:.1f}MB. Max is {settings.MAX_FILE_SIZE_MB}MB.")

    def _save_temp_file(self, data: bytes, original_name: str) -> Path:
        temp_name = f"tmp_{generate_unique_filename(original_name)}"
        temp_path = settings.upload_dir_path / temp_name
        with open(temp_path, "wb") as f:
            f.write(data)
        return temp_path

    def _parse_csv(self, file_path: Path, original_name: str) -> pd.DataFrame:
        ext = get_file_extension(original_name)
        try:
            if ext in ("xlsx", "xls"):
                df = pd.read_excel(file_path, engine="openpyxl")
            else:
                try:
                    df = pd.read_csv(file_path, encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding="latin-1")
            str_cols = df.select_dtypes(include="object").columns
            df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())
            return df
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not parse '{original_name}': {str(e)}")

    def _validate_csv_structure(self, df: pd.DataFrame, filename: str) -> None:
        is_valid, missing = validate_required_columns(list(df.columns))
        if not is_valid:
            raise HTTPException(status_code=422, detail=f"Missing required columns: {missing}.")
        is_valid, errors = validate_dataframe(df)
        if not is_valid:
            raise HTTPException(status_code=422, detail=" | ".join(errors))

    def _finalize_file(self, temp_path: Path, original_name: str) -> Path:
        final_name = generate_unique_filename(original_name)
        final_path = settings.upload_dir_path / final_name
        temp_path.rename(final_path)
        return final_path

    def _save_to_db(self, original_name: str, final_path: Path, file_size: int, df: pd.DataFrame, user_id: int) -> UploadedFile:
        record = UploadedFile(
            user_id=user_id,
            filename=final_path.name,
            original_name=original_name,
            file_path=str(final_path),
            file_size=file_size,
            row_count=len(df),
            column_count=len(df.columns),
            status="processed",
            processed_at=datetime.utcnow(),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
