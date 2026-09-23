"""Executable recipe registry, saved aggregate projections and bounded readback."""
from datetime import datetime
import time
from zoneinfo import ZoneInfo

from .assignments import grading_queue
from .access import course_access
from .events import resource_reach, view_activity
from .grades import grade_distribution
from .completion import activity_completion
from .deadlines import deadline_calendar
from .client import EVENT_FUNCTION, SCOPE_FUNCTION, GRADE_SCOPE_FUNCTION, COMPLETION_SCOPE_FUNCTION, DEFAULT_DATES_FUNCTION
from .authorization import validate_resource_scope, validate_grade_scope, validate_completion_scope
from .presentation import present, TEXT
from ..charts import ChartStore
from ..scope import MoodleScope

RECIPES = {
    'quiz-overview': {'functions':['local_lambanalytics_quiz_scope','local_lambanalytics_quiz_attempts',
                                  'core_enrol_get_enrolled_users'],
                      'title':'Quiz attempts and raw score distribution','metric':'Scored attempts'},
    'deadlines': {'functions':[DEFAULT_DATES_FUNCTION,'core_course_get_contents'],
                  'title':'Stored course schedule','metric':'Deadlines'},
    'view-distribution': {'functions':[EVENT_FUNCTION,SCOPE_FUNCTION,'core_enrol_get_enrolled_users','core_course_get_contents'],
                    'title':'Recorded views per student','metric':'Students'},
    'active-day-distribution': {'functions':[EVENT_FUNCTION,SCOPE_FUNCTION,'core_enrol_get_enrolled_users','core_course_get_contents'],
                    'title':'Observed active days per student','metric':'Students'},
    'view-heatmap': {'functions':[EVENT_FUNCTION,SCOPE_FUNCTION,'core_enrol_get_enrolled_users','core_course_get_contents'],
                    'title':'Recorded views by weekday and hour','metric':'Recorded views'},
    'view-trends': {'functions':[EVENT_FUNCTION,SCOPE_FUNCTION,'core_enrol_get_enrolled_users','core_course_get_contents'],
                    'title':'Recorded view trends','metric':'Recorded views'},
    'activity-completion': {'functions':[COMPLETION_SCOPE_FUNCTION,'core_completion_get_activities_completion_status','core_course_get_contents','core_enrol_get_enrolled_users'],
                            'title':'Observed activity completion','metric':'Incomplete'},
    'grade-distribution': {'functions':[GRADE_SCOPE_FUNCTION,'mod_assign_get_assignments','mod_assign_get_grades','core_enrol_get_enrolled_users'],
                          'title':'Raw assignment grade distribution','metric':'Students'},
    'grading-queue': {'functions': ['mod_assign_get_assignments', 'mod_assign_get_submission_status'],
                      'title': 'Assignments needing grading', 'metric': 'Needs grading'},
    'course-access': {'functions': ['core_enrol_get_enrolled_users'],
                      'title': 'Last recorded course access', 'metric': 'Students'},
    'resource-reach': {'functions': [EVENT_FUNCTION,SCOPE_FUNCTION,'core_enrol_get_enrolled_users','core_course_get_contents'],
                       'title':'Recorded resource reach','metric':'Students with recorded views'},
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
    if recipe == 'deadlines':
        zone = ZoneInfo(params['tz'])
        since = int(datetime.fromisoformat(params['since']).replace(tzinfo=zone).timestamp())
        until = int(datetime.fromisoformat(params['until']).replace(tzinfo=zone).timestamp())
        data = deadline_calendar(client,owner_id,course,since=since,until=until,timezone=params['tz'])
        rows = [{**row,'id':row['cmid'],'name':f"{row['name']} (#{row['cmid']})",
                 'status':'ok','reason':None} for row in data['rows']]
        if data['date_scopes']:
            binding['date_scopes'] = data['date_scopes']
    elif recipe == 'activity-completion':
        data = activity_completion(client,owner_id,course)
        rows = [{**r,'id':r['cmid'],'name':f"{r['name']} (#{r['cmid']})",'value':r['incomplete'],
                 'status':'ok','reason':None} for r in data['rows']]
        completion_scope = {'course_id':course,'module_ids':[r['cmid'] for r in rows]}
        validate_completion_scope(client,completion_scope)
        binding['completion_scopes'] = [completion_scope]
        data['completion_scopes'] = [completion_scope]
    elif recipe == 'grade-distribution':
        data = grade_distribution(client,owner_id,course,params['assignment_id'])
        rows = [{**r,'id':i,'name':f"[{r['lower']}, {r['upper']}{']' if r['upper_inclusive'] else ')'} %",
                 'value':r['count'],'status':'ok','reason':None} for i,r in enumerate(data['rows'])]
        grade_scope = {'course_id':course,'assignment_id':params['assignment_id']}
        validate_grade_scope(client,grade_scope)
        binding['grade_scopes'] = [grade_scope]
        data['grade_scopes'] = [grade_scope]
    elif recipe == 'grading-queue':
        data = grading_queue(client, owner_id, course, progress=progress)
        rows = [{'id':r['assignment_id'], 'name':f"{r['name']} (#{r['assignment_id']})", 'value':r['needs_grading'],
                 'status':r['status'], 'reason':r['reason']} for r in data['rows']]
    elif recipe == 'course-access':
        since = int(datetime.fromisoformat(params['since']).replace(tzinfo=ZoneInfo(params['tz'])).timestamp())
        data = course_access(client, owner_id, course, since=since)
        # Aggregate by default: no learner IDs are persisted or sent to AAC here.
        rows = [{'id':key,'name':key.replace('_',' '),'value':value,'status':'ok','reason':None}
                for key,value in data['metrics'].items()]
    elif recipe in {'resource-reach','view-trends','view-heatmap','view-distribution','active-day-distribution'}:
        since = int(datetime.fromisoformat(params['since']).replace(tzinfo=ZoneInfo(params['tz'])).timestamp())
        until = (int(datetime.fromisoformat(params['until']).replace(tzinfo=ZoneInfo(params['tz'])).timestamp())
                 if params.get('until') else int(time.time()))
        if recipe != 'resource-reach':
            data=view_activity(client,owner_id,course,since=since,until=until,
                timezone=params['tz'],group_id=params.get('group_id') or 0)
            data.update(schema_version=1,recipe={'id':recipe,'version':1},window=data['view_time']['window'],
                limitations=data['view_time']['limitations'])
            if recipe=='view-trends':
                rows=[{**r,'id':r['date'],'name':r['date'],'value':r['recorded_views'],'status':'ok','reason':None}
                    for r in data['view_time']['daily']]
            elif recipe=='view-heatmap':
                rows=[{**r,'id':f"{r['weekday']}-{r['hour']}",'value':r['recorded_views'],'status':'ok','reason':None}
                    for r in data['view_time']['weekday_hour']]
            else:
                from .view_distribution import display_bins
                key='student_view_counts' if recipe=='view-distribution' else 'student_active_days'
                data['distribution']=data['view_time'][key]
                data['distribution_metric']=key
                rows=[{**r,'id':i,'name':str(r['lower']) if r['lower']==r['upper'] else f"{r['lower']}–{r['upper']}",
                    'value':r['students'],'status':'ok','reason':None}
                    for i,r in enumerate(display_bins(data['distribution']))]
            module_ids=data.pop('module_ids')
        else:
            data = resource_reach(client, owner_id, course, since=since, until=until, group_id=params.get('group_id') or 0, window_timezone=params['tz'])
            rows = [{**r,'id':r['cmid'],'name':f"{r['name']} (#{r['cmid']})",
                     'value':r['unique_student_viewers'],'status':'ok','reason':None} for r in data['rows']]
            module_ids=[r['cmid'] for r in rows]
        resource_scope = {'course_id':course,'group_id':data['group_id'],'module_ids':module_ids}
        validate_resource_scope(client, resource_scope)
        binding['resource_scopes'] = [resource_scope]
        data['resource_scopes'] = [resource_scope]
    else:
        raise ValueError('Unknown analytics recipe')
    snapshot = format_snapshot(recipe,data,rows,params)
    client.checkpoint()
    identity = ChartStore(runtime).save(snapshot, binding, command='moodle.analytics.run')
    client.checkpoint()
    return result_page(identity, snapshot)


def format_snapshot(recipe, data, rows, params):
    """Shared deterministic presentation for fresh and recovered collections."""
    course=params['course_id']
    snapshot = {**{k:v for k,v in data.items() if k != 'rows'}, 'rows':rows,
                'view_kind':'metric-bars-v1', 'language':params['language'],
                'course_name':data.get('course_name', f"{TEXT[params['language']]['course']} {course}"),
                'timezone':params['tz'],
                **present(recipe, params['language'], params['tz'], data, rows)}
    snapshot['as_of_local'] = datetime.fromisoformat(data['as_of'].replace('Z', '+00:00')).astimezone(
        ZoneInfo(params['tz'])).isoformat()
    snapshot['snapshot_date_label'] = f"{snapshot['as_of_local']} ({params['tz']})"
    if recipe == 'course-access':
        coverage = data['coverage']
        snapshot['population_counts'] = {
            'included_students': coverage['student_rows'],
            'excluded_non_students': coverage['non_student_rows'],
            'unknown_role_enrolments': coverage['role_unknown'],
            'all_enrolments_scanned': coverage['users_scanned'],
        }
    return snapshot


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
