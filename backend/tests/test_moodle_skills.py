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
    assert pack.version=='1.24.0'
    validate_routing(pack)
    assert validate_skill_contracts(pack)
    names={'moodle-triage','moodle-forums','moodle-course-documents','moodle-assessment-draft'}
    assert names<=allowed_skills(pack,['creator'],['moodle'])
    assert not names & allowed_skills(pack,['creator'],[])
    assert load_pack(version='1.2.4').version=='1.2.4'
    assert load_pack(version='1.3.1').version=='1.3.1'
    validate_routing(load_pack(version='1.4.0'))


def test_all_completion_recovery_commands_have_a_workflow():
    routing=load_pack().data('routing.yaml')
    for suffix in ('run','start','continue','runs'):
        command='moodle.analytics.'+suffix
        assert routing['DEFAULT_SKILL'][command]=='moodle-triage'
        assert command in routing['CAPABILITIES']['moodle-triage']


def test_calendar_guidance_preserves_defaults_window_and_snapshot_semantics():
    text=(load_pack().skills_dir/'moodle_triage.md').read_text()
    assert 'moodle analytics run deadlines --course COURSE_ID' in text
    for phrase in ('not individual or group deadlines','exclusive end','Weekly density counts due events only',
                   'Do not infer lateness','relative-date course','chart read'):
        assert phrase in text
    assert 'connected_account_effective' in text
    assert 'Do not call them verified course defaults' in text


def test_new_task_pack_requires_an_engine_with_task_support(monkeypatch):
    monkeypatch.setattr('lamb.aac.pack_loader.ENGINE_VERSION', '0.7.0')
    with pytest.raises(ValueError, match='newer LAMB engine'):
        load_pack()
    assert load_pack(version='1.3.1').version == '1.3.1'


def test_triage_distinguishes_grading_from_missing_submissions():
    text = (load_pack().skills_dir / 'moodle_triage.md').read_text()
    assert 'It NEVER means ungraded submissions' in text
    assert 'reconsider the requested metric before retrying' in text
    assert 'Never refresh an analytics chart with the submission-chart recipe' in text
    assert 'all_enrolments_scanned includes teachers' in text
    assert 'copy snapshot_date_label' in text
    assert load_pack(version='1.12.0').version == '1.12.0'


def test_grade_recipe_guidance_preserves_raw_missing_and_saved_scope_semantics():
    text = (load_pack().skills_dir / 'moodle_triage.md').read_text()
    assert 'moodle analytics run grade-distribution --course COURSE_ID --assignment ASSIGNMENT_ID' in text
    assert 'NOT final gradebook marks' in text
    assert 'NOT zero or failure' in text
    assert 'both saved course and assignment IDs' in text
    assert 'do not invent a pass threshold' in text
    assert 'use metrics.zero_n' in text
    assert 'mean UNKNOWN' in text
    assert 'run chart read first' in text
    persona = (load_pack().path / 'persona.md').read_text()
    assert 'Only submission charts require' in persona
    assert 'even if the figures are still in conversation history' in persona
    assert 'cannot establish whether the marks have been published' in persona
    assert load_pack(version='1.13.0').version == '1.13.0'


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


def test_completion_guidance_preserves_states_and_evidence_limits():
    text = (load_pack().skills_dir / 'moodle_triage.md').read_text()
    assert 'moodle analytics start activity-completion --course COURSE_ID --tz Europe/Madrid --language es' in text
    assert 'NOT population minus overall_complete' in text
    assert 'complete_fail can still count as overall complete' in text
    assert 'Never recalculate overall_complete' in text
    assert 'unknown and untracked are separate' in text
    assert 'Individual eligibility, required activities and schedules were not collected' in text
    assert 'No date, assignment or group filter is supported' in text
    assert 'read the saved chart first' in text
    assert 'Use the capability listing for implemented recipes' in text
    assert 'mutually exclusive, not nested categories' in text
    assert 'in that turn before answering' in text
    assert load_pack(version='1.15.0').version == '1.15.0'
    assert load_pack(version='1.14.3').version == '1.14.3'


def test_triage_documents_every_executable_analytics_recipe():
    import re
    from lamb.moodle.analytics.recipes import RECIPES
    text = (load_pack().skills_dir / 'moodle_triage.md').read_text()
    documented = set(re.findall(r'^moodle analytics (?:run|start) ([a-z-]+) ', text, re.M))
    assert documented == set(RECIPES)


def test_recoverable_completion_guidance_does_not_confuse_progress_with_evidence():
    text=(load_pack().skills_dir/'moodle_triage.md').read_text()
    assert 'moodle analytics start activity-completion --course COURSE_ID' in text
    assert 'moodle analytics continue RUN_ID --step 0' in text
    assert 'moodle analytics runs' in text
    assert 'creates a run, not a chart' in text
    assert 'Both use the same durable workflow' in text
    assert 'not resumable' not in text
    assert 'do not increment it yourself' in text
    assert 'not students who completed an activity' in text
    assert 'including completed runs' in text
    assert "do not establish the actor's identity or role" in text
    assert load_pack(version='1.15.1').version=='1.15.1'
    assert 'analytics run starts a recoverable collection and executes its first step' in text
    assert 'Tracking mode and manual overrides are different fields' in text
    assert load_pack(version='1.16.0').version=='1.16.0'


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
