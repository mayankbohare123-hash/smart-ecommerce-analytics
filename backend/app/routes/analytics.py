"""
routes/analytics.py — UPDATED: requires authentication, filters by user.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db, User
from app.utils.security import get_current_user
from app.models.schemas import AnalyticsResponse, ErrorResponse
from app.services.upload_service import UploadService
from app.services.analytics_service import AnalyticsService

router = APIRouter()


def _get_analytics(file_id: int, user_id: int, db: Session) -> AnalyticsService:
    df = UploadService(db).load_dataframe(file_id, user_id=user_id)
    return AnalyticsService(df)


@router.get("/analytics/{file_id}", response_model=AnalyticsResponse)
def get_full_analytics(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_analytics(file_id, current_user.id, db).compute_all(file_id)


@router.get("/analytics/{file_id}/kpis")
def get_kpis(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_analytics(file_id, current_user.id, db)._compute_kpis()


@router.get("/analytics/{file_id}/monthly")
def get_monthly_sales(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = _get_analytics(file_id, current_user.id, db)
    return {"file_id": file_id, "monthly_sales": svc._monthly_sales()}


@router.get("/analytics/{file_id}/products")
def get_top_products(
    file_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = _get_analytics(file_id, current_user.id, db)
    return {"file_id": file_id, "top_products": svc._top_products(limit=limit)}


@router.get("/analytics/{file_id}/regions")
def get_region_sales(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = _get_analytics(file_id, current_user.id, db)
    return {"file_id": file_id, "region_sales": svc._region_sales()}


@router.get("/analytics/{file_id}/summary")
def get_summary(file_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc     = _get_analytics(file_id, current_user.id, db)
    kpis    = svc._compute_kpis()
    monthly = svc._monthly_sales()
    date_range = f"{monthly[0].month} to {monthly[-1].month}" if monthly else "N/A"
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
            f"Top product: {kpis.top_product}. Strongest region: {kpis.top_region}. {growth_text}"
        ),
        "kpis": kpis,
    }
