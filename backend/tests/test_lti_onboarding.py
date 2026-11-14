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

    def create_lti_creator_user(self, organization_id, lti_user_id, user_email, user_name):
        if self.get_organization_by_id(organization_id)['is_system']:
            return None
        with self.get_connection() as c:
            return c.execute('''INSERT INTO T_Creator_users (organization_id, user_email, user_name, user_type, lti_user_id,
                auth_provider, enabled, role) VALUES (?,?,?,'creator',?,'lti_creator',1,'user')''',
                (organization_id, user_email, user_name, lti_user_id)).lastrowid

    def create_lti_identity_link(self, lms_user_id, creator_user_id, lms_email=None):
        with self.get_connection() as c:
            return c.execute('INSERT INTO T_lti_identity_links (lms_user_id, lms_email, creator_user_id) VALUES (?,?,?)',
                             (lms_user_id, lms_email, creator_user_id)).lastrowid

    def get_creator_users_by_lms_identity(self, lms_user_id=None, lms_email=None):
        c = self.get_connection()
        try:
            c.row_factory = sqlite3.Row
            rows = c.execute('''SELECT DISTINCT cu.* FROM T_Creator_users cu
                LEFT JOIN T_lti_identity_links l ON l.creator_user_id=cu.id
                WHERE cu.enabled=1 AND ((? IS NOT NULL AND cu.user_email=?) OR cu.lti_user_id=? OR l.lms_user_id=?)''',
                (lms_email, lms_email, lms_user_id, lms_user_id)).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()

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


def test_codes_refuse_the_system_organization_and_nonsense_limits(db):
    for arguments in ({'organization_id': SYSTEM}, {'organization_id': 99}, {'organization_id': ORG_A, 'max_uses': 0},
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
    # The same person arriving again with the code (a link went missing) takes no second use and no second account.
    again = onboarding.redeem(db, manager, ticket(), code)
    assert again.ok and again.creator_user['id'] == user['id']
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
    assert db.count('lti_onboarding_attempts') == 5
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
    assert onboarding.creator_access(db, manager, launch_claims(lti13.user, instance='', email='other@school.example')) == []
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
    monkeypatch.setattr(lti_router.manager, 'identify_instructor', lambda **kw: [
        dict(row, user_email=row['user_email']) for row in ([db._one(
            'SELECT cu.* FROM T_Creator_users cu JOIN T_lti_identity_links l ON l.creator_user_id=cu.id WHERE l.lms_user_id=? AND cu.enabled=1',
            (kw['lms_user_id'],))] if db._one('SELECT 1 FROM T_lti_identity_links WHERE lms_user_id=?', (kw['lms_user_id'],)) else [])])
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


def test_redeeming_through_the_page_continues_to_the_activity_setup_and_the_next_launch_needs_no_code(client, db):
    code = onboarding.create_code(db, ORG_A)['code']
    page = launch(client)
    wrong = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(page), 'code': 'AAAA-AAAA-AAAA'})
    assert wrong.status_code == 400 and 'That code is not valid' in wrong.text and 'name="code"' in wrong.text  # retry possible
    done = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(wrong), 'code': code})
    assert done.status_code == 303 and '/m/chat/setup?token=' in done.headers['location']
    setup = lamb_auth.decode_token(done.headers['location'].split('token=')[1])
    creator = db._one('SELECT * FROM T_Creator_users')
    assert setup['lti_type'] == 'setup' and setup['lti_creator_user_ids'] == [creator['id']] and creator['organization_id'] == ORG_A
    again = launch(client)
    assert again.status_code == 303 and '/m/chat/setup?token=' in again.headers['location']


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


def test_on_lti13_the_page_keeps_the_existing_account_link_and_shows_the_organizations_text(db, lti13, monkeypatch):
    monkeypatch.setattr(lti_router, 'db_manager', db)
    onboarding.set_page_text(db, db.get_organization_by_id(ORG_A), 'Alpha University policy')
    token = onboarding.issue_ticket(lms_user_id=lti13.user, lms_email='ana@school.example', display_name='Ana',
                                    resource_link_id=lti13.resource, protocol='1.3')
    page = lti_router._onboarding_page(SimpleNamespace(), token)
    assert page.status_code == 200 and page.context['page_text'] == 'Alpha University policy'
    link = lamb_auth.decode_token(page.context['link_token'])
    assert link['lti_type'] == 'setup' and link['lti_lms_user_id'] == lti13.user and link['lti_creator_user_ids'] == []


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


def test_the_page_text_is_set_and_cleared_through_the_api_and_the_system_organization_has_no_codes(admin_api, db):
    client, path = admin_api.client, admin_api.path
    saved = client.put(f'{path}/page-text', json={'page_text': 'Alpha policy'}).json()
    assert saved == {'page_text': 'Alpha policy', 'effective_page_text': 'Alpha policy'}
    assert client.get(path).json()['page_text'] == 'Alpha policy'
    cleared = client.put(f'{path}/page-text', json={'page_text': ''}).json()
    assert cleared == {'page_text': '', 'effective_page_text': onboarding.DEFAULT_PAGE_TEXT}
    assert client.put(f'{path}/page-text', json={'page_text': 'x' * (onboarding.PAGE_TEXT_LIMIT + 1)}).status_code == 422
    admin_api.state.system_admin = True
    system = client.get(path).json()
    assert system['codes_available'] is False and system['codes'] == []
    assert client.post(path, json={}).status_code == 400
    assert client.put(f'{path}/page-text', json={'page_text': 'Deployment policy'}).json()['effective_page_text'] == 'Deployment policy'
    assert onboarding.page_text(db) == 'Deployment policy'
    assert client.post(path, params={'org': 'alpha'}, json={'label': 'by the system admin'}).status_code == 200


# ---------------------------------------------------------------------------
# Entering LAMB Creator from the activity
# ---------------------------------------------------------------------------

def launch_claims(user='teacher-1', email='teacher@school.example', instance=INSTANCE, age=0, kind='setup'):
    return {'lti_type': kind, 'lti_lms_user_id': user, 'lti_lms_email': email, 'lti_lms_instance': instance,
            'iat': int(time.time()) - age}


def test_an_lti_creator_may_enter_creator_only_from_the_same_lms_user_and_email_and_a_recent_launch(db, manager):
    code = onboarding.create_code(db, ORG_A)['code']
    account = onboarding.redeem(db, manager, ticket(), code).creator_user
    offered = onboarding.creator_access(db, manager, launch_claims())
    assert offered == [{'creator_user_id': account['id'], 'organization_id': ORG_A,
                        'organization_name': 'Alpha University', 'user_name': 'Ana Teacher'}]
    assert onboarding.creator_access(db, manager, launch_claims(kind='dashboard')) == offered
    assert onboarding.creator_access(db, manager, launch_claims(email='Teacher@School.Example')) == offered  # same address
    for other in (launch_claims(email='someone.else@school.example'), launch_claims(instance='moodle.other.example'),
                  launch_claims(instance=''), launch_claims(user='teacher-2'),
                  launch_claims(age=onboarding.HANDOVER_WINDOW_SECONDS + 60), launch_claims(age=-120),
                  {k: v for k, v in launch_claims().items() if k != 'iat'}):
        assert onboarding.creator_access(db, manager, other) == []
    with db.get_connection() as c:
        c.execute('UPDATE T_Creator_users SET enabled=0')
    assert onboarding.creator_access(db, manager, launch_claims()) == []


def test_accounts_not_obtained_with_a_code_are_never_offered(db, manager):
    with db.get_connection() as c:
        # A regular account whose address is the one the LMS sends, and one linked by hand to this LMS user.
        c.execute("INSERT INTO T_Creator_users (organization_id,user_email,user_name,user_type,lti_user_id,auth_provider,enabled,role) VALUES (?,?,?,?,?,?,1,'admin')",
                  (ORG_A, 'teacher@school.example', 'Regular Admin', 'creator', None, 'password'))
        linked = c.execute("INSERT INTO T_Creator_users (organization_id,user_email,user_name,user_type,lti_user_id,auth_provider,enabled,role) VALUES (?,?,?,?,?,?,1,'user')",
                           (ORG_A, 'linked@alpha.example', 'Linked Regular', 'creator', None, 'password')).lastrowid
        c.execute('INSERT INTO T_lti_identity_links (lms_user_id, lms_email, creator_user_id) VALUES (?,?,?)', ('teacher-1', 'teacher@school.example', linked))
        # An LTI creator of another entry path that happens to carry the same LMS user id.
        c.execute("INSERT INTO T_Creator_users (organization_id,user_email,user_name,user_type,lti_user_id,auth_provider,enabled,role) VALUES (?,?,?,?,?,?,1,'user')",
                  (ORG_B, 'lti_creator_beta_teacher-1@lamb-lti.local', 'Same Id Elsewhere', 'creator', 'teacher-1', 'lti_creator'))
    assert len(manager.identify_instructor(lms_user_id='teacher-1', lms_email='teacher@school.example')) == 3  # all three are identified for the setup
    assert onboarding.creator_access(db, manager, launch_claims()) == []
    for row in sqlite3.connect(db.db_path).execute('SELECT id FROM T_Creator_users').fetchall():
        assert onboarding.creator_session(db, manager, launch_claims(), row[0]) is None


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
    assert onboarding.creator_session(db, manager, launch_claims(age=3600), second['id']) is None


def test_the_creator_entry_route_takes_the_token_of_the_launch_and_nothing_else(client, db):
    code = onboarding.create_code(db, ORG_A)['code']
    page = launch(client)
    done = client.post('/lamb/v1/lti/onboarding', data={'ticket': ticket_in(page), 'code': code})
    setup_token = done.headers['location'].split('token=')[1]
    creator = db._one('SELECT * FROM T_Creator_users')
    assert [a['creator_user_id'] for a in onboarding.creator_access(db, lti_router.manager, lamb_auth.decode_token(setup_token))] == [creator['id']]
    opened = client.post('/lamb/v1/lti/creator-session', json={'token': setup_token, 'creator_user_id': creator['id']})
    assert opened.status_code == 200 and '/assistants?token=' in opened.json()['url']
    session = lamb_auth.decode_token(opened.json()['url'].split('token=')[1])
    assert lamb_auth.is_creator_session(session) and session['sub'] == str(creator['id'])
    for body in ({'token': setup_token, 'creator_user_id': creator['id'] + 1}, {'token': setup_token}, {'token': setup_token, 'creator_user_id': 'x'},
                 {'token': ticket_in(page), 'creator_user_id': creator['id']}, {'token': 'garbage', 'creator_user_id': creator['id']}, {}):
        assert client.post('/lamb/v1/lti/creator-session', json=body).status_code == 403
    # The next launch of the same person carries the same identity, so the setup token it gets offers the entry too.
    again = lamb_auth.decode_token(launch(client).headers['location'].split('token=')[1])
    assert again['lti_lms_instance'] == INSTANCE and len(onboarding.creator_access(db, lti_router.manager, again)) == 1
