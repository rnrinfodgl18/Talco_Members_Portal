from sqlalchemy import select
from app.models import AuditLog, Pump, Tannery
from test_tannery_crud import master_api
import pytest


def test_pump_lifecycle_assignment_rename_and_delete(master_api):
    client, headers, factory = master_api
    auth = headers['talco_admin']
    data = {'code': 'north_1', 'name': 'North Pump', 'location': 'North road', 'notes': 'New pump'}
    response = client.post('/api/pumps', json=data, headers=auth)
    assert response.status_code == 201, response.text
    pump = response.json(); path = f"/api/pumps/{pump['id']}"
    assert pump['code'] == 'NORTH_1'
    assert client.post('/api/pumps', json=data, headers=auth).status_code == 409
    tannery = client.post('/api/tanneries', json={'name':'Test works','pump_house':'NORTH_1'}, headers=auth)
    assert tannery.status_code == 201, tannery.text
    tid = tannery.json()['id']
    assert client.get(path, headers=auth).json()['tannery_count'] == 1
    changed = {**data, 'code':'NORTH_2', 'name':'Renamed pump', 'location':None, 'notes':None}
    response = client.patch(path, json=changed, headers=auth)
    assert response.status_code == 200, response.text
    assert response.json()['tannery_count'] == 1
    assert client.get(f'/api/tanneries/{tid}', headers=auth).json()['pump_house'] == 'NORTH_2'
    assert len(client.get('/api/tanneries?pump_house=NORTH_2', headers=auth).json()) == 1
    assert client.delete(path, headers=auth).status_code == 409
    assert client.patch(f'/api/tanneries/{tid}', json={'pump_house':'A'}, headers=auth).status_code == 200
    assert client.delete(path, headers=auth).status_code == 204
    assert client.get(path, headers=auth).status_code == 404
    with factory() as session:
        logs = session.scalars(select(AuditLog).where(AuditLog.entity_type=='pump').order_by(AuditLog.id)).all()
        assert [x.action for x in logs] == ['create','update','delete']


@pytest.mark.parametrize('role', ['talco_staff','member','member_staff','lessee'])
def test_pump_permissions(master_api, role):
    client, headers, _ = master_api
    auth = {**headers[role], 'X-TALCO-ROLE':'talco_admin'}
    assert client.get('/api/pumps', headers=auth).status_code == (200 if role=='talco_staff' else 403)
    for method, path, data in [('post','/api/pumps',{'code':'F','name':'Test'}),
                               ('patch','/api/pumps/1',{'code':'A','name':'Changed'})]:
        assert getattr(client, method)(path, json=data, headers=auth).status_code == 403
    assert client.delete('/api/pumps/1', headers=auth).status_code == 403


def test_pump_validation_and_unknown_selection(master_api):
    client, headers, _ = master_api
    auth=headers['talco_admin']
    assert client.get('/api/pumps').status_code == 401
    for data in [{'code':'','name':'Test'},{'code':'A B','name':'Test'},{'code':'F','name':'  '}]:
        assert client.post('/api/pumps', json=data, headers=auth).status_code == 422
    assert client.post('/api/tanneries', json={'name':'Test','pump_house':'MISSING'}, headers=auth).status_code == 422
    row=client.post('/api/tanneries', json={'name':'Test','pump_house':'A'}, headers=auth).json()
    assert client.patch(f"/api/tanneries/{row['id']}",json={'pump_house':'MISSING'},headers=auth).status_code == 422
    assert client.get(f"/api/tanneries/{row['id']}", headers=auth).json()['pump_house'] == 'A'
    assert client.patch('/api/pumps/1',json={'code':'B','name':'Duplicate'},headers=auth).status_code == 409
    assert client.get('/api/pumps/1',headers=auth).json()['code'] == 'A'
