"""Executable recipe registry, saved aggregate projections and bounded readback."""
from datetime import datetime
from zoneinfo import ZoneInfo

from .assignments import grading_queue
from .access import course_access
from .presentation import present, TEXT
from ..charts import ChartStore
from ..scope import MoodleScope

RECIPES = {
    'grading-queue': {'functions': ['mod_assign_get_assignments', 'mod_assign_get_submission_status'],
                      'title': 'Assignments needing grading', 'metric': 'Needs grading'},
    'course-access': {'functions': ['core_enrol_get_enrolled_users'],
                      'title': 'Last recorded course access', 'metric': 'Students'},
}


def capabilities(client, owner_id, course_id):
    MoodleScope(client, owner_id).require_teacher(course_id)
    names = {f['name'] for f in client.call('core_webservice_get_site_info').get('functions', [])}
    return {'course_id':course_id, 'recipes':[
        {'id':key, 'implemented':True, 'source_status':'unknown' if set(spec['functions']) <= names else 'unavailable',
         'advertised_functions':sorted(set(spec['functions']) & names),
         'missing_functions':sorted(set(spec['functions']) - names),
         'reason':'Function exposure is not proof of field availability; execution validates fields and coverage.'}
        for key,spec in RECIPES.items()]}


def run_recipe(runtime, client, owner_id, params, *, progress=None):
    recipe, course = params['recipe'], params['course_id']
    binding = dict(runtime.result_binding(), course_id=course)
    if recipe == 'grading-queue':
        data = grading_queue(client, owner_id, course, progress=progress)
        rows = [{'id':r['assignment_id'], 'name':f"{r['name']} (#{r['assignment_id']})", 'value':r['needs_grading'],
                 'status':r['status'], 'reason':r['reason']} for r in data['rows']]
    elif recipe == 'course-access':
        since = int(datetime.fromisoformat(params['since']).replace(tzinfo=ZoneInfo(params['tz'])).timestamp())
        data = course_access(client, owner_id, course, since=since)
        # Aggregate by default: no learner IDs are persisted or sent to AAC here.
        rows = [{'id':key,'name':key.replace('_',' '),'value':value,'status':'ok','reason':None}
                for key,value in data['metrics'].items()]
    else:
        raise ValueError('Unknown analytics recipe')
    snapshot = {**{k:v for k,v in data.items() if k != 'rows'}, 'rows':rows,
                'view_kind':'metric-bars-v1', 'language':params['language'],
                'course_name':data.get('course_name', f"{TEXT[params['language']]['course']} {course}"),
                'timezone':params['tz'],
                **present(recipe, params['language'], params['tz'], data, rows)}
    client.checkpoint()
    identity = ChartStore(runtime).save(snapshot, binding, command='moodle.analytics.run')
    client.checkpoint()
    return result_page(identity, snapshot)


def result_page(identity, snapshot, offset=0):
    if type(offset) is not int or not 0 <= offset <= len(snapshot['rows']):
        raise ValueError('Invalid analytics result offset')
    rows = snapshot['rows'][offset:offset + 20]
    next_offset = offset + len(rows)
    return {key:value for key,value in snapshot.items() if key not in {'rows','caption'}} | {
        'chart_id':identity, 'result_id':identity, 'rows':rows, 'offset':offset,
        'next_offset':next_offset if next_offset < len(snapshot['rows']) else None,
        'evidence_kind':'saved_snapshot', 'refreshed':False, 'untrusted_source':True,
        'view':f'/moodle?tab=charts&chart={identity}',
        'read_command':f'moodle analytics result {identity}'}
