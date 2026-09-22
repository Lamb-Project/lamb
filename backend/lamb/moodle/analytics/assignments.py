"""Loss-aware assignment aggregates. No learner responses are retained."""
from datetime import datetime, timezone

from ..forum_activity import TaskCancelled, TaskLimit, preview
from ..scope import MoodleScope

MAX_ASSIGNMENTS = 100
COUNT_FIELDS = ('participantcount', 'submissiondraftscount',
                'submissionssubmittedcount', 'submissionsneedgradingcount')


def assignment_inventory(client, owner_id, course_id):
    course_id = MoodleScope(client, owner_id).require_teacher(course_id)
    response = client.call('mod_assign_get_assignments', courseids=[course_id])
    courses = response.get('courses', [])
    if response.get('warnings') or len(courses) != 1 or courses[0].get('id') != course_id:
        raise ValueError('Assignment inventory is incomplete')
    assignments = courses[0].get('assignments')
    if not isinstance(assignments, list) or len({a['id'] for a in assignments}) != len(assignments):
        raise ValueError('Invalid assignment inventory')
    return course_id, preview(courses[0]['fullname'], 160)[0], assignments


def grading_queue(client, owner_id, course_id, *, progress=None):
    """Moodle needs-grading counts, not a claim about feedback release/turnaround.

    Moodle's own aggregate joins latest submitted attempts to attempt-specific
    grades and compares modification times. Team submissions return a synthetic
    zero upstream, so those are explicitly unavailable here instead.
    """
    started = datetime.now(timezone.utc).isoformat()
    course_id, name, assignments = assignment_inventory(client, owner_id, course_id)
    rows = []
    for i, assignment in enumerate(assignments[:MAX_ASSIGNMENTS]):
        client.checkpoint()
        row = {'assignment_id': assignment['id'], 'name': preview(assignment['name'], 160)[0],
               'status': 'unavailable', 'reason': None, 'participants': None,
               'submitted': None, 'drafts': None, 'needs_grading': None,
               'marking_workflow': bool(assignment.get('markingworkflow')),
               'grade_released': None}
        if assignment.get('teamsubmission', 1):
            row['reason'] = 'team_submission_count_not_supported'
        else:
            try:
                result = client.call('mod_assign_get_submission_status', assignid=assignment['id'], userid=owner_id, groupid=0)
                summary = result.get('gradingsummary', {})
                if result.get('warnings') or not summary:
                    raise ValueError('grading_summary_unavailable')
                if not summary.get('submissionsenabled'):
                    raise ValueError('online_submissions_disabled')
                values = [summary.get(key) for key in COUNT_FIELDS]
                if any(type(value) is not int or value < 0 for value in values):
                    raise ValueError('grading_counts_missing_or_invalid')
                participants, drafts, submitted, pending = values
                if submitted > participants or drafts > participants or pending > submitted:
                    raise ValueError('grading_counts_inconsistent')
                row.update(status='ok', participants=participants, submitted=submitted,
                           drafts=drafts, needs_grading=pending)
            except (PermissionError, TaskCancelled, TaskLimit):
                raise
            except ValueError as exc:
                row['reason'] = str(exc)
            except Exception:
                row['reason'] = 'grading_summary_unavailable'
        rows.append(row)
        if progress: progress(i + 1, min(len(assignments), MAX_ASSIGNMENTS))
    client.checkpoint()
    supported = [row for row in rows if row['status'] == 'ok']
    return {'schema_version': 1, 'recipe': {'id': 'grading-queue', 'version': 1},
            'course_id': course_id, 'course_name': name, 'as_of': started, 'timezone': 'UTC',
            'rows': rows, 'metrics': {
                'needs_grading': sum(row['needs_grading'] for row in supported) if supported or not assignments else None,
                'population': 'supported_assignments_only'},
            'coverage': {'assignments_found': len(assignments), 'assignments_read': len(supported),
                         'omitted_by_limit': max(0, len(assignments) - MAX_ASSIGNMENTS),
                         'complete': len(supported) == len(assignments)},
            'source': 'mod_assign_get_submission_status.gradingsummary, groupid=0',
            'limitations': ['Counts use Moodle latest-submitted-attempt needs-grading semantics.',
                            'Needs grading is not the same as feedback awaiting release.',
                            'Workflow release state and first-feedback turnaround were not collected.',
                            'Team and offline assignments are excluded, not counted as zero.',
                            'Collection is bounded and is not an atomic course snapshot.']}
