"""Public, minimized completion recovery commands; private cursors never escape."""
from lamb.private_storage import file_lock
from .checkpoints import CompletionCheckpoints, MAX_CHECKPOINTS
from .completion_run import start, advance, publish, MAX_STEP_STUDENTS
from .authorization import validate_completion_scope
from ..scope import MoodleScope
from ..charts import ChartStore
from .recipes import result_page


def scopes(record):
    state=record['state']
    return [{'course_id':state['course_id'],'module_ids':
        [row['cmid'] for row in state['cursor']['rows']] if state['cursor'] else []}]


def authorize(client,owner,record):
    client.checkpoint()
    MoodleScope(client,owner).require_teacher(record['state']['course_id'])
    for scope in scopes(record):validate_completion_scope(client,scope)
    client.checkpoint()


def progress(record):
    state=record['state'];cursor=state['cursor'];step=state.get('public_step',0)
    remaining=len(cursor['students'])-cursor['next_student'] if cursor else None
    return {'run_id':record['id'],'course_id':state['course_id'],'recipe_id':'activity-completion',
        'status':'collected' if state['done'] else 'running','started_at':state['started_at'],
        'processed_students':cursor['next_student'] if cursor else 0,
        'population_students':len(cursor['students']) if cursor else None,
        'remaining_students':remaining,
        'remaining_collection_steps':(remaining+MAX_STEP_STUDENTS-1)//MAX_STEP_STUDENTS if remaining is not None else None,
        'expires_at':record['expires_at'],'completion_scopes':scopes(record),
        'continue_command':f"moodle analytics continue {record['id']} --step {step}",
        'meaning':'Collection progress only, not completion rates. No chart is published until collection finishes.'}


def execute(runtime,results,client,owner,key,params):
    store=CompletionCheckpoints(results)
    # Public-step transactions include the executor and publication, while
    # their narrower locks still protect direct internal callers.
    with file_lock(store.folder/'commands',blocking=False):
        if key=='analytics.start':
            MoodleScope(client,owner).require_teacher(params['course_id'])
            validate_completion_scope(client,{'course_id':params['course_id'],'module_ids':[]})
            client.checkpoint()
            response=progress(start(store,params['course_id'],language=params['language'],tz=params['tz']))
            client.checkpoint()
            return response
        if key=='analytics.runs':
            items=[]
            paths=list(store.folder.glob('*.json'))
            if len(paths)>MAX_CHECKPOINTS:raise ValueError('Completion recovery inventory exceeds its limit')
            for path in paths:
                try:
                    record=store.read(path.stem)
                    authorize(client,owner,record)
                    if record['state'].get('published'):
                        ChartStore(runtime).read(record['state']['publication']['id'])
                except PermissionError:continue
                item=progress(record)
                if record['state'].get('published'):
                    item.update(status='published',chart_id=record['state']['publication']['id'],continue_command=None)
                items.append(item)
            client.checkpoint()
            return {'items':sorted(items,key=lambda item:item['started_at'],reverse=True),
                'meaning':'Private completion runs for this connection; source permissions were rechecked.'}
        record=store.read(params['run_id'])
        authorize(client,owner,record)
        state=record['state'];step=params['step'];current=state.get('public_step',0)
        history=state.get('step_results',{})
        if str(step) in history:
            previous=history[str(step)]
            if previous.get('chart_id'):
                response=result_page(previous['chart_id'],ChartStore(runtime).read(previous['chart_id']))
                client.checkpoint()
                return response
            client.checkpoint()
            return previous
        if step!=current:raise ValueError('Use the exact continuation command from analytics runs')
        if not state['done'] and state.get('finished_public_step')!=step:
            if state.get('active_public_step')!=step:
                state['active_public_step']=step
                state.pop('public_target',None)
                record=store.replace(record['id'],state,expected_revision=record['revision'])
            record=advance(store,client,owner,record['id'])
        if record['state']['done']:
            response=publish(store,runtime,client,record['id'])
            # Publication advances the private revision; reload before ack.
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
