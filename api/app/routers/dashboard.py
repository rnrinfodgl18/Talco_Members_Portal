from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ImportBatch, Invoice, Notification, Party, Receipt, StagingRow, Tannery
from app.models.auth import User
from app.security import current_user, require_roles
from app.routers.portal import available_accounts, statement_rows
from app.services.scope import scoped_query

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
        "pending_mappings": session.scalar(select(func.count()).select_from(StagingRow).where(StagingRow.status == "queued")) or 0,
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
    recent_invoices = []
    recent_receipts = []
    for account in accounts:
        invoice_query = scoped_query(select(Invoice).where(Invoice.party_id == account.id,
            Invoice.is_cancelled.is_(False)), Invoice, user, party_id=account.id)
        receipt_query = scoped_query(select(Receipt).where(Receipt.party_id == account.id,
            Receipt.is_cancelled.is_(False)), Receipt, user, party_id=account.id)
        recent_invoices.extend(session.scalars(invoice_query).all())
        recent_receipts.extend(session.scalars(receipt_query).all())
    recent_invoices = sorted(recent_invoices, key=lambda row: (row.invoice_date, row.id), reverse=True)[:5]
    recent_receipts = sorted(recent_receipts, key=lambda row: (row.receipt_date, row.id), reverse=True)
    latest_receipt = recent_receipts[0] if recent_receipts else None
    unread = session.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None))) or 0
    notices = session.scalars(select(Notification).where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc()).limit(3)).all()
    return {"accounts": summaries, "total_outstanding": str(total), "unread_notifications": unread,
            "email_verified": bool(user.email_verified_at),
            "latest_invoice": None if not recent_invoices else {"id": recent_invoices[0].id,
                "voucher_no": recent_invoices[0].voucher_no, "date": recent_invoices[0].invoice_date.isoformat(),
                "amount": str(recent_invoices[0].gross_amount), "party_id": recent_invoices[0].party_id},
            "latest_receipt": None if latest_receipt is None else {"id": latest_receipt.id,
                "voucher_no": latest_receipt.voucher_no, "date": latest_receipt.receipt_date.isoformat(),
                "amount": str(latest_receipt.amount), "party_id": latest_receipt.party_id},
            "recent_invoices": [{"id": row.id, "voucher_no": row.voucher_no,
                "date": row.invoice_date.isoformat(), "amount": str(row.gross_amount),
                "party_id": row.party_id} for row in recent_invoices],
            "notice_summary": [{"id": row.id, "title": row.title, "message": row.message,
                "read": row.read_at is not None, "created_at": row.created_at.isoformat() if row.created_at else None}
                for row in notices]}
