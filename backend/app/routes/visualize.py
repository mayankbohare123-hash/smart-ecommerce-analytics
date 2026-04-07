"""
routes/visualize.py
────────────────────
HTTP endpoints that return Chart.js-ready JSON for every dashboard chart.

Endpoints:
  GET /api/visualize/{file_id}          — All 4 charts in one payload
  GET /api/visualize/{file_id}/trend    — Revenue & orders line chart
  GET /api/visualize/{file_id}/products — Top products horizontal bar
  GET /api/visualize/{file_id}/category — Category doughnut chart
  GET /api/visualize/{file_id}/regions  — Region horizontal bar chart
  GET /api/visualize/{file_id}/weekly   — Weekly trend line chart
  GET /api/visualize/{file_id}/units    — Top products by units sold

Each response is a ChartData object ready to drop into Chart.js:
    new Chart(ctx, { type: 'line', data: response })
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import VisualizationResponse, ChartData, ErrorResponse
from app.services.upload_service import UploadService
from app.services.analytics_service import AnalyticsService
from app.services.visualization_service import VisualizationService

router = APIRouter()


def _get_viz_service(file_id: int, db: Session) -> VisualizationService:
    """Shared dep: load DataFrame → AnalyticsService → VisualizationService."""
    df = UploadService(db).load_dataframe(file_id)
    return VisualizationService(AnalyticsService(df))


@router.get(
    "/visualize/{file_id}",
    response_model=VisualizationResponse,
    summary="All chart data in one payload",
    responses={404: {"model": ErrorResponse}},
)
def get_all_charts(file_id: int, db: Session = Depends(get_db)):
    """
    Returns all 4 chart payloads in a single response.
    Preferred by the frontend dashboard to minimize round trips.

    **Postman:** GET http://localhost:8000/api/visualize/1
    """
    return _get_viz_service(file_id, db).build_all(file_id)


@router.get(
    "/visualize/{file_id}/trend",
    response_model=ChartData,
    summary="Monthly revenue & orders line chart",
    responses={404: {"model": ErrorResponse}},
)
def get_revenue_trend(
    file_id: int,
    include_orders: bool = Query(default=True, description="Include order count dataset"),
    db: Session = Depends(get_db),
):
    """
    Monthly revenue trend line chart data.
    Pass include_orders=false for a single-dataset chart.

    **Postman:** GET http://localhost:8000/api/visualize/1/trend
    """
    svc = _get_viz_service(file_id, db)
    return svc.revenue_trend_chart(include_orders=include_orders)


@router.get(
    "/visualize/{file_id}/products",
    response_model=ChartData,
    summary="Top products horizontal bar chart",
    responses={404: {"model": ErrorResponse}},
)
def get_products_chart(
    file_id: int,
    limit: int = Query(default=8, ge=1, le=20, description="Number of products"),
    db: Session = Depends(get_db),
):
    """
    Top N products by revenue, formatted for a horizontal bar chart.

    **Postman:** GET http://localhost:8000/api/visualize/1/products?limit=5
    """
    svc = _get_viz_service(file_id, db)
    return svc.top_products_chart(limit=limit)


@router.get(
    "/visualize/{file_id}/category",
    response_model=ChartData,
    summary="Category revenue doughnut chart",
    responses={404: {"model": ErrorResponse}},
)
def get_category_chart(file_id: int, db: Session = Depends(get_db)):
    """
    Product category revenue breakdown for a doughnut/pie chart.

    **Postman:** GET http://localhost:8000/api/visualize/1/category
    """
    return _get_viz_service(file_id, db).category_pie_chart()


@router.get(
    "/visualize/{file_id}/regions",
    response_model=ChartData,
    summary="Regional sales bar chart",
    responses={404: {"model": ErrorResponse}},
)
def get_regions_chart(file_id: int, db: Session = Depends(get_db)):
    """
    Revenue and orders by region for a grouped horizontal bar chart.

    **Postman:** GET http://localhost:8000/api/visualize/1/regions
    """
    return _get_viz_service(file_id, db).region_bar_chart()


@router.get(
    "/visualize/{file_id}/weekly",
    response_model=ChartData,
    summary="Weekly revenue trend line chart",
    responses={404: {"model": ErrorResponse}},
)
def get_weekly_trend(file_id: int, db: Session = Depends(get_db)):
    """
    More granular weekly revenue trend. Good for zoom-in dashboard view.

    **Postman:** GET http://localhost:8000/api/visualize/1/weekly
    """
    return _get_viz_service(file_id, db).weekly_trend_chart()


@router.get(
    "/visualize/{file_id}/units",
    response_model=ChartData,
    summary="Top products by units sold",
    responses={404: {"model": ErrorResponse}},
)
def get_units_chart(
    file_id: int,
    limit: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Top products ranked by units sold (vs. revenue).
    Highlights volume leaders that may differ from revenue leaders.

    **Postman:** GET http://localhost:8000/api/visualize/1/units
    """
    return _get_viz_service(file_id, db).units_sold_chart(limit=limit)
