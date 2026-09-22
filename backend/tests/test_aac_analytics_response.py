import asyncio
from unittest.mock import AsyncMock
import pytest

from lamb.aac.analytics_response import contract, violations
from tests.test_aac_legacy import agent, message, tool, turn

RESULT = {'success':True,'data':{'recipe':{'id':'grade-distribution'},'grade_released':None}}


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
