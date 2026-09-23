from copy import deepcopy
from lamb.moodle.analytics.gradebook_evidence import with_gradebook_semantics
from lamb.aac.result_store import preview


def test_gradebook_semantics_preserve_saved_counts_and_reasons():
    saved={'recipe':{'id':'assessment-comparison'},'rows':[
        {'metrics':{'graded_n':3,'valid_n':0,'excluded_n':1,'null_final_n':1},
         'unavailable_reasons':['stale_final_grades']}]}
    before=deepcopy(saved)
    result=with_gradebook_semantics(saved)
    assert saved==before and result['rows']==saved['rows']
    assert 'NOT submissions' in result['grade_count_basis']
    assert 'do not subtract' in result['grade_count_basis']
    assert 'percentage points' in result['grade_score_basis']
    assert with_gradebook_semantics(result)==result


def test_other_recipes_unchanged():
    for saved in ({},{'recipe':None},{'recipe':{'id':'assignment-grades'}}):
        assert with_gradebook_semantics(saved) is saved


def test_bounded_preview_retains_grade_interpretation():
    saved={str(i):i for i in range(30)}
    saved.update(recipe={'id':'assessment-comparison'},title='Comparison',timezone='UTC')
    enriched=with_gradebook_semantics(saved)
    result=preview(enriched)
    assert 'valid_n=0' in result['grade_count_basis']
    assert 'percentage points' in result['grade_score_basis']
    for key in ('grade_count_basis','grade_score_basis'):
        assert result[key]==enriched[key]
