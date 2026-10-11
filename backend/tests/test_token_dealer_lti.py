"""LLM-access activity module (lamb-0.8): the module contract over token-dealer, and its pages."""
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lamb.migrations import MigrationRunner
from lamb.token_dealer import lti, wiring
from lamb.token_dealer.ledger import UsageLedger
from lamb.token_dealer.service import TokenDealerService
from lamb.token_dealer.settings import Settings
from lamb.token_dealer.store import TokenDealerStore
from lamb.modules.base import LTIContext

from tests.test_token_dealer import Db, FakeProxy

SETTINGS = Settings(enabled=True, proxy_url='http://proxy', proxy_admin_key='k', public_url='https://llm.x/v1',
                    policy='both', teacher_allowance_tokens=100000, models=['course-model'], timezone='Europe/Madrid')
LTI_ACTIVITY = {'id': 7, 'resource_link_id': 'rl-9', 'organization_id': 1, 'owner_email': 't@x.edu', 'owner_name': 'Teacher',
                'context_id': 'c1', 'context_title': 'Databases', 'activity_type': 'llm_access'}
PREFIX = '/lamb/v1/modules/llm_access'


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = Db(str(tmp_path / 'lamb.db'))
    with sqlite3.connect(db.path) as c:
        c.execute('CREATE TABLE T_organizations (id INTEGER PRIMARY KEY)')
        c.execute('INSERT INTO T_organizations VALUES (1)')
        MigrationRunner(db)._migration_33(c.cursor())
    store, proxy = TokenDealerStore(db), FakeProxy()
    settings = {'s': SETTINGS}
    monkeypatch.setattr(wiring, 'store', lambda: store)
    monkeypatch.setattr(wiring, 'settings_for', lambda org: settings['s'])
    monkeypatch.setattr(wiring, 'service', lambda: TokenDealerService(store, lambda o: settings['s'], lambda o: proxy))
    monkeypatch.setattr(wiring, 'ledger', lambda: UsageLedger(tmp_path / 'usage.db'))
    from lamb.modules import llm_access
    mod = llm_access.LlmAccessModule.__new__(llm_access.LlmAccessModule)
    mod.db_manager = SimpleNamespace(get_lti_activity_by_id=lambda i: LTI_ACTIVITY)
    app = FastAPI()
    app.include_router(lti.router, prefix=PREFIX)
    return SimpleNamespace(client=TestClient(app), store=store, proxy=proxy, module=mod, settings=settings)


def configure(env, **fields):
    env.module.on_activity_configured(7, {'configured_by_email': 't@x.edu', 'activity_name': 'Databases', **fields})
    return env.store.get_activity_by_resource_link('rl-9')


def ctx(instructor):
    return LTIContext(resource_link_id='rl-9', lms_user_id='teacher-1' if instructor else 'stu-1', lms_email='x@x.edu',
                      username='u', display_name='Ana', roles='Instructor' if instructor else 'Learner',
                      is_instructor=instructor, context_id='c1', context_title='Databases')


def test_module_contract_and_availability(env):
    m = env.module
    assert m.name == 'llm_access' and m.requires_assistants is False and m.get_migrations() == []
    assert [f.name for f in m.get_setup_fields()] == ['pool_tokens', 'slot_tokens', 'total_tokens']
    assert m.enabled_for_org(1)
    env.settings['s'] = Settings(enabled=False)
    assert not m.enabled_for_org(1)


def test_setup_creates_the_activity_open_all_the_time_in_the_org_zone(env):
    a = configure(env, pool_tokens='50000', slot_tokens='2000')
    assert a['pool_tokens'] == 50000 and a['slot_tokens'] == 2000 and a['models'] == ['course-model']
    assert a['schedule'] == {'timezone': 'Europe/Madrid', 'mode': 'always', 'weekly': []}
    assert env.proxy.names() == ['create_team']
    url = env.module.configured_redirect('https://lamb.x', LTI_ACTIVITY, 'teacher-1', 't@x.edu')
    assert url.startswith('https://lamb.x/lamb/v1/modules/llm_access/manage?token=')


@pytest.mark.parametrize('fields,status', [({'slot_tokens': '2000'}, 400), ({'pool_tokens': 'lots', 'slot_tokens': '1'}, 400)])
def test_setup_errors_reach_the_setup_app_as_400(env, fields, status):
    with pytest.raises(HTTPException) as e:
        configure(env, **fields)
    assert e.value.status_code == status and env.store.get_activity_by_resource_link('rl-9') is None


def test_launches_go_to_the_module_pages(env):
    configure(env, pool_tokens='50000', slot_tokens='2000')
    assert env.module.on_instructor_launch(ctx(True)).headers['location'].startswith(PREFIX + '/manage?token=')
    assert env.module.on_student_launch(ctx(False)).headers['location'].startswith(PREFIX + '/student?token=')
    assert env.module.launch_user(LTI_ACTIVITY, 'u', 'Ana', 'stu-1').startswith(PREFIX + '/student?token=')


def test_student_takes_a_key_once_after_the_notice(env):
    a = configure(env, pool_tokens='50000', slot_tokens='2000')
    t = lti.make_token({'type': 'student', 'activity_id': a['id'], 'lms_user_id': 'stu-1', 'email': 's@x.edu', 'name': 'Ana'})
    assert 'Get my key' in env.client.get(PREFIX + '/student', params={'token': t}).text
    assert 'accept the notice' in env.client.post(PREFIX + '/issue', data={'token': t}).text
    r = env.client.post(PREFIX + '/issue', data={'token': t, 'accept': lti.NOTICE_VERSION})
    assert 'sk-secret-1' in r.text and 'ANTHROPIC_BASE_URL=https://llm.x' in r.text
    again = env.client.get(PREFIX + '/student', params={'token': t}).text
    assert 'sk-secret-1' not in again and 'Replace my key' in again
    assert env.module.get_dashboard_stats(LTI_ACTIVITY)['students_with_keys'] == 1


def test_instructor_pages_need_the_manage_token_and_change_every_key(env):
    a = configure(env, pool_tokens='50000', slot_tokens='2000')
    st = lti.make_token({'type': 'student', 'activity_id': a['id'], 'lms_user_id': 'stu-1'})
    env.client.post(PREFIX + '/issue', data={'token': st, 'accept': lti.NOTICE_VERSION})
    key = env.store.get_current_key(a['id'], 'stu-1')
    assert env.client.post(PREFIX + '/student-action', data={'token': st, 'key_id': key['id'], 'action': 'revoke'}).status_code == 403
    mt = lti.make_token({'type': 'manage', 'activity_id': a['id'], 'lms_user_id': 'teacher-1'})
    assert 'Change limits and timetable' in env.client.get(PREFIX + '/manage', params={'token': mt}).text
    env.client.post(PREFIX + '/student-action', data={'token': mt, 'key_id': key['id'], 'action': 'block'})
    assert env.store.get_key(key['id'])['status'] == 'blocked'
    r = env.client.post(PREFIX + '/configure', follow_redirects=False, data={
        'token': mt, 'models': 'course-model', 'mode': 'weekly', 'days': ['0'], 'start': '15:00', 'end': '17:00',
        'timezone': 'Europe/Madrid', 'pool_tokens': '60000', 'slot_tokens': '3000'})
    assert r.status_code == 303 and env.store.get_activity(a['id'])['slot_tokens'] == 3000
    assert [c for c in env.proxy.calls if c[0] == 'update_key'][0][2]['budget_limits'][0]['max_budget'] == 0.003
