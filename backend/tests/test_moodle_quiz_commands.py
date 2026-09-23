import shlex
from unittest.mock import patch
import pytest
from lamb.moodle.task_contract import parse_task
from lamb.moodle.discovery import IDENTITY, available_recipes, filter_keys
from lamb.moodle.analytics.recovery_tasks import execute
from lamb.moodle.analytics.quiz_run import QuizCheckpoints, start
from tests.test_moodle_completion_tasks import fixture


@pytest.mark.parametrize('verb', ['start', 'run'])
def test_quiz_parser_requires_explicit_policy_and_normalizes_group(verb):
    base = f'moodle analytics {verb} quiz-overview --course 9'
    for tail in ('', ' --quiz 7', ' --attempt-policy all_finished'):
        with pytest.raises(ValueError):
            parse_task(shlex.split(base+tail))
    spec, params = parse_task(shlex.split(base+' --quiz 7 --attempt-policy all_finished'))
    assert params['group_id'] == 0 and params['quiz_id'] == 7
    assert params['attempt_policy'] == 'all_finished'
    _, params = parse_task(shlex.split(base+' --quiz 7 --attempt-policy first_finished --group 3'))
    assert params['group_id'] == 3


@pytest.mark.parametrize('command', [
    'start activity-completion --quiz 7', 'start activity-completion --group 2',
    'run course-access --since 2026-09-01 --attempt-policy all_finished',
    'run quiz-overview --quiz 7 --attempt-policy all_finished --until 2026-09-23',
    'run quiz-overview --quiz 7 --attempt-policy all_finished --since 2026-09-01',
    'run quiz-overview --quiz 7 --attempt-policy all_finished --assignment 1',
])
def test_inapplicable_options_are_rejected(command):
    with pytest.raises(ValueError):
        parse_task(shlex.split('moodle analytics '+command+' --course 9'))


def test_quiz_recipe_requires_both_optional_functions_and_population():
    names = IDENTITY | {'local_lambanalytics_quiz_scope', 'local_lambanalytics_quiz_attempts',
                        'core_enrol_get_enrolled_users'}
    assert 'quiz-overview' in available_recipes(names)
    keys = {'analytics.start', 'analytics.continue', 'analytics.run'}
    assert filter_keys(keys, {'functions': sorted(names)}) == keys
    for function in ('local_lambanalytics_quiz_scope', 'local_lambanalytics_quiz_attempts'):
        assert 'quiz-overview' not in available_recipes(names-{function})


def test_recovery_dispatch_uses_existing_private_namespace(tmp_path):
    results, rt, client = fixture(tmp_path)
    record = start(QuizCheckpoints(results), 9, 7, policy='all_finished')
    with patch('lamb.moodle.analytics.quiz_tasks.execute', return_value={'quiz': True}) as quiz, \
         patch('lamb.moodle.analytics.completion_tasks.execute') as completion:
        assert execute(rt, results, client, 3, 'analytics.continue', {'run_id': record['id'], 'step': 0}) == {'quiz': True}
        quiz.assert_called_once()
        completion.assert_not_called()
    with pytest.raises(PermissionError):
        execute(rt, results, client, 3, 'analytics.continue', {'run_id': '00000000-0000-0000-0000-000000000001', 'step': 0})
