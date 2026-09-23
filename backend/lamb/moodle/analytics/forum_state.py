"""Private bounded forum page transitions. Caller owns ACL and durable storage.

Never return these author join IDs to a model without a separate authorized
learner-table projection. A fixed upper ID does not make collection atomic.
"""
from copy import deepcopy
import hashlib
import json
from .forum_participation import MAX_POSTS, _integer

SCOPE_KEYS = ('courseid', 'forumid', 'discussionid', 'groupid')
ROW_KEYS = {'id', 'parent_id', 'author_id', 'created', 'modified'}


def initial_cursor(course_id, forum_id, discussion_id, group_id=0):
    return {'courseid':_integer(course_id,1), 'forumid':_integer(forum_id,1),
        'discussionid':_integer(discussion_id,1), 'groupid':_integer(group_id),
        'afterid':0, 'throughid':None, 'records':[], 'done':False,
        'first_collected_at':None, 'last_collected_at':None, 'last_page':None}


def advance_cursor(state, after_id, page):
    """Pure replacement; replay of identical last page is idempotent."""
    _integer(after_id)
    if not isinstance(page, dict):
        raise ValueError('Invalid forum source page')
    for key in SCOPE_KEYS:
        if _integer(page.get(key)) != state[key]:
            raise ValueError('Forum source scope changed')
    if (type(page.get('schema_version')) is not int or page['schema_version'] != 1
            or page.get('source') != 'forum_posts' or page.get('atomic_snapshot') is not False
            or page.get('timestamp_basis') != 'stored_creation'
            or page.get('population') != 'visible_public_nondeleted_posts'
            or type(page.get('has_more')) is not bool):
        raise ValueError('Unknown forum source semantics')
    clock = _integer(page.get('collected_at'),1)
    through, next_id = _integer(page.get('throughid')), _integer(page.get('next_afterid'))
    if through < after_id or (state['throughid'] is not None and through != state['throughid']):
        raise ValueError('Forum upper ID changed')
    rows = page.get('posts')
    if not isinstance(rows, list) or len(rows) > 200 or (not rows and page['has_more']):
        raise ValueError('Invalid bounded forum page')
    previous = after_id
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_KEYS:
            raise ValueError('Unexpected forum post fields')
        identity = _integer(row['id'],1)
        if not previous < identity <= through:
            raise ValueError('Unordered forum posts')
        previous = identity
        _integer(row['author_id'],1)
        parent = row['parent_id']
        if parent is not None:
            _integer(parent,1)
            if parent == identity or parent > through:
                raise ValueError('Invalid forum parent identity')
        created = _integer(row['created'],1)
        modified = _integer(row['modified'])
        if created > clock or modified > clock:
            raise ValueError('Forum post timestamp exceeds observation')
    if next_id != previous or (page['has_more'] and next_id >= through):
        raise ValueError('Forum cursor disagrees with page')
    evidence = {'afterid':after_id, 'throughid':through, 'next_afterid':next_id,
                'has_more':page['has_more'], 'posts':rows}
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if state['last_page'] and after_id == state['last_page']['afterid']:
        if digest != state['last_page']['digest']:
            raise ValueError('Acknowledged forum page changed; start a new run')
        return deepcopy(state)
    if state['done'] or after_id != state['afterid']:
        raise ValueError('Out-of-order forum continuation')
    if state['last_collected_at'] is not None and clock < state['last_collected_at']:
        raise ValueError('Forum source clock moved backwards')
    if len(state['records'])+len(rows) > MAX_POSTS:
        raise ValueError('Forum post storage bound exceeded')
    updated = deepcopy(state)
    updated.update(afterid=next_id, throughid=through, done=not page['has_more'],
        first_collected_at=state['first_collected_at'] or clock, last_collected_at=clock,
        last_page={'afterid':after_id, 'digest':digest})
    updated['records'].extend(deepcopy(rows))
    return updated


def normalized_thread(state):
    if state.get('done') is not True:
        raise ValueError('Forum discussion collection is unfinished')
    return {'id':state['discussionid'], 'forum_id':state['forumid'], 'complete':True,
        'timestamp_basis':'stored_creation', 'posts':[
            {'id':row['id'], 'parent_id':row['parent_id'], 'author_id':row['author_id'],
             'created':row['created'], 'deleted':False, 'private':False} for row in state['records']]}
