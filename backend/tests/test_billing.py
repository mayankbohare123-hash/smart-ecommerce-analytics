"""
tests/test_billing.py
─────────────────────
Stripe subscription tests. Stripe itself is mocked — no account or network needed.

Covers the things that go wrong in real billing code:
  • forged / tampered / replayed / stale webhooks
  • the same event delivered twice, and events arriving out of order
  • double-subscribing, plan changes, cancel / resume
  • payment failures, cancellations and downgrades (data must never be deleted)
  • upload limits following the plan end-to-end
"""

import hashlib
import hmac
import itertools
import json
import time
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import stripe
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal, User, create_tables, drop_tables
from app.main import app

pytestmark = pytest.mark.real_auth      # these tests use REAL login, not the test-user override

STARTER, PRO = "price_starter_test", "price_pro_test"
WH_SECRET = "whsec_test_secret"
_counter = itertools.count(1)


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


@pytest.fixture
def stripe_on(monkeypatch):
    """Turn billing 'on' with fake keys."""
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", WH_SECRET)
    monkeypatch.setattr(settings, "STRIPE_STARTER_PRICE_ID", STARTER)
    monkeypatch.setattr(settings, "STRIPE_PRO_PRICE_ID", PRO)
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")


@pytest.fixture
def user(client):
    """A freshly signed-up user that already has a Stripe customer id."""
    email = f"u{uuid.uuid4().hex[:10]}@test.com"
    r = client.post("/api/auth/signup", json={"name": "Test", "email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    cust = f"cus_{next(_counter)}_{uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    row = db.query(User).filter(User.email == email).first()
    row.stripe_customer_id = cust
    db.commit()
    uid = row.id
    db.close()
    return SimpleNamespace(
        email=email, id=uid, customer=cust,
        headers={"Authorization": f"Bearer {r.json()['access_token']}"},
    )


def db_user(email) -> User:
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    db.expunge(u)
    db.close()
    return u


# ── Helpers: build + sign Stripe payloads ─────────────────────────────────────

def make_sub(user, *, status="active", price=STARTER, sub_id="sub_1", cancel=False,
             period_end=2_000_000_000, new_api=False):
    item = {"id": "si_1", "price": {"id": price}}
    sub = {"id": sub_id, "object": "subscription", "customer": user.customer, "status": status,
           "cancel_at_period_end": cancel, "metadata": {"user_id": str(user.id)},
           "items": {"data": [item]}}
    if new_api:                       # newer Stripe API: period end lives on the item
        item["current_period_end"] = period_end
    else:
        sub["current_period_end"] = period_end
    return sub


def make_event(etype, obj, *, event_id=None, created=None):
    return {"id": event_id or f"evt_{next(_counter)}_{uuid.uuid4().hex[:6]}", "type": etype,
            "created": created or int(time.time()), "data": {"object": obj}}


def sign(payload: bytes, secret=WH_SECRET, ts=None) -> str:
    ts = ts or int(time.time())
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def send(client, event, *, secret=WH_SECRET, ts=None, header=None, body=None):
    payload = body if body is not None else json.dumps(event).encode()
    headers = {"Content-Type": "application/json"}
    sig = header if header is not None else sign(payload, secret, ts)
    if sig:
        headers["Stripe-Signature"] = sig
    return client.post("/api/billing/webhook", content=payload, headers=headers)


def activate(client, user, plan_price=STARTER, **kw):
    """Drive a user to a paid plan through a real (signed) subscription.created webhook."""
    r = send(client, make_event("customer.subscription.created", make_sub(user, price=plan_price, **kw)))
    assert r.status_code == 200, r.text


def status(client, user):
    r = client.get("/api/billing/status", headers=user.headers)
    assert r.status_code == 200, r.text
    return r.json()


CSV = ("order_id,order_date,product,category,region,quantity,net_revenue\n"
       "O1,2024-01-15,Headphones,Electronics,North,2,299.98\n"
       "O2,2024-01-16,Keyboard,Electronics,South,1,89.99\n"
       "O3,2024-02-01,Yoga Mat,Sports,East,3,119.97\n")


def upload(client, user, name="s.csv"):
    return client.post("/api/upload", files={"file": (name, CSV.encode(), "text/csv")}, headers=user.headers)


# ══════════════════════════════════════════════════════════════════════════════
# Plans & status
# ══════════════════════════════════════════════════════════════════════════════

class TestPlansAndStatus:

    def test_plans_are_public_and_correct(self, client):
        plans = {p["id"]: p for p in client.get("/api/billing/plans").json()["plans"]}
        assert [plans[k]["price_cents"] for k in ("free", "starter", "pro")] == [0, 1900, 4900]
        assert [plans[k]["upload_limit"] for k in ("free", "starter", "pro")] == [1, 5, None]
        assert plans["starter"]["popular"] is True

    def test_status_requires_login(self, client):
        assert client.get("/api/billing/status").status_code == 401

    def test_new_user_is_free(self, client, user):
        s = status(client, user)
        assert (s["plan"], s["upload_limit"], s["uploads_used"], s["can_upload"]) == ("free", 1, 0, True)
        assert s["subscription_status"] == "none" and s["cancel_at_period_end"] is False

    def test_auth_me_reports_limit(self, client, user):
        me = client.get("/api/auth/me", headers=user.headers).json()["user"]
        assert me["plan"] == "free" and me["upload_limit"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# Checkout
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckout:

    def test_not_configured_returns_503(self, client, user, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")
        r = client.post("/api/billing/checkout", json={"plan": "starter"}, headers=user.headers)
        assert r.status_code == 503 and "not configured" in r.json()["detail"]

    def test_requires_login(self, client, stripe_on):
        assert client.post("/api/billing/checkout", json={"plan": "starter"}).status_code == 401

    @pytest.mark.parametrize("plan", ["free", "enterprise", ""])
    def test_rejects_non_paid_plans(self, client, user, stripe_on, plan):
        assert client.post("/api/billing/checkout", json={"plan": plan}, headers=user.headers).status_code == 422

    def test_creates_session_with_correct_parameters(self, client, user, stripe_on):
        with patch("stripe.checkout.Session.create",
                   return_value={"id": "cs_1", "url": "https://checkout.stripe.com/pay/cs_1"}) as create:
            r = client.post("/api/billing/checkout", json={"plan": "pro"}, headers=user.headers)
        assert r.status_code == 200
        assert r.json() == {"url": "https://checkout.stripe.com/pay/cs_1", "session_id": "cs_1"}
        kw = create.call_args.kwargs
        assert kw["mode"] == "subscription"
        assert kw["customer"] == user.customer
        assert kw["client_reference_id"] == str(user.id)
        assert kw["line_items"] == [{"price": PRO, "quantity": 1}]
        assert kw["success_url"] == "http://localhost:5173/billing/success?session_id={CHECKOUT_SESSION_ID}"
        assert kw["cancel_url"] == "http://localhost:5173/pricing"
        assert kw["metadata"] == {"user_id": str(user.id), "plan": "pro"}

    def test_creates_customer_once_and_reuses_it(self, client, stripe_on):
        email = f"c{uuid.uuid4().hex[:8]}@test.com"
        tok = client.post("/api/auth/signup", json={"name": "Nina", "email": email, "password": "password123"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        with patch("stripe.Customer.create", return_value={"id": "cus_new"}) as cust, \
             patch("stripe.checkout.Session.create", return_value={"id": "cs", "url": "https://x"}):
            client.post("/api/billing/checkout", json={"plan": "starter"}, headers=h)
            client.post("/api/billing/checkout", json={"plan": "pro"}, headers=h)
        assert cust.call_count == 1
        assert db_user(email).stripe_customer_id == "cus_new"

    def test_cannot_subscribe_twice(self, client, user, stripe_on):
        activate(client, user, STARTER)
        with patch("stripe.checkout.Session.create") as create:
            r = client.post("/api/billing/checkout", json={"plan": "pro"}, headers=user.headers)
        assert r.status_code == 409 and "change plan" in r.json()["detail"].lower()
        create.assert_not_called()

    def test_stripe_failure_becomes_502_not_500(self, client, user, stripe_on):
        err = stripe.InvalidRequestError("No such price", param="price")
        with patch("stripe.checkout.Session.create", side_effect=err):
            r = client.post("/api/billing/checkout", json={"plan": "starter"}, headers=user.headers)
        assert r.status_code == 502 and "No such price" in r.json()["detail"]


# ══════════════════════════════════════════════════════════════════════════════
# Webhook security
# ══════════════════════════════════════════════════════════════════════════════

class TestWebhookSecurity:

    def test_refuses_everything_without_a_signing_secret(self, client, user, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        ev = make_event("customer.subscription.created", make_sub(user))
        assert send(client, ev).status_code == 503

    def test_missing_signature_rejected(self, client, user, stripe_on):
        ev = make_event("customer.subscription.created", make_sub(user))
        assert send(client, ev, header="").status_code == 400
        assert status(client, user)["plan"] == "free"

    def test_wrong_secret_rejected(self, client, user, stripe_on):
        ev = make_event("customer.subscription.created", make_sub(user, price=PRO))
        assert send(client, ev, secret="whsec_attacker").status_code == 400
        assert status(client, user)["plan"] == "free"

    def test_tampered_body_rejected(self, client, user, stripe_on):
        ev = make_event("customer.subscription.created", make_sub(user))
        good = json.dumps(ev).encode()
        evil = json.dumps(make_event("customer.subscription.created", make_sub(user, price=PRO))).encode()
        assert send(client, ev, body=evil, header=sign(good)).status_code == 400
        assert status(client, user)["plan"] == "free"

    def test_old_timestamp_rejected_to_block_replays(self, client, user, stripe_on):
        ev = make_event("customer.subscription.created", make_sub(user))
        assert send(client, ev, ts=int(time.time()) - 3600).status_code == 400

    def test_garbage_body_rejected(self, client, stripe_on):
        assert send(client, None, body=b"not json").status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# Subscription lifecycle via webhooks
# ══════════════════════════════════════════════════════════════════════════════

class TestWebhookLifecycle:

    def test_checkout_completed_upgrades_to_starter(self, client, user, stripe_on):
        session = {"id": "cs_1", "mode": "subscription", "payment_status": "paid", "subscription": "sub_1",
                   "customer": user.customer, "client_reference_id": str(user.id)}
        with patch("stripe.Subscription.retrieve", return_value=make_sub(user)) as retrieve:
            r = send(client, make_event("checkout.session.completed", session))
        assert r.status_code == 200
        retrieve.assert_called_once_with("sub_1")
        s = status(client, user)
        assert (s["plan"], s["subscription_status"], s["upload_limit"]) == ("starter", "active", 5)
        assert s["current_period_end"] is not None

    def test_unpaid_checkout_grants_nothing(self, client, user, stripe_on):
        session = {"id": "cs_2", "mode": "subscription", "payment_status": "unpaid", "subscription": "sub_1",
                   "customer": user.customer, "client_reference_id": str(user.id)}
        with patch("stripe.Subscription.retrieve") as retrieve:
            assert send(client, make_event("checkout.session.completed", session)).status_code == 200
        retrieve.assert_not_called()
        assert status(client, user)["plan"] == "free"

    def test_same_event_delivered_twice_is_processed_once(self, client, user, stripe_on):
        session = {"id": "cs_3", "mode": "subscription", "payment_status": "paid", "subscription": "sub_1",
                   "customer": user.customer, "client_reference_id": str(user.id)}
        ev = make_event("checkout.session.completed", session)
        with patch("stripe.Subscription.retrieve", return_value=make_sub(user)) as retrieve:
            first, second = send(client, ev), send(client, ev)
        assert first.json() == {"received": True}
        assert second.json() == {"received": True, "duplicate": True}
        assert retrieve.call_count == 1

    def test_upgrade_starter_to_pro(self, client, user, stripe_on):
        activate(client, user, STARTER)
        send(client, make_event("customer.subscription.updated", make_sub(user, price=PRO), created=int(time.time()) + 5))
        s = status(client, user)
        assert (s["plan"], s["upload_limit"], s["can_upload"]) == ("pro", None, True)

    def test_new_stripe_api_shape_period_end_on_item(self, client, user, stripe_on):
        activate(client, user, STARTER, new_api=True, period_end=2_000_000_000)
        assert status(client, user)["current_period_end"].startswith("2033-")

    def test_scheduled_cancel_keeps_access_until_period_end(self, client, user, stripe_on):
        activate(client, user, PRO)
        send(client, make_event("customer.subscription.updated", make_sub(user, price=PRO, cancel=True),
                                created=int(time.time()) + 5))
        s = status(client, user)
        assert s["plan"] == "pro" and s["cancel_at_period_end"] is True

    def test_subscription_deleted_returns_user_to_free(self, client, user, stripe_on):
        activate(client, user, PRO)
        send(client, make_event("customer.subscription.deleted", make_sub(user, price=PRO, status="canceled"),
                                created=int(time.time()) + 5))
        s = status(client, user)
        assert (s["plan"], s["subscription_status"], s["upload_limit"]) == ("free", "none", 1)
        assert db_user(user.email).stripe_subscription_id is None

    def test_past_due_keeps_plan_but_flags_status(self, client, user, stripe_on):
        activate(client, user, STARTER)
        send(client, make_event("customer.subscription.updated", make_sub(user, status="past_due"),
                                created=int(time.time()) + 5))
        s = status(client, user)
        assert s["plan"] == "starter" and s["subscription_status"] == "past_due"

    def test_unknown_price_never_changes_plan(self, client, user, stripe_on):
        activate(client, user, STARTER)
        send(client, make_event("customer.subscription.updated", make_sub(user, price="price_mystery"),
                                created=int(time.time()) + 5))
        assert status(client, user)["plan"] == "starter"

    def test_incomplete_subscription_grants_nothing(self, client, user, stripe_on):
        send(client, make_event("customer.subscription.created", make_sub(user, status="incomplete")))
        assert status(client, user)["plan"] == "free"

    def test_out_of_order_stale_event_is_ignored(self, client, user, stripe_on):
        now = int(time.time())
        send(client, make_event("customer.subscription.updated", make_sub(user, price=PRO), created=now + 100))
        # an OLDER event (starter) arrives afterwards — must not undo the newer Pro state
        send(client, make_event("customer.subscription.updated", make_sub(user, price=STARTER), created=now + 10))
        assert status(client, user)["plan"] == "pro"

    def test_event_for_unknown_customer_is_acknowledged(self, client, stripe_on):
        ghost = SimpleNamespace(customer="cus_nobody", id=999999)
        assert send(client, make_event("customer.subscription.created", make_sub(ghost))).status_code == 200

    def test_unhandled_event_types_are_acknowledged(self, client, stripe_on):
        assert send(client, make_event("charge.refunded", {"id": "ch_1"})).status_code == 200

    def test_handler_failure_returns_500_and_a_retry_succeeds(self, client, user, stripe_on):
        session = {"id": "cs_9", "mode": "subscription", "payment_status": "paid", "subscription": "sub_1",
                   "customer": user.customer, "client_reference_id": str(user.id)}
        ev = make_event("checkout.session.completed", session)
        with patch("stripe.Subscription.retrieve", side_effect=RuntimeError("network down")):
            assert send(client, ev).status_code == 500          # Stripe will retry…
        assert status(client, user)["plan"] == "free"
        with patch("stripe.Subscription.retrieve", return_value=make_sub(user)):
            assert send(client, ev).status_code == 200          # …and the retry is NOT skipped as a duplicate
        assert status(client, user)["plan"] == "starter"


class TestInvoices:

    def invoice(self, user, inv_id=None, **kw):
        return {"id": inv_id or f"in_{uuid.uuid4().hex[:10]}", "customer": user.customer, "amount_paid": 1900, "amount_due": 1900,
                "currency": "usd", "created": 1_900_000_000, "hosted_invoice_url": "https://inv/1",
                "invoice_pdf": "https://inv/1.pdf",
                "lines": {"data": [{"price": {"id": STARTER}}]}, **kw}

    def test_paid_invoice_appears_in_history(self, client, user, stripe_on):
        send(client, make_event("invoice.paid", self.invoice(user)))
        rows = client.get("/api/billing/history", headers=user.headers).json()["invoices"]
        assert len(rows) == 1
        assert (rows[0]["amount_cents"], rows[0]["status"], rows[0]["plan"]) == (1900, "paid", "starter")
        assert rows[0]["invoice_url"] == "https://inv/1"

    def test_same_invoice_in_two_events_is_stored_once(self, client, user, stripe_on):
        inv = self.invoice(user)
        send(client, make_event("invoice.paid", inv))
        send(client, make_event("invoice.paid", inv))                       # different event id, same invoice
        assert len(client.get("/api/billing/history", headers=user.headers).json()["invoices"]) == 1

    def test_failed_payment_recorded_and_flags_past_due(self, client, user, stripe_on):
        activate(client, user, STARTER)
        send(client, make_event("invoice.payment_failed", self.invoice(user, "in_fail")))
        rows = client.get("/api/billing/history", headers=user.headers).json()["invoices"]
        assert rows[0]["status"] == "failed"
        assert status(client, user)["subscription_status"] == "past_due"

    def test_history_is_private_to_each_user(self, client, user, stripe_on):
        other = client.post("/api/auth/signup", json={"name": "Omar", "email": f"o{uuid.uuid4().hex[:6]}@t.com",
                                                      "password": "password123"}).json()["access_token"]
        send(client, make_event("invoice.paid", self.invoice(user, "in_private")))
        r = client.get("/api/billing/history", headers={"Authorization": f"Bearer {other}"})
        assert r.json()["invoices"] == []


# ══════════════════════════════════════════════════════════════════════════════
# Change plan / cancel / resume / portal / sync
# ══════════════════════════════════════════════════════════════════════════════

class TestPlanManagement:

    def test_change_plan_prorates_and_updates(self, client, user, stripe_on):
        activate(client, user, STARTER)
        with patch("stripe.Subscription.retrieve", return_value=make_sub(user)), \
             patch("stripe.Subscription.modify", return_value=make_sub(user, price=PRO)) as modify:
            r = client.post("/api/billing/change-plan", json={"plan": "pro"}, headers=user.headers)
        assert r.status_code == 200 and r.json()["plan"] == "pro"
        args, kw = modify.call_args
        assert args == ("sub_1",)
        assert kw["items"] == [{"id": "si_1", "price": PRO}]
        assert kw["proration_behavior"] == "create_prorations"
        assert kw["cancel_at_period_end"] is False

    def test_change_to_same_plan_rejected(self, client, user, stripe_on):
        activate(client, user, STARTER)
        r = client.post("/api/billing/change-plan", json={"plan": "starter"}, headers=user.headers)
        assert r.status_code == 400

    def test_change_plan_without_subscription_rejected(self, client, user, stripe_on):
        assert client.post("/api/billing/change-plan", json={"plan": "pro"}, headers=user.headers).status_code == 400

    def test_cancel_then_resume(self, client, user, stripe_on):
        activate(client, user, PRO)
        with patch("stripe.Subscription.modify", return_value=make_sub(user, price=PRO, cancel=True)) as modify:
            r = client.post("/api/billing/cancel", headers=user.headers)
        assert modify.call_args.kwargs == {"cancel_at_period_end": True}
        assert r.json()["cancel_at_period_end"] is True and r.json()["plan"] == "pro"   # access kept
        with patch("stripe.Subscription.modify", return_value=make_sub(user, price=PRO, cancel=False)) as modify:
            r = client.post("/api/billing/resume", headers=user.headers)
        assert modify.call_args.kwargs == {"cancel_at_period_end": False}
        assert r.json()["cancel_at_period_end"] is False

    def test_cancel_without_subscription_rejected(self, client, user, stripe_on):
        assert client.post("/api/billing/cancel", headers=user.headers).status_code == 400

    def test_portal_returns_url(self, client, user, stripe_on):
        with patch("stripe.billing_portal.Session.create", return_value={"url": "https://billing.stripe.com/p/1"}) as portal:
            r = client.post("/api/billing/portal", headers=user.headers)
        assert r.json() == {"url": "https://billing.stripe.com/p/1"}
        assert portal.call_args.kwargs["customer"] == user.customer
        assert portal.call_args.kwargs["return_url"] == "http://localhost:5173/billing"

    def test_portal_without_billing_account_rejected(self, client, stripe_on):
        email = f"p{uuid.uuid4().hex[:8]}@test.com"
        tok = client.post("/api/auth/signup", json={"name": "Nina", "email": email, "password": "password123"}).json()["access_token"]
        assert client.post("/api/billing/portal", headers={"Authorization": f"Bearer {tok}"}).status_code == 400

    def test_sync_applies_live_subscription_without_a_webhook(self, client, user, stripe_on):
        with patch("stripe.Subscription.list", return_value={"data": [make_sub(user, price=PRO)]}):
            r = client.post("/api/billing/sync", headers=user.headers)
        assert r.json()["plan"] == "pro"

    def test_sync_never_downgrades(self, client, user, stripe_on):
        activate(client, user, PRO)
        with patch("stripe.Subscription.list", return_value={"data": []}):
            r = client.post("/api/billing/sync", headers=user.headers)
        assert r.json()["plan"] == "pro"


# ══════════════════════════════════════════════════════════════════════════════
# Plans actually control uploads, end to end
# ══════════════════════════════════════════════════════════════════════════════

class TestPlanLimitsEndToEnd:

    def test_free_blocks_second_upload_then_starter_allows_it(self, client, user, stripe_on):
        assert upload(client, user, "a.csv").status_code == 200
        blocked = upload(client, user, "b.csv")
        assert blocked.status_code == 403 and "Upgrade" in blocked.json()["detail"]

        activate(client, user, STARTER)
        assert upload(client, user, "b.csv").status_code == 200
        s = status(client, user)
        assert (s["uploads_used"], s["upload_limit"], s["uploads_remaining"]) == (2, 5, 3)

    def test_starter_stops_at_five(self, client, user, stripe_on):
        activate(client, user, STARTER)
        assert [upload(client, user, f"{i}.csv").status_code for i in range(5)] == [200] * 5
        assert upload(client, user, "6.csv").status_code == 403

    def test_pro_is_unlimited(self, client, user, stripe_on):
        activate(client, user, PRO)
        assert all(upload(client, user, f"{i}.csv").status_code == 200 for i in range(7))
        assert status(client, user)["uploads_remaining"] is None

    def test_downgrade_blocks_new_uploads_but_keeps_existing_data(self, client, user, stripe_on):
        activate(client, user, STARTER)
        for i in range(3):
            assert upload(client, user, f"{i}.csv").status_code == 200
        send(client, make_event("customer.subscription.deleted", make_sub(user, status="canceled"),
                                created=int(time.time()) + 5))
        s = status(client, user)
        assert (s["plan"], s["uploads_used"], s["over_limit"], s["can_upload"]) == ("free", 3, True, False)
        assert len(client.get("/api/upload/files", headers=user.headers).json()) == 3   # nothing deleted
        assert upload(client, user, "new.csv").status_code == 403
