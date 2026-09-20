import re

import httpx
from sqlalchemy.orm import Session

from app.models import CompanySetting, DeliveryLog
from app.models.auth import User


def normalize_phone(value: str | None) -> str:
    digits = re.sub(r"\\D", "", value or "")
    if len(digits) == 10:
        digits = "91" + digits
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("Enter a valid WhatsApp number with country code")
    return digits


def send_whatsapp(session: Session, user: User | None, message: str, *, destination: str | None = None,
                  force: bool = False, notification_id: int | None = None) -> bool:
    config = session.get(CompanySetting, 1)
    phone = normalize_phone(destination or (user.phone if user else None))
    if not config or (not config.whatsapp_enabled and not force):
        session.add(DeliveryLog(user_id=user.id if user else None, notification_id=notification_id, channel="whatsapp", destination=phone,
                                status="skipped", detail="WhatsApp delivery is disabled"))
        return False
    if not config.whatsapp_base_url or not config.whatsapp_api_key:
        session.add(DeliveryLog(user_id=user.id if user else None, notification_id=notification_id, channel="whatsapp", destination=phone,
                                status="failed", detail="WhatsApp API configuration is incomplete"))
        return False
    payload = {"message": message, "recipients": [phone], "campaignName": "TALCO Portal"}
    if config.whatsapp_device_id:
        payload["deviceId"] = config.whatsapp_device_id
    try:
        response = httpx.post(
            config.whatsapp_base_url.rstrip("/") + "/api/v1/send/text",
            headers={"Authorization": "Bearer " + config.whatsapp_api_key,
                     "Content-Type": "application/json"},
            json=payload, timeout=20,
        )
        response.raise_for_status()
        body = response.json()
        ok = bool(body.get("success", True))
        detail = "messageId=" + str(body.get("messageId", "accepted")) if ok else str(body)[:500]
        session.add(DeliveryLog(user_id=user.id if user else None, notification_id=notification_id, channel="whatsapp", destination=phone,
                                status="sent" if ok else "failed", detail=detail))
        return ok
    except (httpx.HTTPError, ValueError) as exc:
        session.add(DeliveryLog(user_id=user.id if user else None, notification_id=notification_id, channel="whatsapp", destination=phone,
                                status="failed", detail=str(exc)[:1000]))
        return False

