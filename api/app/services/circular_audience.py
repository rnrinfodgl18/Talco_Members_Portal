"""Resolve who a circular is for.

"all" is evaluated at read time from the audience column. Every other audience
is resolved once, when the circular is published, and the resulting users are
snapshotted into circular_recipient. That matters most for the dues audience:
it is a live query, and whoever owed money at send time is who the notice was
addressed to, even after they pay.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TanneryPartyLink
from app.models.auth import User

PORTAL_ROLES = ("member", "member_staff", "lessee")
AUDIENCES = {"all", "selected", "roles", "outstanding"}


def portal_users(session: Session) -> list[User]:
    return list(session.scalars(select(User).where(
        User.active.is_(True), User.role.in_(PORTAL_ROLES))))


def parties_in_arrears(session: Session) -> set[int]:
    """Ledger accounts with money outstanding, by the report's own definition."""
    from app.routers.reports import outstanding_rows

    return {row["party_id"] for row in outstanding_rows(session)
            if Decimal(row["outstanding"]) > 0}


def parties_for(session: Session, user: User) -> set[int]:
    """Ledger accounts this portal user can see."""
    if getattr(user, "ledger_access_configured", False):
        return {grant.party_id for grant in user.ledger_access}
    if user.role == "lessee":
        return {user.party_id} if user.party_id else set()
    if user.tannery_id:
        return set(session.scalars(select(TanneryPartyLink.party_id).where(
            TanneryPartyLink.tannery_id == user.tannery_id)))
    return set()


def resolve(session: Session, audience: str, *, roles: list[str] | None = None,
            selected_ids: list[int] | None = None) -> list[User]:
    """The users a circular with this audience is addressed to."""
    if audience == "all":
        return portal_users(session)
    if audience == "selected":
        chosen = set(selected_ids or ())
        return [user for user in portal_users(session) if user.id in chosen]
    if audience == "roles":
        wanted = set(roles or ())
        return [user for user in portal_users(session) if user.role in wanted]
    if audience == "outstanding":
        in_arrears = parties_in_arrears(session)
        if not in_arrears:
            return []
        return [user for user in portal_users(session)
                if parties_for(session, user) & in_arrears]
    raise ValueError(f"Unknown audience {audience!r}")
