"""The kinds of activity a teacher is offered when setting up an LTI activity.

Marc, 15 November 2026: once the organization is chosen, LAMB tells the available kinds. The
list depends on the organization's settings and on the creator user in that organization:
does the teacher have published assistants, can the teacher hand an LLM key to students.
A kind that cannot be created is not offered, and the server refuses it whatever the page sent.
"""
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lamb import lti_router
from lamb.migrations import MigrationRunner
from lamb.modules import discover_modules, get_module
from lamb.token_dealer import wiring
from lamb.token_dealer.service import TokenDealerService
from lamb.token_dealer.settings import Settings
from lamb.token_dealer.store import TokenDealerStore

from tests.test_token_dealer import Db, FakeProxy

PLAIN = {'id': 11, 'name': 'tutor', 'rubric_eval_ready': False, 'access_type': 'owned'}
RUBRIC = {'id': 12, 'name': 'grader', 'rubric_eval_ready': True, 'access_type': 'shared'}
ON = dict(enabled=True, proxy_url='http://proxy', proxy_admin_key='k', models=['m'])
WEEKLY = {'timezone': 'Europe/Madrid', 'mode': 'always'}


@pytest.fixture
def dealer(tmp_path, monkeypatch):
    """A real token-dealer store and service over a temporary database; settings per organization."""
    db = Db(str(tmp_path / 'lamb.db'))
    with sqlite3.connect(db.path) as c:
        c.execute('CREATE TABLE T_organizations (id INTEGER PRIMARY KEY)')
        c.executemany('INSERT INTO T_organizations VALUES (?)', [(3,), (4,)])
        MigrationRunner(db)._migration_33(c.cursor())
    store, proxy, settings = TokenDealerStore(db), FakeProxy(), {}
    by_org = lambda org: settings.get(org, Settings(enabled=False))
    service = TokenDealerService(store, by_org, lambda org: proxy)
    monkeypatch.setattr(wiring, 'settings_for', by_org)
    monkeypatch.setattr(wiring, 'service', lambda: service)
    discover_modules()
    return SimpleNamespace(settings=settings, service=service)


# ── the rule of each kind ──────────────────────────────────────────────

def test_chat_needs_a_published_assistant(dealer):
    chat = get_module('chat')
    assert chat.unavailable_reason(3, []) == 'no_published_assistant'
    assert chat.unavailable_reason(3, [PLAIN]) is None
    assert chat.unavailable_reason(3, [RUBRIC]) is None        # a rubric assistant can also chat


def test_file_evaluation_needs_a_published_assistant_with_a_rubric(dealer):
    fe = get_module('file_evaluation')
    assert fe.unavailable_reason(3, []) == 'no_published_assistant'
    assert fe.unavailable_reason(3, [PLAIN]) == 'no_rubric_assistant'
    assert fe.unavailable_reason(3, [PLAIN, RUBRIC]) is None


def test_llm_access_needs_the_organization_setup(dealer):
    llm = get_module('llm_access')
    assert llm.unavailable_reason(3, [], 't@x.edu') == 'not_enabled'             # never switched on
    dealer.settings[3] = Settings(**{**ON, 'models': []})
    assert llm.unavailable_reason(3, [], 't@x.edu') == 'not_enabled'             # no model to serve
    dealer.settings[3] = Settings(**{**ON, 'proxy_url': ''})
    assert llm.unavailable_reason(3, [], 't@x.edu') == 'not_enabled'             # no gateway
    dealer.settings[3] = Settings(**ON)
    assert llm.unavailable_reason(3, [], 't@x.edu') is None                      # no allowance limit


def test_llm_access_follows_what_is_left_of_the_teachers_allowance(dealer):
    llm = get_module('llm_access')
    dealer.settings[3] = Settings(**ON, policy='pool', teacher_allowance_tokens=10000)
    assert llm.unavailable_reason(3, [], 't@x.edu') is None
    dealer.service.configure_activity(3, 'rl-1', 't@x.edu', ['m'], WEEKLY, pool_tokens=10000)
    assert llm.unavailable_reason(3, [], 't@x.edu') == 'no_allowance'            # all of it committed
    assert llm.unavailable_reason(3, [], 'colleague@x.edu') is None              # each teacher has their own
    assert llm.unavailable_reason(3, [], 'T@X.edu ') == 'no_allowance'           # as the LMS happens to write it


def test_an_allowance_of_zero_closes_llm_access_only_where_a_pool_is_required(dealer):
    llm = get_module('llm_access')
    for policy in ('pool', 'both'):
        dealer.settings[3] = Settings(**ON, policy=policy, teacher_allowance_tokens=0)
        assert llm.unavailable_reason(3, [], 't@x.edu') == 'no_allowance'
    # Per-student limits per time slot commit nothing, so a key can still be handed out.
    dealer.settings[3] = Settings(**ON, policy='per_student', teacher_allowance_tokens=0)
    assert llm.unavailable_reason(3, [], 't@x.edu') is None
    dealer.service.configure_activity(3, 'rl-2', 't@x.edu', ['m'], WEEKLY, slot_tokens=500)


def test_an_exception_for_one_teacher_decides_for_that_teacher(dealer):
    llm = get_module('llm_access')
    dealer.settings[3] = Settings(**ON, policy='pool', teacher_allowance_tokens=0, teacher_allowances={'t@x.edu': 5000})
    assert llm.unavailable_reason(3, [], 't@x.edu') is None
    assert llm.unavailable_reason(3, [], 'other@x.edu') == 'no_allowance'


# ── the setup page's data and the save route ───────────────────────────

USERS = {5: {'id': 5, 'organization_id': 3, 'user_email': 'lti_creator_a_t1@lamb-lti.local', 'user_name': 'Teacher', 'enabled': True},
         6: {'id': 6, 'organization_id': 4, 'user_email': 'lti_creator_b_t1@lamb-lti.local', 'user_name': 'Teacher', 'enabled': True}}
JWT = {'lti_type': 'setup', 'lti_resource_link_id': 'rl-new', 'lti_creator_user_ids': [5, 6], 'lti_lms_user_id': 'teacher-1',
       'lti_lms_email': 'T@x.edu', 'lti_context_id': 'c1', 'lti_context_title': 'Databases'}


@pytest.fixture
def page(dealer, monkeypatch):
    published, created, calls = {3: [], 4: []}, {}, []
    monkeypatch.setattr(lti_router, '_validate_lti_jwt', lambda token, kind: JWT if kind == 'setup' else None)
    db = SimpleNamespace(
        get_creator_user_by_id=USERS.get,
        get_organization_by_id=lambda i: {'name': f'Faculty {i}', 'slug': f'f{i}'},
        get_published_assistants_for_org_user=lambda org, uid, email: list(published[org]),
        get_lti_activity_by_resource_link=created.get,
        get_assistant_by_id=lambda i: SimpleNamespace(name='a', api_callback='{}'),
        assistant_has_rubric_for_eval=lambda cb: True,
        delete_lti_activity=lambda i: calls.append(('delete', i)))
    monkeypatch.setattr(lti_router, 'db_manager', db)
    monkeypatch.setattr(lti_router.activity_access, 'record_launch', lambda *a, **kw: None)
    monkeypatch.setattr(lti_router.activity_access, 'creators_for_payload', lambda *a: list(USERS.values()))
    # The instructor is identified from the LMS user of the token, never from a list in it.
    monkeypatch.setattr(lti_router.manager, 'identify_instructor',
                        lambda **kw: list(USERS.values()) if kw.get('lms_user_id') == 'teacher-1' else [])
    monkeypatch.setattr(lti_router.manager, 'get_published_assistants_for_instructor',
                        lambda cus: {cu['organization_id']: list(published[cu['organization_id']])
                                     for cu in cus if published[cu['organization_id']]})
    monkeypatch.setattr(lti_router.manager, 'configure_activity',
                        lambda **kw: calls.append(('create', kw['activity_type'], kw['organization_id'])) or
                        created.setdefault(kw['resource_link_id'], {'id': 9, 'resource_link_id': kw['resource_link_id'],
                                                                     'activity_type': kw['activity_type'],
                                                                     'organization_id': kw['organization_id']}))
    monkeypatch.setattr(lti_router.manager, 'get_public_base_url', lambda req: 'https://lamb.x')
    for name in ('chat', 'file_evaluation', 'llm_access'):
        monkeypatch.setattr(get_module(name), 'on_activity_configured', lambda aid, data: None)
        monkeypatch.setattr(get_module(name), 'configured_redirect', lambda *a, **kw: '/done')
    app = FastAPI()
    app.include_router(lti_router.router, prefix='/lamb/v1/lti')
    client = TestClient(app)
    info = lambda: client.get('/lamb/v1/lti/setup/info', params={'token': 't'}).json()
    save = lambda **body: client.post('/lamb/v1/lti/configure', json={'token': 't', **body})
    return SimpleNamespace(info=info, save=save, published=published, created=created, calls=calls, dealer=dealer)


def kinds(info):
    return {org: set(names) for org, names in info['org_modules'].items()}


def test_each_organization_gets_its_own_list(page):
    page.published[3] = [PLAIN]                                   # an assistant, no LLM access
    page.dealer.settings[4] = Settings(**ON)                      # LLM access, nothing published
    info = page.info()
    assert kinds(info) == {'3': {'chat'}, '4': {'llm_access'}}
    # Only kinds offered somewhere are described at all.
    assert {m['name'] for m in info['modules']} == {'chat', 'llm_access'}
    assert set(info['modules_fields']) == {'chat', 'llm_access'}


def test_an_organization_where_nothing_can_be_created_yet_gets_an_empty_list(page):
    info = page.info()
    assert kinds(info) == {'3': set(), '4': set()}
    assert info['modules'] == [] and info['modules_fields'] == {}
    assert set(info['org_names']) == {'3', '4'}                   # the organizations are still named


def test_a_rubric_assistant_opens_file_evaluation(page):
    page.published[3] = [PLAIN]
    assert kinds(page.info())['3'] == {'chat'}
    page.published[3] = [PLAIN, RUBRIC]
    assert kinds(page.info())['3'] == {'chat', 'file_evaluation'}


def test_the_allowance_is_read_for_the_email_the_lms_sends(page):
    page.dealer.settings[3] = Settings(**ON, policy='pool', teacher_allowance_tokens=0, teacher_allowances={'t@x.edu': 5000})
    assert kinds(page.info())['3'] == {'llm_access'}             # JWT says T@x.edu, the exception says t@x.edu
    page.dealer.settings[3] = Settings(**ON, policy='pool', teacher_allowance_tokens=0)
    assert kinds(page.info())['3'] == set()


def test_saving_a_kind_that_is_not_offered_is_refused(page):
    page.published[3] = [PLAIN]
    page.dealer.settings[4] = Settings(**ON, policy='pool', teacher_allowance_tokens=0)
    # File evaluation in an organization where the teacher has no assistant with a rubric.
    r = page.save(organization_id=3, activity_type='file_evaluation', assistant_ids=[11], title='Essay', deadline='2026-12-01')
    assert r.status_code == 400 and 'not available to you' in r.json()['detail']
    # LLM access where the organization has it but this teacher's allowance is zero.
    r = page.save(organization_id=4, activity_type='llm_access', pool_tokens='100')
    assert r.status_code == 400 and 'not available to you' in r.json()['detail']
    assert page.calls == []


def test_saving_an_offered_kind_still_works(page):
    page.published[3] = [PLAIN]
    r = page.save(organization_id=3, activity_type='chat', assistant_ids=[11])
    assert r.status_code == 200 and page.calls == [('create', 'chat', 3)]


def test_an_existing_activity_can_still_be_saved_when_its_kind_is_no_longer_offered(page, monkeypatch):
    page.dealer.settings[4] = Settings(**ON, policy='pool', teacher_allowance_tokens=0)
    page.created['rl-new'] = {'id': 9, 'resource_link_id': 'rl-new', 'activity_type': 'llm_access', 'organization_id': 4, 'owner_email': USERS[6]['user_email']}
    monkeypatch.setattr(lti_router.manager, 'reconfigure_activity', lambda activity, ids: ([], []))
    monkeypatch.setattr(get_module('llm_access'), 'on_activity_reconfigured', lambda *a: None)
    r = page.save(organization_id=4, activity_type='llm_access', pool_tokens='100')
    assert r.status_code == 200
