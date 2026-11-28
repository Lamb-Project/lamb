"""Optional LMS admission: nothing is refused until an administrator asks for it, the
installation is compared as the LMS sends it, and onboarding tickets are used once."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from lamb import activity_access, lti_access as access, lti_onboarding as onboarding, lti_router
from lamb.auth_context import AuthContext, get_auth_context
from tests.test_lti_onboarding import db, manager, client, ticket, launch, launch_claims, ORG_A, ORG_B, SYSTEM, INSTANCE
from tests.test_lti13 import env, launch as launch13

A, B = INSTANCE, 'other.example'


def whitelist(db, instances, enabled=True):
    access.save_settings(db, SYSTEM, {'whitelist_enabled': enabled, 'allowed_instances': instances})


def lock(db, organization_id, instances):
    access.save_settings(db, organization_id, {'locked_instances': instances})


def existing_activity(db, monkeypatch, organization_id=ORG_A):
    module = SimpleNamespace(on_student_launch=Mock(return_value=HTMLResponse('student activity')))
    monkeypatch.setattr(db, 'get_lti_activity_by_resource_link',
                        lambda _: {'id': 8, 'organization_id': organization_id, 'status': 'active'})
    monkeypatch.setattr(lti_router, '_get_activity_module', lambda _: module)
    monkeypatch.setattr(lti_router.activity_access, 'record_launch', lambda *a, **kw: None)
    return module


def student(client, instance=A):
    return launch(client, roles='Learner', tool_consumer_instance_guid=instance)


# -- off by default -------------------------------------------------------------------

@pytest.mark.parametrize('instance', [A, '9a0364b9e99bb480dd25e1f0284c8555', '', 'upc_atenea', 'UPC Atenea', 'localhost'])
def test_nothing_configured_admits_a_signed_launch_whatever_the_lms_calls_itself(client, db, monkeypatch, instance):
    module = existing_activity(db, monkeypatch)
    assert student(client, instance).text == 'student activity'
    module.on_student_launch.assert_called_once()


def test_an_activity_of_the_system_organization_is_launched_like_any_other(client, db, monkeypatch):
    existing_activity(db, monkeypatch, SYSTEM)
    assert student(client).status_code == 200


def legacy_student_client(db, monkeypatch, organization_id):
    from lamb import lti_creator_router, lti_users_router
    monkeypatch.setattr(lti_users_router, 'db_manager', db)
    monkeypatch.setenv('LTI_SECRET', 'secret')
    monkeypatch.setattr(db, 'get_published_assistant_by_oauth_consumer',
                        lambda _: {'assistant_id': 5} if organization_id else None, raising=False)
    monkeypatch.setattr(db, 'get_assistant_by_id', lambda _: SimpleNamespace(organization_id=organization_id), raising=False)
    monkeypatch.setattr(db, 'get_lti_user_by_email', lambda _: {'id': 9}, raising=False)
    monkeypatch.setattr(lti_users_router.owi_user_manager, 'get_auth_token', Mock(return_value='synthetic-token'))
    app = FastAPI()
    app.include_router(lti_users_router.router, prefix='/legacy')
    test_client = TestClient(app, follow_redirects=False)
    def send(instance):
        data = {'oauth_consumer_key': 'key', 'user_id': 'student-1', 'tool_consumer_instance_guid': instance}
        data['oauth_signature'] = lti_creator_router.generate_oauth_signature(data, 'POST', 'http://testserver/legacy/lti', 'secret')
        return test_client.post('/legacy/lti', data=data).status_code
    return send


@pytest.mark.parametrize('organization_id', [ORG_A, SYSTEM, None])
def test_legacy_student_launch_enters_a_regular_the_system_and_an_unresolved_organization(db, monkeypatch, organization_id):
    send = legacy_student_client(db, monkeypatch, organization_id)
    assert send(A) == send('') == send('upc_atenea') == 303


def test_settings_of_the_17_november_dev_build_are_not_read(db):
    access.save_settings(db, ORG_A, {'locked_instances': []})
    db.update_organization_config(ORG_A, {'lti_access': {'moodle_url': 'https://moodle.example/campus'}})
    db.update_organization_config(SYSTEM, {'lti_access': {'whitelist_enabled': True, 'allowed_origins': ['https://x.example']}})
    assert access.global_settings(db) == {'whitelist_enabled': False, 'allowed_instances': []}
    assert access.organization_allowed(db, ORG_A, B)


# -- the organization lock --------------------------------------------------------------

@pytest.mark.parametrize('locked', [A, 'upc_atenea', 'localhost', 'UPC Atenea'])
def test_a_locked_organization_admits_only_its_installations_compared_as_sent(client, db, monkeypatch, locked):
    lock(db, ORG_A, [locked])
    module = existing_activity(db, monkeypatch)
    assert student(client, locked).status_code == 200
    for other in (B, '', locked.upper() + 'x'):
        refused = student(client, other)
        assert refused.status_code == 403 and 'not connected to the organization' in refused.text
    module.on_student_launch.assert_called_once()
    lock(db, ORG_A, [locked, B])
    assert student(client, B).status_code == 200
    lock(db, ORG_A, [])
    assert student(client, '').status_code == 200


def test_the_lock_reaches_the_legacy_routes_and_the_accounts_a_launch_may_act_as(db, manager, monkeypatch):
    send = legacy_student_client(db, monkeypatch, ORG_A)
    code = onboarding.create_code(db, ORG_A)['code']
    account = onboarding.redeem(db, manager, ticket(), code).creator_user
    recognised = lambda instance: [a['id'] for a in manager.identify_instructor(lms_user_id='teacher-1', lms_instance=instance)]
    assert recognised(A) == [account['id']] and recognised(B) == []  # the 15 November rule, with no lock
    lock(db, ORG_A, [B])
    assert send(A) == 403 and send(B) == 303
    assert recognised(A) == []


def test_a_locked_organization_refuses_a_creator_code_from_another_lms_before_any_use(db, manager):
    lock(db, ORG_A, [A])
    code = onboarding.create_code(db, ORG_A)['code']
    refused = onboarding.redeem(db, manager, ticket(instance=B), code)
    assert refused.reason == 'not_allowed'
    assert db.count('Creator_users') == 0 and onboarding.list_codes(db, ORG_A)[0]['use_count'] == 0
    assert onboarding.redeem(db, manager, ticket(), code).ok


def test_a_suspended_organization_is_refused_and_a_trial_one_is_not(db):
    for status, allowed in (('suspended', False), ('trial', True), ('active', True), (None, True)):
        organization = {'id': ORG_A, 'status': status, 'config': {}}
        if allowed:
            assert access.require_organization(db, organization, A) == A
        else:
            with pytest.raises(ValueError, match='suspended'):
                access.require_organization(db, organization, A)


# -- the system whitelist ---------------------------------------------------------------

def test_the_whitelist_is_off_until_enabled_then_applies_to_every_lti_11_entry(client, db, monkeypatch):
    existing_activity(db, monkeypatch)
    send = legacy_student_client(db, monkeypatch, ORG_A)
    whitelist(db, [A], enabled=False)
    assert student(client, B).status_code == 200
    whitelist(db, [A])
    assert student(client, A).status_code == 200 and send(A) == 303
    refused = student(client, B)
    assert refused.status_code == 403 and 'not allowed by the LAMB administrator' in refused.text
    assert send(B) == 403
    whitelist(db, [])  # enabled and empty: the administrator closed LTI 1.1
    assert student(client, A).status_code == 403
    # The whitelist and the lock both apply; an organization cannot widen the whitelist.
    whitelist(db, [A])
    lock(db, ORG_A, [A, B])
    assert student(client, B).status_code == 403


def test_signed_launch_and_headers_cannot_bypass_the_whitelist(client, db, monkeypatch):
    from lamb.lti_activity_manager import LtiActivityManager
    real = SimpleNamespace(get_lti_credentials=lambda: ('key', 'secret'),
        _compute_oauth_signature=LtiActivityManager._compute_oauth_signature)
    monkeypatch.setattr(lti_router.manager, 'validate_oauth_signature',
        lambda *a, **k: LtiActivityManager.validate_oauth_signature(real, *a, **k))
    whitelist(db, [A])
    def signed(instance):
        data = {'oauth_consumer_key': 'key', 'resource_link_id': 'r1', 'roles': 'Instructor',
            'user_id': 'teacher-1', 'tool_consumer_instance_guid': instance}
        data['oauth_signature'] = LtiActivityManager._compute_oauth_signature(
            data, 'POST', 'http://testserver/lamb/v1/lti/launch', 'secret')
        return data
    assert client.post('/lamb/v1/lti/launch', data=signed(B), headers={'Origin': A, 'Referer': A}).status_code == 403
    good = client.post('/lamb/v1/lti/launch', data=signed(A))
    assert good.status_code == 200 and 'Creator code' in good.text
    altered = signed(B)
    altered['tool_consumer_instance_guid'] = A
    assert client.post('/lamb/v1/lti/launch', data=altered).status_code == 401
    assert db.count('Creator_users') == 0


def test_lti_13_is_governed_by_its_registration_not_by_the_whitelist_or_the_lock(env):
    from lamb.lti13 import protocol
    env.db.get_organization_by_slug = lambda _: {'id': 0, 'config': {'lti_access': {'whitelist_enabled': True, 'allowed_instances': []}}}
    env.db.get_organization_by_id = lambda oid: {'id': oid, 'config': {'lti_access': {'locked_instances': [B]}}} if oid in (1, 2) else None
    context = protocol.validate_launch(launch13(env), env.store)
    access.require_organization(env.db, env.db.get_organization_by_id(1), context['lms_instance'])
    with pytest.raises(ValueError, match='not allowed for this LMS registration'):
        access.require_organization(env.db, env.db.get_organization_by_id(2), context['lms_instance'])
    assert access.organization_allowed(env.db, 1, context['lms_instance']) and not access.organization_allowed(env.db, 2, context['lms_instance'])
    # The same installation on LTI 1.1 is under the whitelist and the lock.
    assert not access.organization_allowed(env.db, 1, 'platform.example')


# -- records of the 17 and 18 November dev builds ------------------------------------------

def test_identifiers_stored_as_urls_by_the_earlier_dev_builds_still_match(db, manager):
    assert access.same_instance('https://' + A, A) and access.same_instance(A, 'https://' + A.upper())
    assert access.same_instance('', '') and not access.same_instance('', A) and not access.same_instance(A, B)
    assert not access.same_instance('https://', '')
    old, new = activity_access.launch_scope(db, 'r1', 'https://' + A)[1], activity_access.launch_scope(db, 'r1', A)[1]
    assert new == '["1.1", "%s"]' % A and activity_access.same_scope(old, new)
    assert not activity_access.same_scope(new, activity_access.launch_scope(db, 'r1', B)[1])
    assert activity_access.launch_scope(db, 'r1', '') == ('', '')
    # An account obtained on the earlier build, and a session it issued, are still the same person.
    code = onboarding.create_code(db, ORG_A)['code']
    account = onboarding.redeem(db, manager, ticket(instance='https://' + A), code).creator_user
    for instance in (A, 'https://' + A):
        assert [a['id'] for a in manager.identify_instructor(lms_user_id='teacher-1', lms_instance=instance)] == [account['id']]
    lock(db, ORG_A, [A])
    assert access.organization_allowed(db, ORG_A, 'https://' + A)


# -- the system organization --------------------------------------------------------------

def test_the_system_organization_may_have_creator_codes_and_their_accounts_are_plain_users(db, manager):
    code = onboarding.create_code(db, SYSTEM)['code']
    result = onboarding.redeem(db, manager, ticket(), code)
    assert result.ok and result.creator_user['organization_id'] == SYSTEM
    account = db.get_creator_user_by_id(result.creator_user['id'])
    assert (account['role'], account['auth_provider'], account['user_type']) == ('user', 'lti_creator', 'creator')
    assert [a['organization_id'] for a in manager.identify_instructor(lms_user_id='teacher-1', lms_instance=A)] == [SYSTEM]
    # Only a code opens it: the organization LTI Creator tool still cannot create accounts there.
    assert db.create_lti_creator_user(SYSTEM, 'teacher-9', 'nine@lamb-lti.local', 'Nine') is None


# -- onboarding tickets are used once -----------------------------------------------------

def test_launch_ticket_cannot_create_second_organization_account(db, manager):
    codes = [onboarding.create_code(db, org)['code'] for org in (ORG_A, ORG_B)]
    claims = ticket()
    assert onboarding.redeem(db, manager, claims, codes[0]).ok
    assert onboarding.redeem(db, manager, claims, codes[1]).reason == 'replayed'
    assert db.count('Creator_users') == db.count('lti_creator_code_redemptions') == 1
    assert onboarding.list_codes(db, ORG_B)[0]['use_count'] == 0
    assert onboarding.creator_access(db, manager, launch_claims(instance='other.example')) == []
    # A fresh launch can still join a second organization.
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


# -- what the administrators see and may save ----------------------------------------------

@pytest.fixture
def settings(db, monkeypatch):
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
    return SimpleNamespace(client=TestClient(app), context=context, path='/admin/org-admin/settings/lti-access')


def lti_session(instance, user='teacher-1'):
    return {'lti_identity': {'lms_user_id': user, 'lms_instance': instance}}


def test_an_organization_admin_locks_to_the_lms_they_came_from_and_cannot_lock_themselves_out(db, manager, settings):
    client, context, path = settings.client, settings.context, settings.path
    # A password session has no LMS to offer, and nothing has launched yet.
    assert client.get(path).json() == {'locked_instances': [], 'my_instance': '', 'seen_instances': [], 'can_type': False,
                                       'whitelist_enabled': False, 'allowed_instances': []}
    assert client.put(path, json={'locked_instances': [A]}).status_code == 400  # not typed by an organization admin
    context.token_payload = lti_session(A)
    assert client.get(path).json()['my_instance'] == A
    assert client.put(path, json={'locked_instances': [B]}).status_code == 400
    saved = client.put(path, json={'locked_instances': [A]})
    assert saved.status_code == 200 and saved.json()['locked_instances'] == [A]
    assert access.organization_allowed(db, ORG_A, A) and not access.organization_allowed(db, ORG_A, B)
    # An installation already used with the organization may be added; one's own may not be dropped.
    lock(db, ORG_A, [])
    assert onboarding.redeem(db, manager, ticket(user='teacher-2', instance=B), onboarding.create_code(db, ORG_A)['code']).ok
    assert client.get(path).json()['seen_instances'] == [B]
    refused = client.put(path, json={'locked_instances': [B]})
    assert refused.status_code == 400 and 'lock yourself out' in refused.json()['detail']
    assert client.put(path, json={'locked_instances': [A, B]}).json()['locked_instances'] == [A, B]
    assert client.put(path, json={'locked_instances': []}).json()['locked_instances'] == []
    assert client.put(path + '?org=beta', json={'locked_instances': [A]}).status_code == 403
    # Sessions that have no LTI 1.1 installation to offer: LTI 1.3, and the earlier dev build.
    from lamb.lti13 import PREFIX
    for payload in (lti_session(A, user=PREFIX + 'x'), lti_session(PREFIX + 'i_handle'), lti_session('https://' + A), {}, {'lti_identity': 'x'}):
        assert access.session_instance(payload) == ''


def test_the_system_admin_sets_the_whitelist_and_may_type_what_no_launch_has_shown(db, settings):
    client, context, path = settings.client, settings.context, settings.path
    policy = {'whitelist_enabled': True, 'allowed_instances': [A]}
    assert client.put('/admin/lti-access', json=policy).status_code == 403
    assert client.get('/admin/lti-access').status_code == 403
    context.is_system_admin = True
    assert client.put('/admin/lti-access', json=policy).json() == {**policy, 'seen_instances': []}
    assert client.get('/admin/lti-access').json() == {**policy, 'seen_instances': []}
    for bad in ({'whitelist_enabled': 'yes'}, {'allowed_instances': ['']}, {'allowed_instances': ['a\nb']}, {'allowed_instances': ['x' * 256]}):
        assert client.put('/admin/lti-access', json=bad).status_code in (400, 422)
    typed = client.put(path + '?org=beta', json={'locked_instances': ['campus virtual']})
    assert typed.status_code == 200 and typed.json()['can_type'] is True
    assert access.locked_instances(db.get_organization_by_id(ORG_B)) == ['campus virtual']
    # The system organization keeps its whitelist when it is locked too, and other settings survive.
    before = db.get_organization_by_id(ORG_B)['config']['features']
    lock(db, SYSTEM, [A])
    lock(db, ORG_B, [])
    assert access.global_settings(db) == policy and access.locked_instances(db.get_organization_by_slug('lamb')) == [A]
    assert db.get_organization_by_id(ORG_B)['config']['features'] == before
