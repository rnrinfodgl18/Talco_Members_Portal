from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.auth import User
from app.models.entities import Party, Tannery, TanneryPartyLink
from app.security import require_roles

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/invite-options")
def invite_options(_: User = Depends(require_roles("talco_admin")), session: Session = Depends(get_db)):
    tanneries = session.scalars(select(Tannery).order_by(Tannery.sno)).all()
    links = session.execute(select(Party, TanneryPartyLink, Tannery).join(
        TanneryPartyLink, TanneryPartyLink.party_id == Party.id).join(
        Tannery, Tannery.id == TanneryPartyLink.tannery_id).where(
        TanneryPartyLink.valid_to.is_(None)).order_by(Tannery.sno, Party.name)).all()
    return {"tanneries": [{"id": row.id, "sno": row.sno, "name": row.name} for row in tanneries],
            "parties": [{"id": party.id, "name": party.name, "role": link.role,
                         "tannery_id": tannery.id, "tannery_sno": tannery.sno,
                         "tannery_name": tannery.name} for party, link, tannery in links]}
