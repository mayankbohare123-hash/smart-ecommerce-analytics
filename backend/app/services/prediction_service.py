"""
services/prediction_service.py
───────────────────────────────
Orchestrates the full ML pipeline: train → cache → predict → respond.

Flow for first request on a file:
  1. Get daily revenue series from AnalyticsService
  2. Train models via ModelTrainer (selects best automatically)
  3. Cache model paths + metrics in the DB
  4. Generate 30-day forecast via SalesPredictor
  5. Build Chart.js payload combining history + predictions
  6. Return PredictionResponse

Flow for subsequent requests on the same file:
  1. Load cached model paths from DB
  2. Skip training — go straight to inference
  3. Return fresh predictions (same model, same features)

This avoids re-training on every API call while keeping predictions
up-to-date if the user re-uploads the same file.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from loguru import logger

from sqlalchemy.orm import Session

from app.config import settings
from app.database import PredictionResult
from app.models.schemas import (
    PredictionResponse,
    ModelMetrics,
    PredictionPoint,
)
from app.services.analytics_service import AnalyticsService
from app.ml.train import ModelTrainer
from app.ml.predict import SalesPredictor, build_prediction_chart


class PredictionService:
    """
    High-level coordinator for model training, caching, and inference.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_prediction(
        self,
        file_id: int,
        analytics: AnalyticsService,
        force_retrain: bool = False,
    ) -> PredictionResponse:
        """
        Main entry point — returns a full PredictionResponse.

        If a cached result exists for this file and force_retrain is False,
        returns the cached predictions without re-training.
        """
        # ── Check cache ───────────────────────────────────────────────────────
        cached = self._load_cached(file_id)
        if cached and not force_retrain:
            logger.info(f"Using cached predictions for file_id={file_id}")
            return self._build_response_from_cache(file_id, cached, analytics)

        # ── Train fresh models ────────────────────────────────────────────────
        return self._train_and_predict(file_id, analytics)

    # ─────────────────────────────────────────────────────────────────────────
    # Private: train pipeline
    # ─────────────────────────────────────────────────────────────────────────

    def _train_and_predict(
        self, file_id: int, analytics: AnalyticsService
    ) -> PredictionResponse:
        """Run full train → predict pipeline and persist results."""

        # ── 1. Get daily revenue series ───────────────────────────────────────
        daily_series = analytics.daily_revenue_series()

        if daily_series.empty or len(daily_series) < 30:
            raise ValueError(
                "Not enough daily data to build a forecast. "
                "Upload at least 30 days of sales history."
            )

        # ── 2. Train models ───────────────────────────────────────────────────
        trainer = ModelTrainer(daily_series, file_id=file_id)
        train_result = trainer.train()

        metrics = train_result.metrics
        logger.info(
            f"Training complete — model={metrics.model_type}, "
            f"MAE=${metrics.mae:.2f}, R²={metrics.r2_score:.3f}"
        )

        # ── 3. Generate predictions ───────────────────────────────────────────
        predictor = SalesPredictor(
            model_path=train_result.model_path,
            scaler_path=train_result.scaler_path,
        )

        n_days = settings.PREDICTION_DAYS
        predictions = predictor.forecast(daily_series, n_days=n_days, mae=metrics.mae)

        # ── 4. Build chart payload ────────────────────────────────────────────
        chart_data = build_prediction_chart(daily_series, predictions)

        # ── 5. Cache in DB ────────────────────────────────────────────────────
        self._save_to_db(
            file_id=file_id,
            metrics=metrics,
            predictions=predictions,
            model_path=train_result.model_path,
        )

        # ── 6. Build response ─────────────────────────────────────────────────
        return PredictionResponse(
            file_id=file_id,
            predictions=predictions,
            model_metrics=ModelMetrics(
                model_type=metrics.model_type,
                mae=metrics.mae,
                rmse=metrics.rmse,
                r2_score=metrics.r2_score,
                training_samples=metrics.training_samples,
            ),
            prediction_days=n_days,
            chart_data=chart_data,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Private: cache management
    # ─────────────────────────────────────────────────────────────────────────

    def _load_cached(self, file_id: int) -> Optional[PredictionResult]:
        """Return the most recent cached PredictionResult for a file, or None."""
        return (
            self.db.query(PredictionResult)
            .filter(PredictionResult.file_id == file_id)
            .order_by(PredictionResult.created_at.desc())
            .first()
        )

    def _save_to_db(
        self,
        file_id: int,
        metrics,
        predictions: list,
        model_path: Path,
    ) -> None:
        """Persist model metrics and serialized predictions to the DB."""
        # Serialize predictions as JSON for storage
        pred_json = json.dumps([
            {
                "date": p.date,
                "predicted_revenue": p.predicted_revenue,
                "lower_bound": p.lower_bound,
                "upper_bound": p.upper_bound,
            }
            for p in predictions
        ])

        # Remove any previous cache entry for this file
        self.db.query(PredictionResult).filter(
            PredictionResult.file_id == file_id
        ).delete()

        record = PredictionResult(
            file_id=file_id,
            model_type=metrics.model_type,
            mae=metrics.mae,
            r2_score=metrics.r2_score,
            prediction_json=pred_json,
            created_at=datetime.utcnow(),
        )
        self.db.add(record)
        self.db.commit()

    def _build_response_from_cache(
        self,
        file_id: int,
        cached: PredictionResult,
        analytics: AnalyticsService,
    ) -> PredictionResponse:
        """Reconstruct a PredictionResponse from a DB-cached record."""
        raw = json.loads(cached.prediction_json)
        predictions = [
            PredictionPoint(
                date=p["date"],
                predicted_revenue=p["predicted_revenue"],
                lower_bound=p["lower_bound"],
                upper_bound=p["upper_bound"],
            )
            for p in raw
        ]

        daily_series = analytics.daily_revenue_series()
        chart_data   = build_prediction_chart(daily_series, predictions)

        return PredictionResponse(
            file_id=file_id,
            predictions=predictions,
            model_metrics=ModelMetrics(
                model_type=cached.model_type or "unknown",
                mae=cached.mae or 0.0,
                rmse=0.0,            # not stored separately — use 0 as placeholder
                r2_score=cached.r2_score or 0.0,
                training_samples=0,  # historical detail, not needed for display
            ),
            prediction_days=len(predictions),
            chart_data=chart_data,
        )
