"""Cumulative #510 date/source regressions, independent synthetic oracles."""
import asyncio
from copy import deepcopy
from datetime import date, timedelta
from unittest.mock import patch

import pytest
import respx

from lamb.moodle.analytics.window import plan_window, require_event_window, require_event_timestamps
from lamb.moodle.contract import prepare_moodle
from lamb.moodle.discovery import IDENTITY, ROSTER, recipe_sources
from lamb.moodle.workflow import render_permissions
from lamb.aac.pack_loader import load_pack
from lamb.aac.liteshell.shell import LiteShell
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from tests.test_moodle_discovery import set_functions


@pytest.mark.parametrize('start,through,until,days,supported',[
    ('2026-06-01','2026-08-31','2026-09-01',92,False),
    ('2026-08-01','2026-08-31','2026-09-01',31,True),
    ('2024-02-28','2024-02-29','2024-03-01',2,True),
    ('2026-08-31','2026-08-31','2026-09-01',1,True)])
def test_inclusive_ranges_preserve_exact_calendar_dates(start,through,until,days,supported):
    result=plan_window(start,through=through,tz='Europe/Madrid')
    assert (result['since'],result['through'],result['until'],result['calendar_days']) == (start,through,until,days)
    assert result['collection_supported'] is supported
    assert result['source_availability']=='not_checked' and result['historical_coverage']=='unknown'


@pytest.mark.parametrize('start,days,seconds,supported',[
    ('2026-06-01',90,90*86400,True),
    ('2026-06-01',91,91*86400,False),
    ('2026-03-01',90,90*86400-3600,True),
    ('2026-10-01',90,90*86400+3600,False),
    ('2026-10-25',1,25*3600,True),
    ('2026-03-29',1,23*3600,True)])
def test_local_days_and_adapter_transport_limit_are_separate(start,days,seconds,supported):
    end=(date.fromisoformat(start)+timedelta(days=days)).isoformat()
    result=plan_window(start,until=end,tz='Europe/Madrid')
    assert result['calendar_days']==days and result['elapsed_seconds']==seconds
    assert result['collection_supported'] is supported
    if supported:
        assert require_event_window(start,end,'Europe/Madrid')==result
        require_event_timestamps(result['since_timestamp'],result['until_timestamp'],'Europe/Madrid')
    else:
        with pytest.raises(ValueError,match='unsupported|not implemented'):
            require_event_window(start,end,'Europe/Madrid')
        with pytest.raises(ValueError,match='unsupported'):
            require_event_timestamps(result['since_timestamp'],result['until_timestamp'],'Europe/Madrid')


@pytest.mark.parametrize('kwargs',[
    {}, {'until':'2026-08-02','through':'2026-08-01'}, {'until':'2026-08-01'},
    {'through':'2026-02-30'}, {'through':'20260802'}, {'through':'2026-08-02','tz':'not/a/zone'},
    {'through':'9999-12-31'}])
def test_invalid_ambiguous_bounds_fail_without_inventing_dates(kwargs):
    with pytest.raises(ValueError):plan_window('2026-08-01',**kwargs)


def test_run_through_normalizes_once_and_oversize_fails_before_execution():
    _,params=prepare_moodle('moodle analytics run view-trends --course 7 --since 2026-08-01 --through 2026-08-31 --tz Europe/Madrid')
    assert params['until']=='2026-09-01' and 'through' not in params
    with pytest.raises(ValueError,match=r'2026-06-01, 2026-09-01.*92 local days'):
        prepare_moodle('moodle analytics run view-trends --course 7 --since 2026-06-01 --through 2026-08-31 --tz Europe/Madrid')


@respx.mock
def test_local_window_task_has_no_remote_calls_or_course_binding(stores):
    rt=runtime(stores);set_functions(rt,set())
    shell=LiteShell('', '', 'fixture@test',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    result=asyncio.run(shell.execute('moodle analytics window --since 2026-06-01 --through 2026-08-31 --tz Europe/Madrid'))
    assert result.success,result.error
    assert result.data['calendar_days']==92 and result.data['until']=='2026-09-01'
    assert not result.data['collection_supported'] and not respx.calls
    assert 'course_id' not in (result.result_binding or {})


@respx.mock
def test_missing_functions_prevent_collection_and_preserve_roster(stores):
    rt=runtime(stores);set_functions(rt,IDENTITY | ROSTER)
    sources=recipe_sources(rt.snapshot()['record'])
    assert sources['resource-reach']['function_status']=='missing'
    assert sources['course-access']['function_status']=='exposed'
    assert 'moodle.enrol.list-users' in rt.available()
    spec,params=prepare_moodle('moodle analytics run view-trends --course 7 --since 2026-08-01 --until 2026-09-01')
    with pytest.raises(PermissionError,match='missing required functions') as error:
        rt.execute(spec.key,params)
    assert 'not an empty date range' in str(error.value) and not respx.calls


def test_unavailable_recipe_examples_removed_even_when_run_is_available():
    prompt=load_pack().text('skills/moodle_triage.md')
    sources=recipe_sources({'functions':sorted(IDENTITY | ROSTER)})
    result=render_permissions(prompt,{'moodle.analytics.run','moodle.analytics.window'},sources)
    assert '\nmoodle analytics run course-access ' in result
    assert '\nmoodle analytics run view-trends ' not in result
    assert '\nmoodle analytics run resource-reach ' not in result
    assert '\nmoodle analytics window ' in result
    assert 'UNAVAILABLE ANALYTICS SOURCES' in result
    assert 'historical availability period is UNKNOWN' in result


def test_recipe_capability_change_selects_new_workflow_snapshot_without_prefix_rewrite(stores):
    from tests.test_aac_legacy import agent
    from lamb.moodle.runtime import attach_to_agent
    rt=runtime(stores)
    a,_,shell=agent([]);shell.allowed_commands=set()
    a.pack=load_pack();a.skill_state={'context':{},'brief':{'layers':['creator']}}
    attach_to_agent(a,rt.store);a.activate_skill('moodle-triage')
    previous=a.skill_state['active_snapshot'];saved=deepcopy(a.skill_state['snapshots'][previous])
    # Same command keys, changed source-specific fact: must select a new snapshot.
    a.skill_state['moodle_capability']['analytics_sources']['view-trends']['function_status']='missing'
    a.activate_skill('moodle-triage')
    assert a.skill_state['active_snapshot']!=previous
    assert a.skill_state['snapshots'][previous]==saved
    assert '\nmoodle analytics run view-trends ' not in a.skill_state['snapshots'][a.skill_state['active_snapshot']]['prompt']


def test_successful_empty_and_incomplete_results_do_not_claim_complete_history(monkeypatch):
    from tests.test_moodle_analytics_events import Client, collect, page, event
    empty=collect(Client([page([])]))
    assert empty['coverage']['collection_complete'] and not empty['coverage']['history_complete']
    assert all(row['unique_student_viewers']==0 for row in empty['rows'])
    monkeypatch.setattr('lamb.moodle.analytics.events.MAX_EVENT_PAGES',1)
    partial=collect(Client([page([event(1)],has_more=True,next_afterid=1)]))
    assert not partial['coverage']['collection_complete'] and not partial['coverage']['history_complete']
