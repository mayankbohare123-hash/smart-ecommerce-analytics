"""
ml/predict.py
─────────────
Inference engine — generates future revenue forecasts using a trained model.

Strategy: "Rolling forecast" (also called "recursive forecasting")
  - Start from the last known date in the historical data
  - Predict day N+1 using real historical data + previous predictions
  - Feed each prediction back as a lag feature for the next step
  - Repeat for PREDICTION_DAYS steps

This handles the cold-start problem for lag features:
  lag_7d on day 3 of the forecast uses the actual prediction from day -4,
  not zero or NaN.

Confidence intervals are approximated by adding ± 1.5 × training MAE.
A proper uncertainty estimate would use bootstrapping or quantile regression,
but this gives intuitive bands for a dashboard display.
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from datetime import timedelta
from typing import List, Optional
from loguru import logger

from app.config import settings
from app.ml.train import build_features, get_feature_columns
from app.models.schemas import PredictionPoint, ModelMetrics, PredictionResponse, ChartData, ChartDataset


class SalesPredictor:
    """
    Loads a trained model from disk and generates forward-looking forecasts.

    Usage:
        predictor = SalesPredictor(file_id=1)
        result    = predictor.predict(daily_series, training_metrics)
    """

    def __init__(self, model_path: Path, scaler_path: Optional[Path] = None):
        self.model   = joblib.load(model_path)
        self.scaler  = joblib.load(scaler_path) if scaler_path and scaler_path.exists() else None
        self.feature_cols = get_feature_columns()
        logger.info(f"Loaded model from {model_path}")

    def forecast(
        self,
        daily_series: pd.Series,
        n_days: int,
        mae: float,
    ) -> List[PredictionPoint]:
        """
        Generate n_days of forward predictions using the rolling forecast strategy.

        Args:
            daily_series: Historical daily revenue indexed by datetime
            n_days:       Number of future days to predict
            mae:          Training MAE — used to build confidence intervals

        Returns:
            List of PredictionPoint, one per future day
        """
        logger.info(f"Forecasting {n_days} days ahead from {daily_series.index[-1].date()}")

        # Work with a copy so we can append predictions without mutating input
        extended_series = daily_series.copy()
        predictions: List[PredictionPoint] = []

        for step in range(n_days):
            # Build features for the next date using all data seen so far
            next_date     = extended_series.index[-1] + timedelta(days=1)
            next_features = self._build_next_features(extended_series, next_date)

            # Reshape to (1, n_features) for sklearn
            X = next_features.reshape(1, -1)

            # Apply scaler if the selected model needs it (Linear Regression)
            if self.scaler is not None:
                X = self.scaler.transform(X)

            # Predict and clip to non-negative
            predicted_value = float(max(self.model.predict(X)[0], 0.0))

            # Confidence interval: ±1.5× MAE, widening slightly for distant days
            # The further out we predict, the less certain we are
            uncertainty = mae * (1.5 + step * 0.02)
            lower = max(predicted_value - uncertainty, 0.0)
            upper = predicted_value + uncertainty

            predictions.append(PredictionPoint(
                date=next_date.strftime("%Y-%m-%d"),
                predicted_revenue=round(predicted_value, 2),
                lower_bound=round(lower, 2),
                upper_bound=round(upper, 2),
            ))

            # Append prediction to series so next iteration can use it as a lag
            extended_series[next_date] = predicted_value

        return predictions

    def _build_next_features(self, series: pd.Series, target_date: pd.Timestamp) -> np.ndarray:
        """
        Build the feature vector for a single future date.

        Appends a NaN placeholder for the target date, builds the full
        feature DataFrame, then extracts the last row's features.
        """
        # Extend the series with a placeholder for the target date
        extended = series.copy()
        extended[target_date] = np.nan

        # Build full feature matrix (NaN target row will have real lag/rolling values)
        df_feat = build_features(extended)

        # Extract the last row (our target date) — but only the feature columns
        last_row = df_feat[self.feature_cols].iloc[-1].values

        # If any features are still NaN (very short series), fill with 0
        last_row = np.nan_to_num(last_row, nan=0.0)
        return last_row


# ── Chart builder ─────────────────────────────────────────────────────────────

def build_prediction_chart(
    daily_series: pd.Series,
    predictions: List[PredictionPoint],
    history_days: int = 60,
) -> ChartData:
    """
    Combine the last N days of historical revenue with the forecast
    into a single Chart.js dataset for the prediction chart.

    The frontend renders this as a line chart with:
      - Solid line for historical data (dataset 0)
      - Dashed line for forecast (dataset 1)
      - Shaded area between lower/upper bounds (datasets 2 & 3)
    """
    # ── Historical portion (last history_days days) ───────────────────────────
    historical = daily_series.tail(history_days)
    hist_labels  = [d.strftime("%Y-%m-%d") for d in historical.index]
    hist_revenue = [round(float(v), 2) for v in historical.values]

    # ── Forecast portion ──────────────────────────────────────────────────────
    pred_labels  = [p.date for p in predictions]
    pred_revenue = [p.predicted_revenue for p in predictions]
    pred_lower   = [p.lower_bound for p in predictions]
    pred_upper   = [p.upper_bound for p in predictions]

    # ── Combined labels ───────────────────────────────────────────────────────
    all_labels = hist_labels + pred_labels

    # Pad historical datasets with None for forecast dates (and vice-versa)
    # Chart.js will draw gaps for None values, creating two separate segments
    hist_padded   = hist_revenue + [None] * len(predictions)
    pred_padded   = [None] * len(historical) + pred_revenue
    lower_padded  = [None] * len(historical) + pred_lower
    upper_padded  = [None] * len(historical) + pred_upper

    return ChartData(
        labels=all_labels,
        datasets=[
            ChartDataset(
                label="Historical Revenue ($)",
                data=hist_padded,
                borderColor="#6366f1",
                backgroundColor="rgba(99,102,241,0.06)",
                borderWidth=2,
                fill=False,
                tension=0.3,
            ),
            ChartDataset(
                label="Predicted Revenue ($)",
                data=pred_padded,
                borderColor="#f59e0b",
                backgroundColor="rgba(245,158,11,0.08)",
                borderWidth=2,
                fill=False,
                tension=0.3,
            ),
            ChartDataset(
                label="Upper Bound",
                data=upper_padded,
                borderColor="rgba(245,158,11,0.25)",
                backgroundColor="rgba(245,158,11,0.08)",
                borderWidth=1,
                fill=False,
                tension=0.3,
            ),
            ChartDataset(
                label="Lower Bound",
                data=lower_padded,
                borderColor="rgba(245,158,11,0.25)",
                backgroundColor="rgba(245,158,11,0.08)",
                borderWidth=1,
                fill=False,
                tension=0.3,
            ),
        ],
    )
