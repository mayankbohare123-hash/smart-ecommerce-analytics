# Stripe billing — setup guide (Step 2)

SalesIQ has three plans: **Free** (1 dataset), **Starter $19/mo** (5 datasets), **Pro $49/mo** (unlimited).
Everything works in Stripe **test mode** — no real money, no business verification needed.

## How it works

```
Pricing page ──► POST /api/billing/checkout ──► Stripe Checkout (hosted page, card entry)
                                                     │ pays
Stripe ──signed webhook──► POST /api/billing/webhook ──► plan updated in your database
Browser returns to /billing/success ──► server confirms with Stripe ──► "You're on Starter!"
```

The **webhook is the source of truth**. Landing on the success page does not grant anything by
itself. Webhooks are signature-verified, de-duplicated (Stripe retries), and protected against
out-of-order delivery. Upgrades/downgrades between paid plans are prorated by Stripe.

## One-time setup (≈10 minutes)

**1. Install dependencies** (adds `stripe`, switches password hashing to plain `bcrypt`)
```
cd backend
pip install -r requirements.txt
```

**2. Create a Stripe account** at https://dashboard.stripe.com/register and stay in **Test mode**
(toggle at the top of the dashboard).

**3. Add your secret key** — Dashboard → Developers → API keys → *Secret key* (`sk_test_...`).
Put it in `backend/.env`:
```
STRIPE_SECRET_KEY=sk_test_...
FRONTEND_URL=http://localhost:5173
```
Never commit `.env` (it is already in `.gitignore`) and never paste the secret key anywhere public.

**4. Create the two prices automatically**
```
python scripts/setup_stripe.py
```
It creates "SalesIQ Starter" ($19/mo) and "SalesIQ Pro" ($49/mo) and prints two lines. Paste them into `backend/.env`:
```
STRIPE_STARTER_PRICE_ID=price_...
STRIPE_PRO_PRICE_ID=price_...
```
(Safe to re-run — it reuses existing prices.)

**5. Turn on the Customer Portal** — Dashboard → Settings → Billing → *Customer portal* → **Activate test link**.
This is where customers update their card and download invoices. Without it, the
"Payment method & invoices" button shows an error.

**6. Forward webhooks to your laptop** with the Stripe CLI
(install: https://docs.stripe.com/stripe-cli):
```
stripe login
stripe listen --forward-to localhost:8000/api/billing/webhook
```
It prints a signing secret (`whsec_...`). Add it to `backend/.env`:
```
STRIPE_WEBHOOK_SECRET=whsec_...
```
Keep that terminal open while testing. **Restart the backend** after editing `.env`.

## Test it

1. Run backend + frontend, sign up, open **Billing → Change plan** (or the sidebar *Upgrade* link).
2. Click **Upgrade to Starter** → pay with test card `4242 4242 4242 4242`, any future expiry, any CVC.
3. You return to *"You're on Starter!"*. The sidebar badge shows STARTER and the dataset limit becomes 5.
4. Try **Switch to Pro**, **Cancel subscription**, **Resume subscription**, and the invoice list.
5. Payment-failure test: card `4000 0000 0000 0341` (attaches fine, then the charge fails) → status becomes *Payment failed*.

No Stripe CLI? Checkout still works (the success page pulls your subscription directly from Stripe),
but renewals, cancellations and failed payments only arrive through webhooks.

## Going live (later)

- Switch the dashboard to **Live mode**, re-run `scripts/setup_stripe.py --live` with the live key.
- Dashboard → Developers → Webhooks → **Add endpoint**: `https://YOUR-DOMAIN/api/billing/webhook`, events:
  `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
  `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`,
  `invoice.paid`, `invoice.payment_failed`. Use that endpoint's signing secret.
- Set `FRONTEND_URL` to your real site, and keep live keys only in the host's environment variables.
- **Check Stripe is available for your country / business type before launch.** Availability and
  onboarding rules differ by country and change over time. All Stripe code is isolated in
  `app/services/billing_service.py`, so switching providers later is a contained change.

## Behaviours worth knowing

- **Downgrades never delete data.** Someone with 4 datasets who falls back to Free keeps all 4;
  they just can't upload more until they upgrade or delete some (the Billing page explains this).
- **Cancelling keeps access until the period ends**, then Stripe sends `subscription.deleted` and the user returns to Free.
- **Failed payment** → status *Payment failed*, plan kept while Stripe retries; ends in cancel (→ Free) if it never succeeds.
- **No double billing:** a user who already pays can't start a second Checkout — they change plan instead.
- Not included yet (planned steps): email receipts/dunning (Step 6), tax (GST/VAT — Stripe Tax can be enabled later), admin revenue views (Step 8).

## Tests

```
cd backend
pytest              # 143 tests incl. 50 billing tests (Stripe is mocked — no account needed)
```
