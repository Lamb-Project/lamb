from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.recipes import run_recipe, result_page, capabilities
from lamb.moodle.charts import ChartStore, render_svg
from lamb.moodle.contract import prepare_moodle
from lamb.moodle.analytics.presentation import present, TEXT


def test_resource_recipe_reports_missing_optional_adapter_without_fabricating_support():
    client=SimpleNamespace(call=lambda function:{'functions':[{'name':'core_enrol_get_enrolled_users'}]})
    with patch('lamb.moodle.analytics.recipes.MoodleScope'):
        result=capabilities(client,12,7)
    recipe=next(row for row in result['recipes'] if row['id']=='resource-reach')
    assert recipe['source_status']=='unavailable'
    assert 'local_lambanalytics_resource_events' in recipe['missing_functions']
    assert 'local_lambanalytics_resource_scope' in recipe['missing_functions']


def test_analytics_contracts_are_strict_and_readonly():
    for command in ['moodle analytics capabilities --course 7',
                    'moodle analytics run resource-reach --course 7 --since 2026-09-01 --until 2026-09-10 --group 2',
                    'moodle analytics run grading-queue --course 7',
                    'moodle analytics run course-access --course 7 --since 2026-09-01',
                    'moodle analytics result 00000000-0000-0000-0000-000000000001 --offset 20']:
        assert prepare_moodle(command)[0].policy == 'auto'
    for command in ['moodle analytics run arbitrary --course 7',
                    'moodle analytics run resource-reach --course 7',
                    'moodle analytics run resource-reach --course 7 --since 2026-09-10 --until 2026-09-01',
                    'moodle analytics run course-access --course 7 --since 2026-09-01 --group 2',
                    'moodle analytics run course-access --course 7',
                    'moodle analytics run grading-queue --course 7 --since 2026-09-01',
                    'moodle analytics result ../../secret',
                    'moodle analytics run grading-queue --course 7 --tz invalid']:
        with pytest.raises(ValueError): prepare_moodle(command)


def test_course_access_saves_aggregates_not_learner_records(tmp_path):
    runtime = SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=2),
                              result_binding=lambda:{'generation':1},validate_result_binding=lambda *args:None)
    source = {'course_id':7, 'as_of':'2026-09-22T12:00:00Z',
              'coverage':{'complete':True,'student_rows':6,'non_student_rows':1,'role_unknown':0,'users_scanned':7},
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
    assert result['population_counts'] == {'included_students':6,'excluded_non_students':1,
        'unknown_role_enrolments':0,'all_enrolments_scanned':7}
    assert result['snapshot_date_label'] == '2026-09-22T12:00:00+00:00 (UTC)'


SECRET_ID=123456789


def test_grading_rows_with_same_name_remain_distinct(tmp_path):
    runtime = SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=2),
                              result_binding=lambda:{'generation':1},validate_result_binding=lambda *args:None)
    source = {'course_id':7,'as_of':'2026-09-22T12:00:00Z','coverage':{'complete':True},'limitations':[],
              'rows':[{'assignment_id':identity,'name':'Essay','needs_grading':identity,
                       'status':'ok','reason':None} for identity in (1,2)]}
    with patch('lamb.moodle.analytics.recipes.grading_queue',return_value=source):
        result=run_recipe(runtime,SimpleNamespace(checkpoint=lambda:None),12,
            {'recipe':'grading-queue','course_id':7,'tz':'Europe/Madrid','language':'en'})
    assert [row['name'] for row in result['rows']] == ['Essay (#1)','Essay (#2)']
    assert result['as_of_local'] == '2026-09-22T14:00:00+02:00'
    assert result['snapshot_date_label'].endswith('(Europe/Madrid)')
    assert '<svg' in render_svg(ChartStore(runtime).read(result['chart_id']))


def test_readback_is_bounded_and_preserves_snapshot_date():
    snapshot={'rows':[{'value':i} for i in range(25)],'as_of':'saved-time','coverage':{'complete':True}}
    first=result_page('id',snapshot)
    assert len(first['rows'])==20 and first['next_offset']==20
    last=result_page('id',snapshot,20)
    assert len(last['rows'])==5 and last['next_offset'] is None and last['as_of']=='saved-time'
    with pytest.raises(ValueError): result_page('id',snapshot,26)


@pytest.mark.parametrize('language',['en','es','ca','eu'])
def test_resource_recipe_saves_group_and_module_bindings(language,tmp_path):
    runtime=SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=2),
        result_binding=lambda:{'generation':1},validate_result_binding=lambda *args:None)
    source={'course_id':7,'course_name':'Synthetic','group_id':2,'as_of':'2026-09-22T12:00:00Z',
        'window':{'since':1788213600,'until':1788991200},'coverage':{'complete':False,'student_rows':3},
        'limitations':['Incomplete history'],'rows':[{'cmid':10,'name':'Reading','unique_student_viewers':2,
            'recorded_module_views':4,'recorded_chapter_views':0,'population_students':3}]}
    with patch('lamb.moodle.analytics.recipes.resource_reach',return_value=source), \
            patch('lamb.moodle.analytics.recipes.validate_resource_scope') as authorize:
        result=run_recipe(runtime,SimpleNamespace(checkpoint=lambda:None),12,
            {'recipe':'resource-reach','course_id':7,'group_id':2,'since':'2026-09-01','until':'2026-09-10',
             'tz':'Europe/Madrid','language':language})
    expected={'course_id':7,'group_id':2,'module_ids':[10]}
    assert authorize.call_args.args[1] == expected
    assert result['resource_scopes'] == [expected]
    assert result['rows'][0]['value'] == 2 and len(result['resource_columns']) == 5
    snapshot=ChartStore(runtime).read(result['chart_id'])
    assert '<svg' in render_svg(snapshot)
    assert ChartStore(runtime).listing()['items'][0]['resource_scopes'] == [expected]
    import json
    envelope=json.loads((ChartStore(runtime).root / (result['chart_id']+'.json')).read_text())
    assert envelope['binding']['resource_scopes'] == [expected]


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
