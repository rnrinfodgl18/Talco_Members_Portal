"""Admin reports. The outstanding summary is the office's daily-use screen."""
import csv
import io
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Invoice, Party, Receipt, Tannery, TanneryPartyLink
from app.models.auth import User
from app.security import require_roles

router = APIRouter(prefix="/api/reports", tags=["reports"])

SORT_KEYS = {"name", "opening", "billed", "collected", "outstanding", "last_receipt_date"}


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def outstanding_rows(session: Session, sort: str = "outstanding",
                     direction: str = "desc") -> list[dict]:
    """One row per ledger account: opening + billed - collected.

    Same definition as the member's own closing balance, so the office and the
    member never see two different numbers for the same account.
    """
    billed = select(Invoice.party_id.label("party_id"),
                    func.coalesce(func.sum(Invoice.gross_amount), 0).label("total")) \
        .where(Invoice.is_cancelled.is_(False)).group_by(Invoice.party_id).subquery()
    collected = select(Receipt.party_id.label("party_id"),
                       func.coalesce(func.sum(Receipt.amount), 0).label("total"),
                       func.max(Receipt.receipt_date).label("last_date")) \
        .where(Receipt.is_cancelled.is_(False)).group_by(Receipt.party_id).subquery()

    records = session.execute(
        select(Party, billed.c.total, collected.c.total, collected.c.last_date)
        .outerjoin(billed, billed.c.party_id == Party.id)
        .outerjoin(collected, collected.c.party_id == Party.id)).all()

    units = {}
    for party_id, name in session.execute(
            select(TanneryPartyLink.party_id, Tannery.name)
            .join(Tannery, Tannery.id == TanneryPartyLink.tannery_id)).all():
        units.setdefault(party_id, []).append(name)

    rows = []
    for party, billed_total, collected_total, last_date in records:
        opening = Decimal(party.opening_amount or 0)
        billed_amount = Decimal(billed_total or 0)
        collected_amount = Decimal(collected_total or 0)
        rows.append({
            "party_id": party.id, "code": f"ACC-{party.id:04d}", "name": party.name,
            "tanneries": sorted(units.get(party.id, [])),
            "opening": _money(opening), "billed": _money(billed_amount),
            "collected": _money(collected_amount),
            "outstanding": _money(opening + billed_amount - collected_amount),
            "last_receipt_date": last_date.isoformat() if last_date else None,
        })

    key = sort if sort in SORT_KEYS else "outstanding"

    def sort_value(row):
        if key == "name":
            return row["name"].lower()
        if key == "last_receipt_date":
            return row["last_receipt_date"] or ""
        return Decimal(row[key])

    rows.sort(key=sort_value, reverse=direction != "asc")
    return rows


@router.get("/outstanding")
def outstanding(sort: str = Query("outstanding"), direction: str = Query("desc"),
                _: User = Depends(require_roles("talco_admin", "talco_staff")),
                session: Session = Depends(get_db)):
    rows = outstanding_rows(session, sort, direction)
    return {
        "rows": rows,
        "totals": {field: _money(sum(Decimal(row[field]) for row in rows))
                   for field in ("opening", "billed", "collected", "outstanding")},
        "accounts": len(rows),
        "accounts_with_dues": sum(1 for row in rows if Decimal(row["outstanding"]) > 0),
    }


@router.get("/outstanding.csv")
def outstanding_csv(sort: str = Query("outstanding"), direction: str = Query("desc"),
                    _: User = Depends(require_roles("talco_admin", "talco_staff")),
                    session: Session = Depends(get_db)):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Account", "Ledger name", "Units", "Opening", "Billed",
                     "Collected", "Outstanding", "Last receipt"])
    for row in outstanding_rows(session, sort, direction):
        writer.writerow([row["code"], row["name"], "; ".join(row["tanneries"]),
                         row["opening"], row["billed"], row["collected"],
                         row["outstanding"], row["last_receipt_date"] or ""])
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="outstanding-summary.csv"'})
