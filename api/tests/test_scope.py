from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import ChargeHead, Invoice, Party, Tannery, TanneryPartyLink
from app.models.auth import User
from app.services.scope import user_scope
from test_tannery_crud import master_api


def user(role, tannery_id=None, party_id=None):
    return SimpleNamespace(role=role, tannery_id=tannery_id, party_id=party_id)


def test_owner_cannot_change_tannery_id():
    with pytest.raises(HTTPException) as error:
        user_scope(user("member", 4), requested_tannery_id=29)
    assert error.value.status_code == 403


def test_lessee_cannot_change_party_or_tannery():
    with pytest.raises(HTTPException): user_scope(user("lessee", 4, 10), 29, 10)
    with pytest.raises(HTTPException): user_scope(user("lessee", 4, 10), 4, 11)
    assert user_scope(user("lessee", 4, 10)).party_id == 10


def test_owner_scope_keeps_all_parties_at_own_tannery():
    scope = user_scope(user("member", 4))
    assert scope.tannery_id == 4 and scope.party_id is None


def test_lessee_cannot_see_invoices_raised_outside_their_lease(master_api):
    """A unit that changed hands: the new lessee must not see the old lessee's bills."""
    client, headers, factory = master_api
    with factory() as session:
        tannery = Tannery(sno=1, name="Vaigai A-Unit", normalized_key="vaigaiaunit", pump_house="A")
        party = Party(name="Asian Leathers C/o. Vaigai", normalized_key="asianleathersvaigai")
        head = ChargeHead(code="TREATMENT", name="Treatment charges", gst_rate=Decimal("5.00"))
        session.add_all([tannery, party, head]); session.flush()
        # The ledger is reused across tenants; this lessee's lease starts 1 Jul 2026.
        session.add(TanneryPartyLink(tannery_id=tannery.id, party_id=party.id,
                                     role="lessee", valid_from=date(2026, 7, 1)))
        for label, invoice_date in (("pre-lease", date(2026, 5, 31)), ("in-lease", date(2026, 8, 31))):
            session.add(Invoice(tannery_id=tannery.id, party_id=party.id, charge_head_id=head.id,
                                voucher_no=f"{label}/2026-2027", fy="2026-2027", invoice_date=invoice_date,
                                base_amount=Decimal("1000.00"), cgst=Decimal("25.00"),
                                sgst=Decimal("25.00"), gross_amount=Decimal("1050.00")))
        lessee = session.scalar(select(User).where(User.email == "lessee@test.local"))
        lessee.tannery_id, lessee.party_id = tannery.id, party.id
        session.commit()
    listed = client.get("/api/portal/invoices", headers=headers["lessee"]).json()
    vouchers = {row["voucher_no"] for row in (listed["items"] if isinstance(listed, dict) else listed)}
    assert vouchers == {"in-lease/2026-2027"}, vouchers


def test_lease_window_leaves_non_lessee_access_untouched(master_api):
    """An owner-member sees their unit's bills regardless of any lease dates."""
    client, headers, factory = master_api
    with factory() as session:
        tannery = Tannery(sno=1, name="T.M.S.Leathers", normalized_key="tmsleathers", pump_house="A")
        party = Party(name="T.M.S.Leathers", normalized_key="tmsleathersparty")
        head = ChargeHead(code="TREATMENT", name="Treatment charges", gst_rate=Decimal("5.00"))
        session.add_all([tannery, party, head]); session.flush()
        session.add(Invoice(tannery_id=tannery.id, party_id=party.id, charge_head_id=head.id,
                            voucher_no="001/2026-2027", fy="2026-2027", invoice_date=date(2026, 5, 31),
                            base_amount=Decimal("1000.00"), cgst=Decimal("25.00"),
                            sgst=Decimal("25.00"), gross_amount=Decimal("1050.00")))
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        member.tannery_id = tannery.id
        session.commit()
    listed = client.get("/api/portal/invoices", headers=headers["member"]).json()
    items = listed["items"] if isinstance(listed, dict) else listed
    assert [row["voucher_no"] for row in items] == ["001/2026-2027"]
