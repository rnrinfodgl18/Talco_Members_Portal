import json
import smtplib
import ssl
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CompanySetting, DeliveryLog, Notification, PushSubscription
from app.models.auth import User


def send_email(session: Session, user: User, subject: str, body: str,
               notification_id: int | None = None, force: bool = False,
               destination: str | None = None,
               attachments: list[tuple[str, str, bytes]] | None = None) -> bool:
    """Send one email. attachments are (filename, mime_type, content) triples."""
    config = session.get(CompanySetting, 1)
    recipient = destination or user.email
    if not config or (not config.smtp_enabled and not force):
        session.add(DeliveryLog(user_id=user.id, notification_id=notification_id, channel="email",
            destination=recipient, status="skipped", detail="SMTP is disabled"))
        return False
    if not config.smtp_host or not config.smtp_port or not config.smtp_from_email:
        session.add(DeliveryLog(user_id=user.id, notification_id=notification_id, channel="email",
            destination=recipient, status="failed", detail="SMTP host, port, and from email are required"))
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{config.smtp_from_name or config.short_name} <{config.smtp_from_email}>"
    message["To"] = recipient
    message.set_content(body)
    for filename, mime_type, content in attachments or ():
        main_type, _, sub_type = mime_type.partition("/")
        message.add_attachment(content, maintype=main_type or "application",
                               subtype=sub_type or "octet-stream", filename=filename)
    try:
        if config.smtp_security == "ssl":
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15,
                                      context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
            if config.smtp_security == "starttls":
                server.starttls(context=ssl.create_default_context())
        with server:
            if config.smtp_username:
                server.login(config.smtp_username, config.smtp_password or "")
            server.send_message(message)
        session.add(DeliveryLog(user_id=user.id, notification_id=notification_id, channel="email",
            destination=recipient, status="sent"))
        return True
    except Exception as exc:
        session.add(DeliveryLog(user_id=user.id, notification_id=notification_id, channel="email",
            destination=recipient, status="failed", detail=str(exc)[:1000]))
        return False


def send_push(session: Session, user: User, notification: Notification) -> int:
    settings = get_settings()
    subscriptions = session.scalars(select(PushSubscription).where(
        PushSubscription.user_id == user.id)).all()
    if not subscriptions or not settings.vapid_private_key or not settings.vapid_public_key:
        if subscriptions:
            session.add(DeliveryLog(user_id=user.id, notification_id=notification.id, channel="push",
                status="skipped", detail="VAPID keys are not configured"))
        return 0
    from pywebpush import WebPushException, webpush
    sent = 0
    payload = json.dumps({"title": notification.title, "body": notification.message,
                          "url": notification.link or "/", "notificationId": notification.id})
    for subscription in subscriptions:
        try:
            webpush(subscription_info={"endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth}},
                data=payload, vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject})
            session.add(DeliveryLog(user_id=user.id, notification_id=notification.id,
                channel="push", destination=subscription.endpoint[:500], status="sent"))
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            session.add(DeliveryLog(user_id=user.id, notification_id=notification.id,
                channel="push", destination=subscription.endpoint[:500], status="failed",
                detail=str(exc)[:1000]))
            if status in {404, 410}:
                session.delete(subscription)
    return sent


def notify_users(session: Session, users: list[User], kind: str, title: str, message: str,
                 link: str | None = None, entity_type: str | None = None,
                 entity_id: int | None = None) -> list[int]:
    ids = []
    for user in users:
        row = Notification(user_id=user.id, kind=kind, title=title, message=message,
            link=link, entity_type=entity_type, entity_id=entity_id)
        session.add(row)
        session.flush()
        ids.append(row.id)
    return ids


def deliver_notifications(notification_ids: list[int], bind) -> None:
    from sqlalchemy.orm import Session
    with Session(bind) as session:
        for notification_id in notification_ids:
            row = session.get(Notification, notification_id)
            if not row:
                continue
            user = session.get(User, row.user_id)
            if not user or not user.active:
                continue
            send_push(session, user, row)
            if user.email_verified_at:
                send_email(session, user, row.title, row.message +
                    (f"\n\nOpen: {get_settings().public_url}" if row.link else ""), row.id)
            session.commit()
