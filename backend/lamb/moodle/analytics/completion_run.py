"""Bounded private completion execution. Public continuation is wired separately."""
from datetime import datetime, timezone

from .completion import completion_context
from .completion_state import advance_cursor
from ..forum_activity import TaskLimit

MAX_RUN_STUDENTS = 1000
MAX_STEP_STUDENTS = 25
MAX_RUN_CALLS = 1600
MAX_RUN_STEPS = 60


def start(store, course_id):
    if type(course_id) is not int or course_id < 1:
        raise ValueError('Invalid completion course')
    return store.create({'course_id':course_id,'started_at':datetime.now(timezone.utc).isoformat(),
        'context':None,'cursor':None,'calls':0,'steps':0,'done':False})


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
                selected=cursor['students'][cursor['next_student']:cursor['next_student']+MAX_STEP_STUDENTS]
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
                save()
            client.checkpoint()
            return record
        finally:
            client.before_request = None
