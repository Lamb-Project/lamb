"""Activity and module tokens share the Creator's signing key but are never Creator sessions,
and each module accepts only the tokens issued for it and for the activity in the request."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lamb import auth as lamb_auth
from lamb.auth_context import _build_auth_context
from lamb.modules.file_evaluation import router as file_eval
from lamb.token_dealer import lti as llm_access

CREATOR = {'sub': '1', 'email': 'admin@example.edu', 'role': 'admin'}
ACTIVITY_TOKENS = [
    {'scope': 'llm_access', 'type': 'student', 'activity_id': 7, 'lms_user_id': 'u'},
    {'scope': 'chat', 'type': 'transcript_notice', 'activity_id': 7},
    {'lti_type': 'dashboard', 'lti_activity_id': 7},
    {'lti_type': 'setup', 'lti_resource_link_id': 'rl'},
    {'lti_type': 'file_eval', 'lti_activity_id': 7},
]


def test_creator_sessions_are_recognised_and_activity_tokens_are_not():
    assert lamb_auth.is_creator_session(CREATOR)
    assert lamb_auth.is_creator_session({**CREATOR, 'takeover': {'id': 'x'}})
    assert not lamb_auth.is_creator_session(None)
    assert not lamb_auth.is_creator_session({})
    for claims in ACTIVITY_TOKENS:
        assert not lamb_auth.is_creator_session({**CREATOR, **claims})


def test_llm_access_launch_tokens_carry_no_creator_identity():
    for instructor in (True, False):
        location = llm_access.launch_redirect('https://lamb.example', {'id': 7}, instructor, 'lms-1',
                                              'admin@example.edu', 'Ana').headers['location']
        payload = lamb_auth.decode_token(location.split('token=')[1])
        assert 'email' not in payload
        assert payload['lms_email'] == 'admin@example.edu'
        assert not lamb_auth.is_creator_session(payload)


@pytest.mark.parametrize('claims', ACTIVITY_TOKENS)
def test_creator_authentication_refuses_activity_tokens_even_with_a_matching_email(claims):
    token = lamb_auth.create_token({**claims, 'email': 'admin@example.edu'})
    with patch('lamb.auth_context._db') as db:
        db.get_creator_user_by_email.return_value = {'id': 1, 'email': 'admin@example.edu', 'role': 'admin', 'enabled': True}
        assert _build_auth_context(token) is None
        db.get_creator_user_by_email.assert_not_called()


@pytest.mark.parametrize('claims', ACTIVITY_TOKENS)
def test_the_assistant_router_path_refuses_activity_tokens_too(claims):
    from creator_interface import assistant_router
    token = lamb_auth.create_token({**claims, 'email': 'admin@example.edu'})
    with patch.object(assistant_router, 'db_manager') as db:
        db.get_creator_user_by_email.return_value = {'id': 1, 'email': 'admin@example.edu', 'role': 'admin', 'enabled': True}
        assert assistant_router.get_creator_user_from_token('Bearer ' + token) is None
        db.get_creator_user_by_email.assert_not_called()


def _request(token):
    return SimpleNamespace(headers={'Authorization': 'Bearer ' + token})


def test_file_evaluation_accepts_only_its_own_tokens():
    own = lamb_auth.create_token({'lti_type': 'file_eval', 'lti_activity_id': 7, 'lti_user_email': 's@example.edu'})
    assert file_eval._decode_jwt(_request(own))['lti_activity_id'] == 7
    dashboard = lamb_auth.create_token({'lti_type': 'dashboard', 'lti_activity_id': 7})
    assert file_eval._decode_jwt(_request(dashboard))['lti_type'] == 'dashboard'
    for foreign in (CREATOR, {'scope': 'llm_access', 'type': 'manage', 'activity_id': 7}, {'lti_type': 'setup'}):
        with pytest.raises(HTTPException) as refused:
            file_eval._decode_jwt(_request(lamb_auth.create_token(foreign)))
        assert refused.value.status_code == 401


def test_file_evaluation_binds_every_role_to_the_token_activity():
    student = {'lti_type': 'file_eval', 'lti_activity_id': 7}
    file_eval._assert_activity(student, 7)
    for payload, activity in ((student, 8), ({'lti_type': 'file_eval'}, 7)):
        with pytest.raises(HTTPException) as refused:
            file_eval._assert_activity(payload, activity)
        assert refused.value.status_code == 403


def test_student_routes_refuse_another_activity_before_touching_data():
    app = FastAPI()
    app.include_router(file_eval.router)
    client = TestClient(app)
    token = lamb_auth.create_token({'lti_type': 'file_eval', 'lti_activity_id': 7, 'lti_user_email': 's@example.edu'})
    headers = {'Authorization': 'Bearer ' + token}
    with patch.object(file_eval, '_service') as service:
        assert client.get('/submissions/me?activity_id=8', headers=headers).status_code == 403
        assert client.get('/submissions/my-file/download?activity_id=8', headers=headers).status_code == 403
        assert client.post('/submissions/join?activity_id=8', headers=headers, json={'group_code': 'ABC'}).status_code == 403
        assert client.get('/activities/8/view', headers=headers).status_code == 403
        assert client.post('/activities/8/submissions', headers=headers,
                           files={'file': ('a.pdf', b'%PDF-1.4', 'application/pdf')}).status_code == 403
        assert not service.method_calls


def test_new_student_chat_accounts_get_a_random_password():
    """Regression of #411: the module port had brought back a password derived from the activity id."""
    from unittest.mock import MagicMock
    from lamb.modules.chat.service import ChatModuleService
    service = object.__new__(ChatModuleService)
    service.owi_user_manager = MagicMock()
    service.owi_user_manager.get_user_by_email.return_value = None
    service.owi_user_manager.create_user.return_value = None      # stop right after the creation call
    activity = {'id': 7, 'resource_link_id': 'rl-7'}
    passwords = []
    for _ in range(2):
        assert service.handle_student_launch(activity, 'ana', 'Ana') is None
        passwords.append(service.owi_user_manager.create_user.call_args.kwargs['password'])
    assert all('lti_activity' not in p and len(p) >= 32 for p in passwords)
    assert passwords[0] != passwords[1]
