import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from tests.test_aac_legacy import agent, tool, message, turn
from lamb.aac.approvals import explain_pending_action, small_model_sentence
from lamb.aac.language import confirmation_fallback
from lamb.aac.authorization import ActionAuthorizer
from lamb.moodle.contract import command_specs, CURATED_WRITES
from lamb.moodle.document_contract import document_specs
from lamb.moodle.task_contract import task_specs


def test_all_registered_moodle_reads_auto_writes_ask_and_unknown_denied():
    authorizer = ActionAuthorizer()
    for key, spec in {**command_specs(), **document_specs(), **task_specs()}.items():
        assert authorizer.check('moodle.' + key) == spec.policy
    for key in CURATED_WRITES | {'import.file', 'import.page', 'import.book', 'import.folder', 'import.refresh'}:
        assert authorizer.check('moodle.' + key) == 'ask'
    assert authorizer.check('moodle.call') == 'never'
    assert authorizer.check('moodle.forum.delete') == 'never'


def test_read_commands_execute_without_confirmation_even_with_translation():
    async def run():
        for command in ['moodle course list', 'moodle forum posts 42', 'moodle folder status batch',
                        'moodle import list', 'moodle sync 10 --section forums']:
            a, _, shell = agent([])
            a.skill_state = {'translation_interpretations': [{'term': 'forum'}]}
            a.required_skill = lambda *args: None
            result = await a._execute_tool(tool(command))
            assert not result.get('awaiting_user_confirmation') and a.pending_action is None
            shell.execute.assert_awaited_once_with(command)
    asyncio.run(run())


def test_basic_and_advanced_preserve_one_exact_approval_and_cache_prefix():
    async def run():
        for streaming in (False, True):
            command = 'lamb assistant update 97 --description "New description"'
            a, provider, shell = agent([message('Already saved!', [tool(command)]), message('Saved after approval.')])
            a.skill_state = {'ui_language': 'en', 'response_language_policy': {'effective_language': 'es'}}
            a.required_skill = lambda *args: None
            a.approval_owner = 'owner@test'
            before = a.system_prompt
            with patch('lamb.aac.approvals.small_model_sentence', new=AsyncMock(return_value={
                    'text': 'Si lo apruebas, cambiaré la descripción del asistente 97.', 'provider': 'openai', 'model': 'small'})) as summarize:
                answer = await turn(a, streaming, 'Change the description')
                assert 'Si lo apruebas' in answer and 'New description' in answer
                assert command not in answer and 'Already saved!' not in answer
                assert a.pending_action['command'] == command
                snapshot = copy.deepcopy(a.conversation)
                await explain_pending_action(a)
                assert summarize.await_count == 1 and summarize.call_args.args[1] == 'es'
                assert a.conversation == snapshot and a.system_prompt == before
                a.approval_preferences = {'advanced_mode': True}
                assert command in confirmation_fallback(a)
                shell.execute.assert_not_awaited()
                await turn(a, streaming, 'sí')
                shell.execute.assert_awaited_once_with(command)
                assert a.pending_action is None and summarize.await_count == 1
    asyncio.run(run())


def test_summary_failure_never_loses_exact_values_or_retries():
    async def run():
        a, _, shell = agent([])
        a.approval_owner = 'owner@test'
        command = 'moodle forum reply --post-id 7 --message "Exact text to publish"'
        await a._execute_tool(tool(command))
        with patch('lamb.aac.approvals.small_model_sentence', new=AsyncMock(side_effect=TimeoutError)) as summarize:
            await explain_pending_action(a)
            await explain_pending_action(a)
            assert summarize.await_count == 1
        answer = confirmation_fallback(a)
        assert 'Exact text to publish' in answer and '7' in answer and command not in answer
        assert a.pending_action['command'] == command
        shell.execute.assert_not_awaited()
    asyncio.run(run())


def test_auxiliary_call_uses_only_org_fast_model_no_tools_or_conversation():
    async def run():
        resolver = SimpleNamespace(get_small_fast_model_config=lambda: {'provider': 'openai', 'model': 'gpt-5.6-terra'},
            get_provider_config=lambda p: {'enabled': True, 'api_key': 'fixture', 'base_url': 'https://fixture.test/v1'})
        create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='If approved, I will update assistant 97.', tool_calls=None))]))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        context = AsyncMock(); context.__aenter__.return_value = client
        with patch('lamb.completions.org_config_resolver.OrganizationConfigResolver', return_value=resolver), patch('openai.AsyncOpenAI', return_value=context):
            result = await small_model_sentence('owner@test', 'es', {'action': 'assistant.update', 'id': 97})
        call = create.call_args.kwargs
        assert call['model'] == result['model'] == 'gpt-5.6-terra'
        assert call['reasoning_effort'] == 'none' and 'tools' not in call
        assert len(call['messages']) == 2 and 'Spanish' in call['messages'][0]['content']
        context.__aexit__.assert_awaited_once()
    asyncio.run(run())
