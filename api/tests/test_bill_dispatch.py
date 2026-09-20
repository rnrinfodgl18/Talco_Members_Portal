"""Bill dispatch: the right people, the right channels, exactly once."""
import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import (ChargeHead, ImportBatch, Invoice, Notification, Party,
                        StagingRow, Tannery, TanneryPartyLink)
from app.models.auth import User
from app.services import bill_dispatch
from test_tannery_crud import master_api


@pytest.fixture()
def posted_batch(master_api, monkeypatch):
    client, headers, factory = master_api
    monkeypatch.setattr(bill_dispatch, "invoice_pdf", lambda session, invoice: b"%PDF-fake")
    with factory() as session:
        tannery = Tannery(sno=1, name="Vaigai A-Unit", normalized_key="vaigaiaunit", pump_house="A")
        party = Party(name="Asian Leathers C/o. Vaigai", normalized_key="asianleathersvaigai")
        head = ChargeHead(code="TREATMENT", name="Treatment charges", gst_rate=Decimal("5.00"))
        session.add_all([tannery, party, head]); session.flush()
        session.add(TanneryPartyLink(tannery_id=tannery.id, party_id=party.id,
                                     role="lessee", valid_from=date(2026, 7, 1)))
        invoice = Invoice(tannery_id=tannery.id, party_id=party.id, charge_head_id=head.id,
                          voucher_no="123/2026-2027", fy="2026-2027", invoice_date=date(2026, 8, 31),
                          base_amount=Decimal("96300.00"), cgst=Decimal("2407.50"),
                          sgst=Decimal("2407.50"), gross_amount=Decimal("101115.00"))
        batch = ImportBatch(file_name="aug.xlsx", file_sha256="abc", status="posted",
                            period_start=date(2026, 8, 1), charge_head_id=head.id)
        session.add_all([invoice, batch]); session.flush()
        session.add(StagingRow(batch_id=batch.id, row_number=1, raw_party=party.name, status="posted",
                               payload=json.dumps({"voucher_no": "123/2026-2027",
                                                   "date": "2026-08-31", "is_receipt": False})))
        lessee = session.scalar(select(User).where(User.email == "lessee@test.local"))
        lessee.tannery_id, lessee.party_id = tannery.id, party.id
        lessee.phone = "+91 98765 43210"
        session.commit()
        ids = {"batch": batch.id, "invoice": invoice.id, "lessee": lessee.id}
    return client, headers, factory, ids


def test_dispatch_sends_pdf_by_email_and_a_link_by_whatsapp(posted_batch, monkeypatch):
    client, headers, factory, ids = posted_batch
    emails, texts = [], []
    monkeypatch.setattr(bill_dispatch, "send_email",
        lambda s, u, subject, body, nid=None, attachments=None, **kw: emails.append(
            (u.id, subject, attachments)) or True)
    monkeypatch.setattr(bill_dispatch, "send_whatsapp",
        lambda s, u, message, **kw: texts.append((u.id, message)) or True)
    monkeypatch.setattr(bill_dispatch, "send_push", lambda s, u, n: 0)

    result = client.post(f"/api/imports/{ids['batch']}/dispatch", headers=headers["talco_admin"])
    assert result.status_code == 200, result.text
    assert result.json()["invoices"] == 1 and result.json()["emailed"] == 1

    assert [u for u, _, _ in emails] == [ids["lessee"]]
    filename, mime, content = emails[0][2][0]
    assert filename == "invoice-123-2026-2027.pdf" and mime == "application/pdf"
    assert content == b"%PDF-fake"

    assert len(texts) == 1
    message = texts[0][1]
    assert "123/2026-2027" in message and "/portal" in message
    assert "pdf" not in message.lower(), "the PDF must never go over the WhatsApp gateway"


def test_dispatch_is_safe_to_run_twice(posted_batch, monkeypatch):
    client, headers, factory, ids = posted_batch
    monkeypatch.setattr(bill_dispatch, "send_email", lambda *a, **k: True)
    monkeypatch.setattr(bill_dispatch, "send_whatsapp", lambda *a, **k: True)
    monkeypatch.setattr(bill_dispatch, "send_push", lambda s, u, n: 0)
    admin = headers["talco_admin"]

    first = client.post(f"/api/imports/{ids['batch']}/dispatch", headers=admin).json()
    second = client.post(f"/api/imports/{ids['batch']}/dispatch", headers=admin).json()

    assert first["recipients"] == 1
    assert second["recipients"] == 0 and second["skipped_already_sent"] == 1
    with factory() as session:
        sent = session.scalars(select(Notification).where(
            Notification.kind == "bill", Notification.entity_id == ids["invoice"])).all()
        assert len(sent) == 1, "a second run must not create a second bill notification"


def test_dispatch_refuses_a_batch_that_was_never_posted(posted_batch):
    client, headers, factory, ids = posted_batch
    with factory() as session:
        session.get(ImportBatch, ids["batch"]).status = "reviewed"
        session.commit()
    refused = client.post(f"/api/imports/{ids['batch']}/dispatch", headers=headers["talco_admin"])
    assert refused.status_code == 409


def test_dispatch_requires_office_role(posted_batch):
    client, headers, factory, ids = posted_batch
    assert client.post(f"/api/imports/{ids['batch']}/dispatch",
                       headers=headers["member"]).status_code == 403
