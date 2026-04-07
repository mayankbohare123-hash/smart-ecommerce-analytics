"""
services/upload_service.py
──────────────────────────
All business logic for the file upload flow.

The route handler stays thin — it delegates everything here.
This separation makes the logic unit-testable without HTTP context.

Flow:
  1. Validate file extension and size
  2. Save raw bytes to disk (temp path)
  3. Parse with Pandas and run column/data validation
  4. Rename to a safe unique filename
  5. Persist metadata to the database
  6. Return a rich upload response
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Tuple

import pandas as pd
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from loguru import logger

from app.config import settings
from app.database import UploadedFile
from app.models.schemas import UploadResponse
from app.utils.file_helpers import (
    generate_unique_filename,
    get_file_extension,
    is_allowed_extension,
    safe_delete,
    build_upload_path,
)
from app.utils.validators import (
    validate_required_columns,
    validate_dataframe,
    get_csv_summary,
)


class UploadService:
    """
    Handles the complete lifecycle of a file upload:
    validation → storage → parsing → DB persistence.
    """

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def process_upload(self, file: UploadFile) -> UploadResponse:
        """
        Main entry point — orchestrates the full upload pipeline.
        Raises HTTPException on any validation or processing failure.
        """
        logger.info(f"Processing upload: {file.filename} ({file.content_type})")

        # Step 1 — Validate file type before reading any bytes
        self._validate_extension(file.filename)

        # Step 2 — Read file into memory and check size
        file_bytes = await file.read()
        self._validate_size(len(file_bytes), file.filename)

        # Step 3 — Save to a temp path so we can parse it
        temp_path = self._save_temp_file(file_bytes, file.filename)

        try:
            # Step 4 — Parse and validate the CSV content
            df = self._parse_csv(temp_path, file.filename)
            self._validate_csv_structure(df, file.filename)

            # Step 5 — Move to a permanent unique path
            final_path = self._finalize_file(temp_path, file.filename)

            # Step 6 — Persist to DB and build response
            db_record = self._save_to_db(
                original_name=file.filename,
                final_path=final_path,
                file_size=len(file_bytes),
                df=df,
            )

            summary = get_csv_summary(df)
            logger.info(
                f"Upload complete: file_id={db_record.id}, "
                f"rows={db_record.row_count}, cols={db_record.column_count}"
            )

            return UploadResponse(
                success=True,
                file_id=db_record.id,
                filename=db_record.filename,
                row_count=db_record.row_count,
                column_count=db_record.column_count,
                columns=summary["columns"],
                message=(
                    f"Successfully uploaded '{file.filename}' — "
                    f"{db_record.row_count:,} rows ready for analysis."
                ),
            )

        except HTTPException:
            # Re-raise HTTP exceptions unchanged
            safe_delete(temp_path)
            raise

        except Exception as e:
            # Unexpected error — clean up and wrap
            safe_delete(temp_path)
            logger.error(f"Upload failed for {file.filename}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process file: {str(e)}"
            )

    def get_all_files(self) -> list[UploadedFile]:
        """Return all uploaded files ordered by most recent first."""
        return (
            self.db.query(UploadedFile)
            .order_by(UploadedFile.uploaded_at.desc())
            .all()
        )

    def get_file_by_id(self, file_id: int) -> UploadedFile:
        """
        Fetch a single file record by ID.
        Raises 404 HTTPException if not found.
        """
        record = self.db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"File with id={file_id} not found."
            )
        return record

    def delete_file(self, file_id: int) -> dict:
        """
        Delete a file from disk and remove its DB record.
        Returns a confirmation dict.
        """
        record = self.get_file_by_id(file_id)
        file_path = Path(record.file_path)

        # Remove from disk
        deleted_from_disk = safe_delete(file_path)

        # Remove from DB
        self.db.delete(record)
        self.db.commit()

        logger.info(f"Deleted file_id={file_id}, disk_deleted={deleted_from_disk}")
        return {
            "success": True,
            "file_id": file_id,
            "filename": record.original_name,
            "message": "File deleted successfully.",
        }

    def load_dataframe(self, file_id: int) -> pd.DataFrame:
        """
        Load the CSV for a given file_id into a DataFrame.
        Used by analytics and prediction services.
        Raises 404 if the file record or disk file is missing.
        """
        record = self.get_file_by_id(file_id)
        file_path = Path(record.file_path)

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File data not found on disk for file_id={file_id}. "
                       "It may have been deleted."
            )

        df = self._parse_csv(file_path, record.original_name)
        logger.debug(f"Loaded DataFrame for file_id={file_id}: {df.shape}")
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _validate_extension(self, filename: str) -> None:
        """Reject files with disallowed extensions before touching their bytes."""
        if not filename:
            raise HTTPException(status_code=400, detail="Filename is required.")

        if not is_allowed_extension(filename):
            ext = get_file_extension(filename)
            allowed = ", ".join(settings.allowed_extensions_list)
            raise HTTPException(
                status_code=400,
                detail=f"File type '.{ext}' is not allowed. Accepted: {allowed}."
            )

    def _validate_size(self, byte_count: int, filename: str) -> None:
        """Reject files that exceed MAX_FILE_SIZE_MB."""
        if byte_count > settings.max_file_size_bytes:
            size_mb = byte_count / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File '{filename}' is {size_mb:.1f} MB. "
                    f"Maximum allowed size is {settings.MAX_FILE_SIZE_MB} MB."
                )
            )

        if byte_count == 0:
            raise HTTPException(
                status_code=400,
                detail=f"File '{filename}' is empty."
            )

    def _save_temp_file(self, data: bytes, original_name: str) -> Path:
        """
        Write raw bytes to a temporary file in the upload directory.
        Named with a 'tmp_' prefix so we can identify and clean up
        incomplete uploads.
        """
        temp_name = f"tmp_{generate_unique_filename(original_name)}"
        temp_path = settings.upload_dir_path / temp_name

        with open(temp_path, "wb") as f:
            f.write(data)

        return temp_path

    def _parse_csv(self, file_path: Path, original_name: str) -> pd.DataFrame:
        """
        Parse a CSV (or Excel) file into a DataFrame.
        Handles common encoding issues automatically.
        """
        ext = get_file_extension(original_name)

        try:
            if ext in ("xlsx", "xls"):
                df = pd.read_excel(file_path, engine="openpyxl")
            else:
                # Try UTF-8 first, fall back to latin-1 for legacy files
                try:
                    df = pd.read_csv(file_path, encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding="latin-1")

            # Strip leading/trailing whitespace from all string columns
            str_cols = df.select_dtypes(include="object").columns
            df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())

            return df

        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Could not parse file '{original_name}': {str(e)}. "
                       "Please ensure it is a valid CSV file."
            )

    def _validate_csv_structure(self, df: pd.DataFrame, filename: str) -> None:
        """
        Run column presence + data quality checks.
        Raises 422 with a descriptive message on failure.
        """
        # Check required columns exist
        is_valid, missing = validate_required_columns(list(df.columns))
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Missing required columns: {missing}. "
                    f"Your CSV has: {list(df.columns)}. "
                    "Required: a date column and a revenue/sales column."
                )
            )

        # Run data quality checks
        is_valid, errors = validate_dataframe(df)
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail=f"Data quality issues in '{filename}': " + " | ".join(errors)
            )

    def _finalize_file(self, temp_path: Path, original_name: str) -> Path:
        """
        Rename the temp file to its permanent unique filename.
        Returns the final Path.
        """
        final_name = generate_unique_filename(original_name)
        final_path = settings.upload_dir_path / final_name
        temp_path.rename(final_path)
        return final_path

    def _save_to_db(
        self,
        original_name: str,
        final_path: Path,
        file_size: int,
        df: pd.DataFrame,
    ) -> UploadedFile:
        """
        Create and persist an UploadedFile record in the database.
        Returns the saved ORM object (with its auto-assigned ID).
        """
        record = UploadedFile(
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
        self.db.refresh(record)   # populate the auto-generated `id`
        return record
