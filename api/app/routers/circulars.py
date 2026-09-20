import json
from datetime import date, datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, Circular, CircularRead, CircularRecipient
from app.models.auth import User
from app.security import current_user, require_roles
from app.services.circular_audience import AUDIENCES, PORTAL_ROLES as AUDIENCE_ROLES, resolve
from app.services.notifications import deliver_notifications, notify_users

router = APIRouter(prefix="/api/circulars", tags=["circulars"])
PORTAL_ROLES = {"member", "member_staff", "lessee"}
CATEGORIES = {"general", "meeting", "accounts", "operations", "compliance"}
PRIORITIES = {"normal", "important", "urgent"}
STATUSES = {"draft", "published"}
ALLOWED_ATTACHMENTS = {
    "application/pdf", "image/png", "image/jpeg", "image/webp",
    "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _visible(session: Session, user: User, circular_id: int) -> Circular:
    row = session.get(Circular, circular_id)
    if row is None:
        raise HTTPException(404, "Circular not found")
    if user.role in {"talco_admin", "talco_staff"}:
        return row
    now = datetime.now(timezone.utc)
    if row.status != "published" or not row.published_at or row.published_at.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(404, "Circular not found")
    if row.expires_on and row.expires_on < date.today():
        raise HTTPException(404, "Circular not found")
    # Every audience except "all" was snapshotted when the circular published.
    if row.audience != "all" and session.get(CircularRecipient, (row.id, user.id)) is None:
        raise HTTPException(404, "Circular not found")
    return row


def _summary(session: Session, row: Circular, user_id: int | None = None) -> dict:
    recipients = session.scalar(select(func.count()).select_from(CircularRecipient).where(
        CircularRecipient.circular_id == row.id)) or 0
    reads = session.scalar(select(func.count()).select_from(CircularRead).where(
        CircularRead.circular_id == row.id)) or 0
    read = bool(user_id and session.get(CircularRead, (row.id, user_id)))
    creator = session.get(User, row.created_by)
    return {
        "id": row.id, "title": row.title, "content": row.content, "category": row.category,
        "priority": row.priority, "audience": row.audience, "status": row.status,
        "audience_roles": row.audience_roles.split(",") if row.audience_roles else [],
        "expires_on": row.expires_on.isoformat() if row.expires_on else None,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": creator.display_name or creator.email if creator else "TALCO",
        "has_attachment": bool(row.attachment_data), "attachment_name": row.attachment_name,
        "recipient_count": recipients, "read_count": reads, "is_read": read,
    }


@router.get("/audience")
def audience_options(_: User = Depends(require_roles("talco_admin", "talco_staff")),
                     session: Session = Depends(get_db)):
    users = session.scalars(select(User).where(User.active.is_(True), User.role.in_(PORTAL_ROLES)).order_by(
        User.display_name, User.email)).all()
    return [{"id": user.id, "name": user.display_name or user.email, "email": user.email,
             "role": user.role} for user in users]


@router.get("/audience/preview")
def audience_preview(audience: str = "all", roles: str = "",
                     _: User = Depends(require_roles("talco_admin", "talco_staff")),
                     session: Session = Depends(get_db)):
    """How many members this audience resolves to right now, before sending."""
    if audience not in AUDIENCES:
        raise HTTPException(422, "Invalid audience")
    chosen = [value for value in (x.strip() for x in roles.split(",")) if value]
    if audience == "roles" and (not chosen or not set(chosen) <= set(AUDIENCE_ROLES)):
        return {"audience": audience, "count": 0, "names": []}
    if audience == "selected":
        return {"audience": audience, "count": 0, "names": []}
    targets = resolve(session, audience, roles=chosen)
    return {"audience": audience, "count": len(targets),
            "names": [user.display_name or user.username or user.email or f"User {user.id}"
                      for user in targets[:12]]}


@router.get("/manage")
def manage(_: User = Depends(require_roles("talco_admin", "talco_staff")),
           session: Session = Depends(get_db)):
    rows = session.scalars(select(Circular).order_by(Circular.created_at.desc(), Circular.id.desc())).all()
    return [_summary(session, row) for row in rows]




@router.get("/page")
def notice_board_page(page: int = 1, page_size: int = 10, status: str = "all",
                      user: User = Depends(current_user), session: Session = Depends(get_db)):
    page, page_size = max(1, page), min(50, max(1, page_size))
    now = datetime.now(timezone.utc)
    query = select(Circular).where(Circular.status == "published", Circular.published_at.is_not(None),
        Circular.published_at <= now, or_(Circular.expires_on.is_(None), Circular.expires_on >= date.today()))
    if user.role not in {"talco_admin", "talco_staff"}:
        selected_ids = select(CircularRecipient.circular_id).where(CircularRecipient.user_id == user.id)
        query = query.where(or_(Circular.audience == "all", Circular.id.in_(selected_ids)))
    read_ids = select(CircularRead.circular_id).where(CircularRead.user_id == user.id)
    if status == "read": query = query.where(Circular.id.in_(read_ids))
    elif status == "unread": query = query.where(Circular.id.not_in(read_ids))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(query.order_by(Circular.published_at.desc(), Circular.id.desc())
        .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_summary(session, row, user.id) for row in rows], "page": page,
        "page_size": page_size, "total": total, "pages": max(1, (total + page_size - 1) // page_size)}


@router.get("")
def notice_board(user: User = Depends(current_user), session: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    query = select(Circular).where(
        Circular.status == "published", Circular.published_at.is_not(None), Circular.published_at <= now,
        or_(Circular.expires_on.is_(None), Circular.expires_on >= date.today()))
    if user.role not in {"talco_admin", "talco_staff"}:
        selected_ids = select(CircularRecipient.circular_id).where(CircularRecipient.user_id == user.id)
        query = query.where(or_(Circular.audience == "all", Circular.id.in_(selected_ids)))
    rows = session.scalars(query.order_by(Circular.published_at.desc(), Circular.id.desc())).all()
    return [_summary(session, row, user.id) for row in rows]


@router.post("", status_code=201)
async def create_circular(
    background_tasks: BackgroundTasks, title: str = Form(...), content: str = Form(...), category: str = Form("general"),
    priority: str = Form("normal"), audience: str = Form("all"), status: str = Form("published"),
    expires_on: date | None = Form(None), recipient_ids: str = Form("[]"),
    audience_roles: str = Form(""),
    attachment: UploadFile | None = File(None),
    actor: User = Depends(require_roles("talco_admin", "talco_staff")),
    session: Session = Depends(get_db),
):
    title, content = title.strip(), content.strip()
    if not 3 <= len(title) <= 255 or not content:
        raise HTTPException(422, "Title and message are required")
    if category not in CATEGORIES or priority not in PRIORITIES or audience not in AUDIENCES or status not in STATUSES:
        raise HTTPException(422, "Invalid circular option")
    try:
        ids = [int(value) for value in json.loads(recipient_ids)]
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "Selected recipients are invalid") from exc
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Select each recipient only once")
    roles = [value for value in (x.strip() for x in audience_roles.split(",")) if value]
    if audience == "selected":
        if not ids:
            raise HTTPException(422, "Select at least one member")
        valid = set(session.scalars(select(User.id).where(User.id.in_(ids), User.active.is_(True),
                                                         User.role.in_(PORTAL_ROLES))))
        if valid != set(ids):
            raise HTTPException(422, "One or more selected recipients are invalid")
    else:
        ids = []
    if audience == "roles":
        if not roles or not set(roles) <= set(AUDIENCE_ROLES):
            raise HTTPException(422, "Choose at least one valid recipient role")
    else:
        roles = []
    # Resolve now, so the circular records who it was addressed to rather than
    # a rule that would give a different answer when read later.
    targets = resolve(session, audience, roles=roles, selected_ids=ids)
    if audience in {"roles", "outstanding"} and not targets:
        raise HTTPException(422, "No active member matches this audience right now")
    if audience != "all":
        ids = [user.id for user in targets]
    data = mime = name = None
    if attachment and attachment.filename:
        mime = attachment.content_type or "application/octet-stream"
        if mime not in ALLOWED_ATTACHMENTS:
            raise HTTPException(422, "Attachment must be PDF, image, Word, or Excel")
        data = await attachment.read()
        if not data or len(data) > 8 * 1024 * 1024:
            raise HTTPException(422, "Attachment must be between 1 byte and 8 MB")
        name = attachment.filename.replace("\\", "/").split("/")[-1][:255]
    now = datetime.now(timezone.utc)
    row = Circular(title=title, content=content, category=category, priority=priority,
        audience=audience, audience_roles=",".join(roles) or None,
        status=status, expires_on=expires_on, attachment_name=name,
        attachment_mime=mime, attachment_data=data, created_by=actor.id,
        published_at=now if status == "published" else None)
    session.add(row)
    session.flush()
    session.add_all(CircularRecipient(circular_id=row.id, user_id=user_id) for user_id in ids)
    session.add(AuditLog(entity_type="circular", entity_id=row.id, action=status,
        changed_by=actor.email, changes=json.dumps({"title": title, "audience": audience,
            "audience_roles": roles, "recipients": ids, "priority": priority,
            "expires_on": str(expires_on) if expires_on else None, "attachment": name})))
    session.commit()
    session.refresh(row)
    if status == "published":
        notification_ids = notify_users(session, targets, "circular", title, content[:300], "/?page=circulars", "circular", row.id)
        session.commit()
        background_tasks.add_task(deliver_notifications, notification_ids, session.get_bind())
    return _summary(session, row)


@router.post("/{circular_id}/read")
def mark_read(circular_id: int, user: User = Depends(current_user), session: Session = Depends(get_db)):
    _visible(session, user, circular_id)
    if session.get(CircularRead, (circular_id, user.id)) is None:
        session.add(CircularRead(circular_id=circular_id, user_id=user.id))
        session.commit()
    return {"status": "read"}


@router.post("/{circular_id}/unread")
def mark_unread(circular_id: int, user: User = Depends(current_user), session: Session = Depends(get_db)):
    _visible(session, user, circular_id)
    row = session.get(CircularRead, (circular_id, user.id))
    if row:
        session.delete(row)
        session.commit()
    return {"status": "unread"}


@router.get("/{circular_id}/attachment")
def download_attachment(circular_id: int, user: User = Depends(current_user),
                        session: Session = Depends(get_db)):
    row = _visible(session, user, circular_id)
    if not row.attachment_data:
        raise HTTPException(404, "Attachment not found")
    filename = quote(row.attachment_name or "attachment")
    return Response(row.attachment_data, media_type=row.attachment_mime or "application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"})


@router.delete("/{circular_id}", status_code=204)
def delete_circular(circular_id: int, actor: User = Depends(require_roles("talco_admin")),
                    session: Session = Depends(get_db)):
    row = session.get(Circular, circular_id)
    if row is None:
        raise HTTPException(404, "Circular not found")
    session.add(AuditLog(entity_type="circular", entity_id=row.id, action="delete",
        changed_by=actor.email, changes=json.dumps({"title": row.title, "status": row.status})))
    session.delete(row)
    session.commit()
