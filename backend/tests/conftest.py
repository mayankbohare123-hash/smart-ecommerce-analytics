"""
tests/conftest.py
─────────────────
Shared pytest setup for the whole suite.

1. ISOLATION — points the app at a throwaway SQLite file and temp upload /
   model folders BEFORE the app is imported. Without this, tests run against
   your real dev database and `drop_tables()` at the end of each test module
   would wipe your user accounts.

2. AUTH — since Step 1 every data endpoint needs a logged-in user. The
   upload / analytics / visualize / predict tests are about those features,
   not about login, so they run as a "pro" test user via a FastAPI dependency
   override. Test modules that exercise real authentication or billing opt out
   with:   pytestmark = pytest.mark.real_auth
"""

import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="salesiq_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")
os.environ["MODEL_DIR"] = os.path.join(_TMP, "models")
os.environ["DEBUG"] = "False"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production"

import pytest  # noqa: E402

from app.main import app  # noqa: E402
from app.database import User  # noqa: E402
from app.utils.security import get_current_user  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "real_auth: run without the authenticated-test-user override"
    )


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)


def _test_user() -> User:
    # Transient (never persisted) pro-plan user: unlimited uploads for feature tests.
    return User(id=1, email="tester@example.com", name="Test User",
                hashed_password="x", plan="pro", is_active=True, upload_count=0)


@pytest.fixture(scope="module", autouse=True)
def _auth_override(request):
    """Module scope so module-level fixtures (which upload files) are authenticated too."""
    marks = getattr(request.module, "pytestmark", [])
    marks = marks if isinstance(marks, (list, tuple)) else [marks]
    if any(getattr(m, "name", "") == "real_auth" for m in marks):
        app.dependency_overrides.pop(get_current_user, None)
    else:
        app.dependency_overrides[get_current_user] = _test_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
