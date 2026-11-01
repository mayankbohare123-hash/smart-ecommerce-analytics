"""
plans.py
────────
Single source of truth for subscription plans.

Before this file existed, upload limits were hard-coded in three places
(upload route, /auth/me, config) and disagreed with each other (pro was
"999" in two of them). Everything now reads from here.

`upload_limit = None` means unlimited.
"""

from typing import Optional

from app.config import settings

PLAN_ORDER = ["free", "starter", "pro"]

PLANS = {
    "free": {
        "name": "Free",
        "price_cents": 0,
        "upload_limit": 1,
        "tagline": "Try SalesIQ on one dataset",
        "features": ["1 dataset", "KPI dashboard & 4 charts", "30-day ML forecast"],
    },
    "starter": {
        "name": "Starter",
        "price_cents": 1900,
        "upload_limit": 5,
        "tagline": "For growing stores",
        "features": ["5 datasets", "Full analytics & all charts", "30-day ML forecast", "Email support"],
        "popular": True,
    },
    "pro": {
        "name": "Pro",
        "price_cents": 4900,
        "upload_limit": None,
        "tagline": "For serious sellers",
        "features": ["Unlimited datasets", "Full analytics & all charts", "30-day ML forecast", "Priority support"],
    },
}


def normalize_plan(plan: Optional[str]) -> str:
    return plan if plan in PLANS else "free"


def upload_limit(plan: Optional[str]) -> Optional[int]:
    """Max datasets for a plan; None = unlimited."""
    return PLANS[normalize_plan(plan)]["upload_limit"]


def price_id_for(plan: str) -> str:
    return {"starter": settings.STRIPE_STARTER_PRICE_ID, "pro": settings.STRIPE_PRO_PRICE_ID}.get(plan, "")


def plan_for_price_id(price_id: Optional[str]) -> Optional[str]:
    """Reverse lookup: Stripe price id → plan key. None if the price is unknown."""
    if not price_id:
        return None
    for plan in ("starter", "pro"):
        configured = price_id_for(plan)
        if configured and configured == price_id:
            return plan
    return None
