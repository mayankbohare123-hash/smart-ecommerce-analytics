"""
models/schemas.py
─────────────────
Pydantic schemas for all API request and response bodies.

Pydantic validates incoming data automatically and serializes
outgoing data cleanly. Using separate schemas from DB models
keeps the API contract stable independently of the DB schema.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime


# ── Upload schemas ────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Returned after a successful file upload."""
    success: bool
    file_id: int
    filename: str
    row_count: int
    column_count: int
    columns: List[str]
    message: str

    class Config:
        from_attributes = True  # allow ORM objects to be passed directly


class FileListItem(BaseModel):
    """Summary of a single uploaded file (used in file listings)."""
    id: int
    filename: str
    original_name: str
    row_count: Optional[int]
    status: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


# ── Analytics schemas ─────────────────────────────────────────────────────────

class KPIMetrics(BaseModel):
    """Top-level KPI cards shown on the dashboard."""
    total_revenue: float = Field(..., description="Sum of all sales")
    total_orders: int    = Field(..., description="Total number of orders")
    avg_order_value: float = Field(..., description="Revenue / Orders")
    unique_customers: int
    top_product: str
    top_region: str
    revenue_growth: Optional[float] = Field(None, description="MoM % growth")


class MonthlySales(BaseModel):
    """One data point in the monthly revenue time series."""
    month: str           # e.g. "2024-01"
    revenue: float
    orders: int


class TopProduct(BaseModel):
    """A single product entry in the top-products ranking."""
    product: str
    revenue: float
    units_sold: int
    rank: int


class RegionSales(BaseModel):
    """Sales breakdown by geographic region."""
    region: str
    revenue: float
    orders: int
    percentage: float    # share of total revenue


class CategorySales(BaseModel):
    """Sales breakdown by product category."""
    category: str
    revenue: float
    units_sold: int


class AnalyticsResponse(BaseModel):
    """Full analytics payload returned by /api/analytics/{file_id}."""
    file_id: int
    kpis: KPIMetrics
    monthly_sales: List[MonthlySales]
    top_products: List[TopProduct]
    region_sales: List[RegionSales]
    category_sales: List[CategorySales]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Visualization schemas ─────────────────────────────────────────────────────

class ChartDataset(BaseModel):
    """A single dataset in a Chart.js chart."""
    label: str
    data: List[float]
    backgroundColor: Optional[Any] = None   # string or list
    borderColor: Optional[str] = None
    borderWidth: Optional[int] = 2
    fill: Optional[bool] = False
    tension: Optional[float] = 0.4          # line chart curve


class ChartData(BaseModel):
    """Chart.js-compatible data structure."""
    labels: List[str]
    datasets: List[ChartDataset]


class VisualizationResponse(BaseModel):
    """All chart data for the frontend in one response."""
    file_id: int
    revenue_trend: ChartData    # line chart
    top_products: ChartData     # bar chart
    category_pie: ChartData     # doughnut / pie
    region_bar: ChartData       # horizontal bar


# ── Prediction schemas ────────────────────────────────────────────────────────

class PredictionPoint(BaseModel):
    """A single forecasted data point."""
    date: str            # ISO date string "YYYY-MM-DD"
    predicted_revenue: float
    lower_bound: float   # confidence interval
    upper_bound: float


class ModelMetrics(BaseModel):
    """ML model performance metrics."""
    model_type: str
    mae: float           # Mean Absolute Error
    rmse: float          # Root Mean Square Error
    r2_score: float
    training_samples: int


class PredictionResponse(BaseModel):
    """Full prediction payload returned by /api/predict/{file_id}."""
    file_id: int
    predictions: List[PredictionPoint]
    model_metrics: ModelMetrics
    prediction_days: int
    chart_data: ChartData     # combined historical + forecast for the chart
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Error schema ──────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standardized error response body."""
    success: bool = False
    error: str
    detail: Optional[str] = None
    status_code: int
