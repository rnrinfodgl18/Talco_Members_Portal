import re
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.importer.masters import load_master_directory, load_workbooks
from app.importer.matcher import resolve
from app.importer.normalize import nkey
from app.importer.parser import parse_file
from app.models import AuditLog, ChargeHead, DataQualityIssue, Pump, Tannery, TannerySerialCounter


APPROVED_LEGACY_ALIASES = {
    "S.S.International  (Exports) Tanning": 18,
    "Vaigai Leather Corporation A-Unit": 29,
    "Sea Lord Leathers - Subramanian & Co": 3,
    "K.Mohamed Muthu Sons(KMA-Begam)": 6,
    "K.A.R Leathers (P) Ltd - Unit 1": 16,
    "Khaja Moideen Leather Company (MMMT)": 21,
    "K.A.R.Leathers P Ltd- Unit -2": 33,
    "Super Tanning Compa C/o.K.Kaja Maideen Tannery": 38,
    "S.S.International(CHE) C/o.K.M.Ashraf Nisa Dry Shop": 34,
    "S.M.A.Tanners C/o.M.Raviyathammal Tannery": 25,
    "Aasim Leather Exports C/o.Mubarak Leather Exports-B": 13,
    "S.M.A. Tannery C/O. S.Mohamed Abdullah Tannery": 39,
}


def _gst_checksum_valid(gstin: str) -> bool:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    value = gstin.upper()
    if not re.fullmatch(r"[0-9A-Z]{15}", value):
        return False
    total = 0
    for index, char in enumerate(value[:14]):
        product = alphabet.index(char) * (1 if index % 2 == 0 else 2)
        total += product // 36 + product % 36
    return alphabet[(36 - total % 36) % 36] == value[14]


def _master_issues(master, as_of: date) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    if not master.gstin:
        issues.append(("GSTIN_BLANK", "GSTIN is not on record"))
    elif not _gst_checksum_valid(master.gstin):
        issues.append(("GSTIN_INVALID", f"GSTIN checksum or format is invalid: {master.gstin}"))
    consent_dates = re.findall(r"(\d{2}\.\d{2}\.\d{4})", master.consent or "")
    if consent_dates and datetime.strptime(consent_dates[-1], "%d.%m.%Y").date() < as_of:
        issues.append(("CONSENT_EXPIRED", f"Consent expired on {consent_dates[-1]}"))
    phone = str(master.attributes.get("CONTACT NUMBER") or "")
    if phone and len(re.sub(r"\D", "", phone)) != 10:
        issues.append(("PHONE_INVALID", f"Phone number is not 10 digits: {phone}"))
    email = str(master.attributes.get("EMAIL") or "")
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        issues.append(("EMAIL_INVALID", f"Email is malformed: {email}"))
    return issues



def import_master_workbooks(session: Session, paths: list[str | Path], actor: str,
                            as_of: date | None = None) -> dict[str, int]:
    masters = load_workbooks(paths)
    if not masters:
        raise ValueError("No tannery sheets were found in the selected workbooks")
    imported_names = [nkey(master.name) for master in masters]
    if len(imported_names) != len(set(imported_names)):
        raise ValueError("Duplicate tannery name in master workbooks")

    pump_rows = {row.code: row for row in session.scalars(select(Pump)).all()}
    pumps_created = 0
    for code in sorted({master.pump_house for master in masters}):
        if code not in pump_rows:
            row = Pump(code=code, name=f"Pump house {code}")
            session.add(row)
            pump_rows[code] = row
            pumps_created += 1

    rows_by_sno = {row.sno: row for row in session.scalars(select(Tannery)).all()}
    names_by_key = {row.normalized_key: row for row in rows_by_sno.values()}
    created = updated = 0
    imported_rows = []
    for master in masters:
        row = rows_by_sno.get(master.sno)
        name_key = nkey(master.name)
        conflicting = names_by_key.get(name_key)
        if conflicting is not None and conflicting.sno != master.sno:
            raise ValueError(f"Tannery name already belongs to S.No {conflicting.sno}: {master.name}")
        values = {
            "name": master.name, "normalized_key": name_key, "pump_house": master.pump_house,
            "internal_id": master.internal_id, "factory_id": master.factory_id,
            "tnpcb_user_id": master.tnpcb_user_id, "gps": master.gps, "gstin": master.gstin,
            "consent": master.consent, "original_capacity": master.original_capacity,
            "additional_capacity": master.additional_capacity, "original_shares": master.original_shares,
            "additional_shares": master.additional_shares,
            "phone": str(master.attributes.get("CONTACT NUMBER") or "").strip() or None,
            "email": str(master.attributes.get("EMAIL") or "").strip() or None,
        }
        if row is None:
            row = Tannery(sno=master.sno, **values)
            session.add(row)
            session.flush()
            session.add(AuditLog(entity_type="tannery", entity_id=row.id, action="master_import_create",
                                 changed_by=actor, changes=f'{{"source_serial": {master.sno}}}'))
            rows_by_sno[master.sno] = row
            names_by_key[name_key] = row
            created += 1
        else:
            changes = {}
            for key, value in values.items():
                old = getattr(row, key)
                if old != value:
                    changes[key] = {"from": old, "to": value}
                    setattr(row, key, value)
            if changes:
                import json
                session.add(AuditLog(entity_type="tannery", entity_id=row.id, action="master_import_update",
                                     changed_by=actor, changes=json.dumps(changes, default=str)))
                updated += 1
        imported_rows.append(row)

    session.flush()
    imported_ids = [row.id for row in imported_rows]
    session.execute(delete(DataQualityIssue).where(DataQualityIssue.tannery_id.in_(imported_ids)))
    check_date = as_of or date.today()
    for master, row in zip(masters, imported_rows):
        for code, detail in _master_issues(master, check_date):
            session.add(DataQualityIssue(tannery_id=row.id, code=code, detail=detail))

    highest = session.scalar(select(func.coalesce(func.max(Tannery.sno), 0))) or 0
    counter = session.get(TannerySerialCounter, 1)
    if counter is None:
        session.add(TannerySerialCounter(id=1, last_value=highest))
    elif counter.last_value < highest:
        counter.last_value = highest
    session.commit()
    return {"files": len(paths), "pumps_created": pumps_created, "tanneries_created": created,
            "tanneries_updated": updated, "tanneries_total": len(masters)}

def load_masters(session: Session, fixture_dir: str | Path, as_of: date = date(2026, 8, 31)) -> dict[str, int]:
    fixture_path = Path(fixture_dir)
    masters = load_master_directory(fixture_path)
    pump_codes = set(session.scalars(select(Pump.code)))
    missing = {master.pump_house for master in masters} - pump_codes
    if missing:
        raise ValueError("Create these pumps in Pump Master before loading: " + ", ".join(sorted(missing)))
    rows_by_sno = {row.sno: row for row in session.scalars(select(Tannery)).all()}
    for master in masters:
        row = rows_by_sno.get(master.sno)
        values = {
            "name": master.name, "normalized_key": nkey(master.name), "pump_house": master.pump_house,
            "internal_id": master.internal_id, "factory_id": master.factory_id,
            "tnpcb_user_id": master.tnpcb_user_id, "gps": master.gps, "gstin": master.gstin,
            "consent": master.consent, "original_capacity": master.original_capacity,
            "additional_capacity": master.additional_capacity, "original_shares": master.original_shares,
            "additional_shares": master.additional_shares,
            "phone": str(master.attributes.get("CONTACT NUMBER") or "").strip() or None,
            "email": str(master.attributes.get("EMAIL") or "").strip() or None,
        }
        if row is None:
            row = Tannery(sno=master.sno, **values)
            session.add(row)
            rows_by_sno[master.sno] = row
        else:
            for key, value in values.items():
                setattr(row, key, value)
    session.flush()

    session.execute(delete(DataQualityIssue))
    master_by_sno = {item.sno: item for item in masters}
    for master in masters:
        for code, detail in _master_issues(master, as_of):
            session.add(DataQualityIssue(tannery_id=rows_by_sno[master.sno].id, code=code, detail=detail))

    mismatch_snos: set[int] = set()
    for filename in ("Treatment.xml", "Chrome.xml", "Sludge.xml"):
        for voucher in parse_file(fixture_path / filename):
            matched = resolve(voucher.party, masters, APPROVED_LEGACY_ALIASES)
            if matched.tannery and voucher.gstin:
                master_gstin = master_by_sno[matched.tannery.sno].gstin
                if master_gstin and nkey(master_gstin) != nkey(voucher.gstin):
                    mismatch_snos.add(matched.tannery.sno)
    for sno in mismatch_snos:
        session.add(DataQualityIssue(
            tannery_id=rows_by_sno[sno].id, code="GSTIN_TALLY_MISMATCH",
            detail="Master GSTIN disagrees with at least one August Tally sales voucher",
        ))

    seeds = (("TREATMENT", "Treatment charges", "5.00"),
             ("CHROME", "Chrome water", "5.00"),
             ("SLUDGE", "Sludge disposal", "18.00"))
    existing = {item.code: item for item in session.scalars(select(ChargeHead)).all()}
    for code, name, rate in seeds:
        if code in existing:
            existing[code].name, existing[code].gst_rate = name, rate
        else:
            session.add(ChargeHead(code=code, name=name, gst_rate=rate))
    session.commit()
    return {"tanneries": len(masters), "gst_mismatches": len(mismatch_snos)}

