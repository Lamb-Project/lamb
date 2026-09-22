from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.view_time import ViewTimeBuckets
from lamb.moodle.analytics.recipes import run_recipe
from lamb.moodle.charts import ChartStore,render_svg
from lamb.moodle.contract import prepare_moodle


@pytest.mark.parametrize('language',['en','es','ca','eu'])
@pytest.mark.parametrize('recipe',['view-trends','view-heatmap'])
def test_view_trend_saves_dates_counts_and_current_resource_scope(tmp_path,language,recipe):
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
            {'recipe':recipe,'course_id':7,'since':'2025-06-15','until':'2025-06-16',
                'group_id':2,'tz':'Europe/Madrid','language':language})
    assert scope.call_args.args[1]=={'course_id':7,'group_id':2,'module_ids':[10]}
    saved=ChartStore(runtime).read(result['chart_id'])
    if recipe=='view-trends':
        assert saved['view_kind']=='view-trend-v1' and len(saved['view_columns'])==6
        assert saved['rows'][0]['date']==series.snapshot(collection_complete=True)['daily'][0]['date']
    else:
        assert saved['view_kind']=='view-heatmap-v1'
        assert len(saved['rows'])==168
        assert len(saved['heatmap_rows'])==7
        assert all(len(row['values'])==24 for row in saved['heatmap_rows'])
        assert sum(sum(row['values']) for row in saved['heatmap_rows'])==1
        assert all(row['name'] for row in saved['rows'])
    assert sum(row['value'] for row in saved['rows'])==1
    assert saved['resource_scopes']==[scope.call_args.args[1]]
    assert '<svg' in render_svg(saved)
    if recipe=='view-heatmap':
        saved['rows'][0]['value']=-1
        with pytest.raises(ValueError,match='Invalid view heatmap grid'):render_svg(saved)
        saved['rows'][0]['value']=0
        saved['rows'][0]['hour']=saved['rows'][1]['hour']
        with pytest.raises(ValueError,match='Invalid view heatmap grid'):render_svg(saved)


@pytest.mark.parametrize('recipe',['view-trends','view-heatmap'])
def test_view_trend_command_requires_window_and_accepts_group(recipe):
    spec,params=prepare_moodle(f'moodle analytics run {recipe} --course 7 --since 2026-09-01 --until 2026-09-20 --group 2 --tz Europe/Madrid')
    assert spec.policy=='auto' and params['recipe']==recipe
    for suffix in ('','--since invalid','--since 2026-09-20 --until 2026-09-01',
        '--since 2026-09-01 --assignment 3'):
        with pytest.raises(ValueError):prepare_moodle(f'moodle analytics run {recipe} --course 7 '+suffix)
