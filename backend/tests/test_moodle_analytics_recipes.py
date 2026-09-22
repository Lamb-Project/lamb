from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.recipes import run_recipe, result_page
from lamb.moodle.charts import ChartStore, render_svg
from lamb.moodle.contract import prepare_moodle
from lamb.moodle.analytics.presentation import present, TEXT


def test_analytics_contracts_are_strict_and_readonly():
    for command in ['moodle analytics capabilities --course 7',
                    'moodle analytics run grading-queue --course 7',
                    'moodle analytics run course-access --course 7 --since 2026-09-01',
                    'moodle analytics result 00000000-0000-0000-0000-000000000001 --offset 20']:
        assert prepare_moodle(command)[0].policy == 'auto'
    for command in ['moodle analytics run arbitrary --course 7',
                    'moodle analytics run course-access --course 7',
                    'moodle analytics run grading-queue --course 7 --since 2026-09-01',
                    'moodle analytics result ../../secret',
                    'moodle analytics run grading-queue --course 7 --tz invalid']:
        with pytest.raises(ValueError): prepare_moodle(command)


def test_course_access_saves_aggregates_not_learner_records(tmp_path):
    runtime = SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=2),
                              result_binding=lambda:{'generation':1},validate_result_binding=lambda *args:None)
    source = {'course_id':7, 'as_of':'2026-09-22T12:00:00Z','coverage':{'complete':True},
              'window':{'since':1788213600},
              'metrics':{'recent':3,'older':2,'unknown':1}, 'rows':[{'user_id':SECRET_ID}],
              'limitations':['Not a resource view history.']}
    with patch('lamb.moodle.analytics.recipes.course_access',return_value=source):
        result=run_recipe(runtime,SimpleNamespace(checkpoint=lambda:None),12,
            {'recipe':'course-access','course_id':7,'since':'2026-09-01','tz':'UTC','language':'en'})
    snapshot=ChartStore(runtime).read(result['chart_id'])
    assert 'user_id' not in str(snapshot)
    assert snapshot['rows'][0]['value'] == 3
    assert snapshot['view_kind'] == 'metric-bars-v1'
    assert '<svg' in render_svg(snapshot)
    assert result['refreshed'] is False


SECRET_ID=123456789


def test_grading_rows_with_same_name_remain_distinct(tmp_path):
    runtime = SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=2),
                              result_binding=lambda:{'generation':1},validate_result_binding=lambda *args:None)
    source = {'course_id':7,'coverage':{'complete':True},'limitations':[],
              'rows':[{'assignment_id':identity,'name':'Essay','needs_grading':identity,
                       'status':'ok','reason':None} for identity in (1,2)]}
    with patch('lamb.moodle.analytics.recipes.grading_queue',return_value=source):
        result=run_recipe(runtime,SimpleNamespace(checkpoint=lambda:None),12,
            {'recipe':'grading-queue','course_id':7,'tz':'UTC','language':'en'})
    assert [row['name'] for row in result['rows']] == ['Essay (#1)','Essay (#2)']
    assert '<svg' in render_svg(ChartStore(runtime).read(result['chart_id']))


def test_readback_is_bounded_and_preserves_snapshot_date():
    snapshot={'rows':[{'value':i} for i in range(25)],'as_of':'saved-time','coverage':{'complete':True}}
    first=result_page('id',snapshot)
    assert len(first['rows'])==20 and first['next_offset']==20
    last=result_page('id',snapshot,20)
    assert len(last['rows'])==5 and last['next_offset'] is None and last['as_of']=='saved-time'
    with pytest.raises(ValueError): result_page('id',snapshot,26)


@pytest.mark.parametrize('language', ['en','es','ca','eu'])
def test_localized_access_labels_preserve_counts_and_local_midnight(language):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    since = int(datetime(2026,9,1,tzinfo=ZoneInfo('Europe/Madrid')).timestamp())
    rows = [{'id':key,'value':value} for key,value in
            zip(('recent','older','no_course_access_recorded','unknown'), (3,2,1,0))]
    fields = present('course-access',language,'Europe/Madrid',{'window':{'since':since}},rows)
    assert '2026-09-01' in fields['window_label'] and 'Europe/Madrid' in fields['window_label']
    assert '00:00' in fields['window_label']
    assert [row['value'] for row in rows] == [3,2,1,0]
    assert rows[0]['name'] == TEXT[language]['recent'].format(date='2026-09-01')
    assert fields['title'] == TEXT[language]['course-access']
    assert fields['population_label'] and fields['caption']


@pytest.mark.parametrize('language', ['en','es','ca','eu'])
def test_localized_grading_reasons_keep_machine_codes_and_nulls(language):
    codes = ['team_submission_count_not_supported','online_submissions_disabled',
             'grading_counts_missing_or_invalid','grading_counts_inconsistent','grading_summary_unavailable']
    rows = [{'reason':code,'value':None} for code in codes]
    fields = present('grading-queue',language,'UTC',{},rows)
    assert [row['reason_code'] for row in rows] == codes
    assert all(row['reason'] != code and row['value'] is None for row,code in zip(rows,codes))
    assert fields['metric_label'] == TEXT[language]['grading_metric']
    assert 'window_label' not in fields
