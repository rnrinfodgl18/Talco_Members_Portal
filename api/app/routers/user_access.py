import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, Party
from app.models.auth import User, UserLedgerAccess
from app.security import require_roles

router = APIRouter(prefix='/api/users', tags=['user access'],
                   dependencies=[Depends(require_roles('talco_admin'))])


class LedgerGrant(BaseModel):
    party_id: int = Field(gt=0)
    relationship_role: Literal['owner', 'lessee', 'account_holder', 'staff'] = 'account_holder'


class AccessInput(BaseModel):
    accounts: list[LedgerGrant] = Field(max_length=500)


def validate_grants(session: Session, grants: list[LedgerGrant]) -> None:
    ids = [grant.party_id for grant in grants]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, 'Select each ledger account only once')
    found = set(session.scalars(select(Party.id).where(Party.id.in_(ids))))
    if found != set(ids):
        raise HTTPException(422, 'One or more selected ledger accounts do not exist')


def set_grants(session: Session, user: User, grants: list[LedgerGrant], actor: User):
    validate_grants(session, grants)
    before = {'configured': user.ledger_access_configured, 'tannery_id': user.tannery_id,
              'party_id': user.party_id, 'accounts': [{'party_id': g.party_id,
              'relationship_role': g.relationship_role} for g in user.ledger_access]}
    existing = {grant.party_id: grant for grant in user.ledger_access}
    selected = {grant.party_id for grant in grants}
    for party_id, grant in existing.items():
        if party_id not in selected:
            user.ledger_access.remove(grant)
    for grant in grants:
        if grant.party_id in existing:
            existing[grant.party_id].relationship_role = grant.relationship_role
        else:
            user.ledger_access.append(UserLedgerAccess(party_id=grant.party_id, relationship_role=grant.relationship_role))
    user.ledger_access_configured = True
    # Explicit account access replaces the old single-tannery scope, including
    # when every account is revoked. Empty selection must not restore old access.
    user.tannery_id = user.party_id = None
    session.add(AuditLog(entity_type='user_access', entity_id=user.id, action='update',
        changed_by=actor.email, changes=json.dumps({'from': before,
            'to': [grant.model_dump() for grant in grants]})))


@router.get('')
def list_users(session: Session = Depends(get_db)):
    return [{'id': user.id, 'email': user.email, 'role': user.role, 'active': user.active,
             'ledger_access_configured': user.ledger_access_configured,
             'tannery_id': user.tannery_id, 'party_id': user.party_id,
             'accounts': [{'party_id': grant.party_id, 'relationship_role': grant.relationship_role}
                          for grant in user.ledger_access]}
            for user in session.scalars(select(User).order_by(User.email))]


@router.put('/{user_id}/accounts')
def update_access(user_id: int, data: AccessInput, session: Session = Depends(get_db),
                  actor: User = Depends(require_roles('talco_admin'))):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, 'User not found')
    if user.role in {'talco_admin', 'talco_staff'}:
        raise HTTPException(422, 'Administration users already have access to all accounts')
    set_grants(session, user, data.accounts, actor)
    session.commit()
    return {'status': 'updated', 'account_count': len(data.accounts)}
