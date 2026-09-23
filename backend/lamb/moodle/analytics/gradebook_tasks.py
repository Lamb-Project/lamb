"""Minimized and idempotent assessment task handlers; registry wiring is separate."""
from lamb.private_storage import file_lock
from .checkpoints import MAX_CHECKPOINTS
from .gradebook_run import GradebookCheckpoints, start, advance, publish
from .gradebook_authorization import validate_gradebook_scope
from ..scope import MoodleScope
from ..charts import ChartStore
from .recipes import result_page


def authorize(client, owner, scopes):
    client.checkpoint()
    for scope in scopes:
        validate_gradebook_scope(client,scope)
    MoodleScope(client,owner).require_teacher(scopes[0]['course_id'])
    client.checkpoint()


def progress(record):
    state=record['state']
    scopes=[dict(item['scope']) for item in state['items']]
    return {'run_id':record['id'],'course_id':scopes[0]['course_id'],'group_id':scopes[0]['group_id'],
        'grade_item_ids':[scope['grade_item_id'] for scope in scopes], 'recipe_id':'assessment-comparison',
        'status':'collected' if state['done'] else 'running','phase':state['phase'],
        'started_at':state['started_at'],'expires_at':record['expires_at'],
        'processed_grade_records':sum(len(item['cursor']['records']) for item in state['items']),
        'collected_assessments':sum(item['cursor']['done'] for item in state['items']),
        'selected_assessments':len(scopes),'remaining_grade_records':None,
        'gradebook_scopes':scopes,
        'continue_command':f"moodle analytics continue {record['id']} --step {state.get('public_step',0)}",
        'meaning':'Collection progress only, not score comparison, submission counts or learning evidence.'}


def execute(runtime, results, client, owner, key, params):
    store=GradebookCheckpoints(results)
    with file_lock(store.folder/'commands',blocking=False):
        if key=='analytics.start':
            scopes=[dict(course_id=params['course_id'],grade_item_id=identity,group_id=params['group_id'])
                    for identity in params['grade_item_ids']]
            if not 2<=len(scopes)<=20:
                raise ValueError('Select two to twenty assessment items')
            authorize(client,owner,scopes)
            record=start(store,params['course_id'],params['grade_item_ids'],group_id=params['group_id'],
                language=params['language'],tz=params['tz'])
            client.checkpoint()
            return progress(record)
        if key=='analytics.runs':
            paths=list(store.folder.glob('*.json'))
            if len(paths)>MAX_CHECKPOINTS:
                raise ValueError('Assessment recovery inventory exceeds its limit')
            items=[]
            for path in paths:
                try:
                    record=store.read(path.stem)
                    authorize(client,owner,[item['scope'] for item in record['state']['items']])
                    if record['state'].get('published'):
                        ChartStore(runtime).read(record['state']['publication']['id'])
                except PermissionError:
                    continue
                item=progress(record)
                if record['state'].get('published'):
                    item.update(status='published',chart_id=record['state']['publication']['id'],continue_command=None)
                items.append(item)
            client.checkpoint()
            return {'items':sorted(items,key=lambda item:item['started_at'],reverse=True)}
        if key!='analytics.continue':
            raise ValueError('Unknown assessment continuation operation')
        step=params['step']
        if type(step) is not int or step<0:
            raise ValueError('Invalid assessment continuation step')
        record=store.read(params['run_id'])
        authorize(client,owner,[item['scope'] for item in record['state']['items']])
        state=record['state']
        previous=state.get('step_results',{}).get(str(step))
        if previous is not None:
            response=result_page(previous['chart_id'],ChartStore(runtime).read(previous['chart_id'])) if previous.get('chart_id') else previous
            client.checkpoint()
            return response
        if step!=state.get('public_step',0):
            raise ValueError('Use the exact continuation command from analytics runs')
        if not state['done'] and state.get('finished_public_step')!=step:
            if state.get('active_public_step')!=step:
                state['active_public_step']=step
                state.pop('public_target_pages',None)
                record=store.replace(record['id'],state,expected_revision=record['revision'])
            record=advance(store,client,owner,record['id'])
        if record['state']['done']:
            response=publish(store,runtime,client,record['id'])
            record=store.read(record['id'])
            saved_response={'chart_id':response['chart_id']}
        else:
            record['state']['public_step']=step+1
            response=progress(record)
            saved_response=response
        state=record['state']
        state['public_step']=step+1
        state.setdefault('step_results',{})[str(step)]=saved_response
        store.replace(record['id'],state,expected_revision=record['revision'])
        client.checkpoint()
        return response
