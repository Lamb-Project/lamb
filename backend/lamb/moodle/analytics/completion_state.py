"""Private completion cursor transitions, never a learner-facing projection.

The owner must durably replace the returned state before advancing the remote
cursor. This module does not provide storage, authorization or continuation.
"""
from copy import deepcopy

STATES = ('incomplete', 'complete', 'complete_pass', 'complete_fail')
MAX_COMPLETION_MODULES = 100


def initial_cursor(students, rows):
    ids = list(students)
    if any(type(identity) is not int or identity < 1 for identity in ids) or len(ids) != len(set(ids)):
        raise ValueError('Invalid completion student inventory')
    ids.sort()
    modules = [row['cmid'] for row in rows]
    if len(modules) > MAX_COMPLETION_MODULES or len(set(modules)) != len(modules):
        raise ValueError('Invalid completion module inventory')
    copied = deepcopy(rows)
    for row in copied:
        row['overall_by_state'] = {key:{'true':0,'false':0,'unknown':0} for key in STATES}
    return {'students': ids, 'next_student': 0, 'rows': copied}


def advance_cursor(state, student, response):
    """Return an atomic replacement; replay of an acknowledged learner is a no-op.

    A failed checkpoint leaves the old cursor authoritative, so replaying that
    request applies once. After a successful checkpoint the same request cannot
    add its counts again. Permissions must be rechecked by the caller even when
    a replay needs no remote data.
    """
    ids = state['students']
    index = state['next_student']
    if type(index) is not int or not 0 <= index <= len(ids):
        raise ValueError('Invalid completion cursor')
    if type(student) is not int or student not in ids:
        raise ValueError('Out-of-scope completion student')
    position = ids.index(student)
    if position < index:
        return deepcopy(state)
    if position != index:
        raise ValueError('Out-of-order completion response')
    if not isinstance(response, dict) or response.get('warnings') or not isinstance(response.get('statuses'), list):
        raise ValueError('Completion source is incomplete')
    if len(response['statuses']) > MAX_COMPLETION_MODULES:
        raise ValueError('Completion source exceeds module limit')
    updated = deepcopy(state)
    inventory = {row['cmid']: row for row in updated['rows']}
    records = {}
    for record in response['statuses']:
        if not isinstance(record, dict):
            raise ValueError('Invalid completion status')
        identity = record.get('cmid')
        if type(identity) is not int or identity < 1 or identity in records:
            raise ValueError('Invalid or duplicate completion status')
        if identity not in inventory:
            raise ValueError('Completion inventory changed or source returned an out-of-scope activity')
        records[identity] = record
    for identity, row in inventory.items():
        record = records.get(identity)
        if record is None:
            row['unknown'] += 1
            continue
        tracking = record.get('tracking')
        if type(tracking) is not int or tracking != row['tracking']:
            raise ValueError('Completion tracking changed during collection')
        if record.get('istrackeduser') is False:
            row['untracked'] += 1
            continue
        value = record.get('state')
        if record.get('istrackeduser') is not True or type(value) is not int or value not in range(4):
            row['unknown'] += 1
            continue
        row[STATES[value]] += 1
        overall = record.get('isoverallcomplete')
        # Older checkpoints lack this cross-tab. Never initialize one midway
        # and misrepresent a partial breakdown as covering the whole run.
        if 'overall_by_state' in row:
            bucket = ('true' if overall else 'false') if type(overall) is bool else 'unknown'
            row['overall_by_state'][STATES[value]][bucket] += 1
        if type(overall) is bool:
            row['overall_complete'] += int(overall)
        else:
            row['overall_unknown'] += 1
        override = record.get('overrideby')
        if 'overrideby' not in record or (override is not None and (type(override) is not int or override < 0)):
            row['override_unknown'] += 1
        elif override:
            row['overridden'] += 1
    updated['next_student'] += 1
    return updated
