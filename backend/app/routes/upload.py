"""
routes/upload.py — UPDATED: requires authentication, filters by user.
"""

from fastapi import APIRouter, UploadFile, File, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, User
from app.utils.security import get_current_user
from app.models.schemas import UploadResponse, FileListItem
from app.services.upload_service import UploadService
from app.utils.validators import validate_required_columns, validate_dataframe, get_csv_summary

router = APIRouter()

PLAN_LIMITS = {"free": 1, "starter": 5, "pro": 999}

def _check_upload_limit(user: User, db: Session):
    from app.database import UploadedFile
    count = db.query(UploadedFile).filter(UploadedFile.user_id == user.id).count()
    limit = PLAN_LIMITS.get(user.plan, 1)
    if count >= limit:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail=f"Upload limit reached for your {user.plan.title()} plan ({limit} dataset{'s' if limit != 1 else ''}). Upgrade to upload more."
        )


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_upload_limit(current_user, db)
    service = UploadService(db)
    result = await service.process_upload(file, user_id=current_user.id)
    # Increment user upload count
    current_user.upload_count = (current_user.upload_count or 0) + 1
    db.commit()
    return result


@router.get("/upload/files", response_model=List[FileListItem])
def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return UploadService(db).get_all_files(user_id=current_user.id)


@router.get("/upload/files/{file_id}", response_model=FileListItem)
def get_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return UploadService(db).get_file_by_id(file_id, user_id=current_user.id)


@router.delete("/upload/files/{file_id}")
def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = UploadService(db).delete_file(file_id, user_id=current_user.id)
    current_user.upload_count = max(0, (current_user.upload_count or 1) - 1)
    db.commit()
    return result


@router.get("/upload/preview/{file_id}")
def preview_file(
    file_id: int,
    rows: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = UploadService(db)
    df = service.load_dataframe(file_id, user_id=current_user.id)
    preview_df = df.head(rows).where(df.head(rows).notna(), other=None)
    return {
        "file_id": file_id,
        "total_rows": len(df),
        "preview_rows": len(preview_df),
        "columns": list(df.columns),
        "data": preview_df.to_dict(orient="records"),
    }


@router.get("/upload/validate/{file_id}")
def validate_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = UploadService(db)
    df = service.load_dataframe(file_id, user_id=current_user.id)
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
    }
