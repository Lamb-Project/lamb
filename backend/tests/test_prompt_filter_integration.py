"""Verify the actual completion runner and HTTP transport before the connector boundary."""
import asyncio
import json
import sqlite3
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from lamb.completions import main as runner, prompt_filters as filters
from lamb.completions.pps.simple_augment import prompt_processor
from lamb.completions.filter_state import Conversation, migrate
from lamb.lamb_classes import Assistant
from tests.test_prompt_filters import config


@pytest.fixture
def scenario(tmp_path):
    path = tmp_path / 'integration.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE T_lamb_chats (id TEXT, user_id INTEGER, assistant_id INTEGER, chat TEXT)')
        conn.execute("INSERT INTO T_lamb_chats VALUES ('chat', 7, 5, '{}')")
        migrate(conn.cursor(), 'T_')
    model = Assistant(id=5, organization_id=9, name='Interview', description='', owner='qa@example.invalid',
        api_callback=json.dumps(config()), system_prompt='Age {{RANDOM:25-70}}', prompt_template='{user_input}',
        pre_retrieval_endpoint='', post_retrieval_endpoint='', RAG_endpoint='', RAG_Top_k=3, RAG_collections='')
    metadata = {**config(), 'connector': 'bypass', 'llm': 'test', 'rag_processor': 'no_rag'}
    connector = AsyncMock(return_value={'choices': [{'message': {'role': 'assistant', 'content': 'hello'}}]})
    manager = N(table_prefix='T_', get_connection=lambda: sqlite3.connect(path))
    with patch.object(runner, 'get_assistant_details', return_value=model), \
         patch.object(runner, 'resolve_completion_config', return_value=metadata), \
         patch.object(runner, 'load_and_validate_plugins', return_value=({'simple_augment': prompt_processor}, {'bypass': connector}, {})), \
         patch.object(runner, 'get_rag_context', new=AsyncMock(return_value=None)), \
         patch.object(runner, 'maybe_route_non_streaming_task', new=AsyncMock(return_value=None)), \
         patch('lamb.database_manager.LambDatabaseManager', return_value=manager):
        yield model, metadata, connector, manager, path


def test_runner_reuses_scenario_and_preserves_multimodal_request(scenario):
    model, metadata, connector, _, _ = scenario
    body = {'messages': [{'role': 'user', 'content': 'Question {{RANDOM:1-2}}'}]}
    async def run():
        with patch.object(filters.secrets, 'randbelow', return_value=4) as draw:
            for _ in range(3):
                response = await runner.run_lamb_assistant(body, 5, conversation=Conversation('creator', 'chat', '7'))
                assert response.status_code == 200
                assert connector.call_args.kwargs['messages'][0]['content'] == 'Age 29'
                assert connector.call_args.kwargs['messages'][-1]['content'].strip() == 'Question {{RANDOM:1-2}}'
            metadata.pop('prompt_filters')
            model.system_prompt = 'Teacher changed the template'
            await runner.run_lamb_assistant(body, 5, conversation=Conversation('creator', 'chat', '7'))
            assert connector.call_args.kwargs['messages'][0]['content'] == 'Age 29'
            draw.assert_called_once()
    asyncio.run(run())


def test_missing_continuation_and_failed_storage_never_contact_connector(scenario):
    _, _, connector, manager, _ = scenario
    body = {'messages': [{'role': 'assistant', 'content': 'Previous answer'}, {'role': 'user', 'content': 'Hi'}]}
    async def run():
        with pytest.raises(HTTPException) as missing:
            await runner.run_lamb_assistant(body, 5)
        assert missing.value.status_code == 409
        manager.get_connection = lambda: None
        with pytest.raises(HTTPException) as unavailable:
            await runner.run_lamb_assistant(body, 5, conversation=Conversation('creator', 'chat', '7'))
        assert unavailable.value.status_code == 503
        connector.assert_not_awaited()
    asyncio.run(run())


def test_auxiliary_task_does_not_create_state(scenario):
    _, _, _, _, path = scenario
    asyncio.run(runner.run_lamb_assistant({'metadata': {'task': 'title_generation'},
        'messages': [{'role': 'user', 'content': 'Title'}]}, 5))
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT count(*) FROM T_prompt_filter_states').fetchone()[0] == 0


def test_facade_preserves_verified_conversation_and_multimodal_content():
    import main as facade
    from fastapi.responses import Response
    completion = AsyncMock(return_value=Response(json.dumps({'choices': []}), media_type='application/json'))
    messages = [{'role': 'user', 'content': [{'type': 'text', 'text': 'Hi'},
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,abc'}}]}]
    with patch.object(facade, '_resolve_facade_identity', return_value={'kind': 'creator', 'user_id': 7}), \
         patch.object(facade, '_creator_published_assistant_ids', return_value={5}), \
         patch.object(facade, 'helper_get_assistant_id', return_value=5), \
         patch.object(facade, 'run_lamb_assistant', completion):
        response = TestClient(facade.app).post('/v1/chat/completions', json={
            'model': 'lamb_assistant.5', 'messages': messages, 'conversation_id': 'chat', 'stream': False})
    assert response.status_code == 200, response.text
    assert completion.call_args.kwargs['conversation'] == Conversation('creator', 'chat', '7')
    assert completion.call_args.kwargs['request']['messages'] == messages


def test_owi_pipeline_signs_identity_and_rejects_creator_keys():
    import main as facade
    from lamb.completions.conversation_bridge import unseal
    body = {'model': 'lamb_assistant.5', 'metadata': {'chat_id': 'native-chat'}, 'lamb_conversation': 'forged'}
    client = TestClient(facade.app)
    with patch.object(facade, '_resolve_facade_identity', return_value={'kind': 'system'}), \
         patch.object(facade, 'helper_get_assistant_id', return_value=5):
        response = client.post('/v1/lamb_assistant.5/filter/inlet', json={'body': body, 'user': {'id': 'student'}})
    assert response.status_code == 200
    assert unseal(response.json()['lamb_conversation'], 5, facade.config.API_KEY) == Conversation('owi', 'native-chat', 'student')
    with patch.object(facade, '_resolve_facade_identity', return_value={'kind': 'creator', 'user_id': 7}):
        assert client.post('/v1/lamb_assistant.5/filter/inlet', json={'body': body}).status_code == 403
