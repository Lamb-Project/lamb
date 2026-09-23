"""Aggregate explicit assessment populations over validated stored grade evidence.

No student identifiers leave this reducer. Eligibility must be established by
the caller for each item, not inferred from which learners have grade records.
"""
from decimal import Decimal
from .gradebook_state import decimal, integer
from .grades import _percentile


def summarize_assessment(cursor, eligible_students):
    if cursor.get('done') is not True or cursor.get('item') is None:
        raise ValueError('Complete gradebook evidence required')
    if not isinstance(eligible_students, (list, tuple, set)):
        raise ValueError('Explicit per-assessment population required')
    students = [integer(value, 1) for value in eligible_students]
    if len(students) != len(set(students)):
        raise ValueError('Duplicate assessment population member')
    students = set(students)
    item = cursor['item']
    low, high, threshold = (decimal(item[key]) for key in ('grademin', 'grademax', 'gradepass'))
    reasons = []
    if item['gradetype'] != 1:
        reasons.append('non_numeric_grade_type')
    if low is None or high is None or high <= low:
        reasons.append('invalid_numeric_range')
    if item['needsupdate'] != 0:
        reasons.append('stale_final_grades')
    records = {}
    for row in cursor['records']:
        user = integer(row['userid'], 1)
        if user in records:
            raise ValueError('Duplicate gradebook learner')
        records[user] = row
    counts = dict(population_n=len(students), no_record_n=0, null_final_n=0,
                  excluded_n=0, graded_n=0, overridden_n=0, hidden_flag_n=0,
                  outside_population_records_n=len(set(records)-students))
    values, passed = [], 0
    pass_configured = (not reasons and threshold is not None and threshold != low
                       and low < threshold <= high)
    for user in students:
        row = records.get(user)
        if row is None:
            counts['no_record_n'] += 1
            continue
        # Unknown flags must not silently become false eligibility or release claims.
        for flag in ('excluded', 'overridden', 'hidden'):
            integer(row[flag])
        counts['overridden_n'] += int(row['overridden'] != 0)
        counts['hidden_flag_n'] += int(row['hidden'] != 0)
        if row['excluded'] != 0:
            counts['excluded_n'] += 1
            continue
        final = decimal(row['finalgrade'])
        if final is None:
            counts['null_final_n'] += 1
            continue
        counts['graded_n'] += 1
        if reasons:
            continue
        if not low <= final <= high:
            raise ValueError('Final grade outside declared assessment range')
        values.append((final-low)*100/(high-low))
        passed += int(pass_configured and final >= threshold)
    values.sort()
    counts['missing_n'] = counts['no_record_n'] + counts['null_final_n']
    counts['nonexcluded_population_n'] = counts['population_n']-counts['excluded_n']
    assert counts['graded_n']+counts['missing_n'] == counts['nonexcluded_population_n']
    quantiles = {key: float(_percentile(values, fraction)) if values else None
                 for key, fraction in [('q1_pct', Decimal('.25')), ('median_pct', Decimal('.5')),
                                       ('q3_pct', Decimal('.75'))]}
    metrics = {**counts, **quantiles,
        'valid_n': len(values), 'min_pct': float(values[0]) if values else None,
        'max_pct': float(values[-1]) if values else None,
        'iqr_pct': quantiles['q3_pct']-quantiles['q1_pct'] if values else None,
        'pass_n': passed if pass_configured else None,
        'pass_denominator_n': len(values) if pass_configured else None,
        'pass_rate_pct': 100*passed/len(values) if pass_configured and values else None,
        'missing_grade_rate_pct': 100*counts['missing_n']/counts['nonexcluded_population_n']
            if counts['nonexcluded_population_n'] else None,
        'submission_rate_pct': None}
    return {'grade_item_id': cursor['gradeitemid'], 'course_id': cursor['courseid'],
        'group_id': cursor['groupid'], 'metrics': metrics,
        'comparison_status': 'unavailable' if reasons else 'available', 'unavailable_reasons': reasons,
        'grade_basis': 'stored_finalgrade', 'normalization': '(finalgrade-grademin)/(grademax-grademin)*100',
        'grade_min': item['grademin'], 'grade_max': item['grademax'], 'grade_pass': item['gradepass'],
        'pass_basis': 'configured_threshold_among_valid_nonexcluded_grades' if pass_configured else 'unavailable',
        'first_observed_at': cursor['first_observed_at'], 'last_observed_at': cursor['last_observed_at'],
        'atomic_snapshot': False, 'grade_release_status': 'not_determined',
        'limitations': [
            'Missing grade is not missing submission; no submission rate was collected.',
            'Excluded records are omitted from score and missing-grade denominators.',
            'Override values use stored final grades, not raw assignment marks.',
            'Nonzero hidden flags include scheduled timestamps and do not establish current release status.',
            'Quartiles use linear interpolation at (N-1)*p; extrema are not Tukey whiskers.',
            'Different assessments may measure different skills and grading standards; scores do not establish difficulty or learning.',
            'Per-item populations can differ; comparison is descriptive, not paired or causal.',
            'A fixed upper ID does not freeze grade edits, deletions or eligibility changes.']}


def compare_assessments(evidence):
    """Each entry is (completed private cursor, independently established population)."""
    if not isinstance(evidence, list) or not 2 <= len(evidence) <= 20:
        raise ValueError('Select two to twenty assessments explicitly')
    rows = [summarize_assessment(cursor, students) for cursor, students in evidence]
    if len({row['grade_item_id'] for row in rows}) != len(rows):
        raise ValueError('Assessment selection contains duplicates')
    if len({(row['course_id'], row['group_id']) for row in rows}) != 1:
        raise ValueError('Assessment selection must share course and group scope')
    return {'rows': rows, 'comparison_basis': 'descriptive_per_item_populations',
            'difficulty_ranking': None, 'submission_rate_collected': False}
