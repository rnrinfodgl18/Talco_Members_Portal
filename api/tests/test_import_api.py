from fastapi.testclient import TestClient
from app.main import app
from test_tannery_crud import master_api


def test_untrusted_role_header_cannot_post() -> None:
    response = TestClient(app).post("/api/imports/1/post", headers={"X-TALCO-ROLE": "talco_admin"})
    assert response.status_code == 401

def test_invoice_correction_requires_admin_reason_and_keeps_revision(master_api):
    import json
    from datetime import date
    from decimal import Decimal
    from sqlalchemy import select
    from app.models import AuditLog, ChargeHead, ImportBatch, Invoice, InvoiceRevision, Party, Pump, StagingRow, Tannery

    client, headers, factory = master_api
    with factory() as session:
        pump = Pump(code="Z", name="Correction Pump")
        session.add(pump); session.flush()
        tannery = Tannery(sno=9001, name="Correction Tannery", normalized_key="correction tannery", pump_house="Z")
        party = Party(name="Correction Account", normalized_key="correction account")
        head = ChargeHead(code="CORRECT", name="Treatment Charges", gst_rate=5)
        session.add_all([tannery, party, head]); session.flush()
        invoice = Invoice(tannery_id=tannery.id, party_id=party.id, charge_head_id=head.id,
            voucher_no="INV-CORR-1", fy="2026-2027", invoice_date=date(2026, 8, 31),
            base_amount=Decimal("100.00"), cgst=Decimal("2.50"), sgst=Decimal("2.50"),
            gross_amount=Decimal("105.00"))
        batch = ImportBatch(file_name="corrected.xml", file_sha256="c"*64,
            status="correction_review", period_start=date(2026, 8, 1), charge_head_id=head.id)
        session.add_all([invoice, batch]); session.flush()
        payload = {"date":"2026-08-31","party":"Correction Account","voucher_type":"Sales",
            "voucher_no":"INV-CORR-1","gross":"126.00","base":"120.00","cgst":"3.00",
            "sgst":"3.00","tannery_sno":tannery.sno,"is_step":False,
            "correction":{"invoice_id":invoice.id,"changes":{"gross_amount":{"existing":"105.00","replacement":"126.00"}}}}
        row = StagingRow(batch_id=batch.id, row_number=1, raw_party=party.name,
            payload=json.dumps(payload), status="correction")
        session.add(row); session.commit()
        batch_id, row_id, invoice_id = batch.id, row.id, invoice.id

    path = f"/api/imports/{batch_id}/corrections/{row_id}"
    assert client.post(path, headers=headers["talco_staff"], json={"approve":True,"reason":"Tally correction"}).status_code == 403
    missing = client.post(path, headers=headers["talco_admin"], json={"approve":True,"reason":""})
    assert missing.status_code == 422
    approved = client.post(path, headers=headers["talco_admin"],
        json={"approve":True,"reason":"Corrected taxable value in Tally"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["corrections"] == 0
    detail = client.get(f"/api/portal/invoices/{invoice_id}", headers=headers["talco_admin"])
    assert detail.status_code == 200
    assert detail.json()["gross"] == "126.00"
    assert detail.json()["revision_count"] == 1
    assert detail.json()["account"] == "Correction Account"
    with factory() as session:
        invoice = session.get(Invoice, invoice_id)
        assert invoice.gross_amount == Decimal("126.00")
        revision = session.scalar(select(InvoiceRevision).where(InvoiceRevision.invoice_id == invoice_id))
        assert revision.reason == "Corrected taxable value in Tally"
        assert revision.source_batch_id == batch_id
        assert revision.revised_by
        audit = session.scalar(select(AuditLog).where(
            AuditLog.entity_type == "invoice", AuditLog.entity_id == invoice_id,
            AuditLog.action == "correction_approved"))
        assert audit is not None
def test_reimport_changed_invoice_is_held_for_review(master_api):
    from datetime import date
    from decimal import Decimal
    from pathlib import Path
    from sqlalchemy import select
    from app.models import ChargeHead, Invoice, Party, Pump, StagingRow, Tannery
    from app.services.import_pipeline import create_batch

    _, _, factory = master_api
    content = (Path(__file__).parent / "fixtures" / "ManualPost.xml").read_bytes()
    content = content.replace(b"-105.00", b"-126.00").replace(
        b">100.00</DBCLEDAMT>", b">120.00</DBCLEDAMT>").replace(
        b">2.50</DBCLEDAMT>", b">3.00</DBCLEDAMT>")
    with factory() as session:
        pump = Pump(code="Y", name="Review Pump")
        session.add(pump); session.flush()
        tannery = Tannery(sno=9002, name="ABC Associates", normalized_key="abc associates", pump_house="Y")
        party = Party(name="ABC Associates", normalized_key="abc associates")
        head = ChargeHead(code="REVIEW", name="Treatment", gst_rate=5)
        session.add_all([tannery, party, head]); session.flush()
        session.add(Invoice(tannery_id=tannery.id, party_id=party.id, charge_head_id=head.id,
            voucher_no="UAT-POST-001", fy="2026-2027", invoice_date=date(2026, 9, 10),
            base_amount=Decimal("100"), cgst=Decimal("2.5"), sgst=Decimal("2.5"),
            gross_amount=Decimal("105")))
        session.commit()
        batch = create_batch(session, "corrected-post.xml", content, date(2026, 9, 1), head.id)
        row = session.scalar(select(StagingRow).where(StagingRow.batch_id == batch.id))
        assert row.status == "correction"
        assert '"gross_amount": {"existing": "105.00", "replacement": "126.00"}' in row.payload
        invoice = session.scalar(select(Invoice).where(Invoice.voucher_no == "UAT-POST-001"))
        assert invoice.gross_amount == Decimal("105")