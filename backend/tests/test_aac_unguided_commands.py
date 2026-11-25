"""Issue #567: a guide is advice. A supported, authorized command runs without one.

The Moodle here is the synthetic fixture of the Moodle tests; no institutional system is called.
"""
import asyncio
import copy
import json
from unittest.mock import Mock

import pytest
import respx
from httpx import Response

from lamb.aac.authorization import allowed_commands
from lamb.aac.pack_build import validate_routing
from lamb.aac.pack_loader import load_pack
from lamb.aac.skill_routing import catalogue_prompt
from lamb.aac.liteshell.shell import LiteShell
from lamb.moodle.runtime import attach_to_agent
from tests.test_aac_legacy import agent, message, tool, turn
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores  # noqa: F401  (fixture)


class PackWithout:
    """The installed pack as an older one would be: the same content, minus the guides for some commands."""

    def __init__(self, drop, pack=None, defaults=None):
        self._pack = pack or load_pack()
        routing = copy.deepcopy(self._pack.data('routing.yaml'))
        routing['DEFAULT_SKILL'] = {k: v for k, v in routing['DEFAULT_SKILL'].items() if not drop(k)}
        routing['CAPABILITIES'] = {s: [k for k in keys if not drop(k)] for s, keys in routing['CAPABILITIES'].items()}
        routing['DEFAULT_SKILL'].update(defaults or {})
        self._routing = routing

    def data(self, relative):
        return self._routing if relative == 'routing.yaml' else self._pack.data(relative)

    def __getattr__(self, name):
        return getattr(self._pack, name)


def is_moodle(key):
    return key.startswith('moodle.')


def prepared(pack, messages=()):
    a, provider, shell = agent(list(messages))
    shell.allowed_commands = allowed_commands(['creator'])  # LAMB's role policy, as the session route sets it
    a.pack = pack
    a.skill_state = {'context': {}, 'brief': {'layers': ['creator'], 'glossary': pack.data('glossary/en.yaml')}}
    a.session_logger = Mock()
    return a, provider, shell


def unguided(a):
    return [call.args[1] for call in a.session_logger.log.call_args_list if call.args[0] == 'unguided_command']


def test_a_read_with_no_guide_runs_at_once_without_approval_and_is_recorded(stores):
    rt = runtime(stores)
    a, _, shell = prepared(PackWithout(is_moodle))
    attach_to_agent(a, rt.store)

    result = asyncio.run(a._execute_tool(tool('lamb moodle course list')))

    assert result['success'], result
    assert 'skill_loaded' not in result and 'awaiting_user_confirmation' not in result
    shell.execute.assert_awaited_once()
    assert unguided(a) == [{'command': 'moodle.course.list', 'reason': 'no_guide',
                            'pack_version': load_pack().version, 'outcome': 'succeeded'}]


@respx.mock
def test_the_whole_loop_lists_courses_from_the_synthetic_moodle_with_a_pack_that_has_no_moodle_guide(stores):
    rt = runtime(stores)
    moodle = respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=Response(200, json=[]))
    a, provider, _ = prepared(PackWithout(is_moodle),
                              [message(tools=[tool('lamb moodle course list')]), message('You are enrolled in no course.')])
    a.shell = LiteShell('', '', 'fixture@test', 1, user_id=7, moodle=rt, allowed_commands=allowed_commands(['creator']))
    attach_to_agent(a, rt.store)
    a.shell.moodle = rt  # the fixture's own key decrypts the fixture token

    answer = asyncio.run(turn(a, False, 'Which Moodle courses do I have?'))

    assert answer.endswith('You are enrolled in no course.')
    assert moodle.called, 'the supported read reached Moodle'
    tool_result = json.loads(next(m['content'] for m in a.conversation if m.get('role') == 'tool'))
    assert tool_result['success'], tool_result
    assert 'recipe' not in json.dumps(tool_result).lower()
    assert [row['outcome'] for row in unguided(a)] == ['succeeded']


def test_a_guide_that_exists_is_still_read_first_and_is_not_an_unguided_attempt(stores):
    rt = runtime(stores)
    a, _, shell = prepared(load_pack())
    attach_to_agent(a, rt.store)

    first = asyncio.run(a._execute_tool(tool('lamb moodle sync 10')))
    assert first['skill_loaded'] == 'moodle-triage' and not first['success']
    assert 'run the command again' in first['error']
    shell.execute.assert_not_awaited()
    assert asyncio.run(a._execute_tool(tool('lamb moodle sync 10')))['success']
    assert unguided(a) == []


def test_a_write_with_no_guide_still_waits_for_the_user(stores):
    a, _, shell = prepared(PackWithout(lambda key: key.startswith('assistant.')))

    result = asyncio.run(a._execute_tool(tool('lamb assistant delete 7')))

    assert result['awaiting_user_confirmation'] is True and result['action'] == 'assistant.delete'
    shell.execute.assert_not_awaited()
    assert a.pending_action['command'] == 'lamb assistant delete 7'
    assert unguided(a) == [{'command': 'assistant.delete', 'reason': 'no_guide',
                            'pack_version': load_pack().version, 'outcome': 'awaiting_approval'}]


def test_a_guide_reserved_for_another_role_does_not_stop_the_command():
    # The pack shows `test-lti-tools` to system administrators only; a creator's command goes on without it.
    a, _, shell = prepared(PackWithout(lambda key: key == 'assistant.get', defaults={'assistant.get': 'test-lti-tools'}))

    result = asyncio.run(a._execute_tool(tool('lamb assistant get 7')))

    assert result['success'], result
    shell.execute.assert_awaited_once()
    assert unguided(a)[0]['reason'] == 'guide_unavailable'


def test_real_limits_are_named_and_a_missing_guide_is_never_one_of_them(stores):
    rt = runtime(stores)
    a, _, shell = prepared(PackWithout(is_moodle))
    attach_to_agent(a, rt.store)

    # A Moodle operation the organization has not enabled (read-only connection).
    refused = asyncio.run(a._execute_tool(tool('lamb moodle forum post --forum-id 3 --subject x --message y')))
    assert not refused['success'] and "organization's Moodle settings" in refused['error']
    # A command that does not exist.
    unknown = asyncio.run(a._execute_tool(tool('lamb moodle course teleport')))
    assert not unknown['success']
    # A revoked integration.
    rt.store.disconnect()
    attach_to_agent(a, rt.store)
    disconnected = asyncio.run(a._execute_tool(tool('lamb moodle course list')))
    assert not disconnected['success'] and 'Moodle is not connected' in disconnected['error']

    shell.execute.assert_not_awaited()
    for answer in (refused, unknown, disconnected):
        assert 'recipe' not in answer['error'].lower() and 'improvise' not in answer['error'].lower()
    assert unguided(a) == []


def test_the_model_is_told_it_may_explore_within_what_is_authorized(stores):
    text = catalogue_prompt()
    assert 'the task is not forbidden' in text and 'lamb help' in text
    assert 'do not invent a workflow' not in text
    assert 'Never invent a command' in text and 'not user approval' in text

    rt = runtime(stores)
    a, _, _ = prepared(PackWithout(is_moodle))
    attach_to_agent(a, rt.store)
    capability = a.conversation[-1]['content']
    assert 'trial and error' not in capability and 'before acting' not in capability
    assert 'lamb help' in capability and 'Never invent a command' in capability


def test_a_pack_builds_when_a_supported_command_has_no_guide():
    validate_routing(PackWithout(is_moodle))
    validate_routing(PackWithout(lambda key: key.startswith('assistant.')))


def test_help_lists_the_installed_commands_whatever_the_pack_covers():
    pack = PackWithout(lambda key: True)
    shell = LiteShell(server_url='unused', token='fake', user_email='teacher@test', organization_id=4)
    shell.knowledge = {'pack': pack, 'brief': {'layers': ['creator']}}
    listed = asyncio.run(shell.execute('lamb help'))
    assert listed.success and 'lamb assistant create' in listed.data and 'lamb kb list' in listed.data
    assert asyncio.run(shell.execute('lamb assistant create --help')).success


def test_the_traces_give_the_candidates_for_new_guides_without_any_content(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    from lamb.aac.session_logger import SessionLogger
    from lamb.aac.unguided import summarize
    monkeypatch.setenv('AAC_LOG_PATH', str(tmp_path))
    monkeypatch.setenv('AAC_SESSION_LOGGING', 'true')

    a, _, _ = prepared(PackWithout(lambda key: key.startswith(('assistant.', 'kb.'))))
    a.session_logger = SessionLogger('session-one', 'teacher@test', 7)
    for command in ['lamb assistant get 7', 'lamb assistant get 9', 'lamb assistant delete 7']:
        asyncio.run(a._execute_tool(tool(command)))
        a.pending_action = None
    a.shell.execute.return_value.success = False
    asyncio.run(a._execute_tool(tool('lamb assistant get 404')))

    rows = {row['command']: row for row in summarize()}
    assert rows['assistant.get'] == {'command': 'assistant.get', 'reason': 'no_guide', 'pack_version': load_pack().version,
                                     'attempts': 3, 'succeeded': 2, 'failed': 1, 'awaiting_approval': 0, 'sessions': 1, 'users': 1}
    assert rows['assistant.delete']['awaiting_approval'] == 1
    assert summarize(since=datetime.utcnow() + timedelta(hours=1)) == []
    recorded = [line for path in tmp_path.rglob('*.jsonl') for line in path.read_text().splitlines() if 'unguided_command' in line]
    assert len(recorded) == 4 and not any('404' in line or 'lamb assistant' in line for line in recorded)
