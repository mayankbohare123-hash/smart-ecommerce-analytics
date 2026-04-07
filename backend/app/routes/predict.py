"""
routes/predict.py
──────────────────
HTTP endpoints for ML-powered sales predictions.

Endpoints:
  GET  /api/predict/{file_id}          — Get/generate 30-day forecast
  POST /api/predict/{file_id}/retrain  — Force model re-train
  GET  /api/predict/{file_id}/metrics  — Model performance metrics only
  GET  /api/predict/{file_id}/chart    — Prediction chart data only

The first call to /predict/{file_id} trains the model and caches it.
Subsequent calls return cached predictions instantly.
Use /retrain to force a fresh model when the data has changed.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from loguru import logger

from app.database import get_db
from app.models.schemas import PredictionResponse, ErrorResponse
from app.services.upload_service import UploadService
from app.services.analytics_service import AnalyticsService
from app.services.prediction_service import PredictionService

router = APIRouter()


def _get_services(file_id: int, db: Session):
    """Shared dep: load df → analytics service → prediction service."""
    df         = UploadService(db).load_dataframe(file_id)
    analytics  = AnalyticsService(df)
    prediction = PredictionService(db)
    return analytics, prediction


@router.get(
    "/predict/{file_id}",
    response_model=PredictionResponse,
    summary="Get 30-day sales forecast",
    responses={
        404: {"model": ErrorResponse, "description": "File not found"},
        422: {"model": ErrorResponse, "description": "Not enough data to forecast"},
    },
)
def get_predictions(file_id: int, db: Session = Depends(get_db)):
    """
    Returns a 30-day revenue forecast for the uploaded file.

    - First call: trains the ML model (~2–5 seconds) and caches results
    - Subsequent calls: returns cached predictions instantly
    - Use /retrain to force re-training

    Response includes:
    - predictions: list of {date, predicted_revenue, lower_bound, upper_bound}
    - model_metrics: MAE, RMSE, R² score
    - chart_data: Chart.js payload combining 60-day history + forecast

    **Postman:** GET http://localhost:8000/api/predict/1
    """
    try:
        analytics, prediction = _get_services(file_id, db)
        return prediction.get_or_create_prediction(
            file_id=file_id,
            analytics=analytics,
            force_retrain=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/predict/{file_id}/retrain",
    response_model=PredictionResponse,
    summary="Force model re-training",
    responses={404: {"model": ErrorResponse}},
)
def retrain_model(file_id: int, db: Session = Depends(get_db)):
    """
    Forces the ML model to re-train from scratch, discarding the cache.
    Use this after uploading new data or if predictions seem stale.

    This is a synchronous endpoint — it blocks until training completes.

    **Postman:** POST http://localhost:8000/api/predict/1/retrain
    """
    try:
        analytics, prediction = _get_services(file_id, db)
        logger.info(f"Forced retrain requested for file_id={file_id}")
        return prediction.get_or_create_prediction(
            file_id=file_id,
            analytics=analytics,
            force_retrain=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "/predict/{file_id}/metrics",
    summary="Model performance metrics only",
    responses={404: {"model": ErrorResponse}},
)
def get_model_metrics(file_id: int, db: Session = Depends(get_db)):
    """
    Returns only the model performance metrics without regenerating predictions.
    Useful for a model info panel on the dashboard.

    If no model has been trained yet, triggers training first.

    **Postman:** GET http://localhost:8000/api/predict/1/metrics
    """
    try:
        analytics, prediction_svc = _get_services(file_id, db)
        result = prediction_svc.get_or_create_prediction(
            file_id=file_id,
            analytics=analytics,
        )
        return {
            "file_id": file_id,
            "model_metrics": result.model_metrics,
            "prediction_days": result.prediction_days,
            "generated_at": result.generated_at,
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "/predict/{file_id}/chart",
    summary="Prediction chart data only",
    responses={404: {"model": ErrorResponse}},
)
def get_prediction_chart(file_id: int, db: Session = Depends(get_db)):
    """
    Returns only the Chart.js chart payload for the prediction view.
    Includes 60 days of historical data + 30-day forecast in one dataset.

    **Postman:** GET http://localhost:8000/api/predict/1/chart
    """
    try:
        analytics, prediction_svc = _get_services(file_id, db)
        result = prediction_svc.get_or_create_prediction(
            file_id=file_id,
            analytics=analytics,
        )
        return {"file_id": file_id, "chart_data": result.chart_data}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
