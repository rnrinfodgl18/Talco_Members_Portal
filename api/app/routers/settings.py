import json

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, CompanySetting
from app.models.auth import User
from app.security import current_user, hash_password, require_roles, verify_password
from app.services.notifications import send_email

router = APIRouter(prefix="/api/settings", tags=["settings"])


class CompanyInput(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    short_name: str = Field(min_length=2, max_length=100)
    address: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    gstin: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)


class SmtpInput(BaseModel):
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, max_length=255)
    smtp_password: str | None = Field(default=None, max_length=500)
    smtp_from_email: str | None = Field(default=None, max_length=255)
    smtp_from_name: str | None = Field(default=None, max_length=255)
    smtp_security: str = Field(default="starttls", pattern="^(starttls|ssl|none)$")
    smtp_enabled: bool = False
    clear_password: bool = False


_THEME_DEFAULTS = {
    "theme_name": "TALCO Professional", "background_color": "#f6f8f7", "surface_color": "#ffffff",
    "font_color": "#17231e", "muted_color": "#52645d", "primary_color": "#087f5b",
    "primary_text_color": "#ffffff", "edit_color": "#9a6700", "view_color": "#075985",
    "print_color": "#087f5b", "danger_color": "#c92a2a", "border_color": "#cfd8d4"
}

class ThemeInput(BaseModel):
    theme_name: str = Field(min_length=2, max_length=80)
    background_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    surface_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    font_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    muted_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    primary_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    primary_text_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    edit_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    view_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    print_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    danger_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    border_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


def _theme(row: CompanySetting) -> dict:
    try:
        stored = json.loads(row.theme_json) if row.theme_json else {}
    except (TypeError, json.JSONDecodeError):
        stored = {}
    return _THEME_DEFAULTS | {key: value for key, value in stored.items() if key in _THEME_DEFAULTS}

class SmtpTestInput(BaseModel):
    recipient: str = Field(min_length=5, max_length=255)


class ProfileInput(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    phone: str | None = Field(default=None, max_length=30)


class PasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


def _settings(session: Session) -> CompanySetting:
    row = session.get(CompanySetting, 1)
    if row is None:
        row = CompanySetting(id=1, company_name="TALCO-DINTEC", short_name="TALCO")
        session.add(row)
        session.flush()
    return row


def _company(row: CompanySetting) -> dict:
    return {key: getattr(row, key) for key in ("company_name", "short_name", "address", "city", "state",
        "postal_code", "gstin", "phone", "email", "website")} | {"has_logo": bool(row.logo_data)}


def _smtp(row: CompanySetting) -> dict:
    return {key: getattr(row, key) for key in ("smtp_host", "smtp_port", "smtp_username",
        "smtp_from_email", "smtp_from_name", "smtp_security", "smtp_enabled")} | {
        "password_configured": bool(row.smtp_password)}


@router.get("/public")
def public_settings(session: Session = Depends(get_db)):
    row = _settings(session)
    return _company(row) | {"theme": _theme(row)}


@router.get("/logo")
def logo(session: Session = Depends(get_db)):
    row = _settings(session)
    if not row.logo_data:
        raise HTTPException(404, "Logo not configured")
    return Response(row.logo_data, media_type=row.logo_mime or "image/png",
                    headers={"Cache-Control": "public, max-age=300"})


@router.get("")
def get_settings(user: User = Depends(current_user), session: Session = Depends(get_db)):
    row = _settings(session)
    result = {"company": _company(row), "theme": _theme(row)}
    if user.role == "talco_admin":
        result["smtp"] = _smtp(row)
    return result


@router.put("/company")
def update_company(data: CompanyInput, actor: User = Depends(require_roles("talco_admin")),
                   session: Session = Depends(get_db)):
    row = _settings(session)
    before = _company(row)
    for key, value in data.model_dump().items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    after = _company(row)
    session.add(AuditLog(entity_type="company_setting", entity_id=1, action="update",
        changed_by=actor.email, changes=json.dumps({"from": before, "to": after})))
    session.commit()
    return after


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), actor: User = Depends(require_roles("talco_admin")),
                      session: Session = Depends(get_db)):
    allowed = {"image/png", "image/jpeg", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(422, "Use a PNG, JPEG, or WebP logo")
    content = await file.read()
    if not content or len(content) > 2 * 1024 * 1024:
        raise HTTPException(422, "Logo must be between 1 byte and 2 MB")
    row = _settings(session)
    row.logo_data, row.logo_mime = content, file.content_type
    session.add(AuditLog(entity_type="company_setting", entity_id=1, action="logo_update",
        changed_by=actor.email, changes=json.dumps({"file_name": file.filename, "mime": file.content_type,
                                                    "size": len(content)})))
    session.commit()
    return {"has_logo": True}


@router.delete("/logo", status_code=204)
def delete_logo(actor: User = Depends(require_roles("talco_admin")), session: Session = Depends(get_db)):
    row = _settings(session)
    row.logo_data = row.logo_mime = None
    session.add(AuditLog(entity_type="company_setting", entity_id=1, action="logo_delete",
        changed_by=actor.email, changes="{}"))
    session.commit()



@router.put("/theme")
def update_theme(data: ThemeInput, actor: User = Depends(require_roles("talco_admin")),
                 session: Session = Depends(get_db)):
    row = _settings(session)
    before = _theme(row)
    after = data.model_dump()
    row.theme_json = json.dumps(after)
    session.add(AuditLog(entity_type="theme_setting", entity_id=1, action="update",
        changed_by=actor.email, changes=json.dumps({"from": before, "to": after})))
    session.commit()
    return after
@router.put("/smtp")
def update_smtp(data: SmtpInput, actor: User = Depends(require_roles("talco_admin")),
                session: Session = Depends(get_db)):
    row = _settings(session)
    before = _smtp(row)
    values = data.model_dump(exclude={"clear_password"})
    password = values.pop("smtp_password")
    for key, value in values.items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    if data.clear_password:
        row.smtp_password = None
    elif password:
        row.smtp_password = password
    if row.smtp_enabled and (not row.smtp_host or not row.smtp_port or not row.smtp_from_email):
        raise HTTPException(422, "Host, port, and from email are required before enabling SMTP")
    after = _smtp(row)
    session.add(AuditLog(entity_type="smtp_setting", entity_id=1, action="update",
        changed_by=actor.email, changes=json.dumps({"from": before, "to": after})))
    session.commit()
    return after




@router.post("/smtp/test")
def test_smtp(data: SmtpTestInput, actor: User = Depends(require_roles("talco_admin")),
              session: Session = Depends(get_db)):
    recipient = data.recipient.strip().lower()
    if "@" not in recipient or recipient.startswith("@") or recipient.endswith("@"):
        raise HTTPException(422, "Enter a valid test email address")
    delivered = send_email(session, actor, "TALCO SMTP test successful",
        "This test email confirms that TALCO portal SMTP delivery is working.", force=True,
        destination=recipient)
    session.commit()
    if not delivered:
        raise HTTPException(502, "SMTP test failed. Check the Notification delivery log for the exact reason.")
    return {"status": "sent", "recipient": recipient}
@router.put("/profile")
def update_profile(data: ProfileInput, user: User = Depends(current_user), session: Session = Depends(get_db)):
    before = {"display_name": user.display_name, "email": user.email, "phone": user.phone}
    user.display_name = data.display_name.strip() if data.display_name else None
    if user.email != data.email.strip().lower():
        user.email_verified_at = None
    user.email = data.email.strip().lower()
    user.phone = data.phone.strip() if data.phone else None
    try:
        session.add(AuditLog(entity_type="user_profile", entity_id=user.id, action="update",
            changed_by=before["email"], changes=json.dumps({"from": before,
                "to": {"display_name": user.display_name, "email": user.email, "phone": user.phone}})))
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "This email is already used by another login") from exc
    return {"id": user.id, "display_name": user.display_name, "email": user.email,
            "phone": user.phone, "role": user.role, "email_verified": bool(user.email_verified_at)}


@router.put("/password")
def update_password(data: PasswordInput, user: User = Depends(current_user), session: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(422, "Current password is incorrect")
    try:
        user.password_hash = hash_password(data.new_password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    session.add(AuditLog(entity_type="user_profile", entity_id=user.id, action="password_update",
        changed_by=user.email, changes=json.dumps({"password_changed": True})))
    session.commit()
    return {"status": "password_updated"}
