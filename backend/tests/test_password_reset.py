"""
tests/test_password_reset.py — forgot / reset password.

The properties that matter (each is a classic way these flows get hacked):
  • the response never reveals whether an email is registered
  • the emailed token works ONCE, expires, and only its hash is stored
  • resetting signs out sessions that existed before it
  • email-bombing a user is capped
"""

import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.database import PasswordResetToken, SessionLocal, User, create_tables, drop_tables
from app.main import app

pytestmark = pytest.mark.real_auth

OLD_PW, NEW_PW = "old-password-1", "brand-new-pw-2"


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
def account(client):
    email = f"r{uuid.uuid4().hex[:10]}@test.com"
    r = client.post("/api/auth/signup", json={"name": "Reset Tester", "email": email, "password": OLD_PW})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"email": email, "access": body["access_token"], "refresh": body["refresh_token"]}


def forgot(client, email):
    """Call forgot-password with the mail function mocked; return (response, mock)."""
    with patch("app.routes.auth.send_password_reset_email") as mail:
        r = client.post("/api/auth/forgot-password", json={"email": email})
    return r, mail


def token_from(mail) -> str:
    url = mail.call_args.args[2]
    return parse_qs(urlparse(url).query)["token"][0]


def login(client, email, pw):
    return client.post("/api/auth/login", json={"email": email, "password": pw})


class TestForgotPassword:

    def test_registered_and_unknown_emails_get_identical_responses(self, client, account):
        known, _ = forgot(client, account["email"])
        unknown, _ = forgot(client, "nobody-here@test.com")
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()

    def test_email_sent_only_for_real_accounts(self, client, account):
        _, mail_known = forgot(client, account["email"])
        _, mail_unknown = forgot(client, "ghost@test.com")
        mail_known.assert_called_once()
        mail_unknown.assert_not_called()

    def test_email_contains_a_link_to_the_frontend(self, client, account):
        _, mail = forgot(client, account["email"])
        to, name, url, minutes = mail.call_args.args
        assert to == account["email"] and name == "Reset Tester" and minutes == 60
        assert url.startswith("http://localhost:5173/reset-password?token=")

    def test_email_matching_ignores_case_and_spaces(self, client, account):
        _, mail = forgot(client, f"  {account['email'].upper()}  ")
        mail.assert_called_once()

    def test_only_a_hash_of_the_token_is_stored(self, client, account):
        _, mail = forgot(client, account["email"])
        raw = token_from(mail)
        db = SessionLocal()
        rows = db.query(PasswordResetToken).all()
        db.close()
        assert all(r.token_hash != raw for r in rows)            # raw token never persisted
        assert any(len(r.token_hash) == 64 for r in rows)        # sha-256 hex

    def test_email_bombing_is_capped(self, client, account):
        sent = 0
        for _ in range(6):
            _, mail = forgot(client, account["email"])
            sent += mail.call_count
        assert sent == 3                                          # PASSWORD_RESET_MAX_PER_HOUR

    def test_suspended_accounts_get_no_email(self, client, account):
        db = SessionLocal()
        db.query(User).filter(User.email == account["email"]).update({"is_active": False})
        db.commit(); db.close()
        r, mail = forgot(client, account["email"])
        assert r.status_code == 200
        mail.assert_not_called()


class TestResetPassword:

    def start(self, client, account):
        _, mail = forgot(client, account["email"])
        return token_from(mail)

    def test_full_flow_new_password_works_old_does_not(self, client, account):
        token = self.start(client, account)
        r = client.post("/api/auth/reset-password", json={"token": token, "password": NEW_PW})
        assert r.status_code == 200
        assert login(client, account["email"], NEW_PW).status_code == 200
        assert login(client, account["email"], OLD_PW).status_code == 401

    def test_token_works_only_once(self, client, account):
        token = self.start(client, account)
        assert client.post("/api/auth/reset-password", json={"token": token, "password": NEW_PW}).status_code == 200
        again = client.post("/api/auth/reset-password", json={"token": token, "password": "another-pw-3"})
        assert again.status_code == 400
        assert login(client, account["email"], NEW_PW).status_code == 200      # not overwritten by the replay

    def test_expired_token_rejected(self, client, account):
        token = self.start(client, account)
        db = SessionLocal()
        db.query(PasswordResetToken).update({"expires_at": datetime.utcnow() - timedelta(minutes=1)})
        db.commit(); db.close()
        assert client.post("/api/auth/reset-password", json={"token": token, "password": NEW_PW}).status_code == 400
        assert login(client, account["email"], OLD_PW).status_code == 200

    def test_garbage_token_rejected(self, client):
        r = client.post("/api/auth/reset-password", json={"token": "x" * 40, "password": NEW_PW})
        assert r.status_code == 400 and "invalid or has expired" in r.json()["detail"]

    def test_short_password_rejected_and_token_still_usable(self, client, account):
        token = self.start(client, account)
        assert client.post("/api/auth/reset-password", json={"token": token, "password": "short"}).status_code == 422
        assert client.post("/api/auth/reset-password", json={"token": token, "password": NEW_PW}).status_code == 200

    def test_very_long_password_is_fine(self, client, account):
        token = self.start(client, account)
        long_pw = "p" * 300
        assert client.post("/api/auth/reset-password", json={"token": token, "password": long_pw}).status_code == 200
        assert login(client, account["email"], long_pw).status_code == 200

    def test_using_one_reset_link_kills_all_other_outstanding_links(self, client, account):
        t1 = self.start(client, account)
        t2 = self.start(client, account)
        assert client.post("/api/auth/reset-password", json={"token": t1, "password": NEW_PW}).status_code == 200
        assert client.post("/api/auth/reset-password", json={"token": t2, "password": "sneaky-pw-9"}).status_code == 400

    def test_suspended_account_cannot_reset(self, client, account):
        token = self.start(client, account)
        db = SessionLocal()
        db.query(User).filter(User.email == account["email"]).update({"is_active": False})
        db.commit(); db.close()
        assert client.post("/api/auth/reset-password", json={"token": token, "password": NEW_PW}).status_code == 400


class TestSessionsAreRevoked:

    def test_reset_signs_out_sessions_that_existed_before(self, client, account):
        old_h = {"Authorization": f"Bearer {account['access']}"}
        assert client.get("/api/auth/me", headers=old_h).status_code == 200
        _, mail = forgot(client, account["email"])
        token = token_from(mail)

        time.sleep(1.1)                       # JWT timestamps have 1-second resolution
        assert client.post("/api/auth/reset-password", json={"token": token, "password": NEW_PW}).status_code == 200

        assert client.get("/api/auth/me", headers=old_h).status_code == 401                      # stolen access token dead
        refresh = client.post("/api/auth/refresh", json={"refresh_token": account["refresh"]})
        assert refresh.status_code == 401                                                       # …and so is its refresh token

        fresh = login(client, account["email"], NEW_PW).json()["access_token"]
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {fresh}"}).status_code == 200

    def test_session_created_right_after_reset_works_immediately(self, client, account):
        _, mail = forgot(client, account["email"])
        client.post("/api/auth/reset-password", json={"token": token_from(mail), "password": NEW_PW})
        tok = login(client, account["email"], NEW_PW).json()["access_token"]      # same second as the reset
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


class TestLoginHardening:

    def test_unknown_email_still_burns_a_password_check_so_timing_does_not_leak(self, client):
        with patch("app.routes.auth._burn_password_check") as burn:
            r = login(client, "does-not-exist@test.com", "whatever-123")
        assert r.status_code == 401 and r.json()["detail"] == "Incorrect email or password."
        burn.assert_called_once()

    def test_same_error_for_wrong_password_and_unknown_email(self, client, account):
        wrong = login(client, account["email"], "wrong-password-1")
        unknown = login(client, "does-not-exist@test.com", "wrong-password-1")
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json()

    def test_signup_stores_organisation_and_role_defaults_to_user(self, client):
        email = f"o{uuid.uuid4().hex[:8]}@test.com"
        r = client.post("/api/auth/signup", json={"name": "Org Person", "email": email, "password": OLD_PW,
                                                  "organization": "  Acme Traders  "})
        assert r.json()["user"]["role"] == "user"
        assert r.json()["user"]["organization"] == "Acme Traders"
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()["user"]
        assert (me["role"], me["organization"]) == ("user", "Acme Traders")

    def test_signup_cannot_grant_admin(self, client):
        email = f"a{uuid.uuid4().hex[:8]}@test.com"
        r = client.post("/api/auth/signup", json={"name": "Sneaky", "email": email, "password": OLD_PW,
                                                  "role": "admin"})
        assert r.json()["user"]["role"] == "user"
