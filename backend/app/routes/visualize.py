"""
routes/visualize.py — UPDATED: requires authentication.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db, User
from app.utils.security import get_current_user
from app.models.schemas import VisualizationResponse, ChartData
from app.services.upload_service import UploadService
from app.services.analytics_service import AnalyticsService
from app.services.visualization_service import VisualizationService

router = APIRouter()


def _get_viz(file_id: int, user_id: int, db: Session) -> VisualizationService:
    df = UploadService(db).load_dataframe(file_id, user_id=user_id)
    return VisualizationService(AnalyticsService(df))


@router.get("/visualize/{file_id}", response_model=VisualizationResponse)
def get_all_charts(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_viz(file_id, current_user.id, db).build_all(file_id)

@router.get("/visualize/{file_id}/trend", response_model=ChartData)
def get_trend(file_id: int, include_orders: bool = True, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_viz(file_id, current_user.id, db).revenue_trend_chart(include_orders)

@router.get("/visualize/{file_id}/products", response_model=ChartData)
def get_products(file_id: int, limit: int = Query(default=8, ge=1, le=20), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_viz(file_id, current_user.id, db).top_products_chart(limit)

@router.get("/visualize/{file_id}/category", response_model=ChartData)
def get_category(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_viz(file_id, current_user.id, db).category_pie_chart()

@router.get("/visualize/{file_id}/regions", response_model=ChartData)
def get_regions(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_viz(file_id, current_user.id, db).region_bar_chart()


@router.get("/visualize/{file_id}/weekly", response_model=ChartData)
def get_weekly_trend(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """More granular weekly revenue trend. Good for zoom-in dashboard view."""
    return _get_viz(file_id, current_user.id, db).weekly_trend_chart()


@router.get("/visualize/{file_id}/units", response_model=ChartData)
def get_units_chart(
    file_id: int,
    limit: int = Query(default=8, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Top products ranked by units sold (vs. revenue)."""
    return _get_viz(file_id, current_user.id, db).units_sold_chart(limit=limit)
