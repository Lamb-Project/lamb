"""lamb-0.8 changes to the 1.0-alpha LTI router: modules that need no assistants (LLM access)."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lamb import lti_router
from lamb.modules import discover_modules, get_module
from lamb.token_dealer import wiring
from lamb.token_dealer.settings import Settings

CU = {'id': 5, 'organization_id': 3, 'user_email': 't@x.edu', 'user_name': 'Teacher'}
JWT = {'lti_type': 'setup', 'lti_resource_link_id': 'rl-1', 'lti_creator_user_ids': [5], 'lti_lms_user_id': 'teacher-1',
       'lti_lms_email': 't@x.edu', 'lti_context_id': 'c1', 'lti_context_title': 'Databases'}


@pytest.fixture
def env(monkeypatch):
    discover_modules()
    calls, created = [], {}
    monkeypatch.setattr(wiring, 'settings_for', lambda org: Settings(enabled=True, proxy_url='http://p', models=['m']))
    monkeypatch.setattr(lti_router, '_validate_lti_jwt', lambda token, kind: JWT if kind == 'setup' else None)
    db = SimpleNamespace(
        get_creator_user_by_id=lambda i: CU, get_organization_by_id=lambda i: {'name': 'UPC'},
        get_published_assistants_for_org_user=lambda *a: [], get_lti_activity_by_resource_link=lambda rl: created.get(rl),
        delete_lti_activity=lambda i: calls.append(('delete', i)), get_assistant_by_id=lambda i: None)
    monkeypatch.setattr(lti_router, 'db_manager', db)
    monkeypatch.setattr(lti_router.manager, 'get_published_assistants_for_instructor', lambda cus: {})
    monkeypatch.setattr(lti_router.manager, 'configure_activity',
                        lambda **kw: calls.append(('create', kw['activity_type'], kw['assistant_ids'])) or
                        created.setdefault('rl-1', {'id': 9, 'resource_link_id': 'rl-1', 'activity_type': kw['activity_type'],
                                                    'organization_id': 3}))
    monkeypatch.setattr(lti_router.manager, 'get_public_base_url', lambda req: 'https://lamb.x')
    app = FastAPI()
    app.include_router(lti_router.router, prefix='/lamb/v1/lti')
    return SimpleNamespace(client=TestClient(app), calls=calls)


def test_setup_info_offers_llm_access_to_an_org_without_assistants(env):
    info = env.client.get('/lamb/v1/lti/setup/info', params={'token': 't'}).json()
    assert info['orgs_with_assistants'] == {'3': []}
    mods = {m['name']: m for m in info['modules']}
    assert mods['llm_access']['requires_assistants'] is False and mods['chat']['requires_assistants'] is True


def test_chat_still_needs_an_assistant(env):
    r = env.client.post('/lamb/v1/lti/configure', json={'token': 't', 'organization_id': 3, 'activity_type': 'chat'})
    assert r.status_code == 400 and 'assistant' in r.json()['detail'] and env.calls == []


def test_llm_access_is_configured_without_assistants_and_redirects_to_its_page(env, monkeypatch):
    mod = get_module('llm_access')
    monkeypatch.setattr(mod, 'on_activity_configured', lambda aid, data: env.calls.append(('module', aid, data['pool_tokens'])))
    monkeypatch.setattr(mod, 'configured_redirect', lambda base, a, u, e: f'{base}/lamb/v1/modules/llm_access/manage?token=x')
    r = env.client.post('/lamb/v1/lti/configure', json={'token': 't', 'organization_id': 3, 'activity_type': 'llm_access',
                                                         'pool_tokens': '5000'})
    assert r.status_code == 200 and r.json()['redirect_url'].endswith('/llm_access/manage?token=x')
    assert env.calls == [('create', 'llm_access', []), ('module', 9, '5000')]


def test_a_failed_module_setup_removes_the_new_activity(env, monkeypatch):
    mod = get_module('llm_access')
    def refuse(aid, data):
        raise HTTPException(status_code=400, detail='this organization requires a pool')
    monkeypatch.setattr(mod, 'on_activity_configured', refuse)
    r = env.client.post('/lamb/v1/lti/configure', json={'token': 't', 'organization_id': 3, 'activity_type': 'llm_access'})
    assert r.status_code == 400 and r.json()['detail'] == 'this organization requires a pool'
    assert env.calls[-1] == ('delete', 9)


def test_an_unavailable_module_is_refused(env, monkeypatch):
    monkeypatch.setattr(wiring, 'settings_for', lambda org: Settings(enabled=False))
    r = env.client.post('/lamb/v1/lti/configure', json={'token': 't', 'organization_id': 3, 'activity_type': 'llm_access'})
    assert r.status_code == 400 and 'not available' in r.json()['detail']
