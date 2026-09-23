from copy import deepcopy
from lamb.moodle.analytics.forum_evidence import with_forum_semantics


def test_old_saved_rows_counts_dates_remain_immutable():
    for recipe in ('forum-participation','forum-discussions'):
        original={'recipe':{'id':recipe},'as_of':'2026-09-23T11:59:19Z',
                  'rows':[{'id':4,'posts':4}],
                  'coverage':{'exclusions':{'outside_population_window_posts':5}}}
        before=deepcopy(original)
        result=with_forum_semantics(original)
        assert original==before
        assert all(result[key]==value for key,value in original.items())
        assert 'INSIDE the requested date window' in result['forum_exclusion_basis']
        assert ('ONLY current students' if recipe=='forum-participation' else 'not a last-activity timestamp') in result['forum_reply_basis']
        result['rows'][0]['posts']=99
        assert original==before


def test_other_snapshots_are_untouched():
    for value in ({},{'recipe':{'id':'unknown'}}):
        assert with_forum_semantics(value) is value


def test_bounded_preview_keeps_forum_semantics():
    from lamb.aac.result_store import preview
    source={f'noise_{i}':'irrelevant' for i in range(30)}
    source.update(recipe={'id':'forum-participation'},as_of_local='2026-09-23T13:59:19+02:00')
    result=preview(with_forum_semantics(source))
    assert 'INSIDE the requested date window' in result['forum_exclusion_basis']
    assert 'ONLY current students' in result['forum_reply_basis']
    assert result['as_of_local']==source['as_of_local']


def test_local_window_dates_do_not_shift_to_previous_utc_day():
    value={'recipe':{'id':'forum-participation'},'timezone':'Europe/Madrid',
           'metrics':{'window':{'since':1788213600,'until':1790114400}}}
    result=with_forum_semantics(value)
    assert result['window_start_local']=='2026-09-01T00:00:00+02:00'
    assert result['window_end_local']=='2026-09-23T00:00:00+02:00'
