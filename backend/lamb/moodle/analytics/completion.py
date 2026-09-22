"""Observed completion states, not required-path progress or learning claims."""
from datetime import datetime, timezone

from .events import _students
from ..scope import MoodleScope
from ..forum_activity import preview

MAX_COMPLETION_STUDENTS = 100
MAX_COMPLETION_MODULES = 100
STATES = ('incomplete','complete','complete_pass','complete_fail')


def activity_completion(client, owner_id, course_id):
    scope = MoodleScope(client,owner_id)
    course = scope.require_teacher(course_id)
    course_name = preview(scope.own_courses()[course].fullname,160)[0]
    students, population = _students(client,course,0)
    if not population['population_exhausted'] or population['role_unknown']:
        raise ValueError('Complete student population required for completion counts')
    if len(students)>MAX_COMPLETION_STUDENTS:
        raise ValueError('Completion collection exceeds per-run student limit; continuation is not yet supported')
    sections=client.call('core_course_get_contents',courseid=course,options=[{'name':'excludecontents','value':1}])
    if not isinstance(sections,list):
        raise ValueError('Completion activity inventory unavailable')
    inventory={}
    seen=set()
    disabled=0
    for section in sections:
        if not isinstance(section,dict) or not isinstance(section.get('modules',[]),list):
            raise ValueError('Invalid completion section')
        for module in section.get('modules',[]):
            identity=module.get('id'); tracking=module.get('completion')
            if type(identity) is not int or identity<1 or identity in seen:
                raise ValueError('Invalid completion module ID')
            seen.add(identity)
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
    for student in sorted(students):
        client.checkpoint()
        response=client.call('core_completion_get_activities_completion_status',courseid=course,userid=student)
        if not isinstance(response,dict) or response.get('warnings') or not isinstance(response.get('statuses'),list):
            raise ValueError('Completion source is incomplete')
        if len(response['statuses'])>MAX_COMPLETION_MODULES:
            raise ValueError('Completion source exceeds module limit')
        records={}
        for record in response['statuses']:
            identity=record.get('cmid')
            if type(identity) is not int or identity<1 or identity in records:
                raise ValueError('Invalid or duplicate completion status')
            if identity not in inventory:
                raise ValueError('Completion inventory changed or source returned an out-of-scope activity')
            records[identity]=record
        for identity,row in inventory.items():
            record=records.get(identity)
            if record is None:
                row['unknown']+=1
                continue
            tracking=record.get('tracking')
            if type(tracking) is not int or tracking!=row['tracking']:
                raise ValueError('Completion tracking changed during collection')
            if record.get('istrackeduser') is False:
                row['untracked']+=1
                continue
            state=record.get('state')
            if record.get('istrackeduser') is not True or type(state) is not int or state not in range(4):
                row['unknown']+=1
                continue
            row[STATES[state]]+=1
            overall=record.get('isoverallcomplete')
            if type(overall) is bool:
                row['overall_complete']+=int(overall)
            else:
                row['overall_unknown']+=1
            override=record.get('overrideby')
            if 'overrideby' not in record or (override is not None and (type(override) is not int or override<0)):
                row['override_unknown']+=1
            elif override:
                row['overridden']+=1
    client.checkpoint()
    rows=list(inventory.values())
    return {'schema_version':1,'recipe':{'id':'activity-completion','version':1},
        'course_id':course,'course_name':course_name,'as_of':datetime.now(timezone.utc).isoformat(),'timezone':'UTC',
        'rows':rows,'coverage':{**population,'modules_read':len(rows),'tracking_disabled_modules':disabled,
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
            'Per-run limits do not yet provide durable large-course continuation.']}
