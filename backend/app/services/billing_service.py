"""
services/billing_service.py
───────────────────────────
Everything that talks to Stripe lives here; routes stay thin.

Design rules (the things that usually go wrong with subscriptions):

1. WEBHOOKS ARE THE SOURCE OF TRUTH. Redirecting a browser to /billing/success
   proves nothing — only a signed webhook (or a fresh read from Stripe) may
   change a user's plan.
2. WEBHOOKS ARE VERIFIED. Unsigned / wrongly-signed requests are rejected, and
   if no signing secret is configured we refuse to process anything.
3. WEBHOOKS ARE IDEMPOTENT. Stripe delivers at-least-once, so every event id is
   recorded and replays are ignored. Handlers are also safe to run twice.
4. EVENTS CAN ARRIVE OUT OF ORDER. A stale `subscription.updated` must not undo a
   newer state, so each user remembers the newest event timestamp applied.
5. NO DOUBLE SUBSCRIPTIONS. Someone who already pays cannot start a second
   Checkout — they change plan instead (prorated).
6. DOWNGRADES NEVER DELETE DATA. Falling back to Free only blocks *new* uploads.
7. SDK-VERSION TOLERANT. Stripe moved a few fields between API versions
   (e.g. current_period_end now lives on the subscription *item*); we read both.
"""

import json
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

import stripe
from fastapi import HTTPException
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import plans as plan_defs
from app.config import settings
from app.database import BillingInvoice, StripeEvent, UploadedFile, User

PAID_PLANS = ("starter", "pro")
LIVE_STATUSES = ("active", "trialing", "past_due")          # user keeps access
ENDED_STATUSES = ("canceled", "unpaid", "incomplete_expired")  # user falls back to Free
WEBHOOK_TOLERANCE_SECONDS = 300


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────────────────────────────────────

def _plain(obj) -> dict:
    """Stripe SDK object (or dict) → plain dict. Newer SDKs are not dict subclasses."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return dict(obj)


def _first_item(sub: dict) -> dict:
    items = (sub.get("items") or {}).get("data") or []
    return items[0] if items else {}


def _sub_price_id(sub: dict) -> Optional[str]:
    item = _first_item(sub)
    return (item.get("price") or {}).get("id") or (item.get("plan") or {}).get("id")


def _sub_period_end(sub: dict) -> Optional[int]:
    # Older API versions: on the subscription. Newer: on each subscription item.
    return sub.get("current_period_end") or _first_item(sub).get("current_period_end")


def _invoice_subscription_id(inv: dict) -> Optional[str]:
    return inv.get("subscription") or (
        ((inv.get("parent") or {}).get("subscription_details") or {}).get("subscription")
    )


def _invoice_price_id(inv: dict) -> Optional[str]:
    lines = (inv.get("lines") or {}).get("data") or []
    if not lines:
        return None
    line = lines[0]
    return (
        (line.get("price") or {}).get("id")
        or (((line.get("pricing") or {}).get("price_details") or {}).get("price"))
    )


def _to_dt(ts) -> Optional[datetime]:
    return datetime.utcfromtimestamp(ts) if ts else None


@contextmanager
def _stripe_errors():
    """Turn Stripe SDK failures into clean API errors instead of 500s."""
    try:
        yield
    except stripe.StripeError as e:
        msg = getattr(e, "user_message", None) or str(e)
        logger.error(f"Stripe error: {type(e).__name__}: {msg}")
        raise HTTPException(status_code=502, detail=f"Payment provider error: {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────

class BillingService:

    def __init__(self, db: Session):
        self.db = db

    # ── Read APIs (no Stripe calls) ──────────────────────────────────────────

    @staticmethod
    def list_plans() -> list:
        out = []
        for key in plan_defs.PLAN_ORDER:
            p = plan_defs.PLANS[key]
            out.append({
                "id": key,
                "name": p["name"],
                "price_cents": p["price_cents"],
                "interval": "month" if p["price_cents"] else None,
                "upload_limit": p["upload_limit"],
                "tagline": p["tagline"],
                "features": p["features"],
                "popular": bool(p.get("popular")),
            })
        return out

    def uploads_used(self, user: User) -> int:
        return self.db.query(UploadedFile).filter(UploadedFile.user_id == user.id).count()

    def status(self, user: User) -> dict:
        plan = plan_defs.normalize_plan(user.plan)
        limit = plan_defs.upload_limit(plan)
        used = self.uploads_used(user)
        sub_status = user.subscription_status if user.stripe_subscription_id else "none"
        return {
            "plan": plan,
            "plan_name": plan_defs.PLANS[plan]["name"],
            "price_cents": plan_defs.PLANS[plan]["price_cents"],
            "subscription_status": sub_status,
            "current_period_end": user.current_period_end.isoformat() if user.current_period_end else None,
            "cancel_at_period_end": bool(user.cancel_at_period_end),
            "upload_limit": limit,                                   # None = unlimited
            "uploads_used": used,
            "uploads_remaining": None if limit is None else max(limit - used, 0),
            "can_upload": limit is None or used < limit,
            "over_limit": limit is not None and used > limit,        # e.g. after a downgrade
            "has_billing_account": bool(user.stripe_customer_id),
            "billing_configured": settings.stripe_configured,
        }

    def history(self, user: User) -> list:
        rows = (
            self.db.query(BillingInvoice)
            .filter(BillingInvoice.user_id == user.id)
            .order_by(BillingInvoice.created_at.desc(), BillingInvoice.id.desc())
            .all()
        )
        return [{
            "id": r.stripe_invoice_id,
            "date": r.created_at.isoformat() if r.created_at else None,
            "plan": r.plan,
            "amount_cents": r.amount_cents,
            "currency": r.currency,
            "status": r.status,
            "invoice_url": r.hosted_invoice_url,
            "pdf_url": r.invoice_pdf,
        } for r in rows]

    # ── Stripe actions (called by authenticated users) ───────────────────────

    def _require_stripe(self) -> None:
        if not settings.stripe_configured:
            raise HTTPException(
                status_code=503,
                detail="Billing is not configured on this server yet. "
                       "Set STRIPE_SECRET_KEY, STRIPE_STARTER_PRICE_ID and STRIPE_PRO_PRICE_ID.",
            )
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.max_network_retries = 2

    @staticmethod
    def _validate_paid_plan(plan: str) -> None:
        if plan not in PAID_PLANS:
            raise HTTPException(status_code=400, detail="Choose a paid plan: 'starter' or 'pro'.")

    @staticmethod
    def _has_live_subscription(user: User) -> bool:
        return bool(
            user.stripe_subscription_id
            and user.plan in PAID_PLANS
            and user.subscription_status in LIVE_STATUSES
        )

    def _ensure_customer(self, user: User) -> str:
        if user.stripe_customer_id:
            return user.stripe_customer_id
        with _stripe_errors():
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name or None,
                metadata={"user_id": str(user.id)},
                # Key includes the email so a reset dev database (same id, new
                # email) can't collide with an old idempotent request.
                idempotency_key=f"salesiq-customer-{user.id}-{user.email}",
            )
        user.stripe_customer_id = _plain(customer)["id"]
        self.db.commit()
        return user.stripe_customer_id

    def create_checkout(self, user: User, plan: str) -> dict:
        self._require_stripe()
        self._validate_paid_plan(plan)
        if self._has_live_subscription(user):
            raise HTTPException(
                status_code=409,
                detail="You already have an active subscription. Use 'change plan' instead of subscribing again.",
            )
        customer_id = self._ensure_customer(user)
        meta = {"user_id": str(user.id), "plan": plan}
        with _stripe_errors():
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                client_reference_id=str(user.id),
                line_items=[{"price": plan_defs.price_id_for(plan), "quantity": 1}],
                success_url=f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/pricing",
                allow_promotion_codes=True,
                metadata=meta,
                subscription_data={"metadata": meta},
            )
        s = _plain(session)
        logger.info(f"Checkout session created: user={user.id} plan={plan} session={s.get('id')}")
        return {"url": s["url"], "session_id": s["id"]}

    def create_portal(self, user: User) -> dict:
        self._require_stripe()
        if not user.stripe_customer_id:
            raise HTTPException(status_code=400, detail="No billing account yet. Subscribe to a plan first.")
        with _stripe_errors():
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=f"{settings.FRONTEND_URL}/billing",
            )
        return {"url": _plain(session)["url"]}

    @staticmethod
    def _modify_subscription(sub_id: str, **params):
        # `modify` exists in every SDK version; `update` only in newer ones.
        fn = getattr(stripe.Subscription, "modify", None) or stripe.Subscription.update
        return fn(sub_id, **params)

    def change_plan(self, user: User, new_plan: str) -> dict:
        """Switch between paid plans. Stripe prorates: upgrades are charged the
        difference immediately, downgrades earn credit on the next invoice."""
        self._require_stripe()
        self._validate_paid_plan(new_plan)
        if not user.stripe_subscription_id:
            raise HTTPException(status_code=400, detail="No active subscription. Subscribe first.")
        if user.plan == new_plan:
            raise HTTPException(status_code=400, detail=f"You are already on the {new_plan.title()} plan.")
        with _stripe_errors():
            current = _plain(stripe.Subscription.retrieve(user.stripe_subscription_id))
            item = _first_item(current)
            if not item.get("id"):
                raise HTTPException(status_code=502, detail="Could not read your current subscription from Stripe.")
            updated = _plain(self._modify_subscription(
                user.stripe_subscription_id,
                items=[{"id": item["id"], "price": plan_defs.price_id_for(new_plan)}],
                proration_behavior="create_prorations",
                cancel_at_period_end=False,
            ))
        self.sync_subscription(updated)
        logger.info(f"Plan changed: user={user.id} {user.plan}")
        return self.status(user)

    def set_cancel_at_period_end(self, user: User, cancel: bool) -> dict:
        """Cancel (keep access until the period ends) or undo a pending cancel."""
        self._require_stripe()
        if not user.stripe_subscription_id:
            raise HTTPException(status_code=400, detail="You have no active subscription.")
        with _stripe_errors():
            updated = _plain(self._modify_subscription(
                user.stripe_subscription_id, cancel_at_period_end=cancel
            ))
        self.sync_subscription(updated)
        logger.info(f"Subscription {'cancel scheduled' if cancel else 'resumed'}: user={user.id}")
        return self.status(user)

    def refresh_from_stripe(self, user: User) -> dict:
        """
        Pull the user's subscription straight from Stripe and apply it.
        Used by the post-checkout page so the plan updates instantly even if the
        webhook is slow — or isn't running at all on a local dev machine.
        Conservative: only ever *applies* a live subscription; never downgrades.
        """
        self._require_stripe()
        if user.stripe_customer_id:
            with _stripe_errors():
                subs = stripe.Subscription.list(customer=user.stripe_customer_id, status="all", limit=10)
            for sub in (_plain(subs).get("data") or []):
                sub = _plain(sub)
                if sub.get("status") in LIVE_STATUSES:
                    self.sync_subscription(sub)
                    break
        self.db.refresh(user)
        return self.status(user)

    # ── Subscription → local user mirror ─────────────────────────────────────

    def _find_user(self, *, user_id=None, customer_id=None) -> Optional[User]:
        """Customer id is authoritative (it is what Stripe bills). Metadata user_id is
        only a fallback — after a dev database reset it can point at a different person."""
        user = None
        if customer_id:
            user = self.db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user is None and user_id:
            try:
                user = self.db.get(User, int(user_id))
            except (TypeError, ValueError):
                user = None
        return user

    def sync_subscription(self, sub: dict, event_ts: Optional[int] = None) -> Optional[User]:
        """Apply a Stripe subscription object to the matching user. Idempotent."""
        sub = _plain(sub)
        user = self._find_user(
            user_id=(sub.get("metadata") or {}).get("user_id"),
            customer_id=sub.get("customer"),
        )
        if user is None:
            logger.warning(f"Subscription {sub.get('id')} matches no user; ignored")
            return None

        # Out-of-order protection (rule 4)
        if event_ts is not None and user.stripe_synced_at and event_ts < user.stripe_synced_at:
            logger.info(f"Ignoring stale Stripe event (ts={event_ts} < {user.stripe_synced_at}) for user {user.id}")
            return user

        status = sub.get("status")
        mapped_plan = plan_defs.plan_for_price_id(_sub_price_id(sub))

        if status in LIVE_STATUSES:
            if mapped_plan:
                user.plan = mapped_plan
            else:
                # Never guess a plan from an unrecognised price — keep what we had.
                logger.warning(f"Unknown Stripe price {_sub_price_id(sub)!r} on {sub.get('id')}; plan unchanged")
            user.stripe_subscription_id = sub.get("id")
            user.subscription_status = status
            user.cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
            user.current_period_end = _to_dt(_sub_period_end(sub))
        elif status in ENDED_STATUSES:
            user.plan = "free"
            user.stripe_subscription_id = None
            user.subscription_status = status
            user.cancel_at_period_end = False
            user.current_period_end = None
        else:
            # incomplete / paused: payment not confirmed → grant nothing, change nothing.
            logger.info(f"Subscription {sub.get('id')} status={status}; no plan change")

        if not user.stripe_customer_id and sub.get("customer"):
            user.stripe_customer_id = sub["customer"]
        user.stripe_synced_at = max(user.stripe_synced_at or 0, event_ts or int(time.time()))
        self.db.commit()
        logger.info(f"Synced user={user.id}: plan={user.plan} status={user.subscription_status}")
        return user

    # ── Webhooks ─────────────────────────────────────────────────────────────

    def process_webhook(self, payload: bytes, signature: Optional[str]) -> dict:
        if not settings.STRIPE_WEBHOOK_SECRET:
            # Without a secret we cannot authenticate the sender — refuse everything.
            raise HTTPException(status_code=503, detail="Webhook signing secret is not configured.")
        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe-Signature header.")
        try:
            stripe.WebhookSignature.verify_header(
                payload.decode("utf-8"), signature, settings.STRIPE_WEBHOOK_SECRET,
                tolerance=WEBHOOK_TOLERANCE_SECONDS,
            )
            event = json.loads(payload)
        except (stripe.SignatureVerificationError, ValueError, UnicodeDecodeError) as e:
            logger.warning(f"Rejected webhook: {e}")
            raise HTTPException(status_code=400, detail="Invalid webhook signature or payload.")

        event_id, event_type = event.get("id"), event.get("type")
        if not event_id:
            raise HTTPException(status_code=400, detail="Event has no id.")
        if self.db.query(StripeEvent).filter(StripeEvent.stripe_event_id == event_id).first():
            logger.info(f"Duplicate webhook {event_id} ({event_type}); skipped")
            return {"received": True, "duplicate": True}

        try:
            self._dispatch(event)
        except HTTPException:
            raise
        except Exception as e:
            # 500 → Stripe retries with backoff. Don't record the event as processed.
            self.db.rollback()
            logger.error(f"Webhook {event_id} ({event_type}) failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Webhook handler failed; Stripe will retry.")

        try:
            self.db.add(StripeEvent(stripe_event_id=event_id, event_type=event_type))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()          # concurrent duplicate delivery — already recorded
        return {"received": True}

    def _dispatch(self, event: dict) -> None:
        etype = event["type"]
        obj = (event.get("data") or {}).get("object") or {}
        created = event.get("created")

        if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            self._on_checkout_completed(obj, created)
        elif etype in ("customer.subscription.created", "customer.subscription.updated",
                       "customer.subscription.deleted"):
            self.sync_subscription(obj, event_ts=created)
        elif etype == "invoice.paid":
            self._record_invoice(obj, "paid")
        elif etype == "invoice.payment_failed":
            self._on_payment_failed(obj)
        else:
            logger.debug(f"Ignoring webhook type {etype}")

    def _on_checkout_completed(self, session: dict, created: Optional[int]) -> None:
        if session.get("mode") != "subscription":
            return
        user = self._find_user(
            user_id=session.get("client_reference_id") or (session.get("metadata") or {}).get("user_id"),
            customer_id=session.get("customer"),
        )
        if user is None:
            logger.warning(f"Checkout session {session.get('id')} matches no user; ignored")
            return
        if not user.stripe_customer_id and session.get("customer"):
            user.stripe_customer_id = session["customer"]
            self.db.commit()
        if session.get("payment_status") not in ("paid", "no_payment_required"):
            logger.info(f"Checkout {session.get('id')} not paid yet; waiting for later events")
            return
        sub_id = session.get("subscription")
        if not sub_id:
            return
        stripe.api_key = settings.STRIPE_SECRET_KEY
        sub = _plain(stripe.Subscription.retrieve(sub_id))
        self.sync_subscription(sub, event_ts=created)

    def _on_payment_failed(self, inv: dict) -> None:
        self._record_invoice(inv, "failed")
        user = self._find_user(customer_id=inv.get("customer"))
        if user and user.stripe_subscription_id:
            user.subscription_status = "past_due"
            self.db.commit()
        logger.warning(f"Payment failed for customer {inv.get('customer')} (invoice {inv.get('id')})")

    def _record_invoice(self, inv: dict, status: str) -> None:
        user = self._find_user(customer_id=inv.get("customer"))
        if user is None or not inv.get("id"):
            logger.warning(f"Invoice {inv.get('id')} matches no user; not recorded")
            return
        amount = inv.get("amount_paid") if status == "paid" else inv.get("amount_due")
        plan = plan_defs.plan_for_price_id(_invoice_price_id(inv)) or user.plan
        row = self.db.query(BillingInvoice).filter(BillingInvoice.stripe_invoice_id == inv["id"]).first()
        if row is not None and row.user_id != user.id:
            logger.error(f"Invoice {inv['id']} already belongs to another user; refusing to overwrite")
            return
        if row is None:
            row = BillingInvoice(user_id=user.id, stripe_invoice_id=inv["id"])
            self.db.add(row)
        row.plan = plan
        row.status = status
        row.amount_cents = amount or 0
        row.currency = inv.get("currency") or "usd"
        row.hosted_invoice_url = inv.get("hosted_invoice_url")
        row.invoice_pdf = inv.get("invoice_pdf")
        if inv.get("created"):
            row.created_at = _to_dt(inv["created"])
        self.db.commit()
