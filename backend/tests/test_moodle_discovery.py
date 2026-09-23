"""Cumulative roster/help regression bundle: synthetic only, no model calls."""
import asyncio
import json
from unittest.mock import patch

import pytest
import respx
from httpx import Response
from urllib.parse import parse_qs

from tests.test_moodle_store import stores
from tests.test_moodle_runtime import runtime
from lamb.moodle.discovery import IDENTITY, ROSTER, filter_keys, requirements, help_result
from lamb.moodle.contract import all_specs
from lamb.aac.liteshell.shell import LiteShell, prepare_command
from lamb.aac.authorization import ActionAuthorizer


def set_functions(rt, names):
    snap = rt.store.snapshot()
    record = dict(snap['record'])
    if names is None:
        record.pop('functions', None)
    else:
        record['functions'] = sorted(names)
    rt.store.save(record, expected_generation=snap['generation'], expected_policy=snap['policy'])


@pytest.mark.parametrize('command,path', [('moodle --help',''), ('moodle -h',''),
    ('moodle enrol --help','enrol'), ('moodle enrol list-users --help','enrol.list-users')])
def test_standard_help_parses_without_required_objects(command,path):
    key, _, params, _ = prepare_command(command)
    assert key == 'moodle.help' and params == {'path':path}
    assert ActionAuthorizer().check(key) == 'auto'


@pytest.mark.parametrize('command', ['moodle --help --course 197',
    'moodle enrol list-users 197 --help', 'moodle --help enrol', 'moodle enrol --role student --help'])
def test_help_rejects_object_queries_and_extra_arguments(command):
    with pytest.raises(ValueError):
        prepare_command(command)


def test_every_command_has_a_reviewed_capability_mapping():
    special = {'analytics.run','analytics.start','analytics.continue','content.list','sync'}
    assert set(all_specs()) == set(requirements()) | special


@respx.mock
def test_help_is_local_and_policy_and_token_filtered(stores):
    rt = runtime(stores)
    set_functions(rt, IDENTITY | ROSTER | {'mod_forum_add_discussion'})
    shell = LiteShell('', '', 'fixture@test',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    result = asyncio.run(shell.execute('moodle enrol --help'))
    assert result.success, result.error
    assert {r['command'] for r in result.data['commands']} == {
        'moodle enrol list-users', 'moodle enrol my-courses'}
    assert not respx.calls
    full = asyncio.run(shell.execute('moodle --help'))
    assert 'moodle forum post' not in json.dumps(full.data)
    assert 'moodle assign grade' not in json.dumps(full.data)
    detail = asyncio.run(shell.execute('moodle enrol list-users --help'))
    assert detail.success and '--role' in detail.data['help']
    assert 'COURSE_ID' in detail.data['help'] and not detail.result_binding
    assert not respx.calls


@respx.mock
@pytest.mark.parametrize('names', [None, set(), {'core_enrol_get_users_courses'}])
def test_missing_unknown_capabilities_never_advertise_or_execute_roster(stores,names):
    rt = runtime(stores); set_functions(rt,names)
    shell = LiteShell('', '', 'fixture@test',1,user_id=7,moodle=rt)
    help_ = asyncio.run(shell.execute('moodle --help'))
    assert help_.success and 'moodle enrol list-users' not in json.dumps(help_.data)
    result = asyncio.run(shell.execute('moodle enrol list-users 10'))
    assert not result.success and not respx.calls
    if names is None:
        assert 'Reconnect' in help_.data['notice']


@respx.mock
def test_stale_shell_rechecks_token_and_policy(stores):
    rt = runtime(stores)
    shell = LiteShell('', '', 'fixture@test',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    set_functions(rt, IDENTITY)
    assert not asyncio.run(shell.execute('moodle enrol list-users --help')).success
    assert not asyncio.run(shell.execute('moodle enrol list-users 10')).success
    rt.store.disconnect()
    assert not asyncio.run(shell.execute('moodle --help')).success
    assert not respx.calls


def test_recipe_choices_are_filtered_without_mutating_global_parser():
    record = {'functions': sorted(IDENTITY | ROSTER)}
    keys = filter_keys(set(all_specs()),record)
    result = help_result(keys,record,'analytics.run')
    assert 'course-access' in result['help'] and 'resource-reach' not in result['help']
    recipe = next(param for param in all_specs()['analytics.run'].parser.params if param.name == 'recipe')
    assert 'resource-reach' in recipe.type.choices
    with pytest.raises(PermissionError):
        help_result(keys,record,'forum')


@respx.mock
@pytest.mark.parametrize('teacher', [True, False])
def test_roster_students_all_and_actual_scope_denial(stores,teacher):
    rt=runtime(stores); set_functions(rt,IDENTITY | ROSTER)
    calls=[]
    def reply(request):
        fn=parse_qs(request.content.decode())['wsfunction'][0];calls.append(fn)
        data={'core_enrol_get_users_courses':[{'id':10,'shortname':'fixture','fullname':'Fixture'}],
              'core_user_get_course_user_profiles':[{'id':70,'roles':[{'shortname':'editingteacher' if teacher else 'student'}]}],
              'core_enrol_get_enrolled_users':[
                  {'id':70,'fullname':'Fixture Teacher','roles':[{'shortname':'editingteacher'}]},
                  {'id':71,'fullname':'Fixture Student','roles':[{'shortname':'student'}]},
                  {'id':72,'fullname':'Fixture Observer','roles':[{'shortname':'observer'}]}]}[fn]
        return Response(200,json=data)
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=reply)
    shell=LiteShell('', '', 'fixture@test',1,user_id=7,moodle=rt)
    students=asyncio.run(shell.execute('moodle enrol list-users 10 --role student'))
    if teacher:
        assert students.success and [u['id'] for u in students.data]==[71]
        everyone=asyncio.run(shell.execute('moodle enrol list-users 10'))
        assert everyone.success and len(everyone.data)==3
    else:
        assert not students.success and 'instructor' in students.error
        assert 'core_enrol_get_enrolled_users' not in calls


def test_roster_recipe_and_filtered_examples():
    from lamb.aac.pack_loader import load_pack
    from lamb.moodle.workflow import render_permissions
    text=load_pack().text('skills/moodle_triage.md')
    assert 'moodle enrol list-users COURSE_ID --role student' in text
    assert 'Missing instructions are not proof of missing permissions' in text
    assert 'at most ONE' in text
    filtered=render_permissions(text,{'moodle.course.get','moodle.help'})
    assert '\nmoodle enrol list-users COURSE_ID' not in filtered


@pytest.mark.parametrize('streaming',[False,True])
def test_agent_enforces_one_help_lookup_and_resets_next_turn(streaming):
    from tests.test_aac_legacy import agent, message, tool, turn
    a, provider, shell = agent([
        message(tools=[tool('moodle enrol --help',ident='one'),tool('moodle --help',ident='two')]),
        message('Done'), message(tools=[tool('moodle enrol --help',ident='three')]), message('Done')])
    asyncio.run(turn(a,streaming))
    assert shell.execute.await_count == 1
    assert 'budget exhausted' in json.dumps(a.conversation)
    asyncio.run(turn(a,streaming))
    assert shell.execute.await_count == 2


@respx.mock
def test_write_requires_both_policy_and_function_and_keeps_confirmation(stores):
    rt=runtime(stores)
    functions=IDENTITY | {'core_course_get_contents','mod_forum_add_discussion'}
    set_functions(rt,functions)
    assert 'moodle.forum.post' not in rt.available()
    rt.store.configure({'enabled':True,'base_url':'https://moodle.test','mode':'full','write_groups':['forum']})
    assert 'moodle.forum.post' in rt.available()
    assert ActionAuthorizer().check('moodle.forum.post') == 'ask'
    set_functions(rt,functions-{'mod_forum_add_discussion'})
    assert 'moodle.forum.post' not in rt.available()
    assert not respx.calls
