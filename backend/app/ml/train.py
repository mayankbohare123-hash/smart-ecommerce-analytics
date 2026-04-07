"""
ml/train.py
───────────
Feature engineering and model training pipeline.

Two models are trained and compared:
  1. Linear Regression  — fast, interpretable baseline
  2. Random Forest      — captures non-linear seasonality patterns

The better model (by R² score on the test split) is selected
automatically and serialized to disk with joblib.

Features engineered from the daily revenue time series:
  - Day of week (0=Mon … 6=Sun)
  - Day of month (1–31)
  - Month (1–12)
  - Quarter (1–4)
  - Is weekend flag
  - Lag features: revenue 7, 14, 30 days ago
  - Rolling means: 7-day and 30-day windows
  - Day-of-year (captures annual seasonality)
  - Trend (integer day index from the start)

Usage:
    trainer = ModelTrainer(daily_series)
    result  = trainer.train()
    # result.model_path  → path to saved .joblib file
    # result.metrics     → MAE, RMSE, R²
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from dataclasses import dataclass
from typing import Tuple

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from loguru import logger

from app.config import settings


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TrainingMetrics:
    model_type: str
    mae: float           # Mean Absolute Error ($)
    rmse: float          # Root Mean Square Error ($)
    r2_score: float      # Coefficient of determination (0–1)
    training_samples: int
    test_samples: int


@dataclass
class TrainingResult:
    metrics: TrainingMetrics
    model_path: Path
    scaler_path: Path
    feature_names: list


# ── Feature engineering ───────────────────────────────────────────────────────

def build_features(series: pd.Series) -> pd.DataFrame:
    """
    Transform a daily revenue Series into a feature matrix for ML training.

    Input:  pd.Series indexed by datetime, values = daily revenue
    Output: pd.DataFrame with one row per day, one column per feature

    Why these features?
    - Calendar features (dow, month, quarter) capture seasonality
    - Lag features give the model "memory" of recent revenue
    - Rolling means smooth out day-to-day noise
    - Trend captures overall growth/decline direction
    """
    df = pd.DataFrame({"revenue": series})
    df.index = pd.to_datetime(df.index)

    # ── Calendar features ─────────────────────────────────────────────────────
    df["day_of_week"]  = df.index.dayofweek          # 0=Mon, 6=Sun
    df["day_of_month"] = df.index.day
    df["month"]        = df.index.month
    df["quarter"]      = df.index.quarter
    df["day_of_year"]  = df.index.dayofyear
    df["is_weekend"]   = (df.index.dayofweek >= 5).astype(int)
    df["week_of_year"] = df.index.isocalendar().week.astype(int)

    # ── Trend feature (monotonically increasing) ──────────────────────────────
    df["trend"] = np.arange(len(df))

    # ── Lag features (previous revenue values) ────────────────────────────────
    # These give the model "memory" of recent performance
    for lag in [1, 7, 14, 30]:
        df[f"lag_{lag}d"] = df["revenue"].shift(lag)

    # ── Rolling window statistics ─────────────────────────────────────────────
    df["rolling_mean_7d"]  = df["revenue"].shift(1).rolling(7,  min_periods=1).mean()
    df["rolling_mean_30d"] = df["revenue"].shift(1).rolling(30, min_periods=7).mean()
    df["rolling_std_7d"]   = df["revenue"].shift(1).rolling(7,  min_periods=2).std().fillna(0)

    # ── Cyclical encoding for periodic features ───────────────────────────────
    # Sine/cosine encoding preserves the cyclic nature:
    # e.g., month 12 and month 1 are close, not 11 apart
    df["month_sin"]  = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"]  = np.cos(2 * np.pi * df["month"] / 12)
    df["dow_sin"]    = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"]    = np.cos(2 * np.pi * df["day_of_week"] / 7)

    return df


def get_feature_columns() -> list:
    """Return the ordered list of feature column names used in training."""
    return [
        "day_of_week", "day_of_month", "month", "quarter",
        "day_of_year", "is_weekend", "week_of_year", "trend",
        "lag_1d", "lag_7d", "lag_14d", "lag_30d",
        "rolling_mean_7d", "rolling_mean_30d", "rolling_std_7d",
        "month_sin", "month_cos", "dow_sin", "dow_cos",
    ]


# ── Model trainer ─────────────────────────────────────────────────────────────

class ModelTrainer:
    """
    Trains and evaluates two forecasting models on a daily revenue series.
    Automatically selects the better model and saves it to disk.
    """

    def __init__(self, daily_series: pd.Series, file_id: int = 0):
        self.daily_series = daily_series
        self.file_id      = file_id
        self.feature_cols = get_feature_columns()

    def train(self) -> TrainingResult:
        """
        Full training pipeline:
          1. Engineer features
          2. Prepare train/test split (time-aware: no future leakage)
          3. Train both models
          4. Evaluate and pick the winner
          5. Serialize to disk
        Returns TrainingResult with metrics and file paths.
        """
        logger.info(f"Training models for file_id={self.file_id}, series length={len(self.daily_series)}")

        # ── 1. Feature engineering ────────────────────────────────────────────
        df_features = build_features(self.daily_series)
        df_features = df_features.dropna()   # drop rows with NaN lags

        if len(df_features) < 30:
            raise ValueError(
                f"Not enough data to train: need at least 30 rows after "
                f"feature engineering, got {len(df_features)}."
            )

        X = df_features[self.feature_cols].values
        y = df_features["revenue"].values

        # ── 2. Time-series train/test split ───────────────────────────────────
        # Use the last 20% of data as test set.
        # IMPORTANT: never shuffle time series data — that would leak the future.
        split_idx   = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        logger.debug(f"Train size: {len(X_train)}, Test size: {len(X_test)}")

        # ── 3. Scale features (helps Linear Regression, doesn't hurt RF) ──────
        scaler  = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s  = scaler.transform(X_test)

        # ── 4. Train both models ──────────────────────────────────────────────
        lr_model = LinearRegression()
        lr_model.fit(X_train_s, y_train)

        rf_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=8,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,        # use all CPU cores
        )
        rf_model.fit(X_train, y_train)   # RF doesn't need scaling

        # ── 5. Evaluate both models ───────────────────────────────────────────
        lr_preds = lr_model.predict(X_test_s)
        rf_preds = rf_model.predict(X_test)

        lr_metrics = self._compute_metrics("linear_regression", lr_preds, y_test, len(X_train), len(X_test))
        rf_metrics = self._compute_metrics("random_forest",     rf_preds, y_test, len(X_train), len(X_test))

        logger.info(f"Linear Regression  → MAE=${lr_metrics.mae:.2f}  R²={lr_metrics.r2_score:.3f}")
        logger.info(f"Random Forest      → MAE=${rf_metrics.mae:.2f}  R²={rf_metrics.r2_score:.3f}")

        # ── 6. Select the better model (higher R²) ────────────────────────────
        if rf_metrics.r2_score >= lr_metrics.r2_score:
            best_model, best_metrics = rf_model, rf_metrics
            use_scaler = False
            logger.info("✅ Selected: Random Forest")
        else:
            best_model, best_metrics = lr_model, lr_metrics
            use_scaler = True
            logger.info("✅ Selected: Linear Regression")

        # ── 7. Serialize to disk ──────────────────────────────────────────────
        model_path  = self._save_model(best_model, best_metrics.model_type)
        scaler_path = self._save_scaler(scaler if use_scaler else None)

        return TrainingResult(
            metrics=best_metrics,
            model_path=model_path,
            scaler_path=scaler_path,
            feature_names=self.feature_cols,
        )

    def _compute_metrics(
        self,
        model_type: str,
        predictions: np.ndarray,
        actuals: np.ndarray,
        n_train: int,
        n_test: int,
    ) -> TrainingMetrics:
        """Compute MAE, RMSE, and R² for a set of predictions."""
        # Clip negative predictions to 0 (revenue can't be negative)
        predictions = np.maximum(predictions, 0)

        mae  = float(mean_absolute_error(actuals, predictions))
        rmse = float(np.sqrt(mean_squared_error(actuals, predictions)))
        r2   = float(r2_score(actuals, predictions))

        return TrainingMetrics(
            model_type=model_type,
            mae=round(mae, 2),
            rmse=round(rmse, 2),
            r2_score=round(r2, 4),
            training_samples=n_train,
            test_samples=n_test,
        )

    def _save_model(self, model, model_type: str) -> Path:
        """Serialize the trained model to a .joblib file."""
        path = settings.model_dir_path / f"model_file{self.file_id}_{model_type}.joblib"
        joblib.dump(model, path)
        logger.info(f"Model saved to {path}")
        return path

    def _save_scaler(self, scaler) -> Path:
        """Serialize the feature scaler (None → save a None placeholder)."""
        path = settings.model_dir_path / f"scaler_file{self.file_id}.joblib"
        joblib.dump(scaler, path)
        return path
