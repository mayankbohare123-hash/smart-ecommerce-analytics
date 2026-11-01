"""
scripts/setup_stripe.py
───────────────────────
Creates the SalesIQ products + monthly prices in YOUR Stripe account and prints
the lines to paste into backend/.env.   Safe to run repeatedly: prices are found
by `lookup_key`, never duplicated.

    cd backend
    python scripts/setup_stripe.py            # uses STRIPE_SECRET_KEY from .env (test mode)
    python scripts/setup_stripe.py --live     # required if the key is a LIVE key (sk_live_...)
"""

import os
import sys

import stripe
from dotenv import load_dotenv

PLANS = [  # (plan key, product name, price in cents)
    ("starter", "SalesIQ Starter", 1900),
    ("pro", "SalesIQ Pro", 4900),
]


def ensure_price(plan: str, name: str, amount_cents: int) -> str:
    lookup_key = f"salesiq_{plan}_monthly"
    existing = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
    if existing.data:
        print(f"  ✓ {name}: price already exists ({existing.data[0].id})")
        return existing.data[0].id
    product = stripe.Product.create(name=name, metadata={"plan": plan})
    price = stripe.Price.create(
        product=product.id,
        unit_amount=amount_cents,
        currency="usd",
        recurring={"interval": "month"},
        lookup_key=lookup_key,
    )
    print(f"  + {name}: created ${amount_cents / 100:.0f}/month ({price.id})")
    return price.id


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    load_dotenv()
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        print("STRIPE_SECRET_KEY is not set. Add it to backend/.env first (Stripe → Developers → API keys).")
        return 1
    if key.startswith("sk_live_") and "--live" not in argv:
        print("That is a LIVE key. Re-run with --live if you really mean to create live products.")
        return 1
    stripe.api_key = key
    print(f"Stripe mode: {'LIVE' if key.startswith('sk_live_') else 'test'}")
    ids = {plan: ensure_price(plan, name, cents) for plan, name, cents in PLANS}
    print("\nAdd these to backend/.env:\n")
    print(f"STRIPE_STARTER_PRICE_ID={ids['starter']}")
    print(f"STRIPE_PRO_PRICE_ID={ids['pro']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
