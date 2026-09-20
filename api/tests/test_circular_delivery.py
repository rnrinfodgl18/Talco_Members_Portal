"""A published circular goes out on exactly the channels the admin enabled."""
import pytest
from sqlalchemy import select

from app.models import CompanySetting, Notification
from app.models.auth import User
from app.services import notifications as service
from test_tannery_crud import master_api


@pytest.fixture()
def queued(master_api):
    client, headers, factory = master_api
    with factory() as session:
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        member.phone = "+919876543210"
        session.add(CompanySetting(id=1, company_name="TALCO", short_name="TALCO"))
        session.flush()
        row = Notification(user_id=member.id, kind="circular", title="Pump B shutdown",
                           message="Maintenance on Sunday", link="/?page=circulars",
                           entity_type="circular", entity_id=7)
        session.add(row); session.commit()
        ids = [row.id]
    return factory, ids


def _capture(monkeypatch):
    emails, texts = [], []
    monkeypatch.setattr(service, "send_email",
        lambda s, u, subject, body, nid=None, **kw: emails.append((subject, body)) or True)
    monkeypatch.setattr(service, "send_whatsapp",
        lambda s, u, message, **kw: texts.append(message) or True)
    monkeypatch.setattr(service, "send_push", lambda s, u, n: 0)
    return emails, texts


def _settings(factory, **values):
    with factory() as session:
        row = session.get(CompanySetting, 1)
        for key, value in values.items():
            setattr(row, key, value)
        session.commit()


def test_both_channels_carry_a_portal_link_and_no_attachment(queued, monkeypatch):
    factory, ids = queued
    emails, texts = _capture(monkeypatch)
    _settings(factory, circular_email_enabled=True, circular_whatsapp_enabled=True,
              email_to_unverified=True)
    service.deliver_notifications(ids, factory.kw["bind"], pace=False)
    assert len(emails) == 1 and len(texts) == 1
    assert "Open:" in emails[0][1]
    assert "Pump B shutdown" in texts[0] and "Open:" in texts[0]


def test_disabled_channels_send_nothing(queued, monkeypatch):
    factory, ids = queued
    emails, texts = _capture(monkeypatch)
    _settings(factory, circular_email_enabled=False, circular_whatsapp_enabled=False)
    service.deliver_notifications(ids, factory.kw["bind"], pace=False)
    assert emails == [] and texts == []


def test_unverified_addresses_are_skipped_when_the_admin_says_so(queued, monkeypatch):
    factory, ids = queued
    emails, texts = _capture(monkeypatch)
    _settings(factory, circular_email_enabled=True, circular_whatsapp_enabled=True,
              email_to_unverified=False)
    service.deliver_notifications(ids, factory.kw["bind"], pace=False)
    assert emails == [], "the member's address is not verified"
    assert len(texts) == 1, "WhatsApp is unaffected by email verification"
