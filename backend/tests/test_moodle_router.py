from types import SimpleNamespace
import json
from unittest.mock import patch
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lamb.auth_context import get_auth_context
from lamb.moodle.router import router
from tests.test_moodle_store import stores, record

@pytest.fixture
def client(stores,monkeypatch):
    db,store=stores
    monkeypatch.setenv('LAMB_MOODLE_ENCRYPTION_KEY',Fernet.generate_key().decode())
    app=FastAPI();app.include_router(router)
    auth=SimpleNamespace(user={'id':7},organization={'id':1,'config':{}},is_system_admin=False,is_org_admin=False)
    app.dependency_overrides[get_auth_context]=lambda:auth
    with patch('lamb.moodle.router.database',return_value=db), patch('lamb.moodle.router.effective_driver',return_value={'provider':'ollama','model':'fixture'}):
        yield TestClient(app),auth,store


def test_connection_endpoints_only_return_public_identity(client):
    c,auth,store=client
    with patch('lamb.moodle.router.establish_connection',return_value=record()) as establish:
        result=c.post('/moodle/connection',json={'token':'fixture-secret'})
    assert result.status_code==200,result.text
    assert establish.call_args.kwargs['token']=='fixture-secret'
    assert 'ciphertext' not in result.text and 'fixture-secret' not in result.text
    status=c.get('/moodle/connection');assert status.json()['connected']
    assert 'ciphertext' not in status.text
    assert c.delete('/moodle/connection').status_code==200
    assert c.get('/moodle/connection').json()['connection'] is None


def test_config_is_admin_only_and_scoped(client,stores):
    c,auth,_=client
    payload={'enabled':True,'base_url':'https://other.test','mode':'full','write_groups':['forum']}
    assert c.put('/moodle/settings',json=payload).status_code==403
    auth.is_org_admin=True
    assert c.put('/moodle/settings',json=payload).status_code==200
    result=c.get('/moodle/connection').json()
    assert result['settings']['base_url']=='https://other.test'
    assert not result['settings']['allow_grade_write']
    assert 'hosted' in result['privacy_notice']
    assert c.put('/moodle/settings',json={**payload,'write_groups':['roles']}).status_code==400


def test_missing_key_is_admin_error_not_bad_user_request(client,monkeypatch):
    c,_,_=client;monkeypatch.delenv('LAMB_MOODLE_ENCRYPTION_KEY')
    result=c.post('/moodle/connection',json={'token':'fixture-secret'})
    assert result.status_code==503
    assert 'fixture-secret' not in result.text


def test_foreign_owner_cannot_use_stale_org_context(client):
    c,auth,_=client;auth.organization['id']=2
    assert c.get('/moodle/connection').status_code==403
    assert c.delete('/moodle/connection').status_code==403


def test_anonymous_denied(client):
    c,_,_=client;c.app.dependency_overrides.clear()
    assert c.get('/moodle/connection').status_code in (401,403)
    assert c.get('/moodle/charts').status_code in (401,403)
    assert c.get('/moodle/charts/00000000-0000-0000-0000-000000000001').status_code in (401,403)


def test_chart_listing_is_private_and_failures_are_explicit(client):
    c, auth, _ = client
    with patch('lamb.moodle.runtime.MoodleRuntime') as runtime:
        runtime.return_value.execute.return_value = {'items':[], 'next_offset':None}
        result=c.get('/moodle/charts?offset=20')
        assert result.status_code == 200 and result.headers['cache-control'] == 'private, no-store'
        runtime.return_value.execute.assert_called_once_with('chart.list', {'offset':20})
        for error, status in [(PermissionError('private'),403),(ValueError('private'),400),(ConnectionError('private'),503)]:
            runtime.return_value.execute.side_effect=error
            response=c.get('/moodle/charts')
            assert response.status_code == status and 'private' not in response.text
    auth.organization['id']=2
    assert c.get('/moodle/charts').status_code == 403


def test_stale_general_config_update_cannot_restore_disconnected_token(stores):
    from lamb.database_manager import LambDatabaseManager
    db, store = stores
    snap = store.snapshot()
    store.save(record(), expected_generation=snap['generation'], expected_policy=snap['policy'])
    stale = {'moodle_connection': record(), 'moodle_connection_generation': 1, 'can_share': True}
    store.disconnect()
    assert LambDatabaseManager.update_user_config(db, 7, stale)
    assert store.snapshot()['record'] is None
    assert store.snapshot()['generation'] == 2
    with db.get_connection() as conn:
        config = json.loads(conn.execute('SELECT user_config FROM Creator_users WHERE id=7').fetchone()[0])
    assert config['can_share']


def test_public_user_configuration_redacts_connector_record():
    from lamb.moodle.connection import public_user_config
    raw = {'can_share': True, 'moodle_connection': record(), 'moodle_connection_generation': 3}
    for value in (raw, json.dumps(raw)):
        assert public_user_config(value) == {'can_share': True}
    assert raw['moodle_connection'] == record()


def test_approval_preference_is_personal_strict_and_survives_disconnect(client, stores):
    c, auth, store = client
    from lamb.moodle.store import ConnectionStore
    from lamb.database_manager import LambDatabaseManager
    db, _ = stores
    assert c.get('/moodle/connection').json()['approval_preferences'] == {'advanced_mode': False}
    generation = store.snapshot()['generation']
    assert c.put('/moodle/approval-preferences', json={'advanced_mode': True}).json() == {'advanced_mode': True}
    assert store.snapshot()['generation'] == generation
    assert ConnectionStore(db, 1, 8).approval_preferences() == {'advanced_mode': False}
    assert ConnectionStore(db, 2, 9).approval_preferences() == {'advanced_mode': False}
    c.delete('/moodle/connection')
    assert LambDatabaseManager.update_user_config(db, 7, {'can_share': True})
    assert c.get('/moodle/connection').json()['approval_preferences'] == {'advanced_mode': True}
    assert c.put('/moodle/approval-preferences', json={'advanced_mode': 'true'}).status_code == 422
    assert c.put('/moodle/approval-preferences', json={'advanced_mode': True, 'owner_id': 8}).status_code == 422
    auth.organization['id'] = 2
    assert c.put('/moodle/approval-preferences', json={'advanced_mode': False}).status_code == 403
    c.app.dependency_overrides.clear()
    assert c.put('/moodle/approval-preferences', json={'advanced_mode': False}).status_code in (401, 403)
