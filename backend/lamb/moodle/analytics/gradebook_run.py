"""Private resumable multi-assessment collection, not a public recipe yet."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid
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
                target = state['pages'] + PAGES_PER_STEP
                if 'active_public_step' in state:
                    if 'public_target_pages' not in state:
                        state['public_target_pages'] = target
                        save()
                    target = state['public_target_pages']
                while state['pages'] < target:
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
            if 'active_public_step' in state:
                state['finished_public_step'] = state['active_public_step']
            save()
            client.checkpoint()
            return record
        finally:
            client.before_request = None


def publish(store, runtime, client, identity):
    """Reserve immutable aggregate evidence before saving; retries reuse its ID."""
    from .gradebook_snapshot import snapshot
    from .recipes import result_page
    from ..charts import ChartStore
    with store.execution_lock():
        client.checkpoint()
        record = store.read(identity)
        state = record['state']
        if not state['done']:
            raise ValueError('Assessment collection is not finished')
        current = runtime.result_binding()
        if (store.binding['organization_id'] != runtime.store.organization_id
                or store.binding['owner_id'] != runtime.store.owner_id
                or any(store.binding[key] != current.get(key) for key in ('generation','base_url','moodle_user_id'))):
            raise PermissionError('Assessment run belongs to another connection')
        publication = state.get('publication')
        if publication is None:
            data = snapshot(state,identity)
            binding = dict(current,course_id=data['course_id'],gradebook_scopes=data['gradebook_scopes'])
            runtime.validate_result_binding(binding,'moodle.analytics.run')
            publication = {'id':str(uuid.uuid4()),'snapshot':data,'binding':binding}
            state['publication'] = publication
            record = store.replace(identity,state,expected_revision=record['revision'])
        runtime.validate_result_binding(publication['binding'],'moodle.analytics.run')
        client.checkpoint()
        charts = ChartStore(runtime)
        chart_id = charts.save(publication['snapshot'],publication['binding'],
            command='moodle.analytics.run',publication_id=publication['id'])
        saved = charts.read(chart_id)
        client.checkpoint()
        if not state.get('published'):
            state['published'] = True
            store.replace(identity,state,expected_revision=record['revision'])
        return result_page(chart_id,saved)
