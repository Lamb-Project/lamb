from types import SimpleNamespace
from unittest.mock import Mock,patch
import pytest
from lamb.moodle.contract import prepare_moodle
from lamb.moodle.analytics.recipes import run_recipe
from lamb.moodle.charts import ChartStore,render_svg
from tests.test_moodle_deadlines import collect,SINCE,UNTIL


def test_deadline_contract_requires_explicit_window_and_no_group_or_assignment():
    command='moodle analytics run deadlines --course 7 --since 2026-10-25 --until 2026-10-27'
    assert prepare_moodle(command)[1]['recipe']=='deadlines'
    for invalid in [command+' --group 1',command+' --assignment 2',
                    command.replace(' --until 2026-10-27',''),command.replace('2026-10-27','2026-10-24')]:
        with pytest.raises(ValueError):prepare_moodle(invalid)


@pytest.mark.parametrize('language',['en','es','ca','eu'])
def test_saved_calendar_retains_dates_events_density_and_binding(language,tmp_path):
    validate=Mock()
    runtime=SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=2),
        result_binding=lambda:{'generation':1},validate_result_binding=validate)
    source=collect()
    with patch('lamb.moodle.analytics.recipes.deadline_calendar',return_value=source) as collector:
        result=run_recipe(runtime,SimpleNamespace(checkpoint=lambda:None),12,
            {'recipe':'deadlines','course_id':7,'since':'2026-10-25','until':'2026-10-27',
             'tz':'Europe/Madrid','language':language})
    assert collector.call_args.kwargs['until']-collector.call_args.kwargs['since']==49*3600
    saved=ChartStore(runtime).read(result['chart_id'])
    assert saved['view_kind']=='deadline-calendar-v1'
    assert saved['events']==source['events'] and saved['weekly']==source['weekly']
    assert saved['rows'][1]['due_label'].endswith('+02:00')
    assert saved['rows'][2]['due_label'].endswith('+01:00')
    assert saved['rows'][-1]['due']==0
    assert validate.call_args.args[0]['date_scopes']==source['date_scopes']
    assert ChartStore(runtime).listing()['items'][0]['date_scopes']==source['date_scopes']
    assert '<svg' in render_svg(saved)


def test_full_calendar_capacity_preserves_every_activity_and_event(tmp_path):
    from lamb.moodle.analytics.client import DEFAULT_DATES_FUNCTION
    modules=[{'id':i,'instance':i,'modname':'assign','name':'🌍'*160} for i in range(1,101)]
    records=[{'cmid':i,'instanceid':i,'modname':'assign','opens':SINCE+i,
              'due':SINCE+3600+i,'closes':SINCE+7200+i} for i in range(1,101)]
    def call(function,**params):
        if function!=DEFAULT_DATES_FUNCTION:return [{'modules':modules}]
        return {'authorized':True,'scopeonly':bool(params.get('scopeonly')),'courseid':7,
            'cmids':list(range(1,101)),'basis':'stored_course_defaults','relative_dates':False,
            'dates':[] if params.get('scopeonly') else records}
    runtime=SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=2),
        result_binding=lambda:{'generation':1},validate_result_binding=lambda *args:None)
    with patch('lamb.moodle.analytics.deadlines.MoodleScope') as scope:
        scope.return_value.require_teacher.return_value=7
        scope.return_value.own_courses.return_value={7:SimpleNamespace(fullname='Large fixture')}
        result=run_recipe(runtime,SimpleNamespace(call=call,checkpoint=lambda:None),12,
            {'recipe':'deadlines','course_id':7,'since':'2026-10-25','until':'2026-10-27',
             'tz':'Europe/Madrid','language':'ca'})
    saved=ChartStore(runtime).read(result['chart_id'])
    assert len(saved['rows'])==100 and len(saved['events'])==300
    assert sum(week['deadlines'] for week in saved['weekly'])==100
    assert result['next_offset']==20
    from lamb.moodle.analytics.recipes import result_page
    recovered=[]
    for offset in range(0,100,20):
        recovered.extend(result_page(result['chart_id'],saved,offset)['rows'])
    assert recovered==saved['rows']


def test_calendar_size_allowance_does_not_relax_other_chart_limits(tmp_path):
    from lamb.moodle.charts import MAX_BYTES,MAX_CALENDAR_BYTES
    runtime=SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=2),
        validate_result_binding=lambda *args:None)
    store=ChartStore(runtime)
    calendar={'recipe':{'id':'deadlines','version':1},'view_kind':'deadline-calendar-v1',
        'padding':'x'*MAX_BYTES}
    identity=store.save(calendar,{})
    assert store.read(identity)['padding']==calendar['padding']
    for invalid in [dict(calendar,view_kind='metric-bars-v1'),
                    dict(calendar,recipe={'id':'view-trends'}),
                    dict(calendar,padding='x'*MAX_CALENDAR_BYTES)]:
        with pytest.raises(ValueError,match='size limit'):store.save(invalid,{})
