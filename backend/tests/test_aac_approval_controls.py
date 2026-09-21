import asyncio
import copy
import pytest
from fastapi import HTTPException
from tests.test_aac_legacy import agent, tool, message
from lamb.aac.approval_controls import card, validate_decision
from lamb.aac.approvals import render_details
from lamb.aac.session_guidance import browser_session


def test_basic_assistant_review_hides_implementation_but_keeps_purpose_and_sources():
    action = {'command': '''lamb assistant create Tutor --description "Tutor per a doctorands" --system-prompt "PRIVATE_CONFIGURATION" --connector openai --llm MODEL --prompt-processor simple_augment --rag-processor simple_rag --rag-collections 18 --prompt-template "Context: {context} {user_input}"'''}
    basic = render_details(action, 'ca', False)
    assert 'Tutor per a doctorands' in basic and '18' in basic and 'Propòsit' in basic
    for hidden in ['PRIVATE_CONFIGURATION', 'openai', 'MODEL', 'simple_augment', 'simple_rag', 'lamb assistant create']:
        assert hidden not in basic
        assert hidden in render_details(action, 'ca', True)
    assert "l'apartat" in render_details({'command': '''lamb kb create Notes --description "l'apartat"'''}, 'ca', False)


@pytest.mark.parametrize('streaming', [True, False])
def test_one_button_executes_exact_action_once_and_replay_is_stale(streaming):
    async def run():
        command = 'lamb kb create "Course readings"'
        a, _, shell = agent([message('', [tool(command)]), message('Created.')])
        a.required_skill = lambda *args: None
        a.skill_state = {'ui_language': 'ca'}
        if streaming:
            events = [e async for e in a.chat_stream('Crea la base de coneixement')]
            control = [e['approval'] for e in events if isinstance(e, dict) and e.get('status') == 'approval'][0]
        else:
            await a.chat('Crea la base de coneixement')
            control = card(a.pending_action, a.skill_state)
        assert control['approve_label'] == 'Crear'
        shell.execute.assert_not_awaited()
        body = {'approval': {'action_id': control['action_id'], 'decision': 'approve'}}
        a.approval_decision = validate_decision({'pending_action': a.pending_action}, body)
        await a.chat('Crear')  # Not a yes/no word: only the validated control grants approval.
        shell.execute.assert_awaited_once_with(command)
        with pytest.raises(HTTPException) as exc:
            validate_decision({'pending_action': a.pending_action}, body)
        assert exc.value.status_code == 409
    asyncio.run(run())


def test_stale_changed_and_foreign_proposals_are_not_approved():
    action = {'nonce': 'one', 'command': 'lamb kb create X', 'moodle_review': {'files': [1]}}
    body = {'approval': {'action_id': card(action)['action_id'], 'decision': 'approve'}}
    for altered in [None, dict(action, nonce='two'), dict(action, command='lamb kb create Y'), dict(action, moodle_review={'files':[2]})]:
        with pytest.raises(HTTPException) as exc:
            validate_decision({'pending_action': altered}, body)
        assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        validate_decision({'pending_action': action}, {'approval': {'action_id': 'x', 'decision': 'perhaps'}})
    assert exc.value.status_code == 400


def test_edit_replaces_proposal_without_execution_and_cancel_executes_nothing():
    async def run():
        old, new = 'lamb kb create Old', 'lamb kb create New'
        a, _, shell = agent([message('', [tool(new)]), message('Cancelled.')])
        a.required_skill = lambda *args: None
        await a._execute_tool(tool(old))
        original = copy.deepcopy(a.pending_action)
        a.approval_decision = 'edit'
        await a.chat('Use the name New')
        assert a.pending_action['command'] == new
        assert card(original)['action_id'] != card(a.pending_action)['action_id']
        a.approval_decision = 'reject'
        await a.chat('Cancel·lar')
        assert a.pending_action is None
        shell.execute.assert_not_awaited()
    asyncio.run(run())


def test_browser_resumes_current_card_without_exporting_command_or_replaying_it():
    session = {'pending_action': {'command': 'lamb kb create Secret', 'nonce': 'one'},
               'conversation': [{'role': 'assistant', 'content': 'Review'}], 'skill_info': {'ui_language': 'ca'}}
    before = copy.deepcopy(session)
    visible = browser_session(session)
    assert 'pending_action' not in visible and visible['approval']['approve_label'] == 'Aprovar'
    assert 'command' not in visible['approval'] and session == before


def test_routes_reject_stale_decisions_before_building_an_agent():
    from tests.test_aac_router import LifecycleTests
    from lamb.aac import router
    from unittest.mock import AsyncMock, patch
    async def run():
        fixture = LifecycleTests()
        for endpoint in (router.send_message, router.send_message_stream):
            _, manager, request, auth = fixture.fixture()
            request.json.return_value = {'message': 'Crear', 'approval': {'action_id': 'stale', 'decision': 'approve'}}
            with patch.object(router, 'AACSessionManager', return_value=manager), patch.object(router, '_prepare_agent_and_message', AsyncMock()) as build:
                with pytest.raises(HTTPException) as exc:
                    await endpoint('stale-approval-fixture', request, auth)
                assert exc.value.status_code == 409
                build.assert_not_awaited()
    asyncio.run(run())


def test_browser_review_uses_buttons_without_a_second_text_confirmation_prompt():
    from lamb.aac.language import confirmation_fallback
    a, _, _ = agent([])
    a.pending_action = {'command': 'lamb kb create Notes'}
    a.skill_state = {'ui_language': 'ca'}
    assert 'Respon sí o no' in confirmation_fallback(a)
    a.interactive_approvals = True
    text = confirmation_fallback(a)
    assert 'Notes' in text and 'Respon sí o no' not in text
