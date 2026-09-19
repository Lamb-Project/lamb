import pytest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from lamb.moodle.router import effective_driver
from lamb.moodle.runtime import attach_to_agent
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores


def test_disclosure_matches_actual_fallback_client_without_secrets():
    from lamb.aac import router
    resolver=Mock()
    resolver.organization={'config':{}}
    resolver.get_global_default_model_config.return_value={'provider':'google','model':'original'}
    resolver.resolve_model_for_completion.return_value={'provider':'openai','model':'fallback'}
    resolver.get_provider_config.return_value={'enabled':True,'api_key':'private-key','base_url':'https://private-proxy/v1'}
    auth=SimpleNamespace(user={'email':'fixture@example.invalid'})
    with patch('lamb.completions.org_config_resolver.OrganizationConfigResolver',return_value=resolver):
        disclosure=effective_driver(auth)
    with patch.object(router,'OrganizationConfigResolver',return_value=resolver), patch.object(router,'AsyncOpenAI',return_value=SimpleNamespace()) as allocate:
        client,model=router._resolve_agent_llm(auth.user['email'])
    assert disclosure==client._lamb_aac_driver=={'provider':'openai','model':'fallback'}
    assert model=='fallback'
    assert allocate.call_args.kwargs['api_key']=='private-key'
    assert 'private' not in repr(disclosure)


def test_invalid_driver_reports_unavailable_without_blocking_connector():
    resolver=Mock();resolver.organization={'config':{'setups':{'default':{'aac':{'provider':'ollama'}}}}}
    with patch('lamb.completions.org_config_resolver.OrganizationConfigResolver',return_value=resolver):
        result=effective_driver(SimpleNamespace(user={'email':'fixture@example.invalid'}))
    assert result['provider']=='' and 'administrator' in result['error']


def test_brief_appends_actual_provider_changes_without_rewriting_prefix(stores):
    rt=runtime(stores)
    client=SimpleNamespace(_lamb_aac_driver={'provider':'ollama','model':'same-model'})
    agent=SimpleNamespace(shell=SimpleNamespace(allowed_commands=set()),skill_state={},conversation=[{'role':'system','content':'Pinned'}],model='same-model',llm_client=client)
    attach_to_agent(agent,rt.store)
    assert 'provider: ollama' in agent.conversation[-1]['content']
    client._lamb_aac_driver={'provider':'openai','model':'same-model'}
    attach_to_agent(agent,rt.store)
    assert 'provider: openai' in agent.conversation[-1]['content']
    assert len(agent.conversation)==3 and agent.conversation[0]['content']=='Pinned'


@pytest.mark.parametrize('streaming', [False, True])
@pytest.mark.parametrize('provider,model,expected', [('openai','gpt-5.6-terra','none'),('openai','gpt-4o-mini',None),('ollama','gpt-5.6-terra',None)])
def test_tools_compatibility_scoped_to_openai_56(provider,model,expected,streaming):
    import asyncio
    from unittest.mock import AsyncMock
    from lamb.aac.agent.loop import AgentLoop
    class Stream:
        def __aiter__(self): return self
        async def __anext__(self): raise StopAsyncIteration
        async def close(self): pass
    result = Stream() if streaming else SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='OK',tool_calls=[]))])
    create=AsyncMock(return_value=result)
    client=SimpleNamespace(_lamb_aac_driver={'provider':provider},chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    agent=AgentLoop(shell=Mock(),llm_client=client,model=model)
    async def run():
        return [e async for e in agent._request_message([{'role':'user','content':'courses?'}],True,streaming)]
    asyncio.run(run())
    assert create.call_args.kwargs.get('reasoning_effort') == expected
    assert create.call_args.kwargs['tools']
