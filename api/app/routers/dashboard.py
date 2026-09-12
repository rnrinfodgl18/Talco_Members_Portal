from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ImportBatch, Invoice, Notification, Party, Receipt, Tannery
from app.models.auth import User
from app.security import current_user, require_roles
from app.routers.portal import available_accounts, statement_rows

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/admin")
def admin_dashboard(_: User = Depends(require_roles("talco_admin", "talco_staff")),
                    session: Session = Depends(get_db)):
    invoice_total = session.scalar(select(func.coalesce(func.sum(Invoice.gross_amount), 0)).where(
        Invoice.is_cancelled.is_(False))) or Decimal(0)
    receipt_total = session.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(
        Receipt.is_cancelled.is_(False))) or Decimal(0)
    opening = session.scalar(select(func.coalesce(func.sum(Party.opening_amount), 0))) or Decimal(0)
    recent = session.scalars(select(ImportBatch).order_by(ImportBatch.uploaded_at.desc()).limit(5)).all()
    return {"tanneries": session.scalar(select(func.count()).select_from(Tannery)) or 0,
        "members": session.scalar(select(func.count()).select_from(User).where(
            User.role.in_({"member", "member_staff", "lessee"}), User.active.is_(True))) or 0,
        "unverified_emails": session.scalar(select(func.count()).select_from(User).where(
            User.role.in_({"member", "member_staff", "lessee"}), User.active.is_(True),
            User.email_verified_at.is_(None))) or 0,
        "outstanding": str(opening + invoice_total - receipt_total),
        "invoice_total": str(invoice_total), "receipt_total": str(receipt_total),
        "recent_imports": [{"id": row.id, "file_name": row.file_name, "status": row.status,
            "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None} for row in recent]}


@router.get("/member")
def member_dashboard(user: User = Depends(current_user), session: Session = Depends(get_db)):
    accounts = [] if (user.role not in {"talco_admin", "talco_staff"} and not user.ledger_access_configured and not user.tannery_id) else available_accounts(session, user)
    summaries = []
    total = Decimal(0)
    for account in accounts:
        rows, _, _, _ = statement_rows(session, user, account, None)
        balance = Decimal(rows[-1]["balance"]) if rows else Decimal(0)
        total += balance
        summaries.append({"id": account.id, "code": f"ACC-{account.id:04d}",
                          "name": account.name, "outstanding": str(balance)})
    unread = session.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None))) or 0
    return {"accounts": summaries, "total_outstanding": str(total), "unread_notifications": unread,
            "email_verified": bool(user.email_verified_at)}
