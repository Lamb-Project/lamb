"""Bounded private completion execution. Public continuation is wired separately."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid

from .completion import completion_context
from .completion_state import advance_cursor
from ..forum_activity import TaskLimit

MAX_RUN_STUDENTS = 1000
MAX_STEP_STUDENTS = 25
MAX_RUN_CALLS = 1600
MAX_RUN_STEPS = 60


def start(store, course_id, *, language='en', tz='UTC'):
    if type(course_id) is not int or course_id < 1:
        raise ValueError('Invalid completion course')
    if language not in {'en','es','ca','eu'}:
        raise ValueError('Invalid completion language')
    ZoneInfo(tz)
    return store.create({'course_id':course_id,'started_at':datetime.now(timezone.utc).isoformat(),
        'context':None,'cursor':None,'calls':0,'steps':0,'done':False,'language':language,'tz':tz})


def publish(store, runtime, client, identity):
    """Freeze aggregate evidence before publication; recover the exact same chart.

    Does not recollect source data. Current permission checks still apply to
    every attempt, including one after the chart was already published.
    """
    from .completion import completion_snapshot
    from .recipes import format_snapshot, result_page
    from ..charts import ChartStore
    with store.execution_lock():
        client.checkpoint()
        record=store.read(identity);state=record['state']
        if not state['done']:
            raise ValueError('Completion collection is not finished')
        current=runtime.result_binding()
        if (store.binding['organization_id'] != runtime.store.organization_id or
                store.binding['owner_id'] != runtime.store.owner_id or
                any(store.binding[key] != current.get(key) for key in ('generation','base_url','moodle_user_id'))):
            raise PermissionError('Completion run belongs to another connection')
        publication=state.get('publication')
        if publication is None:
            data=completion_snapshot(state['context'],state['cursor'],state['completed_at'],resumable=True)
            # A multi-step collection has an interval, not an atomic timestamp.
            data['collection_started_at']=state['started_at']
            data['collection_completed_at']=state['completed_at']
            rows=[{**row,'id':row['cmid'],'name':f"{row['name']} (#{row['cmid']})",
                'value':row['incomplete'],'status':'ok','reason':None} for row in data['rows']]
            scope={'course_id':state['course_id'],'module_ids':[row['cmid'] for row in rows]}
            data['completion_scopes']=[scope]
            binding=dict(current,course_id=state['course_id'],completion_scopes=[scope])
            runtime.validate_result_binding(binding,'moodle.analytics.run')
            snapshot=format_snapshot('activity-completion',data,rows,dict(state,recipe='activity-completion'))
            publication={'id':str(uuid.uuid4()),'snapshot':snapshot,'binding':binding}
            state['publication']=publication
            record=store.replace(identity,state,expected_revision=record['revision'])
        runtime.validate_result_binding(publication['binding'],'moodle.analytics.run')
        client.checkpoint()
        charts=ChartStore(runtime)
        chart_id=charts.save(publication['snapshot'],publication['binding'],
            command='moodle.analytics.run',publication_id=publication['id'])
        saved=charts.read(chart_id)
        client.checkpoint()
        if not state.get('published'):
            state['published']=True
            store.replace(identity,state,expected_revision=record['revision'])
        return result_page(chart_id,saved)


def advance(store, client, owner_id, identity):
    """Persist request accounting before reads and counts after complete responses.

    Returns PRIVATE execution state. Never pass this envelope to AAC or a user:
    its cursor retains learner IDs. Callers must build a minimized projection.
    Stop/timeout propagates, leaving the latest acknowledged cursor recoverable.
    """
    with store.execution_lock():
        record = store.read(identity)
        state = record['state']
        if state['steps'] >= MAX_RUN_STEPS:
            raise TaskLimit('completion_run_step_limit')
        if client.before_request is not None:
            raise ValueError('Completion executor cannot replace an existing request guard')

        def save():
            nonlocal record
            record = store.replace(identity,state,expected_revision=record['revision'])

        def before_request():
            if state['calls'] >= MAX_RUN_CALLS:
                raise TaskLimit('completion_run_request_limit')
            state['calls'] += 1
            save()

        def verify():
            client.checkpoint()
            current=completion_context(client,owner_id,state['course_id'],student_limit=MAX_RUN_STUDENTS)
            if state['context'] is not None and current['fingerprint'] != state['context']['fingerprint']:
                raise ValueError('Completion population or activity inventory changed; start a new run')
            return current

        state['steps'] += 1
        save()
        client.before_request = before_request
        try:
            current = verify()
            if state['context'] is None:
                state['cursor'] = current.pop('cursor')
                state['context'] = current
                save()
            if not state['done']:
                cursor=state['cursor']
                target=cursor['next_student']+MAX_STEP_STUDENTS
                if 'active_public_step' in state:
                    if 'public_target' not in state:
                        state['public_target']=min(target,len(cursor['students']))
                        save()
                    target=state['public_target']
                selected=cursor['students'][cursor['next_student']:target]
                for student in selected:
                    client.checkpoint()
                    response=client.call('core_completion_get_activities_completion_status',
                        courseid=state['course_id'],userid=student)
                    state['cursor']=advance_cursor(state['cursor'],student,response)
                    save()
                # Verify again before exposing even aggregate progress. This
                # detects observed inventory drift, not an atomic Moodle view.
                verify()
                state['done']=state['cursor']['next_student']==len(state['cursor']['students'])
                if state['done']:
                    state['completed_at']=datetime.now(timezone.utc).isoformat()
                if 'active_public_step' in state:
                    state['finished_public_step']=state['active_public_step']
                save()
            client.checkpoint()
            return record
        finally:
            client.before_request = None
