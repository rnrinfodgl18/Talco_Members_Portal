from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, func
from app.models import AuditLog, ChargeHead, Invoice, Party, Receipt, TanneryPartyLink
from app.models.auth import User
from test_tannery_crud import master_api


@pytest.fixture()
def ledgers(master_api):
    client, headers, factory = master_api
    admin = headers['talco_admin']
    account_rows=[]
    for index, name in enumerate(['Owner One', 'Lease Two', 'Private Three']):
        tannery=client.post('/api/tanneries',headers=admin,json={'name':f'Factory {index}', 'pump_house':'A'}).json()
        response=client.post('/api/accounts',headers=admin,json={'name':name,'tannery_id':tannery['id'],
            'relationship_role':'owner' if index==0 else 'lessee','valid_from':'2026-01-01',
            'opening_amount':'1000.00' if index==0 else '50.00','opening_side':'Dr' if index==0 else 'Cr',
            'opening_date':'2026-08-01','opening_note':'Opening from prior statement'})
        assert response.status_code==201,response.text
        account_rows.append((response.json(),tannery))
    with factory() as s:
        head=ChargeHead(code='TREAT',name='Treatment',gst_rate=5);s.add(head);s.flush()
        for index,(account,tannery) in enumerate(account_rows):
            s.add(Invoice(party_id=account['id'],tannery_id=tannery['id'],charge_head_id=head.id,
                voucher_no=f'B{index}',fy='2026-2027',invoice_date=date(2026,8,1),base_amount=100,cgst=2.5,sgst=2.5,gross_amount=105))
        account,tannery=account_rows[0]
        s.add(Invoice(party_id=account['id'],tannery_id=tannery['id'],charge_head_id=head.id,voucher_no='OLD',
            fy='2026-2027',invoice_date=date(2026,7,1),base_amount=500,cgst=0,sgst=0,gross_amount=500))
        s.add_all([Receipt(party_id=account['id'],tannery_id=tannery['id'],voucher_no='R1',fy='2026-2027',receipt_date=date(2026,8,2),amount=40,is_step=False),
            Receipt(party_id=account['id'],tannery_id=tannery['id'],voucher_no='OLD-R',fy='2026-2027',receipt_date=date(2026,7,2),amount=100,is_step=False)])
        s.commit()
        user=s.scalar(select(User).where(User.role=='member'))
        uid=user.id
    grants=[{'party_id':account_rows[0][0]['id'],'relationship_role':'owner'},
            {'party_id':account_rows[1][0]['id'],'relationship_role':'lessee'}]
    assert client.put(f'/api/users/{uid}/accounts',headers=admin,json={'accounts':grants}).status_code==200
    return client,headers,factory,account_rows,uid


def test_single_login_multiple_accounts_separate_balances_and_boundaries(ledgers):
    client,headers,factory,rows,uid=ledgers
    auth=headers['member'];a,b,c=[r[0]['id'] for r in rows]
    options=client.get('/api/portal/accounts',headers=auth)
    assert options.status_code==200,options.text
    assert {x['id'] for x in options.json()}=={a,b}
    assert {x['relationship_role'] for x in options.json()}=={'owner','lessee'}
    statement=client.get(f'/api/portal/ledger?party_id={a}',headers=auth)
    assert statement.status_code==200,statement.text
    data=statement.json()
    assert [x['kind'] for x in data]==['opening','invoice','receipt']
    assert [Decimal(x['balance']) for x in data]==[1000,1105,1065]
    assert Decimal(client.get(f'/api/portal/dashboard?party_id={a}',headers=auth).json()['outstanding'])==1065
    assert Decimal(client.get(f'/api/portal/dashboard?party_id={b}',headers=auth).json()['outstanding'])==55
    assert len(client.get(f'/api/portal/invoices?party_id={a}',headers=auth).json())==2
    assert len(client.get(f'/api/portal/receipts?party_id={a}',headers=auth).json())==2
    assert client.get(f'/api/portal/ledger?party_id={c}',headers=auth).status_code==403
    assert client.get(f'/api/portal/dashboard?party_id={c}',headers=auth).status_code==403
    with factory() as s:
        private_id=s.scalar(select(Invoice.id).where(Invoice.party_id==c))
    assert client.get(f'/api/portal/invoices/{private_id}',headers=auth).status_code==403
    for path in ['/api/accounts','/api/users','/api/imports','/api/mappings/queue']:
        assert client.get(path,headers=auth).status_code==403
    assert client.get('/api/portal/ledger',headers=auth).status_code==422


def test_edit_opening_recalculates_without_editing_transactions(ledgers):
    client,headers,factory,rows,uid=ledgers
    account=rows[0][0];pid=account['id'];auth=headers['talco_admin']
    payload={'name':account['name'],'opening_amount':'200.00','opening_side':'Cr','opening_date':'2026-08-01','opening_note':'Corrected opening'}
    response=client.patch(f'/api/accounts/{pid}',headers=auth,json=payload)
    assert response.status_code==200,response.text
    result=client.get(f'/api/portal/ledger?party_id={pid}',headers=headers['member']).json()
    assert Decimal(result[0]['credit'])==200
    assert Decimal(result[-1]['balance'])==-135
    payload['opening_date']='2026-07-01'
    assert client.patch(f'/api/accounts/{pid}',headers=auth,json=payload).status_code==200
    result=client.get(f'/api/portal/ledger?party_id={pid}',headers=headers['member']).json()
    assert len(result)==5
    assert Decimal(result[-1]['balance'])==265
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(Invoice))==4
        assert s.scalar(select(func.count()).select_from(Receipt))==2
        updates=s.scalars(select(AuditLog).where(AuditLog.entity_type=='ledger_account',AuditLog.action=='update')).all()
        assert len(updates)==2
        assert 'opening_amount' in updates[0].changes


def test_revoke_all_access_takes_effect_with_existing_token(ledgers):
    client,headers,_,rows,uid=ledgers
    assert client.put(f'/api/users/{uid}/accounts',headers=headers['talco_admin'],json={'accounts':[]}).status_code==200
    assert client.get('/api/portal/accounts',headers=headers['member']).json()==[]
    assert client.get(f"/api/portal/ledger?party_id={rows[0][0]['id']}",headers=headers['member']).status_code==403
    assert client.get('/api/portal/invoices',headers=headers['member']).json()==[]


def test_validation_permissions_and_access_replacement(ledgers):
    client,headers,_,rows,uid=ledgers
    a=rows[0][0];pid=a['id']
    payload={'name':a['name'],'opening_amount':'10.00','opening_side':'Dr','opening_date':None}
    assert client.patch(f'/api/accounts/{pid}',headers=headers['talco_admin'],json=payload).status_code==422
    for value in ['-10','NaN','Infinity','1.001']:
        assert client.patch(f'/api/accounts/{pid}',headers=headers['talco_admin'],json={**payload,'opening_date':'2026-08-01','opening_amount':value}).status_code==422
    assert client.patch(f'/api/accounts/{pid}',headers=headers['talco_staff'],json={**payload,'opening_date':'2026-08-01'}).status_code==403
    assert client.put(f'/api/users/{uid}/accounts',headers=headers['member'],json={'accounts':[]}).status_code==403
    for grants in [[{'party_id':99999}],[{'party_id':pid},{'party_id':pid}]]:
        assert client.put(f'/api/users/{uid}/accounts',headers=headers['talco_admin'],json={'accounts':grants}).status_code==422
    assert len(client.get('/api/portal/accounts',headers=headers['member']).json())==2


def test_invite_one_login_with_owner_and_lessee_accounts(ledgers):
    client,headers,_,rows,uid=ledgers
    data={'email':'mixed@example.test','role':'member','accounts':[{'party_id':rows[0][0]['id'],'relationship_role':'owner'},
        {'party_id':rows[1][0]['id'],'relationship_role':'lessee'}]}
    invited=client.post('/api/auth/invite',headers=headers['talco_admin'],json=data)
    assert invited.status_code==200,invited.text
    setup=client.post('/api/auth/set-password',json={'token':invited.json()['setup_token'],'password':'Example-password-2026'})
    assert setup.status_code==200,setup.text
    token=setup.json()['access_token']
    result=client.get('/api/portal/accounts',headers={'Authorization':f'Bearer {token}'})
    assert len(result.json())==2
    assert client.post('/api/auth/invite',headers=headers['talco_admin'],json=data).status_code==409


def test_legacy_login_keeps_existing_scope(ledgers):
    client,headers,factory,rows,uid=ledgers
    with factory() as s:
        user=s.scalar(select(User).where(User.role=='lessee'))
        user.tannery_id=rows[0][1]['id'];user.party_id=rows[0][0]['id'];s.commit()
    response=client.get('/api/portal/accounts',headers=headers['lessee'])
    assert {x['id'] for x in response.json()}=={rows[0][0]['id']}
    assert Decimal(client.get('/api/portal/dashboard',headers=headers['lessee']).json()['outstanding'])==1065


def test_renamed_account_import_keeps_same_ledger(ledgers):
    from app.services.import_pipeline import _party_and_link
    client,headers,factory,rows,uid=ledgers
    a=rows[0][0]
    assert client.patch(f"/api/accounts/{a['id']}",headers=headers['talco_admin'],json={'name':'New Owner Name'}).status_code==200
    with factory() as s:
        from app.models import Tannery
        party=_party_and_link(s,s.get(Tannery,rows[0][1]['id']),{'party':a['name']},date(2026,8,1))
        assert party.id==a['id']
        assert party.opening_amount==Decimal('1000.00')


def test_partial_opening_update_and_no_opening(ledgers):
    client,headers,_,rows,_=ledgers
    pid=rows[0][0]['id'];admin=headers['talco_admin']
    response=client.patch(f'/api/accounts/{pid}',headers=admin,json={'opening_amount':'1200.00'})
    assert response.status_code==200,response.text
    assert response.json()['opening_date']=='2026-08-01'
    assert Decimal(client.get(f'/api/portal/dashboard?party_id={pid}',headers=headers['member']).json()['outstanding'])==1265
    assert client.patch(f'/api/accounts/{pid}',headers=admin,json={'opening_date':None}).status_code==422
    assert client.patch(f'/api/accounts/{pid}',headers=admin,json={'opening_amount':'0','opening_date':None}).status_code==200
    statement=client.get(f'/api/portal/ledger?party_id={pid}',headers=headers['member']).json()
    assert all(row['kind']!='opening' for row in statement)
    assert Decimal(statement[-1]['balance'])==465

def test_ledger_master_returns_calculated_closing_not_opening(ledgers):
    client, headers, _, rows, _ = ledgers
    listed = {row["id"]: row for row in client.get("/api/accounts", headers=headers["talco_staff"]).json()}
    owner = listed[rows[0][0]["id"]]
    lessee = listed[rows[1][0]["id"]]
    assert Decimal(owner["closing_amount"]) == Decimal("1065")
    assert owner["closing_side"] == "Dr"
    assert Decimal(lessee["closing_amount"]) == Decimal("55")
    assert lessee["closing_side"] == "Dr"
