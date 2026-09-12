from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PartyAlias, Tannery, TanneryPartyLink
from app.services.master_load import APPROVED_LEGACY_ALIASES


def approved_aliases(session: Session) -> dict[str, int]:
    aliases = dict(APPROVED_LEGACY_ALIASES)
    rows = session.execute(
        select(PartyAlias.raw_name, Tannery.sno)
        .join(TanneryPartyLink, TanneryPartyLink.party_id == PartyAlias.party_id)
        .join(Tannery, Tannery.id == TanneryPartyLink.tannery_id)
        .where(PartyAlias.excluded.is_(False), PartyAlias.revoked_at.is_(None),
               TanneryPartyLink.valid_to.is_(None))
    ).all()
    aliases.update({raw_name: sno for raw_name, sno in rows})
    return aliases

