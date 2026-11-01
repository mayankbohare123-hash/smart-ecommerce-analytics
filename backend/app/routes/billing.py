"""
routes/billing.py
─────────────────
Subscription & billing endpoints.

  GET  /api/billing/plans        — plan catalogue (public)
  GET  /api/billing/status       — my plan, usage, renewal date
  GET  /api/billing/history      — my invoices
  POST /api/billing/checkout     — start Stripe Checkout for a paid plan
  POST /api/billing/change-plan  — switch Starter ⇄ Pro (prorated)
  POST /api/billing/cancel       — cancel at period end
  POST /api/billing/resume       — undo a scheduled cancel
  POST /api/billing/portal       — Stripe customer portal (cards, invoices)
  POST /api/billing/sync         — pull my subscription from Stripe now
  POST /api/billing/webhook      — Stripe → us (signature-verified, no login)
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database import get_db, User
from app.services.billing_service import BillingService
from app.utils.security import get_current_user

router = APIRouter(prefix="/billing", tags=["Billing"])


class PlanRequest(BaseModel):
    plan: Literal["starter", "pro"]


@router.get("/plans", summary="Plan catalogue (public)")
def list_plans():
    return {"plans": BillingService.list_plans()}


@router.get("/status", summary="My plan, usage and renewal date")
def billing_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return BillingService(db).status(current_user)


@router.get("/history", summary="My billing history")
def billing_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"invoices": BillingService(db).history(current_user)}


@router.post("/checkout", summary="Start Stripe Checkout")
def checkout(body: PlanRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return BillingService(db).create_checkout(current_user, body.plan)


@router.post("/change-plan", summary="Switch between paid plans (prorated)")
def change_plan(body: PlanRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return BillingService(db).change_plan(current_user, body.plan)


@router.post("/cancel", summary="Cancel at the end of the billing period")
def cancel(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return BillingService(db).set_cancel_at_period_end(current_user, True)


@router.post("/resume", summary="Undo a scheduled cancellation")
def resume(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return BillingService(db).set_cancel_at_period_end(current_user, False)


@router.post("/portal", summary="Open the Stripe customer portal")
def portal(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return BillingService(db).create_portal(current_user)


@router.post("/sync", summary="Refresh my subscription from Stripe")
def sync(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return BillingService(db).refresh_from_stripe(current_user)


@router.post("/webhook", summary="Stripe webhook receiver", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    # The signature is computed over the RAW bytes, so read the body untouched.
    payload = await request.body()
    return await run_in_threadpool(BillingService(db).process_webhook, payload, stripe_signature)
