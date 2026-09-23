"""Minimized quiz task handlers. Workflow registration is separate."""
from lamb.private_storage import file_lock
from .checkpoints import MAX_CHECKPOINTS
from .quiz_run import QuizCheckpoints, start, advance, publish
from .quiz_authorization import validate_quiz_scope
from ..scope import MoodleScope
from ..charts import ChartStore
from .recipes import result_page


def authorize(client, owner, scope):
    client.checkpoint()
    validate_quiz_scope(client, scope)
    MoodleScope(client, owner).require_teacher(scope['course_id'])
    client.checkpoint()


def progress(record):
    state = record['state']
    return {'run_id': record['id'], **state['scope'], 'recipe_id': 'quiz-overview',
        'attempt_policy': state['policy'], 'status': 'collected' if state['done'] else 'running',
        'started_at': state['started_at'], 'expires_at': record['expires_at'],
        'processed_attempt_records': len(state['cursor']['records']),
        'population_students': len(state['context']['students']) if state['context'] else None,
        'remaining_attempt_records': None, 'remaining_collection_steps': None,
        'quiz_scopes': [dict(state['scope'])],
        'continue_command': f"moodle analytics continue {record['id']} --step {state.get('public_step', 0)}",
        'meaning': 'Collection progress only. Total attempt count is not known until source exhaustion; no grade or learning inference.'}


def execute(runtime, results, client, owner, key, params):
    store = QuizCheckpoints(results)
    with file_lock(store.folder/'commands', blocking=False):
        if key == 'analytics.start':
            scope = {key: params[key] for key in ('course_id', 'quiz_id', 'group_id')}
            authorize(client, owner, scope)
            response = progress(start(store, scope['course_id'], scope['quiz_id'], group_id=scope['group_id'],
                policy=params['attempt_policy'], language=params['language'], tz=params['tz']))
            client.checkpoint()
            return response
        if key == 'analytics.runs':
            paths = list(store.folder.glob('*.json'))
            if len(paths) > MAX_CHECKPOINTS:
                raise ValueError('Quiz recovery inventory exceeds its limit')
            items = []
            for path in paths:
                try:
                    record = store.read(path.stem)
                    authorize(client, owner, record['state']['scope'])
                    if record['state'].get('published'):
                        ChartStore(runtime).read(record['state']['publication']['id'])
                except PermissionError:
                    continue
                item = progress(record)
                if record['state'].get('published'):
                    item.update(status='published', chart_id=record['state']['publication']['id'], continue_command=None)
                items.append(item)
            client.checkpoint()
            return {'items': sorted(items, key=lambda item: item['started_at'], reverse=True)}
        if key != 'analytics.continue':
            raise ValueError('Unknown quiz continuation operation')
        step = params['step']
        if type(step) is not int or step < 0:
            raise ValueError('Invalid quiz continuation step')
        record = store.read(params['run_id'])
        authorize(client, owner, record['state']['scope'])
        state = record['state']
        previous = state.get('step_results', {}).get(str(step))
        if previous is not None:
            if previous.get('chart_id'):
                response = result_page(previous['chart_id'], ChartStore(runtime).read(previous['chart_id']))
            else:
                response = previous
            client.checkpoint()
            return response
        if step != state.get('public_step', 0):
            raise ValueError('Use the exact continuation command from analytics runs')
        if not state['done'] and state.get('finished_public_step') != step:
            if state.get('active_public_step') != step:
                state['active_public_step'] = step
                state.pop('public_target_pages', None)
                record = store.replace(record['id'], state, expected_revision=record['revision'])
            record = advance(store, client, owner, record['id'])
        if record['state']['done']:
            response = publish(store, runtime, client, record['id'])
            record = store.read(record['id'])
            saved_response = {'chart_id': response['chart_id']}
        else:
            record['state']['public_step'] = step + 1
            response = progress(record)
            saved_response = response
        state = record['state']
        state['public_step'] = step + 1
        state.setdefault('step_results', {})[str(step)] = saved_response
        store.replace(record['id'], state, expected_revision=record['revision'])
        client.checkpoint()
        return response
