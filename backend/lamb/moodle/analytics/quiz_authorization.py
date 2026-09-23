"""Recheck exact saved quiz evidence authority without collecting attempts."""
from moodle_cli.client.exceptions import MoodleAPIError
from .client import QUIZ_SCOPE_FUNCTION


def validate_quiz_scope(client,scope):
    if (not isinstance(scope,dict) or set(scope)!={'course_id','quiz_id','group_id'}
            or any(type(value) is not int for value in scope.values())
            or scope['course_id']<1 or scope['quiz_id']<1 or scope['group_id']<0):
        raise PermissionError('Invalid quiz evidence scope')
    expected={'authorized':True,'courseid':scope['course_id'],'quizid':scope['quiz_id'],'groupid':scope['group_id']}
    try:
        data=client.call(QUIZ_SCOPE_FUNCTION,courseid=scope['course_id'],quizid=scope['quiz_id'],groupid=scope['group_id'])
    except MoodleAPIError:
        raise PermissionError('Quiz evidence permissions are no longer available') from None
    if (not isinstance(data,dict) or set(data)!=set(expected) or data['authorized'] is not True
            or any(type(data[key]) is not int for key in ('courseid','quizid','groupid')) or data!=expected):
        raise PermissionError('Quiz evidence authorization mismatch')
