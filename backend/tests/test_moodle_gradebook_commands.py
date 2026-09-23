import shlex
from unittest.mock import patch, Mock
import pytest
from lamb.moodle.task_contract import parse_task
from lamb.moodle.analytics.recipes import RECIPES
from lamb.moodle.analytics import recovery_tasks
from lamb.moodle.discovery import IDENTITY, available_recipes
from tests.test_moodle_store import stores
from tests.test_moodle_runtime import runtime


@pytest.mark.parametrize('verb',['run','start'])
def test_explicit_grade_item_selection(verb):
    spec,p=parse_task(shlex.split(f'moodle analytics {verb} assessment-comparison --course 7 --grade-item 2 --grade-item 3 --group 4 --tz Europe/Madrid'))
    assert spec.key==f'analytics.{verb}'
    assert p['grade_item_ids']==[2,3] and p['group_id']==4
    assert 'local_lambanalytics_gradebook_population' in RECIPES['assessment-comparison']['functions']


@pytest.mark.parametrize('extra', ['', '--grade-item 2', '--grade-item 2 --grade-item 2',
    '--grade-item 0 --grade-item 3', '--grade-item 2 --grade-item 3 --quiz 8',
    '--grade-item 2 --grade-item 3 --since 2026-09-01', '--grade-item 2 --grade-item 3 --until 2026-09-22',
    '--grade-item 2 --grade-item 3 --forum 8', '--grade-item 2 --grade-item 3 --tz not-a-zone',
    ' '.join(f'--grade-item {i}' for i in range(1,22))])
@pytest.mark.parametrize('verb',['run','start'])
def test_invalid_selection_rejected(verb,extra):
    with pytest.raises(ValueError):parse_task(shlex.split(f'moodle analytics {verb} assessment-comparison --course 7 {extra}'))


def test_grade_items_never_apply_to_other_recipe():
    with pytest.raises(ValueError,match='only'):
        parse_task(shlex.split('moodle analytics run grading-queue --course 7 --grade-item 2'))


def test_recovery_start_routes_to_gradebook_handler():
    with patch.object(recovery_tasks.gradebook_tasks,'execute',return_value={'run_id':'test'}) as handler:
        params={'recipe':'assessment-comparison'}
        assert recovery_tasks.execute(None,None,None,3,'analytics.start',params)=={'run_id':'test'}
        handler.assert_called_once_with(None,None,None,3,'analytics.start',params)


def test_discovery_requires_every_gradebook_source():
    required=set(RECIPES['assessment-comparison']['functions'])
    assert 'assessment-comparison' in available_recipes(IDENTITY|required)
    for function in required:
        assert 'assessment-comparison' not in available_recipes((IDENTITY|required)-{function})


def test_runtime_run_starts_and_advances_one_step(stores):
    rt=runtime(stores)
    params={'recipe':'assessment-comparison','course_id':7,'grade_item_ids':[2,3],'group_id':0,'language':'en','tz':'UTC'}
    with patch('lamb.moodle.analytics.gradebook_tasks.execute',side_effect=[{'run_id':'gradebook-run'},{'progress':True}]) as handler:
        assert rt.task('analytics.run',params)=={'progress':True}
        assert [call.args[4:] for call in handler.call_args_list]==[
            ('analytics.start',params),('analytics.continue',{'run_id':'gradebook-run','step':0})]
