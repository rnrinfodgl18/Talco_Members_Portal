import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, DataQualityIssue, TannerySerialCounter, Pump, Tannery, Invoice, Receipt, TanneryPartyLink, StagingRow
from app.models.auth import User
from app.security import require_roles
from app.importer.normalize import nkey
from app.services.master_load import import_master_workbooks
from app.schemas.tannery import QualityIssueOut, TanneryOut, TanneryUpdate, TanneryCreate


router = APIRouter(prefix="/api/tanneries", tags=["tanneries"],
                   dependencies=[Depends(require_roles("talco_admin", "talco_staff"))])


@router.get("", response_model=list[TanneryOut])
def list_tanneries(
    pump_house: str | None = Query(default=None, min_length=1, max_length=20),
    search: str | None = None,
    session: Session = Depends(get_db),
) -> list[Tannery]:
    statement = select(Tannery).order_by(Tannery.sno)
    if pump_house:
        statement = statement.where(Tannery.pump_house == pump_house)
    if search:
        statement = statement.where(Tannery.name.ilike(f"%{search.strip()}%"))
    return list(session.scalars(statement).all())


@router.get("/quality", response_model=list[QualityIssueOut])
def quality_report(session: Session = Depends(get_db)) -> list[QualityIssueOut]:
    rows = session.execute(
        select(DataQualityIssue, Tannery.sno, Tannery.name)
        .join(Tannery, Tannery.id == DataQualityIssue.tannery_id)
        .order_by(DataQualityIssue.code, Tannery.sno)
    ).all()
    return [QualityIssueOut(id=issue.id, tannery_id=issue.tannery_id, tannery_sno=sno,
                            tannery_name=name, code=issue.code, detail=issue.detail)
            for issue, sno, name in rows]


@router.post("/import-master", status_code=201)
async def import_master_excel(
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_db),
    actor: User = Depends(require_roles("talco_admin")),
) -> dict[str, int | str]:
    if not files or len(files) > 5:
        raise HTTPException(422, "Select between 1 and 5 Pump Master Excel files")
    total = 0
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for upload in files:
            name = Path(upload.filename or "").name
            if Path(name).suffix.lower() not in {".xlsx", ".xlsm"}:
                raise HTTPException(422, f"{name or 'File'}: only .xlsx or .xlsm is supported")
            content = await upload.read()
            total += len(content)
            if total > 15 * 1024 * 1024:
                raise HTTPException(422, "Combined master upload exceeds 15 MB")
            path = Path(directory) / name
            path.write_bytes(content)
            paths.append(path)
        try:
            result = import_master_workbooks(session, paths, actor.email)
        except ValueError as exc:
            session.rollback()
            raise HTTPException(422, str(exc)) from exc
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, "Master import conflicts with an existing serial number or tannery name") from exc
    return {**result, "message": "Pump and tannery masters imported successfully"}


@router.get("/{tannery_id}", response_model=TanneryOut)
def get_tannery(tannery_id: int, session: Session = Depends(get_db)) -> Tannery:
    row = session.get(Tannery, tannery_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tannery not found")
    return row


def validate_pump(session: Session, code: str) -> None:
    if session.scalar(select(Pump.id).where(Pump.code == code)) is None:
        raise HTTPException(422, "Select an existing pump from Pump Master")


def commit_changes(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Serial number or tannery name already exists, or this record is in use") from exc


def audit(session: Session, row: Tannery, action: str, actor: User, changes: dict) -> None:
    session.add(AuditLog(entity_type="tannery", entity_id=row.id, action=action,
                         changed_by=actor.email, changes=json.dumps(changes)))


@router.post("", response_model=TanneryOut, status_code=201)
def create_tannery(data: TanneryCreate, session: Session = Depends(get_db),
                   actor: User = Depends(require_roles("talco_admin"))) -> Tannery:
    values = data.model_dump()
    validate_pump(session, data.pump_house)
    key = nkey(data.name)
    if not key:
        raise HTTPException(422, "Tannery name must contain letters or numbers")
    # Atomic counter update serializes concurrent creates. Imported serials remain
    # authoritative; advance above them without reusing deleted manual serials.
    highest = select(func.coalesce(func.max(Tannery.sno), 0)).scalar_subquery()
    counter = TannerySerialCounter
    next_value = case((counter.last_value < highest, highest), else_=counter.last_value) + 1
    values["sno"] = session.scalar(update(counter).where(counter.id == 1)
                                    .values(last_value=next_value).returning(counter.last_value))
    if values["sno"] is None:
        raise HTTPException(503, "Serial numbering is not initialized; apply database migrations")
    row = Tannery(**values, normalized_key=key)
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Serial number or tannery name already exists") from exc
    audit(session, row, "create", actor, values)
    commit_changes(session)
    session.refresh(row)
    return row


@router.patch("/{tannery_id}", response_model=TanneryOut)
def update_tannery(tannery_id: int, update: TanneryUpdate,
                   session: Session = Depends(get_db),
                   actor: User = Depends(require_roles("talco_admin"))) -> Tannery:
    row = session.get(Tannery, tannery_id)
    if row is None:
        raise HTTPException(404, "Tannery not found")
    values = update.model_dump(exclude_unset=True)
    if any(key in values and values[key] is None for key in ("name", "pump_house")):
        raise HTTPException(422, "Name and pump house are required")
    if "pump_house" in values:
        validate_pump(session, values["pump_house"])
    if "name" in values:
        key = nkey(values["name"])
        if not key:
            raise HTTPException(422, "Tannery name must contain letters or numbers")
        values["normalized_key"] = key
    changes = {}
    for field, value in values.items():
        old = getattr(row, field)
        if old != value:
            changes[field] = {"from": old, "to": value}
            setattr(row, field, value)
    if changes:
        audit(session, row, "update", actor, changes)
        commit_changes(session)
        session.refresh(row)
    return row


@router.delete("/{tannery_id}", status_code=204)
def delete_tannery(tannery_id: int, session: Session = Depends(get_db),
                   actor: User = Depends(require_roles("talco_admin"))):
    row = session.get(Tannery, tannery_id)
    if row is None:
        raise HTTPException(404, "Tannery not found")
    for model in (Invoice, Receipt, TanneryPartyLink, User):
        if session.scalar(select(model.id).where(model.tannery_id == row.id).limit(1)) is not None:
            raise HTTPException(409, "Cannot delete: this tannery has linked bills, receipts, parties or user accounts")
    # Staging references the serial number rather than a database foreign key.
    for payload in session.scalars(select(StagingRow.payload)):
        if json.loads(payload).get("tannery_sno") == row.sno:
            raise HTTPException(409, "Cannot delete: this tannery is referenced by an import batch")
    audit(session, row, "delete", actor, TanneryOut.model_validate(row).model_dump())
    session.execute(delete(DataQualityIssue).where(DataQualityIssue.tannery_id == row.id))
    session.delete(row)
    commit_changes(session)
