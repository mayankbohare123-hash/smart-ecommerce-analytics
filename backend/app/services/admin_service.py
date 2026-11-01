"""
services/admin_service.py
─────────────────────────
Everything the founder's admin panel can see and do.

Safety rules baked in (each one has a test):
  • An admin can never act on their own account (no accidental self-lock-out).
  • Admin accounts can't be suspended / deleted / re-planned from the panel at all —
    only from the server (scripts/manage_users.py). A hijacked admin session therefore
    can't remove the other admins.
  • A customer with a LIVE Stripe subscription can't be deleted or have their plan
    overridden here — deleting them would leave Stripe still charging a card for an account
    that no longer exists. Cancel in Stripe first.
  • Every state-changing action is written to the audit log (which outlives the user).
  • Deleting a user removes their data AND their uploaded files from disk.

Numbers: MRR is computed from the local subscription mirror (kept in sync by Stripe
webhooks) — manually "comped" users are correctly excluded. Stripe remains the source of truth.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import plans as plan_defs
from app.database import (
    AdminAuditLog, BillingInvoice, PasswordResetToken, PredictionResult,
    StripeEvent, UploadedFile, User,
)
from app.services.billing_service import LIVE_STATUSES, PAID_PLANS, BillingService
from app.utils.file_helpers import safe_delete


def _last_months(n: int = 6) -> list:
    """['2026-05', …, '2026-10'] — oldest first, current month last."""
    today = datetime.utcnow()
    y, m, out = today.year, today.month, []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


class AdminService:

    def __init__(self, db: Session):
        self.db = db

    # ── Overview numbers ─────────────────────────────────────────────────────

    def stats(self) -> dict:
        db, now = self.db, datetime.utcnow()
        d7, d30 = now - timedelta(days=7), now - timedelta(days=30)

        total_users = db.query(User).count()
        plan_counts = {p: 0 for p in plan_defs.PLAN_ORDER}
        for plan, n in db.query(User.plan, func.count(User.id)).group_by(User.plan).all():
            plan_counts[plan_defs.normalize_plan(plan)] += n

        paying = defaultdict(int)       # live Stripe subscribers by plan (comped users excluded)
        for plan, n in (
            db.query(User.plan, func.count(User.id))
            .filter(User.stripe_subscription_id.isnot(None),
                    User.plan.in_(PAID_PLANS),
                    User.subscription_status.in_(LIVE_STATUSES))
            .group_by(User.plan).all()
        ):
            paying[plan] = n
        mrr_cents = sum(paying[p] * plan_defs.PLANS[p]["price_cents"] for p in PAID_PLANS)
        paying_total = sum(paying.values())

        canceled_30d = db.query(StripeEvent).filter(
            StripeEvent.event_type == "customer.subscription.deleted",
            StripeEvent.processed_at >= d30).count()
        churn = round(100 * canceled_30d / (paying_total + canceled_30d), 1) if (paying_total + canceled_30d) else None

        paid_inv = db.query(BillingInvoice).filter(BillingInvoice.status == "paid")
        revenue_total = paid_inv.with_entities(func.coalesce(func.sum(BillingInvoice.amount_cents), 0)).scalar()
        revenue_30d = paid_inv.filter(BillingInvoice.created_at >= d30) \
            .with_entities(func.coalesce(func.sum(BillingInvoice.amount_cents), 0)).scalar()

        months = _last_months(6)
        start = datetime.strptime(months[0] + "-01", "%Y-%m-%d")
        signups, revenue = defaultdict(int), defaultdict(int)
        for (created,) in db.query(User.created_at).filter(User.created_at >= start).all():
            signups[created.strftime("%Y-%m")] += 1
        for created, cents in db.query(BillingInvoice.created_at, BillingInvoice.amount_cents) \
                .filter(BillingInvoice.status == "paid", BillingInvoice.created_at >= start).all():
            revenue[created.strftime("%Y-%m")] += cents or 0

        return {
            "total_users": total_users,
            "new_users_7d": db.query(User).filter(User.created_at >= d7).count(),
            "new_users_30d": db.query(User).filter(User.created_at >= d30).count(),
            "active_users_30d": db.query(User).filter(User.last_login_at >= d30).count(),
            "suspended_users": db.query(User).filter(User.is_active == False).count(),  # noqa: E712
            "plan_counts": plan_counts,
            "paying_customers": paying_total,
            "paying_by_plan": {p: paying[p] for p in PAID_PLANS},
            "mrr_cents": mrr_cents,
            "past_due": db.query(User).filter(User.subscription_status == "past_due").count(),
            "pending_cancellations": db.query(User).filter(
                User.cancel_at_period_end == True, User.subscription_status.in_(LIVE_STATUSES)).count(),  # noqa: E712
            "canceled_30d": canceled_30d,
            "churn_rate_30d": churn,                      # % ; None until there's any subscription history
            "revenue_total_cents": revenue_total or 0,
            "revenue_30d_cents": revenue_30d or 0,
            "total_datasets": db.query(UploadedFile).count(),
            "datasets_30d": db.query(UploadedFile).filter(UploadedFile.uploaded_at >= d30).count(),
            "signups_by_month": [{"month": m, "count": signups[m]} for m in months],
            "revenue_by_month": [{"month": m, "cents": revenue[m]} for m in months],
        }

    # ── Users ────────────────────────────────────────────────────────────────

    @staticmethod
    def _user_row(u: User, datasets: int) -> dict:
        return {
            "id": u.id, "name": u.name, "email": u.email, "organization": u.organization,
            "role": u.role or "user", "plan": plan_defs.normalize_plan(u.plan),
            "subscription_status": u.subscription_status if u.stripe_subscription_id else "none",
            "cancel_at_period_end": bool(u.cancel_at_period_end),
            "is_active": bool(u.is_active), "datasets": datasets,
            "created_at": _iso(u.created_at), "last_login_at": _iso(u.last_login_at),
        }

    def list_users(self, page: int, limit: int, search: str, plan: str, status: str) -> dict:
        q = self.db.query(User)
        term = (search or "").strip()
        if term:
            like = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            q = q.filter(or_(User.email.ilike(like, escape="\\"),
                             User.name.ilike(like, escape="\\"),
                             User.organization.ilike(like, escape="\\")))
        if plan in plan_defs.PLANS:
            q = q.filter(User.plan == plan)
        if status == "active":
            q = q.filter(User.is_active == True)  # noqa: E712
        elif status == "suspended":
            q = q.filter(User.is_active == False)  # noqa: E712
        elif status == "past_due":
            q = q.filter(User.subscription_status == "past_due")

        total = q.count()
        rows = q.order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * limit).limit(limit).all()
        counts = {}
        if rows:
            counts = dict(
                self.db.query(UploadedFile.user_id, func.count(UploadedFile.id))
                .filter(UploadedFile.user_id.in_([u.id for u in rows]))
                .group_by(UploadedFile.user_id).all()
            )
        return {
            "users": [self._user_row(u, counts.get(u.id, 0)) for u in rows],
            "total": total, "page": page, "limit": limit,
            "pages": max(1, -(-total // limit)),
        }

    def _target(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        return user

    def user_detail(self, user_id: int) -> dict:
        user = self._target(user_id)
        files = (self.db.query(UploadedFile).filter(UploadedFile.user_id == user.id)
                 .order_by(UploadedFile.uploaded_at.desc()).all())
        billing = BillingService(self.db)
        return {
            "user": self._user_row(user, len(files)),
            "billing": billing.status(user),
            "has_stripe_subscription": billing._has_live_subscription(user),
            "datasets": [{
                "id": f.id, "name": f.original_name, "rows": f.row_count, "size_bytes": f.file_size,
                "status": f.status, "uploaded_at": _iso(f.uploaded_at),
            } for f in files],
            "invoices": billing.history(user),
        }

    # ── Guarded actions ──────────────────────────────────────────────────────

    def _guard(self, admin: User, target: User) -> None:
        if target.id == admin.id:
            raise HTTPException(status_code=400, detail="You can't do that to your own account.")
        if (target.role or "user") == "admin":
            raise HTTPException(
                status_code=403,
                detail="Admin accounts can't be changed from the panel. Use scripts/manage_users.py on the server.")

    def _log(self, admin: User, action: str, target: User, detail: str = "") -> None:
        self.db.add(AdminAuditLog(admin_id=admin.id, admin_email=admin.email, action=action,
                                  target_user_id=target.id, target_email=target.email, detail=detail[:500]))
        logger.info(f"ADMIN {admin.email}: {action} -> {target.email} {detail}")

    def set_active(self, admin: User, user_id: int, active: bool) -> dict:
        target = self._target(user_id)
        self._guard(admin, target)
        if bool(target.is_active) != active:
            target.is_active = active
            self._log(admin, "restore" if active else "suspend", target)
            self.db.commit()
        return self._user_row(target, self.db.query(UploadedFile).filter(UploadedFile.user_id == target.id).count())

    def set_plan(self, admin: User, user_id: int, plan: str) -> dict:
        if plan not in plan_defs.PLANS:
            raise HTTPException(status_code=422, detail="Unknown plan.")
        target = self._target(user_id)
        self._guard(admin, target)
        if BillingService._has_live_subscription(target):
            raise HTTPException(
                status_code=409,
                detail="This customer has an active Stripe subscription — change or cancel it in Stripe "
                       "(or ask them to use Billing). A manual override would be overwritten by the next webhook.")
        old, target.plan = target.plan, plan
        self._log(admin, "set_plan", target, f"{old} -> {plan} (manual, no Stripe subscription)")
        self.db.commit()
        return self._user_row(target, self.db.query(UploadedFile).filter(UploadedFile.user_id == target.id).count())

    def delete_user(self, admin: User, user_id: int) -> dict:
        target = self._target(user_id)
        self._guard(admin, target)
        if BillingService._has_live_subscription(target):
            raise HTTPException(
                status_code=409,
                detail="This customer has an active Stripe subscription. Cancel it in Stripe first, "
                       "otherwise their card would keep being charged for a deleted account.")
        files = self.db.query(UploadedFile).filter(UploadedFile.user_id == target.id).all()
        for f in files:
            safe_delete(Path(f.file_path))
        self._log(admin, "delete_user", target, f"removed {len(files)} dataset(s)")
        self.db.query(PredictionResult).filter(PredictionResult.user_id == target.id).delete()
        self.db.query(UploadedFile).filter(UploadedFile.user_id == target.id).delete()
        self.db.query(BillingInvoice).filter(BillingInvoice.user_id == target.id).delete()
        self.db.query(PasswordResetToken).filter(PasswordResetToken.user_id == target.id).delete()
        self.db.delete(target)
        self.db.commit()
        return {"success": True, "deleted_user_id": user_id, "datasets_removed": len(files)}

    # ── Audit trail ──────────────────────────────────────────────────────────

    def activity(self, page: int, limit: int) -> dict:
        q = self.db.query(AdminAuditLog)
        total = q.count()
        rows = q.order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc()) \
                .offset((page - 1) * limit).limit(limit).all()
        return {
            "entries": [{"id": r.id, "admin": r.admin_email, "action": r.action, "target": r.target_email,
                         "detail": r.detail, "at": _iso(r.created_at)} for r in rows],
            "total": total, "page": page, "pages": max(1, -(-total // limit)),
        }
