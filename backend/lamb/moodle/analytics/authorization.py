"""Revalidate saved event-derived evidence without recollecting events."""
from moodle_cli.client.exceptions import MoodleAPIError
from .client import SCOPE_FUNCTION, GRADE_SCOPE_FUNCTION, COMPLETION_SCOPE_FUNCTION, DEFAULT_DATES_FUNCTION


def validate_date_scope(client, scope):
    if not isinstance(scope,dict) or set(scope)!={'course_id','module_ids'}:
        raise PermissionError('Invalid date evidence scope')
    course,modules=scope['course_id'],scope['module_ids']
    if (type(course) is not int or course<1 or not isinstance(modules,list) or not 1<=len(modules)<=100
            or any(type(value) is not int or value<1 for value in modules) or len(set(modules))!=len(modules)):
        raise PermissionError('Invalid date evidence scope')
    try:
        data=client.call(DEFAULT_DATES_FUNCTION,courseid=course,cmids=modules,scopeonly=1)
    except MoodleAPIError:
        raise PermissionError('Date evidence permissions are no longer available') from None
    if (not isinstance(data,dict) or set(data)!={'courseid','cmids','authorized','scopeonly','basis','relative_dates','dates'}
            or data['authorized'] is not True or data['scopeonly'] is not True
            or type(data['courseid']) is not int or data['courseid']!=course
            or not isinstance(data['cmids'],list) or any(type(value) is not int for value in data['cmids'])
            or data['cmids']!=modules or data['basis']!='stored_course_defaults'
            or type(data['relative_dates']) is not bool or data['dates']!=[]):
        raise PermissionError('Date evidence authorization mismatch')


def validate_completion_scope(client, scope):
    if not isinstance(scope,dict) or set(scope) != {'course_id','module_ids'}:
        raise PermissionError('Invalid completion evidence scope')
    course, modules = scope['course_id'], scope['module_ids']
    if (type(course) is not int or course < 1 or not isinstance(modules,list) or len(modules)>100 or
            any(type(v) is not int or v<1 for v in modules) or len(set(modules)) != len(modules)):
        raise PermissionError('Invalid completion evidence scope')
    try:
        data = client.call(COMPLETION_SCOPE_FUNCTION,courseid=course,cmids=modules)
    except MoodleAPIError:
        raise PermissionError('Completion evidence permissions are no longer available') from None
    if (not isinstance(data,dict) or data.get('authorized') is not True or type(data.get('courseid')) is not int or
            not isinstance(data.get('cmids'),list) or any(type(v) is not int for v in data['cmids']) or
            data != {'authorized':True,'courseid':course,'cmids':modules}):
        raise PermissionError('Completion evidence authorization mismatch')


def validate_grade_scope(client, scope):
    if (not isinstance(scope,dict) or set(scope) != {'course_id','assignment_id'} or
            any(type(v) is not int or v < 1 for v in scope.values())):
        raise PermissionError('Invalid grade evidence scope')
    expected = {'authorized':True,'courseid':scope['course_id'],'assignmentid':scope['assignment_id']}
    try:
        data = client.call(GRADE_SCOPE_FUNCTION, courseid=scope['course_id'], assignmentid=scope['assignment_id'])
    except MoodleAPIError:
        raise PermissionError('Grade evidence permissions are no longer available') from None
    if (not isinstance(data,dict) or data != expected or data.get('authorized') is not True or
            type(data.get('courseid')) is not int or type(data.get('assignmentid')) is not int):
        raise PermissionError('Grade evidence authorization mismatch')


def validate_resource_scope(client, scope):
    if not isinstance(scope,dict) or set(scope) != {'course_id','group_id','module_ids'}:
        raise PermissionError('Invalid resource evidence scope')
    course, group, modules = scope['course_id'], scope['group_id'], scope['module_ids']
    if type(course) is not int or course < 1 or type(group) is not int or group < 0 or not isinstance(modules,list):
        raise PermissionError('Invalid resource evidence scope')
    if len(modules)>100 or any(type(v) is not int or v<1 for v in modules) or len(set(modules)) != len(modules):
        raise PermissionError('Invalid resource evidence scope')
    try:
        data = client.call(SCOPE_FUNCTION,courseid=course,groupid=group,cmids=modules)
    except MoodleAPIError:
        raise PermissionError('Resource evidence permissions are no longer available') from None
    if (not isinstance(data,dict) or data.get('authorized') is not True or
            type(data.get('courseid')) is not int or type(data.get('groupid')) is not int or
            not isinstance(data.get('cmids'),list) or any(type(v) is not int for v in data['cmids']) or
            data != {'authorized':True,'courseid':course,'groupid':group,'cmids':modules}):
        raise PermissionError('Resource evidence authorization mismatch')
