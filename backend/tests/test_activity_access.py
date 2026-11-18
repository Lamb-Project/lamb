"""Shared assistants do not convey ownership or student-data access to activities (#565)."""
import json
from types import SimpleNamespace, MethodType
from urllib.parse import urlparse, parse_qs

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lamb import activity_access as access, auth as lamb_auth, lti_router
from lamb.auth_context import AuthContext, get_auth_context
from lamb.database_manager import LambDatabaseManager
from lamb.lti_activity_manager import LtiActivityManager
from creator_interface import activities_router as catalogue
from lamb.modules.file_evaluation import router as fe
from tests.test_lti_onboarding import FakeDb, ORG_A, ORG_B, INSTANCE


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = FakeDb(tmp_path / 'activities.db')
    users = [db.create_lti_creator_user(org, f'teacher-{i}', f'{name}@example.test', name)
             for i, (name, org) in enumerate([('Assistant owner', ORG_A), ('Activity owner', ORG_A),
                 ('Instructor', ORG_A), ('Unrelated', ORG_A), ('Foreign', ORG_B)])]
    with db.get_connection() as c:
        c.execute('''CREATE TABLE T_lti_activities (id INTEGER PRIMARY KEY, resource_link_id TEXT UNIQUE,
            organization_id INTEGER, owner_email TEXT, owner_name TEXT, activity_name TEXT, activity_type TEXT,
            context_id TEXT, context_title TEXT, status TEXT, setup_config TEXT, chat_visibility_enabled INTEGER,
            created_at INTEGER)''')
        for aid, kind in [(1, 'chat'), (2, 'file_evaluation'), (3, 'llm_access')]:
            c.execute('INSERT INTO T_lti_activities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (aid, f'resource-{aid}', ORG_A, 'Activity owner@example.test', 'Activity owner', f'Activity {aid}',
                 kind, 'course-1', 'Databases', 'active', '{}', 0, 1))
        c.execute('CREATE TABLE T_assistants (id INTEGER PRIMARY KEY, name TEXT, description TEXT, owner TEXT, organization_id INTEGER, api_callback TEXT)')
        c.execute('CREATE TABLE T_assistant_publish (assistant_id INTEGER, oauth_consumer_name TEXT, group_id TEXT, group_name TEXT)')
        c.execute('CREATE TABLE T_assistant_shares (assistant_id INTEGER, shared_with_user_id INTEGER)')
        c.execute('CREATE TABLE T_lti_activity_assistants (activity_id INTEGER, assistant_id INTEGER, added_at INTEGER)')
        for aid, org in [(11, ORG_A), (12, ORG_B)]:
            c.execute('INSERT INTO T_assistants VALUES (?,?,?,?,?,?)', (aid, 'Shared evaluator', '', 'Assistant owner@example.test', org,
                json.dumps({'rag_processor': 'rubric_rag', 'rubric_id': 'rubric-1'})))
            c.execute('INSERT INTO T_assistant_publish VALUES (?,?,?,?)', (aid, f'published-{aid}', 'g', 'Group'))
            c.execute('INSERT INTO T_assistant_shares VALUES (?,?)', (aid, users[1]))
        access.migrate(c.cursor(), 'T_')
        access.migrate(c.cursor(), 'T_')
    for name in ('get_published_assistants_for_org_user', 'get_lti_activities_by_org', 'get_activity_assistants'):
        setattr(db, name, MethodType(getattr(LambDatabaseManager, name), db))
    db.assistant_has_rubric_for_eval = LambDatabaseManager.assistant_has_rubric_for_eval
    db.get_lti_activity_by_resource_link = lambda rid: db._one('SELECT * FROM T_lti_activities WHERE resource_link_id=?', (rid,))
    manager = SimpleNamespace(db_manager=db)
    manager.identify_instructor = lambda **kw: LtiActivityManager.identify_instructor(manager, **kw)
    manager.get_published_assistants_for_instructor = lambda creators: {c['organization_id']: db.get_published_assistants_for_org_user(c['organization_id'], c['id'], c['user_email']) for c in creators}
    monkeypatch.setattr(catalogue, 'db', db)
    monkeypatch.setattr(lti_router, 'db_manager', db)
    monkeypatch.setattr(lti_router, 'manager', manager)
    monkeypatch.setattr(fe._service, 'db', db)
    monkeypatch.setattr(fe._service, 'get_submissions_by_activity', lambda aid: [])
    monkeypatch.setattr(fe._service, 'get_dashboard_stats', lambda aid: {})
    current = {'id': users[1]}
    app = FastAPI()
    app.include_router(catalogue.router, prefix='/activities')
    app.include_router(lti_router.router, prefix='/lti')
    app.include_router(fe.router, prefix='/fe')
    from lamb.token_dealer.lti import router as td_router
    app.include_router(td_router, prefix='/td')
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user=db.get_creator_user_by_id(current['id']), token_payload={},
        organization=db.get_organization_by_id(db.get_creator_user_by_id(current['id'])['organization_id']))
    return SimpleNamespace(db=db, users=users, current=current, client=TestClient(app))


def bridge(env, activity=1, user=1):
    env.current['id'] = env.users[user]
    response = env.client.post(f'/activities/{activity}/open')
    assert response.status_code == 200, response.text
    return parse_qs(urlparse(response.json()['url']).query)['token'][0]


def grant(env, activity=1, user=2):
    access.record_launch(env.db, access.activity_by_id(env.db, activity),
        {'lti_lms_user_id': f'teacher-{user}', 'lti_lms_instance': INSTANCE})


def test_shared_assistant_user_owns_activity_but_assistant_owner_does_not(env):
    activity = access.activity_by_id(env.db, 1)
    creator = env.db.get_creator_user_by_id(env.users[1])
    assert access.validate_assistants(env.db, activity, creator, [11]) == [11]
    assert access.relationship(env.db, activity, creator) == 'owner'
    assert access.relationship(env.db, activity, env.db.get_creator_user_by_id(env.users[0])) == 'catalogue'
    token = bridge(env)
    info = env.client.get('/lti/dashboard/info', params={'resource_link_id': 'resource-1', 'token': token})
    assert info.status_code == 200 and info.json()['is_owner'] is True
    env.current['id'] = env.users[0]
    assert env.client.post('/activities/1/open').status_code == 403


def test_catalogue_is_org_scoped_and_contains_no_setup_or_student_data(env):
    env.current['id'] = env.users[3]
    rows = env.client.get('/activities').json()['activities']
    assert len(rows) == 3
    assert all(not r['can_manage'] and r['relationship'] == 'catalogue' for r in rows)
    assert not {'setup_config', 'submissions', 'resource_link_id', 'token'} & rows[0].keys()
    assert env.client.post('/activities/1/open').status_code == 403
    env.current['id'] = env.users[4]
    assert env.client.get('/activities').json()['activities'] == []
    assert env.client.post('/activities/1/open').status_code == 404


def test_verified_instructor_can_read_but_not_change_settings(env):
    grant(env)
    token = bridge(env, user=2)
    info = env.client.get('/lti/dashboard/info', params={'token': token, 'resource_link_id': 'resource-1'})
    assert info.status_code == 200 and info.json()['is_owner'] is False
    assert info.json()['lms_origin'] == 'https://moodle.school.example'
    assert env.client.get('/lti/setup/info', params={'token': token}).status_code == 403
    assert env.client.post('/lti/reconfigure', data={'token': token, 'assistant_ids': 11}).status_code == 403
    assert env.client.get('/lti/dashboard/chats', params={'token': token, 'resource_link_id': 'resource-1'}).status_code == 403


def test_file_evaluation_instructor_keeps_view_but_only_activity_owner_can_edit(env):
    grant(env, activity=2)
    token = bridge(env, activity=2, user=2)
    params = {'token': token}
    view = env.client.get('/fe/activities/2/view', params=params)
    assert view.status_code == 200, view.text
    assert view.json()['activity_info']['is_owner'] is False
    assert env.client.put('/fe/activities/2/setup-config', params=params, json={'description': 'changed'}).status_code == 403
    owner = bridge(env, activity=2)
    response = env.client.put('/fe/activities/2/setup-config', params={'token': owner}, json={'evaluator_id': '11', 'description': 'changed'})
    assert response.status_code == 200, response.text
    cfg = json.loads(access.activity_by_id(env.db, 2)['setup_config'])
    assert cfg == {'evaluator_id': '11', 'description': 'changed'}
    assert env.client.put('/fe/activities/2/setup-config', params={'token': owner}, json={'evaluator_id': 12}).status_code == 403
    assert env.client.get('/fe/activities/1/view', params=params).status_code == 403


@pytest.mark.parametrize('change', ['disabled', 'moved', 'archived', 'grant_removed'])
def test_bridge_rechecks_current_account_and_activity_access(env, change):
    grant(env)
    token = bridge(env, user=2)
    with env.db.get_connection() as c:
        if change == 'disabled': c.execute('UPDATE T_Creator_users SET enabled=0 WHERE id=?', (env.users[2],))
        if change == 'moved': c.execute('UPDATE T_Creator_users SET organization_id=? WHERE id=?', (ORG_B, env.users[2]))
        if change == 'archived': c.execute("UPDATE T_lti_activities SET status='archived' WHERE id=1")
        if change == 'grant_removed': c.execute('DELETE FROM T_activity_instructors')
    assert env.client.get('/lti/dashboard/info', params={'token': token, 'resource_link_id': 'resource-1'}).status_code == 403


def test_legacy_context_is_unknown_until_verified_and_cannot_be_rebound(env):
    activity = access.activity_by_id(env.db, 1)
    assert access.context(env.db, activity)['context_known'] is False
    grant(env)
    with pytest.raises(Exception) as exc:
        access.record_launch(env.db, access.activity_by_id(env.db, 1), {'lti_lms_instance': 'other.example'}, instructor=False)
    assert exc.value.status_code == 403
    assert access.activity_by_id(env.db, 1)['lms_origin'] == 'https://moodle.school.example'


def test_removing_assistant_share_blocks_replacement_but_does_not_transfer_activity(env):
    with env.db.get_connection() as c:
        c.execute('DELETE FROM T_assistant_shares')
    activity = access.activity_by_id(env.db, 1)
    creator = env.db.get_creator_user_by_id(env.users[1])
    assert access.is_owner(activity, creator)
    with pytest.raises(Exception) as exc:
        access.validate_assistants(env.db, activity, creator, [11])
    assert exc.value.status_code == 403


def test_assistant_analytics_cannot_reveal_other_owners_activity_chats(env, tmp_path):
    import sqlite3
    from lamb.services.chat_analytics_service import ChatAnalyticsService
    with env.db.get_connection() as c:
        c.execute('CREATE TABLE T_lti_activity_users (activity_id INTEGER, owi_user_id TEXT)')
        c.execute("INSERT INTO T_lti_activity_users VALUES (1,'student')")
        c.execute('UPDATE T_lti_activities SET chat_visibility_enabled=1 WHERE id=1')
    path = tmp_path / 'owi.db'
    with sqlite3.connect(path) as c:
        c.executescript('CREATE TABLE chat(id TEXT,user_id TEXT,title TEXT,created_at INTEGER,updated_at INTEGER,chat TEXT); CREATE TABLE user(id TEXT,name TEXT,email TEXT);')
        c.execute('INSERT INTO chat VALUES (?,?,?,?,?,?)', ('private', 'student', 'Private', 1, 1,
            json.dumps({'models': ['lamb_assistant.11'], 'history': {'messages': {'q': {'role': 'user', 'content': 'private work'}}}})))
    service = ChatAnalyticsService.__new__(ChatAnalyticsService)
    service.lamb_db = env.db
    service._get_lamb_internal_chats = lambda *a, **kw: []
    service._get_lamb_chat_detail = lambda *a, **kw: None
    def query(sql, params=(), fetch_one=False):
        with sqlite3.connect(path) as c:
            cursor = c.execute(sql, params)
            return cursor.fetchone() if fetch_one else cursor.fetchall()
    service._execute_query = query
    def scoped(index):
        return service.for_auth(AuthContext(user=env.db.get_creator_user_by_id(env.users[index]),
            token_payload={}, organization={'id': ORG_A}))
    assert scoped(0).get_chats_for_assistant(11)['total'] == 0
    assert scoped(0).get_chat_detail('private', 11) is None
    assert scoped(0).get_assistant_stats(11)['stats']['total_chats'] == 0
    assert scoped(1).get_chat_detail('private', 11) is not None
    grant(env)
    assert scoped(2).get_chat_detail('private', 11) is not None
    with env.db.get_connection() as c:
        c.execute('UPDATE T_lti_activities SET chat_visibility_enabled=0 WHERE id=1')
    assert scoped(1).get_chat_detail('private', 11) is None


def test_lti13_context_and_instructor_grants_use_registration_and_deployment(env):
    from lamb.lti13.store import Store
    # The object store binds external IDs to both registration and deployment.
    store = Store(env.db)
    registration = dict(name='Platform', issuer='https://platform.example', client_id='client-1',
        authorization_url='https://platform.example/authorize', token_url='https://platform.example/token',
        jwks_url='https://platform.example/jwks', deployment_ids=['deployment-1', 'deployment-2'],
        organization_ids=[ORG_A], service_origins=['https://platform.example'], enabled=True)
    registration['organization_ids'] = [ORG_A]
    reg = store.save_registration(registration)
    rid = store.object_id(reg, registration['deployment_ids'][0], 'resource', 'same-link')
    with env.db.get_connection() as c:
        c.execute('UPDATE T_lti_activities SET resource_link_id=? WHERE id=1', (rid,))
    activity = access.activity_by_id(env.db, 1)
    access.record_launch(env.db, activity, {}, instructor=False)
    assert activity['lms_origin'] == registration['issuer']
    assert json.loads(activity['lms_scope']) == ['1.3', reg, registration['deployment_ids'][0]]


def test_llm_access_instructor_can_manage_students_but_only_owner_changes_timetable(env, monkeypatch, tmp_path):
    from lamb.migrations import MigrationRunner
    from lamb.token_dealer import wiring
    from lamb.token_dealer.service import TokenDealerService
    from lamb.token_dealer.store import TokenDealerStore
    from lamb.token_dealer.settings import Settings
    from lamb.token_dealer.ledger import UsageLedger
    from tests.test_token_dealer import FakeProxy
    with env.db.get_connection() as c:
        MigrationRunner(env.db)._migration_33(c.cursor())
    settings = Settings(enabled=True, proxy_url='http://synthetic', proxy_admin_key='test', models=['course-model'])
    store = TokenDealerStore(env.db)
    service = TokenDealerService(store, lambda org: settings, lambda org: FakeProxy())
    monkeypatch.setattr(wiring, 'store', lambda: store)
    monkeypatch.setattr(wiring, 'service', lambda: service)
    monkeypatch.setattr(wiring, 'settings_for', lambda org: settings)
    monkeypatch.setattr(wiring, 'ledger', lambda: UsageLedger(tmp_path / 'usage.db'))
    service.configure_activity(ORG_A, 'resource-3', 'Activity owner@example.test', ['course-model'], {'mode': 'always', 'timezone': 'UTC'}, slot_tokens=1000)
    grant(env, activity=3)
    instructor = bridge(env, activity=3, user=2)
    page = env.client.get('/td/manage', params={'token': instructor})
    assert page.status_code == 200, page.text
    assert 'Change limits and timetable' not in page.text
    assert 'moodle.school.example' in page.text and 'Databases' in page.text
    assert env.client.post('/td/configure', data={'token': instructor, 'models': 'course-model'}).status_code == 403
    assert env.client.post('/td/override', data={'token': instructor, 'override': 'closed'}).status_code == 403
    owner = bridge(env, activity=3)
    assert 'Change limits and timetable' in env.client.get('/td/manage', params={'token': owner}).text
    assert env.client.post('/td/override', data={'token': owner, 'override': 'closed'}, follow_redirects=False).status_code == 303
