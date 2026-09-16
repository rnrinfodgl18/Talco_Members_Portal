from datetime import date, datetime, timezone
import json

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, Party, PartyAlias, Tannery, TanneryPartyLink
from app.services.mapping_queue import MappingConflictError, exclude_row, link_row, queue_rows


router = APIRouter(prefix="/api/mappings", tags=["mappings"])


class LinkRequest(BaseModel):
    tannery_id: int
    role: str
    valid_from: date


class AliasBindRequest(LinkRequest):
    pass


def _admin(role: str) -> None:
    if role != "talco_admin":
        raise HTTPException(403, "Admin role required")


@router.get("/queue")
def mapping_queue(session: Session = Depends(get_db)) -> list[dict]:
    return queue_rows(session)


@router.post("/queue/{staging_id}/link")
def link(staging_id: int, request: LinkRequest, role: str = Header(default="", alias="X-TALCO-ROLE"),
         actor: str = Header(default="admin@talco.test", alias="X-TALCO-ACTOR"),
         session: Session = Depends(get_db)) -> dict:
    _admin(role)
    try:
        batch = link_row(session, staging_id, request.tannery_id, request.role, request.valid_from, actor)
    except MappingConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"batch_id": batch.id, "status": batch.status}


@router.post("/queue/{staging_id}/exclude")
def exclude(staging_id: int, role: str = Header(default="", alias="X-TALCO-ROLE"),
            actor: str = Header(default="admin@talco.test", alias="X-TALCO-ACTOR"),
            session: Session = Depends(get_db)) -> dict:
    _admin(role)
    try:
        batch = exclude_row(session, staging_id, actor)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"batch_id": batch.id, "status": batch.status}


def _alias_row(session: Session, alias: PartyAlias) -> dict:
    party = session.get(Party, alias.party_id) if alias.party_id else None
    tannery = session.get(Tannery, alias.tannery_id) if alias.tannery_id else None
    if tannery is None and party:
        link = session.scalar(select(TanneryPartyLink).where(
            TanneryPartyLink.party_id == party.id, TanneryPartyLink.valid_to.is_(None))
            .order_by(TanneryPartyLink.id.desc()))
        tannery = session.get(Tannery, link.tannery_id) if link else None
    audit = session.scalar(select(AuditLog).where(AuditLog.entity_type == "party_alias",
                                                   AuditLog.entity_id == alias.id)
                           .order_by(AuditLog.id.desc()).limit(1))
    return {"id": alias.id, "raw_name": alias.raw_name, "party_id": alias.party_id,
            "account_name": party.name if party else None, "tannery_id": tannery.id if tannery else None,
            "tannery_name": tannery.name if tannery else None, "excluded": alias.excluded,
            "revoked_at": alias.revoked_at.isoformat() if alias.revoked_at else None,
            "approved_by": audit.changed_by if audit else None,
            "approved_at": audit.created_at.isoformat() if audit else None}


@router.get("/aliases")
def aliases(session: Session = Depends(get_db)) -> list[dict]:
    return [_alias_row(session, row) for row in
            session.scalars(select(PartyAlias).order_by(PartyAlias.raw_name)).all()]


@router.post("/aliases/{alias_id}/revoke")
def revoke(alias_id: int, role: str = Header(default="", alias="X-TALCO-ROLE"),
           actor: str = Header(default="admin@talco.test", alias="X-TALCO-ACTOR"),
           session: Session = Depends(get_db)) -> dict:
    _admin(role)
    alias = session.get(PartyAlias, alias_id)
    if alias is None:
        raise HTTPException(404, "Ledger mapping not found")
    alias.revoked_at = datetime.now(timezone.utc)
    session.add(AuditLog(entity_type="party_alias", entity_id=alias.id, action="unbind",
                         changed_by=actor, changes=json.dumps({"tannery_id": alias.tannery_id})))
    session.commit()
    return _alias_row(session, alias)


@router.post("/aliases/{alias_id}/bind")
def bind_alias(alias_id: int, request: AliasBindRequest,
               role: str = Header(default="", alias="X-TALCO-ROLE"),
               actor: str = Header(default="admin@talco.test", alias="X-TALCO-ACTOR"),
               session: Session = Depends(get_db)) -> dict:
    _admin(role)
    if request.role not in {"owner", "lessee"}:
        raise HTTPException(422, "Role must be owner or lessee")
    alias = session.get(PartyAlias, alias_id)
    tannery = session.get(Tannery, request.tannery_id)
    if alias is None:
        raise HTTPException(404, "Ledger mapping not found")
    if alias.party_id is None:
        raise HTTPException(422, "This excluded name has no ledger account; map it from the queue")
    if tannery is None:
        raise HTTPException(422, "Tannery not found")
    previous = alias.tannery_id
    alias.tannery_id, alias.excluded, alias.revoked_at = tannery.id, False, None
    link = session.scalar(select(TanneryPartyLink).where(
        TanneryPartyLink.party_id == alias.party_id,
        TanneryPartyLink.tannery_id == tannery.id,
        TanneryPartyLink.valid_to.is_(None)))
    if link is None:
        session.add(TanneryPartyLink(party_id=alias.party_id, tannery_id=tannery.id,
                                     role=request.role, valid_from=request.valid_from))
    session.add(AuditLog(entity_type="party_alias", entity_id=alias.id, action="bind",
                         changed_by=actor, changes=json.dumps({"from_tannery_id": previous,
                             "to_tannery_id": tannery.id, "role": request.role,
                             "valid_from": request.valid_from.isoformat()})))
    session.commit()
    return _alias_row(session, alias)