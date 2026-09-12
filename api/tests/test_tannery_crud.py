import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateSchema, DropSchema
from app.config import get_settings

import app.main as main
from app.db import get_db
from app.models.base import Base
from app.models import AuditLog, ImportBatch, StagingRow, Tannery, Party, TanneryPartyLink, TannerySerialCounter, Pump, ChargeHead, Invoice, Receipt
from app.models.auth import User
from app.security import issue_token
from datetime import date


@pytest.fixture()
def master_api(monkeypatch):
    schema = None
    if os.environ.get('TALCO_TEST_POSTGRES') == '1':
        schema = 'test_ledger_' + uuid4().hex
        engine = create_engine(get_settings().database_url)
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = engine.execution_options(schema_translate_map={None: schema})
    else:
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        @event.listens_for(engine, 'connect')
        def foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(main, 'SessionLocal', factory)
    def database():
        with factory() as session:
            yield session
    main.app.dependency_overrides[get_db] = database
    with factory() as session:
        session.add(TannerySerialCounter(id=1, last_value=0))
        session.add_all([Pump(code=code, name=f"Pump house {code}") for code in "ABCDE"])
        session.commit()
    headers = {}
    with factory() as session:
        for role in ('talco_admin', 'talco_staff', 'member', 'member_staff', 'lessee'):
            user = User(email=f'{role}@test.local', role=role, must_set_password=False)
            session.add(user)
            session.commit()
            headers[role] = {'Authorization': 'Bearer ' + issue_token(session, user)}
    with TestClient(main.app) as client:
        yield client, headers, factory
    main.app.dependency_overrides.pop(get_db, None)
    if schema:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
    engine.dispose()


def test_complete_master_lifecycle_and_audit(master_api):
    client, headers, factory = master_api
    auth = headers['talco_admin']
    data = {'name': ' Alpha Works ', 'pump_house': 'A', 'gstin': 'SOURCE VALUE',
            'internal_id': 'I1', 'factory_id': 'F1', 'tnpcb_user_id': 'T1', 'gps': '10.1, 77.1',
            'consent': 'Consent reference', 'original_capacity': '100 KLD', 'additional_capacity': '20 KLD',
            'original_shares': 50, 'additional_shares': 10, 'phone': '9999999999', 'email': 'office@example.test'}
    response = client.post('/api/tanneries', json=data, headers=auth)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row['name'] == 'Alpha Works'
    path = f"/api/tanneries/{row['id']}"
    updated = {key: value for key, value in data.items() if key != 'sno'}
    updated.update(name='Beta Works', pump_house='B', internal_id='I2', factory_id='F2',
                   tnpcb_user_id='T2', gps='11, 78', gstin='UPDATED', consent='Renewed',
                   original_capacity='200', additional_capacity='30', original_shares=60,
                   additional_shares=0, phone=None, email=None)
    response = client.patch(path, json=updated, headers=auth)
    assert response.status_code == 200, response.text
    assert all(response.json()[key] == value for key, value in updated.items())
    assert client.get(path, headers=auth).json()['consent'] == 'Renewed'
    assert len(client.get('/api/tanneries?search=Beta&pump_house=B', headers=auth).json()) == 1
    with factory() as session:
        assert session.get(Tannery, row['id']).normalized_key == 'BETAWORKS'
    assert client.delete(path, headers=auth).status_code == 204
    assert client.get(path, headers=auth).status_code == 404
    with factory() as session:
        logs = session.scalars(select(AuditLog).order_by(AuditLog.id)).all()
        assert [log.action for log in logs] == ['create', 'update', 'delete']
        assert all(log.changed_by == 'talco_admin@test.local' for log in logs)
        assert json.loads(logs[1].changes)['name'] == {'from': 'Alpha Works', 'to': 'Beta Works'}


@pytest.mark.parametrize('role', ['talco_staff', 'member', 'member_staff', 'lessee'])
def test_master_permissions_cannot_be_spoofed(master_api, role):
    client, headers, _ = master_api
    auth = {**headers[role], 'X-TALCO-ROLE': 'talco_admin'}
    assert client.post('/api/tanneries', json={'name': 'Test', 'pump_house': 'A'}, headers=auth).status_code == 403
    assert client.patch('/api/tanneries/1', json={'name': 'Changed'}, headers=auth).status_code == 403
    assert client.delete('/api/tanneries/1', headers=auth).status_code == 403
    assert client.get('/api/tanneries', headers=auth).status_code == (200 if role == 'talco_staff' else 403)


def test_duplicates_validation_and_stable_serial(master_api):
    client, headers, _ = master_api
    auth = headers['talco_admin']
    data = {'name': 'Alpha Works', 'pump_house': 'A'}
    row = client.post('/api/tanneries', json=data, headers=auth).json()
    assert client.post('/api/tanneries', json={**data, 'sno': 1}, headers=auth).status_code == 422
    assert client.post('/api/tanneries', json={**data, 'name': 'ALPHA-WORKS'}, headers=auth).status_code == 409
    for invalid in ({'name': '   '}, {'name': '!!!'}, {'sno': 0}, {'pump_house': 'Z'}, {'original_shares': -1}):
        assert client.post('/api/tanneries', json={**data, **invalid}, headers=auth).status_code == 422
    path = f"/api/tanneries/{row['id']}"
    for invalid in ({'name': None}, {'pump_house': None}, {'sno': 12}):
        assert client.patch(path, json=invalid, headers=auth).status_code == 422
    assert client.get(path, headers=auth).json()['name'] == 'Alpha Works'


@pytest.mark.parametrize('reference', ['user', 'party', 'staging', 'invoice', 'receipt'])
def test_delete_preserves_referenced_tanneries(master_api, reference):
    client, headers, factory = master_api
    auth = headers['talco_admin']
    row = client.post('/api/tanneries', json={'name': 'Linked Works', 'pump_house': 'C'}, headers=auth).json()
    with factory() as session:
        if reference == 'user':
            session.add(User(email='linked@test.local', role='member', tannery_id=row['id']))
        elif reference == 'party':
            party = Party(name='Party', normalized_key='PARTY'); session.add(party); session.flush()
            session.add(TanneryPartyLink(tannery_id=row['id'], party_id=party.id, role='owner', valid_from=date(2026, 8, 1)))
        elif reference in ('invoice', 'receipt'):
            party = Party(name='Party', normalized_key='PARTY'); session.add(party); session.flush()
            if reference == 'invoice':
                head = ChargeHead(code='TREATMENT', name='Treatment', gst_rate=5)
                session.add(head); session.flush()
                session.add(Invoice(tannery_id=row['id'], party_id=party.id, charge_head_id=head.id,
                    voucher_no='1', fy='2026-2027', invoice_date=date(2026, 8, 1),
                    base_amount=100, cgst=2.5, sgst=2.5, gross_amount=105))
            else:
                session.add(Receipt(tannery_id=row['id'], party_id=party.id, voucher_no='1',
                    fy='2026-2027', receipt_date=date(2026, 8, 1), amount=105, is_step=False))
        else:
            batch = ImportBatch(file_name='test.xml', file_sha256='a'*64, status='reviewed', period_start=date(2026, 8, 1))
            session.add(batch); session.flush()
            session.add(StagingRow(batch_id=batch.id, row_number=1, raw_party='Linked Works', payload=json.dumps({'tannery_sno':row['sno']}), status='matched'))
        session.commit()
    assert client.delete(f"/api/tanneries/{row['id']}", headers=auth).status_code == 409
    assert client.get(f"/api/tanneries/{row['id']}", headers=auth).status_code == 200


def test_delete_preflight(master_api):
    client, _, _ = master_api
    response = client.options('/api/tanneries/1', headers={'Origin':'http://localhost:5173',
        'Access-Control-Request-Method':'DELETE', 'Access-Control-Request-Headers':'authorization'})
    assert response.status_code == 200


def test_auto_serial_advances_from_existing_and_never_reuses_deleted(master_api):
    client, headers, factory = master_api
    auth = headers['talco_admin']
    with factory() as session:
        session.add(Tannery(sno=40, name='Existing master', normalized_key='EXISTINGMASTER', pump_house='A'))
        session.commit()
    first = client.post('/api/tanneries', json={'name':'New master','pump_house':'A'}, headers=auth)
    assert first.status_code == 201, first.text
    assert first.json()['sno'] == 41
    assert client.delete(f"/api/tanneries/{first.json()['id']}", headers=auth).status_code == 204
    second = client.post('/api/tanneries', json={'name':'Next master','pump_house':'B'}, headers=auth)
    assert second.status_code == 201, second.text
    assert second.json()['sno'] == 42
    with factory() as session:
        assert session.scalar(select(Tannery).where(Tannery.name=='Existing master')).sno == 40
        session.add(Tannery(sno=90, name='Later import', normalized_key='LATERIMPORT', pump_house='C'))
        session.commit()
    third = client.post('/api/tanneries', json={'name':'After import','pump_house':'A'}, headers=auth)
    assert third.status_code == 201, third.text
    assert third.json()['sno'] == 91


def test_first_auto_serial_and_failed_create_rollback(master_api):
    client, headers, factory = master_api
    auth = headers['talco_admin']
    data = {'name':'First master','pump_house':'A'}
    assert client.post('/api/tanneries', json=data, headers=auth).json()['sno'] == 1
    assert client.post('/api/tanneries', json=data, headers=auth).status_code == 409
    assert client.post('/api/tanneries', json={**data,'name':'Second master'}, headers=auth).json()['sno'] == 2
