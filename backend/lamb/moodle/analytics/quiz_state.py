"""Private, atomic quiz-page transitions for a resumable collector.

Caller owns permission revalidation, population verification and durable writes.
These records contain learner join IDs and must never be returned to AAC.
"""
from copy import deepcopy
import hashlib
import json
import math

MAX_ATTEMPTS = 10000
ROW_KEYS = {'id', 'quiz', 'userid', 'attempt', 'preview', 'state', 'sumgrades',
            'timestart', 'timefinish', 'timemodified'}


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('Invalid quiz source integer')
    return value


def initial_cursor(course_id, quiz_id, group_id=0):
    return {'courseid': _integer(course_id, 1), 'quizid': _integer(quiz_id, 1),
            'groupid': _integer(group_id), 'afterid': 0, 'throughid': None,
            'metadata': None, 'records': [], 'done': False, 'last_page': None}


def advance_cursor(state, after_id, page):
    """Return a replacement without mutating state, including on invalid input.

    Identical replay of the last acknowledged page is a no-op. A changed replay
    fails rather than combining new marks with old evidence. The source remains
    non-atomic even with a fixed upper ID; older acknowledged pages may change.
    """
    _integer(after_id)
    if not isinstance(page, dict):
        raise ValueError('Invalid quiz page')
    for key in ('courseid', 'quizid', 'groupid'):
        if _integer(page.get(key)) != state[key]:
            raise ValueError('Quiz page scope changed')
    if (type(page.get('schema_version')) is not int or page['schema_version'] != 1
            or page.get('source') != 'quiz_attempts' or page.get('atomic_snapshot') is not False
            or type(page.get('has_more')) is not bool):
        raise ValueError('Unknown quiz source contract')
    _integer(page.get('collected_at'), 1)
    through = _integer(page.get('throughid'))
    next_id = _integer(page.get('next_afterid'))
    if through < after_id or (state['throughid'] is not None and through != state['throughid']):
        raise ValueError('Quiz upper ID changed')
    metadata = {key: page.get(key) for key in ('raw_maximum', 'grade_maximum', 'grading_method')}
    for key in ('raw_maximum', 'grade_maximum'):
        value = metadata[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Quiz maximum is unavailable')
    if _integer(metadata['grading_method'], 1) not in (1, 2, 3, 4):
        raise ValueError('Unknown quiz grading method')
    if state['metadata'] is not None and metadata != state['metadata']:
        raise ValueError('Quiz grading metadata changed')
    rows = page.get('attempts')
    if not isinstance(rows, list) or len(rows) > 200 or (not rows and page['has_more']):
        raise ValueError('Invalid bounded quiz page')
    previous = after_id
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_KEYS:
            raise ValueError('Unknown quiz attempt fields')
        identity = _integer(row['id'], 1)
        if not previous < identity <= through or _integer(row['quiz'], 1) != state['quizid']:
            raise ValueError('Unordered or foreign quiz attempt')
        previous = identity
        _integer(row['userid'], 1)
        _integer(row['attempt'], 1)
        if type(row['preview']) is not bool or row['state'] not in {'inprogress', 'overdue', 'finished', 'abandoned'}:
            raise ValueError('Unknown quiz attempt state')
        for key in ('timestart', 'timefinish', 'timemodified'):
            _integer(row[key])
        mark = row['sumgrades']
        if mark is not None and (type(mark) not in (int, float) or not math.isfinite(mark)
                                 or not 0 <= mark <= metadata['raw_maximum']):
            raise ValueError('Invalid raw quiz mark')
    if next_id != previous:
        raise ValueError('Quiz next cursor does not match evidence')
    if page['has_more'] and next_id >= through:
        raise ValueError('Quiz page claims impossible continuation')
    evidence = dict(afterid=after_id, throughid=through, next_afterid=next_id,
                    has_more=page['has_more'], metadata=metadata, rows=rows)
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if state['last_page'] and after_id == state['last_page']['afterid']:
        if digest != state['last_page']['digest']:
            raise ValueError('Acknowledged quiz page changed; start a new run')
        return deepcopy(state)
    if state['done'] or after_id != state['afterid']:
        raise ValueError('Out-of-order quiz continuation')
    if len(state['records']) + len(rows) > MAX_ATTEMPTS:
        raise ValueError('Quiz attempt limit exceeded')
    updated = deepcopy(state)
    updated.update(afterid=next_id, throughid=through, metadata=metadata,
                   done=not page['has_more'], last_page={'afterid': after_id, 'digest': digest})
    updated['records'].extend(deepcopy(rows))
    return updated
