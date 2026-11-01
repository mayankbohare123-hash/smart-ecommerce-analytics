"""
scripts/manage_users.py
───────────────────────
Server-side user administration. Run from the backend folder:

    python scripts/manage_users.py list
    python scripts/manage_users.py create-admin you@example.com "Your Name"   # asks for a password
    python scripts/manage_users.py make-admin  someone@example.com
    python scripts/manage_users.py remove-admin someone@example.com
    python scripts/manage_users.py set-password you@example.com               # recovery: asks for a new password

WHY a script and not a signup option? Admin rights must never be obtainable through the
website. (If the app auto-promoted a particular email, anyone could register that email
first and become admin.) Passwords are typed at a hidden prompt — never on the command
line, so they don't end up in your shell history or in chat.
"""

import argparse
import getpass
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # so `app` imports when run as a script

from app.database import SessionLocal, User, create_tables  # noqa: E402
from app.utils.security import hash_password                 # noqa: E402


def _prompt_password() -> str:
    while True:
        pw = getpass.getpass("New password (min 8 characters, hidden): ")
        if len(pw) < 8:
            print("  Too short — use at least 8 characters.")
            continue
        if pw != getpass.getpass("Repeat password: "):
            print("  Passwords didn't match — try again.")
            continue
        return pw


def _find(db, email: str):
    return db.query(User).filter(User.email == email.strip().lower()).first()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SalesIQ user administration")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    c = sub.add_parser("create-admin"); c.add_argument("email"); c.add_argument("name", nargs="?", default="")
    for name in ("make-admin", "remove-admin", "set-password"):
        sub.add_parser(name).add_argument("email")
    args = parser.parse_args(argv)

    create_tables()                       # also works on a brand-new database
    db = SessionLocal()
    try:
        if args.cmd == "list":
            users = db.query(User).order_by(User.id).all()
            if not users:
                print("No users yet. Create yourself with:  python scripts/manage_users.py create-admin you@example.com \"Your Name\"")
            for u in users:
                print(f"#{u.id:<4} {u.email:<35} role={u.role or 'user':<6} plan={u.plan:<8} "
                      f"{'active' if u.is_active else 'SUSPENDED'}  {u.organization or ''}")
            return 0

        user = _find(db, args.email)

        if args.cmd == "create-admin":
            if user:
                user.role = "admin"
                db.commit()
                print(f"{user.email} already existed — promoted to admin. (Use set-password if you also need a new password.)")
                return 0
            email = args.email.strip().lower()
            if "@" not in email:
                print("That doesn't look like an email address.")
                return 1
            pw = _prompt_password()
            db.add(User(email=email, name=args.name.strip() or email.split("@")[0], hashed_password=hash_password(pw),
                        role="admin", plan="pro", is_active=True, created_at=datetime.utcnow()))
            db.commit()
            print(f"Admin account created for {email}. Log in on the website and you'll land in the admin panel.")
            return 0

        if user is None:
            print(f"No user with email {args.email}. Run 'list' to see who exists.")
            return 1

        if args.cmd == "make-admin":
            user.role = "admin"
            db.commit(); print(f"{user.email} is now an admin.")
        elif args.cmd == "remove-admin":
            others = db.query(User).filter(User.role == "admin", User.id != user.id).count()
            if (user.role or "user") == "admin" and others == 0:
                print("Refusing: that's the last admin — you'd lock yourself out of the panel.")
                return 1
            user.role = "user"
            db.commit(); print(f"{user.email} is no longer an admin.")
        elif args.cmd == "set-password":
            user.hashed_password = hash_password(_prompt_password())
            user.password_changed_at = datetime.utcnow()      # signs the account out everywhere
            db.commit(); print(f"Password updated for {user.email}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
