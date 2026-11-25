"""Issue #568: a plan is given as fields, and LAMB writes its commands.

The first test is derived from the exchange saved on public dev on 25 November 2026: the model wrote
`lamb plan prepare --json '{...}` twice, with a valid plan and no closing quotation mark, and the
second time it had replaced every space by an underscore. The words are synthetic; the shape is real.
"""
import copy
import json
import shlex
from types import SimpleNamespace as N

import pytest

from lamb.aac.auto_work import PLAN_ATTEMPTS
from lamb.aac.liteshell.shell import ShellResult, prepare_command
from lamb.aac.structured import plan_from_structure, render_step
from tests.test_aac_auto_work import agent, tool
from tests.test_aac_legacy import Provider, message

MODULES = [201, 202, 203, 204, 205, 206, 207]
KB_NAME = "Transformers course PDFs"
KB_DESCRIPTION = "The seven readings of the course (unit 1), as the teacher's students see them."
PROMPT = ('You are a patient tutor for "Transformers, LLMs & RAG".\n'
          "Answer only from the course readings; when they don't cover a question, say so.\n"
          'Cite the reading as {title} (p. N). Never invent a page: C:\\readings\\unit1 is not a source.\n'
          'Saluda en català si l’estudiant ho fa: «Bon dia!» → respon igual. Use {{RANDOM:25-70}} only when asked.')


def plan_tool(payload, ident='plan-call'):
    return N(id=ident, function=N(name='prepare_plan', arguments=json.dumps(payload)))


def course_plan(**changes):
    """What the professor asked for: import seven course PDFs into a new knowledge base and build an assistant on it."""
    plan = {'title': 'Assistant grounded in the course PDFs', 'steps': [
        {'id': 'import_docs', 'title': 'Import the seven PDFs into a new knowledge base', 'operation': 'moodle import course',
         'arguments': [10], 'options': {'module': MODULES, 'new_kb': KB_NAME, 'description': KB_DESCRIPTION}},
        {'id': 'create_assistant', 'title': 'Create the assistant on that knowledge base', 'operation': 'assistant create',
         'after': 'import_docs', 'arguments': ["Transformers tutor (teacher's draft)"],
         'options': {'description': 'Answers from the seven readings of unit 1.', 'system_prompt': PROMPT,
                     'rag_processor': 'simple_rag', 'rag_collections': {'ref': 'import_docs.destination.kb_id'}}},
        {'id': 'verify', 'title': 'Read the saved assistant back', 'operation': 'assistant get', 'after': 'create_assistant',
         'arguments': [{'ref': 'create_assistant.assistant_id'}]}],
        'assistant_calls': 10, 'tool_estimate': 12, 'evaluate': False}
    plan.update(changes)
    return plan


def moodle_agent(batch_status='completed', messages=()):
    """The plan fixture of the Auto tests, with a synthetic Moodle: the import and the assistant are answered
    here, and every command that reaches execution is recorded exactly as it arrived."""
    a, http, saved = agent()
    a.llm_client = Provider(list(messages))
    reviewed, executed = [], []
    a.shell.moodle = N(prepare_import=lambda key, params: reviewed.append((key, dict(params))) or
                       {'review_id': 'batch_1', 'files': [f'reading-{m}.pdf' for m in params['module']], 'destination': {'new_kb': params['new_kb']}})
    real = a.shell.execute
    files = [{'path': f'/reading-{m}.pdf', 'status': 'completed' if batch_status == 'completed' or i < 5 else 'failed'} for i, m in enumerate(MODULES)]
    counts = {status: sum(f['status'] == status for f in files) for status in {f['status'] for f in files}}

    async def execute(command, **options):
        key, args, params, _ = prepare_command(command)
        executed.append((key, args, params))
        if key == 'moodle.import.course':
            return ShellResult(True, data={'batch_id': 'batch_1', 'status': batch_status, 'files': files, 'counts': counts,
                                           'destination': {'single_file': False, 'kb_id': 31, 'name': params['new_kb']}}, command=command)
        if key == 'moodle.folder.status':
            return ShellResult(True, data={'batch_id': params['batch_id'], 'files': files, 'counts': counts}, command=command)
        if key == 'assistant.create':
            http.created = {'assistant_id': 12, 'name': args[0], **params}
            return ShellResult(True, data={'assistant_id': 12, 'name': args[0]}, command=command)
        if key == 'assistant.get' and args == ['12']:
            return ShellResult(True, data=dict(http.created), command=command)
        return await real(command, **options)

    a.shell.execute = execute
    return a, N(reviewed=reviewed, executed=executed, http=http, saved=saved)


def step_commands(a):
    plan = (a.pending_action or {}).get('plan') or a.auto_work.task['plan']
    return {step['id']: prepare_command(step['command'].replace('@import_docs.destination.kb_id', '31').replace('@create_assistant.assistant_id', '12'))
            for step in plan['steps']}


@pytest.mark.asyncio
async def test_the_malformed_exchange_of_issue_568_is_explained_and_the_same_plan_as_fields_reaches_approval():
    a, seen = moodle_agent()
    modules = ' '.join(f'--module {m}' for m in MODULES)
    cli_plan = {'title': 'Assistant grounded in the course PDFs', 'steps': [
        {'id': 'import_docs', 'title': 'Import', 'command': f'moodle import course 10 {modules} --new-kb "{KB_NAME}" --description "The seven readings of the course (unit 1)."'},
        {'id': 'create_assistant', 'title': 'Create', 'after': 'import_docs',
         'command': 'lamb assistant create "Transformers tutor" --description "Answers from the seven readings." --system-prompt "You are a patient tutor. Answer only from the course readings." --rag-collections @import_docs.destination.kb_id'}],
        'assistant_calls': 10, 'tool_estimate': 12, 'evaluate': False}
    first = "lamb plan prepare --json '" + json.dumps(cli_plan)  # the plan is valid JSON; the closing quotation mark is missing
    degraded = json.loads(json.dumps(cli_plan).replace(KB_NAME, 'Transformers_course_PDFs'))
    second = "lamb plan prepare --json '" + json.dumps(degraded)

    for attempt in (first, second):
        answer = await a._execute_tool(tool(attempt))
        assert not answer['success'] and answer['error'] != 'No closing quotation'
        for phrase in ('unbalanced quotation mark', 'Nothing was executed', 'prepare_plan', 'Do not shorten'):
            assert phrase in answer['error']
    assert a.pending_action is None and not seen.executed and not seen.reviewed
    assert a.auto_work.rejections == 2 and not a.auto_work.state['journal']

    answer = await a._execute_tool(plan_tool(course_plan()))
    assert answer['awaiting_user_confirmation'] is True and answer['action'] == 'plan.prepare', answer
    assert a.auto_work.rejections == 0 and not seen.executed, 'approval comes before any import or creation'
    commands = step_commands(a)
    key, _, params, _ = commands['import_docs']
    assert key == 'moodle.import.course' and list(params['module']) == MODULES
    assert params['new_kb'] == KB_NAME and params['description'] == KB_DESCRIPTION
    assert seen.reviewed == [('import.course', seen.reviewed[0][1])], 'the import was reviewed once, for the approval'
    key, args, params, _ = commands['create_assistant']
    assert (key, args) == ('assistant.create', ["Transformers tutor (teacher's draft)"]) and params['system_prompt'] == PROMPT


@pytest.mark.asyncio
async def test_the_tool_loop_goes_from_seven_course_pdfs_to_a_verified_assistant():
    a, seen = moodle_agent(messages=[message(tools=[plan_tool(course_plan())]), message('I have prepared the plan for your approval.')])
    await a.chat('Create an assistant from the seven PDFs of my Transformers course.')

    call = next(m for m in a.conversation if m.get('tool_calls'))['tool_calls'][0]
    assert call['function']['name'] == 'prepare_plan', 'the model used the structured tool through the real loop'
    assert a.pending_action['action_key'] == 'plan.prepare' and not seen.executed
    await a._resolve_pending_action('yes')
    result = await a._execute_tool(tool('lamb plan execute'))
    assert result['success'], result
    assert [step['status'] for step in result['data']['steps']] == ['completed', 'completed', 'completed']

    imported, created, read_back = seen.executed[-3:]
    assert imported[0] == 'moodle.import.course' and list(imported[2]['module']) == MODULES and imported[2]['new_kb'] == KB_NAME
    # The reference resolved to the knowledge base the import really created, and the text arrived untouched.
    assert created[0] == 'assistant.create' and str(created[2]['rag_collections']) == '31'
    assert created[2]['system_prompt'] == PROMPT and created[1] == ["Transformers tutor (teacher's draft)"]
    assert read_back[:2] == ('assistant.get', ['12'])
    assert result['data']['steps'][2]['result']['system_prompt'] == PROMPT, 'saved state was read back'
    status = await a._execute_tool(tool('lamb plan status'))
    assert [(w['step_id'], w['operation'], w['status']) for w in status['data']['writes']] == [
        ('import_docs', 'moodle.import.course', 'completed'), ('create_assistant', 'assistant.create', 'completed')]


@pytest.mark.parametrize('text', [
    'two words', "the teacher's own", 'she said "no"', 'a back\\slash and C:\\dir\\file', 'català, euskara, 日本語, émoji 🐑',
    'line one\nline two\n\n- a list item', 'template {user_input} and {{RANDOM:25-70}}', '- starts with a dash', '--looks-like an option',
    '@looks.like_a_reference', '$HOME `whoami` $(date) ; rm -rf /', "mixed ' and \" and \\' together", '  spaces at both ends  ', '=equals first'])
@pytest.mark.asyncio
async def test_text_reaches_execution_exactly_as_given_without_any_escaping_by_the_model(text):
    a, seen = moodle_agent()
    plan = {'title': 'One assistant', 'steps': [{'id': 'make', 'operation': 'assistant create', 'arguments': ['Tutor ' + text.strip('-@= ')[:20].strip() or 'Tutor'],
                                               'options': {'system_prompt': text, 'description': text}}]}
    answer = await a._execute_tool(plan_tool(plan))
    assert answer.get('awaiting_user_confirmation'), answer
    await a._resolve_pending_action('yes')
    assert (await a._execute_tool(tool('lamb plan execute')))['success']
    key, _, params = seen.executed[-1]
    assert key == 'assistant.create' and params['system_prompt'] == text and params['description'] == text


@pytest.mark.asyncio
async def test_a_wrong_field_is_named_and_the_correction_keeps_the_content_and_writes_nothing_early():
    a, seen = moodle_agent()
    broken = course_plan()
    broken['steps'][1]['options']['sytem_prompt'] = broken['steps'][1]['options'].pop('system_prompt')
    broken['steps'][1]['options']['rag_collections'] = {'ref': 'import_documents.destination.kb_id'}
    broken['steps'][2]['operation'] = 'assistant fetch'
    broken['steps'][0]['arguments'] = []

    answer = await a._execute_tool(plan_tool(broken))
    assert answer['success'] is False and answer['executed'] is False and answer['attempt'] == 1 and answer['attempts_left'] == PLAN_ATTEMPTS - 1
    assert 'Nothing was executed' in answer['error'] and 'do not shorten' in answer['error']
    problems = {(p['step'], p['field']): p['problem'] for p in answer['problems']}
    assert 'no option "sytem_prompt"' in problems[('create_assistant', 'options.sytem_prompt')] and 'system_prompt' in problems[('create_assistant', 'options.sytem_prompt')]
    assert 'not an earlier step' in problems[('create_assistant', 'options.rag_collections')]
    assert 'not an installed operation' in problems[('verify', 'operation')] and 'assistant get' in problems[('verify', 'operation')]
    assert a.pending_action is None and not seen.executed and not seen.reviewed and not a.auto_work.state['journal']

    # The contract of the Moodle import is checked by the plan machinery itself, which names the step.
    incomplete = course_plan()
    incomplete['steps'][0]['arguments'] = []
    answer = await a._execute_tool(plan_tool(incomplete))
    assert answer['problems'][0]['step'] == 'import_docs' and answer['executed'] is False and not seen.executed

    answer = await a._execute_tool(plan_tool(course_plan()))
    assert answer['awaiting_user_confirmation'] and a.auto_work.rejections == 0
    assert step_commands(a)['create_assistant'][2]['system_prompt'] == PROMPT


@pytest.mark.asyncio
async def test_after_three_refused_proposals_legatus_must_stop_and_tell_the_user():
    a, seen = moodle_agent()
    wrong = course_plan()
    wrong['steps'][1]['operation'] = 'assistant construct'
    answers = [await a._execute_tool(plan_tool(wrong)) for _ in range(PLAN_ATTEMPTS)]
    assert [x['attempts_left'] for x in answers] == [2, 1, 0]
    assert 'Tell the user what is blocking' in answers[-1]['error']
    # Even a correct plan waits for the user now, through either door.
    assert (await a._execute_tool(plan_tool(course_plan())))['attempts_left'] == 0
    refused = await a._execute_tool(tool('lamb plan prepare --json ' + json.dumps(json.dumps({'title': 'T', 'steps': [{'id': 'r', 'command': 'lamb assistant get 7'}]}))))
    assert not refused['success'] and 'no further one is accepted' in refused['error']
    assert a.pending_action is None and not seen.executed


@pytest.mark.asyncio
async def test_a_partial_import_stops_the_assistant_and_only_a_declared_recovery_may_read_it():
    plan = course_plan()
    # An external write needs a concrete target before approval, so the planned answer to a failure is a read:
    # which files are missing. Resuming the batch is then its own approved action.
    plan['steps'].insert(1, {'id': 'inspect_import', 'title': 'See which files are missing if the import fails', 'operation': 'moodle folder status',
                             'after': 'import_docs', 'when': 'failure', 'arguments': [{'ref': 'import_docs.batch_id'}]})
    unplannable = copy.deepcopy(plan)
    unplannable['steps'][1].update(operation='moodle folder finish')
    a, seen = moodle_agent(batch_status='partial')
    refused = await a._execute_tool(plan_tool(unplannable))
    assert refused['problems'][0]['step'] == 'inspect_import' and 'concrete targets before plan approval' in refused['problems'][0]['problem']
    assert (await a._execute_tool(plan_tool(plan))).get('awaiting_user_confirmation')
    await a._resolve_pending_action('yes')
    result = await a._execute_tool(tool('lamb plan execute'))

    steps = {step['id']: step for step in result['data']['steps']}
    assert steps['import_docs']['status'] == 'failed' and steps['import_docs']['partial'] is True
    assert 'Completed only in part' in steps['import_docs']['error'] and '"failed": 2' in steps['import_docs']['error']
    assert steps['inspect_import']['status'] == 'completed', 'the step declared as the answer to a failure could read the batch'
    assert seen.executed[-1][0] == 'moodle.folder.status' and seen.executed[-1][2]['batch_id'] == 'batch_1'
    assert steps['create_assistant']['status'] == 'skipped' and steps['verify']['status'] == 'skipped'
    assert not any(key == 'assistant.create' for key, _, _ in seen.executed), 'no assistant was built on five of seven files'
    status = (await a._execute_tool(tool('lamb plan status')))['data']
    assert [s['status'] for s in status['steps']] == ['failed', 'completed', 'skipped', 'skipped']

    # A step that is not a recovery cannot read the partial result, even without `after`.
    a, seen = moodle_agent(batch_status='partial')
    independent = course_plan()
    del independent['steps'][1]['after']
    assert (await a._execute_tool(plan_tool(independent))).get('awaiting_user_confirmation')
    await a._resolve_pending_action('yes')
    steps = {step['id']: step for step in (await a._execute_tool(tool('lamb plan execute')))['data']['steps']}
    assert steps['create_assistant']['status'] == 'failed' and 'completed only in part' in steps['create_assistant']['error']
    assert not any(key == 'assistant.create' for key, _, _ in seen.executed)


@pytest.mark.asyncio
async def test_a_repeated_plan_cannot_create_the_same_knowledge_base_or_assistant_twice():
    a, seen = moodle_agent()
    await a._execute_tool(plan_tool(course_plan()))
    await a._resolve_pending_action('yes')
    assert (await a._execute_tool(tool('lamb plan execute')))['success']
    assert (await a._execute_tool(tool('lamb plan finish')))['success']
    executed = len(seen.executed)

    again = await a._execute_tool(plan_tool(course_plan()))
    assert again['success'] is False and again['executed'] is False
    assert again['problems'][0]['step'] == 'import_docs'
    assert 'already completed the same creation' in again['problems'][0]['problem'] and '"batch_id": "batch_1"' in again['problems'][0]['problem']
    assert len(seen.executed) == executed and a.pending_action is None


@pytest.mark.asyncio
async def test_permissions_and_approvals_are_the_same_through_the_structured_door():
    a, seen = moodle_agent()
    # A read-only plan starts without approval.
    read = await a._execute_tool(plan_tool({'title': 'Look', 'steps': [{'id': 'look', 'operation': 'assistant get', 'arguments': [7]}]}))
    assert read['success'] and a.pending_action is None
    assert (await a._execute_tool(tool('lamb plan cancel')))['success']
    # Control commands, unknown operations and commands outside the role stay refused.
    for operation, reason in [('plan execute', 'cannot be a plan step'), ('skill load', 'cannot be a plan step')]:
        refused = await a._execute_tool(plan_tool({'title': 'No', 'steps': [{'id': 'x', 'operation': operation, 'arguments': ['create-assistant'] if 'skill' in operation else []}]}))
        assert refused['executed'] is False and reason in refused['problems'][0]['problem'], refused
    a.auto_work.rejections = 0
    a.shell.allowed_commands = {'assistant.get', 'plan.prepare', 'plan.extend'}
    outside = await a._execute_tool(plan_tool({'title': 'No', 'steps': [{'id': 'x', 'operation': 'assistant delete', 'arguments': [7]}]}))
    assert 'outside your role' in outside['problems'][0]['problem'] and a.pending_action is None
    # Guided mode still has no batch plans.
    a.auto_work.rejections = 0
    a.auto_work.state['mode'] = 'guided'
    guided = await a._execute_tool(plan_tool(course_plan()))
    assert guided['executed'] is False and 'Enable Auto' in guided['problems'][0]['problem']
    assert not any(key in ('moodle.import.course', 'assistant.create', 'assistant.delete') for key, _, _ in seen.executed) and not seen.reviewed


def test_a_step_is_written_as_the_command_the_cli_form_would_hold():
    command, problems = render_step({'id': 'a', 'operation': 'lamb assistant create', 'arguments': ['My Tutor'],
                                     'options': {'system_prompt': 'You are…', 'vision': True, 'no_image_generation': False, 'rag_collections': [3, 4]}}, set())
    assert problems == [] and prepare_command(command) == ('assistant.create', ['My Tutor'], {'system_prompt': 'You are…', 'vision': True, 'rag_collections': '3,4'}, False)
    command, problems = render_step({'id': 'b', 'operation': 'kb.ingest', 'arguments': [5], 'options': {'plugin': 'url_ingest', 'param': ['depth=2', 'lang=ca']}}, set())
    assert problems == [] and prepare_command(command)[2] == {'plugin': 'url_ingest', 'param': ['depth=2', 'lang=ca']}
    plan, extend, problems = plan_from_structure({'title': 'More', 'extend': True, 'steps': [
        {'id': 'again', 'operation': 'test run', 'arguments': [7], 'options': {'case': {'ref': 'create.id'}}, 'after': 'create'}]})
    assert problems == [] and extend is True and plan['steps'] == [{'id': 'again', 'command': 'lamb test run 7 --case @create.id', 'after': 'create'}]
    for bad, field in [({'title': '', 'steps': [{'id': 'a', 'operation': 'assistant get', 'arguments': [7]}]}, 'title'),
                       ({'title': 'T', 'steps': []}, 'steps'),
                       ({'title': 'T', 'steps': [{'id': 'Bad Id', 'operation': 'assistant get', 'arguments': [7]}]}, 'id'),
                       ({'title': 'T', 'steps': [{'id': 'a', 'operation': 'assistant get', 'arguments': [7], 'command': 'lamb x'}]}, 'command'),
                       ({'title': 'T', 'steps': [{'id': 'a', 'operation': 'assistant get', 'arguments': [7, 8]}]}, 'arguments'),
                       ({'title': 'T', 'steps': [{'id': 'a', 'operation': 'assistant get', 'arguments': [{'nested': 1}]}]}, 'arguments[0]'),
                       ({'title': 'T', 'steps': [{'id': 'a', 'operation': 'assistant get', 'arguments': [7], 'when': 'later'}]}, 'when'),
                       ({'title': 'T', 'bonus': 1, 'steps': [{'id': 'a', 'operation': 'assistant get', 'arguments': [7]}]}, 'bonus')]:
        assert [p['field'] for p in plan_from_structure(bad)[2]] == [field], bad


@pytest.mark.asyncio
async def test_plans_written_the_old_way_and_pending_approvals_still_work():
    a, seen = moodle_agent()
    old = {'title': 'Old form', 'steps': [{'id': 'change', 'title': 'Rename', 'command': 'lamb assistant update 7 --description "kept as it was"'}]}
    assert (await a._execute_tool(tool('lamb plan prepare --json ' + shlex.quote(json.dumps(old))))).get('awaiting_user_confirmation')
    pending = copy.deepcopy(a.pending_action)
    assert pending['command'].startswith('lamb plan prepare --json ')
    await a._resolve_pending_action('yes')
    assert (await a._execute_tool(tool('lamb plan execute')))['success'] and seen.http.assistant['description'] == 'kept as it was'


def test_the_plan_example_taught_by_the_pack_being_written_is_a_valid_structured_plan():
    import re
    from lamb.aac.pack_loader import packs_root, WORKSPACE
    guide = (packs_root() / WORKSPACE / 'skills' / 'test_and_evaluate.md').read_text()
    examples = [json.loads(block) for block in re.findall(r'```json\n(.*?)```', guide, re.S) if '"operation"' in block]
    if not examples:
        pytest.skip('the workspace pack still teaches the command form')
    for example in examples:
        plan, extend, problems = plan_from_structure(example)
        assert problems == [] and not extend
        assert plan['steps'][1]['command'] == 'lamb test run 7 --case @normal.id'
        assert prepare_command(plan['steps'][0]['command'])[2]['expected'].startswith('Explain light, water')


def test_context_metrics_name_the_structured_plan_call_without_its_content():
    from lamb.aac.context_metrics import command_name
    call = lambda payload: {'function': {'name': 'prepare_plan', 'arguments': json.dumps(payload)}}
    assert command_name(call({'title': 'T', 'steps': []})) == 'plan.prepare'
    assert command_name(call({'title': 'T', 'extend': True, 'steps': []})) == 'plan.extend'


def test_the_tool_schema_is_plain_enough_for_every_provider():
    from lamb.aac.agent.loop import TOOL_DEFINITIONS
    from lamb.aac.structured import PLAN_TOOL
    assert [tool['function']['name'] for tool in TOOL_DEFINITIONS] == ['execute_command', 'prepare_plan']
    def walk(node):
        if isinstance(node, dict):
            assert not {'anyOf', 'oneOf', 'allOf', '$ref', 'additionalProperties'} & node.keys()
            if 'properties' in node:
                assert all(isinstance(spec.get('type'), str) for spec in node['properties'].values())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(PLAN_TOOL['function']['parameters'])
    json.dumps(PLAN_TOOL)
