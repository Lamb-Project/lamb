"""Permission-bound forum continuation handlers; registration is separate."""
from lamb.private_storage import file_lock
from .checkpoints import MAX_CHECKPOINTS
from .forum_checkpoints import ForumCheckpoints
from .forum_run import start, advance, publish
from .forum_evidence_authorization import validate_forum_evidence_scope
from .recipes import result_page
from ..scope import MoodleScope
from ..charts import ChartStore


def evidence_scope(state):
    context = state.get('context')
    return dict(state['scope'],discussion_ids=sorted(
        row['discussion_id'] for row in context['discussions']) if context else [])


def authorize(client, owner, state):
    client.checkpoint()
    validate_forum_evidence_scope(client,evidence_scope(state))
    MoodleScope(client,owner).require_teacher(state['scope']['course_id'])
    client.checkpoint()


def progress(record):
    state=record['state']
    return {'run_id':record['id'],**state['scope'],'recipe_id':state['recipe'],
        'status':'collected' if state['done'] else 'running',
        'started_at':state['started_at'],'expires_at':record['expires_at'],
        'processed_post_records':state['posts'],'completed_discussions':len(state['threads']),
        'population_students':len(state['context']['students']) if state['context'] else None,
        'remaining_post_records':None,'remaining_collection_steps':None,
        'window':{'since':state['since'],'until':state['until'],'until_exclusive':True,'timezone':state['tz']},
        'forum_scopes':[evidence_scope(state)],
        'continue_command':f"moodle analytics continue {record['id']} --step {state.get('public_step',0)}",
        'meaning':'Collection progress only. No contribution quality, learning or resolution inference.'}


def execute(runtime, results, client, owner, key, params):
    store=ForumCheckpoints(results)
    with file_lock(store.folder/'commands',blocking=False):
        if key=='analytics.start':
            scope={key:params[key] for key in ('course_id','forum_id','group_id')}
            authorize(client,owner,{'scope':scope})
            record=start(store,scope['course_id'],scope['forum_id'],group_id=scope['group_id'],
                since=params['since'],until=params['until'],recipe=params['recipe'],
                language=params['language'],tz=params['tz'])
            client.checkpoint()
            return progress(record)
        if key=='analytics.runs':
            paths=list(store.folder.glob('*.json'))
            if len(paths)>MAX_CHECKPOINTS:
                raise ValueError('Forum recovery inventory exceeds its limit')
            items=[]
            for path in paths:
                try:
                    record=store.read(path.stem)
                    authorize(client,owner,record['state'])
                    item=progress(record)
                    chart_id=record['state'].get('published_chart_id')
                    if chart_id:
                        ChartStore(runtime).read(chart_id)
                        item.update(status='published',chart_id=chart_id,continue_command=None)
                except PermissionError:
                    continue
                items.append(item)
            client.checkpoint()
            return {'items':sorted(items,key=lambda item:item['started_at'],reverse=True)}
        if key!='analytics.continue':
            raise ValueError('Unknown forum continuation operation')
        step=params['step']
        if type(step) is not int or step<0:
            raise ValueError('Invalid forum continuation step')
        record=store.read(params['run_id'])
        state=record['state']
        authorize(client,owner,state)
        previous=state.get('step_results',{}).get(str(step))
        if previous is not None:
            response=(result_page(previous['chart_id'],ChartStore(runtime).read(previous['chart_id']))
                      if previous.get('chart_id') else previous)
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
            response=publish(store,runtime,client,record['id'],recipe=record['state']['recipe'])
            record=store.read(record['id'])
            record['state']['published_chart_id']=response['chart_id']
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
