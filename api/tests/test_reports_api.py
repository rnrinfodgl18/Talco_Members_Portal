"""Admin outstanding summary: the number must match the member's own ledger."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import ChargeHead, Invoice, Party, Receipt, Tannery, TanneryPartyLink
from app.models.auth import User
from test_tannery_crud import master_api


@pytest.fixture()
def ledgers(master_api):
    client, headers, factory = master_api
    with factory() as session:
        tannery = Tannery(sno=1, name="Vaigai A-Unit", normalized_key="vaigaiaunit", pump_house="A")
        head = ChargeHead(code="TREATMENT", name="Treatment charges", gst_rate=Decimal("5.00"))
        paid_up = Party(name="Shan Leathers", normalized_key="shanleathers",
                        opening_amount=Decimal("0.00"))
        in_dues = Party(name="Asian Leathers C/o. Vaigai", normalized_key="asianvaigai",
                        opening_amount=Decimal("5000.00"))
        session.add_all([tannery, head, paid_up, in_dues]); session.flush()
        session.add_all([
            TanneryPartyLink(tannery_id=tannery.id, party_id=in_dues.id,
                             role="lessee", valid_from=date(2026, 7, 1)),
            Invoice(tannery_id=tannery.id, party_id=in_dues.id, charge_head_id=head.id,
                    voucher_no="1/2026-2027", fy="2026-2027", invoice_date=date(2026, 8, 31),
                    base_amount=Decimal("10000.00"), cgst=Decimal("250.00"),
                    sgst=Decimal("250.00"), gross_amount=Decimal("10500.00")),
            Receipt(tannery_id=tannery.id, party_id=in_dues.id, voucher_no="R1/2026-2027",
                    fy="2026-2027", receipt_date=date(2026, 9, 5), amount=Decimal("2500.00")),
            Invoice(tannery_id=tannery.id, party_id=paid_up.id, charge_head_id=head.id,
                    voucher_no="2/2026-2027", fy="2026-2027", invoice_date=date(2026, 8, 31),
                    base_amount=Decimal("1000.00"), cgst=Decimal("25.00"),
                    sgst=Decimal("25.00"), gross_amount=Decimal("1050.00")),
            Receipt(tannery_id=tannery.id, party_id=paid_up.id, voucher_no="R2/2026-2027",
                    fy="2026-2027", receipt_date=date(2026, 9, 6), amount=Decimal("1050.00")),
        ])
        session.commit()
    return client, headers, factory


def test_outstanding_summary_totals_and_ordering(ledgers):
    client, headers, _ = ledgers
    body = client.get("/api/reports/outstanding", headers=headers["talco_admin"]).json()
    assert body["accounts"] == 2 and body["accounts_with_dues"] == 1
    # opening 5000 + billed 10500 - collected 2500
    assert body["rows"][0]["name"] == "Asian Leathers C/o. Vaigai"
    assert body["rows"][0]["outstanding"] == "13000.00"
    assert body["rows"][0]["tanneries"] == ["Vaigai A-Unit"]
    assert body["rows"][1]["outstanding"] == "0.00"
    assert body["totals"]["outstanding"] == "13000.00"
    assert body["totals"]["billed"] == "11550.00"


def test_outstanding_summary_is_sortable(ledgers):
    client, headers, _ = ledgers
    ascending = client.get("/api/reports/outstanding?sort=name&direction=asc",
                           headers=headers["talco_admin"]).json()
    assert [row["name"] for row in ascending["rows"]] == [
        "Asian Leathers C/o. Vaigai", "Shan Leathers"]
    descending = client.get("/api/reports/outstanding?sort=name&direction=desc",
                            headers=headers["talco_admin"]).json()
    assert [row["name"] for row in descending["rows"]] == [
        "Shan Leathers", "Asian Leathers C/o. Vaigai"]


def test_outstanding_summary_exports_csv(ledgers):
    client, headers, _ = ledgers
    export = client.get("/api/reports/outstanding.csv", headers=headers["talco_admin"])
    assert export.status_code == 200
    assert "attachment" in export.headers["content-disposition"]
    lines = export.text.strip().splitlines()
    assert lines[0].startswith("Account,Ledger name,Units")
    assert "13000.00" in lines[1]


def test_outstanding_summary_is_office_only(ledgers):
    client, headers, _ = ledgers
    for role in ("member", "member_staff", "lessee"):
        assert client.get("/api/reports/outstanding", headers=headers[role]).status_code == 403
