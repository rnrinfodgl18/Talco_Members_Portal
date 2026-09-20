from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import Select, and_, exists, or_, select

from app.models.auth import User
from app.models.entities import TanneryPartyLink

# Rows a lessee may see are bounded by the lease window, not only by the party.
# Each entry maps a scopable model to the column holding the document's date.
_DOCUMENT_DATE_COLUMN = {"Invoice": "invoice_date", "Receipt": "receipt_date"}


def _lessee_party_ids(user: User) -> set[int]:
    """Parties this user reaches as a lessee, whose rows are lease-period bound."""
    if getattr(user, "ledger_access_configured", False):
        return {grant.party_id for grant in user.ledger_access
                if grant.relationship_role == "lessee"}
    if user.role == "lessee" and user.party_id:
        return {user.party_id}
    return set()


def lease_window_filter(query: Select, model, user: User) -> Select:
    """Hide documents dated outside the lease that gives this lessee access.

    A tannery can change hands, so party identity alone is not enough: a lessee
    must never see bills or receipts raised before their lease began or after it
    ended. Parties the user reaches in any other role are left untouched.
    """
    party_ids = _lessee_party_ids(user)
    column_name = _DOCUMENT_DATE_COLUMN.get(model.__name__)
    if not party_ids or column_name is None:
        return query
    document_date = getattr(model, column_name)
    within_lease = exists(select(TanneryPartyLink.id).where(and_(
        TanneryPartyLink.tannery_id == model.tannery_id,
        TanneryPartyLink.party_id == model.party_id,
        TanneryPartyLink.valid_from <= document_date,
        or_(TanneryPartyLink.valid_to.is_(None), document_date <= TanneryPartyLink.valid_to),
    )))
    return query.where(or_(model.party_id.notin_(party_ids), within_lease))


@dataclass(frozen=True)
class Scope:
    tannery_id: int | None
    party_id: int | None


def user_scope(user: User, requested_tannery_id: int | None = None,
               requested_party_id: int | None = None) -> Scope:
    if user.role in {"talco_admin", "talco_staff"}:
        return Scope(requested_tannery_id, requested_party_id)
    if getattr(user, "ledger_access_configured", False):
        allowed = {grant.party_id for grant in user.ledger_access}
        if requested_party_id is not None and requested_party_id not in allowed:
            raise HTTPException(403, "Ledger account is outside your account access")
        return Scope(requested_tannery_id, requested_party_id)
    if user.role in {"member", "member_staff"}:
        if not user.tannery_id or (requested_tannery_id and requested_tannery_id != user.tannery_id):
            raise HTTPException(403, "Tannery is outside your account scope")
        return Scope(user.tannery_id, None)
    if user.role == "lessee":
        if not user.tannery_id or not user.party_id:
            raise HTTPException(403, "Lessee account is not linked")
        if requested_tannery_id and requested_tannery_id != user.tannery_id:
            raise HTTPException(403, "Tannery is outside your account scope")
        if requested_party_id and requested_party_id != user.party_id:
            raise HTTPException(403, "Party is outside your account scope")
        return Scope(user.tannery_id, user.party_id)
    raise HTTPException(403, "Unknown account role")


def scoped_query(query: Select, model, user: User, tannery_id: int | None = None,
                 party_id: int | None = None) -> Select:
    scope = user_scope(user, tannery_id, party_id)
    if user.role not in {"talco_admin", "talco_staff"} and getattr(user, "ledger_access_configured", False):
        query = query.where(model.party_id.in_([grant.party_id for grant in user.ledger_access]))
    if scope.tannery_id is not None:
        query = query.where(model.tannery_id == scope.tannery_id)
    if scope.party_id is not None:
        query = query.where(model.party_id == scope.party_id)
    return lease_window_filter(query, model, user)
