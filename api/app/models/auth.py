from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


ROLES = {"talco_admin", "talco_staff", "member", "member_staff", "lessee"}


class User(Base):
    __tablename__ = "app_user"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    tannery_id: Mapped[int | None] = mapped_column(ForeignKey("tannery.id"))
    party_id: Mapped[int | None] = mapped_column(ForeignKey("party.id"))
    must_set_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ledger_access_configured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    ledger_access: Mapped[list["UserLedgerAccess"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthToken(Base):
    __tablename__ = "auth_token"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserLedgerAccess(Base):
    __tablename__ = "user_ledger_access"
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id", ondelete="RESTRICT"), primary_key=True)
    relationship_role: Mapped[str] = mapped_column(String(20), nullable=False)
