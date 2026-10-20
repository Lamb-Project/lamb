"""Teacher review material and stale-submission protection for grade writes."""
import math
from moodle_cli.services.assign import AssignService
from .scoped_reads import execute_scoped_read


def grade_review(client, params, *, owner_moodle_id, context):
    if not params.get('rationale', '').strip() or not math.isfinite(params['grade_value']):
        raise ValueError('A finite proposed grade and a non-empty rationale are required')
    status = execute_scoped_read(client, 'assign.status',
        {'assign_id': params['assignment_id'], 'user_id': params['user_id']},
        owner_moodle_id=owner_moodle_id, context=context)
    attempt = status.get('lastattempt') or {}
    submission = attempt.get('submission') or attempt.get('teamsubmission')
    if not submission or submission.get('status') != 'submitted':
        raise ValueError('Review a submitted attempt before proposing a saved grade')
    return {'course_id': context['course_id'], 'proposal': dict(params),
            'submission': submission,
            'review_instruction': 'Review the submission, including any attached files, and the proposed grade, feedback and rationale before approving. The proposal is not a judgment of the learner.'}


def save_grade(client, params):
    AssignService(client).grade_submission(params['assignment_id'], params['user_id'],
        params['grade_value'], params['feedback'], params['workflow_state'])
    return {'saved': True, 'assignment_id': params['assignment_id'],
            'user_id': params['user_id'], 'grade': params['grade_value'],
            'feedback': params['feedback'], 'rationale': params['rationale']}
