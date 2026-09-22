"""Observed completion states, not required-path progress or learning claims."""
from datetime import datetime, timezone
import hashlib
import json

from .events import _students
from .authorization import validate_completion_scope
from ..scope import MoodleScope
from ..forum_activity import preview
from .completion_state import STATES, MAX_COMPLETION_MODULES, initial_cursor, advance_cursor

MAX_COMPLETION_STUDENTS = 100


def completion_context(client, owner_id, course_id, *, student_limit=MAX_COMPLETION_STUDENTS):
    scope = MoodleScope(client,owner_id)
    course = scope.require_teacher(course_id)
    validate_completion_scope(client,{'course_id':course,'module_ids':[]})
    course_name = preview(scope.own_courses()[course].fullname,160)[0]
    students, population = _students(client,course,0)
    if not population['population_exhausted'] or population['role_unknown']:
        raise ValueError('Complete student population required for completion counts')
    if len(students)>student_limit:
        raise ValueError('Completion collection exceeds per-run student limit; continuation is not yet supported')
    sections=client.call('core_course_get_contents',courseid=course,options=[{'name':'excludecontents','value':1}])
    if not isinstance(sections,list):
        raise ValueError('Completion activity inventory unavailable')
    inventory={}
    seen=set()
    disabled=0
    module_facts=[]
    for section in sections:
        if not isinstance(section,dict) or not isinstance(section.get('modules',[]),list):
            raise ValueError('Invalid completion section')
        for module in section.get('modules',[]):
            if not isinstance(module,dict):
                raise ValueError('Invalid completion module')
            identity=module.get('id'); tracking=module.get('completion')
            if type(identity) is not int or identity<1 or identity in seen:
                raise ValueError('Invalid completion module ID')
            seen.add(identity)
            module_facts.append({key:module.get(key) for key in ('id','name','completion','availability',
                'uservisible','visible','completiongradeitemnumber','completionpassgrade')})
            if module.get('uservisible') is False:
                continue
            if type(tracking) is not int or tracking not in (0,1,2):
                raise ValueError('Completion tracking mode unavailable')
            if tracking==0:
                disabled+=1
                continue
            inventory[identity]={'cmid':identity,'name':preview(module['name'],160)[0],
                'tracking':tracking,'availability_configured':bool(module['availability']) if 'availability' in module else None,
                'learner_eligibility':'not_collected',
                **{state:0 for state in STATES},'unknown':0,'untracked':0,'overridden':0,
                'override_unknown':0,'overall_complete':0,'overall_unknown':0,'population_students':len(students)}
    if len(inventory)>MAX_COMPLETION_MODULES:
        raise ValueError('Completion collection exceeds module limit')
    validate_completion_scope(client,{'course_id':course,'module_ids':list(inventory)})
    cursor = initial_cursor(students, list(inventory.values()))
    fingerprint = hashlib.sha256(json.dumps({'students':sorted(students),'population':population,
        'course_name':course_name,'modules':sorted(module_facts,key=lambda item:item['id'])},
        sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'course_id':course,'course_name':course_name,'population':population,'disabled':disabled,
            'cursor':cursor,'fingerprint':fingerprint}


def activity_completion(client, owner_id, course_id):
    context = completion_context(client,owner_id,course_id)
    course=context['course_id']; cursor=context['cursor']
    for student in cursor['students']:
        client.checkpoint()
        response=client.call('core_completion_get_activities_completion_status',courseid=course,userid=student)
        cursor = advance_cursor(cursor, student, response)
    client.checkpoint()
    return completion_snapshot(context,cursor,datetime.now(timezone.utc).isoformat())


def completion_snapshot(context, cursor, as_of, *, resumable=False):
    """Project only finished aggregate evidence, never private learner cursors."""
    if cursor['next_student'] != len(cursor['students']):
        raise ValueError('Completion collection is not finished')
    fields=('cmid','name','tracking','availability_configured','learner_eligibility',*STATES,
        'unknown','untracked','overridden','override_unknown','overall_complete','overall_unknown','population_students')
    rows=[{key:row[key] for key in fields} for row in cursor['rows']]
    population={key:context['population'][key] for key in
        ('student_rows','users_scanned','role_unknown','population_exhausted') if key in context['population']}
    return {'schema_version':1,'recipe':{'id':'activity-completion','version':1},
        'course_id':context['course_id'],'course_name':context['course_name'],'as_of':as_of,'timezone':'UTC',
        'rows':rows,'coverage':{**population,'modules_read':len(rows),'tracking_disabled_modules':context['disabled'],
            'complete':all(row['unknown']==0 and row['override_unknown']==0 and row['overall_unknown']==0 for row in rows)},
        'source':'core_completion_get_activities_completion_status per current active student-role enrolment',
        'limitations':['States are observed completion configuration, not proof of learning or attainment.',
            'Complete, complete-pass and complete-fail remain separate states.',
            'Overall completion uses Moodle isoverallcomplete, not an inferred merge of the state categories.',
            'Required activities, learner-specific availability and schedules were not collected.',
            'No claim of being behind schedule or following a mandatory sequence is supported.',
            'Untracked learners and missing source states are not incomplete learners.',
            'Override actors and learner identifiers are not retained.',
            'Current configuration and enrolment are not historical state; collection is not atomic.',
            ('Collected across bounded resumable steps; values were observed at different times.' if resumable else
             'Per-run limits do not yet provide durable large-course continuation.')]}
