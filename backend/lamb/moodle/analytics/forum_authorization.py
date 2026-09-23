"""Exact current discussion authority, separate from reading its posts."""
from moodle_cli.client.exceptions import MoodleAPIError
from .client import FORUM_SCOPE_FUNCTION


def validate_forum_scope(client, scope):
    fields = {'course_id':'courseid', 'forum_id':'forumid',
              'discussion_id':'discussionid', 'group_id':'groupid'}
    if (not isinstance(scope, dict) or set(scope) != set(fields)
            or any(type(value) is not int for value in scope.values())
            or any(scope[key] < (0 if key == 'group_id' else 1) for key in fields)):
        raise PermissionError('Invalid forum evidence scope')
    params = {value:scope[key] for key,value in fields.items()}
    try:
        data = client.call(FORUM_SCOPE_FUNCTION, **params)
    except MoodleAPIError:
        raise PermissionError('Forum evidence permissions are no longer available') from None
    expected = dict(params, authorized=True)
    if (not isinstance(data, dict) or set(data) != set(expected) or data['authorized'] is not True
            or any(type(data[key]) is not int for key in params) or data != expected):
        raise PermissionError('Forum evidence authorization mismatch')
