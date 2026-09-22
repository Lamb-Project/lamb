from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.view_time import ViewTimeBuckets
from lamb.moodle.analytics.recipes import run_recipe
from lamb.moodle.charts import ChartStore,render_svg
from lamb.moodle.contract import prepare_moodle


@pytest.mark.parametrize('language',['en','es','ca','eu'])
def test_view_trend_saves_dates_counts_and_current_resource_scope(tmp_path,language):
    runtime=SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=2),
        result_binding=lambda:{'generation':1},validate_result_binding=lambda *args:None)
    series=ViewTimeBuckets([1,2],since=1750000000,until=1750086400,timezone='Europe/Madrid')
    series.add(event_id=1,student_id=1,timestamp=1750000001,kind='course_view')
    source={'course_id':7,'course_name':'Fixture','group_id':2,'as_of':'2026-09-22T12:00:00Z',
        'source':'fixture','watermark':1,'coverage':{'student_rows':2,'complete':False,'collection_complete':True},
        'module_ids':[10],'view_time':series.snapshot(collection_complete=True)}
    with patch('lamb.moodle.analytics.recipes.view_activity',return_value=source), \
         patch('lamb.moodle.analytics.recipes.validate_resource_scope') as scope:
        result=run_recipe(runtime,SimpleNamespace(checkpoint=lambda:None),12,
            {'recipe':'view-trends','course_id':7,'since':'2025-06-15','until':'2025-06-16',
                'group_id':2,'tz':'Europe/Madrid','language':language})
    assert scope.call_args.args[1]=={'course_id':7,'group_id':2,'module_ids':[10]}
    saved=ChartStore(runtime).read(result['chart_id'])
    assert saved['view_kind']=='view-trend-v1' and len(saved['view_columns'])==6
    assert saved['rows'][0]['date']==series.snapshot(collection_complete=True)['daily'][0]['date']
    assert sum(row['value'] for row in saved['rows'])==1
    assert saved['resource_scopes']==[scope.call_args.args[1]]
    assert '<svg' in render_svg(saved)


def test_view_trend_command_requires_window_and_accepts_group():
    spec,params=prepare_moodle('moodle analytics run view-trends --course 7 --since 2026-09-01 --until 2026-09-20 --group 2 --tz Europe/Madrid')
    assert spec.policy=='auto' and params['recipe']=='view-trends'
    for suffix in ('','--since invalid','--since 2026-09-20 --until 2026-09-01',
        '--since 2026-09-01 --assignment 3'):
        with pytest.raises(ValueError):prepare_moodle('moodle analytics run view-trends --course 7 '+suffix)
