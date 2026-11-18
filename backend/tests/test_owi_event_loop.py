"""LAMB must never leave its event loop waiting for Open WebUI.

Open WebUI calls LAMB on every chat turn (the conversation hooks) with a blocking
request from its single event loop. If LAMB at that moment waits for Open WebUI on
its own event loop, each service waits for the other and both stop answering.
These tests hold LAMB's side of that: no network call when the bridge object is
built, a time limit on every bridge call, and the launch, login and token-check
paths running in worker threads.
"""
import asyncio
import socket
import threading
import time

import pytest
import requests
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.testclient import TestClient

import config
from lamb import auth as lamb_auth
from lamb import auth_context, lti_router
from lamb.owi_bridge import owi_users
from lamb.owi_bridge.owi_users import OwiUserManager


def _on_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


class _Recorder:
    """Stands in for an activity module and records where each hook ran."""

    def __init__(self):
        self.calls = []

    def _record(self, name):
        self.calls.append((name, 'event loop' if _on_event_loop() else 'worker thread'))
        return RedirectResponse('https://chat.example/', status_code=303)

    def on_student_launch(self, ctx):
        return self._record('student')

    def on_instructor_launch(self, ctx):
        return self._record('instructor')

    def launch_user(self, **kwargs):
        self._record('enter chat')
        return 'https://chat.example/'


ACTIVITY = {'id': 7, 'status': 'active', 'activity_type': 'chat', 'organization_id': 1,
            'resource_link_id': 'rl-1', 'lis_outcome_service_url': None}


def _launch_form(roles):
    return {'oauth_consumer_key': 'key', 'resource_link_id': 'rl-1', 'roles': roles, 'user_id': 'u1',
            'ext_user_username': 'ana', 'lis_person_name_full': 'Ana Example'}


@pytest.fixture
def launch_app(monkeypatch):
    """The real unified LTI router with the LMS signature and the database stood in."""
    module = _Recorder()
    monkeypatch.setattr(lti_router.manager, 'get_lti_credentials', lambda: ('key', 'secret'))
    monkeypatch.setattr(lti_router.manager, 'validate_oauth_signature', lambda *a, **k: True)
    monkeypatch.setattr(lti_router.db_manager, 'get_lti_activity_by_resource_link', lambda rl: dict(ACTIVITY))
    monkeypatch.setattr(lti_router, '_get_activity_module', lambda activity: module)
    app = FastAPI()
    app.include_router(lti_router.router, prefix='/lamb/v1/lti')
    return app, module


def test_building_the_bridge_object_makes_no_network_call(monkeypatch):
    calls = []  # recorded, not raised: the bridge swallows exceptions from its HTTP calls
    monkeypatch.setattr(owi_users.requests, 'post', lambda *args, **kwargs: calls.append('post'))
    monkeypatch.setattr(owi_users.requests, 'get', lambda *args, **kwargs: calls.append('get'))
    monkeypatch.setattr(OwiUserManager, 'get_user_by_email', lambda self, email: {'email': email})
    OwiUserManager()
    assert calls == []


def test_every_bridge_call_carries_the_time_limit(monkeypatch):
    seen = {}

    class Answer:
        status_code = 200

        def json(self):
            return {'token': 't', 'email': 'ana@example.edu'}

    def record(name):
        def call(*args, **kwargs):
            seen[name] = kwargs.get('timeout')
            return Answer()
        return call
    monkeypatch.setattr(owi_users.requests, 'post', record('sign-in'))
    monkeypatch.setattr(owi_users.requests, 'get', record('token check'))
    bridge = OwiUserManager.__new__(OwiUserManager)
    bridge.OWI_API_BASE_URL = 'http://chat.invalid/api/v1'
    assert bridge.get_auth_token('ana@example.edu', 'Ana') == 't'
    assert bridge.get_user_auth('some-token')['email'] == 'ana@example.edu'
    assert seen == {'sign-in': config.OWI_HTTP_TIMEOUT_SECONDS, 'token check': config.OWI_HTTP_TIMEOUT_SECONDS}
    assert 0 < config.OWI_HTTP_TIMEOUT_SECONDS <= 60


@pytest.mark.parametrize('roles,hook', [('Learner', 'student'), ('Instructor', 'instructor')])
def test_launch_hooks_run_in_a_worker_thread(launch_app, roles, hook):
    app, module = launch_app
    response = TestClient(app).post('/lamb/v1/lti/launch', data=_launch_form(roles), follow_redirects=False)
    assert response.status_code == 303
    assert module.calls == [(hook, 'worker thread')]


def test_entering_the_chat_from_the_dashboard_runs_in_a_worker_thread(launch_app, monkeypatch):
    app, module = launch_app
    monkeypatch.setattr(lti_router, '_validate_lti_jwt', lambda token, kind: {
        'lti_resource_link_id': 'rl-1', 'lti_display_name': 'Ana', 'lti_lms_user_id': 'u1', 'lti_username': 'ana'})
    response = TestClient(app).get('/lamb/v1/lti/enter-chat', params={'resource_link_id': 'rl-1', 'token': 't'},
                                   follow_redirects=False)
    assert response.status_code == 303
    assert module.calls == [('enter chat', 'worker thread')]


def test_a_token_that_is_not_a_lamb_session_is_checked_off_the_event_loop(monkeypatch):
    where = []
    monkeypatch.setattr(auth_context, '_build_auth_context',
                        lambda token: where.append('event loop' if _on_event_loop() else 'worker thread'))
    # Not a LAMB JWT: the check goes to Open WebUI over HTTP, so it leaves the loop.
    asyncio.run(auth_context._auth_context('not-a-lamb-token'))
    # A LAMB session is resolved from LAMB's own database and stays inline.
    asyncio.run(auth_context._auth_context(lamb_auth.create_token({'sub': '1', 'email': 'ana@example.edu', 'role': 'user'})))
    assert where == ['worker thread', 'event loop']


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _serve(app):
    """Run an ASGI app on its own single event loop, as each service runs in production."""
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error', loop='asyncio'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        assert time.time() < deadline, 'test server did not start'
        time.sleep(0.02)
    return server, thread, f'http://127.0.0.1:{port}'


def test_a_launch_completes_while_the_chat_service_is_waiting_for_lamb(launch_app, monkeypatch):
    """The freeze itself, with two real servers, each on one event loop.

    The stand-in for Open WebUI answers the sign-in only after its own blocking
    call to LAMB returns, which is the position Open WebUI 0.5.6 is in whenever a
    chat turn is being handed to LAMB's conversation hook. A LAMB that makes the
    sign-in call on its event loop cannot answer that call, and neither side moves.
    """
    app, module = launch_app
    hook_calls = []

    @app.post('/hook')  # stands in for LAMB's conversation hook: any route on the same event loop
    async def hook():
        hook_calls.append(time.time())
        return {}

    lamb_server, lamb_thread, lamb_url = _serve(app)
    chat = FastAPI()

    @chat.post('/api/v1/auths/signin')
    async def signin():
        # Open WebUI has no time limit here; the test uses one only so that a
        # failing run ends by itself instead of leaving two stuck threads.
        requests.post(lamb_url + '/hook', json={}, timeout=20)
        return JSONResponse({'token': 'student-token'})

    chat_server, chat_thread, chat_url = _serve(chat)
    bridge = OwiUserManager.__new__(OwiUserManager)
    bridge.OWI_API_BASE_URL = chat_url + '/api/v1'

    def student_launch(ctx):  # the chat module's launch: the real sign-in call of the bridge
        token = bridge.get_auth_token('ana@example.edu', 'Ana Example')
        return RedirectResponse(f'https://chat.example/auth?token={token}', status_code=303)
    monkeypatch.setattr(module, 'on_student_launch', student_launch)

    try:
        started = time.time()
        response = requests.post(lamb_url + '/lamb/v1/lti/launch', data=_launch_form('Learner'),
                                 allow_redirects=False, timeout=6)
        elapsed = time.time() - started
    finally:
        lamb_server.should_exit = chat_server.should_exit = True
        lamb_thread.join(timeout=30)
        chat_thread.join(timeout=30)
    assert response.status_code == 303
    assert response.headers['location'].endswith('token=student-token')
    assert len(hook_calls) == 1
    assert elapsed < 5
