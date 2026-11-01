"""
routes/admin.py — the founder's admin panel API.

EVERY route depends on `require_admin`, so a customer's valid login is still a 403 here.

  GET    /api/admin/stats                     — platform overview numbers + 6-month series
  GET    /api/admin/users                     — search / filter / paginate customers
  GET    /api/admin/users/{id}                — one customer: profile, billing, datasets, invoices
  POST   /api/admin/users/{id}/suspend        — block login (data kept)
  POST   /api/admin/users/{id}/restore        — unblock
  PUT    /api/admin/users/{id}/plan           — manual plan override (only if no Stripe subscription)
  DELETE /api/admin/users/{id}                — delete customer + their data + files
  GET    /api/admin/activity                  — audit log of admin actions
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import User, get_db
from app.services.admin_service import AdminService
from app.utils.security import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


class PlanBody(BaseModel):
    plan: Literal["free", "starter", "pro"]


@router.get("/stats")
def stats(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return AdminService(db).stats()


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    plan: Literal["all", "free", "starter", "pro"] = "all",
    status: Literal["all", "active", "suspended", "past_due"] = "all",
    admin: User = Depends(require_admin), db: Session = Depends(get_db),
):
    return AdminService(db).list_users(page, limit, search, plan, status)


@router.get("/users/{user_id}")
def user_detail(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return AdminService(db).user_detail(user_id)


@router.post("/users/{user_id}/suspend")
def suspend(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return AdminService(db).set_active(admin, user_id, False)


@router.post("/users/{user_id}/restore")
def restore(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return AdminService(db).set_active(admin, user_id, True)


@router.put("/users/{user_id}/plan")
def set_plan(user_id: int, body: PlanBody, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return AdminService(db).set_plan(admin, user_id, body.plan)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return AdminService(db).delete_user(admin, user_id)


@router.get("/activity")
def activity(page: int = Query(1, ge=1), limit: int = Query(30, ge=1, le=100),
             admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return AdminService(db).activity(page, limit)
