"""Private stored-grade page transitions; never an AAC-facing projection.

The caller owns current permissions, population verification and durable storage.
A stable record upper bound does not freeze edits or deletion of existing grades.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

MAX_RECORDS = 10000
ROW_INTS = {'id', 'userid', 'rawscaleid', 'hidden', 'locked', 'locktime',
            'overridden', 'excluded', 'timecreated', 'timemodified'}
ROW_DECIMALS = {'rawgrade', 'rawgrademin', 'rawgrademax', 'finalgrade'}
ITEM_INTS = {'id', 'gradetype', 'scaleid', 'hidden', 'locked', 'locktime',
             'needsupdate', 'iteminstance', 'itemnumber', 'timecreated', 'timemodified'}
ITEM_DECIMALS = {'grademin', 'grademax', 'gradepass', 'multfactor', 'plusfactor'}


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('Invalid gradebook source integer')
    return value


def decimal(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 64 or not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise ValueError('Invalid stored gradebook decimal')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError('Invalid stored gradebook decimal') from None
    if not result.is_finite():
        raise ValueError('Non-finite stored gradebook decimal')
    return result


def initial_cursor(course_id, grade_item_id, group_id=0):
    return {'courseid': integer(course_id, 1), 'gradeitemid': integer(grade_item_id, 1),
            'groupid': integer(group_id), 'afterid': 0, 'throughid': None,
            'item': None, 'item_fingerprint': None, 'records': [], 'done': False, 'last_page': None,
            'first_observed_at': None, 'last_observed_at': None}


def advance_cursor(state, after_id, page):
    """Atomic replacement, with identical last-page replay and no mixed metadata."""
    integer(after_id)
    if not isinstance(page, dict):
        raise ValueError('Invalid gradebook page')
    for key in ('courseid', 'gradeitemid', 'groupid'):
        if integer(page.get(key)) != state[key]:
            raise ValueError('Gradebook page scope changed')
    if (type(page.get('schema_version')) is not int or page['schema_version'] != 1
            or page.get('source') != 'stored_grade_items_and_grade_grades'
            or page.get('atomic_snapshot') is not False or type(page.get('has_more')) is not bool):
        raise ValueError('Unknown gradebook source contract')
    integer(page.get('collected_at'), 1)
    upper = integer(page.get('throughid'))
    next_id = integer(page.get('next_afterid'))
    if upper < after_id or (state['throughid'] is not None and upper != state['throughid']):
        raise ValueError('Gradebook upper ID changed')
    item = page.get('item')
    if not isinstance(item, dict) or set(item) != ITEM_INTS | ITEM_DECIMALS | {'itemtype', 'itemmodule', 'has_calculation'}:
        raise ValueError('Unknown gradebook item fields')
    for key in ITEM_INTS:
        if item[key] is not None:
            integer(item[key])
    if (integer(item['id'], 1) != state['gradeitemid'] or item['gradetype'] not in (0, 1, 2, 3)
            or item['needsupdate'] not in (0, 1) or item['itemtype'] not in ('manual', 'mod')
            or type(item['has_calculation']) is not bool
            or (item['itemmodule'] is not None and
                (not isinstance(item['itemmodule'], str) or not re.fullmatch(r'[a-z][a-z0-9_]*', item['itemmodule'])))):
        raise ValueError('Invalid gradebook item metadata')
    for key in ITEM_DECIMALS:
        decimal(item[key])
    fingerprint = page.get('item_fingerprint')
    if not isinstance(fingerprint, str) or not re.fullmatch(r'[a-f0-9]{64}', fingerprint):
        raise ValueError('Invalid gradebook item fingerprint')
    if state['item'] is not None and (item != state['item'] or fingerprint != state['item_fingerprint']):
        raise ValueError('Gradebook item changed; start a new run')
    rows = page.get('grades')
    if not isinstance(rows, list) or len(rows) > 200 or (not rows and page['has_more']):
        raise ValueError('Invalid bounded gradebook page')
    previous = after_id
    users = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_INTS | ROW_DECIMALS:
            raise ValueError('Unknown gradebook record fields')
        identity = integer(row['id'], 1)
        user = integer(row['userid'], 1)
        if not previous < identity <= upper or user in users:
            raise ValueError('Unordered or duplicate gradebook record')
        users.add(user)
        previous = identity
        for key in ROW_INTS:
            if row[key] is not None:
                integer(row[key])
        for key in ROW_DECIMALS:
            decimal(row[key])
    if next_id != previous or (page['has_more'] and next_id >= upper):
        raise ValueError('Invalid gradebook continuation cursor')
    evidence = dict(afterid=after_id, upper=upper, next_id=next_id, more=page['has_more'],
                    item=item, fingerprint=fingerprint, rows=rows)
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if state['last_page'] and after_id == state['last_page']['afterid']:
        if digest != state['last_page']['digest']:
            raise ValueError('Acknowledged gradebook page changed; start a new run')
        return deepcopy(state)
    if state['done'] or after_id != state['afterid']:
        raise ValueError('Out-of-order gradebook continuation')
    if users.intersection(row['userid'] for row in state['records']):
        raise ValueError('Duplicate gradebook learner across pages')
    if len(state['records']) + len(rows) > MAX_RECORDS:
        raise ValueError('Gradebook record limit exceeded')
    updated = deepcopy(state)
    updated.update(afterid=next_id, throughid=upper, item=deepcopy(item), item_fingerprint=fingerprint,
                   done=not page['has_more'], last_page={'afterid': after_id, 'digest': digest},
                   first_observed_at=state['first_observed_at'] or page['collected_at'],
                   last_observed_at=page['collected_at'])
    updated['records'].extend(deepcopy(rows))
    return updated
