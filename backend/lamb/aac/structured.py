"""Structured plan input (issue #568).

The model used to write a plan as command strings inside JSON inside another quoted command.
Three layers of quoting made a routine request fragile: one missing quote and nothing ran.
Here the model names an operation and gives its values as fields; LAMB writes the command.

A structured step becomes exactly the command the CLI form would hold, so validation,
authorization, the approval review, cost controls, journals and saved plans are the ones
that already exist. This module adds no permission and removes none.
"""
import json
import re
import shlex

STEP_ID = re.compile(r'[a-z][a-z0-9_]{0,39}')
REFERENCE = re.compile(r'[a-z][a-z0-9_]{0,39}(?:\.[A-Za-z0-9_]+)+')
PLAN_FIELDS = {'title', 'steps', 'assistant_calls', 'tool_estimate', 'evaluate', 'report', 'extend'}
STEP_FIELDS = {'id', 'title', 'operation', 'arguments', 'options', 'after', 'when'}
MAX_TEXT = 30000

# The schema stays plain (one type per field, no anyOf) so that every provider accepts it. What a value may be is
# said in words here and checked by plan_from_structure.
PLAN_TOOL = {
    'type': 'function',
    'function': {
        'name': 'prepare_plan',
        'description': (
            'Prepare (or extend) a plan of several operations for one approval. Give every value as its own field: '
            'names, descriptions and instructions are plain text and need no quoting or escaping, whatever they contain. '
            'LAMB writes the commands. Each step names one installed operation, for example "assistant create" or '
            '"moodle import course", with its positional arguments in order and its options by name. '
            'To use a value returned by an earlier step, give {"ref": "step_id.field"}, for example {"ref": "import_docs.kb_id"}. '
            'Read-only plans start without approval; a plan with changes is shown to the user once. '
            'If the proposal is rejected nothing was executed: correct only the fields named in the answer and send the '
            'whole plan again with every other value unchanged.'),
        'parameters': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string', 'description': 'The outcome, in a few words.'},
                'extend': {'type': 'boolean', 'description': 'true adds these steps to the approved plan in progress.'},
                'steps': {'type': 'array', 'minItems': 1, 'items': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'string', 'description': 'Lowercase identifier, unique in the plan, e.g. create_assistant.'},
                        'title': {'type': 'string', 'description': 'What this step does, for the person approving.'},
                        'operation': {'type': 'string', 'description': 'An installed operation, e.g. "assistant create", "test add", "moodle import course". See lamb help.'},
                        'arguments': {'type': 'array', 'description': 'Positional values in the order lamb OPERATION --help shows. Each is text, a number, or {"ref": "step_id.field"}.'},
                        'options': {'type': 'object', 'description': 'Options by name without dashes, e.g. {"system_prompt": "...", "rag_collections": {"ref": "import_docs.destination.kb_id"}}. A value is text, a number, true for a flag, {"ref": "step_id.field"}, or a list (which repeats the option or joins its values).'},
                        'after': {'type': 'string', 'description': 'Optional id of an earlier step this one depends on.'},
                        'when': {'type': 'string', 'enum': ['success', 'failure', 'always'], 'description': 'With after: run on its success (default), failure, or always.'},
                    },
                    'required': ['id', 'operation'],
                }},
                'assistant_calls': {'type': 'integer', 'description': 'Cumulative ceiling of calls to the target assistant for the whole task.'},
                'tool_estimate': {'type': 'integer'},
                'evaluate': {'type': 'boolean', 'description': 'true approves your own evaluation of the runs this plan produces.'},
                'report': {'type': 'object', 'description': 'Only when a report is requested: {"title": "...", "assistant_id": "7"}.'},
            },
            'required': ['title', 'steps'],
        },
    },
}


def operation_key(operation):
    """'assistant create', 'lamb assistant create' or 'assistant.create' -> ('assistant.create', ['assistant', 'create'])."""
    if not isinstance(operation, str):
        return None, []
    tokens = operation.replace('.', ' ').split()
    if tokens[:1] == ['lamb']:
        tokens = tokens[1:]
    if not tokens or any(not re.fullmatch(r'[a-z][a-z0-9-]*', token) for token in tokens):
        return None, []
    return '.'.join(tokens), tokens


def _is_reference(value):
    return isinstance(value, dict) and set(value) == {'ref'}


def _option(flag, token, *, reference):
    """Tokens for one option value. A reference is its own token, which is how it is recognized. A text that
    starts with a dash or looks like a reference travels as --name=TEXT, so it is read as the text it is."""
    if reference or not (token.startswith('@') or (token.startswith('-') and not re.fullmatch(r'-\d+(\.\d+)?', token))):
        return [flag, token]
    return [f'{flag}={token}']


def _token(value, field, problems, known_steps):
    """One command token for a scalar or a reference; None after recording a problem.
    A reference comes back as '@step.field'; `_is_reference(value)` tells it from a text that starts with @."""
    if _is_reference(value):
        ref = value['ref']
        if not isinstance(ref, str) or not REFERENCE.fullmatch(ref):
            problems.append({'field': field, 'problem': 'A reference is {"ref": "step_id.field"}, naming an earlier step and a field of its result.'})
            return None
        if ref.split('.')[0] not in known_steps:
            problems.append({'field': field, 'problem': f'The reference names step "{ref.split(".")[0]}", which is not an earlier step of this plan.'})
            return None
        return '@' + ref
    if isinstance(value, bool) or value is None or isinstance(value, (dict, list)):
        problems.append({'field': field, 'problem': 'Expected text, a number or {"ref": "step_id.field"}.'})
        return None
    text = str(value)
    if len(text) > MAX_TEXT:
        problems.append({'field': field, 'problem': f'Text longer than {MAX_TEXT} characters.'})
        return None
    return text


def render_step(step, known_steps):
    """(command, problems) for one structured step. The command is None when it cannot be written."""
    from lamb.aac.liteshell.shell import COMMAND_CONTRACTS
    problems = []
    unknown = set(step) - STEP_FIELDS
    if unknown:
        problems.append({'field': sorted(unknown)[0], 'problem': 'Unknown step field. A step has id, title, operation, arguments, options, after, when.'})
    key, tokens = operation_key(step.get('operation'))
    if key is None:
        return None, problems + [{'field': 'operation', 'problem': 'Name one installed operation, for example "assistant create" or "moodle import course".'}]
    moodle = tokens[0] == 'moodle'
    contract = COMMAND_CONTRACTS.get(key)
    if not moodle and contract is None:
        group = sorted(k.replace('.', ' ') for k in COMMAND_CONTRACTS if k.startswith(tokens[0] + '.'))
        hint = ('Operations of this group: ' + ', '.join(group) + '.') if group else 'Use lamb help to list the installed operations.'
        return None, problems + [{'field': 'operation', 'problem': f'"{" ".join(tokens)}" is not an installed operation. {hint}'}]
    arguments, options = step.get('arguments', []), step.get('options', {})
    if not isinstance(arguments, list):
        problems.append({'field': 'arguments', 'problem': 'Expected a list of positional values.'})
        arguments = []
    if not isinstance(options, dict):
        problems.append({'field': 'options', 'problem': 'Expected an object of option names and values.'})
        options = {}
    command = ['lamb', *tokens]
    for index, value in enumerate(arguments):
        token = _token(value, f'arguments[{index}]', problems, known_steps)
        if token is not None and not _is_reference(value) and (
                (token.startswith('-') and not re.fullmatch(r'-\d+(\.\d+)?', token)) or REFERENCE.fullmatch(token[1:] if token.startswith('@') else '')):
            problems.append({'field': f'arguments[{index}]', 'problem': 'A positional text cannot start with a dash or look like @step.field; if this is a name or a text, give it as an option.'})
        elif token is not None:
            command.append(token)
    if contract is not None and not contract[0] <= len(arguments) <= contract[1]:
        expected = str(contract[0]) if contract[0] == contract[1] else f'{contract[0]} to {contract[1]}'
        problems.append({'field': 'arguments', 'problem': f'{" ".join(tokens)} takes {expected} positional value(s); {len(arguments)} given.'})
    accepted = set(contract[2].split()) if contract is not None else None
    for name, value in options.items():
        field = f'options.{name}'
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', name) or name in {'help', 'h', 'json'}:
            problems.append({'field': field, 'problem': 'Not an option name. Write it without dashes, for example system_prompt.'})
            continue
        flag = '--' + name.replace('_', '-')
        if accepted is not None and name.replace('-', '_') not in {a.replace('-', '_') for a in accepted}:
            listed = ', '.join(sorted(a.replace('-', '_') for a in accepted)) or 'none'
            problems.append({'field': field, 'problem': f'{" ".join(tokens)} has no option "{name}". Its options: {listed}.'})
            continue
        if value is True:
            command.append(flag)
        elif value is False or value is None:
            continue  # an option that is not wanted is simply absent
        elif isinstance(value, list):
            parts = [_token(item, f'{field}[{index}]', problems, known_steps) for index, item in enumerate(value)]
            if None in parts:
                continue
            references = [_is_reference(item) for item in value]
            if moodle or name == 'param':
                for part, reference in zip(parts, references):  # repeated option
                    command += _option(flag, part, reference=reference)
            elif any(references) and len(parts) > 1:
                problems.append({'field': field, 'problem': 'A reference must be the whole value of this option: give one reference, not a list containing one.'})
            elif parts:
                command += _option(flag, ','.join(parts), reference=references[0])
        else:
            token = _token(value, field, problems, known_steps)
            if token is not None:
                command += _option(flag, token, reference=_is_reference(value))
    return (None if problems else shlex.join(command)), problems


def plan_from_structure(payload):
    """(CLI plan payload, extend, problems). The payload is what `lamb plan prepare --json` accepts."""
    problems = []
    if not isinstance(payload, dict):
        return None, False, [{'step': None, 'field': 'plan', 'problem': 'Expected an object with title and steps.'}]
    for name in sorted(set(payload) - PLAN_FIELDS):
        problems.append({'step': None, 'field': name, 'problem': 'Unknown plan field. A plan has title, steps, assistant_calls, tool_estimate, evaluate, report, extend.'})
    title = payload.get('title')
    if not isinstance(title, str) or not 1 <= len(title) <= 250:
        problems.append({'step': None, 'field': 'title', 'problem': 'Give a title of 1 to 250 characters.'})
    extend = payload.get('extend', False)
    if not isinstance(extend, bool):
        problems.append({'step': None, 'field': 'extend', 'problem': 'Expected true or false.'})
        extend = False
    raw = payload.get('steps')
    if not isinstance(raw, list) or not raw:
        return None, extend, problems + [{'step': None, 'field': 'steps', 'problem': 'Give at least one step.'}]
    steps, known = [], set()
    for index, item in enumerate(raw):
        label = item.get('id') if isinstance(item, dict) and isinstance(item.get('id'), str) and item.get('id') else f'#{index + 1}'
        if not isinstance(item, dict):
            problems.append({'step': label, 'field': 'step', 'problem': 'Each step is an object with id and operation.'})
            continue
        identifier = item.get('id')
        if not isinstance(identifier, str) or not STEP_ID.fullmatch(identifier):
            problems.append({'step': label, 'field': 'id', 'problem': 'A step id is a lowercase identifier such as create_assistant.'})
        elif identifier in known:
            problems.append({'step': label, 'field': 'id', 'problem': 'This id is already used by an earlier step.'})
        after, when = item.get('after'), item.get('when', 'success')
        # In an extension an earlier step may belong to the approved plan; that is checked when the plan is prepared.
        if after is not None and not extend and after not in known:
            problems.append({'step': label, 'field': 'after', 'problem': f'"{after}" is not an earlier step of this plan.'})
        if when not in ('success', 'failure', 'always'):
            problems.append({'step': label, 'field': 'when', 'problem': 'Use success, failure or always.'})
        if 'title' in item and not isinstance(item['title'], str):
            problems.append({'step': label, 'field': 'title', 'problem': 'Expected text.'})
        command, found = render_step(item, known if not extend else _AnyStep())
        problems += [{'step': label, **problem} for problem in found]
        if command is not None and isinstance(identifier, str):
            entry = {'id': identifier, 'command': command}
            for name in ('title', 'after', 'when'):
                if item.get(name) is not None:
                    entry[name] = item[name]
            steps.append(entry)
        if isinstance(identifier, str):
            known.add(identifier)
    if problems:
        return None, extend, problems
    plan = {'title': title, 'steps': steps}
    for name in ('assistant_calls', 'tool_estimate', 'evaluate', 'report'):
        if name in payload:
            plan[name] = payload[name]
    return plan, extend, []


class _AnyStep:
    """In an extension the earlier steps live in the approved plan; their existence is checked there."""
    def __contains__(self, name):
        return True


def rejection(problems, *, attempt, limit):
    """What the model reads when a proposal is not accepted. Nothing ran, and it is told so."""
    left = max(limit - attempt, 0)
    answer = {
        'success': False, 'executed': False, 'attempt': attempt, 'attempts_left': left, 'problems': problems,
        'error': ('The plan was not accepted. Nothing was executed and nothing changed. Correct only the fields named in '
                  '"problems" and call prepare_plan again with every other value exactly as it was: do not shorten, rename '
                  'or simplify names, descriptions or instructions to make the plan pass.'),
    }
    if not left:
        answer['error'] += (' This was the last proposal accepted in this turn. Tell the user what is blocking, with the '
                            'problems listed, and ask how to proceed.')
    return answer


def command_for(plan, extend):
    """The CLI form of a validated plan. LAMB writes the quoting; nobody else does."""
    return shlex.join(['lamb', 'plan', 'extend' if extend else 'prepare', '--json', json.dumps(plan, ensure_ascii=False)])
