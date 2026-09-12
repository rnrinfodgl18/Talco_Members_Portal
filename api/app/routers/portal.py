from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Numeric, cast, func, literal, select, union_all
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.auth import User
from app.models.entities import ChargeHead, Invoice, InvoiceRevision, Party, Receipt, Tannery, TanneryPartyLink
from app.security import current_user
from app.services.scope import scoped_query, user_scope

router = APIRouter(prefix='/api/portal', tags=['portal'])


def money(value: Decimal | None) -> str:
    return str(value or Decimal('0.00'))


def available_accounts(session: Session, user: User) -> list[Party]:
    if user.role in {'talco_admin', 'talco_staff'}:
        query = select(Party)
    elif user.ledger_access_configured:
        query = select(Party).where(Party.id.in_([grant.party_id for grant in user.ledger_access]))
    else:
        ids = set()
        for model in (Invoice, Receipt, TanneryPartyLink):
            ids.update(session.scalars(scoped_query(select(model.party_id), model, user)))
        query = select(Party).where(Party.id.in_(ids))
    return list(session.scalars(query.order_by(Party.name)))


@router.get('/accounts')
def portal_accounts(user: User = Depends(current_user), session: Session = Depends(get_db)):
    scope = user_scope(user)
    grants = {grant.party_id: grant.relationship_role for grant in user.ledger_access}
    result = []
    for account in available_accounts(session, user):
        links = session.execute(scoped_query(select(TanneryPartyLink, Tannery.name).join(
            Tannery, Tannery.id == TanneryPartyLink.tannery_id).where(TanneryPartyLink.party_id == account.id),
            TanneryPartyLink, user)).all()
        result.append({'id': account.id, 'code': f'ACC-{account.id:04d}', 'name': account.name,
            'relationship_role': grants.get(account.id),
            'tanneries': [{'name': name, 'role': link.role} for link, name in links]})
    return result


def selected_account(session: Session, user: User, party_id: int | None, tannery_id: int | None):
    user_scope(user, tannery_id, party_id)
    accounts = available_accounts(session, user)
    if party_id is None:
        if len(accounts) != 1:
            raise HTTPException(422, 'Choose a ledger account')
        party_id = accounts[0].id
    account = next((account for account in accounts if account.id == party_id), None)
    if account is None:
        raise HTTPException(403, 'Ledger account is outside your account access')
    return account


def opening_context(session: Session, user: User, account: Party, tannery_id: int | None):
    scope = user_scope(user, tannery_id, account.id)
    # An opening belongs to the whole ledger. A legacy premises-only login must
    # never receive amounts belonging to another premises under the same party.
    if scope.tannery_id is not None:
        for model in (Invoice, Receipt, TanneryPartyLink):
            outside = session.scalar(select(model.id).where(model.party_id == account.id,
                model.tannery_id != scope.tannery_id).limit(1))
            if outside is not None:
                return Decimal(0), None, 'This is a premises-only view. Ask the admin for full ledger access to include its opening balance.'
    return account.opening_amount or Decimal(0), account.opening_date, None


def statement_rows(session: Session, user: User, account: Party, tannery_id: int | None):
    opening, start, warning = opening_context(session, user, account, tannery_id)
    zero = cast(literal(0), Numeric(14, 2))
    invoices = scoped_query(select(Invoice.id.label('id'), literal('invoice').label('kind'),
        Invoice.invoice_date.label('entry_date'), Invoice.voucher_no.label('voucher_no'),
        Invoice.gross_amount.label('debit'), zero.label('credit'), literal(False).label('is_step'),
        literal(1).label('sort_order'), ChargeHead.name.label('description')).join(ChargeHead, ChargeHead.id == Invoice.charge_head_id), Invoice, user, tannery_id, account.id)
    receipts = scoped_query(select(Receipt.id.label('id'), literal('receipt').label('kind'),
        Receipt.receipt_date.label('entry_date'), Receipt.voucher_no.label('voucher_no'),
        zero.label('debit'), Receipt.amount.label('credit'), Receipt.is_step.label('is_step'),
        literal(2).label('sort_order'), literal('Payment received').label('description')), Receipt, user, tannery_id, account.id)
    # Legacy member scope deliberately covered all parties at a tannery. The
    # account selector further narrows it so two accounts can never be mixed.
    invoices = invoices.where(Invoice.party_id == account.id, Invoice.is_cancelled.is_(False))
    receipts = receipts.where(Receipt.party_id == account.id, Receipt.is_cancelled.is_(False))
    if start:
        invoices = invoices.where(Invoice.invoice_date >= start)
        receipts = receipts.where(Receipt.receipt_date >= start)
    sources = [invoices, receipts]
    if start:
        sources.append(select(literal(account.id).label('id'), literal('opening').label('kind'),
            literal(start).label('entry_date'), literal('Opening balance').label('voucher_no'),
            cast(literal(max(opening, Decimal(0))), Numeric(14, 2)).label('debit'),
            cast(literal(max(-opening, Decimal(0))), Numeric(14, 2)).label('credit'),
            literal(False).label('is_step'), literal(0).label('sort_order'), literal('Opening balance').label('description')))
    entries = union_all(*sources).subquery()
    order = (entries.c.entry_date, entries.c.sort_order, entries.c.id)
    running = func.sum(entries.c.debit - entries.c.credit).over(order_by=order, rows=(None, 0)).label('balance')
    rows = session.execute(select(entries, running).order_by(*order)).all()
    return [{'id': row.id, 'kind': row.kind, 'date': row.entry_date.isoformat(), 'voucher_no': row.voucher_no,
             'debit': money(row.debit), 'credit': money(row.credit), 'balance': money(row.balance),
             'is_step': row.is_step, 'description': row.description} for row in rows], opening, start, warning


@router.get('/dashboard')
def dashboard(tannery_id: int | None = None, party_id: int | None = None,
              user: User = Depends(current_user), session: Session = Depends(get_db)):
    account = selected_account(session, user, party_id, tannery_id)
    rows, opening, start, warning = statement_rows(session, user, account, tannery_id)
    last = next((row for row in reversed(rows) if row['kind'] == 'invoice'), None)
    return {'party': {'id': account.id, 'code': f'ACC-{account.id:04d}', 'name': account.name},
            'outstanding': rows[-1]['balance'] if rows else '0.00', 'opening_balance': money(opening),
            'opening_date': start.isoformat() if start else None, 'scope_note': warning,
            'last_bill': None if last is None else {'id':last['id'], 'voucher_no':last['voucher_no'],
                'date':last['date'], 'amount':last['debit']}}


@router.get('/ledger')
def ledger(tannery_id: int | None = None, party_id: int | None = None,
           user: User = Depends(current_user), session: Session = Depends(get_db)):
    account = selected_account(session, user, party_id, tannery_id)
    return statement_rows(session, user, account, tannery_id)[0]


@router.get('/invoices')
def invoices(tannery_id: int | None = None, party_id: int | None = None,
             user: User = Depends(current_user), session: Session = Depends(get_db)):
    query = scoped_query(select(Invoice, ChargeHead.name).join(ChargeHead, ChargeHead.id == Invoice.charge_head_id).where(Invoice.is_cancelled.is_(False)).order_by(Invoice.invoice_date.desc()), Invoice, user, tannery_id, party_id)
    if party_id is not None:
        query = query.where(Invoice.party_id == party_id)
    return [{'id': x.id, 'voucher_no': x.voucher_no, 'date': x.invoice_date.isoformat(), 'base': money(x.base_amount),
             'cgst': money(x.cgst), 'sgst': money(x.sgst), 'gross': money(x.gross_amount), 'description': description} for x, description in session.execute(query)]


@router.get('/invoices/{invoice_id}')
def invoice_detail(invoice_id: int, user: User = Depends(current_user), session: Session = Depends(get_db)):
    existing = session.get(Invoice, invoice_id)
    if not existing: raise HTTPException(404, 'Invoice not found')
    found = session.scalar(scoped_query(select(Invoice).where(Invoice.id == invoice_id), Invoice, user))
    if not found: raise HTTPException(403, 'Invoice is outside your account scope')
    party = session.get(Party, found.party_id)
    tannery = session.get(Tannery, found.tannery_id)
    head = session.get(ChargeHead, found.charge_head_id)
    revisions = session.scalars(select(InvoiceRevision).where(
        InvoiceRevision.invoice_id == found.id).order_by(InvoiceRevision.revised_at.desc())).all()
    return {'id': found.id, 'voucher_no': found.voucher_no, 'fy': found.fy,
            'date': found.invoice_date.isoformat(), 'account': party.name if party else '',
            'account_code': f'ACC-{party.id:04d}' if party else '', 'tannery': tannery.name if tannery else '',
            'tannery_gstin': tannery.gstin if tannery else None, 'charge_head': head.name if head else '',
            'base': money(found.base_amount), 'cgst': money(found.cgst), 'sgst': money(found.sgst),
            'gross': money(found.gross_amount), 'revision_count': len(revisions),
            'revisions': [{'date': row.revised_at.isoformat(), 'reason': row.reason,
                           'revised_by': row.revised_by} for row in revisions]}


@router.get('/receipts')
def receipts(tannery_id: int | None = None, party_id: int | None = None,
             user: User = Depends(current_user), session: Session = Depends(get_db)):
    query = scoped_query(select(Receipt).where(Receipt.is_cancelled.is_(False)).order_by(Receipt.receipt_date.desc()), Receipt, user, tannery_id, party_id)
    if party_id is not None:
        query = query.where(Receipt.party_id == party_id)
    return [{'id': x.id, 'voucher_no': x.voucher_no, 'date': x.receipt_date.isoformat(),
             'amount': money(x.amount), 'is_step': x.is_step} for x in session.scalars(query)]
