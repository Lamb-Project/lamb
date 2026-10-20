"""lamb-0.8: a chat activity whose teachers can read transcripts tells each student once, before
the chat opens; entering the chat is the acceptance and is recorded (Marc, 2026-10-16)."""
import re
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.testclient import TestClient

import lamb.modules.chat as chat_pkg
from lamb.modules.chat import ChatModule, notice

ACTIVITY = {'id': 9, 'resource_link_id': 'rl-9', 'activity_name': 'Python tutor', 'owi_group_id': 'g',
            'chat_visibility_enabled': 1}
CTX = SimpleNamespace(resource_link_id='rl-9', username='charlie', display_name='Charlie Brown',
                      lms_user_id='lms-42', context_title='Introduction to Python')


@pytest.fixture
def mod(monkeypatch):
    users, launches = {}, []
    activity = dict(ACTIVITY)
    db = SimpleNamespace(
        get_lti_activity_by_resource_link=lambda rl: activity if rl == 'rl-9' else None,
        get_activity_user=lambda aid, email: users.get((aid, email)),
        record_student_consent=lambda aid, email: bool(users.get((aid, email))) and
        users[(aid, email)].update(consent_given_at=1) is None)

    def handle_student_launch(activity, username, display_name, lms_user_id=None, is_instructor=False):
        launches.append(username)
        users.setdefault((activity['id'], f'{username}@lti'), {'consent_given_at': None})
        return 'owi-token'

    m = ChatModule.__new__(ChatModule)
    m.db_manager = db
    m.service = SimpleNamespace(generate_student_email=lambda u, rl: f'{u}@lti',
                                handle_student_launch=handle_student_launch)
    monkeypatch.setattr(chat_pkg, 'ChatModule', lambda: m)
    monkeypatch.setattr(ChatModule, '_get_owi_redirect_url', lambda self, t: f'https://owi.x/complete?token={t}')
    app = FastAPI()
    app.include_router(notice.router, prefix='/lamb/v1/modules/chat')
    return SimpleNamespace(m=m, users=users, launches=launches, activity=activity,
                           client=TestClient(app, follow_redirects=False))


def _token(page):
    return re.search(r'name="token" value="([^"]+)"', page.body.decode()).group(1)


def test_first_launch_shows_the_notice_and_does_not_enter(mod):
    page = mod.m.on_student_launch(CTX)
    assert isinstance(page, HTMLResponse)
    body = page.body.decode()
    assert 'Your teacher can read your conversations' in body and 'By entering the chat you accept' in body
    assert 'action="' in body and '/lamb/v1/modules/chat/enter' in body
    assert mod.launches == []


def test_entering_records_acceptance_and_opens_the_chat(mod):
    token = _token(mod.m.on_student_launch(CTX))
    r = mod.client.post('/lamb/v1/modules/chat/enter', data={'token': token})
    assert r.status_code == 303 and r.headers['location'] == 'https://owi.x/complete?token=owi-token'
    assert mod.users[(9, 'charlie@lti')]['consent_given_at'] == 1
    again = mod.m.on_student_launch(CTX)
    assert isinstance(again, RedirectResponse) and mod.launches == ['charlie', 'charlie']


def test_no_notice_without_transcript_review(mod):
    mod.activity['chat_visibility_enabled'] = 0
    assert isinstance(mod.m.on_student_launch(CTX), RedirectResponse) and mod.launches == ['charlie']


def test_enter_refuses_a_bad_or_foreign_token(mod):
    assert mod.client.post('/lamb/v1/modules/chat/enter', data={'token': 'nonsense'}).status_code == 403
    other = notice.make_token({'id': 9, 'resource_link_id': 'rl-other'}, CTX)
    assert mod.client.post('/lamb/v1/modules/chat/enter', data={'token': other}).status_code == 404
    assert mod.launches == [] and mod.users == {}
