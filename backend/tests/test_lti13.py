"""LTI 1.3 security/upgrade tests using real RSA signatures and SQLite transactions."""
import concurrent.futures
import json
import sqlite3
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from lamb.lti13 import CLAIM, AGS, SCORE_SCOPE
from lamb.lti13 import protocol, network, grades, store as store_module
from lamb.lti13.keys import KeyRing
from lamb.lti13.store import Store, migrate

TARGET = 'https://tool.example/lamb/v1/lti/launch'


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'lamb.db'
    db = SimpleNamespace(table_prefix='T_', db_path=str(path), get_connection=lambda: sqlite3.connect(path, timeout=10))
    def creator(uid):
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM T_Creator_users WHERE id=?', (uid,)).fetchone()
            return dict(row) if row else None
    db.get_creator_user_by_id = creator
    db.get_organization_by_id = lambda oid: {'id': oid, 'name': 'Organization'} if oid in (1, 2) else None
    with db.get_connection() as c:
        c.execute('CREATE TABLE T_Creator_users (id INTEGER PRIMARY KEY, organization_id INTEGER, user_email TEXT, user_name TEXT, enabled INTEGER)')
        c.executemany('INSERT INTO T_Creator_users VALUES (?,?,?,?,?)', [(1,1,'teacher@example.edu','Teacher',1), (2,2,'other@example.edu','Other',1)])
        c.execute('CREATE TABLE T_lti_activities (id INTEGER PRIMARY KEY, resource_link_id TEXT UNIQUE, organization_id INTEGER, status TEXT, activity_type TEXT)')
        c.execute("INSERT INTO T_lti_activities VALUES (1,'old-resource',1,'active','chat')")
        migrate(c.cursor(), 'T_')
    store = Store(db)
    config = dict(name='Platform', issuer='https://platform.example', client_id='client-1',
                  authorization_url='https://platform.example/authorize', token_url='https://platform.example/token',
                  jwks_url='https://platform.example/jwks', deployment_ids=['deployment-1', 'deployment-2'],
                  organization_ids=[1], service_origins=['https://platform.example'], enabled=True)
    rid = store.save_registration(config)
    reg = store.registration(rid)
    keys = KeyRing(tmp_path / 'platform-keys')
    monkeypatch.setenv('LAMB_PUBLIC_BASE_URL', 'https://tool.example')
    monkeypatch.setenv('LTI13_KEY_DIR', str(tmp_path / 'tool-keys'))
    protocol._JWKS.clear()
    grades._TOKENS.clear()
    monkeypatch.setattr(network, 'request', lambda method, url, **kw: keys.public())
    return SimpleNamespace(db=db, store=store, config=config, rid=rid, reg=reg, keys=keys)


def launch(env, changes=None, remove=(), registration=None, transaction=None):
    reg = registration or env.reg
    state, nonce, proof = transaction or env.store.new_transaction(reg, TARGET)
    now = int(time.time())
    claims = {'iss': reg['issuer'], 'aud': reg['client_id'], 'sub': 'same-subject', 'iat': now, 'exp': now+300,
              'nonce': nonce, CLAIM+'deployment_id': 'deployment-1', CLAIM+'message_type': 'LtiResourceLinkRequest',
              CLAIM+'version': '1.3.0', CLAIM+'target_link_uri': TARGET,
              CLAIM+'resource_link': {'id': 'same-resource'}, CLAIM+'context': {'id': 'same-course', 'title': 'Course'},
              CLAIM+'roles': [protocol.LEARNER_ROLE], 'name': 'Learner', 'email': 'teacher@example.edu',
              AGS+'claim/endpoint': {'lineitem': 'https://platform.example/lineitems/1', 'scope': [SCORE_SCOPE]}}
    claims.update(changes or {})
    for key in remove:
        claims.pop(key)
    return {'state': state, 'browser_proof': proof, 'id_token': env.keys.sign(claims)}


def object_count(env):
    with env.db.get_connection() as c:
        return c.execute('SELECT COUNT(*) FROM T_lti13_objects').fetchone()[0]


def test_valid_launch_stable_ids_optional_pii_and_exact_roles(env):
    first = protocol.validate_launch(launch(env), env.store)
    second = protocol.validate_launch(launch(env, remove=['name', 'email']), env.store)
    for field in ('resource_link_id', 'lms_user_id', 'context_id', 'username'):
        assert first[field] == second[field]
    assert not second['is_instructor'] and second['lms_email'] == ''
    assert second['display_name'] == 'LMS user'
    assert env.store.object(first['lms_user_id'])['external_id'] == 'same-subject'
    teacher = protocol.validate_launch(launch(env, {CLAIM+'roles': [next(iter(protocol.INSTRUCTOR_ROLES))]}), env.store)
    assert teacher['is_instructor']


@pytest.mark.parametrize('changes,remove', [
    ({'iss':'https://impostor.example'}, []), ({'aud':'wrong-client'}, []),
    ({'aud':['client-1','another']}, []), ({'azp':'another'}, []),
    ({'nonce':'wrong'}, []), ({}, ['nonce']), ({}, ['sub']), ({'sub':''}, []),
    ({}, ['exp']), ({}, ['iat']), ({'exp':int(time.time())-60}, []),
    ({'exp':float('inf')}, []), ({'exp':float('nan')}, []),
    ({'iat':int(time.time())+120}, []), ({'iat':int(time.time())-700}, []),
    ({CLAIM+'deployment_id':'unknown'}, []), ({}, [CLAIM+'deployment_id']),
    ({CLAIM+'target_link_uri':'https://evil.example/launch'}, []),
    ({CLAIM+'message_type':'LtiDeepLinkingRequest'}, []), ({CLAIM+'version':'1.1'}, []),
    ({CLAIM+'resource_link':{}}, []), ({CLAIM+'resource_link':[]}, []),
    ({CLAIM+'roles':[]}, []), ({CLAIM+'roles':['fake-Instructor']}, []),
    ({CLAIM+'roles':'Instructor'}, []), ({CLAIM+'context':None}, []),
    ({AGS+'claim/endpoint':{'scope':'bad'}}, []),
    ({AGS+'claim/endpoint':{'scope':[SCORE_SCOPE], 'lineitem':'https://evil.example/lineitems/1'}}, []),
    ({AGS+'claim/endpoint':{'scope':[SCORE_SCOPE], 'lineitem':'http://platform.example/lineitems/1'}}, []),
])
def test_invalid_launches_never_create_objects(env, changes, remove):
    form = launch(env, changes, remove)
    with pytest.raises(ValueError):
        protocol.validate_launch(form, env.store)
    assert object_count(env) == 0
    assert env.store.transaction(form['state'], form['browser_proof'])['consumed'] == 0


def test_signature_and_algorithm_rejected(env):
    good = launch(env)
    claims = jwt.decode(good['id_token'], options={'verify_signature': False})
    alien = KeyRing(env.keys.directory.parent / 'alien')
    with pytest.raises(ValueError):
        protocol.validate_launch({**good, 'id_token': alien.sign(claims)}, env.store)
    with pytest.raises(ValueError):
        protocol.validate_launch({**good, 'id_token': jwt.encode(claims, 'secret', algorithm='HS256', headers={'kid':'x'})}, env.store)
    assert object_count(env) == 0


def test_replay_and_crossed_browser_transactions(env):
    a, b = launch(env), launch(env)
    for crossed in ({**a, 'browser_proof':b['browser_proof']}, {**a,'state':b['state'],'browser_proof':b['browser_proof']}):
        with pytest.raises(ValueError):
            protocol.validate_launch(crossed, env.store)
    protocol.validate_launch(a, env.store)
    protocol.validate_launch(b, env.store)
    with pytest.raises(ValueError):
        protocol.validate_launch(a, env.store)


def test_two_workers_cannot_consume_same_transaction(env):
    state, nonce, proof = env.store.new_transaction(env.reg, TARGET)
    row = env.store.transaction(state, proof)
    def consume():
        try:
            env.store.consume(row)
            return True
        except ValueError:
            return False
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(lambda _: consume(), range(2))) == [False, True]


def test_expired_transaction_and_registration_changes(env):
    form = launch(env)
    with env.db.get_connection() as c:
        c.execute('UPDATE T_lti13_transactions SET expires_at=?', (int(time.time())-1,))
    with pytest.raises(ValueError):
        protocol.validate_launch(form, env.store)
    form = launch(env)
    env.store.save_registration({**env.config, 'enabled':False}, env.rid)
    with pytest.raises(ValueError):
        protocol.validate_launch(form, env.store)
    env.store.save_registration(env.config, env.rid)
    with pytest.raises(ValueError):
        protocol.validate_launch(form, env.store)


def test_registration_and_deployment_identifiers_are_isolated(env):
    a = protocol.validate_launch(launch(env), env.store)
    rid = env.store.save_registration({**env.config, 'client_id':'client-2'})
    b = protocol.validate_launch(launch(env, registration=env.store.registration(rid)), env.store)
    c = protocol.validate_launch(launch(env, {CLAIM+'deployment_id':'deployment-2'}), env.store)
    for field in ('resource_link_id', 'lms_user_id', 'context_id'):
        assert len({a[field],b[field],c[field]}) == 3


def test_instructor_identity_requires_confirmed_link_and_allowed_org(env):
    user = protocol.validate_launch(launch(env), env.store)['lms_user_id']
    assert env.store.creators(user) == [] # even though email matches an existing creator
    with pytest.raises(ValueError):
        env.store.link_creator(user, 2)
    env.store.link_creator(user, 1)
    assert [u['id'] for u in env.store.creators(user)] == [1]
    with env.db.get_connection() as c:
        c.execute('UPDATE T_Creator_users SET enabled=0 WHERE id=1')
    assert env.store.creators(user) == []


def test_module_sessions_are_revoked_on_registration_edit(env, monkeypatch):
    from lamb import auth
    monkeypatch.setattr(store_module, 'Store', lambda db=None: env.store)
    ctx = protocol.validate_launch(launch(env), env.store)
    for data in ({'lti_lms_user_id':ctx['lms_user_id'], 'lti_resource_link_id':ctx['resource_link_id']},
                 {'scope':'llm_access', 'lms_user_id':ctx['lms_user_id']},
                 {'scope':'chat', 'resource_link_id':ctx['resource_link_id']}):
        token = auth.create_token(data)
        assert auth.decode_token(token)['lti13_registration_id'] == env.rid
    env.store.save_registration({**env.config, 'enabled':False}, env.rid)
    assert auth.decode_token(token) is None
    assert auth.decode_token(auth.create_token({'email':'ordinary@example.edu'}))['email'] == 'ordinary@example.edu'


def test_login_selects_registered_client_and_exact_target(env):
    params = {'iss':env.reg['issuer'], 'client_id':env.reg['client_id'], 'login_hint':'opaque-hint', 'target_link_uri':TARGET}
    html = protocol.begin_login(params, env.store).body.decode()
    assert 'sessionStorage.setItem' in html and 'response_mode=form_post' in html and 'nonce=' in html
    assert 'Referrer' not in html
    with pytest.raises(ValueError):
        protocol.begin_login({**params,'target_link_uri':'https://evil.example'}, env.store)
    with pytest.raises(ValueError):
        protocol.begin_login({**params,'lti_deployment_id':'unknown'}, env.store)
    env.store.save_registration({**env.config,'client_id':'another'})
    with pytest.raises(ValueError):
        protocol.begin_login({k:v for k,v in params.items() if k!='client_id'}, env.store)


def test_jwks_rotation_keeps_previous_public_key_and_never_private(env):
    old = env.keys.public()['keys'][0]['kid']
    new = env.keys.rotate()
    public = env.keys.public()
    assert {k['kid'] for k in public['keys']} == {old,new}
    assert all('d' not in k and 'private' not in k for k in public['keys'])
    assert jwt.get_unverified_header(env.keys.sign({'example':True}))['kid'] == new
    assert (env.keys.directory/'keyring.json').stat().st_mode & 0o777 == 0o600


def test_platform_key_rotation_refreshes_unknown_kid(env):
    protocol.validate_launch(launch(env), env.store)
    env.keys.rotate()
    assert protocol.validate_launch(launch(env), env.store)['lti_version'] == '1.3.0'


def test_idempotent_upgrade_preserves_existing_rows(env):
    with env.db.get_connection() as c:
        before = list(c.execute('SELECT * FROM T_lti_activities'))
        migrate(c.cursor(), 'T_')
        migrate(c.cursor(), 'T_')
        assert list(c.execute('SELECT * FROM T_lti_activities')) == before
        assert c.execute('SELECT COUNT(*) FROM T_lti13_registrations').fetchone()[0] == 1
        migrate(c.cursor(), '') # also supports empty prefixes


def test_ags_sends_real_subject_and_correct_score_without_excess_scopes(env, monkeypatch):
    ctx = protocol.validate_launch(launch(env), env.store)
    env.store.save_grade_target(ctx['resource_link_id'], ctx['lms_user_id'], 'synthetic@lamb-lti.local', ctx['grade_endpoint'])
    calls = []
    def request(method, url, **kw):
        calls.append((method,url,kw))
        if url == env.reg['token_url']:
            data = kw['data']
            assert data['scope'] == SCORE_SCOPE
            assertion = data['client_assertion']
            key = jwt.PyJWK(KeyRing().public()['keys'][0]).key
            claims = jwt.decode(assertion,key,algorithms=['RS256'],audience=url)
            assert claims['sub'] == env.reg['client_id'] and claims['iss'] == env.reg['client_id']
            assert claims['exp']-claims['iat'] == 60
            return {'access_token':'test-access-token','token_type':'Bearer','expires_in':300,'scope':SCORE_SCOPE}
        assert url == 'https://platform.example/lineitems/1/scores'
        assert kw['payload']['userId'] == 'same-subject'
        assert kw['payload']['scoreGiven'] == 8 and kw['payload']['scoreMaximum'] == 10
        return {}
    monkeypatch.setattr(network, 'request', request)
    for _ in range(2):
        assert grades.send_score(ctx['resource_link_id'], 'synthetic@lamb-lti.local', 8, store=env.store)['success']
    assert len(calls) == 3 # token reused only for this registration/revision/scope
    env.store.save_registration({**env.config,'enabled':False}, env.rid)
    assert not grades.send_score(ctx['resource_link_id'], 'synthetic@lamb-lti.local', 8, store=env.store)['success']
    assert len(calls) == 3


@pytest.mark.parametrize('endpoint,score', [({'scope':[]},8), ({'scope':[SCORE_SCOPE]},8),
    ({'scope':[SCORE_SCOPE],'lineitem':'https://evil.example'},8),
    ({'scope':[SCORE_SCOPE],'lineitem':'https://platform.example/lineitems/1'},float('nan'))])
def test_unavailable_or_invalid_grades_do_not_report_success(env, monkeypatch, endpoint, score):
    ctx = protocol.validate_launch(launch(env), env.store)
    env.store.save_grade_target(ctx['resource_link_id'],ctx['lms_user_id'],'student',endpoint)
    monkeypatch.setattr(network,'request',lambda *a,**kw: pytest.fail('No network request expected'))
    result = grades.send_score(ctx['resource_link_id'],'student',score,store=env.store)
    assert not result['success'] and result['error_message']


@pytest.fixture
def api(env, monkeypatch):
    from lamb import lti_router
    from lamb.lti13 import router as admin_router
    monkeypatch.setattr(store_module, 'Store', lambda db=None: env.store)
    monkeypatch.setattr(protocol, 'Store', lambda: env.store)
    monkeypatch.setattr(admin_router, 'Store', lambda: env.store)
    monkeypatch.setattr(lti_router, 'Store', lambda: env.store)
    monkeypatch.setattr(lti_router, 'db_manager', env.db)
    monkeypatch.setattr(lti_router.manager, 'db_manager', env.db)
    env.db.get_lti_activity_by_resource_link = lambda rid: None
    app = FastAPI()
    app.include_router(lti_router.router, prefix='/lamb/v1/lti')
    return SimpleNamespace(client=TestClient(app), app=app, router=lti_router, admin=admin_router)


def test_direct_post_cannot_dispatch_or_create_activity(api, env):
    form = launch(env)
    response = api.client.post('/lamb/v1/lti/launch', data={k:v for k,v in form.items() if k!='browser_proof'})
    assert response.status_code == 200 and 'sessionStorage.getItem' in response.text
    assert response.headers['cache-control'] == 'no-store'
    assert object_count(env) == 0
    response = api.client.post('/lamb/v1/lti/launch', data={**form,'browser_proof':'attacker'})
    assert response.status_code == 401 and object_count(env) == 0


@pytest.mark.parametrize('module_name', ['chat','file_evaluation','llm_access'])
@pytest.mark.parametrize('teacher', [False,True])
def test_valid_launch_dispatches_every_module(api, env, monkeypatch, module_name, teacher):
    env.db.get_lti_activity_by_resource_link = lambda rid: {'id':2,'resource_link_id':rid,'organization_id':1,'status':'active','activity_type':module_name}
    module = SimpleNamespace(on_instructor_launch=lambda ctx: JSONResponse({'instructor':True,'type':module_name,'version':ctx.lti_version}),
                             on_student_launch=lambda ctx: JSONResponse({'instructor':False,'type':module_name,'version':ctx.lti_version}))
    monkeypatch.setattr(api.router,'get_module',lambda _:module)
    changes = {CLAIM+'roles':[next(iter(protocol.INSTRUCTOR_ROLES))]} if teacher else {}
    response = api.client.post('/lamb/v1/lti/launch',data=launch(env,changes))
    assert response.status_code == 200, response.text
    assert response.json() == {'instructor':teacher,'type':module_name,'version':'1.3.0'}


def test_unlinked_instructor_goes_to_explicit_account_link(api, env):
    response = api.client.post('/lamb/v1/lti/launch', data=launch(env,{CLAIM+'roles':[next(iter(protocol.INSTRUCTOR_ROLES))]}),follow_redirects=False)
    assert response.status_code == 303, response.text
    assert urlsplit(response.headers['location']).path == '/lamb/v1/lti/link-account'
    token = parse_qs(urlsplit(response.headers['location']).query)['token'][0]
    page = api.client.get('/lamb/v1/lti/link-account', params={'token':token})
    assert page.status_code == 200 and 'password' in page.text


def test_lti11_reserved_ids_and_mixed_protocol_rejected(api, env, monkeypatch):
    monkeypatch.setattr(api.router.manager,'get_lti_credentials',lambda:('lamb','secret'))
    monkeypatch.setattr(api.router.manager,'validate_oauth_signature',lambda *a:True)
    response = api.client.post('/lamb/v1/lti/launch', data={'oauth_consumer_key':'lamb','resource_link_id':'lti13_r_attack','user_id':'u'})
    assert response.status_code == 400
    assert api.client.post('/lamb/v1/lti/launch',data={**launch(env),'oauth_consumer_key':'lamb'}).status_code == 400


def test_admin_registration_requires_system_admin(api, env):
    response = api.client.get('/lamb/v1/lti/registrations')
    assert response.status_code in (401,403)
    def forbidden():
        raise HTTPException(403,'Administrator required')
    api.app.dependency_overrides[api.admin.get_auth_context] = lambda: SimpleNamespace(require_system_admin=forbidden)
    assert api.client.post('/lamb/v1/lti/registrations',json=env.config).status_code == 403
    api.app.dependency_overrides[api.admin.get_auth_context] = lambda: SimpleNamespace(require_system_admin=lambda:None)
    response = api.client.post('/lamb/v1/lti/registrations',json={**env.config,'client_id':'new'})
    assert response.status_code == 201
    assert api.client.post('/lamb/v1/lti/registrations',json={**env.config,'client_id':'x','organization_ids':[999]}).status_code == 422
    assert api.client.post('/lamb/v1/lti/registrations',json={**env.config,'client_id':'x','jwks_url':'http://platform.example/jwks'}).status_code == 422


@pytest.mark.parametrize('changes', [
    {'token_type':None}, {'access_token':None}, {'expires_in':float('nan')},
    {'scope':'unrelated'}, {'expires_in':0}])
def test_invalid_oauth_responses_fail_cleanly(env, monkeypatch, changes):
    monkeypatch.setattr(network, 'request', lambda *a,**kw: {
        'access_token':'synthetic', 'token_type':'Bearer', 'expires_in':300, 'scope':SCORE_SCOPE, **changes})
    with pytest.raises(ValueError):
        grades.access_token(env.reg, {SCORE_SCOPE}, env.store)
    assert not grades._TOKENS


def test_multiple_audiences_require_matching_authorized_party(env):
    ctx = protocol.validate_launch(launch(env, {'aud':['client-1','another'], 'azp':'client-1'}), env.store)
    assert ctx['registration_id'] == env.rid


def test_deployment_hint_is_binding(env):
    transaction = env.store.new_transaction(env.reg, TARGET, 'deployment-2')
    with pytest.raises(ValueError, match='deployment mismatch'):
        protocol.validate_launch(launch(env, transaction=transaction), env.store)
    assert object_count(env) == 0


def test_service_failure_does_not_report_grade_success(env, monkeypatch):
    ctx = protocol.validate_launch(launch(env), env.store)
    env.store.save_grade_target(ctx['resource_link_id'],ctx['lms_user_id'],'student',ctx['grade_endpoint'])
    def fail(*args, **kwargs):
        raise ValueError('Platform service returned HTTP 503')
    monkeypatch.setattr(network,'request',fail)
    result = grades.send_score(ctx['resource_link_id'],'student',8,store=env.store)
    assert not result['success'] and '503' in result['error_message']


def test_relay_csp_allows_only_self_and_configured_chat_origin(env, monkeypatch):
    monkeypatch.setenv('OWI_PUBLIC_BASE_URL', 'https://chat.example:9443/some/path')
    response = protocol.browser_response('synthetic-id-token', 'state')
    policy = response.headers['content-security-policy']
    assert "form-action 'self' https://chat.example:9443;" in policy
    assert 'platform.example' not in policy
