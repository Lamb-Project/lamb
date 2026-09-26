import asyncio
import pytest
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from tests.test_aac_legacy import agent,tool
from lamb.aac.pack_loader import load_pack,allowed_skills
from lamb.aac.pack_build import validate_routing
from lamb.aac.contract import validate_skill_contracts
from lamb.moodle.runtime import attach_to_agent


def test_moodle_recipes_and_generated_commands_validate():
    pack=load_pack()
    assert pack.version=='1.11.5'
    validate_routing(pack)
    assert validate_skill_contracts(pack)
    names={'moodle-triage','moodle-forums','moodle-course-documents','moodle-assessment-draft'}
    assert names<=allowed_skills(pack,['creator'],['moodle'])
    assert not names & allowed_skills(pack,['creator'],[])
    assert load_pack(version='1.2.4').version=='1.2.4'
    assert load_pack(version='1.3.1').version=='1.3.1'
    validate_routing(load_pack(version='1.4.0'))


def test_restoration_pack_corrects_ids_and_dates_without_changing_old_release():
    pack = load_pack()
    forums = pack.text('skills/moodle_forums.md')
    assert 'discussion_id for posts reads' in forums
    assert 'first_post_id for replies' in forums
    assert 'not verified course defaults or individual student deadlines' in pack.text('skills/moodle_triage.md')
    assert load_pack(version='1.11.1').version == '1.11.1'
    assert 'Use the returned discussion ID' in load_pack(version='1.11.1').text('skills/moodle_forums.md')


def test_triage_coverage_discipline_is_in_the_current_pack_only():
    """#518: unread courses are reported as not inspected, never as no data; 1.11.4 stays frozen."""
    triage = load_pack().text('skills/moodle_triage.md')
    for phrase in ['NOT INSPECTED, never "no data"', 'inspected N of M courses', 'Every count you give must come from a read']:
        assert phrase in triage
    assert 'NOT INSPECTED' not in load_pack(version='1.11.4').text('skills/moodle_triage.md')


@pytest.mark.parametrize('version', ['1.12.0', '1.28.0', '1.34.0'])
def test_post_baseline_pack_pins_fail_explicitly_without_silent_fallback(version):
    with pytest.raises(ValueError, match='not installed'):
        load_pack(settings={'pack_version': version})


def test_new_task_pack_requires_an_engine_with_task_support(monkeypatch):
    monkeypatch.setattr('lamb.aac.pack_loader.ENGINE_VERSION', '0.7.0')
    with pytest.raises(ValueError, match='newer LAMB engine'):
        load_pack()
    assert load_pack(version='1.3.1').version == '1.3.1'


def test_runtime_guard_loads_recipe_before_execution_and_revokes_access(stores):
    rt=runtime(stores)
    a,_,shell=agent([])
    shell.allowed_commands=set()
    a.pack=load_pack();a.skill_state={'context':{},'brief':{'layers':['creator']}}
    attach_to_agent(a,rt.store)
    assert 'moodle-triage' in a.conversation[-1]['content']
    first=asyncio.run(a._execute_tool(tool('moodle sync 10')))
    assert first['skill_loaded']=='moodle-triage' and not first['success']
    shell.execute.assert_not_awaited()
    second=asyncio.run(a._execute_tool(tool('moodle sync 10')))
    assert second['success']
    shell.execute.assert_awaited_once()
    rt.store.disconnect();attach_to_agent(a,rt.store)
    with pytest.raises(ValueError):a.activate_skill('moodle-forums')


def test_permission_change_selects_new_snapshot_without_rewriting_old_one(stores):
    rt=runtime(stores)
    a,_,shell=agent([])
    shell.allowed_commands=set()
    a.pack=load_pack();a.skill_state={'context':{},'brief':{'layers':['creator']}}
    attach_to_agent(a,rt.store)
    # Start with an explicit runtime-derived readonly capability.
    facts=a.skill_state['moodle_capability']
    facts['commands']=[key for key in facts['commands'] if key not in {'moodle.forum.reply','moodle.forum.post'}]
    first=a.activate_skill('moodle-forums')
    old=a.skill_state['active_snapshot']
    stored=a.skill_state['snapshots'][old]['prompt']
    assert 'Forum posting is unavailable' in first
    assert 'already active' in a.activate_skill('moodle-forums')
    facts['commands']+=['moodle.forum.reply','moodle.forum.post']
    second=a.activate_skill('moodle-forums')
    assert a.skill_state['active_snapshot']!=old
    assert a.skill_state['snapshots'][old]['prompt']==stored
    assert 'Forum posting is unavailable' not in second
    assert 'moodle forum reply --post-id' in second
