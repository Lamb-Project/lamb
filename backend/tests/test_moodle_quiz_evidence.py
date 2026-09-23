from copy import deepcopy
import pytest
from lamb.moodle.analytics.quiz_evidence import (
    BEST_LIMITATION, BEST_WARNINGS, SCORE_BASES, with_quiz_semantics,
)
from lamb.aac.result_store import preview


@pytest.mark.parametrize('policy', SCORE_BASES)
@pytest.mark.parametrize('warning', BEST_WARNINGS)
def test_saved_semantics_preserve_evidence_and_scope_warning(policy, warning):
    saved = {'recipe': {'id':'quiz-overview'}, 'caption':'Policy. '+warning+' End.',
        'as_of':'2026-09-23T10:20:01+00:00', 'rows':[{'value':3}],
        'metrics': {'attempt_policy':policy, 'selected_attempts':4,
                    'limitations':[BEST_LIMITATION, 'Other caveat.']},
        'limitations':[BEST_LIMITATION, 'Current population.']}
    original = deepcopy(saved)
    result = with_quiz_semantics(saved)
    assert saved == original
    assert result['rows'] == saved['rows'] and result['as_of'] == saved['as_of']
    assert result['metrics']['selected_attempts'] == 4
    assert result['attempt_policy'] == policy and result['score_basis'] == SCORE_BASES[policy]
    assert 'not student exemptions' in result['preview_basis']
    assert (warning in result['caption']) == (policy == 'best_scored_finished')
    for container in (result, result['metrics']):
        assert (BEST_LIMITATION in container['limitations']) == (policy == 'best_scored_finished')
    assert with_quiz_semantics(result) == result


def test_nonquiz_and_unknown_policy_are_not_reinterpreted():
    for value in ({'recipe':'assignment-submissions-v1'},
                  {'recipe':{'id':'quiz-overview'}, 'metrics':{'attempt_policy':'unknown'}}):
        assert with_quiz_semantics(value) is value


def test_bounded_preview_keeps_policy_and_meaning():
    saved = {str(i):i for i in range(30)}
    saved.update(recipe={'id':'quiz-overview'}, metrics={'attempt_policy':'all_finished'},
                 snapshot_date_label='2026-09-23T12:20:01+02:00 (Europe/Madrid)')
    result = preview(with_quiz_semantics(saved))
    assert result['attempt_policy'] == 'all_finished'
    assert 'ALL selected finished attempts' in result['score_basis']
    assert 'not student exemptions' in result['preview_basis']
    assert result['snapshot_date_label'] == saved['snapshot_date_label']
