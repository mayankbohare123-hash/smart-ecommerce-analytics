"""
tests/test_admin.py — the founder's admin panel API.

Focus: who is allowed in, and the guard rails that stop an admin (or someone who
hijacked an admin session) from doing irreversible damage.
"""

import os
import time
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.database import (
    AdminAuditLog, BillingInvoice, SessionLocal, StripeEvent, UploadedFile, User, create_tables, drop_tables,
)
from app.main import app

pytestmark = pytest.mark.real_auth

CSV = ("order_id,order_date,product,category,region,quantity,net_revenue\n"
       "O1,2024-01-15,Headphones,Electronics,North,2,299.98\n"
       "O2,2024-01-16,Keyboard,Electronics,South,1,89.99\n")


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    create_tables()
    yield
    drop_tables()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def signup(client, *, name="Customer One", org=None, plan=None, **db_fields):
    email = f"u{uuid.uuid4().hex[:10]}@test.com"
    r = client.post("/api/auth/signup", json={"name": name, "email": email, "password": "password123",
                                              "organization": org})
    assert r.status_code == 200, r.text
    db = SessionLocal()
    row = db.query(User).filter(User.email == email).first()
    if plan:
        row.plan = plan
    for k, v in db_fields.items():
        setattr(row, k, v)
    db.commit()
    uid = row.id
    db.close()
    return SimpleNamespace(id=uid, email=email, headers={"Authorization": f"Bearer {r.json()['access_token']}"})


@pytest.fixture
def admin(client):
    return signup(client, name="Founder", role="admin")


@pytest.fixture
def customer(client):
    return signup(client, name="Regular Customer")


def upload(client, user, name="s.csv"):
    return client.post("/api/upload", files={"file": (name, CSV.encode(), "text/csv")}, headers=user.headers)


def live_sub(user_id, plan="starter"):
    """Give a user an active Stripe subscription (local mirror)."""
    db = SessionLocal()
    db.query(User).filter(User.id == user_id).update({
        "plan": plan, "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:8]}", "subscription_status": "active",
        "stripe_customer_id": f"cus_{uuid.uuid4().hex[:8]}"})
    db.commit(); db.close()


ADMIN_ROUTES = [
    ("get", "/api/admin/stats"), ("get", "/api/admin/users"), ("get", "/api/admin/users/1"),
    ("post", "/api/admin/users/1/suspend"), ("post", "/api/admin/users/1/restore"),
    ("put", "/api/admin/users/1/plan"), ("delete", "/api/admin/users/1"), ("get", "/api/admin/activity"),
]


class TestAccessControl:

    @pytest.mark.parametrize("method,url", ADMIN_ROUTES)
    def test_logged_out_visitors_get_401(self, client, method, url):
        assert getattr(client, method)(url).status_code == 401

    @pytest.mark.parametrize("method,url", ADMIN_ROUTES)
    def test_customers_get_403_even_with_a_valid_login(self, client, customer, method, url):
        kwargs = {"json": {"plan": "pro"}} if method == "put" else {}
        r = getattr(client, method)(url, headers=customer.headers, **kwargs)
        assert r.status_code == 403 and "Admin" in r.json()["detail"]

    def test_role_is_read_from_the_database_not_the_token(self, client, customer):
        assert client.get("/api/admin/stats", headers=customer.headers).status_code == 403
        db = SessionLocal(); db.query(User).filter(User.id == customer.id).update({"role": "admin"}); db.commit(); db.close()
        assert client.get("/api/admin/stats", headers=customer.headers).status_code == 200      # same token, now admin
        db = SessionLocal(); db.query(User).filter(User.id == customer.id).update({"role": "user"}); db.commit(); db.close()
        assert client.get("/api/admin/stats", headers=customer.headers).status_code == 403      # demotion is instant

    def test_admins_can_still_use_the_normal_app(self, client, admin):
        assert upload(client, admin).status_code == 200
        assert client.get("/api/billing/status", headers=admin.headers).status_code == 200


class TestStats:

    def test_counts_mrr_and_series(self, client, admin):
        before = client.get("/api/admin/stats", headers=admin.headers).json()
        s1 = signup(client); live_sub(s1.id, "starter")
        s2 = signup(client); live_sub(s2.id, "starter")
        p1 = signup(client); live_sub(p1.id, "pro")
        comped = signup(client, plan="pro")                       # pro WITHOUT a Stripe subscription
        after = client.get("/api/admin/stats", headers=admin.headers).json()

        assert after["total_users"] - before["total_users"] == 4
        assert after["paying_by_plan"]["starter"] - before["paying_by_plan"]["starter"] == 2
        assert after["paying_by_plan"]["pro"] - before["paying_by_plan"]["pro"] == 1
        assert after["mrr_cents"] - before["mrr_cents"] == 2 * 1900 + 4900      # comped user is NOT revenue
        assert after["plan_counts"]["pro"] - before["plan_counts"]["pro"] == 2   # but is counted as a pro user
        assert len(after["signups_by_month"]) == len(after["revenue_by_month"]) == 6
        this_month = datetime.utcnow().strftime("%Y-%m")
        assert after["signups_by_month"][-1]["month"] == this_month
        assert after["signups_by_month"][-1]["count"] >= 4

    def test_past_due_and_pending_cancellations(self, client, admin):
        before = client.get("/api/admin/stats", headers=admin.headers).json()
        u = signup(client); live_sub(u.id)
        db = SessionLocal(); db.query(User).filter(User.id == u.id).update({"subscription_status": "past_due"}); db.commit(); db.close()
        v = signup(client); live_sub(v.id)
        db = SessionLocal(); db.query(User).filter(User.id == v.id).update({"cancel_at_period_end": True}); db.commit(); db.close()
        after = client.get("/api/admin/stats", headers=admin.headers).json()
        assert after["past_due"] - before["past_due"] == 1
        assert after["pending_cancellations"] - before["pending_cancellations"] == 1

    def test_revenue_and_churn_come_from_billing_records(self, client, admin):
        before = client.get("/api/admin/stats", headers=admin.headers).json()
        u = signup(client); live_sub(u.id)
        db = SessionLocal()
        db.add(BillingInvoice(user_id=u.id, stripe_invoice_id=f"in_{uuid.uuid4().hex[:8]}", plan="starter",
                              amount_cents=1900, status="paid", created_at=datetime.utcnow()))
        db.add(BillingInvoice(user_id=u.id, stripe_invoice_id=f"in_{uuid.uuid4().hex[:8]}", plan="starter",
                              amount_cents=1900, status="failed", created_at=datetime.utcnow()))      # failed ≠ revenue
        db.add(StripeEvent(stripe_event_id=f"evt_{uuid.uuid4().hex[:8]}", event_type="customer.subscription.deleted"))
        db.commit(); db.close()
        after = client.get("/api/admin/stats", headers=admin.headers).json()
        assert after["revenue_total_cents"] - before["revenue_total_cents"] == 1900
        assert after["canceled_30d"] - before["canceled_30d"] == 1
        assert after["churn_rate_30d"] is not None and 0 < after["churn_rate_30d"] <= 100
        assert after["revenue_by_month"][-1]["cents"] >= 1900


class TestUserList:

    def test_search_by_email_name_and_organisation(self, client, admin):
        tag = uuid.uuid4().hex[:8]
        a = signup(client, name=f"Priya {tag}", org="Globex Retail")
        b = signup(client, name="Someone Else", org=f"Initech {tag}")
        for q, expect in [(a.email, a.id), (f"Priya {tag}", a.id), (f"initech {tag}", b.id)]:
            users = client.get("/api/admin/users", params={"search": q}, headers=admin.headers).json()["users"]
            assert [u["id"] for u in users] == [expect], q

    def test_percent_sign_in_search_is_literal_not_a_wildcard(self, client, admin):
        r = client.get("/api/admin/users", params={"search": "%"}, headers=admin.headers).json()
        assert r["total"] == 0

    def test_filter_by_plan_and_status(self, client, admin):
        tag = uuid.uuid4().hex[:6]
        pro = signup(client, org=f"P{tag}", plan="pro")
        sus = signup(client, org=f"S{tag}", is_active=False)
        by_plan = client.get("/api/admin/users", params={"plan": "pro", "search": f"P{tag}"}, headers=admin.headers).json()
        assert [u["id"] for u in by_plan["users"]] == [pro.id]
        by_status = client.get("/api/admin/users", params={"status": "suspended", "search": f"S{tag}"}, headers=admin.headers).json()
        assert [u["id"] for u in by_status["users"]] == [sus.id] and by_status["users"][0]["is_active"] is False

    def test_pagination(self, client, admin):
        for _ in range(3):
            signup(client)
        p1 = client.get("/api/admin/users", params={"limit": 2, "page": 1}, headers=admin.headers).json()
        p2 = client.get("/api/admin/users", params={"limit": 2, "page": 2}, headers=admin.headers).json()
        assert len(p1["users"]) == 2 and p1["pages"] >= 2 and p1["total"] >= 4
        assert not {u["id"] for u in p1["users"]} & {u["id"] for u in p2["users"]}

    def test_rows_show_dataset_counts_and_never_leak_password_hashes(self, client, admin, customer):
        upload(client, customer, "a.csv")
        row = [u for u in client.get("/api/admin/users", params={"search": customer.email}, headers=admin.headers).json()["users"]][0]
        assert row["datasets"] == 1 and row["role"] == "user" and row["plan"] == "free"
        assert not any("password" in k or "hash" in k for k in row)

    def test_limit_is_capped(self, client, admin):
        assert client.get("/api/admin/users", params={"limit": 1000}, headers=admin.headers).status_code == 422


class TestUserDetail:

    def test_detail_has_profile_billing_datasets_and_invoices(self, client, admin, customer):
        upload(client, customer, "report.csv")
        db = SessionLocal()
        db.add(BillingInvoice(user_id=customer.id, stripe_invoice_id=f"in_{uuid.uuid4().hex[:8]}", plan="starter",
                              amount_cents=1900, status="paid", created_at=datetime.utcnow()))
        db.commit(); db.close()
        d = client.get(f"/api/admin/users/{customer.id}", headers=admin.headers).json()
        assert d["user"]["email"] == customer.email
        assert [x["name"] for x in d["datasets"]] == ["report.csv"]
        assert d["invoices"][0]["amount_cents"] == 1900
        assert d["billing"]["plan"] == "free" and d["has_stripe_subscription"] is False

    def test_missing_user_is_404(self, client, admin):
        assert client.get("/api/admin/users/999999", headers=admin.headers).status_code == 404


class TestSuspend:

    def test_suspended_customer_is_locked_out_everywhere_then_restored(self, client, admin, customer):
        assert client.post(f"/api/admin/users/{customer.id}/suspend", headers=admin.headers).json()["is_active"] is False
        assert client.get("/api/auth/me", headers=customer.headers).status_code == 401           # existing session dies
        login = client.post("/api/auth/login", json={"email": customer.email, "password": "password123"})
        assert login.status_code == 403
        assert client.post(f"/api/admin/users/{customer.id}/restore", headers=admin.headers).json()["is_active"] is True
        assert client.post("/api/auth/login", json={"email": customer.email, "password": "password123"}).status_code == 200

    def test_suspending_keeps_their_data(self, client, admin, customer):
        upload(client, customer)
        client.post(f"/api/admin/users/{customer.id}/suspend", headers=admin.headers)
        detail = client.get(f"/api/admin/users/{customer.id}", headers=admin.headers).json()
        assert len(detail["datasets"]) == 1

    def test_admin_cannot_suspend_themselves(self, client, admin):
        r = client.post(f"/api/admin/users/{admin.id}/suspend", headers=admin.headers)
        assert r.status_code == 400
        assert client.get("/api/admin/stats", headers=admin.headers).status_code == 200

    def test_admin_cannot_touch_another_admin(self, client, admin):
        other = signup(client, name="Co-founder", role="admin")
        for call in (lambda: client.post(f"/api/admin/users/{other.id}/suspend", headers=admin.headers),
                     lambda: client.delete(f"/api/admin/users/{other.id}", headers=admin.headers),
                     lambda: client.put(f"/api/admin/users/{other.id}/plan", json={"plan": "free"}, headers=admin.headers)):
            r = call()
            assert r.status_code == 403 and "manage_users.py" in r.json()["detail"]
        assert client.get("/api/admin/stats", headers=other.headers).status_code == 200


class TestPlanOverride:

    def test_comping_a_plan_unlocks_uploads(self, client, admin, customer):
        assert upload(client, customer, "1.csv").status_code == 200
        assert upload(client, customer, "2.csv").status_code == 403                            # free = 1 dataset
        r = client.put(f"/api/admin/users/{customer.id}/plan", json={"plan": "starter"}, headers=admin.headers)
        assert r.status_code == 200 and r.json()["plan"] == "starter"
        assert upload(client, customer, "2.csv").status_code == 200

    def test_cannot_override_a_plan_that_stripe_is_billing(self, client, admin):
        payer = signup(client); live_sub(payer.id, "starter")
        r = client.put(f"/api/admin/users/{payer.id}/plan", json={"plan": "pro"}, headers=admin.headers)
        assert r.status_code == 409 and "Stripe" in r.json()["detail"]

    def test_unknown_plan_rejected(self, client, admin, customer):
        assert client.put(f"/api/admin/users/{customer.id}/plan", json={"plan": "platinum"}, headers=admin.headers).status_code == 422


class TestDelete:

    def test_deletes_user_data_and_files_from_disk(self, client, admin, customer):
        assert upload(client, customer).status_code == 200
        db = SessionLocal()
        path = db.query(UploadedFile).filter(UploadedFile.user_id == customer.id).first().file_path
        db.close()
        assert os.path.exists(path)
        r = client.delete(f"/api/admin/users/{customer.id}", headers=admin.headers)
        assert r.status_code == 200 and r.json()["datasets_removed"] == 1
        assert not os.path.exists(path)
        assert client.get(f"/api/admin/users/{customer.id}", headers=admin.headers).status_code == 404
        assert client.post("/api/auth/login", json={"email": customer.email, "password": "password123"}).status_code == 401
        db = SessionLocal()
        assert db.query(UploadedFile).filter(UploadedFile.user_id == customer.id).count() == 0
        db.close()

    def test_will_not_delete_a_paying_customer(self, client, admin):
        payer = signup(client); live_sub(payer.id)
        r = client.delete(f"/api/admin/users/{payer.id}", headers=admin.headers)
        assert r.status_code == 409 and "Cancel it in Stripe" in r.json()["detail"]
        assert client.get(f"/api/admin/users/{payer.id}", headers=admin.headers).status_code == 200

    def test_admin_cannot_delete_themselves(self, client, admin):
        assert client.delete(f"/api/admin/users/{admin.id}", headers=admin.headers).status_code == 400

    def test_deleting_one_customer_does_not_touch_anothers_data(self, client, admin, customer):
        other = signup(client)
        upload(client, customer); upload(client, other)
        client.delete(f"/api/admin/users/{customer.id}", headers=admin.headers)
        assert len(client.get("/api/upload/files", headers=other.headers).json()) == 1


class TestAuditLog:

    def test_actions_are_recorded_and_outlive_the_deleted_user(self, client, admin):
        victim = signup(client, name="Soon Gone")
        client.post(f"/api/admin/users/{victim.id}/suspend", headers=admin.headers)
        client.post(f"/api/admin/users/{victim.id}/restore", headers=admin.headers)
        client.put(f"/api/admin/users/{victim.id}/plan", json={"plan": "starter"}, headers=admin.headers)
        client.delete(f"/api/admin/users/{victim.id}", headers=admin.headers)
        entries = [e for e in client.get("/api/admin/activity", params={"limit": 100}, headers=admin.headers).json()["entries"]
                   if e["target"] == victim.email]
        assert [e["action"] for e in entries] == ["delete_user", "set_plan", "restore", "suspend"]   # newest first
        assert all(e["admin"] == admin.email for e in entries)
        assert "free -> starter" in entries[1]["detail"]

    def test_failed_attempts_are_not_logged_as_actions(self, client, admin):
        before = client.get("/api/admin/activity", headers=admin.headers).json()["total"]
        client.post(f"/api/admin/users/{admin.id}/suspend", headers=admin.headers)          # refused (self)
        assert client.get("/api/admin/activity", headers=admin.headers).json()["total"] == before

    def test_noop_does_not_spam_the_log(self, client, admin, customer):
        client.post(f"/api/admin/users/{customer.id}/restore", headers=admin.headers)       # already active
        entries = client.get("/api/admin/activity", params={"limit": 100}, headers=admin.headers).json()["entries"]
        assert not [e for e in entries if e["target"] == customer.email]
