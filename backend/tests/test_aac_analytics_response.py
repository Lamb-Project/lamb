import asyncio
from unittest.mock import AsyncMock
import pytest

from lamb.aac.analytics_response import contract, violations, evidence_instruction
from tests.test_aac_legacy import agent, message, tool, turn

RESULT = {'success':True,'data':{'recipe':{'id':'grade-distribution'},'grade_released':None}}


@pytest.mark.parametrize('streaming',[False,True])
def test_network_evidence_guidance_preserves_peer_semantics(streaming):
    evidence={'success':True,'data':{'recipe':{'id':'forum-network'},'language':'ca'}}
    a,provider,shell=agent([message(tools=[tool()]),message('No prueba aislamiento social.')])
    a.skill_state={'ui_language':'es'}
    a._execute_tool=AsyncMock(return_value=evidence)
    assert asyncio.run(turn(a,streaming))=='No prueba aislamiento social.'
    guide=evidence_instruction(contract(evidence),a.skill_state)
    assert 'Reply in Spanish.' in guide and 'immediate parent' in guide
    assert 'not their sum' in guide and 'does not prove social isolation' in guide
    assert 'positions follow student IDs around a circle' in guide
    assert 'self-replies with self-criticism' in guide
    assert 'all visible authors' not in guide
    assert a._execute_tool.await_count==1
    assert '[Application analytics evidence guidance]' not in str(a.conversation)


@pytest.mark.parametrize('recipe',['forum-participation','forum-discussions'])
@pytest.mark.parametrize('streaming',[False,True])
def test_forum_evidence_gets_language_semantics_and_bounded_menu_repair(recipe,streaming):
    evidence={'success':True,'data':{'recipe':{'id':recipe},'language':'ca'}}
    assert contract(evidence)['recipe']==recipe
    bad='Dos discusiones sin respuestas públicas.\n¿Qué hacemos ahora?\n1. Actualizar'
    good='Dos discusiones sin respuestas públicas observadas; su resolución es desconocida.'
    a,provider,shell=agent([message(tools=[tool()]),message(bad),message(good)])
    a.skill_state={'ui_language':'es'}
    a._execute_tool=AsyncMock(return_value=evidence)
    assert asyncio.run(turn(a,streaming))==good
    assert a._execute_tool.await_count==1 and 'tools' not in provider.calls[-1]
    guidance=evidence_instruction(contract(evidence),a.skill_state)
    assert 'Reply in Spanish.' in guidance and 'not now' in guidance
    assert 'all visible authors and self-replies' in guidance
    assert 'do not invent identity mappings' in guidance
    assert '[Application analytics evidence guidance]' not in str(a.conversation)


def test_evidence_language_uses_effective_session_not_source_locale():
    evidence = {'recipe':'quiz-overview', 'language':'ca'}
    guide = evidence_instruction(evidence, {'ui_language':'ca',
        'response_language_policy':{'effective_language':'es'}})
    assert 'Reply in Spanish.' in guide and 'Reply in Catalan.' not in guide
    assert 'PERCENTAGE POINTS' in guide and 'not raw points' in guide
    assert 'not exemptions' in guide
    assert 'Reply in' not in evidence_instruction(evidence, {'ui_language':'untrusted text'})


@pytest.mark.parametrize('streaming', [False, True])
def test_quiz_guidance_follows_tool_evidence_without_rewriting_history(streaming):
    quiz = {'success':True, 'data':{'recipe':{'id':'quiz-overview'}, 'language':'ca'}}
    a, provider, shell = agent([message(tools=[tool()]), message('Cambio: 100 puntos porcentuales.')])
    a.skill_state = {'ui_language':'es'}
    a._execute_tool = AsyncMock(return_value=quiz)
    assert asyncio.run(turn(a, streaming)) == 'Cambio: 100 puntos porcentuales.'
    guide = provider.calls[-1]['messages'][-1]
    assert guide['role'] == 'user' and 'Reply in Spanish.' in guide['content']
    assert 'PERCENTAGE POINTS' in guide['content']
    assert '[Application analytics evidence guidance]' not in str(a.conversation)
    assert a._execute_tool.await_count == 1


@pytest.mark.parametrize('streaming', [False, True])
def test_quiz_saved_evidence_uses_bounded_menu_repair(streaming):
    quiz = {'success':True, 'data':{'recipe':{'id':'quiz-overview'}, 'attempt_policy':'all_finished'}}
    bad = 'Four finished attempts.\n**¿Qué hacemos ahora?**\n1. Refrescar'
    good = 'Four finished attempts; three scored attempts. No new collection.'
    assert violations(bad, contract(quiz))
    a, provider, shell = agent([message(tools=[tool()]), message(bad), message(good)])
    a._execute_tool = AsyncMock(return_value=quiz)
    assert asyncio.run(turn(a, streaming)) == good
    assert a._execute_tool.await_count == 1
    assert 'tools' not in provider.calls[-1]
    assert bad not in str(a.conversation)


@pytest.mark.parametrize('text', ['No son notas finales ni publicadas.', 'These marks are not yet published.',
                                'No són notes finals ni publicades.', 'Argitaratu gabe.'])
def test_observed_publication_claims_rejected(text):
    assert violations(text,contract(RESULT))


def test_uncertainty_and_requested_statistics_remain_valid():
    assert not violations('No se puede establecer si ya se han publicado. Media 50%.',contract(RESULT))
    assert not violations('Publication is unknown. 11 valid, 19 missing.',contract(RESULT))
    assert contract({'success':False,'data':RESULT['data']}) is None
    assert contract({'success':True,'data':{'recipe':{'id':'unknown'}}}) is None


@pytest.mark.parametrize('streaming',[False,True])
@pytest.mark.parametrize('cap',[1,5])
def test_repair_is_bounded_tool_free_and_never_streams_or_saves_rejected_draft(streaming,cap):
    bad='No son notas finales ni publicadas.\n¿Qué hacemos ahora?\n1. Otra cosa'
    good='La publicación es desconocida. Hay 11 notas válidas y 19 ausentes.'
    a,p,s=agent([message(tools=[tool()]),message(bad),message(good)],max_tool_rounds=cap)
    a._execute_tool=AsyncMock(return_value=RESULT)
    answer=asyncio.run(turn(a,streaming))
    assert answer==good
    assert a._execute_tool.await_count==1
    assert len(p.calls)==3 and 'tools' not in p.calls[-1]
    assert p.calls[-1]['messages'][-1]['role']=='user'
    assert p.calls[-1]['messages'][-2]=={'role':'assistant','content':bad}
    assert '[Application analytics response check]' not in str(a.conversation)
    assert not p.calls[-1].get('stream') and not p.calls[-2].get('stream')
    assert bad not in str(a.conversation)
    assert a.conversation[-1]['content']==answer


@pytest.mark.parametrize('streaming',[False,True])
def test_repeated_failure_is_explicit_not_an_invented_answer(streaming):
    bad='These marks are unpublished.'
    a,p,s=agent([message(tools=[tool()]),message(bad),message(bad)])
    a._execute_tool=AsyncMock(return_value=RESULT)
    answer=asyncio.run(turn(a,streaming))
    assert 'could not validate' in answer
    assert bad not in str(a.conversation)
    assert len(p.calls)==3


def test_repair_cannot_execute_provider_tool_calls():
    a,p,s=agent([message(tools=[tool()]),message('<<<CANVAS title="bad">>>'),message(tools=[tool()])])
    a._execute_tool=AsyncMock(return_value=RESULT)
    assert 'No additional action was executed' in asyncio.run(turn(a,True))
    assert a._execute_tool.await_count==1


def test_later_resource_result_does_not_erase_grade_constraint():
    a,p,s=agent([message(tools=[tool(ident='one'),tool(ident='two')]),
        message('These marks are unpublished.'),message('Publication is unknown.')])
    a._execute_tool=AsyncMock(side_effect=[RESULT,
        {'success':True,'data':{'recipe':{'id':'resource-reach'}}}])
    assert asyncio.run(turn(a,True))=='Publication is unknown.'
    assert a._execute_tool.await_count==2


@pytest.mark.parametrize('streaming',[False,True])
def test_empty_repair_is_explicit_failure(streaming):
    a,p,s=agent([message(tools=[tool()]),message('These marks are unpublished.'),message('')])
    a._execute_tool=AsyncMock(return_value=RESULT)
    answer=asyncio.run(turn(a,streaming))
    assert 'could not validate' in answer
    assert a.conversation[-1]['content']==answer
