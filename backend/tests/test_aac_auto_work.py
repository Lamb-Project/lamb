"""Task approval, exact grants, persistence and accounting without provider calls."""
import asyncio
import copy
import json
import shlex
from types import SimpleNamespace as N
from unittest.mock import AsyncMock

import pytest
from lamb.aac.agent.loop import AgentLoop
from lamb.aac.auto_work import AutoWork, signature, substitute
from lamb.aac.approval_controls import action_id, validate_decision
from lamb.aac.liteshell.shell import LiteShell
from lamb.aac.resource_names import choose, resolve


def tool(command):
    return N(id='fixture-call', function=N(name='execute_command', arguments=json.dumps({'command': command})))


class HTTP:
    def __init__(self):
        self.cases, self.runs, self.evaluations, self.calls = [], [], [], 0
        self.assistant = {'id': 7, 'name': '7_prova_carles', 'system_prompt': 'Original', 'description': '',
                          'prompt_template': '', 'RAG_Top_k': 3, 'RAG_collections': '', 'metadata': '{}'}
        self.fail = False

    async def get(self, path, **kwargs):
        if path.endswith('/get_assistants'): return {'assistants': [self.assistant], 'total_count': 1}
        if path.endswith('/shared-with-me'): return []
        if path.endswith('/get_assistant/7'): return dict(self.assistant)
        if path.endswith('/snapshot'): return {'fields': dict(self.assistant), 'revision': signature(self.assistant)}
        if path.endswith('/scenarios'): return copy.deepcopy(self.cases)
        if path.endswith('/runs'): return copy.deepcopy(self.runs)
        raise ValueError(path)

    async def put(self, path, json=None, **kwargs):
        self.assistant.update(json or {})
        return {'success': True}

    async def post(self, path, json=None, **kwargs):
        body = json or {}
        if path.endswith('/scenarios'):
            case = {'id': 'case_' + str(len(self.cases) + 1), 'assistant_id': 7, **body}
            self.cases.append(case)
            return dict(case)
        if path.endswith('/tests/run'):
            self.calls += 1
            if self.fail:
                self.fail = False
                raise ValueError('Synthetic provider failure')
            run = {'id': 'run_' + str(len(self.runs) + 1), 'assistant_id': 7,
                   'scenario_id': body['scenario_id'], 'response': 'Synthetic answer'}
            self.runs.append(run)
            return dict(run)
        if path.endswith('/evaluate'):
            self.evaluations.append(body)
            return {'id': 'evaluation_' + str(len(self.evaluations))}
        if path.endswith('/completions'):
            self.calls += 1
            return {'choices': [{'message': {'content': 'Synthetic answer'}}]}
        raise ValueError(path)


def agent():
    shell = LiteShell('unused', 'fixture-token', 'teacher@example.test', 1, user_id=2, session_id='fixture')
    http = HTTP()
    shell._http_client = http
    shell.model_result = lambda command, payload: payload
    a = AgentLoop(shell, None, 'fixture', skill_state={'execution': {'mode': 'auto'}}, session_id='fixture')
    a.required_skill = lambda *args: None
    a.auto_work = AutoWork(a)
    shell.knowledge['auto_work'] = a.auto_work
    snapshots = []
    a.checkpoint = lambda: snapshots.append(copy.deepcopy(a.skill_state))
    return a, http, snapshots


def proposal(**overrides):
    return {'title': 'Test and report', 'steps': [
        {'id': 'create', 'title': 'Save a case', 'command': 'lamb test add 7 Normal --message hello --expected greeting'},
        {'id': 'run', 'title': 'Run it', 'command': 'lamb test run 7 --case @create.id', 'after': 'create'}],
        'assistant_calls': 10, 'tool_estimate': 8, 'evaluate': True,
        'report': {'title': 'Test report', 'assistant_id': '7'}, **overrides}


async def prepare(a, payload):
    return await a._execute_tool(tool('lamb plan prepare --json ' + shlex.quote(json.dumps(payload))))


@pytest.mark.asyncio
async def test_one_approval_covers_creation_run_evaluation_and_report():
    a, h, saved = agent()
    result = await prepare(a, proposal())
    assert result['awaiting_user_confirmation'] and not h.cases
    await a._resolve_pending_action('yes')
    result = await a._execute_tool(tool('lamb plan execute'))
    assert result['success'], result
    assert len(h.cases) == len(h.runs) == 1 and not a.pending_action
    result = await a._execute_tool(tool('lamb test evaluate run_1 7 good --notes Evidence'))
    assert result['success'] and not a.pending_action
    assert h.evaluations[0]['evaluator'] == 'legatus'
    result = await a._execute_tool(tool('lamb report save --content "One actual result"'))
    assert result['success'] and not a.pending_action
    assert result['data']['run_ids'] == ['run_1']
    result = await a._execute_tool(tool('lamb plan finish'))
    assert result['success'] and a.auto_work.task['status'] == 'completed'
    assert a.auto_work.task['calls'] == h.calls == 1
    assert any(s['execution']['journal'][0]['status'] == 'running' for s in saved if s['execution']['journal'])


@pytest.mark.asyncio
async def test_concrete_plan_does_not_approve_other_writes_or_other_runs():
    a, h, _ = agent()
    await prepare(a, proposal())
    await a._resolve_pending_action('yes')
    assert (await a._execute_tool(tool('lamb assistant update 7 --system-prompt unrelated')))['awaiting_user_confirmation']
    assert h.assistant['system_prompt'] == 'Original'
    a.pending_action = None
    assert (await a._execute_tool(tool('lamb test evaluate foreign_run 7 good')))['awaiting_user_confirmation']
    assert not h.evaluations


@pytest.mark.asyncio
async def test_read_plan_has_no_approval_and_can_use_more_than_ten_tools():
    a, _, _ = agent()
    steps = [{'id': 'read_' + str(i), 'command': 'lamb assistant get 7'} for i in range(12)]
    result = await prepare(a, {'title': 'Inspect', 'steps': steps})
    assert result['success'] and not a.pending_action
    result = await a._execute_tool(tool('lamb plan execute'))
    assert result['success'] and all(s['status'] == 'completed' for s in result['data']['steps'])
    assert a.auto_work.task['tools'] == 12 and a.auto_work.task['calls'] == 0


@pytest.mark.asyncio
async def test_calls_nine_ten_eleven_and_resumption_keep_allowance():
    a, h, _ = agent()
    for _ in range(10):
        result = await a._execute_tool(tool('lamb assistant chat 7 --message hello'))
        assert result['success'] and not a.pending_action, result
    assert a.auto_work.task['calls'] == 10
    a.auto_work = AutoWork(a)  # restored request boundary; no reset
    a.shell.knowledge['auto_work'] = a.auto_work
    result = await a._execute_tool(tool('lamb assistant chat 7 --message eleventh'))
    assert result['awaiting_user_confirmation'] and a.pending_action['call_limit'] == 11
    assert h.calls == 10
    await a._resolve_pending_action('yes')
    assert h.calls == a.auto_work.task['calls'] == 11


@pytest.mark.asyncio
async def test_larger_approved_plan_does_not_pause_at_eleven():
    a, h, _ = agent()
    steps = [{'id': f'call_{i}', 'command': 'lamb assistant chat 7 --message hello'} for i in range(12)]
    await prepare(a, {'title': 'Twelve calls', 'steps': steps, 'assistant_calls': 12})
    assert a.pending_action
    await a._resolve_pending_action('yes')
    await a._execute_tool(tool('lamb plan execute'))
    assert h.calls == 12 and not a.pending_action


@pytest.mark.asyncio
async def test_test_batch_freezes_cases_and_approves_cost_together():
    a, h, _ = agent()
    h.cases = [{'id': f'case_{i}', 'title': str(i)} for i in range(11)]
    result = await a._execute_tool(tool('lamb test run 7'))
    assert result['awaiting_user_confirmation'] and a.pending_action['call_limit'] == 11
    h.cases.append({'id': 'late_case', 'title': 'Added after approval was prepared'})
    await a._resolve_pending_action('yes')
    assert h.calls == 11 and len(h.runs) == 11 and a.auto_work.task['calls'] == 11
    assert not any(r['scenario_id'] == 'late_case' for r in h.runs)


@pytest.mark.asyncio
async def test_retry_branch_runs_without_second_approval():
    a, h, _ = agent()
    p = proposal()
    p['steps'].append({'id': 'retry', 'title': 'Retry once', 'command': 'lamb test run 7 --case @create.id', 'after': 'run', 'when': 'failure'})
    await prepare(a, p)
    await a._resolve_pending_action('yes')
    h.fail = True
    result = await a._execute_tool(tool('lamb plan execute'))
    assert [s['status'] for s in result['data']['steps']] == ['completed', 'failed', 'completed']
    assert h.calls == 2 and not a.pending_action


@pytest.mark.asyncio
async def test_rejected_or_stale_plan_does_not_execute():
    a, h, _ = agent()
    await prepare(a, proposal())
    original = action_id(a.pending_action)
    a.pending_action['plan']['assistant_calls'] = 11
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        validate_decision({'pending_action': a.pending_action}, {'approval': {'action_id': original, 'decision': 'approve'}})
    await a._resolve_pending_action('no')
    assert not h.cases
    assert not (await a._execute_tool(tool('lamb plan execute')))['success']


@pytest.mark.asyncio
async def test_journal_preserves_prompt_and_uncertain_write_is_not_repeated():
    a, h, _ = agent()
    await a._execute_tool(tool('lamb assistant update 7 --system-prompt New'))
    await a._resolve_pending_action('yes')
    entry = a.auto_work.state['journal'][-1]
    assert entry['before']['fields']['system_prompt'] == 'Original'
    assert entry['after']['fields']['system_prompt'] == 'New'
    entry['status'] = 'uncertain'
    result = await a.auto_work.execute(entry['command'], confirmed=True)
    assert not result.success and 'uncertain' in result.error
    await a.auto_work.reconcile()
    assert entry['status'] == 'completed'


@pytest.mark.asyncio
async def test_uncertain_plan_does_not_replay_creation_on_resume():
    a, h, _ = agent()
    await prepare(a, proposal())
    await a._resolve_pending_action('yes')
    await a._execute_tool(tool('lamb plan execute'))
    await a._execute_tool(tool('lamb plan execute'))
    assert len(h.cases) == len(h.runs) == 1
    a.auto_work.task['plan']['steps'][0]['status'] = 'uncertain'
    result = await a._execute_tool(tool('lamb plan execute'))
    assert not result['success'] and len(h.cases) == 1


@pytest.mark.asyncio
async def test_declared_calls_cannot_understate_conditional_steps():
    a, _, _ = agent()
    p = proposal(assistant_calls=0)
    result = await prepare(a, p)
    assert not result['success'] and not a.pending_action


@pytest.mark.parametrize('value', ['prova carles', 'Prova_Carles', 'PROVA-CARLES'])
def test_unique_normalized_name(value):
    assert choose([{'id': 7, 'name': '7_prova_carles'}], value, kind='assistant')['id'] == 7


def test_name_collisions_are_not_silent():
    with pytest.raises(ValueError, match='Ambiguous'):
        choose([{'id': 7, 'name': '7_prova_carles'}, {'id': 8, 'name': '8_prova-carles'}], 'prova carles', kind='assistant')


@pytest.mark.asyncio
async def test_resolver_reads_beyond_first_page():
    async def get(path, **kwargs):
        if path.endswith('shared-with-me'): return []
        offset = kwargs['params']['offset']
        return {'assistants': [{'id': i + 1, 'name': 'prova_carles' if i == 100 else f'unrelated_{i}'}
                               for i in range(offset, min(offset + 100, 101))], 'total_count': 101}
    assert await resolve(N(get=get), 'assistant', 'prova carles') == '101'


def test_result_reference_is_an_identifier_not_injected_command():
    steps = [{'id': 'a', 'status': 'completed', 'result': {'id': '7; lamb assistant delete 8'}}]
    with pytest.raises(ValueError, match='identifier'):
        substitute('lamb assistant get @a.id', steps)


@pytest.mark.asyncio
async def test_role_denial_applies_before_plan_preparation():
    a, h, _ = agent()
    a.shell.allowed_commands = {'plan.prepare', 'assistant.get'}
    result = await prepare(a, proposal())
    assert not result['success'] and not h.cases and not a.pending_action


@pytest.mark.asyncio
async def test_names_are_frozen_even_when_step_contains_result_reference():
    a, h, _ = agent()
    p = proposal()
    p['steps'][1]['command'] = 'lamb test run "prova carles" --case @create.id'
    await prepare(a, p)
    assert a.pending_action['plan']['steps'][1]['command'].startswith('lamb test run 7 ')
    await a._resolve_pending_action('yes')
    assert (await a._execute_tool(tool('lamb plan execute')))['success']
    assert len(h.runs) == 1 and not a.pending_action


@pytest.mark.asyncio
async def test_final_report_requires_completed_steps_and_evaluations():
    a, h, _ = agent()
    await prepare(a, proposal())
    await a._resolve_pending_action('yes')
    assert not (await a._execute_tool(tool('lamb report save --content premature')))['success']
    await a._execute_tool(tool('lamb plan execute'))
    assert not (await a._execute_tool(tool('lamb report save --content unevaluated')))['success']
    await a._execute_tool(tool('lamb test evaluate run_1 7 good --notes Evidence'))
    assert (await a._execute_tool(tool('lamb report save --content Final')))['success']
    with pytest.raises(ValueError, match='final report'):
        await a.auto_work.prepare(proposal(), extend=True)


@pytest.mark.asyncio
async def test_extension_preserves_grants_and_counts_unexecuted_calls():
    a, h, _ = agent()
    await prepare(a, proposal())
    await a._resolve_pending_action('yes')
    extension = {'title': 'Add a read', 'steps': [{'id': 'read', 'command': 'lamb assistant get 7'}]}
    p = await a.auto_work.prepare(extension, extend=True)
    assert p['evaluate'] and p['report'] and not p['needs_approval']
    assert len(p['steps']) == 3
    a.auto_work.task['calls'] = 10
    with pytest.raises(ValueError, match='cumulative'):
        await a.auto_work.prepare({**extension, 'assistant_calls': 10}, extend=True)


@pytest.mark.asyncio
async def test_cancel_stops_remaining_steps_and_retains_changes():
    a, h, _ = agent()
    await prepare(a, proposal())
    await a._resolve_pending_action('yes')
    await a._execute_tool(tool('lamb plan cancel'))
    assert not (await a._execute_tool(tool('lamb plan execute')))['success']
    assert not h.cases and a.auto_work.task['status'] == 'cancelled'


@pytest.mark.asyncio
async def test_finish_saves_a_verified_resource_destination():
    a, h, _ = agent()
    result = await a._execute_tool(tool('lamb plan finish --resource assistant --id 7 --tab properties'))
    assert result['success']
    assert result['data']['result']['destination'] == {'resource': 'assistant', 'id': '7', 'tab': 'properties'}


@pytest.mark.asyncio
async def test_read_extension_cannot_renew_an_expired_write_grant():
    a, _, _ = agent()
    await prepare(a, proposal())
    await a._resolve_pending_action('yes')
    a.auto_work.task['plan']['expires'] = 0
    with pytest.raises(ValueError, match='expired'):
        await a.auto_work.prepare({'title': 'Read', 'steps': [{'id': 'read', 'command': 'lamb assistant get 7'}]}, extend=True)


@pytest.mark.asyncio
async def test_attached_kb_name_is_frozen_before_plan_approval():
    a, h, _ = agent()
    original = h.get
    async def get(path, **kwargs):
        if path.endswith('/knowledgebases/user'):
            return {'knowledge_bases': [{'id': 9, 'name': 'prova_carles'}]}
        if path.endswith('/knowledgebases/shared'):
            return {'knowledge_bases': []}
        return await original(path, **kwargs)
    h.get = get
    await prepare(a, proposal(steps=[{'id': 'attach', 'command': 'lamb assistant update 7 --rag-collections "prova carles"'}]))
    assert a.pending_action['plan']['steps'][0]['command'] == 'lamb assistant update 7 --rag-collections 9'
