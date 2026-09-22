"""Raw latest-attempt assignment grades, not final/released gradebook marks."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .assignments import assignment_inventory
from .events import _students
from .authorization import validate_grade_scope
from ..forum_activity import preview

MAX_GRADE_ROWS = 1000


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('Invalid numeric grade')
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid numeric grade') from None
    if not result.is_finite():
        raise ValueError('Nonfinite grade')
    return result


def _percentile(values, fraction):
    """Linear interpolation at (N-1)*p, including singleton populations."""
    position = Decimal(len(values) - 1) * fraction
    index = int(position)
    return values[index] + (values[min(index + 1, len(values) - 1)] - values[index]) * (position - index)


def grade_distribution(client, owner_id, course_id, assignment_id):
    if type(assignment_id) is not int or assignment_id <= 0:
        raise ValueError('Use a positive assignment ID')
    course, course_name, assignments = assignment_inventory(client, owner_id, course_id)
    matches = [a for a in assignments if a['id'] == assignment_id]
    if len(matches) != 1:
        raise PermissionError('Assignment is not in the visible course inventory')
    assignment = matches[0]
    validate_grade_scope(client, {'course_id':course,'assignment_id':assignment_id})
    maximum = _number(assignment.get('grade'))
    if maximum <= 0:
        raise ValueError('Numeric distribution requires a positive point maximum; scales and no-grade items are unsupported')
    if assignment.get('teamsubmission', 1):
        raise ValueError('Team assignment grade population is not yet supported')
    students, population = _students(client, course, 0)
    if not population['population_exhausted'] or population['role_unknown']:
        raise ValueError('Complete student population required for grade denominator')
    client.checkpoint()
    response = client.call('mod_assign_get_grades', assignmentids=[assignment_id], since=0)
    warnings = response.get('warnings', [])
    for warning in warnings:
        if warning.get('warningcode') == '1':
            raise PermissionError('Assignment grade access denied')
        if not (warning.get('warningcode') == '3' and warning.get('item') == 'assignment'
                and warning.get('itemid') == assignment_id):
            raise ValueError('Grade source returned an unrecognized warning')
    groups = response.get('assignments')
    if not isinstance(groups, list) or len(groups) > 1:
        raise ValueError('Invalid grade response')
    if groups and (groups[0].get('assignmentid') != assignment_id or warnings):
        raise ValueError('Inconsistent grade response scope')
    if not groups and not warnings:
        raise ValueError('Missing grade response coverage')
    records = groups[0].get('grades') if groups else []
    if not isinstance(records, list) or len(records) > MAX_GRADE_ROWS:
        raise ValueError('Grade response exceeds supported row limit')
    values, seen, excluded, sentinel = [], set(), 0, 0
    for record in records:
        client.checkpoint()
        user = record.get('userid')
        attempt = record.get('attemptnumber')
        if type(user) is not int or user <= 0 or user in seen or type(attempt) is not int or attempt < 0:
            raise ValueError('Invalid or duplicate latest-attempt grade')
        seen.add(user)
        if user not in students:
            excluded += 1
            continue
        grade = _number(record.get('grade'))
        if grade == -1:
            sentinel += 1
            continue
        if not 0 <= grade <= maximum:
            raise ValueError('Raw grade outside assignment point range')
        values.append(grade * 100 / maximum)
    values.sort()
    counts = [0] * 10
    for value in values:
        counts[min(int(value // 10), 9)] += 1
    summary = {'valid_n':len(values), 'missing_n':len(students)-len(values), 'population_n':len(students),
               'mean':float(sum(values) / len(values)) if values else None,
               **{name:float(_percentile(values, p)) if values else None
                  for name, p in [('q1',Decimal('.25')),('median',Decimal('.5')),('q3',Decimal('.75'))]}}
    client.checkpoint()
    return {'schema_version':1, 'recipe':{'id':'grade-distribution','version':1},
            'course_id':course, 'course_name':course_name, 'assignment_id':assignment_id,
            'assignment_name':preview(assignment.get('name',''),160)[0],
            'as_of':datetime.now(timezone.utc).isoformat(), 'timezone':'UTC',
            'grade_min':0, 'grade_max':float(maximum), 'grade_kind':'raw_latest_attempt_assignment_grade',
            'marking_workflow':bool(assignment.get('markingworkflow')), 'grade_released':None,
            'rows':[{'lower':i*10,'upper':(i+1)*10,'upper_inclusive':i==9,'count':n} for i,n in enumerate(counts)],
            'metrics':summary, 'coverage':{**population, 'complete':True, 'records_read':len(records),
                'excluded_nonpopulation_records':excluded, 'ungraded_sentinel_records':sentinel},
            'source':'mod_assign_get_grades, latest submission attempt join',
            'limitations':['Raw assignment grades are not final, overridden or excluded gradebook values.',
                'Missing includes absent latest-attempt grade records and the Moodle -1 ungraded sentinel.',
                'Grade release, hidden gradebook state and feedback publication were not collected.',
                'Population is currently active enrolled users with role shortname student.',
                'Bins are left-inclusive, right-exclusive except the final bin includes 100.',
                'Quartiles use linear interpolation at (N-1)*p on normalized percentages.',
                'Source has no paging; oversized responses fail rather than produce partial distributions.',
                'Collection is not an atomic course snapshot.']}
