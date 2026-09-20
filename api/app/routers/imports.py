import json
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.importer.parser import TallyParseError
from app.models import ChargeHead, ImportBatch, StagingRow
from app.services.bill_dispatch import dispatch_batch
from app.services.import_pipeline import DuplicateImportError, create_batch, post_batch, resolve_invoice_correction


router = APIRouter(prefix="/api/imports", tags=["imports"])


def _summary(session: Session, batch: ImportBatch) -> dict:
    rows = session.scalars(select(StagingRow).where(StagingRow.batch_id == batch.id)
                           .order_by(StagingRow.row_number)).all()
    parsed = [{**json.loads(row.payload), "id": row.id, "status": row.status,
               "row_number": row.row_number} for row in rows]
    return {
        "id": batch.id, "file_name": batch.file_name, "status": batch.status,
        "period_start": batch.period_start.isoformat(), "charge_head_id": batch.charge_head_id,
        "row_count": len(rows), "matched": sum(row.status in {"matched", "posted"} for row in rows),
        "queued": sum(row.status == "queued" for row in rows),
        "errors": sum(row.status == "error" for row in rows),
        "corrections": sum(row.status == "correction" for row in rows),
        "duplicates": sum(row.status == "duplicate" for row in rows),
        "cancelled": sum(bool(item.get("is_cancelled")) for item in parsed),
        "allocations": sum(len(item.get("bill_allocations", [])) for item in parsed),
        "warnings": sum(len(item.get("warnings", [])) for item in parsed),
        "base_total": str(sum((Decimal(item["base"]) if item["base"] else Decimal()) for item in parsed)),
        "gross_total": str(sum(Decimal(item["gross"]) for item in parsed)), "rows": parsed,
    }


@router.get("/charge-heads")
def charge_heads(session: Session = Depends(get_db)) -> list[dict]:
    return [{"id": row.id, "code": row.code, "name": row.name, "gst_rate": str(row.gst_rate)}
            for row in session.scalars(select(ChargeHead).order_by(ChargeHead.id)).all()]


@router.get("")
def batches(session: Session = Depends(get_db)) -> list[dict]:
    return [{"id": row.id, "file_name": row.file_name, "status": row.status,
             "period_start": row.period_start.isoformat(), "uploaded_at": row.uploaded_at.isoformat()}
            for row in session.scalars(select(ImportBatch).order_by(ImportBatch.id.desc())).all()]


@router.post("", status_code=201)
async def upload_import(file: UploadFile = File(...), charge_head_id: int | None = Form(None),
                        period_start: date = Form(...), source_type: str = Form("auto"),
                        session: Session = Depends(get_db)) -> dict:
    if source_type not in {"auto", "excel", "tally_xml"}:
        raise HTTPException(422, "Supported import types are Excel and Tally XML")
    try:
        batch = create_batch(session, file.filename or "import.xml", await file.read(), period_start, charge_head_id)
    except DuplicateImportError as exc:
        raise HTTPException(409, f"Already imported as batch #{exc.batch_id}") from exc
    except (ValueError, TallyParseError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return _summary(session, batch)


@router.get("/{batch_id}")
def batch_detail(batch_id: int, session: Session = Depends(get_db)) -> dict:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(404, "Batch not found")
    return _summary(session, batch)


@router.post("/{batch_id}/post")
def post(batch_id: int, role: str = Header(default="", alias="X-TALCO-ROLE"),
         session: Session = Depends(get_db)) -> dict:
    if role != "talco_admin":
        raise HTTPException(403, "Admin role required")
    try:
        batch = post_batch(session, batch_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _summary(session, batch)


@router.post("/{batch_id}/dispatch")
def dispatch(batch_id: int, role: str = Header(default="", alias="X-TALCO-ROLE"),
             session: Session = Depends(get_db)) -> dict:
    """Email and WhatsApp the bills this batch posted. Safe to re-run."""
    if role not in {"talco_admin", "talco_staff"}:
        raise HTTPException(403, "Admin or office staff role required")
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(404, "Import batch was not found")
    if batch.status not in {"posted", "partially_posted"}:
        raise HTTPException(409, "Post the batch before sending its bills")
    return dispatch_batch(session, batch)


class CorrectionDecision(BaseModel):
    approve: bool
    reason: str = Field(default="", max_length=500)


@router.post("/{batch_id}/corrections/{staging_id}")
def decide_correction(batch_id: int, staging_id: int, decision: CorrectionDecision,
                      role: str = Header(default="", alias="X-TALCO-ROLE"),
                      actor: str = Header(default="", alias="X-TALCO-ACTOR"),
                      session: Session = Depends(get_db)) -> dict:
    if role != "talco_admin":
        raise HTTPException(403, "Admin role required")
    staging = session.get(StagingRow, staging_id)
    if staging is None or staging.batch_id != batch_id:
        raise HTTPException(404, "Correction row not found in this batch")
    try:
        batch = resolve_invoice_correction(session, staging_id, decision.approve, decision.reason, actor)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _summary(session, batch)