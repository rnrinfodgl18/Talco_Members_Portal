import json
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.importer.normalize import nkey
from app.models import AuditLog, Invoice, Party, PartyAlias, Receipt, Tannery, TanneryPartyLink
from app.models.auth import User
from app.security import require_roles

router = APIRouter(prefix='/api/accounts', tags=['ledger accounts'],
                   dependencies=[Depends(require_roles('talco_admin', 'talco_staff'))])


class AccountInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str = Field(min_length=1, max_length=255)
    opening_amount: Decimal = Field(default=Decimal('0'), ge=0, max_digits=14, decimal_places=2)
    opening_side: Literal['Dr', 'Cr'] = 'Dr'
    opening_date: date | None = None
    opening_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def check_opening(self):
        if self.opening_amount != 0 and self.opening_date is None:
            raise ValueError('Opening date is required for a non-zero opening balance')
        if not nkey(self.name):
            raise ValueError('Account name must contain letters or numbers')
        return self


class AccountUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=255)
    opening_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    opening_side: Literal['Dr', 'Cr'] | None = None
    opening_date: date | None = None
    opening_note: str | None = Field(default=None, max_length=500)


class AccountCreate(AccountInput):
    tannery_id: int = Field(gt=0)
    relationship_role: Literal['owner', 'lessee'] = 'owner'
    valid_from: date


def closing_balance(session: Session, account: Party) -> Decimal:
    invoice_query = select(func.coalesce(func.sum(Invoice.gross_amount), 0)).where(
        Invoice.party_id == account.id, Invoice.is_cancelled.is_(False))
    receipt_query = select(func.coalesce(func.sum(Receipt.amount), 0)).where(
        Receipt.party_id == account.id, Receipt.is_cancelled.is_(False))
    if account.opening_date:
        invoice_query = invoice_query.where(Invoice.invoice_date >= account.opening_date)
        receipt_query = receipt_query.where(Receipt.receipt_date >= account.opening_date)
    invoices = session.scalar(invoice_query) or Decimal(0)
    receipts = session.scalar(receipt_query) or Decimal(0)
    return (account.opening_amount or Decimal(0)) + invoices - receipts


def account_details(session: Session, account: Party) -> dict:
    links = session.execute(select(TanneryPartyLink, Tannery).join(Tannery, Tannery.id == TanneryPartyLink.tannery_id)
        .where(TanneryPartyLink.party_id == account.id).order_by(TanneryPartyLink.valid_from)).all()
    amount = account.opening_amount or Decimal(0)
    closing = closing_balance(session, account)
    return {'id': account.id, 'code': f'ACC-{account.id:04d}', 'name': account.name,
        'opening_amount': str(abs(amount)), 'opening_side': 'Cr' if amount < 0 else 'Dr',
        'closing_amount': str(abs(closing)), 'closing_side': 'Cr' if closing < 0 else 'Dr',
        'opening_date': account.opening_date.isoformat() if account.opening_date else None,
        'opening_note': account.opening_note,
        'links': [{'tannery_id': tannery.id, 'tannery_name': tannery.name, 'sno': tannery.sno,
                   'role': link.role, 'valid_from': link.valid_from.isoformat(),
                   'valid_to': link.valid_to.isoformat() if link.valid_to else None} for link, tannery in links]}


def remember_name(session: Session, account: Party, name: str) -> None:
    alias = session.scalar(select(PartyAlias).where(PartyAlias.normalized_key == nkey(name)))
    if alias is not None:
        if alias.party_id != account.id or alias.excluded or alias.revoked_at is not None:
            raise HTTPException(409, 'This Tally ledger name already has a different or revoked mapping')
        return
    session.add(PartyAlias(party_id=account.id, raw_name=name, normalized_key=nkey(name), excluded=False))


def commit_account(session: Session, account: Party, actor: User, action: str, changes: dict):
    try:
        session.flush()
        session.add(AuditLog(entity_type='ledger_account', entity_id=account.id, action=action,
                             changed_by=actor.email, changes=json.dumps(changes, default=str)))
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, 'An account with this ledger name already exists') from exc


def values(data: AccountInput) -> dict:
    return {'name': data.name, 'normalized_key': nkey(data.name),
        'opening_amount': data.opening_amount * (-1 if data.opening_side == 'Cr' else 1),
        'opening_date': data.opening_date, 'opening_note': data.opening_note}


@router.get('')
def accounts(session: Session = Depends(get_db)):
    return [account_details(session, account) for account in session.scalars(select(Party).order_by(Party.name))]


@router.post('', status_code=201)
def create_account(data: AccountCreate, session: Session = Depends(get_db),
                   actor: User = Depends(require_roles('talco_admin'))):
    if session.get(Tannery, data.tannery_id) is None:
        raise HTTPException(422, 'Choose an existing tannery')
    account = Party(**values(data))
    session.add(account)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, 'An account with this ledger name already exists') from exc
    remember_name(session, account, account.name)
    session.add(TanneryPartyLink(party_id=account.id, tannery_id=data.tannery_id,
                                role=data.relationship_role, valid_from=data.valid_from))
    commit_account(session, account, actor, 'create', data.model_dump())
    return account_details(session, account)


@router.patch('/{account_id}')
def update_account(account_id: int, data: AccountUpdate, session: Session = Depends(get_db),
                   actor: User = Depends(require_roles('talco_admin'))):
    account = session.get(Party, account_id)
    if account is None:
        raise HTTPException(404, 'Ledger account not found')
    current = {'name': account.name, 'opening_amount': abs(account.opening_amount or Decimal(0)),
               'opening_side': 'Cr' if account.opening_amount < 0 else 'Dr',
               'opening_date': account.opening_date, 'opening_note': account.opening_note}
    try:
        data = AccountInput.model_validate({**current, **data.model_dump(exclude_unset=True)})
    except ValidationError as exc:
        raise HTTPException(422, 'Opening values are invalid; a non-zero balance requires an effective date') from exc
    if account.name != data.name:
        remember_name(session, account, account.name)
        remember_name(session, account, data.name)
    changes = {}
    for key, value in values(data).items():
        old = getattr(account, key)
        if old != value:
            changes[key] = {'from': old, 'to': value}
            setattr(account, key, value)
    if changes:
        commit_account(session, account, actor, 'update', changes)
    return account_details(session, account)
