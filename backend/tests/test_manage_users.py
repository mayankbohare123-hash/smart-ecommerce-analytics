"""scripts/manage_users.py — how the founder becomes admin, and recovers a locked-out account."""

import uuid
from unittest.mock import patch

import pytest

from app.database import SessionLocal, User, create_tables, drop_tables
from app.utils.security import hash_password, verify_password
from scripts import manage_users

pytestmark = pytest.mark.real_auth


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    create_tables()
    yield
    drop_tables()


def run(*argv, passwords=()):
    with patch("scripts.manage_users.getpass.getpass", side_effect=list(passwords)):
        return manage_users.main(list(argv))


def get(email):
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    if u:
        db.expunge(u)
    db.close()
    return u


def make_customer(email=None):
    email = email or f"c{uuid.uuid4().hex[:8]}@test.com"
    db = SessionLocal()
    db.add(User(email=email, name="Cust", hashed_password=hash_password("original-pw-1"), plan="free", is_active=True))
    db.commit(); db.close()
    return email


def test_create_admin_makes_a_working_admin_account(capsys):
    email = f"founder{uuid.uuid4().hex[:6]}@test.com"
    assert run("create-admin", email, "The Founder", passwords=["a-strong-pass-1", "a-strong-pass-1"]) == 0
    u = get(email)
    assert u.role == "admin" and u.name == "The Founder" and u.is_active
    assert verify_password("a-strong-pass-1", u.hashed_password)
    assert "a-strong-pass-1" not in capsys.readouterr().out          # the password is never printed


def test_prompt_rejects_short_and_mismatched_passwords_then_accepts():
    email = f"p{uuid.uuid4().hex[:6]}@test.com"
    seq = ["short", "long-enough-1", "different-1", "good-password-1", "good-password-1"]
    assert run("create-admin", email, passwords=seq) == 0
    assert verify_password("good-password-1", get(email).hashed_password)


def test_create_admin_on_existing_account_promotes_without_touching_password():
    email = make_customer()
    assert run("create-admin", email) == 0                            # no password prompt needed
    u = get(email)
    assert u.role == "admin" and verify_password("original-pw-1", u.hashed_password)


def test_make_admin_and_remove_admin():
    a, b = make_customer(), make_customer()
    run("make-admin", a); run("make-admin", b)
    assert run("remove-admin", a) == 0 and get(a).role == "user"


def test_refuses_to_remove_the_last_admin():
    db = SessionLocal(); db.query(User).update({"role": "user"}); db.commit(); db.close()
    only = make_customer(); run("make-admin", only)
    assert run("remove-admin", only) == 1
    assert get(only).role == "admin"


def test_set_password_recovers_a_locked_out_account_and_revokes_old_sessions():
    email = make_customer()
    assert run("set-password", email, passwords=["recovered-pw-9", "recovered-pw-9"]) == 0
    u = get(email)
    assert verify_password("recovered-pw-9", u.hashed_password) and not verify_password("original-pw-1", u.hashed_password)
    assert u.password_changed_at is not None


def test_unknown_email_is_reported_not_crashed(capsys):
    assert run("set-password", "nobody@test.com") == 1
    assert "No user with email" in capsys.readouterr().out


def test_list_shows_roles_and_empty_state(capsys):
    db = SessionLocal(); db.query(User).delete(); db.commit(); db.close()
    assert run("list") == 0 and "No users yet" in capsys.readouterr().out
    email = make_customer(); run("make-admin", email)
    run("list")
    out = capsys.readouterr().out
    assert email in out and "role=admin" in out
