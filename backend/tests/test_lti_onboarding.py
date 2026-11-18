"""Creator codes (#467, #562): an instructor with no LAMB account becomes a creator in one
organization, and only from the page of a verified instructor launch."""
import json
import logging
import sqlite3
import time
from types import SimpleNamespace

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lamb import auth as lamb_auth
from lamb import lti_onboarding as onboarding
from lamb import lti_router
from lamb.database_manager import LambDatabaseManager
from lamb.lti13.store import Store, migrate as migrate_lti13
from lamb.lti_activity_manager import LtiActivityManager

ORG_A, ORG_B, SYSTEM = 2, 3, 1


class FakeDb:
    """The handful of LambDatabaseManager calls the feature uses, on a real SQLite file."""
    table_prefix = 'T_'

    def __init__(self, path):
        self.db_path = str(path)
        with self.get_connection() as c:
            c.execute('CREATE TABLE T_organizations (id INTEGER PRIMARY KEY, slug TEXT, name TEXT, is_system INTEGER, config TEXT)')
            c.executemany('INSERT INTO T_organizations VALUES (?,?,?,?,?)', [
                (SYSTEM, 'lamb', 'System', 1, '{}'), (ORG_A, 'alpha', 'Alpha University', 0, '{}'),
                (ORG_B, 'beta', 'Beta College', 0, json.dumps({'features': {'signup_enabled': True, 'signup_key': 'beta-signup-key'}}))])
            c.execute('''CREATE TABLE T_Creator_users (id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER,
                user_email TEXT UNIQUE, user_name TEXT, user_type TEXT, lti_user_id TEXT, auth_provider TEXT,
                enabled INTEGER, role TEXT)''')
            c.execute('CREATE TABLE T_lti_identity_links (id INTEGER PRIMARY KEY AUTOINCREMENT, lms_user_id TEXT, lms_email TEXT, creator_user_id INTEGER)')
            migrate_lti13(c.cursor(), 'T_')
            onboarding.migrate(c.cursor(), 'T_')
            onboarding.migrate(c.cursor(), 'T_')  # idempotent

    def get_connection(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def _one(self, sql, params=()):
        c = self.get_connection()
        try:
            c.row_factory = sqlite3.Row
            row = c.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            c.close()

    def _organization(self, row):
        return None if not row else {**row, 'is_system': bool(row['is_system']), 'config': json.loads(row['config'] or '{}')}

    def get_organization_by_id(self, organization_id):
        return self._organization(self._one('SELECT * FROM T_organizations WHERE id=?', (organization_id,)))

    def get_organization_by_slug(self, slug):
        return self._organization(self._one('SELECT * FROM T_organizations WHERE slug=?', (slug,)))

    def update_organization_config(self, organization_id, config):
        with self.get_connection() as c:
            return c.execute('UPDATE T_organizations SET config=? WHERE id=?', (json.dumps(config), organization_id)).rowcount == 1

    def get_creator_user_by_id(self, user_id):
        return self._one('SELECT * FROM T_Creator_users WHERE id=?', (user_id,))

    def get_creator_user_by_lti(self, organization_id, lti_user_id):
        row = self._one('SELECT * FROM T_Creator_users WHERE organization_id=? AND lti_user_id=?', (organization_id, lti_user_id))
        return None if not row else {**row, 'email': row['user_email'], 'name': row['user_name'], 'enabled': bool(row['enabled'])}

    def create_lti_creator_user(self, organization_id, lti_user_id, user_email, user_name, allow_system=False):
        if self.get_organization_by_id(organization_id)['is_system'] and not allow_system:
            return None
        with self.get_connection() as c:
            return c.execute('''INSERT INTO T_Creator_users (organization_id, user_email, user_name, user_type, lti_user_id,
                auth_provider, enabled, role) VALUES (?,?,?,'creator',?,'lti_creator',1,'user')''',
                (organization_id, user_email, user_name, lti_user_id)).lastrowid

    def create_lti_identity_link(self, lms_user_id, creator_user_id, lms_email=None):
        with self.get_connection() as c:
            return c.execute('INSERT INTO T_lti_identity_links (lms_user_id, lms_email, creator_user_id) VALUES (?,?,?)',
                             (lms_user_id, lms_email, creator_user_id)).lastrowid

    # The real lookup of LTI creator accounts, run on this database.
    get_lti_creator_users_by_lms_user = LambDatabaseManager.get_lti_creator_users_by_lms_user

    def get_lti_activity_by_resource_link(self, resource_link_id):
        return None  # every activity in these tests is unconfigured

    def count(self, table):
        return self._one(f'SELECT COUNT(*) AS n FROM T_{table}')['n']


@pytest.fixture
def db(tmp_path):
    return FakeDb(tmp_path / 'lamb.db')


@pytest.fixture
def manager(db):
    # The real identity-link routing of the activity manager, over the test database.
    real = SimpleNamespace(db_manager=db)
    return SimpleNamespace(link_identity=lambda **kw: LtiActivityManager.link_identity(real, **kw),
                           identify_instructor=lambda **kw: LtiActivityManager.identify_instructor(real, **kw))


INSTANCE = 'moodle.school.example'


def ticket(user='teacher-1', protocol='1.1', resource='rl-1', email='teacher@school.example', instance=INSTANCE, **changes):
    token = onboarding.issue_ticket(lms_user_id=user, lms_email=email, display_name='Ana Teacher', resource_link_id=resource,
                                    context_id='course-1', context_title='Databases', protocol=protocol,
                                    lms_instance='' if protocol == '1.3' else instance)
    data = onboarding.read_ticket(token)
    assert data is not None
    data.update(changes)
    return data


def test_a_code_is_shown_once_stored_as_a_hash_and_belongs_to_one_organization(db):
    created = onboarding.create_code(db, ORG_A, label='Autumn term', max_uses=30, created_by=7)
    code = created['code']
    assert len(onboarding.normalize(code)) == onboarding.CODE_LENGTH and created['hint'] == code[-4:]
    stored = db._one('SELECT * FROM T_lti_creator_codes WHERE id=?', (created['id'],))
    assert code not in json.dumps(stored) and onboarding.normalize(code) not in json.dumps(stored)
    listed = onboarding.list_codes(db, ORG_A)
    assert [c['id'] for c in listed] == [created['id']] and 'code' not in listed[0] and listed[0]['status'] == 'active'
    assert onboarding.list_codes(db, ORG_B) == []
    # Another organization's admin cannot switch it off or on.
    assert onboarding.set_enabled(db, ORG_B, created['id'], False) is None
    assert onboarding.list_codes(db, ORG_A)[0]['enabled'] is True
    assert onboarding.set_enabled(db, ORG_A, created['id'], False)['status'] == 'disabled'
    assert onboarding.set_enabled(db, ORG_A, created['id'], True)['status'] == 'active'


def test_codes_refuse_an_unknown_organization_and_nonsense_limits(db):
    # The system organization is not among them since 18 November 2026: see test_lti_access.
    for arguments in ({'organization_id': 99}, {'organization_id': ORG_A, 'max_uses': 0},
                      {'organization_id': ORG_A, 'expires_at': int(time.time()) - 1}):
        with pytest.raises(ValueError):
            onboarding.create_code(db, **arguments)
    assert db.count('lti_creator_codes') == 0


def test_an_instructor_with_a_valid_code_becomes_a_creator_in_that_organization_only(db, manager):
    code = onboarding.create_code(db, ORG_A)['code']
    result = onboarding.redeem(db, manager, ticket(), code.lower().replace('-', ' '))  # typed without care
    assert result.ok and result.creator_user['organization_id'] == ORG_A
    user = db.get_creator_user_by_id(result.creator_user['id'])
    assert (user['user_type'], user['role'], user['auth_provider'], user['enabled']) == ('creator', 'user', 'lti_creator', 1)
    assert user['user_name'] == 'Ana Teacher' and user['user_email'] == 'lti_creator_alpha_teacher-1@lamb-lti.local'
    assert db._one('SELECT * FROM T_lti_identity_links')['creator_user_id'] == user['id']
    assert db._one('SELECT COUNT(*) AS n FROM T_Creator_users WHERE organization_id!=?', (ORG_A,))['n'] == 0
    assert onboarding.list_codes(db, ORG_A)[0]['use_count'] == 1 and db.count('lti_creator_code_redemptions') == 1
    # The same person entering the code of the organization again is told she is already in it: no second
    # account, no second use.
    again = onboarding.redeem(db, manager, ticket(), code)
    assert again.reason == 'already_member' and 'already have an account' in again.message
    assert db.count('Creator_users') == 1 and onboarding.list_codes(db, ORG_A)[0]['use_count'] == 1


def test_wrong_disabled_expired_and_used_up_codes_say_so_and_create_nothing(db, manager, caplog):
    disabled = onboarding.create_code(db, ORG_A, label='disabled')
    onboarding.set_enabled(db, ORG_A, disabled['id'], False)
    expired = onboarding.create_code(db, ORG_A, label='expired', expires_at=int(time.time()) + 60)
    with db.get_connection() as c:
        c.execute('UPDATE T_lti_creator_codes SET expires_at=? WHERE id=?', (int(time.time()) - 5, expired['id']))
    used = onboarding.create_code(db, ORG_A, label='used', max_uses=1)
    assert onboarding.redeem(db, manager, ticket('first'), used['code']).ok
    with caplog.at_level(logging.DEBUG):
        outcomes = {name: onboarding.redeem(db, manager, ticket(name), code) for name, code in (
            ('invalid', 'AAAA-BBBB-CCCC'), ('disabled', disabled['code']), ('expired', expired['code']), ('used_up', used['code']))}
    assert {name: r.reason for name, r in outcomes.items()} == {n: n for n in outcomes}
    assert len({r.message for r in outcomes.values()}) == 4 and not any(r.ok for r in outcomes.values())
    assert outcomes['invalid'].organization is None and outcomes['disabled'].organization['id'] == ORG_A
    assert db.count('Creator_users') == 1 and db.count('lti_identity_links') == 1
    # Attempts are recorded and logged, never with the code itself.
    assert db._one("SELECT count(*) AS n FROM T_lti_onboarding_attempts WHERE outcome != 'claimed'")['n'] == 5
    logged = caplog.text + json.dumps([list(r) for r in sqlite3.connect(db.db_path).execute('SELECT * FROM T_lti_onboarding_attempts')])
    for secret in ('AAAA-BBBB-CCCC', disabled['code'], expired['code'], used['code']):
        assert secret not in logged and onboarding.normalize(secret) not in logged


def test_the_last_use_of_a_code_goes_to_one_instructor_only(db, manager):
    code = onboarding.create_code(db, ORG_A, max_uses=1)['code']
    results = [onboarding.redeem(db, manager, ticket(f'teacher-{n}'), code) for n in range(3)]
    assert [r.ok for r in results] == [True, False, False] and results[1].reason == 'used_up'
    assert db.count('Creator_users') == 1 and onboarding.list_codes(db, ORG_A)[0]['use_count'] == 1


def test_attempts_are_limited_per_launch_identity(db, manager):
    code = onboarding.create_code(db, ORG_A)['code']
    for _ in range(onboarding.MAX_FAILED_ATTEMPTS):
        assert onboarding.redeem(db, manager, ticket('guesser'), 'ZZZZ-ZZZZ-ZZZZ').reason == 'invalid'
    blocked = onboarding.redeem(db, manager, ticket('guesser'), code)  # even the right code, even a new launch
    assert blocked.reason == 'rate_limited' and db.count('Creator_users') == 0
    assert onboarding.redeem(db, manager, ticket('someone-else'), code).ok  # another instructor is not affected


def test_only_the_ticket_of_an_instructor_launch_is_a_ticket(db):
    good = onboarding.issue_ticket(lms_user_id='t', lms_email='', display_name='T', resource_link_id='rl', protocol='1.1')
    assert onboarding.read_ticket(good)['lti_instructor'] is True
    claims = {k: v for k, v in lamb_auth.decode_token(good).items() if k not in ('exp', 'iat')}

    def signed(payload, seconds=600):  # signed with LAMB's own key: only the claims are wrong
        return jwt.encode({**payload, 'exp': int(time.time()) + seconds}, lamb_auth._get_jwt_secret(), algorithm='HS256')
    assert onboarding.read_ticket(signed(claims)) is not None
    refused = [
        '', 'not-a-token', good[:-2] + 'xx',
        signed({**claims, 'lti_type': 'setup'}), signed({**claims, 'lti_type': 'dashboard'}),
        signed({**claims, 'lti_instructor': False}), signed({**claims, 'lti_instructor': 'true'}),
        signed({k: v for k, v in claims.items() if k != 'lti_launch_id'}),
        signed({**claims, 'lti_protocol': '2.0'}),
        signed({**claims, 'lti_protocol': '1.3'}),                 # a 1.1 identity claiming 1.3
        signed({**claims, 'lti_lms_user_id': 'lti13_u_abc'}),       # a scoped identity claiming 1.1
        signed(claims, seconds=-5),
        signed({'sub': '1', 'email': 'admin@example.edu', 'role': 'admin'}),  # a Creator session
    ]
    assert [onboarding.read_ticket(token) for token in refused] == [None] * len(refused)
    # And the ticket is no Creator session.
    assert not lamb_auth.is_creator_session(lamb_auth.decode_token(good))


def test_the_signup_key_of_an_organization_is_never_a_creator_code(db, manager):
    assert onboarding.redeem(db, manager, ticket(), 'beta-signup-key').reason == 'invalid'
    assert db.count('Creator_users') == 0


def test_a_disabled_account_is_not_revived_by_a_code(db, manager):
    code = onboarding.create_code(db, ORG_A)['code']
    assert onboarding.redeem(db, manager, ticket(), code).ok
    with db.get_connection() as c:
        c.execute('UPDATE T_Creator_users SET enabled=0')
    result = onboarding.redeem(db, manager, ticket(), code)
    assert result.reason == 'account_disabled' and onboarding.list_codes(db, ORG_A)[0]['use_count'] == 1


@pytest.fixture
def lti13(db, monkeypatch):
    # Tokens that carry an LTI 1.3 identity are stamped with their registration from the default store.
    monkeypatch.setattr('lamb.database_manager.LambDatabaseManager', lambda: db)
    store = Store(db)
    rid = store.save_registration(dict(
        name='Moodle', issuer='https://moodle.example', client_id='client-1', authorization_url='https://moodle.example/auth',
        token_url='https://moodle.example/token', jwks_url='https://moodle.example/jwks', deployment_ids=['d1'],
        organization_ids=[ORG_A], service_origins=['https://moodle.example'], enabled=True))
    return SimpleNamespace(store=store, rid=rid, user=store.object_id(rid, 'd1', 'user', 'subject-1'),
                           resource=store.object_id(rid, 'd1', 'resource', 'resource-1'))


def test_on_lti13_the_code_must_belong_to_an_organization_of_the_registration(db, manager, lti13):
    code_a, code_b = onboarding.create_code(db, ORG_A)['code'], onboarding.create_code(db, ORG_B)['code']
    refused = onboarding.redeem(db, manager, ticket(lti13.user, '1.3', lti13.resource), code_b)
    assert refused.reason == 'not_allowed' and db.count('Creator_users') == 0 and db.count('lti13_identity_links') == 0
    assert onboarding.list_codes(db, ORG_B)[0]['use_count'] == 0
    accepted = onboarding.redeem(db, manager, ticket(lti13.user, '1.3', lti13.resource), code_a)
    assert accepted.ok and accepted.creator_user['organization_id'] == ORG_A
    assert [c['id'] for c in lti13.store.creators(lti13.user)] == [accepted.creator_user['id']]  # next launch needs no code
    # The LTI 1.3 identity is scoped to its registration, so the Creator entry needs no instance name.
    assert [a['creator_user_id'] for a in onboarding.creator_access(db, manager, launch_claims(lti13.user, instance=''))] == [accepted.creator_user['id']]
    # ... and no email: whatever the LMS shares about the person, it is the same person.
    assert [a['creator_user_id'] for a in onboarding.creator_access(db, manager, launch_claims(lti13.user, instance='', email='other@school.example'))] == [accepted.creator_user['id']]
    # An LTI creator account whose link to the LMS identity went missing is linked again by the code, with no new use.
    with db.get_connection() as c:
        c.execute('DELETE FROM T_lti13_identity_links')
    relinked = onboarding.redeem(db, manager, ticket(lti13.user, '1.3', lti13.resource), code_a)
    assert relinked.ok and relinked.creator_user['id'] == accepted.creator_user['id'] and db.count('Creator_users') == 1
    assert onboarding.list_codes(db, ORG_A)[0]['use_count'] == 1 and len(lti13.store.creators(lti13.user)) == 1
    # On LTI 1.1 the code alone picks the organization: the same code B lands in B and nowhere else.
    landed = onboarding.redeem(db, manager, ticket('teacher-11'), code_b)
    assert landed.ok and landed.creator_user['organization_id'] == ORG_B


def test_the_page_text_is_the_organizations_then_the_deployments_then_the_default(db):
    assert onboarding.page_text(db, [ORG_A]) == onboarding.DEFAULT_PAGE_TEXT == onboarding.page_text(db)
    onboarding.set_page_text(db, db.get_organization_by_id(SYSTEM), 'Deployment policy')
    assert onboarding.page_text(db) == 'Deployment policy' == onboarding.page_text(db, [ORG_A])
    onboarding.set_page_text(db, db.get_organization_by_id(ORG_A), '  Alpha policy: write to lamb@alpha.example  ')
    assert onboarding.page_text(db, [ORG_A]) == 'Alpha policy: write to lamb@alpha.example'
    assert onboarding.page_text(db, [ORG_A, ORG_B]) == 'Deployment policy' == onboarding.page_text(db, [ORG_B])
    onboarding.set_page_text(db, db.get_organization_by_id(ORG_A), '')
    assert onboarding.page_text(db, [ORG_A]) == 'Deployment policy'
    assert 'features' in db.get_organization_by_id(ORG_B)['config']  # other settings untouched
    with pytest.raises(ValueError):
        onboarding.set_page_text(db, db.get_organization_by_id(ORG_A), 'x' * (onboarding.PAGE_TEXT_LIMIT + 1))


# ---------------------------------------------------------------------------
# Through the launch route
# ---------------------------------------------------------------------------

@pytest.fixture
def client(db, manager, monkeypatch):
    monkeypatch.setattr(lti_router, 'db_manager', db)
    monkeypatch.setattr(lti_router.manager, 'get_lti_credentials', lambda: ('key', 'secret'))
    monkeypatch.setattr(lti_router.manager, 'validate_oauth_signature', lambda data, *a, **k: data.get('oauth_signature') == 'good')
    monkeypatch.setattr(lti_router.manager, 'identify_instructor', manager.identify_instructor)
    monkeypatch.setattr(lti_router.manager, 'link_identity', manager.link_identity)
    app = FastAPI()
    app.include_router(lti_router.router, prefix='/lamb/v1/lti')
    return TestClient(app, follow_redirects=False)


def launch(client, roles='Instructor', signature='good', **extra):
    return client.post('/lamb/v1/lti/launch', data={
        'oauth_consumer_key': 'key', 'oauth_signature': signature, 'resource_link_id': 'rl-1', 'roles': roles, 'user_id': 'teacher-1',
        'ext_user_username': 'ana', 'lis_person_name_full': 'Ana Teacher', 'lis_person_contact_email_primary': 'ana@school.example',
        'context_id': 'course-1', 'context_title': 'Databases', 'tool_consumer_instance_guid': INSTANCE, **extra})


def ticket_in(page):
    return page.text.split('name="ticket" value="')[1].split('"')[0]


def test_the_launch_of_an_instructor_without_an_account_returns_the_code_page(client, db):
    onboarding.set_page_text(db, db.get_organization_by_id(SYSTEM), 'Ask <lamb@school.example> for a code.')
    page = launch(client)
    assert page.status_code == 200 and 'Creator code' in page.text and 'Unable to Set Up This Activity' not in page.text
    assert 'Ask &lt;lamb@school.example&gt; for a code.' in page.text  # the institution's text, escaped
    assert onboarding.read_ticket(ticket_in(page))['lti_lms_user_id'] == 'teacher-1'
    assert 'link-existing-account' not in page.text  # LTI 1.1 had no linking form and gets none here


def test_a_student_launch_gets_the_waiting_page_and_no_ticket(client, db):
    code = onboarding.create_code(db, ORG_A)['code']
    page = launch(client, roles='Learner', code=code, creator_code=code)
    assert page.status_code == 200 and 'name="ticket"' not in page.text and 'Creator code' not in page.text
    assert db.count('Creator_users') == 0 and db.count('lti_onboarding_attempts') == 0


def test_a_launch_that_fails_verification_writes_nothing_even_with_a_valid_code(client, db):
    code = onboarding.create_code(db, ORG_A)['code']
    for attempt in (dict(signature='forged'), dict(oauth_consumer_key='unknown-consumer')):
        assert launch(client, code=code, creator_code=code, **attempt).status_code == 401
    assert db.count('Creator_users') == 0 and db.count('lti_identity_links') == 0 and db.count('lti_onboarding_attempts') == 0
    assert onboarding.list_codes(db, ORG_A)[0]['use_count'] == 0


def test_a_first_account_goes_on_to_lamb_creator_and_can_come_back_to_the_activity(client, db):
    code = onboarding.create_code(db, ORG_A)['code']
    page = launch(client)
    wrong = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(page), 'code': 'AAAA-AAAA-AAAA'})
    assert wrong.status_code == 400 and 'That code is not valid' in wrong.text and 'name="code"' in wrong.text  # retry possible
    done = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(wrong), 'code': code})
    assert done.status_code == 303 and '/assistants?token=' in done.headers['location'] and '&activity=' in done.headers['location']
    session_token, activity = done.headers['location'].split('token=')[1].split('&activity=')
    creator = db._one('SELECT * FROM T_Creator_users')
    session = lamb_auth.decode_token(session_token)
    assert lamb_auth.is_creator_session(session) and session['sub'] == str(creator['id']) and creator['organization_id'] == ORG_A
    assert session['lti_identity']['lms_user_id'] == 'teacher-1' and session['lti_identity']['lms_instance'] == INSTANCE
    # Back from Creator: the activity is not set up yet, so the way back leads to its setup.
    back = client.get('/lamb/v1/lti/return', params={'token': activity})
    assert back.status_code == 303 and '/m/chat/setup?token=' in back.headers['location']
    setup = lamb_auth.decode_token(back.headers['location'].split('token=')[1])
    assert setup['lti_type'] == 'setup' and setup['lti_creator_user_ids'] == [creator['id']]
    # The four hours count from the launch, not from each hop.
    assert setup['lti_launched_at'] == session['lti_identity']['launched_at'] == lamb_auth.decode_token(activity)['lti_launched_at']
    again = launch(client)
    assert again.status_code == 303 and '/m/chat/setup?token=' in again.headers['location']


def test_the_way_back_is_only_for_its_own_token_and_only_for_four_hours(client, db, monkeypatch):
    code = onboarding.create_code(db, ORG_A)['code']
    done = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(launch(client)), 'code': code})
    activity = done.headers['location'].split('&activity=')[1]
    setup_token = launch(client).headers['location'].split('token=')[1]
    for token in ('', 'garbage', setup_token, done.headers['location'].split('token=')[1].split('&')[0]):
        assert client.get('/lamb/v1/lti/return', params={'token': token}).status_code == 403
    # A configured activity: the way back is the instructor's entry of its module, off the event loop.
    seen = []

    class Module:
        def on_instructor_launch(self, ctx):
            seen.append((ctx.is_instructor, ctx.lms_user_id, ctx.resource_link_id, ctx.launched_at > 0, _thread()))
            from fastapi.responses import RedirectResponse
            return RedirectResponse('https://tool.example/m/chat/dashboard', status_code=303)
    monkeypatch.setattr(db, 'get_lti_activity_by_resource_link', lambda rl: {'id': 7, 'status': 'active', 'activity_type': 'chat', 'resource_link_id': rl})
    monkeypatch.setattr(lti_router, '_get_activity_module', lambda activity: Module())
    back = client.get('/lamb/v1/lti/return', params={'token': activity})
    assert back.status_code == 303 and back.headers['location'].endswith('/m/chat/dashboard')
    assert seen == [(True, 'teacher-1', 'rl-1', True, 'worker thread')]
    # After four hours every hop is closed: back to the LMS.
    monkeypatch.setattr(onboarding, 'ACTIVITY_SESSION_SECONDS', -1)
    assert client.get('/lamb/v1/lti/return', params={'token': activity}).status_code == 403
    assert client.get('/lamb/v1/lti/onboarding', params={'token': setup_token}).status_code == 403
    assert client.post('/lamb/v1/lti/creator-session', json={'token': setup_token, 'creator_user_id': 1}).status_code == 403


def _thread():
    import asyncio
    try:
        asyncio.get_running_loop()
        return 'event loop'
    except RuntimeError:
        return 'worker thread'


def test_a_creator_adds_an_organization_with_a_code_and_comes_back_to_the_choice(client, db):
    first = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(launch(client)), 'code': onboarding.create_code(db, ORG_A)['code']})
    assert '/assistants?token=' in first.headers['location']
    setup_token = launch(client).headers['location'].split('token=')[1]
    page = client.get('/lamb/v1/lti/onboarding', params={'token': setup_token})
    assert page.status_code == 200 and 'Add an organization' in page.text and 'id="back-to-organizations"' in page.text
    assert 'link-existing-account' not in page.text
    # The code of the organization they are already in adds nothing; a code of another one adds it.
    code_b = onboarding.create_code(db, ORG_B)['code']
    added = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(page), 'code': code_b})
    assert added.status_code == 303 and '/m/chat/setup?token=' in added.headers['location'] and added.headers['location'].endswith(f'&org={ORG_B}')
    setup = lamb_auth.decode_token(added.headers['location'].split('token=')[1].split('&org=')[0])
    accounts = {row[0]: row[1] for row in sqlite3.connect(db.db_path).execute('SELECT id, organization_id FROM T_Creator_users')}
    assert sorted(setup['lti_creator_user_ids']) == sorted(accounts) and sorted(accounts.values()) == [ORG_A, ORG_B]
    assert [a['organization_name'] for a in onboarding.creator_access(db, lti_router.manager, setup)] == ['Alpha University', 'Beta College']
    for garbage in ('', 'x', ticket_in(page)):
        assert client.get('/lamb/v1/lti/onboarding', params={'token': garbage}).status_code == 403


def test_never_two_lti_creator_accounts_in_one_organization_and_a_password_account_is_another_matter(db, manager):
    with db.get_connection() as c:  # an account with a password whose address is the one the LMS sends
        c.execute("INSERT INTO T_Creator_users (organization_id,user_email,user_name,user_type,lti_user_id,auth_provider,enabled,role) VALUES (?,?,?,?,?,?,1,'user')",
                  (ORG_A, 'teacher@school.example', 'Regular Ana', 'creator', None, 'password'))
    code_a, code_b = onboarding.create_code(db, ORG_A)['code'], onboarding.create_code(db, ORG_B)['code']
    # The email identifies nobody: that account does not stand in the way, and this is a first account.
    first = onboarding.redeem(db, manager, ticket(), code_a)
    assert first.ok and first.first_account is True and first.creator_user['organization_id'] == ORG_A
    assert db.count('Creator_users') == 2 and onboarding.list_codes(db, ORG_A)[0]['use_count'] == 1
    # The same LMS user again in the same organization: refused, nothing created, no use taken.
    again = onboarding.redeem(db, manager, ticket(email=''), code_a)
    assert again.reason == 'already_member' and db.count('Creator_users') == 2 and onboarding.list_codes(db, ORG_A)[0]['use_count'] == 1
    added = onboarding.redeem(db, manager, ticket(), code_b)   # another organization is fine, and it is not a first account
    assert added.ok and added.first_account is False and added.creator_user['organization_id'] == ORG_B
    assert onboarding.redeem(db, manager, ticket('newcomer', email='new@school.example'), code_b).first_account is True


def test_the_redemption_route_refuses_everything_but_its_own_ticket(client, db):
    code = onboarding.create_code(db, ORG_A)['code']
    setup_token = lti_router._create_setup_jwt([], 'teacher-1', 'ana@school.example', 'rl-1')
    for ticket_value in ('', 'garbage', setup_token, lamb_auth.create_token({'sub': '1', 'email': 'a@example.edu', 'role': 'admin'})):
        response = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_value, 'code': code})
        assert response.status_code == 403
    assert db.count('Creator_users') == 0 and db.count('lti_onboarding_attempts') == 0


def test_too_many_attempts_close_the_form_and_show_the_organizations_text_for_a_closed_code(client, db):
    closed = onboarding.create_code(db, ORG_A)
    onboarding.set_enabled(db, ORG_A, closed['id'], False)
    onboarding.set_page_text(db, db.get_organization_by_id(ORG_A), 'Enrolment closed in June. Write to lamb@alpha.example')
    page = launch(client)
    late = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(page), 'code': closed['code']})
    assert late.status_code == 400 and 'no longer active' in late.text and 'Enrolment closed in June' in late.text
    for _ in range(onboarding.MAX_FAILED_ATTEMPTS):
        last = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(page), 'code': 'AAAA-AAAA-AAAA'})
    assert last.status_code == 429 and 'Too many attempts' in last.text and 'name="code"' not in last.text


def test_on_lti13_the_page_offers_no_account_linking_and_shows_the_organizations_text(db, manager, lti13, monkeypatch):
    monkeypatch.setattr(lti_router, 'db_manager', db)
    monkeypatch.setattr(lti_router.manager, 'identify_instructor', manager.identify_instructor)
    onboarding.set_page_text(db, db.get_organization_by_id(ORG_A), 'Alpha University policy')
    token = onboarding.issue_ticket(lms_user_id=lti13.user, lms_email='ana@school.example', display_name='Ana',
                                    resource_link_id=lti13.resource, protocol='1.3')
    page = lti_router._onboarding_page(SimpleNamespace(), token)
    assert page.status_code == 200 and page.context['page_text'] == 'Alpha University policy'
    # No way to tie an account with a password to the LMS identity (15 November 2026).
    assert 'link_token' not in page.context and b'link-account' not in page.body and b'Sign in' not in page.body


# ---------------------------------------------------------------------------
# The organization admin's API
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_api(db, monkeypatch):
    from fastapi import HTTPException
    from creator_interface import lti_onboarding_router as api
    state = SimpleNamespace(organization_id=ORG_A, system_admin=False)

    async def verify(request, organization_id=None):  # the confinement verify_organization_admin_access applies
        if state.system_admin:
            return {'user_id': 1, 'organization_id': organization_id or SYSTEM}
        if organization_id and organization_id != state.organization_id:
            raise HTTPException(status_code=403, detail='Access denied for this organization')
        return {'user_id': 7, 'organization_id': state.organization_id}
    monkeypatch.setattr(api, 'db_manager', db)
    monkeypatch.setattr(api, 'verify_organization_admin_access', verify)
    app = FastAPI()
    app.include_router(api.router, prefix='/creator/admin')
    return SimpleNamespace(client=TestClient(app), state=state, path='/creator/admin/org-admin/settings/creator-codes')


def test_an_organization_admin_manages_only_the_codes_of_their_own_organization(admin_api, db):
    client, path = admin_api.client, admin_api.path
    theirs = onboarding.create_code(db, ORG_B, label='Beta term')
    created = client.post(path, json={'label': 'Alpha term', 'max_uses': 25}).json()
    assert onboarding.normalize(created['code']) and created['max_uses'] == 25 and created['status'] == 'active'
    listing = client.get(path).json()
    assert [c['label'] for c in listing['codes']] == ['Alpha term'] and listing['codes_available'] is True
    assert created['code'] not in json.dumps(listing) and theirs['hint'] not in json.dumps(listing)
    assert client.put(f"{path}/{created['id']}", json={'enabled': False}).json()['status'] == 'disabled'
    assert client.put(f"{path}/{created['id']}", json={'enabled': True}).json()['status'] == 'active'
    # Another organization's code, by id or by naming the organization: refused, unchanged.
    assert client.put(f"{path}/{theirs['id']}", json={'enabled': False}).status_code == 404
    assert client.get(path, params={'org': 'beta'}).status_code == 403
    assert client.post(path, params={'org': 'beta'}, json={}).status_code == 403
    assert onboarding.list_codes(db, ORG_B)[0]['enabled'] is True and len(onboarding.list_codes(db, ORG_B)) == 1
    assert client.post(path, json={'max_uses': 0}).status_code == 422
    assert client.post(path, json={'expires_at': 5}).status_code == 400


def test_the_page_text_is_set_and_cleared_through_the_api_and_the_system_organization_has_codes_too(admin_api, db):
    client, path = admin_api.client, admin_api.path
    saved = client.put(f'{path}/page-text', json={'page_text': 'Alpha policy'}).json()
    assert saved == {'page_text': 'Alpha policy', 'effective_page_text': 'Alpha policy'}
    assert client.get(path).json()['page_text'] == 'Alpha policy'
    cleared = client.put(f'{path}/page-text', json={'page_text': ''}).json()
    assert cleared == {'page_text': '', 'effective_page_text': onboarding.DEFAULT_PAGE_TEXT}
    assert client.put(f'{path}/page-text', json={'page_text': 'x' * (onboarding.PAGE_TEXT_LIMIT + 1)}).status_code == 422
    admin_api.state.system_admin = True
    system = client.get(path).json()
    # A small installation may have no other organization (Marc, 18 November 2026).
    assert system['codes_available'] is True and system['codes'] == []
    assert client.post(path, json={}).status_code == 200
    assert len(client.get(path).json()['codes']) == 1
    assert client.put(f'{path}/page-text', json={'page_text': 'Deployment policy'}).json()['effective_page_text'] == 'Deployment policy'
    assert onboarding.page_text(db) == 'Deployment policy'
    assert client.post(path, params={'org': 'alpha'}, json={'label': 'by the system admin'}).status_code == 200


# ---------------------------------------------------------------------------
# Entering LAMB Creator from the activity
# ---------------------------------------------------------------------------

def launch_claims(user='teacher-1', email='teacher@school.example', instance=INSTANCE, age=0, kind='setup'):
    return {'lti_type': kind, 'lti_lms_user_id': user, 'lti_lms_email': email, 'lti_lms_instance': instance,
            'iat': int(time.time()) - age}


def test_an_lti_creator_enters_creator_from_the_same_lms_user_and_instance_whatever_the_email_and_a_recent_launch(db, manager):
    code = onboarding.create_code(db, ORG_A)['code']
    account = onboarding.redeem(db, manager, ticket(), code).creator_user
    offered = onboarding.creator_access(db, manager, launch_claims())
    assert offered == [{'creator_user_id': account['id'], 'organization_id': ORG_A,
                        'organization_name': 'Alpha University', 'user_name': 'Ana Teacher'}]
    assert onboarding.creator_access(db, manager, launch_claims(kind='dashboard')) == offered
    # The LMS shares another address, or stops sharing one: the same person, the same account.
    for same in (launch_claims(email='Teacher@School.Example'), launch_claims(email='someone.else@school.example'), launch_claims(email='')):
        assert onboarding.creator_access(db, manager, same) == offered
    # Another LMS instance, another LMS user, or a launch that is not recent: nothing.
    for other in (launch_claims(instance='moodle.other.example'), launch_claims(instance=''), launch_claims(user='teacher-2'),
                  launch_claims(age=onboarding.ACTIVITY_SESSION_SECONDS + 60), launch_claims(age=-120),
                  {k: v for k, v in launch_claims().items() if k != 'iat'}):
        assert onboarding.creator_access(db, manager, other) == []
    with db.get_connection() as c:
        c.execute('UPDATE T_Creator_users SET enabled=0')
    assert onboarding.creator_access(db, manager, launch_claims()) == []


def password_account(db, organization, email, role='user'):
    with db.get_connection() as c:
        return c.execute("INSERT INTO T_Creator_users (organization_id,user_email,user_name,user_type,lti_user_id,auth_provider,enabled,role) VALUES (?,?,?,?,?,?,1,?)",
                         (organization, email, 'With Password', 'creator', None, 'password', role)).lastrowid


def test_accounts_with_a_password_take_no_part_and_lti_creators_of_the_older_tool_do(db, manager):
    # An administrator of the system organization and a creator of Alpha, both with the address the LMS sends.
    password_account(db, SYSTEM, 'teacher@school.example', role='admin')
    linked = password_account(db, ORG_A, 'linked@alpha.example')
    with db.get_connection() as c:
        # A link made earlier by signing in during a launch: it grants nothing any more.
        c.execute('INSERT INTO T_lti_identity_links (lms_user_id, lms_email, creator_user_id) VALUES (?,?,?)', ('teacher-1', 'teacher@school.example', linked))
        # An LTI creator made by the organization's own LTI Creator tool, recognised by the LMS user id as that tool does.
        older = c.execute("INSERT INTO T_Creator_users (organization_id,user_email,user_name,user_type,lti_user_id,auth_provider,enabled,role) VALUES (?,?,?,?,?,?,1,'user')",
                          (ORG_B, 'lti_creator_beta_teacher-1@lamb-lti.local', 'Ana of the older tool', 'creator', 'teacher-1', 'lti_creator')).lastrowid
    identified = manager.identify_instructor(lms_user_id='teacher-1', lms_instance=INSTANCE)
    assert [(a['id'], a['organization_id']) for a in identified] == [(older, ORG_B)]   # neither password account, so no system organization
    offered = onboarding.creator_access(db, manager, launch_claims())
    assert [(a['creator_user_id'], a['organization_name']) for a in offered] == [(older, 'Beta College')]   # he is in (Marc, 14 November 2026)
    assert onboarding.creator_access(db, manager, launch_claims(instance='elsewhere', email='x@y.example'))[0]['creator_user_id'] == older
    for row in sqlite3.connect(db.db_path).execute('SELECT id FROM T_Creator_users WHERE auth_provider != ?', ('lti_creator',)).fetchall():
        assert onboarding.creator_session(db, manager, launch_claims(), row[0]) is None
    # The email alone identifies nobody at all.
    assert manager.identify_instructor(lms_user_id='somebody-else', lms_instance=INSTANCE) == []


def test_a_creator_in_two_organizations_chooses_and_gets_a_creator_session_for_that_account_only(db, manager):
    first = onboarding.redeem(db, manager, ticket(), onboarding.create_code(db, ORG_B)['code']).creator_user
    second = onboarding.redeem(db, manager, ticket(), onboarding.create_code(db, ORG_A)['code']).creator_user
    offered = onboarding.creator_access(db, manager, launch_claims())
    assert [a['organization_name'] for a in offered] == ['Alpha University', 'Beta College']
    assert {a['creator_user_id'] for a in offered} == {first['id'], second['id']}
    session = lamb_auth.decode_token(onboarding.creator_session(db, manager, launch_claims(), second['id']))
    assert lamb_auth.is_creator_session(session) and session['sub'] == str(second['id']) and session['role'] == 'user'
    assert session['email'] == 'lti_creator_alpha_teacher-1@lamb-lti.local'
    assert onboarding.creator_session(db, manager, launch_claims(), 9999) is None
    assert onboarding.creator_session(db, manager, launch_claims(age=onboarding.ACTIVITY_SESSION_SECONDS + 5), second['id']) is None
    # Inside LAMB Creator the session remembers the launch: the same accounts can be switched to, for the same four hours.
    remembered = onboarding.session_identity(session)
    assert [a['creator_user_id'] for a in onboarding.creator_access(db, manager, remembered)] == [a['creator_user_id'] for a in offered]
    switched = lamb_auth.decode_token(onboarding.creator_session(db, manager, remembered, first['id']))
    assert switched['sub'] == str(first['id']) and switched['lti_identity'] == session['lti_identity']
    assert onboarding.session_identity({'sub': '1', 'email': 'a@example.edu', 'role': 'user'}) == {}   # a session that did not come from the LMS
    assert onboarding.creator_access(db, manager, {**remembered, 'lti_launched_at': int(time.time()) - onboarding.ACTIVITY_SESSION_SECONDS - 5}) == []


def test_the_creator_entry_route_takes_the_token_of_the_launch_and_nothing_else(client, db):
    code = onboarding.create_code(db, ORG_A)['code']
    page = launch(client)
    client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(page), 'code': code})
    setup_token = launch(client).headers['location'].split('token=')[1]   # the next launch: straight to the setup
    creator = db._one('SELECT * FROM T_Creator_users')
    claims = lamb_auth.decode_token(setup_token)
    assert claims['lti_lms_instance'] == INSTANCE and claims['lti_launched_at'] > 0
    assert [a['creator_user_id'] for a in onboarding.creator_access(db, lti_router.manager, claims)] == [creator['id']]
    opened = client.post('/lamb/v1/lti/creator-session', json={'token': setup_token, 'creator_user_id': creator['id']})
    assert opened.status_code == 200 and '/assistants?token=' in opened.json()['url'] and '&activity=' in opened.json()['url']
    session = lamb_auth.decode_token(opened.json()['url'].split('token=')[1].split('&activity=')[0])
    assert lamb_auth.is_creator_session(session) and session['sub'] == str(creator['id'])
    assert onboarding.read_return(opened.json()['url'].split('&activity=')[1])['lti_resource_link_id'] == 'rl-1'
    for body in ({'token': setup_token, 'creator_user_id': creator['id'] + 1}, {'token': setup_token}, {'token': setup_token, 'creator_user_id': 'x'},
                 {'token': ticket_in(page), 'creator_user_id': creator['id']}, {'token': 'garbage', 'creator_user_id': creator['id']}, {}):
        assert client.post('/lamb/v1/lti/creator-session', json=body).status_code == 403


# ---------------------------------------------------------------------------
# Who an instructor is in an LTI launch (Marc, 15 November 2026): the LMS user and, on LTI 1.1,
# the LMS instance; never the email; only LTI creator accounts.
# ---------------------------------------------------------------------------

def test_the_same_lms_user_enters_every_one_of_their_organizations_whatever_email_each_launch_carried(db, manager):
    code_a, code_b = onboarding.create_code(db, ORG_A)['code'], onboarding.create_code(db, ORG_B)['code']
    # The first code while the LMS shared no address, the second after it began to share one.
    a = onboarding.redeem(db, manager, ticket(email=''), code_a).creator_user
    b = onboarding.redeem(db, manager, ticket(email='ana@school.example'), code_b).creator_user
    for email in ('', 'ana@school.example', 'another@school.example'):
        offered = onboarding.creator_access(db, manager, launch_claims(email=email))
        assert [x['creator_user_id'] for x in offered] == [a['id'], b['id']]
        assert [x['organization_id'] for x in manager.identify_instructor(lms_user_id='teacher-1', lms_instance=INSTANCE)] == [ORG_A, ORG_B]
    # From inside LAMB Creator, the session of one account reaches the other.
    session = jwt.decode(onboarding.creator_session(db, manager, launch_claims(email=''), a['id']), options={'verify_signature': False})
    switched = onboarding.creator_session(db, manager, onboarding.session_identity(session), b['id'])
    assert jwt.decode(switched, options={'verify_signature': False})['sub'] == str(b['id'])


def test_the_same_user_id_from_another_lms_is_another_person(db, manager):
    code = onboarding.create_code(db, ORG_A, max_uses=5)['code']
    ana = onboarding.redeem(db, manager, ticket(), code).creator_user
    elsewhere = 'moodle.other.example'
    # Not identified, so not listed on the setup page, not the owner of anything, not offered LAMB Creator.
    assert manager.identify_instructor(lms_user_id='teacher-1', lms_instance=elsewhere) == []
    assert onboarding.creator_access(db, manager, launch_claims(instance=elsewhere)) == []
    assert onboarding.creator_session(db, manager, launch_claims(instance=elsewhere), ana['id']) is None
    # The organization's code does not hand Ana's account over to that other person either.
    refused = onboarding.redeem(db, manager, ticket(instance=elsewhere), code)
    assert refused.reason == 'other_lms' and not refused.ok
    assert db.count('Creator_users') == 1 and db.count('lti_identity_links') == 1 and db.count('lti_creator_code_redemptions') == 1
    assert onboarding.list_codes(db, ORG_A)[0]['use_count'] == 1
    assert onboarding.MESSAGES['other_lms'].startswith('An account for this LMS user already exists')
    assert manager.identify_instructor(lms_user_id='teacher-1', lms_instance=elsewhere) == []


def test_an_account_of_the_lti_creator_tool_is_bound_to_an_instance_once_a_code_links_it(db, manager):
    with db.get_connection() as c:
        older = c.execute("INSERT INTO T_Creator_users (organization_id,user_email,user_name,user_type,lti_user_id,auth_provider,enabled,role) VALUES (?,?,?,?,?,?,1,'user')",
                          (ORG_A, 'lti_creator_alpha_teacher-1@lamb-lti.local', 'Ana of the older tool', 'creator', 'teacher-1', 'lti_creator')).lastrowid
    # As that tool recognises it: by the user id, from any instance. A code of its own organization is not needed.
    assert [a['id'] for a in manager.identify_instructor(lms_user_id='teacher-1', lms_instance='anywhere')] == [older]
    assert onboarding.redeem(db, manager, ticket(), onboarding.create_code(db, ORG_A)['code']).reason == 'already_member'


def test_a_launch_whose_email_is_that_of_a_password_account_reaches_the_code_page(client, db):
    password_account(db, SYSTEM, 'ana@school.example', role='admin')
    password_account(db, ORG_A, 'Ana@School.example')
    page = launch(client)                       # the launch says ana@school.example
    assert page.status_code == 200 and 'Creator code' in page.text and 'name="ticket"' in page.text
    assert 'System' not in page.text and 'Alpha University' not in page.text


def test_the_setup_lists_the_same_organizations_whatever_the_lms_says_about_the_email(client, db, manager):
    password_account(db, SYSTEM, 'ana@school.example', role='admin')
    code = onboarding.create_code(db, ORG_A)['code']
    assert onboarding.redeem(db, manager, ticket(email=''), code).ok
    seen = []
    for email in ('ana@school.example', '', 'changed@school.example'):
        response = launch(client, lis_person_contact_email_primary=email)
        assert response.status_code == 303 and '/m/chat/setup?token=' in response.headers['location']
        token = response.headers['location'].split('token=')[1]
        info = client.get('/lamb/v1/lti/setup/info', params={'token': token}).json()
        seen.append((sorted(info['org_names'].values()), [a['organization_id'] for a in info['creator_access']]))
    # Alpha every time, with its way into LAMB Creator; the system organization never.
    assert seen == [(['Alpha University'], [ORG_A])] * 3


def test_no_route_ties_an_account_with_a_password_to_an_lms_identity(client, db, manager, lti13):
    token = lti_router._create_setup_jwt([], 'teacher-1', 'ana@school.example', 'rl-1', lms_instance=INSTANCE)
    assert client.get('/lamb/v1/lti/link-account', params={'token': token}).status_code == 404
    assert client.post('/lamb/v1/lti/link-account', data={'token': token, 'email': 'x@y.example', 'password': 'p'}).status_code in (404, 405)
    assert not hasattr(LtiActivityManager, 'verify_creator_credentials')
    # LTI 1.3: neither the store nor, through it, the system administrator's endpoint links one.
    regular = password_account(db, ORG_A, 'regular@alpha.example')
    with pytest.raises(ValueError, match='Only an LTI creator account'):
        lti13.store.link_creator(lti13.user, regular)
    assert db.count('lti13_identity_links') == 0
    # A link that was made before grants nothing when read.
    with db.get_connection() as c:
        c.execute('INSERT INTO T_lti13_identity_links (user_id, creator_user_id, linked_at) VALUES (?,?,?)', (lti13.user, regular, 1))
    assert lti13.store.creators(lti13.user) == [] and manager.identify_instructor(lms_user_id=lti13.user) == []


def test_the_owner_of_an_activity_is_recognised_by_the_launch_and_not_by_the_email(db, manager):
    code = onboarding.create_code(db, ORG_A)['code']
    ana = onboarding.redeem(db, manager, ticket(), code).creator_user
    owner = SimpleNamespace(db_manager=db, identify_instructor=lambda user, instance='': LtiActivityManager.identify_instructor(owner, user, instance))
    is_owner = lambda activity, user='teacher-1', instance=INSTANCE: LtiActivityManager.determine_is_owner(owner, activity, user, instance)
    hers = {'resource_link_id': 'rl-1', 'organization_id': ORG_A, 'owner_email': ana['user_email']}
    assert is_owner(hers) is True                                    # whatever address the LMS now sends: none is asked
    assert is_owner(hers, instance='moodle.other.example') is False  # the same number in another LMS
    assert is_owner(hers, user='teacher-2') is False
    assert is_owner({**hers, 'organization_id': ORG_B}) is False
    # An activity set up by an account with a password has no owner among LTI launches.
    password_account(db, ORG_A, 'teacher@school.example')
    assert is_owner({'resource_link_id': 'rl-2', 'organization_id': ORG_A, 'owner_email': 'teacher@school.example'}) is False
    assert is_owner({'resource_link_id': 'rl-3', 'organization_id': ORG_A, 'owner_email': ''}) is False
