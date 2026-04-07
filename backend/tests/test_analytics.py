"""
tests/test_analytics.py
────────────────────────
Unit + integration tests for the analytics service and routes.

Tests run against the real sample_sales.csv to validate
that the analytics engine produces sensible numbers.

Run with:
    cd backend
    pytest tests/test_analytics.py -v
"""

import io
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.database import create_tables, drop_tables
from app.services.analytics_service import AnalyticsService


# ── Sample DataFrame used in unit tests ──────────────────────────────────────

SAMPLE_CSV = """order_id,order_date,customer_id,product,category,region,quantity,net_revenue
ORD001,2024-01-10,CUST001,Headphones,Electronics,North,2,299.98
ORD002,2024-01-15,CUST002,Keyboard,Electronics,South,1,89.99
ORD003,2024-01-20,CUST001,Yoga Mat,Sports,East,1,49.99
ORD004,2024-02-05,CUST003,Coffee Maker,Kitchen,West,1,149.99
ORD005,2024-02-10,CUST004,Headphones,Electronics,North,1,149.99
ORD006,2024-02-20,CUST002,Backpack,Accessories,South,2,79.98
ORD007,2024-03-01,CUST005,Yoga Mat,Sports,East,3,149.97
ORD008,2024-03-15,CUST003,Keyboard,Electronics,West,2,179.98
"""


@pytest.fixture(scope="module")
def sample_df() -> pd.DataFrame:
    return pd.read_csv(io.StringIO(SAMPLE_CSV))


@pytest.fixture(scope="module")
def analytics(sample_df) -> AnalyticsService:
    return AnalyticsService(sample_df)


# ── Fixtures ──────────────────────────────────────────────────────────────────

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
    """Upload the sample CSV once and reuse its ID across all integration tests."""
    with open("../data/sample_sales.csv", "rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": ("sample_sales.csv", f, "text/csv")},
        )
    if response.status_code != 200:
        # Fallback: upload inline sample
        response = client.post(
            "/api/upload",
            files={"file": ("test.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")},
        )
    assert response.status_code == 200
    return response.json()["file_id"]


# ── Unit tests: AnalyticsService ──────────────────────────────────────────────

class TestAnalyticsServiceUnit:
    """Test AnalyticsService directly with a known DataFrame."""

    def test_total_revenue(self, analytics):
        kpis = analytics._compute_kpis()
        expected = round(299.98 + 89.99 + 49.99 + 149.99 + 149.99 + 79.98 + 149.97 + 179.98, 2)
        assert kpis.total_revenue == expected

    def test_total_orders(self, analytics):
        kpis = analytics._compute_kpis()
        assert kpis.total_orders == 8

    def test_avg_order_value(self, analytics):
        kpis = analytics._compute_kpis()
        expected = round(kpis.total_revenue / 8, 2)
        assert kpis.avg_order_value == expected

    def test_unique_customers(self, analytics):
        kpis = analytics._compute_kpis()
        assert kpis.unique_customers == 5  # CUST001 through CUST005

    def test_top_product_is_headphones(self, analytics):
        """Headphones appear twice with $299.98 + $149.99 = $449.97 — highest."""
        kpis = analytics._compute_kpis()
        assert kpis.top_product == "Headphones"

    def test_top_region_is_north(self, analytics):
        """North: $299.98 + $149.99 = $449.97 — highest region."""
        kpis = analytics._compute_kpis()
        assert kpis.top_region == "North"

    def test_monthly_sales_count(self, analytics):
        """Should have 3 months: Jan, Feb, March 2024."""
        monthly = analytics._monthly_sales()
        assert len(monthly) == 3

    def test_monthly_sales_sorted(self, analytics):
        """Monthly data must be in chronological order."""
        monthly = analytics._monthly_sales()
        months = [m.month for m in monthly]
        assert months == sorted(months)

    def test_monthly_january_revenue(self, analytics):
        monthly = analytics._monthly_sales()
        jan = next(m for m in monthly if "2024-01" in m.month)
        expected = round(299.98 + 89.99 + 49.99, 2)
        assert jan.revenue == expected

    def test_top_products_ranked(self, analytics):
        products = analytics._top_products(limit=5)
        assert products[0].rank == 1
        assert products[0].product == "Headphones"

    def test_top_products_limit(self, analytics):
        products = analytics._top_products(limit=3)
        assert len(products) == 3

    def test_region_sales_percentages_sum_to_100(self, analytics):
        regions = analytics._region_sales()
        total_pct = sum(r.percentage for r in regions)
        assert abs(total_pct - 100.0) < 0.5  # allow for rounding

    def test_category_sales_includes_electronics(self, analytics):
        categories = analytics._category_sales()
        cat_names = [c.category for c in categories]
        assert "Electronics" in cat_names

    def test_category_sales_sorted_by_revenue(self, analytics):
        categories = analytics._category_sales()
        revenues = [c.revenue for c in categories]
        assert revenues == sorted(revenues, reverse=True)

    def test_daily_revenue_series_is_indexed_by_date(self, analytics):
        series = analytics.daily_revenue_series()
        assert not series.empty
        assert hasattr(series.index, "date")

    def test_normalization_handles_unknown_columns(self):
        """DataFrame missing optional columns should still compute without error."""
        minimal_df = pd.DataFrame({
            "order_date": ["2024-01-01", "2024-01-02"],
            "net_revenue": [100.0, 200.0],
        })
        svc = AnalyticsService(minimal_df)
        kpis = svc._compute_kpis()
        assert kpis.total_revenue == 300.0
        assert kpis.top_product == "Unknown"

    def test_compute_all_returns_full_response(self, analytics):
        result = analytics.compute_all(file_id=99)
        assert result.file_id == 99
        assert result.kpis is not None
        assert len(result.monthly_sales) > 0
        assert len(result.top_products) > 0
        assert len(result.region_sales) > 0
        assert len(result.category_sales) > 0


# ── Integration tests: HTTP endpoints ─────────────────────────────────────────

class TestAnalyticsEndpoints:

    def test_full_analytics_200(self, client, uploaded_file_id):
        r = client.get(f"/api/analytics/{uploaded_file_id}")
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data
        assert "monthly_sales" in data
        assert "top_products" in data
        assert "region_sales" in data
        assert "category_sales" in data

    def test_kpis_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/analytics/{uploaded_file_id}/kpis")
        assert r.status_code == 200
        data = r.json()
        assert data["total_revenue"] > 0
        assert data["total_orders"] > 0
        assert data["avg_order_value"] > 0

    def test_monthly_endpoint_sorted(self, client, uploaded_file_id):
        r = client.get(f"/api/analytics/{uploaded_file_id}/monthly")
        assert r.status_code == 200
        months = [m["month"] for m in r.json()["monthly_sales"]]
        assert months == sorted(months)

    def test_products_limit_param(self, client, uploaded_file_id):
        r = client.get(f"/api/analytics/{uploaded_file_id}/products?limit=3")
        assert r.status_code == 200
        assert len(r.json()["top_products"]) <= 3

    def test_regions_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/analytics/{uploaded_file_id}/regions")
        assert r.status_code == 200
        regions = r.json()["region_sales"]
        assert len(regions) > 0
        assert all("percentage" in reg for reg in regions)

    def test_summary_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/analytics/{uploaded_file_id}/summary")
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert len(data["summary"]) > 20  # non-trivial string

    def test_analytics_404_for_missing_file(self, client):
        r = client.get("/api/analytics/99999")
        assert r.status_code == 404
