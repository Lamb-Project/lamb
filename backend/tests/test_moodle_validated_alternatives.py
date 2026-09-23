"""Regression for Heavy's 91-day prose suggestions; deterministic, no inference."""
from datetime import date
import pytest
from lamb.moodle.analytics.window import plan_window, MAX_SOURCE_SECONDS


def test_summer_alternatives_preserve_requested_range_and_both_exact_anchors():
    result=plan_window('2026-06-01',through='2026-08-31',tz='Europe/Madrid')
    assert (result['since'],result['through'],result['calendar_days'],result['collection_supported'])==('2026-06-01','2026-08-31',92,False)
    alternatives=result['validated_alternatives']
    assert [(a['since'],a['through'],a['preserves']) for a in alternatives]==[
        ('2026-06-01','2026-08-29','start'),('2026-06-03','2026-08-31','end')]
    assert all(a['calendar_days']==90 and a['requires_user_selection'] for a in alternatives)


@pytest.mark.parametrize('start,end,tz',[
    ('2026-06-01','2026-08-31','Europe/Madrid'),
    ('2026-06-02','2026-08-31','Europe/Madrid'),
    ('2026-06-01','2026-08-30','Europe/Madrid'),
    ('2026-10-01','2026-12-29','Europe/Madrid'),
    ('2026-03-01','2026-06-30','Europe/Madrid'),
    ('2024-01-01','2024-06-30','UTC'),
    ('2011-10-02','2012-02-01','Pacific/Apia'),
    ('0001-01-01','0001-06-30','UTC'),
    ('9999-06-01','9999-12-30','UTC')])
def test_every_alternative_is_subset_with_inclusive_count_and_same_transport_validation(start,end,tz):
    result=plan_window(start,through=end,tz=tz)
    assert not result['collection_supported'] and len(result['validated_alternatives'])==2
    for proposal in result['validated_alternatives']:
        assert start<=proposal['since']<=proposal['through']<=end
        assert proposal['calendar_days']==(date.fromisoformat(proposal['through'])-date.fromisoformat(proposal['since'])).days+1
        assert proposal['calendar_days']<=90 and proposal['elapsed_seconds']<=MAX_SOURCE_SECONDS
        checked=plan_window(proposal['since'],through=proposal['through'],tz=tz)
        assert checked['collection_supported'] and checked['validated_alternatives']==[]
        assert proposal['source_availability']=='not_checked' and proposal['historical_coverage']=='unknown'


def test_autumn_90_local_days_need_89_day_alternatives_due_to_transport_limit():
    result=plan_window('2026-10-01',through='2026-12-29',tz='Europe/Madrid')
    assert result['calendar_days']==90 and result['elapsed_seconds']>MAX_SOURCE_SECONDS
    assert all(a['calendar_days']==89 for a in result['validated_alternatives'])


def test_valid_requested_interval_has_no_unasked_replacement():
    result=plan_window('2026-08-01',through='2026-08-31',tz='Europe/Madrid')
    assert result['collection_supported'] and result['validated_alternatives']==[]
    assert 'This planner call' in result['notice']
