"""Bounded task execution. A plan grants exact mutations, never a policy bypass.

The session turn lock serializes execution; checkpoints precede dispatch. An
interrupted mutation stays uncertain and is never blindly replayed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shlex
import time
import uuid

from lamb.aac.authorization import ActionAuthorizer
from lamb.aac.liteshell.shell import prepare_command, ShellResult

LIMIT = 10
MAX_STEPS = 50
MAX_TOOLS = 250
MAX_CALLS = 200
REF = re.compile(r'^@([a-z][a-z0-9_]{0,39})((?:\.[a-zA-Z0-9_]+)+)$')
MUTATIONS = {'test.add', 'test.run', 'test.evaluate', 'report.save', 'change.restore'}
CONTROL = {'plan.prepare', 'plan.extend', 'plan.execute', 'plan.status', 'plan.finish', 'plan.cancel', 'plan.reconcile', 'plan.allow-calls', 'change.list', 'change.get', 'report.get'}


def stamp():
    return time.time()


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def canonical(command):
    key, args, kwargs, help_requested = prepare_command(command)
    return [key, args, kwargs, help_requested]


def mutation(key, kwargs=None):
    if key in CONTROL or key.startswith(('notebook.', 'session.')):
        return False
    if key == 'assistant.chat':
        return (kwargs or {}).get('persist') in (True, 'true')
    return key in MUTATIONS or ActionAuthorizer().check(key) == 'ask'


def substitute(command, steps, *, preview=False):
    tokens = shlex.split(command)
    for index, token in enumerate(tokens):
        match = REF.fullmatch(token)
        if not match:
            continue
        name, path = match.groups()
        source = next((s for s in steps if s['id'] == name), None)
        if source is None:
            raise ValueError(f'Unknown earlier step reference: {token}')
        if preview:
            tokens[index] = '1'
            continue
        if source.get('status') != 'completed':
            raise ValueError(f'Referenced step {name} has not completed')
        value = source.get('result')
        for field in path[1:].split('.'):
            try:
                value = value[int(field)] if isinstance(value, list) else value[field]
            except (IndexError, KeyError, TypeError, ValueError):
                raise ValueError(f'Result has no reference {token}') from None
        # References are identifiers, not arbitrary source text or commands.
        if not isinstance(value, (str, int)) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', str(value)):
            raise ValueError(f'Reference {token} is not a resource identifier')
        tokens[index] = str(value)
    return shlex.join(tokens)


def task_state(state):
    execution = state.setdefault('execution', {})
    execution.setdefault('mode', 'guided')
    execution.setdefault('journal', [])
    execution.setdefault('reports', [])
    execution.setdefault('task', {'id': str(uuid.uuid4()), 'calls': 0, 'call_limit': LIMIT,
                                  'tools': 0, 'status': 'active', 'created_at': stamp()})
    return execution


class AutoWork:
    def __init__(self, agent):
        self.agent = agent
        self.state = task_state(agent.skill_state)
        self.executing = None
        self.current_entry = None

    @property
    def task(self):
        return self.state['task']

    @property
    def enabled(self):
        return self.state['mode'] == 'auto'

    def save(self):
        callback = getattr(self.agent, 'checkpoint', None)
        if callback:
            callback()

    def public(self):
        plan = self.task.get('plan')
        return {'mode': self.state['mode'], 'task_id': self.task['id'], 'calls': self.task['calls'],
                'call_limit': self.task['call_limit'], 'tools': self.task['tools'],
                'status': self.task['status'],
                'result': self.task.get('result'),
                'plan': {k: plan[k] for k in ('id', 'title', 'status') if k in plan} if plan else None,
                'steps': [{k: s[k] for k in ('id', 'title', 'status', 'error') if k in s}
                          for s in plan.get('steps', [])] if plan else [],
                'reports': [{k: r[k] for k in ('id', 'title', 'task_id', 'destination', 'created_at') if k in r} for r in self.state['reports']],
                'changes': len(self.state['journal'])}

    async def progress(self):
        bridge = getattr(getattr(self.agent.shell, 'frontend', None), '__self__', None)
        emit = getattr(bridge, 'emit', None)
        if emit:
            await emit({'status': 'execution', 'execution': self.public()})

    async def normalize(self, command):
        key, args, kwargs, help_requested = prepare_command(command)
        if help_requested:
            return command
        from lamb.aac.resource_names import resolve
        if key == 'change.restore':
            entries = await self.agent.shell._get_http().get(f'/creator/aac/sessions/{self.agent.session_id}/changes')
            if not any(e['id'] == args[0] and e.get('restorable') for e in entries):
                raise ValueError('No currently accessible restorable change has that ID')
        index, kind = None, None
        if key.startswith(('assistant.', 'test.', 'analytics.')) and args and key not in {'assistant.create'}:
            kind, index = 'assistant', 0
            if key in {'test.evaluate', 'test.run-detail', 'test.case-detail', 'test.scenario-detail', 'test.delete-case', 'test.delete-scenario'}:
                index = 1 if len(args) > 1 else None
            if key == 'test.evaluate' and len(args) > 2 and args[1] in {'good', 'bad', 'mixed'}:
                index = 2
        elif key.startswith('kb.') and args and key not in {'kb.create'}:
            kind, index = 'kb', 0
        if index is not None and not str(args[index]).isdigit() and not REF.fullmatch(str(args[index])):
            args[index] = await resolve(self.agent.shell._get_http(), kind, args[index])
            command = render(key, args, kwargs)
        if key in {'assistant.create', 'assistant.update'} and kwargs.get('rag_collections') and not REF.fullmatch(str(kwargs['rag_collections'])):
            kwargs['rag_collections'] = ','.join([await resolve(self.agent.shell._get_http(), 'kb', value.strip())
                                                for value in kwargs['rag_collections'].split(',') if value.strip()])
            command = render(key, args, kwargs)
        return command

    async def prepare(self, payload, *, extend=False):
        if not self.enabled:
            raise ValueError('Enable Auto in this conversation to prepare a batch plan.')
        if not isinstance(payload, dict) or set(payload) - {'title', 'steps', 'assistant_calls', 'tool_estimate', 'evaluate', 'report'}:
            raise ValueError('Plan fields: title, steps, assistant_calls, tool_estimate, evaluate, report')
        title = payload.get('title')
        if not isinstance(title, str) or not 1 <= len(title) <= 250:
            raise ValueError('Provide a short plan title')
        current = self.task.get('plan')
        if extend and (not current or current.get('status') not in {'approved', 'running'}):
            raise ValueError('There is no active plan to extend')
        if extend and current['expires'] < stamp():
            raise ValueError('The previous approval expired. Cancel it and prepare a fresh review of the remaining work.')
        if extend and current.get('report_id'):
            raise ValueError('This plan already has its final report. Finish it before preparing further work.')
        if not extend and current and current.get('status') in {'approved', 'running', 'uncertain'}:
            raise ValueError('Finish or reconcile the current plan before preparing another one.')
        raw = payload.get('steps', [])
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_STEPS:
            raise ValueError(f'Provide 1..{MAX_STEPS} concrete steps')
        steps, calls, writes = copy.deepcopy(current['steps']) if extend else [], 0, False
        for step in steps:
            if step['status'] == 'pending':
                key, _, kwargs, _ = prepare_command(substitute(step['command'], steps, preview=True))
                calls += call_count(key, kwargs)
        for item in raw:
            if not isinstance(item, dict) or set(item) - {'id', 'title', 'command', 'after', 'when'}:
                raise ValueError('Each step has id, title, command, optional after and when=success|failure|always')
            identifier = item.get('id', '')
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', identifier) or any(s['id'] == identifier for s in steps):
                raise ValueError('Step IDs must be unique lowercase identifiers')
            command = item.get('command', '')
            if not isinstance(command, str) or len(command) > 30000:
                raise ValueError('Invalid step command')
            after, when = item.get('after'), item.get('when', 'success')
            if when not in {'success', 'failure', 'always'} or (after and not any(s['id'] == after for s in steps)):
                raise ValueError('A conditional step must refer to an earlier step')
            preview = substitute(command, steps, preview=True)
            key, args, kwargs, help_requested = prepare_command(preview, self.agent.shell.allowlist)
            allowed = self.agent.shell.allowed_commands
            if allowed is not None and key not in allowed:
                raise ValueError(f'{key} is outside your role')
            if key.startswith(('plan.', 'report.', 'change.', 'skill.')) or help_requested or ActionAuthorizer().check(key) == 'never':
                raise ValueError(f'{key} cannot be a plan step')
            if key == 'test.run' and not any(k in kwargs for k in ('case', 'scenario', 's')):
                raise ValueError('Plan test runs need --case ID or --case @earlier_step.id; list cases first. This freezes the selected set.')
            command = await self.normalize(command)
            key, args, kwargs, _ = prepare_command(substitute(command, steps, preview=True))
            entry = {**item, 'command': command, 'title': str(item.get('title', identifier))[:250],
                     'when': when, 'status': 'pending'}
            # Freeze concrete external reviews at preparation, just like an exact action.
            if key.startswith('moodle.') and mutation(key, kwargs):
                if preview != shlex.join(shlex.split(command)) and any(REF.fullmatch(t) for t in shlex.split(command)):
                    raise ValueError('External writes require concrete targets before plan approval')
                entry['review'] = await self.review(key, kwargs)
            writes = writes or mutation(key, kwargs)
            calls += call_count(key, kwargs)
            steps.append(entry)
        ceiling = payload.get('assistant_calls', max(LIMIT, self.task['calls'] + calls))
        if type(ceiling) is not int or not self.task['calls'] + calls <= ceiling <= MAX_CALLS:
            raise ValueError('assistant_calls must cover the cumulative task calls, including all possible branches, up to 200')
        evaluate = payload.get('evaluate', current.get('evaluate', False) if extend else False)
        report = payload.get('report', current.get('report') if extend else None)
        if extend and ((current.get('evaluate') and not evaluate) or (current.get('report') and not report)):
            raise ValueError('An extension retains the existing evaluation and report requirements. Cancel the old task explicitly if its outcome has changed.')
        if type(evaluate) is not bool:
            raise ValueError('evaluate must be boolean; it covers only runs created by this plan')
        if report is not None:
            if not isinstance(report, dict) or set(report) - {'title', 'assistant_id', 'analysis_id'} or not {'title', 'assistant_id'} <= set(report) or not isinstance(report['title'], str) or not 1 <= len(report['title']) <= 250:
                raise ValueError('report requires title and a verified assistant_id')
            report = dict(report)
            report['assistant_id'] = await self._assistant(report['assistant_id'])
            if report.get('analysis_id'):
                report['analysis_id'] = str(uuid.UUID(report['analysis_id']))
                await self.agent.shell._get_http().get(f"/creator/analytics/assistant/{report['assistant_id']}/analysis-reports/{report['analysis_id']}", params={'draft': True})
        estimate = payload.get('tool_estimate', len(steps))
        if type(estimate) is not int or not 1 <= estimate <= MAX_TOOLS:
            raise ValueError('tool_estimate must be 1..250')
        if len(steps) > MAX_STEPS:
            raise ValueError('The combined plan exceeds 50 steps')
        return {'id': str(uuid.uuid4()), 'title': title, 'steps': steps, 'assistant_calls': ceiling,
                'tool_estimate': estimate, 'evaluate': evaluate, 'report': report,
                'needs_approval': writes or (evaluate and not (extend and current.get('evaluate'))) or
                    (report is not None and (not extend or report != current.get('report'))) or ceiling > self.task['call_limit'],
                'created_at': stamp(), 'expires': stamp() + 86400, 'status': 'prepared',
                'evaluated': list(current.get('evaluated', [])) if extend else [],
                **({'report_id': current['report_id']} if extend and current.get('report_id') else {}),
                **({'previous_plan_id': current['id']} if extend else {})}

    async def _assistant(self, identifier):
        from lamb.aac.resource_names import resolve, unwrap
        identifier = await resolve(self.agent.shell._get_http(), 'assistant', identifier)
        unwrap(await self.agent.shell._get_http().get(f'/creator/assistant/get_assistant/{identifier}'))
        return identifier

    async def review(self, key, kwargs):
        import asyncio
        if not getattr(self.agent.shell, 'moodle', None):
            raise ValueError('Moodle is unavailable')
        if key == 'moodle.assign.grade':
            return await asyncio.to_thread(self.agent.shell.moodle.prepare_grade, kwargs)
        from lamb.moodle.document_contract import IMPORT_KEYS
        if key.removeprefix('moodle.') in IMPORT_KEYS:
            return await asyncio.to_thread(self.agent.shell.moodle.prepare_import, key.removeprefix('moodle.'), kwargs)
        return None

    def approve(self, plan):
        if plan['expires'] < stamp():
            raise ValueError('Plan expired. Prepare a fresh review.')
        self.task['plan'] = copy.deepcopy(plan)
        self.task['plan']['status'] = 'approved'
        self.task['call_limit'] = max(self.task['call_limit'], plan['assistant_calls'])
        self.task['status'] = 'active'
        self.save()

    def evaluation_allowed(self, args):
        plan = self.task.get('plan') or {}
        if not self.enabled or plan.get('status') not in {'approved', 'running'} or not plan.get('evaluate') or len(args) != 3:
            return False
        if args[0] in plan['evaluated']:
            return False
        return any(str(r.get('id')) == args[0] and str(r.get('assistant_id')) == args[1]
                   for step in plan['steps'] for r in runs(step.get('result')) if step.get('status') == 'completed')

    def covered(self, command):
        key, args, kwargs, _ = prepare_command(command)
        plan = self.task.get('plan') or {}
        if not self.enabled or plan.get('status') not in {'approved', 'running'} or plan.get('expires', 0) < stamp():
            return False
        if self.executing:
            return canonical(command) == canonical(substitute(self.executing['command'], plan['steps']))
        if key == 'test.evaluate':
            return self.evaluation_allowed(args)
        if key == 'report.save':
            return bool(plan.get('report')) and not plan.get('report_id')
        return False

    async def execute_plan(self):
        plan = self.task.get('plan')
        if not self.enabled or not plan or plan['status'] not in {'approved', 'running'} or plan['expires'] < stamp():
            raise ValueError('There is no approved executable plan')
        plan['status'] = 'running'
        for step in plan['steps']:
            if step['status'] in {'completed', 'failed', 'skipped'}:
                continue
            if step['status'] in {'running', 'uncertain'}:
                plan['status'] = 'uncertain'
                self.save()
                raise ValueError(f"Step {step['id']} has an uncertain outcome. Inspect saved resources before any retry; no write was repeated.")
            prior = next((s for s in plan['steps'] if s['id'] == step.get('after')), None)
            if prior and ((step['when'] == 'success' and prior['status'] != 'completed') or
                          (step['when'] == 'failure' and prior['status'] != 'failed')):
                step['status'] = 'skipped'
                self.save()
                continue
            try:
                command = substitute(step['command'], plan['steps'])
                step['status'] = 'running'
                self.executing = step
                self.save()
                await self.progress()
                from types import SimpleNamespace
                tool = SimpleNamespace(id='plan_' + step['id'], function=SimpleNamespace(
                    name='execute_command', arguments=json.dumps({'command': command})))
                result = await self.agent._execute_tool(tool)
                if result.get('awaiting_user_confirmation'):
                    step['status'] = 'pending'
                    self.save()
                    return {'success': False, 'pending_approval': True, 'steps': plan['steps']}
                uncertain = any(e.get('step_id') == step['id'] and e['task_id'] == self.task['id'] and e['status'] == 'uncertain'
                                for e in self.state['journal'])
                step['status'] = 'uncertain' if uncertain else 'completed' if result.get('success') else 'failed'
                step['result'] = result.get('data')
                step['error'] = result.get('error')
                if uncertain:
                    plan['status'] = 'uncertain'
                    self.save()
                    return {'success': False, 'uncertain': step['id'], 'steps': plan['steps']}
            except Exception as error:
                step.update(status='failed', error=str(error))
            except BaseException:
                step['status'] = 'uncertain'
                plan['status'] = 'uncertain'
                raise
            finally:
                self.executing = None
                self.save()
            await self.progress()
        return {'plan_id': plan['id'], 'steps': plan['steps'], 'next': 'Read actual results, evaluate the runs if requested, save the report, then plan finish.'}

    async def snapshot(self, key, args):
        http = self.agent.shell._get_http()
        if key == 'assistant.update':
            return await http.get(f'/creator/aac/assistants/{args[0]}/snapshot')
        if key == 'test.update':
            return await http.get(f'/creator/assistant/{args[0]}/tests/scenarios/{args[1]}')
        if key == 'kb.update':
            return await http.get(f'/creator/knowledgebases/kb/{args[0]}')
        if key == 'test.add':
            return await http.get(f'/creator/assistant/{args[0]}/tests/scenarios')
        if key == 'test.run':
            return []  # The journal ID is the idempotent test request ID; read back that exact run.
        return None

    async def cost(self, command):
        key, args, kwargs, _ = prepare_command(command)
        cost = call_count(key, kwargs)
        batch = None
        if key == 'test.run' and not any(k in kwargs for k in ('case', 'scenario', 's')):
            from lamb.aac.resource_names import unwrap
            raw = unwrap(await self.agent.shell._get_http().get(f'/creator/assistant/{args[0]}/tests/scenarios'))
            batch = raw if isinstance(raw, list) else raw.get('scenarios', [])
            cost *= len(batch)
        return cost, batch

    async def execute(self, command, *, confirmed=False, review=None, batch_snapshot=None):
        key, args, kwargs, _ = prepare_command(command)
        if key in CONTROL or key == 'report.save':
            return await self.agent.shell.execute(command, confirmed=confirmed, review=review)
        if self.task['tools'] >= MAX_TOOLS:
            return ShellResult(False, error='Task reached its technical tool limit. Completed work is saved; no further action executed.')
        cost, batch = await self.cost(command) if batch_snapshot is None else (len(batch_snapshot) * call_count(key, kwargs), batch_snapshot)
        if self.task['calls'] + cost > self.task['call_limit']:
            return ShellResult(False, error='Assistant-call allowance would be exceeded. Prepare a plan with a larger cumulative assistant_calls limit before dispatch.')
        writes = mutation(key, kwargs)
        if writes and any(e['status'] in {'running', 'uncertain'} and canonical(e['command']) == canonical(command)
                          for e in self.state['journal']):
            return ShellResult(False, error='An earlier identical write has an uncertain outcome. Run plan reconcile before retrying.')
        before = await self.snapshot(key, args) if writes else None
        entry = {'id': str(uuid.uuid4()), 'command': command, 'task_id': self.task['id'],
                 'step_id': self.executing['id'] if self.executing else None,
                 'actor': self.agent.shell.user_email, 'organization_id': self.agent.shell.organization_id,
                 'plan_id': (self.task.get('plan') or {}).get('id'), 'approved': confirmed,
                 'created_at': stamp(), 'status': 'running', 'before': before, 'after': None}
        if writes:
            self.state['journal'].append(entry)
        if key == 'test.run':
            self.agent.shell.knowledge['test_request_id'] = entry['id']
            entry['request_ids'] = []
        self.task['tools'] += 1
        # A batch reserves the full allowance, but increments actual attempts one by one.
        if batch is None:
            self.task['calls'] += cost
        # Persist reservations and intent before an HTTP call, including before an uncertain crash.
        self.save()
        try:
            if batch is None:
                if key == 'test.run':
                    entry['request_ids'].append(entry['id'])
                    self.save()
                result = await self.agent.shell.execute(command, confirmed=confirmed, review=review)
            else:
                responses = []
                for case in batch:
                    request_id = str(uuid.uuid4())
                    entry['request_ids'].append(request_id)
                    self.agent.shell.knowledge['test_request_id'] = request_id
                    self.task['calls'] += call_count(key, kwargs)
                    self.save()
                    result = await self.agent.shell.execute(render(key, args, {**kwargs, 'case': case['id']}), confirmed=confirmed)
                    if result.success:
                        responses.extend(result.data if isinstance(result.data, list) else [result.data])
                    else:
                        responses.append({'scenario_id': case['id'], 'error': result.error})
                    await self.progress()
                result = ShellResult(True, data={'runs': responses, 'count': len(responses)})
            entry.update(status='completed' if result.success else 'failed', result=result.data, error=result.error)
            if not result.success and any(part in (result.error or '').casefold() for part in ('timed out', 'timeout', 'http error', 'api error (5')):
                entry['status'] = 'uncertain'
            if writes and before is not None and result.success:
                entry['after'] = await self.snapshot(key, args)
            if key == 'change.restore' and result.success:
                entry.update(before=result.data.get('before'), after=result.data.get('after'))
            if result.success and key == 'test.evaluate' and self.evaluation_allowed(args):
                self.task['plan']['evaluated'].append(args[0])
            return result
        except BaseException:
            entry['status'] = 'uncertain'
            raise
        finally:
            self.agent.shell.knowledge.pop('test_request_id', None)
            self.save()
            await self.progress()

    async def handle(self, key, args, kwargs):
        if key == 'plan.cancel':
            if self.task.get('plan'):
                self.task['plan']['status'] = 'cancelled'
            self.task['status'] = 'cancelled'
            self.save()
            return {'status': 'cancelled', 'message': 'No further steps will run. Completed changes and uncertain outcomes remain recorded; cancellation does not undo them.'}
        if key == 'plan.reconcile':
            return await self.reconcile()
        if key == 'plan.allow-calls':
            ceiling = int(args[0])
            if not 1 <= ceiling <= MAX_CALLS:
                raise ValueError('Call allowance must be 1..200')
            self.task['call_limit'] = max(ceiling, self.task['call_limit'])
            self.save()
            return self.public()
        if key == 'plan.status':
            return {**self.public(), 'plan_detail': self.task.get('plan')}
        if key == 'plan.execute':
            return await self.execute_plan()
        if key == 'plan.finish':
            plan = self.task.get('plan')
            if plan:
                if any(s['status'] in {'pending', 'running', 'uncertain'} for s in plan['steps']):
                    raise ValueError('Plan has unfinished or uncertain steps; report partial progress and resolve them first.')
                if plan.get('report') and not plan.get('report_id'):
                    raise ValueError('Save the requested report before finishing.')
                if plan.get('evaluate'):
                    missing = {r['id'] for s in plan['steps'] for r in runs(s.get('result'))} - set(plan['evaluated'])
                    if missing:
                        raise ValueError('Evaluate the actual remaining runs before finishing: ' + ', '.join(sorted(missing)))
            if kwargs:
                from lamb.aac.frontend import destination
                target = destination([kwargs.get('resource', ''), kwargs.get('id', '')], {'tab': kwargs['tab']} if 'tab' in kwargs else {})
                paths = {'assistant': '/creator/assistant/get_assistant/', 'kb': '/creator/knowledgebases/kb/',
                         'rubric': '/creator/rubrics/', 'learning-scenario': '/creator/aac/learning-scenarios/',
                         'moodle-result': '/creator/moodle/results/'}
                await self.agent.shell._get_http().get(paths[target['resource']] + target['id'])
                self.task['result'] = {'title': plan['title'] if plan else '', 'destination': target}
            if plan:
                plan['status'] = 'completed'
            self.task['status'] = 'completed'
            self.save()
            await self.progress()
            return self.public()
        if key in {'change.list', 'change.get'}:
            # Historical values use the same current resource checks as the UI.
            visible = await self.agent.shell._get_http().get(f'/creator/aac/sessions/{self.agent.session_id}/changes')
            allowed = {e['id'] for e in visible}
            entries = [e for e in self.state['journal'] if e['id'] in allowed]
            if key == 'change.get':
                entry = next((e for e in entries if e['id'] == args[0]), None)
                if entry is None:
                    raise ValueError('Change not found in this session')
                return entry
            return [{k: e[k] for k in ('id', 'action', 'status', 'created_at')} for e in visible]
        if key == 'change.restore':
            entry = next((e for e in self.state['journal'] if e['id'] == args[0]), None)
            if not entry or entry['status'] != 'completed' or not entry.get('before') or not entry.get('after'):
                raise ValueError('This change has no complete restorable snapshot')
            oldkey, oldargs, _kw, _ = prepare_command(entry['command'])
            if oldkey != 'assistant.update':
                raise ValueError('Automatic restoration currently supports assistant fields. Inspect the recorded values for this change.')
            return await self.agent.shell._get_http().post(f'/creator/aac/assistants/{oldargs[0]}/restore', json={
                'session_id': self.agent.session_id, 'change_id': entry['id']})
        if key == 'report.save':
            plan = self.task.get('plan') or {}
            spec = plan.get('report')
            if not spec or plan.get('report_id'):
                raise ValueError('Prepare a plan including report: {title, assistant_id} first')
            if any(s['status'] in {'pending', 'running', 'uncertain'} for s in plan['steps']):
                raise ValueError('Resolve the remaining plan steps before saving the final report.')
            if plan.get('evaluate') and {r['id'] for s in plan['steps'] for r in runs(s.get('result'))} - set(plan['evaluated']):
                raise ValueError('Evaluate the actual runs before saving the final report.')
            content = kwargs.get('content', '')
            if not isinstance(content, str) or not 1 <= len(content) <= 100000:
                raise ValueError('Report content must be 1..100000 characters')
            assistant_id = await self._assistant(spec['assistant_id'])
            report = {'id': str(uuid.uuid4()), 'title': spec['title'], 'content': content,
                      'task_id': self.task['id'], 'created_at': stamp(),
                      'destination': {'resource': 'assistant', 'id': assistant_id, 'tab': 'tests'},
                      'run_ids': [r['id'] for s in plan['steps'] for r in runs(s.get('result'))],
                      'calls': self.task['calls'], 'tools': self.task['tools']}
            if spec.get('analysis_id'):
                reviewed = json.loads(kwargs.get('reviewed', '[]'))
                report = await self.agent.shell._get_http().post(
                    f"/creator/analytics/assistant/{assistant_id}/analysis-reports/{spec['analysis_id']}",
                    json={'title': spec['title'], 'content': content, 'reviewed_chat_ids': reviewed})
                report = {**report, 'task_id': self.task['id'], 'kind': 'activity-analysis'}
            self.state['reports'].append(report)
            plan['report_id'] = report['id']
            self.save()
            await self.progress()
            return report
        if key == 'report.get':
            report = next((r for r in self.state['reports'] if r['id'] == args[0]), None)
            if not report:
                raise ValueError('Report not found in this session')
            await self._assistant(report['destination']['id'])
            if report.get('kind') == 'activity-analysis':
                return await self.agent.shell._get_http().get(f"/creator/analytics/assistant/{report['assistant_id']}/analysis-reports/{report['id']}")
            return report
        raise ValueError('Unsupported task command')

    async def reconcile(self):
        """Read back supported interrupted operations. Ambiguous outcomes stay blocked."""
        plan = self.task.get('plan') or {}
        for entry in self.state['journal']:
            if entry['status'] not in {'running', 'uncertain'}:
                continue
            key, args, kwargs, _ = prepare_command(entry['command'])
            if entry.get('before') is None:
                continue
            current = await self.snapshot(key, args)
            result = None
            if key == 'assistant.update':
                fields = {'name': 'name', 'n': 'name', 'description': 'description', 'd': 'description',
                          'system_prompt': 'system_prompt', 'prompt_template': 'prompt_template', 'rag_top_k': 'RAG_Top_k'}
                if not set(kwargs) <= fields.keys():
                    continue
                expected = dict(entry['before']['fields'])
                expected.update({fields[k]: int(v) if k == 'rag_top_k' else v for k, v in kwargs.items()})
                if current['fields'] == expected:
                    result = {'assistant_id': int(args[0])}
                elif current['revision'] == entry['before']['revision']:
                    entry['status'] = 'failed'
            elif key == 'test.run' and len(entry.get('request_ids', [])) == 1:
                from lamb.aac.liteshell.http_client import APIResponseError
                try:
                    result = await self.agent.shell._get_http().get(f'/creator/assistant/{args[0]}/tests/runs/{entry["request_ids"][0]}')
                except APIResponseError as error:
                    # Absence is not proof of failure: the original completion may still be running.
                    if error.status_code != 404:
                        raise
            elif key == 'test.add' and isinstance(current, list) and isinstance(entry['before'], list):
                before_ids = {item['id'] for item in entry['before']}
                candidates = [item for item in current if item['id'] not in before_ids]
                from lamb.aac.liteshell.commands import _messages
                candidates = [i for i in candidates if i.get('title') == (args[1] if len(args) > 1 else kwargs.get('title', 'Test case'))
                              and i.get('messages') == _messages(kwargs)
                              and i.get('expected_behavior', '') == kwargs.get('expected', kwargs.get('e', ''))]
                if len(candidates) == 1:
                    result = candidates[0]
            if result is not None:
                entry.update(status='completed', result=result, after=current, reconciled_at=stamp())
            step = next((s for s in plan.get('steps', []) if s['id'] == entry.get('step_id')), None)
            if step and entry['status'] in {'completed', 'failed'}:
                step.update(status=entry['status'], result=result)
        if plan.get('status') == 'uncertain' and not any(s['status'] in {'running', 'uncertain'} for s in plan['steps']):
            plan['status'] = 'running'
        self.save()
        return self.public()


def call_count(key, kwargs):
    return int(key in {'assistant.chat', 'test.run'} and kwargs.get('bypass', kwargs.get('b')) not in (True, 'true'))


def runs(value):
    if isinstance(value, dict) and 'runs' in value:
        value = value['runs']
    values = value if isinstance(value, list) else [value]
    return [v for v in values if isinstance(v, dict) and v.get('id') and v.get('assistant_id') and 'scenario_id' in v]


def render(key, args, kwargs):
    tokens = ['lamb', *key.split('.'), *map(str, args)]
    for name, value in kwargs.items():
        for item in value if isinstance(value, list) else [value]:
            tokens.append('--' + name.replace('_', '-'))
            if item is not True:
                tokens.append(str(item).lower() if isinstance(item, bool) else str(item))
    return shlex.join(tokens)
