"""Private current student targeting context for one assessment item."""
import hashlib
import json
from .client import GRADEBOOK_POPULATION_FUNCTION
from .events import _students
from .gradebook_authorization import validate_gradebook_scope
from ..scope import MoodleScope

BASES = {'active_candidate_population_manual_item', 'module_and_section_availability_user_list'}


def target_batch(client, scope, candidates):
    params = {'courseid': scope['course_id'], 'gradeitemid': scope['grade_item_id'], 'groupid': scope['group_id']}
    data = client.call(GRADEBOOK_POPULATION_FUNCTION, **params, userids=candidates)
    if (not isinstance(data, dict) or any(type(data.get(k)) is not int or data[k] != v for k,v in params.items())
            or type(data.get('schema_version')) is not int or data['schema_version'] != 1
            or data.get('atomic_snapshot') is not False or data.get('population_basis') not in BASES
            or type(data.get('collected_at')) is not int or data['collected_at']<1):
        raise ValueError('Invalid assessment population source contract')
    lists = []
    for key in ('included_userids', 'excluded_userids'):
        ids = data.get(key)
        if (not isinstance(ids, list) or len(ids)>200 or any(type(v) is not int or v<1 for v in ids)
                or ids != sorted(set(ids))):
            raise ValueError('Invalid assessment population partition')
        lists.append(set(ids))
    if lists[0] & lists[1] or lists[0] | lists[1] != set(candidates):
        raise ValueError('Assessment population partition does not match candidates')
    return data


def gradebook_context(client, owner_id, scope):
    validate_gradebook_scope(client, scope)
    MoodleScope(client, owner_id).require_teacher(scope['course_id'])
    students, population = _students(client, scope['course_id'], scope['group_id'])
    if not population['population_exhausted'] or population['role_unknown']:
        raise ValueError('Complete known student population required for assessment comparison')
    candidates = sorted(students)
    included, excluded, bases, clocks = [], [], set(), []
    # Empty population still obtains item interpretation and source authority.
    for offset in range(0, max(1,len(candidates)), 200):
        client.checkpoint()
        batch = target_batch(client, scope, candidates[offset:offset+200])
        included.extend(batch['included_userids'])
        excluded.extend(batch['excluded_userids'])
        bases.add(batch['population_basis'])
        clocks.append(batch['collected_at'])
    if len(bases) != 1:
        raise ValueError('Assessment population basis changed during collection')
    validate_gradebook_scope(client, scope)
    evidence = {'candidates': candidates, 'students': sorted(included), 'excluded_students': sorted(excluded),
                'population': population, 'population_basis': bases.pop(),
                'candidate_basis': 'current_active_enrolments_with_role_shortname_student'}
    return dict(evidence, fingerprint=hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest(),
                first_observed_at=min(clocks), last_observed_at=max(clocks), atomic_snapshot=False)
