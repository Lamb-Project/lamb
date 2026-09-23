"""Private bounded quiz collection; not yet a public analytics command."""
from datetime import datetime, timezone
import hashlib
import json
import uuid
from zoneinfo import ZoneInfo

from .checkpoints import CompletionCheckpoints
from .client import QUIZ_ATTEMPTS_FUNCTION
from .events import _students
from .quiz_authorization import validate_quiz_scope
from .quiz_state import initial_cursor, advance_cursor
from .quiz_attempts import POLICIES, summarize_attempts
from ..scope import MoodleScope
from ..forum_activity import TaskLimit

MAX_QUIZ_CHECKPOINT_BYTES = 4 * 1024 * 1024
MAX_RUN_CALLS = 1600
MAX_RUN_STEPS = 60
PAGES_PER_STEP = 5


class QuizCheckpoints(CompletionCheckpoints):
    namespace = 'quiz-runs'
    max_bytes = MAX_QUIZ_CHECKPOINT_BYTES


def _now():
    return datetime.now(timezone.utc).isoformat()


def quiz_context(client, owner_id, scope):
    validate_quiz_scope(client, scope)
    MoodleScope(client, owner_id).require_teacher(scope['course_id'])
    students, population = _students(client, scope['course_id'], scope['group_id'])
    if not population['population_exhausted'] or population['role_unknown']:
        raise ValueError('Complete known student population required for quiz analytics')
    validate_quiz_scope(client, scope)
    evidence = {'students': sorted(students), 'population': population}
    return dict(evidence, fingerprint=hashlib.sha256(
        json.dumps(evidence, sort_keys=True).encode()).hexdigest())


def start(store, course_id, quiz_id, *, group_id=0, policy, language='en', tz='UTC'):
    if policy not in POLICIES:
        raise ValueError('Explicit quiz attempt policy required')
    if language not in {'en', 'es', 'ca', 'eu'}:
        raise ValueError('Invalid quiz language')
    ZoneInfo(tz)
    cursor = initial_cursor(course_id, quiz_id, group_id)
    return store.create({'scope': {'course_id': course_id, 'quiz_id': quiz_id, 'group_id': group_id},
                         'policy': policy, 'language': language, 'tz': tz, 'started_at': _now(), 'cursor': cursor,
                         'context': None, 'calls': 0, 'steps': 0, 'done': False})


def advance(store, client, owner_id, identity):
    """Persist accounting before requests and acknowledge only validated pages.

    Returns PRIVATE state containing learner IDs. A public caller must project
    aggregate evidence, not expose this envelope. Each step rechecks population
    and permissions, including retries after source exhaustion.
    """
    with store.execution_lock():
        record = store.read(identity)
        state = record['state']
        if client.before_request is not None:
            raise ValueError('Quiz executor cannot replace an existing request guard')
        if state['steps'] >= MAX_RUN_STEPS:
            raise TaskLimit('quiz_run_step_limit')

        def save():
            nonlocal record
            record = store.replace(identity, state, expected_revision=record['revision'])

        def before_request():
            if state['calls'] >= MAX_RUN_CALLS:
                raise TaskLimit('quiz_run_request_limit')
            state['calls'] += 1
            save()

        def verify():
            client.checkpoint()
            current = quiz_context(client, owner_id, state['scope'])
            if state['context'] is not None and current['fingerprint'] != state['context']['fingerprint']:
                raise ValueError('Quiz population changed; start a new run')
            return current

        state['steps'] += 1
        save()
        client.before_request = before_request
        try:
            current = verify()
            if state['context'] is None:
                state['context'] = current
                save()
            if not state['done']:
                for _ in range(PAGES_PER_STEP):
                    cursor = state['cursor']
                    if cursor['done']:
                        break
                    client.checkpoint()
                    scope = state['scope']
                    page = client.call(QUIZ_ATTEMPTS_FUNCTION, courseid=scope['course_id'],
                        quizid=scope['quiz_id'], groupid=scope['group_id'], afterid=cursor['afterid'],
                        throughid=cursor['throughid'] or 0, limit=200)
                    state['cursor'] = advance_cursor(cursor, cursor['afterid'], page)
                    save()
                verify()
                if state['cursor']['done']:
                    # Validate cross-page identities and finished clocks before
                    # marking complete; do not publish a corrupt raw checkpoint.
                    summarize_attempts(state['cursor']['records'], state['context']['students'],
                        quiz_id=state['scope']['quiz_id'], maximum=state['cursor']['metadata']['raw_maximum'],
                        policy=state['policy'])
                    state['done'] = True
                    state['completed_at'] = _now()
                save()
            client.checkpoint()
            return record
        finally:
            client.before_request = None


def publish(store, runtime, client, identity):
    """Reserve an immutable aggregate snapshot before idempotent publication."""
    from .quiz_snapshot import snapshot
    from .recipes import result_page
    from ..charts import ChartStore
    with store.execution_lock():
        client.checkpoint()
        record = store.read(identity)
        state = record['state']
        if not state['done']:
            raise ValueError('Quiz collection is not finished')
        current = runtime.result_binding()
        if (store.binding['organization_id'] != runtime.store.organization_id or
                store.binding['owner_id'] != runtime.store.owner_id or
                any(store.binding[key] != current.get(key) for key in ('generation', 'base_url', 'moodle_user_id'))):
            raise PermissionError('Quiz run belongs to another connection')
        publication = state.get('publication')
        if publication is None:
            data = snapshot(state, identity)
            binding = dict(current, course_id=state['scope']['course_id'], quiz_scopes=data['quiz_scopes'])
            runtime.validate_result_binding(binding, 'moodle.analytics.run')
            publication = {'id': str(uuid.uuid4()), 'snapshot': data, 'binding': binding}
            state['publication'] = publication
            record = store.replace(identity, state, expected_revision=record['revision'])
        runtime.validate_result_binding(publication['binding'], 'moodle.analytics.run')
        client.checkpoint()
        charts = ChartStore(runtime)
        chart_id = charts.save(publication['snapshot'], publication['binding'],
                              command='moodle.analytics.run', publication_id=publication['id'])
        saved = charts.read(chart_id)
        client.checkpoint()
        if not state.get('published'):
            state['published'] = True
            store.replace(identity, state, expected_revision=record['revision'])
        return result_page(chart_id, saved)
