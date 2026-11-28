"""For LAMB an LMS is one installation on LTI 1.1 and on LTI 1.3 (#579).

When the administrator of an LMS changes the LAMB tool from one version to the other, in
either direction, or uses both at once, every teacher, student and activity is the same one.
Real RSA signatures for LTI 1.3; the LTI 1.1 signature check is replaced, as its own tests
cover it.
"""
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from lamb import activity_access, lti_onboarding as onboarding, lti_router
from lamb.lti13 import CLAIM, grades, network, protocol, store as store_module
from lamb.lti13.keys import KeyRing
from lamb.lti13.store import Store
from lamb.lti_activity_manager import LtiActivityManager
from tests.test_lti13 import launch as launch13
from tests.test_lti_onboarding import FakeDb, ORG_A, ORG_B

SCHOOL, OTHER = 'moodle.school.example', 'moodle.other.example'
TEACHER = next(iter(protocol.INSTRUCTOR_ROLES))


@pytest.fixture
def lms(tmp_path, monkeypatch):
    db = FakeDb(tmp_path / 'lamb.db')
    with db.get_connection() as c:
        c.execute('''CREATE TABLE T_lti_activities (id INTEGER PRIMARY KEY AUTOINCREMENT, resource_link_id TEXT UNIQUE,
            organization_id INTEGER, status TEXT, activity_type TEXT, owner_email TEXT, context_id TEXT, context_title TEXT,
            lis_outcome_service_url TEXT)''')
        activity_access.migrate(c.cursor(), 'T_')
    db.get_lti_activity_by_resource_link = lambda key: db._one('SELECT * FROM T_lti_activities WHERE resource_link_id=?', (key,))
    def update(activity_id, **fields):
        with db.get_connection() as c:
            for name, value in fields.items():
                c.execute(f'UPDATE T_lti_activities SET {name}=? WHERE id=?', (value, activity_id))
    db.update_lti_activity = update
    store = Store(db)

    def register(issuer, organizations=(ORG_A,), **more):
        rid = store.save_registration(dict(
            name=issuer, issuer=issuer, client_id='client-1', authorization_url=issuer + '/auth', token_url=issuer + '/token',
            jwks_url=issuer + '/jwks', deployment_ids=['deployment-1'], organization_ids=list(organizations),
            service_origins=['https://platform.example'], enabled=True, **more))
        return store.registration(rid)

    keys = KeyRing(tmp_path / 'platform-keys')
    monkeypatch.setenv('LAMB_PUBLIC_BASE_URL', 'https://tool.example')
    monkeypatch.setenv('LTI13_KEY_DIR', str(tmp_path / 'tool-keys'))
    protocol._JWKS.clear()
    grades._TOKENS.clear()
    monkeypatch.setattr(network, 'request', lambda method, url, **kw: keys.public())
    monkeypatch.setattr('lamb.database_manager.LambDatabaseManager', lambda: db)
    monkeypatch.setattr(store_module, 'Store', lambda db=None: store)
    monkeypatch.setattr(protocol, 'Store', lambda: store)
    monkeypatch.setattr(lti_router, 'Store', lambda: store)
    monkeypatch.setattr(lti_router, 'db_manager', db)
    monkeypatch.setattr(lti_router.manager, 'db_manager', db)
    monkeypatch.setattr(lti_router.manager, 'get_lti_credentials', lambda: ('lamb', 'secret'))
    monkeypatch.setattr(lti_router.manager, 'validate_oauth_signature', lambda *a: True)
    # The module answers with what the launch handed it.
    seen = lambda ctx: JSONResponse({'activity': ctx.resource_link_id, 'user': ctx.lms_user_id, 'username': ctx.username,
                                     'course': ctx.context_id, 'teacher': ctx.is_instructor, 'version': ctx.lti_version,
                                     'student_email': lti_router.manager.generate_student_email(ctx.username, ctx.resource_link_id)})
    monkeypatch.setattr(lti_router, 'get_module', lambda _: SimpleNamespace(on_instructor_launch=seen, on_student_launch=seen))
    app = FastAPI()
    app.include_router(lti_router.router, prefix='/lamb/v1/lti')
    client = TestClient(app)
    school = register('https://platform.example')
    env = SimpleNamespace(store=store, reg=school, keys=keys)

    def on13(resource, user='42', login='ana', teacher=False, guid=SCHOOL, registration=None):
        changes = {'sub': user, CLAIM + 'resource_link': {'id': resource}, CLAIM + 'context': {'id': '7', 'title': 'Databases'},
                   CLAIM + 'tool_platform': {'guid': guid}, CLAIM + 'ext': {'user_username': login}}
        if teacher:
            changes[CLAIM + 'roles'] = [TEACHER]
        return client.post('/lamb/v1/lti/launch', data=launch13(env, changes, registration=registration), follow_redirects=False)

    def on11(resource, user='42', login='ana', teacher=False, guid=SCHOOL):
        return client.post('/lamb/v1/lti/launch', follow_redirects=False, data={
            'oauth_consumer_key': 'lamb', 'resource_link_id': resource, 'user_id': user, 'ext_user_username': login,
            'roles': 'Instructor' if teacher else 'Learner', 'context_id': '7', 'context_title': 'Databases',
            'tool_consumer_instance_guid': guid, 'lis_outcome_service_url': 'https://platform.example/service'})

    def activity(key, scope='', organization=ORG_A, owner=''):
        with db.get_connection() as c:
            return c.execute('''INSERT INTO T_lti_activities (resource_link_id, organization_id, status, activity_type,
                owner_email, lms_scope) VALUES (?,?,'active','chat',?,?)''', (key, organization, owner, scope)).lastrowid

    return SimpleNamespace(db=db, store=store, client=client, register=register, on13=on13, on11=on11, activity=activity,
                           school=school, scope=lambda key: db.get_lti_activity_by_resource_link(key)['lms_scope'])


def test_an_activity_set_up_on_lti11_is_the_same_activity_on_lti13_and_back(lms):
    lms.activity('57', json.dumps(['1.1', SCHOOL]))
    before = lms.on11('57').json()
    after = lms.on13('57').json()
    back = lms.on11('57').json()
    # The same activity, the same learner, the same course, the same LAMB user in the activity.
    for field in ('activity', 'user', 'username', 'course', 'student_email'):
        assert before[field] == after[field] == back[field], field
    assert (after['activity'], after['user'], after['username'], after['version']) == ('57', '42', 'ana', '1.3.0')
    assert json.loads(lms.scope('57')) == ['1.1', SCHOOL]
    # The same number in another LMS is another activity, on either version.
    stranger = lms.register('https://other.example')
    waiting = lms.on13('57', guid=OTHER, registration=stranger)
    assert waiting.status_code == 200 and 'activity' not in waiting.text[:20] and waiting.headers['content-type'].startswith('text/html')
    assert lms.on11('57', guid=OTHER).status_code == 403  # as before this change: the number is taken by the first LMS


def test_an_activity_set_up_on_lti13_is_the_same_activity_on_lti11(lms):
    # A teacher opens a new activity on LTI 1.3: it gets an opaque key.
    first = lms.on13('90', teacher=True)
    assert first.status_code == 200 and 'Creator code' in first.text
    key = lms.db._one("SELECT id FROM T_lti13_objects WHERE kind='resource' AND external_id='90'")['id']
    lms.activity(key)
    on13 = lms.on13('90').json()
    assert on13['activity'] == key and json.loads(lms.scope(key)) == ['1.3', SCHOOL]
    # The administrator changes the tool back to LTI 1.1.
    on11 = lms.on11('90').json()
    for field in ('activity', 'user', 'username', 'course', 'student_email'):
        assert on11[field] == on13[field], field
    assert on11['version'] == '1.1' and json.loads(lms.scope(key)) == ['1.1', SCHOOL]
    # A second tool of the same LMS (another client, the same issuer) reaches it too.
    with lms.db.get_connection() as c:
        c.execute("UPDATE T_lti13_registrations SET client_id='client-0' WHERE id=?", (lms.school['id'],))
    second = lms.register('https://platform.example')
    assert lms.on13('90', registration=second).json()['activity'] == key
    # The same number from another LMS on LTI 1.1 is not that activity.
    assert 'activity' not in lms.on11('90', guid=OTHER).headers['content-type']
    assert lms.db.count('lti_activities') == 1


def test_an_activity_from_before_installations_were_recorded(lms):
    lms.activity('12')  # set up on LAMB 0.8: no installation on record
    # A platform LAMB has never seen on LTI 1.1 does not take it.
    assert lms.on13('12').headers['content-type'].startswith('text/html')
    assert lms.scope('12') == ''
    # Once the installation has been seen on LTI 1.1 (any activity), its activities are its own.
    lms.activity('13')
    assert lms.on11('13').json()['activity'] == '13'
    assert lms.on13('12').json()['activity'] == '12'
    assert json.loads(lms.scope('12')) == ['1.3', SCHOOL]


def test_the_administrator_declares_the_installation_of_a_platform_never_seen_on_lti11(lms):
    lms.activity('12')
    declared = lms.register('https://moved.example', installation=SCHOOL)
    assert lms.on13('12', guid='', registration=declared).json()['activity'] == '12'


def test_a_teacher_is_the_same_person_on_both_versions(lms):
    def manager():
        real = SimpleNamespace(db_manager=lms.db)
        return SimpleNamespace(link_identity=lambda **kw: LtiActivityManager.link_identity(real, **kw),
                               identify_instructor=lambda **kw: LtiActivityManager.identify_instructor(real, **kw))
    # A teacher got the account with a creator code on LTI 1.1.
    code = onboarding.create_code(lms.db, ORG_A)['code']
    ticket = onboarding.read_ticket(onboarding.issue_ticket(
        lms_user_id='42', lms_email='', display_name='Ana', resource_link_id='57', protocol='1.1', lms_instance=SCHOOL))
    ana = onboarding.redeem(lms.db, manager(), ticket, code).creator_user
    # On LTI 1.3 the same teacher goes to the setup of a new activity, with no code asked.
    setup = lms.on13('91', teacher=True)
    assert setup.status_code == 303 and '/m/chat/setup?token=' in setup.headers['location']
    token = lti_router.lamb_auth.decode_token(setup.headers['location'].split('token=')[1])
    assert token['lti_creator_user_ids'] == [ana['id']] and token['lti13_registration_id'] == lms.school['id']
    # The same user number from another LMS is asked for a code, on either version.
    stranger = lms.register('https://other.example')
    assert 'Creator code' in lms.on13('92', teacher=True, guid=OTHER, registration=stranger).text
    assert 'Creator code' in lms.on11('92', teacher=True, guid=OTHER).text
    # She owns her activity whichever version she comes in on.
    lms.activity('57', json.dumps(['1.1', SCHOOL]), owner=ana['user_email'])
    owner = SimpleNamespace(db_manager=lms.db)
    owner.identify_instructor = lambda user, instance='': LtiActivityManager.identify_instructor(owner, user, instance)
    handle = lms.store.instance_handle(lms.school['id'], 'deployment-1', SCHOOL)
    activity = lms.db.get_lti_activity_by_resource_link('57')
    for instance, hers in ((SCHOOL, True), (handle, True), (OTHER, False)):
        assert LtiActivityManager.determine_is_owner(owner, activity, '42', instance) is hers
    # An account in an organization the registration does not list is not hers through LTI 1.3 ...
    code_b = onboarding.create_code(lms.db, ORG_B)['code']
    ticket = onboarding.read_ticket(onboarding.issue_ticket(
        lms_user_id='42', lms_email='', display_name='Ana', resource_link_id='57', protocol='1.1', lms_instance=SCHOOL))
    in_b = onboarding.redeem(lms.db, manager(), ticket, code_b).creator_user
    identified = lambda instance: sorted(c['id'] for c in LtiActivityManager.identify_instructor(owner, '42', instance))
    assert identified(handle) == [ana['id']]
    # ... and is hers through LTI 1.1, where nothing restricts the installation.
    assert identified(SCHOOL) == sorted([ana['id'], in_b['id']])


def test_an_account_from_the_organizations_creator_tool_is_found_on_lti13(lms):
    legacy = lms.db.create_lti_creator_user(ORG_A, '42', 'lti_creator_alpha_42@lamb-lti.local', 'Ana')
    setup = lms.on13('91', teacher=True)
    assert setup.status_code == 303
    assert lti_router.lamb_auth.decode_token(setup.headers['location'].split('token=')[1])['lti_creator_user_ids'] == [legacy]


def test_a_grade_returns_through_the_service_of_the_learners_latest_launch(lms):
    lms.activity('57', json.dumps(['1.1', SCHOOL]))
    email = lms.on11('57').json()['student_email']
    assert not lms.store.has_grade_endpoint('57', email)          # Basic Outcomes
    lms.on13('57')
    assert lms.store.has_grade_endpoint('57', email)              # the LTI 1.3 grade service
    registration, subject, _ = lms.store.grade_target('57', email)
    assert (registration['id'], subject) == (lms.school['id'], '42')
    assert not lms.store.has_grade_endpoint('57', lms.on11('57', user='43', login='ben').json()['student_email'])
    lms.on11('57')
    assert not lms.store.has_grade_endpoint('57', email)          # Basic Outcomes again
    assert lms.db.get_lti_activity_by_resource_link('57')['lis_outcome_service_url'] == 'https://platform.example/service'


def test_a_platform_cannot_reach_an_organization_its_registration_does_not_list(lms):
    lms.activity('57', json.dumps(['1.1', SCHOOL]), organization=ORG_B)
    refused = lms.on13('57')
    assert refused.status_code == 403 and 'not allowed for this LMS registration' in refused.text
    assert lms.on11('57').status_code == 200   # LTI 1.1 from the same installation: its own rules
