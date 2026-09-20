from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import CircularRead, DeliveryLog, Notification, PushSubscription
from app.models.auth import User
from app.security import current_user, require_roles

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=1000)
    auth: str = Field(min_length=5, max_length=500)


class SubscriptionInput(BaseModel):
    endpoint: str = Field(min_length=20, max_length=5000)
    keys: PushKeys


def serialize(row: Notification) -> dict:
    return {"id": row.id, "kind": row.kind, "title": row.title, "message": row.message,
            "link": row.link, "read_at": row.read_at.isoformat() if row.read_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None}


@router.get("")
def list_notifications(page: int = 1, page_size: int = 10, status: str = "all",
                       user: User = Depends(current_user), session: Session = Depends(get_db)):
    page, page_size = max(1, page), min(50, max(1, page_size))
    base = select(Notification).where(Notification.user_id == user.id)
    if status == "read": base = base.where(Notification.read_at.is_not(None))
    elif status == "unread": base = base.where(Notification.read_at.is_(None))
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    unread = session.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None))) or 0
    rows = session.scalars(base.order_by(Notification.created_at.desc())
                           .offset((page - 1) * page_size).limit(page_size)).all()
    return {"unread": unread, "items": [serialize(row) for row in rows], "page": page,
            "page_size": page_size, "total": total, "pages": max(1, (total + page_size - 1) // page_size)}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(current_user), session: Session = Depends(get_db)):
    row = session.scalar(select(Notification).where(Notification.id == notification_id,
                                                     Notification.user_id == user.id))
    if not row:
        raise HTTPException(404, "Notification not found")
    row.read_at = row.read_at or datetime.now(timezone.utc)
    session.commit()
    return {"status": "read"}


@router.post("/{notification_id}/unread")
def mark_unread(notification_id: int, user: User = Depends(current_user), session: Session = Depends(get_db)):
    row = session.scalar(select(Notification).where(Notification.id == notification_id,
                                                     Notification.user_id == user.id))
    if not row: raise HTTPException(404, "Notification not found")
    row.read_at = None
    session.commit()
    return {"status": "unread"}


@router.post("/read-all")
def read_all(user: User = Depends(current_user), session: Session = Depends(get_db)):
    session.query(Notification).filter(Notification.user_id == user.id,
        Notification.read_at.is_(None)).update({"read_at": datetime.now(timezone.utc)})
    session.commit()
    return {"status": "read"}


@router.get("/push-key")
def push_key(user: User = Depends(current_user), session: Session = Depends(get_db)):
    settings = get_settings()
    configured = bool(settings.vapid_public_key and settings.vapid_private_key)
    devices = session.scalar(select(func.count()).select_from(PushSubscription).where(
        PushSubscription.user_id == user.id)) or 0
    return {"public_key": settings.vapid_public_key, "configured": configured,
            "devices": devices,
            "reason": None if configured else
                      "The server has no VAPID keys, so push cannot be delivered to any device."}


@router.post("/subscriptions")
def subscribe(data: SubscriptionInput, request: Request, user: User = Depends(current_user),
              session: Session = Depends(get_db)):
    row = session.scalar(select(PushSubscription).where(PushSubscription.endpoint == data.endpoint))
    if row:
        row.user_id, row.p256dh, row.auth = user.id, data.keys.p256dh, data.keys.auth
    else:
        row = PushSubscription(user_id=user.id, endpoint=data.endpoint, p256dh=data.keys.p256dh,
            auth=data.keys.auth, user_agent=request.headers.get("user-agent", "")[:500])
        session.add(row)
    session.commit()
    return {"status": "subscribed"}


@router.delete("/subscriptions")
def unsubscribe(endpoint: str, user: User = Depends(current_user), session: Session = Depends(get_db)):
    row = session.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint,
                                                         PushSubscription.user_id == user.id))
    if row:
        session.delete(row)
        session.commit()
    return {"status": "unsubscribed"}


def _recipient_name(user: User | None) -> str:
    if user is None:
        return "—"
    return user.display_name or user.username or user.email or f"User {user.id}"


@router.get("/delivery-log")
def delivery_log(channel: str | None = None, status: str | None = None, kind: str | None = None,
                 search: str | None = None, page: int = 1, page_size: int = 50,
                 _: User = Depends(require_roles("talco_admin")),
                 session: Session = Depends(get_db)):
    """Every delivery attempt, filterable. One row per recipient per channel."""
    query = (select(DeliveryLog, User, Notification)
             .outerjoin(User, User.id == DeliveryLog.user_id)
             .outerjoin(Notification, Notification.id == DeliveryLog.notification_id))
    if channel:
        query = query.where(DeliveryLog.channel == channel)
    if status:
        query = query.where(DeliveryLog.status == status)
    if kind:
        query = query.where(Notification.kind == kind)
    if search:
        term = f"%{search.strip().lower()}%"
        query = query.where(or_(
            func.lower(func.coalesce(User.display_name, "")).like(term),
            func.lower(func.coalesce(User.username, "")).like(term),
            func.lower(func.coalesce(User.email, "")).like(term),
            func.coalesce(DeliveryLog.destination, "").like(term),
            func.lower(func.coalesce(Notification.title, "")).like(term)))

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = max(1, page)
    page_size = min(max(page_size, 1), 200)
    rows = session.execute(query.order_by(DeliveryLog.attempted_at.desc(), DeliveryLog.id.desc())
                           .offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "items": [{
            "id": log.id, "recipient": _recipient_name(user),
            "email": user.email if user else None,
            "destination": log.destination, "channel": log.channel, "status": log.status,
            "detail": log.detail,
            "attempted_at": log.attempted_at.isoformat() if log.attempted_at else None,
            "notification_id": log.notification_id,
            "kind": notification.kind if notification else None,
            "subject": notification.title if notification else None,
            "entity_type": notification.entity_type if notification else None,
            "entity_id": notification.entity_id if notification else None,
        } for log, user, notification in rows],
    }


@router.get("/delivery-log/filters")
def delivery_log_filters(_: User = Depends(require_roles("talco_admin")),
                         session: Session = Depends(get_db)):
    """The values actually present, so the filter menus never offer a dead option."""
    return {
        "channels": sorted(x for x in session.scalars(select(DeliveryLog.channel).distinct()) if x),
        "statuses": sorted(x for x in session.scalars(select(DeliveryLog.status).distinct()) if x),
        "kinds": sorted(x for x in session.scalars(select(Notification.kind).distinct()) if x),
    }


@router.get("/deliveries/{entity_type}/{entity_id}")
def delivery_detail(entity_type: str, entity_id: int,
                    _: User = Depends(require_roles("talco_admin")),
                    session: Session = Depends(get_db)):
    """Who a circular or bill went to, how each channel fared, and who has read it."""
    if entity_type not in {"circular", "invoice"}:
        raise HTTPException(404, "Unknown item type")
    notifications = session.execute(
        select(Notification, User).outerjoin(User, User.id == Notification.user_id)
        .where(Notification.entity_type == entity_type, Notification.entity_id == entity_id)).all()
    if not notifications:
        return {"entity_type": entity_type, "entity_id": entity_id, "subject": None,
                "recipients": [], "totals": {}}

    logs = {}
    for log in session.scalars(select(DeliveryLog).where(DeliveryLog.notification_id.in_(
            [row.id for row, _ in notifications]))):
        logs.setdefault(log.notification_id, []).append(log)

    read_users = set()
    if entity_type == "circular":
        read_users = set(session.scalars(select(CircularRead.user_id).where(
            CircularRead.circular_id == entity_id)))

    recipients = []
    for notification, user in notifications:
        attempts = sorted(logs.get(notification.id, []),
                          key=lambda x: (x.attempted_at is None, x.attempted_at))
        channels = {}
        for attempt in attempts:
            channels[attempt.channel] = {
                "status": attempt.status, "detail": attempt.detail,
                "destination": attempt.destination,
                "attempted_at": attempt.attempted_at.isoformat() if attempt.attempted_at else None}
        recipients.append({
            "user_id": notification.user_id, "recipient": _recipient_name(user),
            "email": user.email if user else None, "phone": user.phone if user else None,
            "channels": channels,
            "read": (notification.user_id in read_users) if entity_type == "circular"
                    else notification.read_at is not None,
            "read_at": notification.read_at.isoformat() if notification.read_at else None,
        })
    recipients.sort(key=lambda row: row["recipient"].lower())

    def channel_count(name, state):
        return sum(1 for row in recipients if row["channels"].get(name, {}).get("status") == state)

    return {
        "entity_type": entity_type, "entity_id": entity_id,
        "subject": notifications[0][0].title,
        "recipients": recipients,
        "totals": {
            "recipients": len(recipients),
            "read": sum(1 for row in recipients if row["read"]),
            "unread": sum(1 for row in recipients if not row["read"]),
            "email_sent": channel_count("email", "sent"),
            "email_failed": channel_count("email", "failed"),
            "whatsapp_sent": channel_count("whatsapp", "sent"),
            "whatsapp_failed": channel_count("whatsapp", "failed"),
            "push_sent": channel_count("push", "sent"),
        },
    }
