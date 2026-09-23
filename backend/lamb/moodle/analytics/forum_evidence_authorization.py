"""Recheck exact saved discussion scopes without collecting fresh post evidence."""
from moodle_cli.client.exceptions import MoodleAPIError
from .client import FORUM_EVIDENCE_SCOPE_FUNCTION


def validate_forum_evidence_scope(client, scope):
    if not isinstance(scope,dict) or set(scope)!={'course_id','forum_id','group_id','discussion_ids'}:
        raise PermissionError('Invalid saved forum scope')
    for key in ('course_id','forum_id','group_id'):
        if type(scope[key]) is not int or scope[key] < (0 if key=='group_id' else 1):
            raise PermissionError('Invalid saved forum scope')
    ids = scope['discussion_ids']
    if (not isinstance(ids,list) or len(ids)>1000 or
            any(type(value) is not int or value<1 for value in ids) or len(set(ids))!=len(ids)):
        raise PermissionError('Invalid saved forum discussions')
    for offset in range(0,max(1,len(ids)),100):
        params = dict(courseid=scope['course_id'],forumid=scope['forum_id'],
                      groupid=scope['group_id'],discussionids=ids[offset:offset+100])
        try:
            response = client.call(FORUM_EVIDENCE_SCOPE_FUNCTION,**params)
        except MoodleAPIError:
            raise PermissionError('Saved forum evidence is no longer available') from None
        expected = dict(params,authorized=True)
        if (not isinstance(response,dict) or response != expected or response.get('authorized') is not True
                or any(type(response.get(key)) is not int for key in ('courseid','forumid','groupid'))
                or not isinstance(response.get('discussionids'),list)
                or any(type(value) is not int for value in response['discussionids'])):
            raise PermissionError('Saved forum authority response does not match')
