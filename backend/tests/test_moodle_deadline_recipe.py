from types import SimpleNamespace
from unittest.mock import Mock,patch
import pytest
from lamb.moodle.contract import prepare_moodle
from lamb.moodle.analytics.recipes import run_recipe
from lamb.moodle.charts import ChartStore,render_svg
from tests.test_moodle_deadlines import collect


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
