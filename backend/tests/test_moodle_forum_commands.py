import shlex
from unittest.mock import patch
import pytest
from lamb.moodle.task_contract import parse_task
from lamb.moodle.analytics.forum_window import parse_window
from lamb.moodle.analytics.recipes import RECIPES
from lamb.moodle.discovery import IDENTITY,available_recipes,filter_keys
from lamb.moodle.analytics.recovery_tasks import execute
from lamb.moodle.analytics.forum_checkpoints import ForumCheckpoints
from lamb.moodle.analytics.forum_run import start
from tests.test_moodle_completion_tasks import fixture


@pytest.mark.parametrize('verb',['start','run'])
@pytest.mark.parametrize('recipe',['forum-participation','forum-discussions','forum-network'])
def test_explicit_forum_window(verb,recipe):
    command=f'moodle analytics {verb} {recipe} --course 7 --forum 8 --since 2025-10-25 --through 2025-10-26 --tz Europe/Madrid'
    spec,p=parse_task(shlex.split(command))
    assert p['until']-p['since']==49*3600 and p['group_id']==0
    assert p['forum_id']==8 and spec.key==f'analytics.{verb}'
    _,exclusive=parse_task(shlex.split(command.replace('--through 2025-10-26','--until 2025-10-27')))
    assert exclusive==p


@pytest.mark.parametrize('tail',['','--forum 8','--forum 8 --since 2025-01-01',
    '--forum 8 --since 2025-01-01 --until 2025-02-01 --through 2025-01-31',
    '--forum 8 --since 2025-01-01 --until 2027-01-01',
    '--forum 8 --since 2025-01-01 --until 2025-02-01 --quiz 1',
    '--forum 8 --since 2025-01-01 --until 2025-02-01 --assignment 1'])
@pytest.mark.parametrize('recipe',['forum-participation','forum-discussions','forum-network'])
def test_missing_ambiguous_and_foreign_options_rejected(tail,recipe):
    with pytest.raises(ValueError):
        parse_task(shlex.split(f'moodle analytics run {recipe} --course 7 '+tail))


def test_future_window_rejected_without_clamping():
    with patch('lamb.moodle.analytics.forum_window.time.time',return_value=0),pytest.raises(ValueError,match='not changed'):
        parse_window('2025-01-01','2025-02-01',None,'UTC')


def test_capabilities_require_all_sources():
    functions=set(RECIPES['forum-participation']['functions'])
    names=IDENTITY|functions
    assert {'forum-participation','forum-discussions','forum-network'}<=set(available_recipes(names))
    keys={'analytics.run','analytics.start','analytics.continue'}
    assert filter_keys(keys,{'functions':sorted(names)})==keys
    for missing in functions:
        assert not {'forum-participation','forum-discussions','forum-network'} & set(available_recipes(names-{missing}))


def test_recovery_routes_exact_forum_namespace(tmp_path):
    results,rt,client=fixture(tmp_path)
    record=start(ForumCheckpoints(results),7,8,since=100,until=150)
    with patch('lamb.moodle.analytics.forum_tasks.execute',return_value={'forum':True}) as handler:
        assert execute(rt,results,client,3,'analytics.continue',{'run_id':record['id'],'step':0})=={'forum':True}
        handler.assert_called_once()
