"""Private resumable multi-assessment collection, not a public recipe yet."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from .checkpoints import CompletionCheckpoints
from .client import GRADEBOOK_GRADES_FUNCTION
from .gradebook_context import gradebook_context
from .gradebook_state import initial_cursor, advance_cursor, integer
from .assessment_comparison import compare_assessments
from ..forum_activity import TaskLimit

MAX_GRADEBOOK_CHECKPOINT_BYTES = 8 * 1024 * 1024
MAX_RUN_CALLS = 16000
MAX_RUN_STEPS = 400
PAGES_PER_STEP = 5


class GradebookCheckpoints(CompletionCheckpoints):
    namespace = 'gradebook-runs'
    max_bytes = MAX_GRADEBOOK_CHECKPOINT_BYTES


def _now():
    return datetime.now(timezone.utc).isoformat()


def start(store, course_id, grade_item_ids, *, group_id=0, language='en', tz='UTC'):
    if (not isinstance(grade_item_ids, list) or not 2 <= len(grade_item_ids) <= 20
            or any(type(v) is not int or v < 1 for v in grade_item_ids)
            or len(set(grade_item_ids)) != len(grade_item_ids)):
        raise ValueError('Select two to twenty distinct assessment items')
    integer(course_id, 1); integer(group_id)
    if language not in {'en','es','ca','eu'}:
        raise ValueError('Invalid assessment language')
    ZoneInfo(tz)
    items = [{'scope':{'course_id':course_id,'grade_item_id':identity,'group_id':group_id},
              'cursor':initial_cursor(course_id,identity,group_id),'context':None} for identity in grade_item_ids]
    return store.create({'items':items,'language':language,'tz':tz,'started_at':_now(),
        'phase':'collect','index':0,'calls':0,'steps':0,'pages':0,'done':False})


def advance(store, client, owner_id, identity):
    """One item / at most five pages per step; a final population verification pass.

    Source reads are non-atomic. Publication must revalidate all saved scopes.
    Private rows and context must not escape through a public task response.
    """
    with store.execution_lock():
        record = store.read(identity)
        state = record['state']
        if client.before_request is not None:
            raise ValueError('Gradebook executor cannot replace an existing request guard')
        if state['steps'] >= MAX_RUN_STEPS:
            raise TaskLimit('gradebook_run_step_limit')

        def save():
            nonlocal record
            record = store.replace(identity,state,expected_revision=record['revision'])

        def before_request():
            if state['calls'] >= MAX_RUN_CALLS:
                raise TaskLimit('gradebook_run_request_limit')
            state['calls'] += 1
            save()

        def verify(item):
            client.checkpoint()
            current = gradebook_context(client,owner_id,item['scope'])
            if item['context'] is not None and current['fingerprint'] != item['context']['fingerprint']:
                raise ValueError('Assessment population changed; start a new run')
            return current

        state['steps'] += 1
        save()
        client.before_request = before_request
        try:
            if state['done']:
                for item in state['items']:
                    verify(item)
                client.checkpoint()
                return record
            item = state['items'][state['index']]
            current = verify(item)
            if item['context'] is None:
                item['context'] = current
                save()
            if state['phase'] == 'collect':
                for _ in range(PAGES_PER_STEP):
                    cursor = item['cursor']
                    if cursor['done']:
                        break
                    client.checkpoint()
                    scope = item['scope']
                    page = client.call(GRADEBOOK_GRADES_FUNCTION,courseid=scope['course_id'],
                        gradeitemid=scope['grade_item_id'],groupid=scope['group_id'],
                        afterid=cursor['afterid'],throughid=cursor['throughid'] or 0,limit=200)
                    item['cursor'] = advance_cursor(cursor,cursor['afterid'],page)
                    state['pages'] += 1
                    save()
                verify(item)
                if item['cursor']['done']:
                    state['index'] += 1
                    if state['index'] == len(state['items']):
                        state.update(phase='verify',index=0)
            else:
                state['index'] += 1
                if state['index'] == len(state['items']):
                    # Validate numerical semantics before acknowledging completion.
                    compare_assessments([(i['cursor'],i['context']['students']) for i in state['items']])
                    state.update(done=True,phase='done',completed_at=_now())
            save()
            client.checkpoint()
            return record
        finally:
            client.before_request = None
