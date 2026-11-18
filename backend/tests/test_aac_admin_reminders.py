"""Reminders reflect current role/settings without provider calls or saved-state changes."""
import copy
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lamb.aac.admin_reminders import admin_reminders, reminder_context
from lamb.aac import router
from lamb.auth_context import AuthContext, get_auth_context
from lamb.aac.brief import session_brief
from lamb.aac.pack_loader import load_pack, render_prefix
from lamb.aac.session_guidance import POLICY_VERSION


@pytest.mark.parametrize('org_admin,system_admin,system_org,origin,count', [
    (False, False, False, '', 0), (True, False, False, '', 1),
    (False, True, False, '', 1), (True, True, True, '', 0),
    (True, False, False, 'https://moodle.example', 0),
])
def test_reminder_endpoint_only_reports_current_unconfigured_admin_org(org_admin, system_admin, system_org, origin, count):
    auth = AuthContext(user={'id': 7}, token_payload={}, is_org_admin=org_admin, is_system_admin=system_admin,
                       organization={'id': 4, 'slug': 'school', 'is_system': system_org,
                                     'config': {'lti_access': {'moodle_url': origin}}})
    app = FastAPI()
    app.dependency_overrides[get_auth_context] = lambda: auth
    app.include_router(router.router)
    response = TestClient(app).get('/aac/admin-reminders')
    assert response.status_code == 200
    reminders = response.json()['reminders']
    assert len(reminders) == count
    if count:
        assert reminders[0]['organization_id'] == 4
        assert reminders[0]['settings_path'].startswith('/org-admin?view=settings&section=lti-creator')
        assert ('org=school' in reminders[0]['settings_path']) == system_admin
        auth.organization['config']['lti_access']['moodle_url'] = 'https://moodle.example'
        assert admin_reminders(auth) == []
        assert reminder_context(auth) == ''


def test_existing_agent_reminder_refreshes_without_rewriting_pinned_state():
    auth = AuthContext(user={'id': 7, 'email': 'teacher@example.test'}, token_payload={}, is_org_admin=True,
                       organization={'id': 4, 'name': 'School', 'slug': 'school'})
    pack = load_pack()
    brief = session_brief(auth, 'en', {}, {}, pack)
    state = {'brief': brief, 'pack_version': pack.version, 'pack_hash': pack.fingerprint,
             'policy_version': POLICY_VERSION, 'system_prompt': render_prefix(pack, brief)}
    session = {'id': 'reminder-fixture', 'skill_info': state,
               'conversation': [{'role': 'user', 'content': 'Earlier work'}]}
    with patch.object(router, '_resolve_agent_llm', return_value=(SimpleNamespace(), 'fake')), patch.object(router, 'SessionLogger'):
        first = router._build_agent(auth, session)
        assert 'LMS origin has not been configured' in first.system_prompt
        assert 'LMS origin has not been configured' not in first.skill_state['system_prompt']
        resumed = dict(session, skill_info=copy.deepcopy(first.skill_state))
        auth.organization['config'] = {'lti_access': {'moodle_url': 'https://moodle.example'}}
        configured = router._build_agent(auth, resumed)
        assert 'LMS origin has not been configured' not in configured.system_prompt
        assert configured.conversation == session['conversation']
        auth.organization['config'] = {}
        auth.is_org_admin = False
        member = router._build_agent(auth, resumed)
        assert 'LMS origin has not been configured' not in member.system_prompt
