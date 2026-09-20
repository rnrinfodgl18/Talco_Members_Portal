from sqlalchemy import select

from app.models import Notification
from app.models.auth import User
from app.security import hash_password
from test_tannery_crud import master_api


def test_username_phone_login_and_profile_update(master_api):
    client, headers, factory = master_api
    with factory() as session:
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        member.username = "member.one"
        member.phone = "+91 98765 43210"
        member.password_hash = hash_password("StrongPass123")
        session.commit()
    for identifier in ("member.one", "member@test.local", "9876543210"):
        response = client.post("/api/auth/login", json={"identifier": identifier, "password": "StrongPass123"})
        assert response.status_code == 200, response.text
        assert response.json()["user"]["username"] == "member.one"
    updated = client.put("/api/settings/profile", headers=headers["member"], json={
        "username": "member.updated", "display_name": "Member One",
        "email": "member@test.local", "phone": "+91 98765 43210"})
    assert updated.status_code == 200
    assert updated.json()["username"] == "member.updated"


def test_notification_pagination_and_unread_toggle(master_api):
    client, headers, factory = master_api
    with factory() as session:
        user = session.scalar(select(User).where(User.email == "member@test.local"))
        session.add_all(Notification(user_id=user.id, kind="test", title=f"Notice {i}", message="Test") for i in range(13))
        session.commit()
    first = client.get("/api/notifications?page=1&page_size=5&status=unread", headers=headers["member"]).json()
    assert first["total"] == 13 and first["pages"] == 3 and len(first["items"]) == 5
    item = first["items"][0]
    assert client.post(f"/api/notifications/{item['id']}/read", headers=headers["member"]).status_code == 200
    assert client.post(f"/api/notifications/{item['id']}/unread", headers=headers["member"]).json()["status"] == "unread"

