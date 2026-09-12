from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import DeliveryLog, Notification, PushSubscription
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
def list_notifications(user: User = Depends(current_user), session: Session = Depends(get_db)):
    rows = session.scalars(select(Notification).where(Notification.user_id == user.id)
                           .order_by(Notification.created_at.desc()).limit(100)).all()
    return {"unread": sum(row.read_at is None for row in rows), "items": [serialize(row) for row in rows]}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(current_user), session: Session = Depends(get_db)):
    row = session.scalar(select(Notification).where(Notification.id == notification_id,
                                                     Notification.user_id == user.id))
    if not row:
        raise HTTPException(404, "Notification not found")
    row.read_at = row.read_at or datetime.now(timezone.utc)
    session.commit()
    return {"status": "read"}


@router.post("/read-all")
def read_all(user: User = Depends(current_user), session: Session = Depends(get_db)):
    session.query(Notification).filter(Notification.user_id == user.id,
        Notification.read_at.is_(None)).update({"read_at": datetime.now(timezone.utc)})
    session.commit()
    return {"status": "read"}


@router.get("/push-key")
def push_key(_: User = Depends(current_user)):
    key = get_settings().vapid_public_key
    return {"public_key": key, "configured": bool(key and get_settings().vapid_private_key)}


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


@router.get("/delivery-log")
def delivery_log(_: User = Depends(require_roles("talco_admin")), session: Session = Depends(get_db)):
    rows = session.execute(select(DeliveryLog, User.email).outerjoin(User, User.id == DeliveryLog.user_id)
                           .order_by(DeliveryLog.attempted_at.desc()).limit(250)).all()
    return [{"id": row.id, "email": email, "channel": row.channel, "status": row.status,
             "detail": row.detail, "attempted_at": row.attempted_at.isoformat() if row.attempted_at else None}
            for row, email in rows]
