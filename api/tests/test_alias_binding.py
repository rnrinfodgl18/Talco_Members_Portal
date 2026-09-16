from datetime import date

from sqlalchemy import select

from app.models import Party, PartyAlias, Tannery, TanneryPartyLink
from test_tannery_crud import master_api


def test_admin_can_unbind_and_rebind_alias(master_api):
    client, headers, factory = master_api
    with factory() as session:
        first = Tannery(sno=301, name="First Works", normalized_key="FIRSTWORKS", pump_house="A")
        second = Tannery(sno=302, name="Second Works", normalized_key="SECONDWORKS", pump_house="B")
        party = Party(name="Member Account", normalized_key="MEMBERACCOUNT")
        session.add_all([first, second, party]); session.flush()
        session.add(TanneryPartyLink(tannery_id=first.id, party_id=party.id,
                                     role="owner", valid_from=date(2026, 4, 1)))
        alias = PartyAlias(party_id=party.id, tannery_id=first.id, raw_name="Tally Member Name",
                           normalized_key="TALLYMEMBERNAME", excluded=False)
        session.add(alias); session.commit()
        alias_id, second_id = alias.id, second.id

    listing = client.get("/api/mappings/aliases", headers=headers["talco_admin"])
    row = next(item for item in listing.json() if item["id"] == alias_id)
    assert row["account_name"] == "Member Account"
    assert row["tannery_name"] == "First Works"

    unbound = client.post(f"/api/mappings/aliases/{alias_id}/revoke",
                          headers=headers["talco_admin"])
    assert unbound.status_code == 200
    assert unbound.json()["revoked_at"] is not None

    rebound = client.post(f"/api/mappings/aliases/{alias_id}/bind",
        headers=headers["talco_admin"], json={"tannery_id": second_id, "role": "lessee",
                                               "valid_from": "2026-09-01"})
    assert rebound.status_code == 200, rebound.text
    assert rebound.json()["revoked_at"] is None
    assert rebound.json()["tannery_name"] == "Second Works"
    with factory() as session:
        alias = session.get(PartyAlias, alias_id)
        assert alias.tannery_id == second_id
        assert session.scalar(select(TanneryPartyLink).where(
            TanneryPartyLink.party_id == alias.party_id,
            TanneryPartyLink.tannery_id == second_id)) is not None


def test_staff_cannot_change_alias_binding(master_api):
    client, headers, _ = master_api
    payload = {"tannery_id": 1, "role": "owner", "valid_from": "2026-09-01"}
    assert client.post("/api/mappings/aliases/1/bind", headers=headers["talco_staff"],
                       json=payload).status_code == 403
    assert client.post("/api/mappings/aliases/1/revoke",
                       headers=headers["talco_staff"]).status_code == 403
