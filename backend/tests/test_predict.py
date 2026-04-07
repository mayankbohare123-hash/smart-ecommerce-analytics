"""
tests/test_predict.py
──────────────────────
Tests for the ML training, prediction, and HTTP endpoints.

Focuses on:
  - Feature engineering correctness
  - Model trains without error on realistic data
  - Predictions are in a sensible range (non-negative, not astronomically large)
  - Chart payload has correct structure
  - HTTP endpoints return expected shapes

Run with:
    cd backend
    pytest tests/test_predict.py -v
"""

import io
import json
import pytest
import numpy as np
import pandas as pd
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database import create_tables, drop_tables
from app.ml.train import build_features, get_feature_columns, ModelTrainer
from app.ml.predict import build_prediction_chart
from app.models.schemas import PredictionPoint


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_daily_series(n_days: int = 180, seed: int = 42) -> pd.Series:
    """
    Generate a realistic daily revenue series with trend + seasonality + noise.
    Used across multiple tests.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start="2023-01-01", periods=n_days, freq="D")

    trend      = np.linspace(500, 800, n_days)                     # upward trend
    seasonality = 100 * np.sin(np.arange(n_days) * 2 * np.pi / 7) # weekly cycle
    noise       = rng.normal(0, 50, n_days)

    revenue = np.maximum(trend + seasonality + noise, 0)
    return pd.Series(revenue, index=dates, name="revenue")


SAMPLE_CSV = """order_id,order_date,customer_id,product,category,region,quantity,net_revenue
""" + "\n".join(
    f"ORD{i:04d},{(date(2023,1,1) + timedelta(days=i % 180)).isoformat()},CUST{i%50:04d},"
    f"Product{i%10},Category{i%4},Region{i%3},{(i%5)+1},{round(100 + (i%200) * 1.5 + (i%7)*20, 2)}"
    for i in range(250)
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def daily_series() -> pd.Series:
    return make_daily_series(180)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    create_tables()
    yield
    drop_tables()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def uploaded_file_id(client):
    r = client.post(
        "/api/upload",
        files={"file": ("predict_test.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")},
    )
    assert r.status_code == 200, f"Upload failed: {r.json()}"
    return r.json()["file_id"]


# ── Unit tests: feature engineering ──────────────────────────────────────────

class TestFeatureEngineering:

    def test_feature_columns_count(self, daily_series):
        """build_features should produce all expected feature columns."""
        df = build_features(daily_series)
        expected = set(get_feature_columns())
        actual   = set(df.columns) - {"revenue"}
        assert expected.issubset(actual), f"Missing: {expected - actual}"

    def test_day_of_week_range(self, daily_series):
        df = build_features(daily_series)
        assert df["day_of_week"].between(0, 6).all()

    def test_month_range(self, daily_series):
        df = build_features(daily_series)
        assert df["month"].between(1, 12).all()

    def test_is_weekend_binary(self, daily_series):
        df = build_features(daily_series)
        assert set(df["is_weekend"].unique()).issubset({0, 1})

    def test_cyclical_encoding_in_range(self, daily_series):
        df = build_features(daily_series)
        assert df["month_sin"].between(-1.01, 1.01).all()
        assert df["month_cos"].between(-1.01, 1.01).all()

    def test_lag_1d_equals_previous_revenue(self, daily_series):
        df = build_features(daily_series).dropna()
        # lag_1d[i] should equal revenue[i-1]
        for idx in range(5, 10):
            expected = daily_series.iloc[idx - 1]
            actual   = df["lag_1d"].iloc[idx - 30]  # offset for NaN-dropped rows
            assert abs(expected - actual) < 0.01

    def test_trend_is_monotonic(self, daily_series):
        df = build_features(daily_series)
        assert (df["trend"].diff().dropna() == 1).all()

    def test_rolling_mean_7d_is_positive(self, daily_series):
        df = build_features(daily_series).dropna()
        assert (df["rolling_mean_7d"] >= 0).all()


# ── Unit tests: model training ────────────────────────────────────────────────

class TestModelTraining:

    def test_trainer_completes_without_error(self, daily_series, tmp_path, monkeypatch):
        """ModelTrainer.train() should complete and return a TrainingResult."""
        monkeypatch.setattr("app.config.settings.MODEL_DIR", str(tmp_path))
        monkeypatch.setattr("app.config.settings.model_dir_path",
                            property(lambda self: tmp_path))

        from app.config import settings
        settings.__dict__["model_dir_path"] = tmp_path   # direct patch

        trainer = ModelTrainer(daily_series, file_id=999)
        result  = trainer.train()

        assert result.metrics.mae > 0
        assert result.metrics.rmse > 0
        assert -1.0 <= result.metrics.r2_score <= 1.0
        assert result.metrics.training_samples > 0
        assert result.model_path.exists()

    def test_trainer_model_type_is_valid(self, daily_series, tmp_path, monkeypatch):
        from app.config import settings
        settings.__dict__["model_dir_path"] = tmp_path
        trainer = ModelTrainer(daily_series, file_id=998)
        result  = trainer.train()
        assert result.metrics.model_type in ("random_forest", "linear_regression")

    def test_trainer_rejects_short_series(self, tmp_path, monkeypatch):
        from app.config import settings
        settings.__dict__["model_dir_path"] = tmp_path
        short_series = make_daily_series(10)   # too short
        trainer = ModelTrainer(short_series, file_id=997)
        with pytest.raises(ValueError, match="Not enough data"):
            trainer.train()


# ── Unit tests: prediction / chart ───────────────────────────────────────────

class TestPrediction:

    def test_prediction_chart_structure(self, daily_series):
        """build_prediction_chart should return 4 datasets."""
        fake_predictions = [
            PredictionPoint(
                date=(pd.Timestamp("2023-07-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
                predicted_revenue=float(600 + i * 2),
                lower_bound=float(500 + i * 2),
                upper_bound=float(700 + i * 2),
            )
            for i in range(30)
        ]
        chart = build_prediction_chart(daily_series, fake_predictions, history_days=60)

        assert len(chart.labels) == 60 + 30        # 60 history + 30 forecast
        assert len(chart.datasets) == 4
        for ds in chart.datasets:
            assert len(ds.data) == len(chart.labels)

    def test_prediction_chart_historical_dataset_non_null_in_history(self, daily_series):
        """The first dataset (historical) should have non-None values for history days."""
        preds = [
            PredictionPoint(date="2023-07-01", predicted_revenue=600, lower_bound=500, upper_bound=700)
        ]
        chart = build_prediction_chart(daily_series, preds, history_days=30)
        hist_data = chart.datasets[0].data
        # First 30 values = historical, should be non-None
        assert all(v is not None for v in hist_data[:30])
        # Last 1 value = None (forecast padding)
        assert hist_data[-1] is None


# ── Integration tests: HTTP endpoints ─────────────────────────────────────────

class TestPredictEndpoints:

    def test_predict_returns_200(self, client, uploaded_file_id):
        r = client.get(f"/api/predict/{uploaded_file_id}")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"

    def test_predict_response_structure(self, client, uploaded_file_id):
        r = client.get(f"/api/predict/{uploaded_file_id}")
        data = r.json()
        assert "predictions" in data
        assert "model_metrics" in data
        assert "chart_data" in data
        assert "prediction_days" in data

    def test_predict_predictions_non_empty(self, client, uploaded_file_id):
        r = client.get(f"/api/predict/{uploaded_file_id}")
        preds = r.json()["predictions"]
        assert len(preds) > 0

    def test_predict_predictions_non_negative(self, client, uploaded_file_id):
        r = client.get(f"/api/predict/{uploaded_file_id}")
        for p in r.json()["predictions"]:
            assert p["predicted_revenue"] >= 0
            assert p["lower_bound"] >= 0
            assert p["upper_bound"] >= p["predicted_revenue"]

    def test_predict_model_metrics_valid(self, client, uploaded_file_id):
        r = client.get(f"/api/predict/{uploaded_file_id}")
        metrics = r.json()["model_metrics"]
        assert metrics["mae"] > 0
        assert metrics["r2_score"] <= 1.0
        assert metrics["model_type"] in ("random_forest", "linear_regression")

    def test_predict_chart_has_four_datasets(self, client, uploaded_file_id):
        r = client.get(f"/api/predict/{uploaded_file_id}")
        datasets = r.json()["chart_data"]["datasets"]
        assert len(datasets) == 4

    def test_cached_predict_returns_same_count(self, client, uploaded_file_id):
        """Second call should return cached results with same number of predictions."""
        r1 = client.get(f"/api/predict/{uploaded_file_id}")
        r2 = client.get(f"/api/predict/{uploaded_file_id}")
        assert len(r1.json()["predictions"]) == len(r2.json()["predictions"])

    def test_metrics_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/predict/{uploaded_file_id}/metrics")
        assert r.status_code == 200
        assert "model_metrics" in r.json()

    def test_chart_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/predict/{uploaded_file_id}/chart")
        assert r.status_code == 200
        assert "chart_data" in r.json()

    def test_predict_404_for_missing_file(self, client):
        r = client.get("/api/predict/99999")
        assert r.status_code == 404
