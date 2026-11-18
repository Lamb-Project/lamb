"""Platform policy, organization settings and single-use onboarding across workers."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lamb import lti_access as access, lti_onboarding as onboarding, lti_router
from lamb.auth_context import AuthContext, get_auth_context
from lamb.lti_activity_manager import LtiActivityManager
from tests.test_lti_onboarding import db, manager, client, ticket, launch, launch_claims, ORG_A, ORG_B, SYSTEM, INSTANCE
from tests.test_lti13 import env, launch as launch13

A = 'https://' + INSTANCE
B = 'https://other.example'


def whitelist(db, origins, enabled=True):
    access.save_settings(db, SYSTEM, {'whitelist_enabled': enabled, 'allowed_origins': origins})


@pytest.mark.parametrize('raw,expected', [('https://MOODLE.example:443/', 'https://moodle.example'),
    ('http://moodle.example:80/campus/', 'http://moodle.example/campus'),
    ('https://moodle.example:8443/campus', 'https://moodle.example:8443/campus')])
def test_installation_url_normalization(raw, expected):
    assert access.normalize_url(raw) == expected


@pytest.mark.parametrize('raw', ['', 'moodle.example', 'https://*.example', 'https://user@school.example',
    'https://school.example:0', 'https://school.example/?x=1', 'https://school.example/#x', 'https://school.example/../other',
    'https://school.example/%2e%2e/other', 'https://school.example\\@other.example', 'javascript:alert(1)'])
def test_ambiguous_or_non_url_settings_rejected(raw):
    with pytest.raises(ValueError):
        access.normalize_url(raw)


def test_global_and_organization_rules_intersect(db):
    whitelist(db, [A])
    assert access.require_organization(db, db.get_organization_by_id(ORG_A), A) == A
    for other in (B, A + '.evil', A + '/other', A.replace('https:', 'http:')):
        assert not access.organization_allowed(db, ORG_A, other)
    whitelist(db, [])
    assert not access.organization_allowed(db, ORG_A, A)
    whitelist(db, [], enabled=False)
    assert access.organization_allowed(db, ORG_A, A)
    assert not access.organization_allowed(db, ORG_A, B)


@pytest.mark.parametrize('config', [{}, {'lti_access': {}}, {'lti_access': {'moodle_url': ''}}])
def test_legacy_org_keeps_access_until_bound_and_preserves_account(db, manager, config):
    uid = db.create_lti_creator_user(ORG_A, 'teacher-1', 'legacy@example.test', 'Legacy')
    db.update_organization_config(ORG_A, config)
    assert [a['id'] for a in manager.identify_instructor(lms_user_id='teacher-1', lms_instance=INSTANCE)] == [uid]
    assert onboarding.create_code(db, ORG_A)['code']
    assert access.organization_allowed(db, ORG_A, B)
    access.save_settings(db, ORG_A, {'moodle_url': A})
    assert [a['id'] for a in manager.identify_instructor(lms_user_id='teacher-1', lms_instance=INSTANCE)] == [uid]
    assert manager.identify_instructor(lms_user_id='teacher-1', lms_instance='other.example') == []
    assert db.count('Creator_users') == 1


def test_unset_binding_still_enforces_global_policy_and_organization_state(db, manager):
    access.save_settings(db, ORG_A, {'moodle_url': ''})
    code = onboarding.create_code(db, ORG_A)['code']
    whitelist(db, [A])
    assert access.organization_allowed(db, ORG_A, A)
    assert not access.organization_allowed(db, ORG_A, B)
    assert onboarding.redeem(db, manager, ticket(instance='other.example'), code).reason == 'not_allowed'
    assert onboarding.list_codes(db, ORG_A)[0]['use_count'] == 0
    whitelist(db, [])
    assert not access.organization_allowed(db, ORG_A, A)
    whitelist(db, [], enabled=False)
    assert not access.organization_allowed(db, SYSTEM, A)
    assert not access.organization_allowed(db, 9999, A)
    inactive = {**db.get_organization_by_id(ORG_A), 'status': 'inactive'}
    with pytest.raises(ValueError, match='does not accept'):
        access.require_organization(db, inactive, A)


def test_unset_binding_allows_new_account_but_keeps_ticket_and_account_origin(db, manager):
    for org in (ORG_A, ORG_B):
        access.save_settings(db, org, {'moodle_url': ''})
    codes = [onboarding.create_code(db, org)['code'] for org in (ORG_A, ORG_B)]
    claims = ticket()
    assert onboarding.redeem(db, manager, claims, codes[0]).ok
    assert onboarding.redeem(db, manager, claims, codes[1]).reason == 'replayed'
    assert onboarding.creator_access(db, manager, launch_claims(instance='other.example')) == []
    assert db.count('Creator_users') == 1
    assert onboarding.redeem(db, manager, ticket(), codes[1]).ok


def test_existing_student_activity_launch_continues_without_binding(client, db, monkeypatch):
    from fastapi.responses import HTMLResponse
    access.save_settings(db, ORG_A, {'moodle_url': ''})
    module = SimpleNamespace(on_student_launch=Mock(return_value=HTMLResponse('student activity')))
    monkeypatch.setattr(db, 'get_lti_activity_by_resource_link', lambda _: {'id': 8, 'organization_id': ORG_A, 'status': 'active'})
    monkeypatch.setattr(lti_router, '_get_activity_module', lambda _: module)
    response = launch(client, roles='Learner', tool_consumer_instance_url=B)
    assert response.status_code == 200
    assert response.text == 'student activity'
    module.on_student_launch.assert_called_once()


def test_origin_check_precedes_code_use_or_creation(db, manager):
    code = onboarding.create_code(db, ORG_A)['code']
    assert onboarding.redeem(db, manager, ticket(instance='other.example'), code).reason == 'not_allowed'
    assert db.count('Creator_users') == db.count('lti_identity_links') == 0
    assert onboarding.list_codes(db, ORG_A)[0]['use_count'] == 0
    whitelist(db, [])
    assert onboarding.redeem(db, manager, ticket(), code).reason == 'not_allowed'


def test_launch_ticket_cannot_create_second_organization_account(db, manager):
    codes = [onboarding.create_code(db, org)['code'] for org in (ORG_A, ORG_B)]
    claims = ticket()
    assert onboarding.redeem(db, manager, claims, codes[0]).ok
    assert onboarding.redeem(db, manager, claims, codes[1]).reason == 'replayed'
    assert db.count('Creator_users') == db.count('lti_creator_code_redemptions') == 1
    assert onboarding.list_codes(db, ORG_B)[0]['use_count'] == 0
    assert onboarding.creator_access(db, manager, launch_claims(instance='other.example')) == []
    # A fresh launch can still join a second organization attached to the same Moodle.
    assert onboarding.redeem(db, manager, ticket(), codes[1]).ok


def test_concurrent_redemptions_claim_a_ticket_once(db, manager):
    codes = [onboarding.create_code(db, org)['code'] for org in (ORG_A, ORG_B)]
    claims, barrier = ticket(), Barrier(2)
    def redeem(code):
        barrier.wait()
        return onboarding.redeem(db, manager, claims, code)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(redeem, codes))
    assert sum(r.ok for r in results) == 1
    assert next(r for r in results if not r.ok).reason == 'replayed'
    assert db.count('Creator_users') == db.count('lti_creator_code_redemptions') == 1


def test_signed_launch_and_headers_cannot_bypass_admission(client, db, monkeypatch):
    real = SimpleNamespace(get_lti_credentials=lambda: ('key', 'secret'),
        _compute_oauth_signature=LtiActivityManager._compute_oauth_signature)
    monkeypatch.setattr(lti_router.manager, 'validate_oauth_signature',
        lambda *a, **k: LtiActivityManager.validate_oauth_signature(real, *a, **k))
    whitelist(db, [A])
    def signed(origin, **extra):
        data = {'oauth_consumer_key': 'key', 'resource_link_id': 'r1', 'roles': 'Instructor',
            'user_id': 'teacher-1', 'tool_consumer_instance_url': origin, **extra}
        data['oauth_signature'] = LtiActivityManager._compute_oauth_signature(
            data, 'POST', 'http://testserver/lamb/v1/lti/launch', 'secret')
        return data
    assert client.post('/lamb/v1/lti/launch', data=signed(B), headers={'Origin': A, 'Referer': A}).status_code == 403
    good = client.post('/lamb/v1/lti/launch', data=signed(A))
    assert good.status_code == 200 and 'Creator code' in good.text
    altered = signed(B)
    altered['tool_consumer_instance_url'] = A
    assert client.post('/lamb/v1/lti/launch', data=altered).status_code == 401
    assert db.count('Creator_users') == 0


def test_configured_activity_is_checked_before_module_dispatch(client, db, monkeypatch):
    module = SimpleNamespace(on_instructor_launch=Mock(), on_student_launch=Mock())
    monkeypatch.setattr(db, 'get_lti_activity_by_resource_link', lambda _: {'id': 8, 'organization_id': ORG_A, 'status': 'active'})
    monkeypatch.setattr(lti_router, '_get_activity_module', lambda _: module)
    response = launch(client, roles='Learner', tool_consumer_instance_url=B)
    assert response.status_code == 403
    module.on_student_launch.assert_not_called()
    module.on_instructor_launch.assert_not_called()


def test_lti13_whitelist_applies_before_identity_creation(env):
    from lamb.lti13 import protocol
    env.db.get_organization_by_slug = lambda _: {'config': {'lti_access': {'whitelist_enabled': True, 'allowed_origins': [A]}}}
    with pytest.raises(ValueError, match='not allowed'):
        protocol.validate_launch(launch13(env), env.store)
    with env.db.get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM T_lti13_objects').fetchone()[0] == 0


def test_lti13_registration_allowlist_does_not_replace_org_binding(env):
    from lamb.lti13 import protocol
    context = protocol.validate_launch(launch13(env), env.store)
    env.db.get_organization_by_id = lambda oid: {'id': oid, 'config': {'lti_access': {'moodle_url': B}}}
    with pytest.raises(ValueError, match='not connected'):
        env.store.link_creator(context['lms_user_id'], 1)
    with pytest.raises(ValueError, match='not connected'):
        env.store.assert_org(context['resource_link_id'], 1)


def test_settings_permissions_and_saved_policy(db, monkeypatch):
    from creator_interface import lti_onboarding_router as api
    monkeypatch.setattr(api, 'db_manager', db)
    context = AuthContext(user={'id': 7}, token_payload={}, organization=db.get_organization_by_id(ORG_A), is_org_admin=True)
    app = FastAPI()
    app.dependency_overrides[get_auth_context] = lambda: context
    async def org_admin(request, target=None):
        from fastapi import HTTPException
        if target not in (None, ORG_A) and not context.is_system_admin:
            raise HTTPException(403, 'Wrong organization')
        return {'organization_id': target or ORG_A, 'user_id': 7}
    monkeypatch.setattr(api, 'verify_organization_admin_access', org_admin)
    app.include_router(api.router, prefix='/admin')
    client = TestClient(app)
    policy = {'whitelist_enabled': True, 'allowed_origins': [A]}
    assert client.put('/admin/lti-access', json=policy).status_code == 403
    assert client.get('/admin/lti-access').status_code == 403
    context.is_system_admin = True
    assert client.put('/admin/lti-access', json=policy).status_code == 200
    assert client.get('/admin/lti-access').json() == policy
    context.is_system_admin = False
    path = '/admin/org-admin/settings/lti-access'
    assert client.put(path, json={'moodle_url': B}).status_code == 400
    assert client.put(path + '?org=beta', json={'moodle_url': A}).status_code == 403
    assert client.put(path, json={'moodle_url': A + '/'}).json()['moodle_url'] == A
    assert client.get(path).json()['moodle_url'] == A
    # Clearing the binding is allowed, including when a global restriction exists.
    assert client.put(path, json={'moodle_url': ''}).json()['moodle_url'] == ''
    assert access.organization_allowed(db, ORG_A, A)
    assert not access.organization_allowed(db, ORG_A, B)
    assert client.put('/admin/lti-access', json={'whitelist_enabled': False}).status_code == 403
    # Feature-specific writes do not discard other organization configuration.
    before = db.get_organization_by_id(ORG_B)['config']['features']
    access.save_settings(db, ORG_B, {'moodle_url': A})
    assert db.get_organization_by_id(ORG_B)['config']['features'] == before


@pytest.mark.parametrize('kind', ['creator', 'student'])
def test_legacy_endpoints_enforce_binding_and_global_whitelist(db, monkeypatch, kind):
    from lamb import lti_creator_router, lti_users_router
    module = lti_creator_router if kind == 'creator' else lti_users_router
    monkeypatch.setattr(module, 'db_manager', db)
    monkeypatch.setenv('LTI_SECRET', 'secret')
    org = db.get_organization_by_id(ORG_A)
    org['lti_creator'] = {'oauth_consumer_secret': 'secret'}
    monkeypatch.setattr(db, 'get_organization_by_lti_consumer_key', lambda _: org, raising=False)
    monkeypatch.setattr(db, 'get_published_assistant_by_oauth_consumer', lambda _: {'assistant_id': 5}, raising=False)
    monkeypatch.setattr(db, 'get_assistant_by_id', lambda _: SimpleNamespace(organization_id=ORG_A), raising=False)
    monkeypatch.setattr(db, 'get_lti_user_by_email', lambda _: {'id': 9}, raising=False)
    token = Mock(return_value='synthetic-token')
    monkeypatch.setattr(lti_users_router.owi_user_manager, 'get_auth_token', token)
    app = FastAPI()
    app.include_router(module.router, prefix='/legacy')
    client = TestClient(app, follow_redirects=False)
    path = '/legacy/launch' if kind == 'creator' else '/legacy/lti'
    def send(origin):
        data = {'oauth_consumer_key': 'key', 'user_id': 'teacher-1', 'tool_consumer_instance_url': origin}
        data['oauth_signature'] = lti_creator_router.generate_oauth_signature(data, 'POST', 'http://testserver' + path, 'secret')
        return client.post(path, data=data)
    assert send(B).status_code == 403
    assert db.count('Creator_users') == 0
    token.assert_not_called()
    whitelist(db, [])
    assert send(A).status_code == 403
    whitelist(db, [A])
    assert send(A).status_code == 303


def test_lti13_organization_without_binding_keeps_registration_checks(env):
    from lamb.lti13 import protocol
    context = protocol.validate_launch(launch13(env), env.store)
    env.db.get_organization_by_id = lambda oid: {'id': oid, 'config': {}}
    env.store.assert_org(context['resource_link_id'], 1)
    env.db.get_organization_by_id = lambda oid: {'id': oid, 'config': {'lti_access': {'moodle_url': B}}}
    with pytest.raises(ValueError, match='not connected'):
        env.store.assert_org(context['resource_link_id'], 1)
