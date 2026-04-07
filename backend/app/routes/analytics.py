"""
routes/analytics.py
────────────────────
HTTP endpoints for sales analytics.

Endpoints:
  GET /api/analytics/{file_id}          — Full analytics payload
  GET /api/analytics/{file_id}/kpis     — KPI metrics only
  GET /api/analytics/{file_id}/monthly  — Monthly sales time series
  GET /api/analytics/{file_id}/products — Top products ranking
  GET /api/analytics/{file_id}/regions  — Regional breakdown
  GET /api/analytics/{file_id}/summary  — Lightweight text summary

All heavy logic lives in AnalyticsService. Routes stay thin.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import AnalyticsResponse, ErrorResponse
from app.services.upload_service import UploadService
from app.services.analytics_service import AnalyticsService

router = APIRouter()


def _get_analytics(file_id: int, db: Session) -> AnalyticsService:
    """
    Shared dependency: load the DataFrame for a file and
    return a ready-to-use AnalyticsService instance.
    """
    upload_svc = UploadService(db)
    df = upload_svc.load_dataframe(file_id)
    return AnalyticsService(df)


@router.get(
    "/analytics/{file_id}",
    response_model=AnalyticsResponse,
    summary="Full analytics for an uploaded file",
    responses={404: {"model": ErrorResponse}},
)
def get_full_analytics(file_id: int, db: Session = Depends(get_db)):
    """
    Returns the complete analytics payload in one call:
    KPIs, monthly trend, top products, regional & category breakdown.

    **Postman:** GET http://localhost:8000/api/analytics/1
    """
    svc = _get_analytics(file_id, db)
    return svc.compute_all(file_id)


@router.get(
    "/analytics/{file_id}/kpis",
    summary="KPI metrics only",
    responses={404: {"model": ErrorResponse}},
)
def get_kpis(file_id: int, db: Session = Depends(get_db)):
    """
    Lightweight endpoint — returns only the KPI card values.
    Useful for a quick dashboard refresh without reloading all charts.

    **Postman:** GET http://localhost:8000/api/analytics/1/kpis
    """
    svc = _get_analytics(file_id, db)
    return svc._compute_kpis()


@router.get(
    "/analytics/{file_id}/monthly",
    summary="Monthly revenue time series",
    responses={404: {"model": ErrorResponse}},
)
def get_monthly_sales(file_id: int, db: Session = Depends(get_db)):
    """
    Returns the month-by-month revenue and order count series.
    Ready to be plugged into a line chart.

    **Postman:** GET http://localhost:8000/api/analytics/1/monthly
    """
    svc = _get_analytics(file_id, db)
    return {"file_id": file_id, "monthly_sales": svc._monthly_sales()}


@router.get(
    "/analytics/{file_id}/products",
    summary="Top products by revenue",
    responses={404: {"model": ErrorResponse}},
)
def get_top_products(
    file_id: int,
    limit: int = Query(default=10, ge=1, le=50, description="How many products to return"),
    db: Session = Depends(get_db),
):
    """
    Returns the top N products ranked by total revenue.

    **Postman:** GET http://localhost:8000/api/analytics/1/products?limit=5
    """
    svc = _get_analytics(file_id, db)
    return {"file_id": file_id, "top_products": svc._top_products(limit=limit)}


@router.get(
    "/analytics/{file_id}/regions",
    summary="Sales breakdown by region",
    responses={404: {"model": ErrorResponse}},
)
def get_region_sales(file_id: int, db: Session = Depends(get_db)):
    """
    Returns revenue, orders, and % share for each region.

    **Postman:** GET http://localhost:8000/api/analytics/1/regions
    """
    svc = _get_analytics(file_id, db)
    return {"file_id": file_id, "region_sales": svc._region_sales()}


@router.get(
    "/analytics/{file_id}/summary",
    summary="Human-readable text summary",
    responses={404: {"model": ErrorResponse}},
)
def get_summary(file_id: int, db: Session = Depends(get_db)):
    """
    Returns a short natural-language summary of the sales data.
    Useful for a dashboard header or quick export.

    **Postman:** GET http://localhost:8000/api/analytics/1/summary
    """
    svc = _get_analytics(file_id, db)
    kpis    = svc._compute_kpis()
    monthly = svc._monthly_sales()

    date_range = (
        f"{monthly[0].month} to {monthly[-1].month}"
        if monthly else "N/A"
    )

    growth_text = (
        f"Revenue {'grew' if kpis.revenue_growth and kpis.revenue_growth > 0 else 'declined'} "
        f"{abs(kpis.revenue_growth):.1f}% month-over-month."
        if kpis.revenue_growth is not None else ""
    )

    return {
        "file_id": file_id,
        "summary": (
            f"Dataset covers {date_range} with {kpis.total_orders:,} orders "
            f"generating ${kpis.total_revenue:,.2f} in revenue. "
            f"Average order value is ${kpis.avg_order_value:,.2f}. "
            f"Top product: {kpis.top_product}. "
            f"Strongest region: {kpis.top_region}. "
            f"{growth_text}"
        ),
        "kpis": kpis,
    }
