from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import Select

from app.models.auth import User


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
    return query
