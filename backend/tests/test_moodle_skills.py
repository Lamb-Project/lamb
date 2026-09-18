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
    assert pack.version=='1.3.0'
    validate_routing(pack)
    assert validate_skill_contracts(pack)
    names={'moodle-triage','moodle-forums','moodle-course-documents','moodle-assessment-draft'}
    assert names<=allowed_skills(pack,['creator'],['moodle'])
    assert not names & allowed_skills(pack,['creator'],[])
    assert load_pack(version='1.2.4').version=='1.2.4'


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
