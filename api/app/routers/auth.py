from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.auth import AuthToken, ROLES, User
from app.security import consume_token, current_user, hash_password, issue_token, require_roles, verify_password
from app.config import get_settings
from app.services.notifications import send_email

from app.routers.user_access import LedgerGrant, set_grants, validate_grants

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str
    password: str


class InviteRequest(BaseModel):
    email: str
    role: str
    tannery_id: int | None = None
    party_id: int | None = None
    accounts: list[LedgerGrant] | None = Field(default=None, max_length=500)


class TokenPassword(BaseModel):
    token: str
    password: str

class VerifyToken(BaseModel):
    token: str


@router.post("/bootstrap")
def bootstrap(request: Credentials, session: Session = Depends(get_db)):
    if session.scalar(select(func.count()).select_from(User)):
        raise HTTPException(409, "Bootstrap is already complete")
    try:
        user = User(email=request.email.lower(), password_hash=hash_password(request.password),
                    role="talco_admin", must_set_password=False)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    session.add(user); session.commit(); session.refresh(user)
    return {"access_token": issue_token(session, user), "user": serialize_user(user)}


@router.post("/login")
def login(request: Credentials, session: Session = Depends(get_db)):
    user = session.scalar(select(User).where(User.email == request.email.lower()))
    if not user or not user.active or not verify_password(request.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if user.must_set_password:
        raise HTTPException(403, "Use your invitation link to set a password")
    return {"access_token": issue_token(session, user), "user": serialize_user(user)}


@router.post("/logout", status_code=204)
def logout(user: User = Depends(current_user), session: Session = Depends(get_db)):
    session.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.purpose == "session",
                                    AuthToken.used_at.is_(None)).update({"used_at": datetime.now(timezone.utc)})
    session.commit()


@router.get("/me")
def me(user: User = Depends(current_user)):
    return serialize_user(user)


@router.post("/invite")
def invite(request: InviteRequest, actor: User = Depends(require_roles("talco_admin")),
           session: Session = Depends(get_db)):
    if request.role not in ROLES:
        raise HTTPException(422, "Unknown role")
    if request.role in {"member", "member_staff", "lessee"} and request.accounts is None and not request.tannery_id:
        raise HTTPException(422, "Member accounts require a tannery")
    if request.role == "lessee" and request.accounts is None and not request.party_id:
        raise HTTPException(422, "Lessee accounts require a party")
    if session.scalar(select(User).where(User.email == request.email.lower())):
        raise HTTPException(409, "Email already invited")
    if request.accounts is not None:
        validate_grants(session, request.accounts)
    user = User(email=request.email.lower(), role=request.role, tannery_id=request.tannery_id,
                party_id=request.party_id, must_set_password=True)
    session.add(user); session.flush()
    if request.accounts is not None:
        set_grants(session, user, request.accounts, actor)
    session.commit(); session.refresh(user)
    return {"user": serialize_user(user), "setup_token": issue_token(session, user, "invite", 48)}


@router.post("/set-password")
def set_password(request: TokenPassword, session: Session = Depends(get_db)):
    user = consume_token(session, request.token, "invite")
    try: user.password_hash = hash_password(request.password)
    except ValueError as error: raise HTTPException(422, str(error)) from error
    user.must_set_password = False; session.commit()
    return {"access_token": issue_token(session, user), "user": serialize_user(user)}




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
    return {"status": "sent"}


@router.post("/verify-email")
def verify_email(request: VerifyToken, session: Session = Depends(get_db)):
    user = consume_token(session, request.token, "verify_email")
    user.email_verified_at = datetime.now(timezone.utc)
    session.commit()
    return {"status": "verified"}
@router.post("/reset-request")
def reset_request(email: str, session: Session = Depends(get_db)):
    user = session.scalar(select(User).where(User.email == email.lower(), User.active.is_(True)))
    return {"reset_token": issue_token(session, user, "reset", 1) if user else None}


@router.post("/reset-password")
def reset_password(request: TokenPassword, session: Session = Depends(get_db)):
    user = consume_token(session, request.token, "reset")
    try: user.password_hash = hash_password(request.password)
    except ValueError as error: raise HTTPException(422, str(error)) from error
    user.must_set_password = False; session.commit()
    return {"status": "password_reset"}


def serialize_user(user: User) -> dict:
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "phone": user.phone, "role": user.role,
            "tannery_id": user.tannery_id, "party_id": user.party_id,
            "must_set_password": user.must_set_password, "email_verified": bool(user.email_verified_at)}
