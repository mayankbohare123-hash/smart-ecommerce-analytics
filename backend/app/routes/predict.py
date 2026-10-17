"""
routes/predict.py — UPDATED: requires authentication.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db, User
from app.utils.security import get_current_user
from app.models.schemas import PredictionResponse
from app.services.upload_service import UploadService
from app.services.analytics_service import AnalyticsService
from app.services.prediction_service import PredictionService

router = APIRouter()


def _get_prediction_services(file_id: int, user_id: int, db: Session):
    df = UploadService(db).load_dataframe(file_id, user_id=user_id)
    return AnalyticsService(df), PredictionService(db)


@router.get("/predict/{file_id}", response_model=PredictionResponse)
def get_predictions(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        analytics, prediction = _get_prediction_services(file_id, current_user.id, db)
        return prediction.get_or_create_prediction(file_id=file_id, analytics=analytics, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/predict/{file_id}/retrain", response_model=PredictionResponse)
def retrain(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        analytics, prediction = _get_prediction_services(file_id, current_user.id, db)
        return prediction.get_or_create_prediction(file_id=file_id, analytics=analytics, force_retrain=True, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/predict/{file_id}/metrics")
def get_metrics(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        analytics, prediction = _get_prediction_services(file_id, current_user.id, db)
        result = prediction.get_or_create_prediction(file_id=file_id, analytics=analytics, user_id=current_user.id)
        return {"file_id": file_id, "model_metrics": result.model_metrics, "prediction_days": result.prediction_days}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
