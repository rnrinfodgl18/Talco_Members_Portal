from datetime import date, timedelta
from sqlalchemy import select

from app.models import AuditLog, Circular, CircularRead
from app.models.auth import User
from test_tannery_crud import master_api


def publish(client, headers, **overrides):
    data = {
        "title": "September review meeting",
        "content": "Meeting on 15 September at 10:30 AM.\nBring the monthly records.",
        "category": "meeting", "priority": "important", "audience": "all",
        "status": "published", "recipient_ids": "[]",
    }
    data.update(overrides)
    return client.post("/api/circulars", headers=headers, data=data)


def test_global_circular_notice_read_and_attachment(master_api):
    client, headers, factory = master_api
    response = client.post("/api/circulars", headers=headers["talco_staff"],
        data={"title":"Compliance circular", "content":"Submit the report.", "category":"compliance",
              "priority":"urgent", "audience":"all", "status":"published", "recipient_ids":"[]"},
        files={"attachment":("notice.pdf", b"%PDF-test", "application/pdf")})
    assert response.status_code == 201, response.text
    circular = response.json()
    member_items = client.get("/api/circulars", headers=headers["member"]).json()
    assert [row["id"] for row in member_items] == [circular["id"]]
    assert member_items[0]["is_read"] is False
    assert client.post(f"/api/circulars/{circular['id']}/read", headers=headers["member"]).status_code == 200
    assert client.get("/api/circulars", headers=headers["member"]).json()[0]["is_read"] is True
    attachment = client.get(f"/api/circulars/{circular['id']}/attachment", headers=headers["member"])
    assert attachment.content == b"%PDF-test"
    with factory() as session:
        user = session.scalar(select(User).where(User.email == "member@test.local"))
        assert session.get(CircularRead, (circular["id"], user.id))


def test_selected_circular_is_private_and_expired_notice_is_hidden(master_api):
    client, headers, factory = master_api
    with factory() as session:
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        member_id = member.id
    selected = publish(client, headers["talco_admin"], audience="selected",
                       recipient_ids=f"[{member_id}]")
    assert selected.status_code == 201, selected.text
    circular_id = selected.json()["id"]
    assert [x["id"] for x in client.get("/api/circulars", headers=headers["member"]).json()] == [circular_id]
    assert client.get("/api/circulars", headers=headers["lessee"]).json() == []
    assert client.get(f"/api/circulars/{circular_id}/attachment", headers=headers["lessee"]).status_code == 404
    expired = publish(client, headers["talco_admin"], title="Old notice",
                      expires_on=(date.today()-timedelta(days=1)).isoformat())
    assert expired.status_code == 201
    assert all(x["id"] != expired.json()["id"] for x in client.get("/api/circulars", headers=headers["member"]).json())


def test_draft_permissions_delete_and_audit(master_api):
    client, headers, factory = master_api
    draft = publish(client, headers["talco_staff"], status="draft")
    assert draft.status_code == 201
    circular_id = draft.json()["id"]
    assert client.get("/api/circulars", headers=headers["member"]).json() == []
    assert client.delete(f"/api/circulars/{circular_id}", headers=headers["talco_staff"]).status_code == 403
    assert client.delete(f"/api/circulars/{circular_id}", headers=headers["talco_admin"]).status_code == 204
    with factory() as session:
        assert session.get(Circular, circular_id) is None
        actions = list(session.scalars(select(AuditLog.action).where(AuditLog.entity_type == "circular")))
        assert actions == ["draft", "delete"]


def test_invalid_recipients_and_attachments_are_rejected(master_api):
    client, headers, _ = master_api
    assert publish(client, headers["talco_admin"], audience="selected", recipient_ids="[]").status_code == 422
    assert publish(client, headers["member"]).status_code == 403
    bad = client.post("/api/circulars", headers=headers["talco_admin"],
        data={"title":"Unsafe file", "content":"Message", "audience":"all", "recipient_ids":"[]"},
        files={"attachment":("script.html", b"<script>", "text/html")})
    assert bad.status_code == 422


def test_as_utc_keeps_a_non_utc_offset_instead_of_relabelling_it():
    """The production bug this pins.

    published_at is DateTime(timezone=True). PostgreSQL returns it aware, in the
    container's zone (Asia/Kolkata), while SQLite returns it naive - which is why
    no test caught this. The old code called .replace(tzinfo=utc) on the aware
    value, relabelling 07:35+05:30 as 07:35 UTC and pushing it 5.5 hours into the
    future. For those 5.5 hours a circular appeared on the notice board, because
    the list query compares in SQL, but its attachment 404'd, because visibility
    is checked in Python.
    """
    from datetime import datetime, timedelta, timezone

    from app.security import as_utc

    india = timezone(timedelta(hours=5, minutes=30))
    published = datetime(2026, 9, 21, 7, 35, tzinfo=india)
    assert as_utc(published) == datetime(2026, 9, 21, 2, 5, tzinfo=timezone.utc)
    assert as_utc(published) < datetime.now(timezone.utc)

    # A naive value is still read as UTC, which is what SQLite hands back.
    assert as_utc(datetime(2026, 9, 21, 2, 5)) == datetime(2026, 9, 21, 2, 5, tzinfo=timezone.utc)
    assert as_utc(None) is None


def test_a_published_circular_serves_its_attachment_immediately(master_api):
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.models import Circular
    from app.models.auth import User

    client, headers, factory = master_api
    with factory() as session:
        admin = session.scalar(select(User).where(User.email == "talco_admin@test.local"))
        row = Circular(title="Pump B shutdown", content="Maintenance on Sunday",
                       audience="all", status="published", created_by=admin.id,
                       attachment_name="notice.pdf", attachment_mime="application/pdf",
                       attachment_data=b"%PDF-fake",
                       published_at=datetime.now(timezone.utc))
        session.add(row); session.commit()
        circular_id = row.id
    fetched = client.get(f"/api/circulars/{circular_id}/attachment", headers=headers["member"])
    assert fetched.status_code == 200, fetched.text
    assert fetched.content == b"%PDF-fake"
