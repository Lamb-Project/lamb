"""Bounded current forum population/inventory used to validate resume context.

Private metadata only. Caller supplies the request-budget/revocation guard.
Inventory is observed, not atomic; changed inventories invalidate a run.
"""
import hashlib
import json
from .events import _students
from .forum_authorization import validate_forum_scope
from .forum_participation import MAX_DISCUSSIONS, _integer
from ..scope import MoodleScope

PAGE_SIZE = 50


def discussion_inventory(client, forum_id, group_id):
    _integer(forum_id,1); _integer(group_id)
    rows, seen = [], set()
    for page in range(MAX_DISCUSSIONS//PAGE_SIZE+1):
        data = client.call('mod_forum_get_forum_discussions', forumid=forum_id,
            groupid=group_id, page=page, perpage=PAGE_SIZE, sortorder=4)
        if not isinstance(data,dict) or data.get('warnings') != []:
            raise ValueError('Forum inventory warnings or unknown coverage')
        source = data.get('discussions')
        if not isinstance(source,list) or len(source)>PAGE_SIZE or len(rows)+len(source)>MAX_DISCUSSIONS:
            raise ValueError('Forum discussion inventory exceeds bound')
        for row in source:
            if not isinstance(row,dict):
                raise ValueError('Invalid forum inventory row')
            # Standard API id is the ROOT POST id, not the discussion id.
            identity = _integer(row.get('discussion'),1)
            root = _integer(row.get('id'),1)
            group = _integer(row.get('groupid'),-1)
            if identity in seen or (group_id and group not in (-1,0,group_id)):
                raise ValueError('Unstable or out-of-group forum inventory')
            if 'forum' in row and (type(row['forum']) is not int or row['forum'] != forum_id):
                raise ValueError('Foreign forum discussion')
            seen.add(identity)
            rows.append({'discussion_id':identity,'root_post_id':root,'group_id':group,
                'timestart':_integer(row.get('timestart')), 'timeend':_integer(row.get('timeend'))})
        if len(source)<PAGE_SIZE:
            return sorted(rows,key=lambda row:row['discussion_id'])
    raise ValueError('Forum discussion inventory not exhausted')


def forum_context(client, owner_id, scope):
    if not isinstance(scope,dict) or set(scope)!={'course_id','forum_id','group_id'}:
        raise ValueError('Invalid forum collection scope')
    authority = dict(scope,discussion_id=0)
    validate_forum_scope(client,authority)
    MoodleScope(client,owner_id).require_teacher(scope['course_id'])
    students,population = _students(client,scope['course_id'],scope['group_id'])
    if not population['population_exhausted'] or population['role_unknown']:
        raise ValueError('Complete known student population required for forum analytics')
    inventory = discussion_inventory(client,scope['forum_id'],scope['group_id'])
    validate_forum_scope(client,authority)
    evidence = {'students':sorted(students),'population':population,'discussions':inventory}
    return dict(evidence,fingerprint=hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest())
