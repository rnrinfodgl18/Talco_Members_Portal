from datetime import datetime, timezone

from sqlalchemy import select

from app.models import DeliveryLog, Notification, PushSubscription
from app.models.auth import User
from app.security import issue_token
from test_tannery_crud import master_api


def test_member_notification_scope_read_and_subscription(master_api):
    client, headers, factory = master_api
    with factory() as session:
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        lessee = session.scalar(select(User).where(User.email == "lessee@test.local"))
        session.add_all([
            Notification(user_id=member.id, kind="test", title="Member alert", message="Private"),
            Notification(user_id=lessee.id, kind="test", title="Lessee alert", message="Private"),
        ])
        session.commit()
    result = client.get("/api/notifications", headers=headers["member"]).json()
    assert result["unread"] == 1
    assert [row["title"] for row in result["items"]] == ["Member alert"]
    notification_id = result["items"][0]["id"]
    assert client.post(f"/api/notifications/{notification_id}/read", headers=headers["lessee"]).status_code == 404
    assert client.post(f"/api/notifications/{notification_id}/read", headers=headers["member"]).status_code == 200
    subscription = {"endpoint":"https://push.example.test/subscription/12345",
                    "keys":{"p256dh":"p"*32, "auth":"a"*16}}
    assert client.post("/api/notifications/subscriptions", headers=headers["member"], json=subscription).status_code == 200
    with factory() as session:
        row = session.scalar(select(PushSubscription))
        assert row.user_id == session.scalar(select(User.id).where(User.email == "member@test.local"))


def test_email_verification_and_delivery_log(master_api):
    client, headers, factory = master_api
    with factory() as session:
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        raw = issue_token(session, member, "verify_email", 1)
    assert client.post("/api/auth/verify-email", json={"token":raw}).status_code == 200
    assert client.post("/api/auth/verify-email", json={"token":raw}).status_code == 400
    assert client.post("/api/auth/verification-email", headers=headers["member"]).json()["status"] == "already_verified"
    with factory() as session:
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        assert member.email_verified_at is not None


def test_admin_and_member_dashboards_are_role_scoped(master_api):
    client, headers, _ = master_api
    admin = client.get("/api/dashboard/admin", headers=headers["talco_admin"])
    assert admin.status_code == 200
    assert {"tanneries","members","unverified_emails","outstanding","recent_imports","pending_mappings"} <= admin.json().keys()
    assert client.get("/api/dashboard/admin", headers=headers["member"]).status_code == 403
    member = client.get("/api/dashboard/member", headers=headers["member"])
    assert member.status_code == 200
    assert {"accounts","total_outstanding","unread_notifications","email_verified","latest_invoice","latest_receipt","recent_invoices","notice_summary"} <= member.json().keys()
    assert client.get("/api/notifications/delivery-log", headers=headers["talco_staff"]).status_code == 403
    assert client.get("/api/notifications/delivery-log", headers=headers["talco_admin"]).status_code == 200


def test_push_records_why_it_did_not_deliver(master_api, monkeypatch):
    """A silent nothing is why 'push does not work' is hard to diagnose."""
    from sqlalchemy import select

    from app.config import get_settings
    from app.models import DeliveryLog, Notification
    from app.models.auth import User
    from app.services.notifications import send_push

    client, headers, factory = master_api
    get_settings.cache_clear()
    with factory() as session:
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        row = Notification(user_id=member.id, kind="circular", title="Notice", message="Body")
        session.add(row); session.commit()

        monkeypatch.setattr("app.services.notifications.get_settings",
            lambda: type("S", (), {"vapid_private_key": None, "vapid_public_key": None})())
        assert send_push(session, member, row) == 0
        session.commit()
        logged = session.scalar(select(DeliveryLog).where(DeliveryLog.channel == "push"))
        assert "VAPID" in logged.detail

        session.delete(logged); session.commit()
        monkeypatch.setattr("app.services.notifications.get_settings",
            lambda: type("S", (), {"vapid_private_key": "x", "vapid_public_key": "y",
                                   "vapid_subject": "mailto:a@b.test"})())
        assert send_push(session, member, row) == 0
        session.commit()
        logged = session.scalar(select(DeliveryLog).where(DeliveryLog.channel == "push"))
        assert "No device has push enabled" in logged.detail
