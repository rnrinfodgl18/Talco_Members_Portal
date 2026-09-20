"""The admin issues credentials directly: many tannery owners have no email."""
from sqlalchemy import func, select

from app.models.auth import User
from test_tannery_crud import master_api


def _tannery(client, headers):
    created = client.post("/api/tanneries", headers=headers["talco_admin"], json={
        "name": "Vaigai A-Unit", "pump_house": "A"})
    assert created.status_code in {200, 201}, created.text
    return created.json()["id"]


def test_admin_creates_a_username_only_account_and_sees_the_credentials_once(master_api):
    client, headers, factory = master_api
    tannery_id = _tannery(client, headers)
    created = client.post("/api/auth/invite", headers=headers["talco_admin"], json={
        "role": "member", "username": "vaigai.a", "display_name": "Vaigai Leather Corporation",
        "phone": "+91 98765 43210", "password": "HandedOver123", "tannery_id": tannery_id})
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["user"]["email"] is None
    assert body["user"]["username"] == "vaigai.a"
    assert body["email_delivery"] == "not_required"
    assert body["credentials"] == {"identifier": "vaigai.a", "password": "HandedOver123"}

    signed_in = client.post("/api/auth/login", json={
        "identifier": "vaigai.a", "password": "HandedOver123"})
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["user"]["phone"]


def test_account_with_no_email_needs_a_password(master_api):
    client, headers, _ = master_api
    tannery_id = _tannery(client, headers)
    refused = client.post("/api/auth/invite", headers=headers["talco_admin"], json={
        "role": "member", "username": "no.password", "tannery_id": tannery_id})
    assert refused.status_code == 422


def test_account_needs_a_username_or_an_email(master_api):
    client, headers, _ = master_api
    tannery_id = _tannery(client, headers)
    refused = client.post("/api/auth/invite", headers=headers["talco_admin"], json={
        "role": "member", "password": "HandedOver123", "tannery_id": tannery_id})
    assert refused.status_code == 422


def test_usernames_stay_unique(master_api):
    client, headers, _ = master_api
    tannery_id = _tannery(client, headers)
    payload = {"role": "member", "username": "vaigai.a", "password": "HandedOver123",
               "tannery_id": tannery_id}
    assert client.post("/api/auth/invite", headers=headers["talco_admin"], json=payload).status_code == 200
    assert client.post("/api/auth/invite", headers=headers["talco_admin"], json=payload).status_code == 409


def test_several_accounts_can_have_no_email(master_api):
    """The unique index on email must tolerate more than one NULL."""
    client, headers, factory = master_api
    tannery_id = _tannery(client, headers)
    for name in ("vaigai.a", "vaigai.b", "shan.a"):
        assert client.post("/api/auth/invite", headers=headers["talco_admin"], json={
            "role": "member", "username": name, "password": "HandedOver123",
            "tannery_id": tannery_id}).status_code == 200
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(User).where(User.email.is_(None))) == 3


def test_email_invitation_path_still_works(master_api):
    client, headers, _ = master_api
    tannery_id = _tannery(client, headers)
    created = client.post("/api/auth/invite", headers=headers["talco_admin"], json={
        "role": "member", "email": "Owner@Example.Test", "tannery_id": tannery_id})
    assert created.status_code == 200, created.text
    assert created.json()["user"]["email"] == "owner@example.test"
    assert created.json()["user"]["must_set_password"] is True
    assert "credentials" not in created.json()
