import hashlib
import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.importer.matcher import resolve
from app.importer.models import Tannery as ImportTannery
from app.importer.normalize import nkey, split_party
from app.importer.parser import parse_file
from app.models import (AuditLog, ChargeHead, ImportBatch, Invoice, InvoiceRevision, Party, PartyAlias,
                        Receipt, ReceiptAllocation, StagingRow, Tannery, TanneryPartyLink)
from app.services.alias_resolver import approved_aliases

class DuplicateImportError(ValueError):
    def __init__(self, batch_id: int):
        super().__init__(f"File already imported as batch #{batch_id}")
        self.batch_id = batch_id

def _fy(value: date) -> str:
    start = value.year if value.month >= 4 else value.year - 1
    return f"{start}-{start + 1}"

def _legacy_voucher_key(row) -> str:
    value = f"{row.voucher_date.isoformat()}|{nkey(row.party)}|{row.gross}|{row.row_number}"
    return f"legacy-{hashlib.sha1(value.encode()).hexdigest()}"

def _import_tanneries(session: Session) -> list[ImportTannery]:
    return [ImportTannery(sno=x.sno, name=x.name, pump_house=x.pump_house)
            for x in session.scalars(select(Tannery).order_by(Tannery.sno)).all()]

def _charge_head(session: Session, ledger: str | None, selected: int | None) -> ChargeHead | None:
    if selected:
        return session.get(ChargeHead, selected)
    if not ledger:
        return None
    key = nkey(ledger)
    aliases = {"effluent treatment charges": "TREATMENT", "treatment charges": "TREATMENT",
               "chrome water": "CHROME", "sludge disposal": "SLUDGE"}
    code = aliases.get(key)
    if code:
        return session.scalar(select(ChargeHead).where(ChargeHead.code == code))
    return session.scalar(select(ChargeHead).where(
        or_(ChargeHead.code.ilike(ledger), ChargeHead.name.ilike(ledger))))

def _invoice_values(payload: dict, tannery_id: int, party_id: int) -> dict:
    return {"tannery_id": tannery_id, "party_id": party_id, "charge_head_id": payload["charge_head_id"],
            "invoice_date": date.fromisoformat(payload["date"]), "base_amount": Decimal(payload["base"]),
            "cgst": Decimal(payload["cgst"]), "sgst": Decimal(payload["sgst"]),
            "gross_amount": Decimal(payload["gross"]), "source_guid": payload.get("source_guid"),
            "source_alter_id": payload.get("source_alter_id"), "is_cancelled": bool(payload.get("is_cancelled"))}

def _invoice_snapshot(invoice: Invoice) -> dict:
    return {"tannery_id": invoice.tannery_id, "party_id": invoice.party_id,
            "charge_head_id": invoice.charge_head_id, "invoice_date": invoice.invoice_date.isoformat(),
            "base_amount": str(invoice.base_amount), "cgst": str(invoice.cgst), "sgst": str(invoice.sgst),
            "gross_amount": str(invoice.gross_amount), "is_cancelled": invoice.is_cancelled}

def _serial(values: dict) -> dict:
    return {k: v.isoformat() if isinstance(v, date) else str(v) if isinstance(v, Decimal) else v
            for k, v in values.items()}

def _find_invoice(session: Session, payload: dict) -> Invoice | None:
    if payload.get("source_guid"):
        found = session.scalar(select(Invoice).where(Invoice.source_guid == payload["source_guid"]))
        if found:
            return found
    if payload.get("voucher_no"):
        return session.scalar(select(Invoice).where(Invoice.voucher_no == payload["voucher_no"],
            Invoice.fy == _fy(date.fromisoformat(payload["date"]))))
    return None

def _find_receipt(session: Session, payload: dict) -> Receipt | None:
    if payload.get("source_guid"):
        found = session.scalar(select(Receipt).where(Receipt.source_guid == payload["source_guid"]))
        if found:
            return found
    if payload.get("voucher_no"):
        return session.scalar(select(Receipt).where(Receipt.voucher_no == payload["voucher_no"],
            Receipt.fy == _fy(date.fromisoformat(payload["date"]))))
    return None

def create_batch(session: Session, filename: str, content: bytes, period_start: date,
                 charge_head_id: int | None) -> ImportBatch:
    digest = hashlib.sha256(content).hexdigest()
    duplicate = session.scalar(select(ImportBatch).where(ImportBatch.file_sha256 == digest))
    if duplicate:
        raise DuplicateImportError(duplicate.id)
    if len(content) > 20 * 1024 * 1024:
        raise ValueError("Import file exceeds 20 MB")
    if charge_head_id and session.get(ChargeHead, charge_head_id) is None:
        raise ValueError("Unknown charge head")
    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".xml", delete=False) as handle:
        handle.write(content); temp_path = Path(handle.name)
    try:
        parsed = parse_file(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    masters = _import_tanneries(session)
    batch = ImportBatch(file_name=filename, file_sha256=digest, status="parsed",
                        period_start=period_start, charge_head_id=charge_head_id)
    session.add(batch); session.flush()
    corrections = 0
    for row in parsed:
        matched = resolve(row.party, masters, approved_aliases(session))
        head = None if row.is_receipt else _charge_head(session, row.charge_ledger, charge_head_id)
        errors = list(row.tax_errors)
        if not row.is_receipt and head is None:
            errors.append(f"Unknown charge ledger: {row.charge_ledger or 'missing'}")
        state = "error" if errors else "matched" if matched.matched else "queued"
        payload = {"date": row.voucher_date.isoformat(), "party": row.party,
            "party_name": matched.party_name, "voucher_type": row.voucher_type,
            "voucher_no": row.voucher_no, "source_guid": row.source_guid,
            "source_alter_id": row.source_alter_id, "is_cancelled": row.is_cancelled,
            "gstin": row.gstin, "gross": str(row.gross), "base": str(row.base) if row.base is not None else None,
            "cgst": str(row.cgst) if row.cgst is not None else None,
            "sgst": str(row.sgst) if row.sgst is not None else None,
            "gst_rate": str(row.gst_rate) if row.gst_rate is not None else None,
            "charge_ledger": row.charge_ledger, "charge_head_id": head.id if head else None,
            "bill_allocations": [{"reference": a[0], "type": a[1], "amount": str(a[2])} for a in row.bill_allocations],
            "ledger_names": list(row.ledger_names), "tax_errors": errors,
            "warnings": list(row.warnings), "source_format": row.source_format,
            "tannery_sno": matched.tannery.sno if matched.tannery else None,
            "match_method": matched.method, "is_step": matched.is_step}
        existing = _find_receipt(session, payload) if row.is_receipt else _find_invoice(session, payload)
        if state == "matched" and existing:
            if row.is_receipt:
                changes = {}
                proposed = {"receipt_date": payload["date"], "amount": payload["gross"],
                            "is_cancelled": payload["is_cancelled"]}
                current = {"receipt_date": existing.receipt_date.isoformat(), "amount": str(existing.amount),
                           "is_cancelled": existing.is_cancelled}
            else:
                tid = session.scalar(select(Tannery.id).where(Tannery.sno == matched.tannery.sno))
                pid = session.scalar(select(Party.id).where(Party.normalized_key == nkey(
                    matched.party_name or split_party(row.party).left))) or existing.party_id
                proposed = _serial(_invoice_values(payload, tid, pid)); current = _invoice_snapshot(existing)
            changes = {k: {"existing": current[k], "replacement": proposed[k]}
                       for k in current if str(current[k]) != str(proposed[k])}
            state = "correction" if changes else "duplicate"
            if state == "correction":
                corrections += 1
            payload["correction"] = {"entity_type": "receipt" if row.is_receipt else "invoice",
                                     "entity_id": existing.id, "changes": changes}
        session.add(StagingRow(batch_id=batch.id, row_number=row.row_number, raw_party=row.party,
                               payload=json.dumps(payload), status=state))
    batch.status = "correction_review" if corrections else "reviewed"
    session.commit(); session.refresh(batch); return batch

def _party_and_link(session: Session, tannery: Tannery, payload: dict, valid_from: date) -> Party:
    parts = split_party(payload["party"]); key = nkey(parts.left)
    alias = session.scalar(select(PartyAlias).where(PartyAlias.normalized_key == nkey(parts.cleaned),
        PartyAlias.excluded.is_(False), PartyAlias.revoked_at.is_(None)))
    party = session.get(Party, alias.party_id) if alias and alias.party_id else None
    party = party or session.scalar(select(Party).where(Party.normalized_key == key))
    if party is None:
        party = Party(name=parts.left, normalized_key=key); session.add(party); session.flush()
    link = session.scalar(select(TanneryPartyLink).where(TanneryPartyLink.tannery_id == tannery.id,
        TanneryPartyLink.party_id == party.id, TanneryPartyLink.valid_from == valid_from))
    if link is None:
        role = "owner" if nkey(parts.left) == tannery.normalized_key else "lessee"
        session.add(TanneryPartyLink(tannery_id=tannery.id, party_id=party.id, role=role, valid_from=valid_from))
    return party

def _allocations(session: Session, receipt: Receipt, payload: dict) -> None:
    for old in session.scalars(select(ReceiptAllocation).where(ReceiptAllocation.receipt_id == receipt.id)).all():
        session.delete(old)
    for item in payload.get("bill_allocations", []):
        invoice = session.scalar(select(Invoice).where(Invoice.party_id == receipt.party_id,
            Invoice.voucher_no == item["reference"], Invoice.fy == receipt.fy))
        session.add(ReceiptAllocation(receipt_id=receipt.id, invoice_id=invoice.id if invoice else None,
            bill_ref=item["reference"], allocation_type=item["type"], amount=Decimal(item["amount"])))

def post_batch(session: Session, batch_id: int) -> ImportBatch:
    batch = session.get(ImportBatch, batch_id)
    if batch is None: raise ValueError("Batch not found")
    rows = session.scalars(select(StagingRow).where(StagingRow.batch_id == batch.id).order_by(StagingRow.row_number)).all()
    for staging in rows:
        if staging.status != "matched": continue
        payload = json.loads(staging.payload)
        tannery = session.scalar(select(Tannery).where(Tannery.sno == payload["tannery_sno"]))
        if tannery is None: staging.status = "queued"; continue
        party = _party_and_link(session, tannery, payload, batch.period_start)
        dt = date.fromisoformat(payload["date"]); voucher = payload["voucher_no"] or _legacy_voucher_key(type("R",(),{
            "voucher_date":dt,"party":payload["party"],"gross":Decimal(payload["gross"]),"row_number":staging.row_number})())
        fy = _fy(dt)
        if "RECEIPT" in payload["voucher_type"].upper():
            if _find_receipt(session, payload): staging.status="correction"; continue
            entity = Receipt(tannery_id=tannery.id, party_id=party.id, voucher_no=voucher, fy=fy,
                receipt_date=dt, amount=Decimal(payload["gross"]), is_step=bool(payload["is_step"]),
                source_guid=payload.get("source_guid"), source_alter_id=payload.get("source_alter_id"),
                is_cancelled=bool(payload.get("is_cancelled")))
            session.add(entity); session.flush(); _allocations(session, entity, payload)
        else:
            if _find_invoice(session, payload): staging.status="correction"; continue
            session.add(Invoice(voucher_no=voucher, fy=fy, **_invoice_values(payload, tannery.id, party.id)))
        staging.status = "posted"
    _refresh_batch_status(batch, rows); session.commit(); session.refresh(batch); return batch

def _refresh_batch_status(batch: ImportBatch, rows: list[StagingRow]) -> None:
    if any(x.status == "correction" for x in rows): batch.status = "correction_review"
    elif any(x.status in {"queued","error","matched"} for x in rows): batch.status = "partially_posted"
    else: batch.status = "posted"

def resolve_invoice_correction(session: Session, staging_id: int, approve: bool, reason: str, actor: str) -> ImportBatch:
    staging = session.get(StagingRow, staging_id)
    if staging is None or staging.status != "correction": raise ValueError("Correction is no longer awaiting review")
    if approve and not reason.strip(): raise ValueError("A correction reason is required before replacement")
    payload=json.loads(staging.payload); correction=payload.get("correction") or {}; kind=correction.get("entity_type","invoice")
    entity=session.get(Receipt if kind=="receipt" else Invoice, correction.get("entity_id") or correction.get("invoice_id"))
    batch=session.get(ImportBatch, staging.batch_id)
    if entity is None or batch is None: raise ValueError("Correction source or batch was not found")
    payload.setdefault("charge_head_id", batch.charge_head_id)
    before = ({"receipt_date":entity.receipt_date.isoformat(),"amount":str(entity.amount),"is_cancelled":entity.is_cancelled}
              if kind=="receipt" else _invoice_snapshot(entity))
    after=before
    if approve:
        tannery=session.scalar(select(Tannery).where(Tannery.sno==payload["tannery_sno"]))
        party=_party_and_link(session,tannery,payload,batch.period_start)
        if kind=="receipt":
            entity.tannery_id=tannery.id; entity.party_id=party.id; entity.receipt_date=date.fromisoformat(payload["date"])
            entity.amount=Decimal(payload["gross"]); entity.is_cancelled=bool(payload.get("is_cancelled"))
            entity.source_guid=payload.get("source_guid"); entity.source_alter_id=payload.get("source_alter_id")
            _allocations(session,entity,payload)
            after={"receipt_date":entity.receipt_date.isoformat(),"amount":str(entity.amount),"is_cancelled":entity.is_cancelled}
        else:
            values=_invoice_values(payload,tannery.id,party.id); after=_serial(values)
            session.add(InvoiceRevision(invoice_id=entity.id,snapshot=json.dumps(before),replacement=json.dumps(after),
                source_batch_id=batch.id,reason=reason.strip(),revised_by=actor))
            for k,v in values.items(): setattr(entity,k,v)
        staging.status="posted"; action="correction_approved"
    else:
        staging.status="ignored"; action="correction_rejected"
    session.add(AuditLog(entity_type=kind,entity_id=entity.id,action=action,changed_by=actor or "admin",
        changes=json.dumps({"before":before,"after":after,"reason":reason.strip(),"batch_id":batch.id})))
    rows=session.scalars(select(StagingRow).where(StagingRow.batch_id==batch.id)).all()
    _refresh_batch_status(batch,rows);session.commit();session.refresh(batch);return batch
