from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, PartyAlias
from app.services.mapping_queue import MappingConflictError, exclude_row, link_row, queue_rows


router = APIRouter(prefix="/api/mappings", tags=["mappings"])


class LinkRequest(BaseModel):
    tannery_id: int
    role: str
    valid_from: date


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


@router.get("/aliases")
def aliases(session: Session = Depends(get_db)) -> list[dict]:
    rows = session.scalars(select(PartyAlias).order_by(PartyAlias.id.desc())).all()
    output = []
    for alias in rows:
        audit = session.scalar(select(AuditLog).where(AuditLog.entity_type == "party_alias",
                                                       AuditLog.entity_id == alias.id)
                               .order_by(AuditLog.id.desc()).limit(1))
        output.append({"id": alias.id, "raw_name": alias.raw_name, "excluded": alias.excluded,
                       "revoked_at": alias.revoked_at.isoformat() if alias.revoked_at else None,
                       "approved_by": audit.changed_by if audit else None,
                       "approved_at": audit.created_at.isoformat() if audit else None})
    return output


@router.post("/aliases/{alias_id}/revoke")
def revoke(alias_id: int, role: str = Header(default="", alias="X-TALCO-ROLE"),
           actor: str = Header(default="admin@talco.test", alias="X-TALCO-ACTOR"),
           session: Session = Depends(get_db)) -> dict:
    _admin(role)
    alias = session.get(PartyAlias, alias_id)
    if alias is None:
        raise HTTPException(404, "Alias not found")
    alias.revoked_at = datetime.now(timezone.utc)
    session.add(AuditLog(entity_type="party_alias", entity_id=alias.id, action="revoke",
                         changed_by=actor, changes="{}"))
    session.commit()
    return {"id": alias.id, "status": "revoked"}

