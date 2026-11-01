"""
services/email_service.py
─────────────────────────
Minimal transactional email over SMTP (standard library only — no extra dependency).

Works with Gmail (app password), Resend, SendGrid, Mailgun, Amazon SES… anything SMTP.

Never raises: a failing mail server must not turn "forgot password" into a 500
(that would also reveal which emails exist). Failures are logged instead.

Development: with no SMTP_HOST the email is printed to the backend terminal so you
can click the reset link without setting anything up. In PRODUCTION without SMTP the
body is NOT logged (it contains a secret link) — only a warning is.
"""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from loguru import logger

from app.config import settings


def send_email(to: str, subject: str, text: str, html: Optional[str] = None) -> bool:
    if not settings.SMTP_HOST:
        if settings.is_production:
            logger.warning(f"SMTP not configured; email to {to} ('{subject}') was NOT sent")
        else:
            logger.info(f"\n📧 EMAIL (SMTP not configured — shown here instead of sent)\n"
                        f"   To: {to}\n   Subject: {subject}\n\n{text}\n")
        return False

    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_STARTTLS:
                server.starttls(context=ssl.create_default_context())
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:  # noqa: BLE001 — see module docstring
        logger.error(f"Failed to send email to {to}: {type(e).__name__}: {e}")
        return False


def send_password_reset_email(to: str, name: str, reset_url: str, minutes: int) -> bool:
    first = (name or "there").split()[0]
    text = (
        f"Hi {first},\n\n"
        f"We received a request to reset your SalesIQ password. Open this link to choose a new one "
        f"(it works once and expires in {minutes} minutes):\n\n{reset_url}\n\n"
        f"If you didn't ask for this, you can ignore this email — your password won't change.\n\n— SalesIQ"
    )
    html = (
        f"<p>Hi {first},</p>"
        f"<p>We received a request to reset your SalesIQ password. Click the button to choose a new one "
        f"(it works once and expires in {minutes} minutes).</p>"
        f'<p><a href="{reset_url}" style="background:#0ea5e9;color:#fff;padding:10px 18px;border-radius:8px;'
        f'text-decoration:none;display:inline-block">Reset password</a></p>'
        f'<p style="color:#666;font-size:13px">Or paste this link into your browser:<br>{reset_url}</p>'
        f"<p style=\"color:#666;font-size:13px\">If you didn't ask for this, ignore this email — your password won't change.</p>"
    )
    return send_email(to, "Reset your SalesIQ password", text, html)
