"""Minimize the standard forum exporter without treating display dates as raw dates.

Caller establishes current forum/group authority and rechecks after collection.
This adapter does not prove inventory exhaustion or authorization by itself.
"""
from .forum_participation import MAX_POSTS, _integer


def normalize_discussion(response, *, course_id, forum_id, discussion):
    if not isinstance(discussion, dict):
        raise ValueError('Invalid forum discussion metadata')
    for value in (course_id, forum_id):
        _integer(value, 1)
    did = _integer(discussion['id'], 1)
    start = _integer(discussion['timestart'])
    _integer(discussion['timeend'])
    # Moodle's post exporter uses max(stored created, discussion timestart)
    # when timed posts are enabled. Raw creation cannot be reconstructed.
    if start:
        raise ValueError('Timed discussion requires a verified raw-creation source')
    if (not isinstance(response, dict) or type(response.get('courseid')) is not int
            or type(response.get('forumid')) is not int
            or response['courseid'] != course_id or response['forumid'] != forum_id):
        raise ValueError('Mismatched forum evidence scope')
    if not isinstance(response.get('warnings'), list):
        raise ValueError('Unknown forum source warnings')
    source = response.get('posts')
    if not isinstance(source, list) or len(source) > MAX_POSTS:
        raise ValueError('Forum post response bound exceeded')
    posts, seen = [], set()
    for row in source:
        if not isinstance(row, dict):
            raise ValueError('Invalid forum post object')
        pid = _integer(row['id'], 1)
        if pid in seen or type(row.get('discussionid')) is not int or row['discussionid'] != did:
            raise ValueError('Duplicate or foreign forum post')
        seen.add(pid)
        for flag in ('hasparent', 'isdeleted', 'isprivatereply'):
            if type(row.get(flag)) is not bool:
                raise ValueError('Unknown forum source visibility or ancestry')
        if not isinstance(row.get('capabilities'), dict) or not isinstance(row.get('author'), dict):
            raise ValueError('Missing forum visibility or author metadata')
        view = row['capabilities'].get('view')
        if type(view) is not bool:
            raise ValueError('Unknown forum post visibility')
        parent = row.get('parentid')
        if row['hasparent']:
            _integer(parent, 1)
        elif parent is not None:
            raise ValueError('Inconsistent forum root')
        author = row.get('author', {}).get('id')
        stamp = row.get('timecreated')
        if author is not None:
            _integer(author, 1)
        if stamp is not None:
            _integer(stamp)
        posts.append({'id':pid, 'parent_id':parent,
            'author_id':author if view and not row['isdeleted'] else None,
            'created':stamp if view and not row['isdeleted'] else None,
            'deleted':row['isdeleted'], 'private':row['isprivatereply']})
    return {'id':did, 'forum_id':forum_id, 'posts':posts,
        'complete':not response['warnings'], 'timestamp_basis':'stored_creation_untimed_discussion'}
