"""Role-wise and dues-based circular audiences, resolved and snapshotted at send time."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import ChargeHead, CircularRecipient, Invoice, Party, Receipt, Tannery, TanneryPartyLink
from app.models.auth import User
from test_tannery_crud import master_api


@pytest.fixture()
def portal(master_api):
    """Two ledgers: one in arrears held by a lessee, one settled held by a member."""
    client, headers, factory = master_api
    with factory() as session:
        tannery = Tannery(sno=1, name="Vaigai A-Unit", normalized_key="vaigaiaunit", pump_house="A")
        settled_unit = Tannery(sno=2, name="Shan A-Unit", normalized_key="shanaunit", pump_house="B")
        head = ChargeHead(code="TREATMENT", name="Treatment charges", gst_rate=Decimal("5.00"))
        owing = Party(name="Asian Leathers C/o. Vaigai", normalized_key="asianvaigai")
        settled = Party(name="Shan Leathers", normalized_key="shanleathers")
        session.add_all([tannery, settled_unit, head, owing, settled]); session.flush()
        session.add_all([
            TanneryPartyLink(tannery_id=tannery.id, party_id=owing.id, role="lessee",
                             valid_from=date(2026, 1, 1)),
            TanneryPartyLink(tannery_id=settled_unit.id, party_id=settled.id, role="owner",
                             valid_from=date(2026, 1, 1)),
            Invoice(tannery_id=tannery.id, party_id=owing.id, charge_head_id=head.id,
                    voucher_no="1/2026-2027", fy="2026-2027", invoice_date=date(2026, 8, 31),
                    base_amount=Decimal("10000.00"), cgst=Decimal("250.00"),
                    sgst=Decimal("250.00"), gross_amount=Decimal("10500.00")),
            Invoice(tannery_id=settled_unit.id, party_id=settled.id, charge_head_id=head.id,
                    voucher_no="2/2026-2027", fy="2026-2027", invoice_date=date(2026, 8, 31),
                    base_amount=Decimal("1000.00"), cgst=Decimal("25.00"),
                    sgst=Decimal("25.00"), gross_amount=Decimal("1050.00")),
            Receipt(tannery_id=settled_unit.id, party_id=settled.id, voucher_no="R2/2026-2027",
                    fy="2026-2027", receipt_date=date(2026, 9, 6), amount=Decimal("1050.00")),
        ])
        lessee = session.scalar(select(User).where(User.email == "lessee@test.local"))
        lessee.tannery_id, lessee.party_id, lessee.display_name = tannery.id, owing.id, "Asian Leathers"
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        member.tannery_id, member.display_name = settled_unit.id, "Shan Leathers"
        staff = session.scalar(select(User).where(User.email == "member_staff@test.local"))
        staff.tannery_id, staff.display_name = settled_unit.id, "Shan Accountant"
        session.commit()
        ids = {"lessee": lessee.id, "member": member.id, "staff": staff.id}
    return client, headers, factory, ids


def _publish(client, headers, **fields):
    form = {"title": "Pump B shutdown", "content": "Maintenance on Sunday",
            "audience": "all", "status": "published", **fields}
    return client.post("/api/circulars", headers=headers["talco_admin"], data=form)


def _recipients(factory, circular_id):
    with factory() as session:
        return set(session.scalars(select(CircularRecipient.user_id).where(
            CircularRecipient.circular_id == circular_id)))


def test_role_wise_circular_reaches_only_those_roles(portal):
    client, headers, factory, ids = portal
    created = _publish(client, headers, audience="roles", audience_roles="lessee")
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["audience"] == "roles" and body["audience_roles"] == ["lessee"]
    assert _recipients(factory, body["id"]) == {ids["lessee"]}

    assert client.get("/api/circulars", headers=headers["lessee"]).json()
    assert client.get("/api/circulars", headers=headers["member"]).json() == []


def test_role_wise_circular_accepts_several_roles(portal):
    client, headers, factory, ids = portal
    body = _publish(client, headers, audience="roles",
                    audience_roles="member,member_staff").json()
    assert _recipients(factory, body["id"]) == {ids["member"], ids["staff"]}


def test_role_wise_circular_rejects_an_unknown_role(portal):
    client, headers, _, _ = portal
    assert _publish(client, headers, audience="roles", audience_roles="talco_admin").status_code == 422
    assert _publish(client, headers, audience="roles", audience_roles="").status_code == 422


def test_outstanding_circular_reaches_only_ledgers_in_arrears(portal):
    client, headers, factory, ids = portal
    body = _publish(client, headers, audience="outstanding").json()
    assert _recipients(factory, body["id"]) == {ids["lessee"]}, "the settled ledger owes nothing"
    assert client.get("/api/circulars", headers=headers["member"]).json() == []


def test_outstanding_audience_is_a_snapshot_not_a_live_rule(portal):
    """Paying up afterwards must not hide a notice that was already addressed."""
    client, headers, factory, ids = portal
    body = _publish(client, headers, audience="outstanding").json()
    with factory() as session:
        owing = session.scalar(select(Party).where(Party.normalized_key == "asianvaigai"))
        link = session.scalar(select(TanneryPartyLink).where(TanneryPartyLink.party_id == owing.id))
        session.add(Receipt(tannery_id=link.tannery_id, party_id=owing.id,
                            voucher_no="R1/2026-2027", fy="2026-2027",
                            receipt_date=date(2026, 9, 10), amount=Decimal("10500.00")))
        session.commit()
    assert _recipients(factory, body["id"]) == {ids["lessee"]}
    assert [row["id"] for row in client.get("/api/circulars", headers=headers["lessee"]).json()] == [body["id"]]


def test_an_audience_matching_nobody_is_refused(portal):
    client, headers, factory, _ = portal
    with factory() as session:
        for row in session.scalars(select(User).where(User.role == "lessee")):
            row.active = False
        session.commit()
    assert _publish(client, headers, audience="roles", audience_roles="lessee").status_code == 422


def test_audience_preview_counts_before_sending(portal):
    client, headers, _, _ = portal
    admin = headers["talco_admin"]
    dues = client.get("/api/circulars/audience/preview?audience=outstanding", headers=admin).json()
    assert dues["count"] == 1 and dues["names"] == ["Asian Leathers"]
    by_role = client.get("/api/circulars/audience/preview?audience=roles&roles=member,member_staff",
                         headers=admin).json()
    assert by_role["count"] == 2
    everyone = client.get("/api/circulars/audience/preview?audience=all", headers=admin).json()
    assert everyone["count"] == 3
