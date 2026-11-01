# Admin panel, customer accounts & password reset

## 1. Become the admin (do this first — it also fixes a locked-out login)

You can't become admin by signing up (that would let anyone who registers your email first take over).
Admin rights are granted from the server, in the `backend` folder:

```
python scripts/manage_users.py list                                   # who exists? is your account there?
python scripts/manage_users.py create-admin you@example.com "Your Name"   # new account — asks for a password (hidden)
python scripts/manage_users.py make-admin you@example.com             # …or promote an account you already signed up with
python scripts/manage_users.py set-password you@example.com           # forgot it / locked out → set a new one (asks, hidden)
```
Then log in on the website — admins land in the **admin panel** automatically.

> "Incorrect email or password" is the same message whether the password is wrong or the account doesn't
> exist (deliberate — it stops people discovering who has an account). Run `list` to see which it is.
> If you reset the database, accounts are gone and need creating again.

## 2. Two separate areas

| | Customers (organisations) | You (admin) |
|---|---|---|
| Where | `/` — dashboard, upload, analytics, predictions, billing | `/admin` — own sidebar, amber "ADMIN PANEL" badge |
| Sees | only their own data | all customers, revenue, activity |
| Enforced by | login + per-user data filtering | `require_admin` on every `/api/admin/*` route (customers get **403** even with a valid login) |

Customers can enter an optional **company / organisation** at signup; it shows in their sidebar and in your customer list.
Admins can still use the normal app (sidebar has an *Admin panel* link; the admin sidebar has *Switch to customer view*).

**Admin panel pages**
- **Overview** — MRR, paying customers, revenue (30 days / all time), churn, sign-ups, active users, datasets, plan mix, monthly charts, and a "needs attention" banner (failed payments, pending cancellations, suspended).
- **Customers** — search (name / email / organisation), filter by plan and status, pagination → click a customer for details.
- **Customer detail** — profile, billing, datasets, invoices, and actions: **Suspend / Restore**, **Set plan** (grant a plan without payment), **Delete**.
- **Activity log** — every admin action, kept even after a customer is deleted.

**Guard rails (all enforced by the server and covered by tests)**
- You can't suspend / delete / re-plan **yourself** or **another admin** from the panel (use the script) — a hijacked admin session can't remove the other admins.
- A customer **paying through Stripe** can't be deleted or re-planned here — otherwise their card would keep being charged for a deleted account, or the next webhook would overwrite your change. Cancel in Stripe first.
- Deleting a customer removes their account, datasets, **uploaded files on disk**, and billing history. You must type their email to confirm.
- Suspending signs them out immediately and blocks login; their data is kept.
- MRR counts only live Stripe subscriptions (plans you grant manually are excluded).

## 3. Forgot password

Login page → **Forgot password?** → email → link → choose a new password.

- The reply is identical whether or not the email is registered.
- The link works **once** and expires after **60 minutes**; only a hash of it is stored.
- Max **3** reset emails per account per hour (stops email-bombing).
- Resetting **signs the account out everywhere** — sessions that existed before the reset stop working.
- Suspended accounts can't reset.

**Development (no email server):** the email is printed in the **backend terminal**:
```
📧 EMAIL (SMTP not configured — shown here instead of sent)
   To: you@example.com
   ...  http://localhost:5173/reset-password?token=...
```
Click that link. **Production:** configure SMTP in `backend/.env` — any provider works:
```
# Gmail (turn on 2-step verification, then create an "App password")
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-16-char-app-password
EMAIL_FROM=SalesIQ <you@gmail.com>

# Resend:  SMTP_HOST=smtp.resend.com  SMTP_USER=resend  SMTP_PASSWORD=<your Resend API key>
```
With `APP_ENV=production` and no SMTP, reset links are **not** logged (they're secrets) — only a warning.
Also set `FRONTEND_URL` to your real site so links point to the right place.

## 4. Not included yet
- Teams: several people sharing one organisation account (invites, member roles). Today each login is its own account; "organisation" is a label.
- Login rate-limiting / lockout after repeated wrong passwords, and email verification at signup.
- Welcome / receipt emails (the email service is ready for them — Step 6).

## 5. Tests
```
cd backend
pytest        # 215 tests: auth, billing, admin permissions, password reset, user script
```
