"""LTI pages of LLM-access activities (token-dealer): setup, manage, student key page."""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lamb import auth as lamb_auth
from lamb.migrations import MigrationRunner
from lamb.token_dealer import lti, wiring
from lamb.token_dealer.ledger import UsageLedger
from lamb.token_dealer.service import TokenDealerService
from lamb.token_dealer.settings import Settings
from lamb.token_dealer.store import TokenDealerStore
from datetime import timedelta

from tests.test_token_dealer import FakeProxy, Db

SETTINGS = Settings(enabled=True, proxy_url='http://proxy', proxy_admin_key='k', public_url='https://llm.x/v1',
                    policy='both', teacher_allowance_tokens=100000, models=['course-model'])


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = Db(str(tmp_path / 'lamb.db'))
    with sqlite3.connect(db.path) as c:
        c.execute('CREATE TABLE T_organizations (id INTEGER PRIMARY KEY)')
        c.execute('INSERT INTO T_organizations VALUES (1)')
        MigrationRunner(db)._migration_33(c.cursor())
    store, proxy = TokenDealerStore(db), FakeProxy()
    monkeypatch.setattr(wiring, 'store', lambda: store)
    monkeypatch.setattr(wiring, 'settings_for', lambda org: SETTINGS)
    monkeypatch.setattr(wiring, 'service', lambda: TokenDealerService(store, lambda o: SETTINGS, lambda o: proxy))
    monkeypatch.setattr(wiring, 'ledger', lambda: UsageLedger(tmp_path / 'usage.db'))
    monkeypatch.setattr(wiring, 'db', lambda: type('D', (), {'get_organization_by_id': staticmethod(lambda i: {'name': 'UPC'})})())
    app = FastAPI()
    app.include_router(lti.router, prefix='/lamb/v1/lti/llm-access')
    return TestClient(app), store, proxy


def setup_token():
    return lamb_auth.create_token({'scope': 'lti_unified', 'type': 'setup', 'resource_link_id': 'rl-9', 'lms_user_id': 'teacher-1',
                                   'context_id': 'c1', 'context_title': 'Databases', 'creator_users': [
                                       {'id': 5, 'organization_id': 1, 'user_email': 't@x.edu', 'user_name': 'Teacher'}]},
                                  expires_delta=timedelta(minutes=10))


def configure(client, **extra):
    form = {'token': setup_token(), 'organization_id': '1', 'models': 'course-model', 'mode': 'weekly', 'days': ['0', '2'],
            'start': '15:00', 'end': '17:00', 'timezone': 'Europe/Madrid', 'pool_tokens': '50000', 'slot_tokens': '2000', **extra}
    return client.post('/lamb/v1/lti/llm-access/configure', data=form, follow_redirects=False)


def test_setup_page_lists_the_policy_and_the_allowance_left(env):
    client, store, proxy = env
    r = client.get('/lamb/v1/lti/llm-access/setup', params={'token': setup_token()})
    assert r.status_code == 200 and 'an activity pool and a per-student allowance' in r.text and '100,000' in r.text


def test_configure_creates_the_activity_and_opens_the_manage_page(env):
    client, store, proxy = env
    r = configure(client)
    assert r.status_code == 303 and r.headers['location'].startswith('manage?token=')
    a = store.get_activity_by_resource_link('rl-9')
    assert a['pool_tokens'] == 50000 and a['schedule']['weekly'][0]['days'] == [0, 2] and proxy.names() == ['create_team']
    page = client.get('/lamb/v1/lti/llm-access/' + r.headers['location'])
    assert page.status_code == 200 and 'No student has taken a key yet' in page.text


def test_policy_violations_come_back_to_the_form(env):
    client, store, proxy = env
    r = configure(client, pool_tokens='')                       # policy "both" needs a pool
    assert r.status_code == 303 and 'setup?token=' in r.headers['location'] and 'error=' in r.headers['location']
    assert store.get_activity_by_resource_link('rl-9') is None and proxy.names() == []


def test_student_takes_a_key_once_after_the_notice(env):
    client, store, proxy = env
    configure(client)
    a = store.get_activity_by_resource_link('rl-9')
    t = lti.make_token({'type': 'student', 'activity_id': a['id'], 'lms_user_id': 'stu-1', 'email': 's@x.edu', 'name': 'Ana'})
    page = client.get('/lamb/v1/lti/llm-access/student', params={'token': t})
    assert 'Get my key' in page.text and 'does not store the text' in page.text
    refused = client.post('/lamb/v1/lti/llm-access/issue', data={'token': t})
    assert 'accept the notice' in refused.text and 'generate_key' not in proxy.names()
    r = client.post('/lamb/v1/lti/llm-access/issue', data={'token': t, 'accept': lti.NOTICE_VERSION})
    assert 'sk-secret-1' in r.text and 'ANTHROPIC_BASE_URL=https://llm.x' in r.text
    again = client.get('/lamb/v1/lti/llm-access/student', params={'token': t})
    assert 'sk-secret-1' not in again.text and 'sk-secr…' in again.text and 'Replace my key' in again.text
    assert store.get_current_key(a['id'], 'stu-1')['notice_version'] == lti.NOTICE_VERSION


def test_instructor_actions_need_the_manage_token_of_that_activity(env):
    client, store, proxy = env
    configure(client)
    a = store.get_activity_by_resource_link('rl-9')
    st = lti.make_token({'type': 'student', 'activity_id': a['id'], 'lms_user_id': 'stu-1'})
    client.post('/lamb/v1/lti/llm-access/issue', data={'token': st, 'accept': lti.NOTICE_VERSION})
    key = store.get_current_key(a['id'], 'stu-1')
    assert client.post('/lamb/v1/lti/llm-access/student-action', data={'token': st, 'key_id': key['id'], 'action': 'revoke'}).status_code == 403
    mt = lti.make_token({'type': 'manage', 'activity_id': a['id'], 'lms_user_id': 'teacher-1'})
    client.post('/lamb/v1/lti/llm-access/student-action', data={'token': mt, 'key_id': key['id'], 'action': 'block'})
    assert store.get_key(key['id'])['status'] == 'blocked'
    client.post('/lamb/v1/lti/llm-access/override', data={'token': mt, 'override': 'closed'})
    assert store.get_activity(a['id'])['override'] == 'closed'


def test_the_manage_page_changes_limits_for_every_key(env):
    client, store, proxy = env
    configure(client)
    a = store.get_activity_by_resource_link('rl-9')
    st = lti.make_token({'type': 'student', 'activity_id': a['id'], 'lms_user_id': 'stu-1'})
    client.post('/lamb/v1/lti/llm-access/issue', data={'token': st, 'accept': lti.NOTICE_VERSION})
    mt = lti.make_token({'type': 'manage', 'activity_id': a['id'], 'lms_user_id': 'teacher-1'})
    assert 'Change limits and timetable' in client.get('/lamb/v1/lti/llm-access/manage', params={'token': mt}).text
    r = client.post('/lamb/v1/lti/llm-access/configure', follow_redirects=False, data={
        'token': mt, 'models': 'course-model', 'mode': 'always', 'timezone': 'Europe/Madrid', 'pool_tokens': '60000', 'slot_tokens': '3000'})
    assert r.status_code == 303 and store.get_activity(a['id'])['slot_tokens'] == 3000
    upd = [c for c in proxy.calls if c[0] == 'update_key']
    assert len(upd) == 1 and upd[0][2]['budget_limits'][0]['max_budget'] == 0.003
