"""Delivery log filtering, and the per-item recipient drill-down."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import Circular, CircularRead, DeliveryLog, Notification
from app.models.auth import User
from test_tannery_crud import master_api


@pytest.fixture()
def delivered(master_api):
    client, headers, factory = master_api
    with factory() as session:
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        member.display_name, member.phone = "Vaigai Leather", "+919876543210"
        staff = session.scalar(select(User).where(User.email == "member_staff@test.local"))
        staff.display_name = "Shan Leathers"
        admin = session.scalar(select(User).where(User.email == "talco_admin@test.local"))
        session.add(Circular(id=7, title="Pump B shutdown", content="Maintenance on Sunday",
                             audience="all", status="published", created_by=admin.id))
        session.commit()
        circular = Notification(user_id=member.id, kind="circular", title="Pump B shutdown",
                                message="Maintenance on Sunday", link="/?page=circulars",
                                entity_type="circular", entity_id=7,
                                read_at=datetime.now(timezone.utc))
        unread = Notification(user_id=staff.id, kind="circular", title="Pump B shutdown",
                              message="Maintenance on Sunday", link="/?page=circulars",
                              entity_type="circular", entity_id=7)
        session.add_all([circular, unread]); session.flush()
        session.add_all([
            DeliveryLog(user_id=member.id, notification_id=circular.id, channel="email",
                        destination="member@test.local", status="sent"),
            DeliveryLog(user_id=member.id, notification_id=circular.id, channel="whatsapp",
                        destination="919876543210", status="sent"),
            DeliveryLog(user_id=staff.id, notification_id=unread.id, channel="email",
                        destination="member_staff@test.local", status="failed",
                        detail="Mailbox unavailable"),
        ])
        session.add(CircularRead(circular_id=7, user_id=member.id))
        session.commit()
        ids = {"member": member.id, "staff": staff.id}
    return client, headers, factory, ids


def test_delivery_log_paginates_and_filters(delivered):
    client, headers, _, _ = delivered
    admin = headers["talco_admin"]
    everything = client.get("/api/notifications/delivery-log", headers=admin).json()
    assert everything["total"] == 3 and len(everything["items"]) == 3
    assert everything["items"][0]["subject"] == "Pump B shutdown"

    by_channel = client.get("/api/notifications/delivery-log?channel=whatsapp", headers=admin).json()
    assert by_channel["total"] == 1
    assert by_channel["items"][0]["destination"] == "919876543210"

    failures = client.get("/api/notifications/delivery-log?status=failed", headers=admin).json()
    assert failures["total"] == 1
    assert failures["items"][0]["detail"] == "Mailbox unavailable"

    by_kind = client.get("/api/notifications/delivery-log?kind=circular", headers=admin).json()
    assert by_kind["total"] == 3

    searched = client.get("/api/notifications/delivery-log?search=vaigai", headers=admin).json()
    assert searched["total"] == 2
    assert {row["recipient"] for row in searched["items"]} == {"Vaigai Leather"}

    paged = client.get("/api/notifications/delivery-log?page_size=2", headers=admin).json()
    assert paged["pages"] == 2 and len(paged["items"]) == 2


def test_delivery_log_filter_options_come_from_the_data(delivered):
    client, headers, _, _ = delivered
    options = client.get("/api/notifications/delivery-log/filters", headers=headers["talco_admin"]).json()
    assert options["channels"] == ["email", "whatsapp"]
    assert options["statuses"] == ["failed", "sent"]
    assert options["kinds"] == ["circular"]


def test_drill_down_shows_recipients_channels_and_read_state(delivered):
    client, headers, _, ids = delivered
    detail = client.get("/api/notifications/deliveries/circular/7",
                        headers=headers["talco_admin"]).json()
    assert detail["subject"] == "Pump B shutdown"
    assert detail["totals"] == {"recipients": 2, "read": 1, "unread": 1,
                                "email_sent": 1, "email_failed": 1,
                                "whatsapp_sent": 1, "whatsapp_failed": 0, "push_sent": 0}
    by_name = {row["recipient"]: row for row in detail["recipients"]}
    assert by_name["Vaigai Leather"]["read"] is True
    assert by_name["Vaigai Leather"]["channels"]["whatsapp"]["status"] == "sent"
    assert by_name["Shan Leathers"]["read"] is False
    assert by_name["Shan Leathers"]["channels"]["email"]["status"] == "failed"
    assert "whatsapp" not in by_name["Shan Leathers"]["channels"]


def test_drill_down_rejects_unknown_item_types(delivered):
    client, headers, _, _ = delivered
    assert client.get("/api/notifications/deliveries/tannery/7",
                      headers=headers["talco_admin"]).status_code == 404


def test_delivery_views_are_admin_only(delivered):
    client, headers, _, _ = delivered
    for role in ("talco_staff", "member", "lessee"):
        assert client.get("/api/notifications/delivery-log", headers=headers[role]).status_code == 403
        assert client.get("/api/notifications/deliveries/circular/7",
                          headers=headers[role]).status_code == 403
