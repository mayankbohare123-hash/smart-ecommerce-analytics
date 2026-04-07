"""
tests/test_visualize.py
────────────────────────
Tests for the visualization service and HTTP endpoints.

Validates that every chart payload has the correct Chart.js
structure: labels list, datasets list, each dataset has label + data.

Run with:
    cd backend
    pytest tests/test_visualize.py -v
"""

import io
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.database import create_tables, drop_tables
from app.services.analytics_service import AnalyticsService
from app.services.visualization_service import VisualizationService


# ── Sample data ───────────────────────────────────────────────────────────────

SAMPLE_CSV = """order_id,order_date,customer_id,product,category,region,quantity,net_revenue
ORD001,2024-01-10,CUST001,Headphones,Electronics,North,2,299.98
ORD002,2024-01-15,CUST002,Keyboard,Electronics,South,1,89.99
ORD003,2024-02-05,CUST003,Coffee Maker,Kitchen,West,1,149.99
ORD004,2024-02-10,CUST004,Headphones,Electronics,North,1,149.99
ORD005,2024-02-20,CUST002,Backpack,Accessories,East,2,79.98
ORD006,2024-03-01,CUST005,Yoga Mat,Sports,East,3,149.97
ORD007,2024-03-15,CUST003,Keyboard,Electronics,West,2,179.98
ORD008,2024-03-20,CUST001,Coffee Maker,Kitchen,North,1,129.99
"""


@pytest.fixture(scope="module")
def viz_service() -> VisualizationService:
    df = pd.read_csv(io.StringIO(SAMPLE_CSV))
    return VisualizationService(AnalyticsService(df))


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
        files={"file": ("viz_test.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")},
    )
    assert r.status_code == 200
    return r.json()["file_id"]


# ── Helper ────────────────────────────────────────────────────────────────────

def assert_chart_structure(chart: dict):
    """Assert that a chart dict has the expected Chart.js structure."""
    assert "labels" in chart, "Chart missing 'labels'"
    assert "datasets" in chart, "Chart missing 'datasets'"
    assert isinstance(chart["labels"], list), "'labels' must be a list"
    assert isinstance(chart["datasets"], list), "'datasets' must be a list"
    assert len(chart["datasets"]) > 0, "Chart must have at least one dataset"
    for ds in chart["datasets"]:
        assert "label" in ds, "Dataset missing 'label'"
        assert "data" in ds, "Dataset missing 'data'"
        assert isinstance(ds["data"], list), "Dataset 'data' must be a list"
        assert len(ds["data"]) == len(chart["labels"]), \
            "Dataset length must match labels length"


# ── Unit tests: VisualizationService ─────────────────────────────────────────

class TestVisualizationService:

    def test_revenue_trend_has_two_datasets(self, viz_service):
        chart = viz_service.revenue_trend_chart(include_orders=True)
        assert len(chart.datasets) == 2

    def test_revenue_trend_single_dataset(self, viz_service):
        chart = viz_service.revenue_trend_chart(include_orders=False)
        assert len(chart.datasets) == 1
        assert "Revenue" in chart.datasets[0].label

    def test_revenue_trend_labels_are_year_month(self, viz_service):
        chart = viz_service.revenue_trend_chart()
        for label in chart.labels:
            # Should be "YYYY-M" format from Period
            parts = label.split("-")
            assert len(parts) == 2
            assert parts[0].isdigit() and parts[1].isdigit()

    def test_revenue_trend_data_length_matches_labels(self, viz_service):
        chart = viz_service.revenue_trend_chart()
        for ds in chart.datasets:
            assert len(ds.data) == len(chart.labels)

    def test_revenue_trend_values_are_positive(self, viz_service):
        chart = viz_service.revenue_trend_chart()
        revenue_ds = chart.datasets[0]
        assert all(v >= 0 for v in revenue_ds.data)

    def test_top_products_limit(self, viz_service):
        chart = viz_service.top_products_chart(limit=3)
        assert len(chart.labels) <= 3
        assert len(chart.datasets[0].data) <= 3

    def test_top_products_sorted_by_revenue(self, viz_service):
        chart = viz_service.top_products_chart(limit=10)
        data = chart.datasets[0].data
        assert data == sorted(data, reverse=True)

    def test_top_products_has_colors(self, viz_service):
        chart = viz_service.top_products_chart()
        ds = chart.datasets[0]
        assert ds.backgroundColor is not None
        assert isinstance(ds.backgroundColor, list)
        assert len(ds.backgroundColor) == len(chart.labels)

    def test_category_pie_has_one_dataset(self, viz_service):
        chart = viz_service.category_pie_chart()
        assert len(chart.datasets) == 1

    def test_category_pie_labels_match_data_length(self, viz_service):
        chart = viz_service.category_pie_chart()
        assert len(chart.labels) == len(chart.datasets[0].data)

    def test_category_pie_includes_electronics(self, viz_service):
        chart = viz_service.category_pie_chart()
        assert "Electronics" in chart.labels

    def test_region_bar_has_two_datasets(self, viz_service):
        """Region chart has revenue + orders datasets."""
        chart = viz_service.region_bar_chart()
        assert len(chart.datasets) == 2

    def test_region_bar_sorted_by_revenue(self, viz_service):
        chart = viz_service.region_bar_chart()
        revenue_data = chart.datasets[0].data
        assert revenue_data == sorted(revenue_data, reverse=True)

    def test_weekly_trend_has_weekly_labels(self, viz_service):
        chart = viz_service.weekly_trend_chart()
        # Weekly labels should be date strings
        assert len(chart.labels) > 0
        for label in chart.labels[:3]:
            assert len(label) == 10  # "YYYY-MM-DD"

    def test_units_sold_chart_has_data(self, viz_service):
        chart = viz_service.units_sold_chart(limit=5)
        assert len(chart.labels) <= 5
        assert all(v >= 0 for v in chart.datasets[0].data)

    def test_build_all_contains_four_charts(self, viz_service):
        result = viz_service.build_all(file_id=42)
        assert result.file_id == 42
        assert result.revenue_trend is not None
        assert result.top_products is not None
        assert result.category_pie is not None
        assert result.region_bar is not None


# ── Integration tests: HTTP endpoints ─────────────────────────────────────────

class TestVisualizationEndpoints:

    def test_all_charts_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/visualize/{uploaded_file_id}")
        assert r.status_code == 200
        data = r.json()
        assert "revenue_trend" in data
        assert "top_products" in data
        assert "category_pie" in data
        assert "region_bar" in data

    def test_all_charts_have_correct_structure(self, client, uploaded_file_id):
        r = client.get(f"/api/visualize/{uploaded_file_id}")
        assert r.status_code == 200
        data = r.json()
        for chart_key in ("revenue_trend", "top_products", "category_pie", "region_bar"):
            assert_chart_structure(data[chart_key])

    def test_trend_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/visualize/{uploaded_file_id}/trend")
        assert r.status_code == 200
        assert_chart_structure(r.json())

    def test_trend_without_orders(self, client, uploaded_file_id):
        r = client.get(f"/api/visualize/{uploaded_file_id}/trend?include_orders=false")
        assert r.status_code == 200
        data = r.json()
        assert len(data["datasets"]) == 1

    def test_products_endpoint_with_limit(self, client, uploaded_file_id):
        r = client.get(f"/api/visualize/{uploaded_file_id}/products?limit=3")
        assert r.status_code == 200
        data = r.json()
        assert len(data["labels"]) <= 3

    def test_category_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/visualize/{uploaded_file_id}/category")
        assert r.status_code == 200
        assert_chart_structure(r.json())

    def test_regions_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/visualize/{uploaded_file_id}/regions")
        assert r.status_code == 200
        data = r.json()
        assert len(data["datasets"]) == 2  # revenue + orders

    def test_weekly_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/visualize/{uploaded_file_id}/weekly")
        assert r.status_code == 200
        assert_chart_structure(r.json())

    def test_units_endpoint(self, client, uploaded_file_id):
        r = client.get(f"/api/visualize/{uploaded_file_id}/units")
        assert r.status_code == 200
        assert_chart_structure(r.json())

    def test_visualize_404_for_missing_file(self, client):
        r = client.get("/api/visualize/99999")
        assert r.status_code == 404
