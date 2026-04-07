"""
routes/upload.py
────────────────
All HTTP endpoints for file upload management.

Endpoints:
  POST   /api/upload              — Upload a CSV file
  GET    /api/upload/files        — List all uploaded files
  GET    /api/upload/files/{id}   — Get a single file's metadata
  DELETE /api/upload/files/{id}   — Delete a file
  GET    /api/upload/preview/{id} — Preview first N rows as JSON
  GET    /api/upload/validate/{id}— Re-validate structure & column mapping

All heavy logic is in UploadService — routes stay thin.
"""

from fastapi import APIRouter, UploadFile, File, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.schemas import UploadResponse, FileListItem, ErrorResponse
from app.services.upload_service import UploadService


router = APIRouter()


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload a sales CSV file",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file type or empty file"},
        413: {"model": ErrorResponse, "description": "File too large"},
        422: {"model": ErrorResponse, "description": "CSV structure or data quality error"},
    }
)
async def upload_file(
    file: UploadFile = File(..., description="CSV or Excel sales file"),
    db: Session = Depends(get_db),
):
    """
    Upload a sales CSV file for analysis.

    Must contain at minimum:
    - A date column (date, order_date, sale_date ...)
    - A revenue column (revenue, net_revenue, total, sales ...)

    **Postman:** POST /api/upload · Body → form-data · Key: file (type: File)
    """
    service = UploadService(db)
    return await service.process_upload(file)


@router.get("/upload/files", response_model=List[FileListItem], summary="List all uploaded files")
def list_files(db: Session = Depends(get_db)):
    """Returns all uploaded files, newest first. **Postman:** GET /api/upload/files"""
    return UploadService(db).get_all_files()


@router.get(
    "/upload/files/{file_id}",
    response_model=FileListItem,
    summary="Get file metadata by ID",
    responses={404: {"model": ErrorResponse}},
)
def get_file(file_id: int, db: Session = Depends(get_db)):
    """**Postman:** GET /api/upload/files/1"""
    return UploadService(db).get_file_by_id(file_id)


@router.delete("/upload/files/{file_id}", summary="Delete an uploaded file")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    """Permanently deletes the file from disk and DB. **Postman:** DELETE /api/upload/files/1"""
    return UploadService(db).delete_file(file_id)


@router.get("/upload/preview/{file_id}", summary="Preview first N rows of an uploaded file")
def preview_file(
    file_id: int,
    rows: int = Query(default=10, ge=1, le=100, description="Number of rows to preview"),
    db: Session = Depends(get_db),
):
    """
    Returns the first N rows of the CSV as JSON.
    **Postman:** GET /api/upload/preview/1?rows=5
    """
    service = UploadService(db)
    df = service.load_dataframe(file_id)
    preview_df = df.head(rows).where(df.head(rows).notna(), other=None)
    return {
        "file_id": file_id,
        "total_rows": len(df),
        "preview_rows": len(preview_df),
        "columns": list(df.columns),
        "data": preview_df.to_dict(orient="records"),
    }


@router.get("/upload/validate/{file_id}", summary="Validate an uploaded file's structure")
def validate_file(file_id: int, db: Session = Depends(get_db)):
    """
    Re-runs column detection and data quality checks.
    Returns detected column mapping so you can confirm before running analytics.
    **Postman:** GET /api/upload/validate/1
    """
    from app.utils.validators import get_csv_summary, validate_required_columns, validate_dataframe

    service = UploadService(db)
    df = service.load_dataframe(file_id)

    col_valid, missing = validate_required_columns(list(df.columns))
    data_valid, data_errors = validate_dataframe(df)
    summary = get_csv_summary(df)

    return {
        "file_id": file_id,
        "is_valid": col_valid and data_valid,
        "column_validation": {"passed": col_valid, "missing_required": missing},
        "data_validation": {"passed": data_valid, "errors": data_errors},
        "detected_mapping": summary.get("detected_mapping", {}),
        "date_range": summary.get("date_range"),
        "row_count": summary["row_count"],
        "null_counts": summary["null_counts"],
    }
