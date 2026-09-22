from datetime import datetime
import json
import pytest
from lamb.moodle.analytics.view_time import ViewTimeBuckets


def stamp(value):return int(datetime.fromisoformat(value).timestamp())


def test_local_days_exclusive_end_distinct_viewers_and_event_types():
    start=stamp('2026-09-20T00:00:00+02:00');end=stamp('2026-09-22T00:00:00+02:00')
    buckets=ViewTimeBuckets([9123456,9123457],since=start,until=end,timezone='Europe/Madrid')
    for identity,student,when,kind in [(1,9123456,start,'course_view'),(2,9123456,start+1,'resource_view'),
        (3,9123457,end-1,'chapter_view'),(4,9999999,end-1,'course_view')]:
        buckets.add(event_id=identity,student_id=student,timestamp=when,kind=kind)
    result=buckets.snapshot(collection_complete=True)
    assert [row['date'] for row in result['daily']]==['2026-09-20','2026-09-21']
    assert [row['recorded_views'] for row in result['daily']]==[2,1]
    assert result['totals']=={'unique_student_viewers':2,'recorded_views':3,'course_view':1,'resource_view':1,'chapter_view':1}
    assert result['coverage']['excluded_actor_events']==1 and not result['coverage']['history_complete']
    assert '912345' not in json.dumps(result) and '9999999' not in json.dumps(result)
    with pytest.raises(ValueError):buckets.add(event_id=5,student_id=9123456,timestamp=end,kind='course_view')


def test_fall_clock_change_keeps_both_events_in_same_local_heatmap_cell():
    buckets=ViewTimeBuckets([1],since=stamp('2026-10-25T00:00:00+02:00'),
        until=stamp('2026-10-26T00:00:00+01:00'),timezone='Europe/Madrid')
    for identity,instant in enumerate(('2026-10-25T02:30:00+02:00','2026-10-25T02:30:00+01:00'),1):
        buckets.add(event_id=identity,student_id=1,timestamp=stamp(instant),kind='course_view')
    result=buckets.snapshot(collection_complete=True)
    cell=next(row for row in result['weekday_hour'] if row['weekday']==6 and row['hour']==2)
    assert cell['recorded_views']==2 and cell['unique_student_viewers']==1
    assert len(result['daily'])==1


def test_empty_days_and_partial_coverage_are_not_hidden():
    buckets=ViewTimeBuckets([],since=100,until=100+3*86400,timezone='UTC')
    result=buckets.snapshot(collection_complete=False)
    assert len(result['daily'])==4 and all(row['recorded_views']==0 for row in result['daily'])
    assert not result['coverage']['collection_complete']
    with pytest.raises(ValueError):buckets.snapshot(collection_complete=1)


@pytest.mark.parametrize('change',[{'event_id':True},{'student_id':False},{'timestamp':-1},{'kind':'forum_post'}])
def test_invalid_events_do_not_mutate_aggregates(change):
    buckets=ViewTimeBuckets([1],since=100,until=200,timezone='UTC')
    before=buckets.snapshot(collection_complete=True)
    values=dict(event_id=1,student_id=1,timestamp=150,kind='course_view');values.update(change)
    with pytest.raises(ValueError):buckets.add(**values)
    assert buckets.snapshot(collection_complete=True)==before


def test_duplicate_event_rejected_without_double_counting():
    buckets=ViewTimeBuckets([1],since=100,until=200,timezone='UTC')
    event=dict(event_id=1,student_id=1,timestamp=150,kind='course_view')
    buckets.add(**event)
    with pytest.raises(ValueError):buckets.add(**event)
    assert buckets.snapshot(collection_complete=True)['totals']['recorded_views']==1


def test_weekly_distinct_viewers_are_not_sum_of_daily_counts():
    start=stamp('2026-09-21T00:00:00+00:00')
    buckets=ViewTimeBuckets([1],since=start,until=start+3*86400,timezone='UTC')
    for identity,when in enumerate((start,start+86400),1):
        buckets.add(event_id=identity,student_id=1,timestamp=when,kind='course_view')
    result=buckets.snapshot(collection_complete=True)
    assert sum(row['unique_student_viewers'] for row in result['daily'])==2
    assert result['weekly'][0]['week_start']=='2026-09-21'
    assert result['weekly'][0]['unique_student_viewers']==1
    assert result['weekly'][0]['recorded_views']==2
