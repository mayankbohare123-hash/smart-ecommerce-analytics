"""
tests/test_upload.py
─────────────────────
Integration tests for the file upload API.

Run with:
    cd backend
    pytest tests/test_upload.py -v

Uses httpx's AsyncClient with the FastAPI app directly — no live server needed.
The test database is an in-memory SQLite instance (isolated per test session).
"""

import io
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import create_tables, drop_tables


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Create tables before tests, drop them after."""
    create_tables()
    yield
    drop_tables()


@pytest.fixture(scope="module")
def client():
    """Synchronous TestClient (simpler for upload tests)."""
    with TestClient(app) as c:
        yield c


def _make_csv_bytes(content: str) -> bytes:
    """Helper to turn a CSV string into bytes for multipart upload."""
    return content.strip().encode("utf-8")


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_CSV = """order_id,order_date,product,category,region,quantity,net_revenue
ORD001,2024-01-15,Headphones,Electronics,North,2,299.98
ORD002,2024-01-16,Keyboard,Electronics,South,1,89.99
ORD003,2024-02-01,Yoga Mat,Sports,East,3,119.97
ORD004,2024-02-14,Coffee Maker,Kitchen,West,1,149.99
ORD005,2024-03-05,Backpack,Accessories,Central,2,79.98
"""

MISSING_DATE_CSV = """product,category,revenue
Headphones,Electronics,299.98
Keyboard,Electronics,89.99
"""

MISSING_REVENUE_CSV = """order_date,product,category
2024-01-15,Headphones,Electronics
2024-01-16,Keyboard,Electronics
"""

EMPTY_CSV = "order_date,net_revenue\n"  # header only, no rows


# ── Tests: successful upload ──────────────────────────────────────────────────

class TestUploadSuccess:
    def test_upload_valid_csv(self, client):
        """A well-formed CSV should return 200 with file_id and row count."""
        response = client.post(
            "/api/upload",
            files={"file": ("sales.csv", io.BytesIO(_make_csv_bytes(VALID_CSV)), "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["file_id"] > 0
        assert data["row_count"] == 5
        assert data["column_count"] == 7
        assert "net_revenue" in data["columns"]
        assert "order_date" in data["columns"]

    def test_upload_returns_column_list(self, client):
        """Response must include the full column list from the uploaded file."""
        response = client.post(
            "/api/upload",
            files={"file": ("sales2.csv", io.BytesIO(_make_csv_bytes(VALID_CSV)), "text/csv")},
        )
        assert response.status_code == 200
        cols = response.json()["columns"]
        assert isinstance(cols, list)
        assert len(cols) == 7

    def test_upload_success_message_contains_filename(self, client):
        """The message field should mention the original filename."""
        response = client.post(
            "/api/upload",
            files={"file": ("my_sales_data.csv", io.BytesIO(_make_csv_bytes(VALID_CSV)), "text/csv")},
        )
        assert response.status_code == 200
        assert "my_sales_data.csv" in response.json()["message"]


# ── Tests: validation failures ────────────────────────────────────────────────

class TestUploadValidation:
    def test_upload_wrong_extension(self, client):
        """Non-CSV/XLSX files must be rejected with 400."""
        response = client.post(
            "/api/upload",
            files={"file": ("report.pdf", io.BytesIO(b"fake pdf content"), "application/pdf")},
        )
        assert response.status_code == 400

    def test_upload_empty_file(self, client):
        """Zero-byte files must be rejected with 400."""
        response = client.post(
            "/api/upload",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert response.status_code == 400

    def test_upload_missing_date_column(self, client):
        """CSV without a recognizable date column must return 422."""
        response = client.post(
            "/api/upload",
            files={"file": ("no_date.csv", io.BytesIO(_make_csv_bytes(MISSING_DATE_CSV)), "text/csv")},
        )
        assert response.status_code == 422

    def test_upload_missing_revenue_column(self, client):
        """CSV without a recognizable revenue column must return 422."""
        response = client.post(
            "/api/upload",
            files={"file": ("no_rev.csv", io.BytesIO(_make_csv_bytes(MISSING_REVENUE_CSV)), "text/csv")},
        )
        assert response.status_code == 422

    def test_upload_header_only_csv(self, client):
        """CSV with header row but no data must return 422."""
        response = client.post(
            "/api/upload",
            files={"file": ("empty_data.csv", io.BytesIO(_make_csv_bytes(EMPTY_CSV)), "text/csv")},
        )
        assert response.status_code == 422


# ── Tests: file management endpoints ─────────────────────────────────────────

class TestFileManagement:
    @pytest.fixture(autouse=True)
    def uploaded_file_id(self, client):
        """Upload a file once and store its ID for use in all tests in this class."""
        response = client.post(
            "/api/upload",
            files={"file": ("test_mgmt.csv", io.BytesIO(_make_csv_bytes(VALID_CSV)), "text/csv")},
        )
        assert response.status_code == 200
        self.file_id = response.json()["file_id"]

    def test_list_files_returns_array(self, client):
        """GET /files should return a JSON array."""
        response = client.get("/api/upload/files")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_file_by_id(self, client):
        """GET /files/{id} should return the file's metadata."""
        response = client.get(f"/api/upload/files/{self.file_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == self.file_id
        assert data["status"] == "processed"

    def test_get_nonexistent_file(self, client):
        """GET /files/99999 should return 404."""
        response = client.get("/api/upload/files/99999")
        assert response.status_code == 404

    def test_preview_returns_rows(self, client):
        """GET /preview/{id}?rows=3 should return exactly 3 rows."""
        response = client.get(f"/api/upload/preview/{self.file_id}?rows=3")
        assert response.status_code == 200
        data = response.json()
        assert data["preview_rows"] == 3
        assert data["total_rows"] == 5
        assert len(data["data"]) == 3

    def test_validate_endpoint(self, client):
        """GET /validate/{id} should confirm the file is valid."""
        response = client.get(f"/api/upload/validate/{self.file_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert "order_date" in data["detected_mapping"]
        assert "net_revenue" in data["detected_mapping"]

    def test_delete_file(self, client):
        """DELETE /files/{id} should succeed and make the file unfetchable."""
        del_response = client.delete(f"/api/upload/files/{self.file_id}")
        assert del_response.status_code == 200
        assert del_response.json()["success"] is True

        # Confirm it's gone
        get_response = client.get(f"/api/upload/files/{self.file_id}")
        assert get_response.status_code == 404


# ── Tests: health / root ──────────────────────────────────────────────────────

class TestHealthEndpoints:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "name" in response.json()
