import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.importer.matcher import suggest
from app.importer.models import Tannery as ImportTannery
from app.importer.normalize import nkey, split_party
from app.models import AuditLog, ImportBatch, Party, PartyAlias, StagingRow, Tannery, TanneryPartyLink
from app.services.import_pipeline import post_batch


class MappingConflictError(ValueError):
    pass


def queue_rows(session: Session) -> list[dict]:
    rows = session.execute(
        select(StagingRow, ImportBatch).join(ImportBatch).where(StagingRow.status == "queued")
        .order_by(ImportBatch.id, StagingRow.row_number)
    ).all()
    masters_db = session.scalars(select(Tannery).order_by(Tannery.sno)).all()
    masters = [ImportTannery(sno=x.sno, name=x.name, pump_house=x.pump_house) for x in masters_db]
    ids = {x.sno: x.id for x in masters_db}
    result = []
    for staging, batch in rows:
        payload = json.loads(staging.payload)
        parts = split_party(staging.raw_party)
        result.append({
            "id": staging.id, "batch_id": batch.id, "batch_file": batch.file_name,
            "period_start": batch.period_start.isoformat(), "row_number": staging.row_number,
            "raw_name": staging.raw_party, "left": parts.left, "right": parts.right,
            "is_step": parts.is_step, "gross": payload["gross"],
            "suggestions": [{"tannery_id": ids[item.sno], "sno": item.sno, "name": item.name,
                             "pump_house": item.pump_house} for item in suggest(staging.raw_party, masters)],
        })
    return result


def link_row(session: Session, staging_id: int, tannery_id: int, role: str,
             valid_from: date, actor: str) -> ImportBatch:
    if role not in {"owner", "lessee"}:
        raise ValueError("Role must be owner or lessee")
    staging = session.get(StagingRow, staging_id)
    tannery = session.get(Tannery, tannery_id)
    if staging is None or staging.status != "queued":
        raise ValueError("Queued row not found")
    if tannery is None:
        raise ValueError("Tannery not found")
    parts = split_party(staging.raw_party)
    party_key = nkey(parts.left)
    party = session.scalar(select(Party).where(Party.normalized_key == party_key))
    if party is None:
        party = Party(name=parts.left, normalized_key=party_key)
        session.add(party)
        session.flush()
    alias_key = nkey(parts.cleaned)
    existing_alias = session.scalar(select(PartyAlias).where(PartyAlias.normalized_key == alias_key))
    if existing_alias and existing_alias.revoked_at is None and existing_alias.party_id != party.id:
        raise MappingConflictError("This ledger name is already linked to another party")
    if existing_alias is None:
        alias = PartyAlias(party_id=party.id, normalized_key=alias_key, raw_name=parts.cleaned, excluded=False)
        session.add(alias)
        session.flush()
    else:
        alias = existing_alias
        alias.party_id, alias.excluded, alias.revoked_at = party.id, False, None
    active_links = session.scalars(select(TanneryPartyLink).where(
        TanneryPartyLink.party_id == party.id, TanneryPartyLink.valid_to.is_(None))).all()
    if any(link.tannery_id != tannery.id for link in active_links):
        raise MappingConflictError("Party already has an active link to another tannery")
    if not any(link.tannery_id == tannery.id and link.valid_from == valid_from for link in active_links):
        session.add(TanneryPartyLink(tannery_id=tannery.id, party_id=party.id, role=role,
                                     valid_from=valid_from))
    payload = json.loads(staging.payload)
    payload.update({"tannery_sno": tannery.sno, "match_method": "alias", "party_name": parts.left})
    staging.payload, staging.status = json.dumps(payload), "matched"
    session.add(AuditLog(entity_type="party_alias", entity_id=alias.id, action="create",
                         changed_by=actor, changes=json.dumps({"tannery_id": tannery.id, "role": role,
                                                              "valid_from": valid_from.isoformat()})))
    batch_id = staging.batch_id
    session.commit()
    return post_batch(session, batch_id)


def exclude_row(session: Session, staging_id: int, actor: str) -> ImportBatch:
    staging = session.get(StagingRow, staging_id)
    if staging is None or staging.status != "queued":
        raise ValueError("Queued row not found")
    parts = split_party(staging.raw_party)
    alias = session.scalar(select(PartyAlias).where(PartyAlias.normalized_key == nkey(parts.cleaned)))
    if alias is None:
        alias = PartyAlias(normalized_key=nkey(parts.cleaned), raw_name=parts.cleaned, excluded=True)
        session.add(alias)
        session.flush()
    else:
        alias.party_id, alias.excluded, alias.revoked_at = None, True, None
    staging.status = "excluded"
    session.add(AuditLog(entity_type="party_alias", entity_id=alias.id, action="exclude",
                         changed_by=actor, changes="{}"))
    batch = session.get(ImportBatch, staging.batch_id)
    pending = session.scalar(select(StagingRow.id).where(
        StagingRow.batch_id == staging.batch_id, StagingRow.id != staging.id,
        StagingRow.status.in_(["queued", "error", "matched"])).limit(1))
    batch.status = "partially_posted" if pending else "posted"
    session.commit()
    return batch

