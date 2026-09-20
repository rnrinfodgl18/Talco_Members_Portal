import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.auth import AuthToken, ROLES, User
from app.routers.user_access import LedgerGrant, set_grants, validate_grants
from app.security import (SESSION_HOURS, consume_token, current_user, hash_password, issue_token,
                          require_roles, token_user, verify_password)
from app.services.notifications import send_email
from app.services.whatsapp import normalize_phone, send_whatsapp

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    identifier: str | None = None
    email: str | None = None
    password: str


class InviteRequest(BaseModel):
    """Create one portal account.

    Email is optional by design: the admin issues a username, and many tannery
    owners have no reliable email address. Supply a password to create the
    account ready to use and hand the credentials over in person; omit it and
    an email invitation link is sent instead, which needs an email address.
    """
    role: str
    email: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=80)
    display_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    tannery_id: int | None = None
    party_id: int | None = None
    accounts: list[LedgerGrant] | None = Field(default=None, max_length=500)


class TokenPassword(BaseModel):
    token: str
    password: str


class VerifyToken(BaseModel):
    token: str


class PhoneCode(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


def send_invitation(session: Session, user: User) -> bool:
    session.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.purpose == "invite",
                                    AuthToken.used_at.is_(None)).update({"used_at": datetime.now(timezone.utc)})
    session.commit()
    raw = issue_token(session, user, "invite", 48)
    link = get_settings().public_url.rstrip("/") + "/?invite=" + raw
    delivered = send_email(session, user, "Set up your TALCO portal account",
        "Your TALCO portal login has been created.\n\nSet your password using this secure link:\n" + link +
        "\n\nThis one-time link expires in 48 hours.", force=True)
    session.commit()
    return delivered


@router.post("/bootstrap")
def bootstrap(request: Credentials, session: Session = Depends(get_db)):
    if session.scalar(select(func.count()).select_from(User)):
        raise HTTPException(409, "Bootstrap is already complete")
    try:
        email = (request.email or request.identifier or "").strip().lower()
        if "@" not in email: raise HTTPException(422, "A valid email is required")
        user = User(email=email, password_hash=hash_password(request.password),
                    role="talco_admin", must_set_password=False)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    session.add(user); session.commit(); session.refresh(user)
    return {"access_token": issue_token(session, user, hours=SESSION_HOURS), "user": serialize_user(user)}


@router.post("/login")
def login(request: Credentials, session: Session = Depends(get_db)):
    identifier = (request.identifier or request.email or "").strip()
    key = identifier.lower()
    user = session.scalar(select(User).where(or_(func.lower(User.email) == key, func.lower(User.username) == key)))
    if not user:
        digits = "".join(ch for ch in identifier if ch.isdigit())
        matches = [row for row in session.scalars(select(User).where(User.phone.is_not(None)))
                   if "".join(ch for ch in (row.phone or "") if ch.isdigit())[-10:] == digits[-10:]]
        user = matches[0] if len(matches) == 1 and digits else None
    if not user or not user.active or not verify_password(request.password, user.password_hash):
        raise HTTPException(401, "Invalid username, email, phone, or password")
    if user.must_set_password:
        raise HTTPException(403, "Use your invitation link to set a password")
    return {"access_token": issue_token(session, user, hours=SESSION_HOURS), "user": serialize_user(user)}


@router.post("/logout", status_code=204)
def logout(user: User = Depends(current_user), session: Session = Depends(get_db)):
    session.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.purpose == "session",
                                    AuthToken.used_at.is_(None)).update({"used_at": datetime.now(timezone.utc)})
    session.commit()


@router.get("/me")
def me(user: User = Depends(current_user)):
    return serialize_user(user)


@router.post("/keep-alive")
def keep_alive(user: User = Depends(current_user)):
    return {"status": "active", "user": serialize_user(user)}


@router.post("/invite")
def invite(request: InviteRequest, actor: User = Depends(require_roles("talco_admin")),
           session: Session = Depends(get_db)):
    if request.role not in ROLES:
        raise HTTPException(422, "Unknown role")
    if request.role in {"member", "member_staff", "lessee"} and request.accounts is None and not request.tannery_id:
        raise HTTPException(422, "Member accounts require a tannery")
    if request.role == "lessee" and request.accounts is None and not request.party_id:
        raise HTTPException(422, "Lessee accounts require a party")
    email = (request.email or "").strip().lower() or None
    username = (request.username or "").strip() or None
    if not email and not username:
        raise HTTPException(422, "A username or an email address is required")
    if not email and not request.password:
        raise HTTPException(422, "Set a password for an account with no email address")
    if email and session.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "Email already invited")
    if username and session.scalar(select(User).where(func.lower(User.username) == username.lower())):
        raise HTTPException(409, "Username is already taken")
    if request.accounts is not None:
        validate_grants(session, request.accounts)
    user = User(email=email, username=username, role=request.role,
                display_name=(request.display_name or "").strip() or None,
                phone=normalize_phone(request.phone) if request.phone else None,
                tannery_id=request.tannery_id, party_id=request.party_id,
                must_set_password=request.password is None)
    if request.password:
        user.password_hash = hash_password(request.password)
    session.add(user); session.flush()
    if request.accounts is not None:
        set_grants(session, user, request.accounts, actor)
    session.commit(); session.refresh(user)
    if request.password:
        # Credentials are handed over in person; show them once, never store them.
        return {"user": serialize_user(user), "email_delivery": "not_required",
                "credentials": {"identifier": username or email, "password": request.password}}
    delivered = send_invitation(session, user)
    return {"user": serialize_user(user), "email_delivery": "sent" if delivered else "failed"}


@router.post("/invite/{user_id}/resend")
def resend_invite(user_id: int, _: User = Depends(require_roles("talco_admin")),
                  session: Session = Depends(get_db)):
    user = session.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(404, "User not found")
    if not user.must_set_password:
        raise HTTPException(409, "This user has already set a password")
    delivered = send_invitation(session, user)
    if not delivered:
        raise HTTPException(502, "Invitation email could not be sent. Check the delivery log and SMTP settings.")
    return {"status": "sent"}


@router.get("/action")
def action_details(token: str, session: Session = Depends(get_db)):
    auth_token, user = token_user(session, token, {"invite", "reset"})
    return {"email": user.email, "purpose": auth_token.purpose,
            "expires_at": auth_token.expires_at.isoformat()}


@router.post("/set-password")
def set_password(request: TokenPassword, session: Session = Depends(get_db)):
    user = consume_token(session, request.token, "invite")
    try:
        user.password_hash = hash_password(request.password)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    user.must_set_password = False
    user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
    session.commit()
    return {"access_token": issue_token(session, user, hours=SESSION_HOURS), "user": serialize_user(user)}


@router.post("/verification-email")
def verification_email(user: User = Depends(current_user), session: Session = Depends(get_db)):
    if user.email_verified_at:
        return {"status": "already_verified"}
    raw = issue_token(session, user, "verify_email", 24)
    link = get_settings().public_url.rstrip("/") + "/?verify=" + raw
    delivered = send_email(session, user, "Verify your TALCO portal email",
        "Confirm this email address for TALCO portal notifications:\n\n" + link +
        "\n\nThis link expires in 24 hours.")
    session.commit()
    return {"status": "sent" if delivered else "failed"}


@router.post("/verify-email")
def verify_email(request: VerifyToken, session: Session = Depends(get_db)):
    user = consume_token(session, request.token, "verify_email")
    user.email_verified_at = datetime.now(timezone.utc)
    session.commit()
    return {"status": "verified"}


@router.post("/phone-verification/request")
def request_phone_verification(user: User = Depends(current_user), session: Session = Depends(get_db)):
    if not user.phone:
        raise HTTPException(422, "Add your WhatsApp phone number in My profile first")
    try:
        phone = normalize_phone(user.phone)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if user.phone_verified_at:
        return {"status": "already_verified", "phone": phone}
    now = datetime.now(timezone.utc)
    latest = session.scalar(select(AuthToken).where(AuthToken.user_id == user.id,
        AuthToken.purpose == "verify_phone").order_by(AuthToken.created_at.desc()))
    if latest and latest.created_at and (now - latest.created_at.replace(tzinfo=timezone.utc)).total_seconds() < 60:
        raise HTTPException(429, "Wait one minute before requesting another code")
    session.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.purpose == "verify_phone",
                                    AuthToken.used_at.is_(None)).update({"used_at": now})
    code = f"{secrets.randbelow(1_000_000):06d}"
    raw = f"{user.id}:{code}"
    session.add(AuthToken(user_id=user.id, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                          purpose="verify_phone", expires_at=now + timedelta(minutes=10)))
    delivered = send_whatsapp(session, user,
        f"Your TALCO portal verification code is {code}. It expires in 10 minutes.",
        destination=phone)
    session.commit()
    if not delivered:
        raise HTTPException(502, "WhatsApp code could not be sent. Ask the administrator to check WhatsApp settings.")
    return {"status": "sent", "phone": phone}


@router.post("/phone-verification/confirm")
def confirm_phone_verification(request: PhoneCode, user: User = Depends(current_user),
                               session: Session = Depends(get_db)):
    raw = f"{user.id}:{request.code}"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    token = session.scalar(select(AuthToken).where(AuthToken.user_id == user.id,
        AuthToken.token_hash == digest, AuthToken.purpose == "verify_phone"))
    now = datetime.now(timezone.utc)
    if not token or token.used_at or token.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(400, "The verification code is invalid or has expired")
    token.used_at = now
    user.phone_verified_at = now
    session.commit()
    return {"status": "verified", "phone_verified": True}

@router.post("/reset-request")
def reset_request(request: ResetRequest, session: Session = Depends(get_db)):
    user = session.scalar(select(User).where(User.email == request.email.strip().lower(), User.active.is_(True)))
    if user:
        session.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.purpose == "reset",
                                        AuthToken.used_at.is_(None)).update({"used_at": datetime.now(timezone.utc)})
        session.commit()
        raw = issue_token(session, user, "reset", 1)
        link = get_settings().public_url.rstrip("/") + "/?reset=" + raw
        send_email(session, user, "Reset your TALCO portal password",
            "A password reset was requested for your TALCO portal login.\n\nSet a new password using this secure link:\n" + link +
            "\n\nThis one-time link expires in 1 hour. If you did not request this, ignore this email.", force=True)
        session.commit()
    return {"status": "accepted", "message": "If this email has an active account, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(request: TokenPassword, session: Session = Depends(get_db)):
    user = consume_token(session, request.token, "reset")
    try:
        user.password_hash = hash_password(request.password)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    user.must_set_password = False
    session.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.purpose == "session",
                                    AuthToken.used_at.is_(None)).update({"used_at": datetime.now(timezone.utc)})
    session.commit()
    return {"status": "password_reset", "access_token": issue_token(session, user, hours=SESSION_HOURS),
            "user": serialize_user(user)}


def serialize_user(user: User) -> dict:
    return {"id": user.id, "email": user.email, "username": user.username, "display_name": user.display_name, "phone": user.phone,
            "role": user.role, "tannery_id": user.tannery_id, "party_id": user.party_id,
            "must_set_password": user.must_set_password, "email_verified": bool(user.email_verified_at),
            "phone_verified": bool(user.phone_verified_at)}
