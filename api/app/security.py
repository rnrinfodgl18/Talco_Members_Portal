import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.auth import AuthToken, User

bearer = HTTPBearer(auto_error=False)
SESSION_HOURS = 24 * 365


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        _, rounds, salt, expected = encoded.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_token(session: Session, user: User, purpose: str = "session", hours: int = 8) -> str:
    raw = secrets.token_urlsafe(32)
    session.add(AuthToken(user_id=user.id, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                          purpose=purpose, expires_at=datetime.now(timezone.utc) + timedelta(hours=hours)))
    session.commit()
    return raw


def token_user(session: Session, raw: str, purposes: set[str]) -> tuple[AuthToken, User]:
    digest = hashlib.sha256(raw.encode()).hexdigest()
    token = session.scalar(select(AuthToken).where(AuthToken.token_hash == digest,
                                                    AuthToken.purpose.in_(purposes)))
    now = datetime.now(timezone.utc)
    if not token or token.used_at or token.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(400, "This link is invalid or has expired")
    user = session.get(User, token.user_id)
    if not user or not user.active:
        raise HTTPException(400, "This account is no longer active")
    return token, user


def consume_token(session: Session, raw: str, purpose: str) -> User:
    token, user = token_user(session, raw, {purpose})
    token.used_at = datetime.now(timezone.utc)
    session.commit()
    return user


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                 session: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(401, "Authentication required")
    digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    token = session.scalar(select(AuthToken).where(AuthToken.token_hash == digest, AuthToken.purpose == "session"))
    now = datetime.now(timezone.utc)
    if not token or token.used_at or token.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(401, "Session is invalid or expired")
    user = session.get(User, token.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Account is inactive")
    if user.must_set_password:
        raise HTTPException(403, "Password setup required")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Insufficient permission")
        return user
    return dependency
