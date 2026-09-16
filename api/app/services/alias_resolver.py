from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importer.normalize import nkey
from app.models import PartyAlias, Tannery, TanneryPartyLink
from app.services.master_load import APPROVED_LEGACY_ALIASES


def approved_aliases(session: Session) -> dict[str, int]:
    records = session.scalars(select(PartyAlias)).all()
    blocked = {row.normalized_key for row in records if row.excluded or row.revoked_at is not None}
    aliases = {raw: sno for raw, sno in APPROVED_LEGACY_ALIASES.items() if nkey(raw) not in blocked}
    for alias in records:
        if alias.excluded or alias.revoked_at is not None:
            continue
        tannery = session.get(Tannery, alias.tannery_id) if alias.tannery_id else None
        if tannery is None and alias.party_id:
            link = session.scalar(select(TanneryPartyLink).where(
                TanneryPartyLink.party_id == alias.party_id,
                TanneryPartyLink.valid_to.is_(None)).order_by(TanneryPartyLink.id.desc()))
            tannery = session.get(Tannery, link.tannery_id) if link else None
        if tannery:
            aliases[alias.raw_name] = tannery.sno
    return aliases