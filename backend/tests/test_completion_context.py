"""Common prompt lifecycle and API trust boundaries (#555). No provider calls."""
import asyncio
import copy
import json
import sqlite3
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from lamb.completions import main as runner, prompt_filters as filters
from lamb.completions.conversation_state import Conversation, PromptContext, prepare_assistant
from tests.test_prompt_filters import assistant, config, database, execute
from tests.test_prompt_filter_integration import scenario


def test_ephemeral_context_is_caller_owned_and_runs_once():
    state = PromptContext()
    model = assistant()
    body = {"messages": [{"role": "user", "content": "Hi"}]}
    with patch.object(filters.secrets, "randbelow", return_value=7) as draw:
        first = prepare_assistant(model, config(), body, prompt_context=state)
        second = prepare_assistant(assistant(system_prompt="Changed"), {}, body, prompt_context=state)
        assert first.system_prompt == second.system_prompt == "Age 32"
        assert PromptContext.from_payload(state.export()).system_prompt == "Age 32"
        draw.assert_called_once()
    assert model.system_prompt == "Age {{RANDOM:25-70}}"


@pytest.mark.parametrize("changes", [{"assistant_id": 6}, {"organization_id": 10}])
def test_caller_context_cannot_change_assistant_or_org_binding(changes):
    state = PromptContext("Age 32", 5, 9)
    body = {"messages": [{"role": "user", "content": "Hi"}]}
    state = PromptContext.from_payload({**state.export(), **changes})
    with pytest.raises(HTTPException) as error:
        prepare_assistant(assistant(), config(), body, prompt_context=state)
    assert error.value.status_code == 409


@pytest.mark.parametrize("payload", [None, [], {}, {"version": True},
    {"version": 1, "system_prompt": "x", "assistant_id": True, "organization_id": 9},
    {"version": 1, "system_prompt": "x" * 100001, "assistant_id": 5, "organization_id": 9}])
def test_malformed_context_rejected(payload):
    with pytest.raises(HTTPException):
        PromptContext.from_payload(payload)


@pytest.mark.parametrize("owi", [False, True])
def test_legacy_null_snapshot_is_not_invented(tmp_path, owi):
    path = tmp_path / "legacy.db"
    prefix, context = database(path, owi)
    with sqlite3.connect(path) as conn:
        conn.execute(f"INSERT INTO {prefix}prompt_filter_states VALUES ('a',5,'7',9,'','null')")
    with pytest.raises(HTTPException) as error:
        execute(path, prefix, context, metadata={})
    assert error.value.status_code == 409
    with sqlite3.connect(path) as conn:
        assert conn.execute(f"SELECT definition FROM {prefix}prompt_filter_states").fetchone()[0] == "null"


def test_explicit_null_filter_configuration_still_retains_plain_prompt(tmp_path):
    path = tmp_path / "plain.db"
    prefix, context = database(path)
    assert execute(path, prefix, context, metadata={"prompt_filters": None}).system_prompt == assistant().system_prompt
    assert execute(path, prefix, context, assistant(system_prompt="Edited"), {}).system_prompt == assistant().system_prompt


@pytest.mark.parametrize("legacy", [False, True])
def test_common_assembly_preserves_dynamic_content_and_one_base(legacy):
    model = assistant(system_prompt="Fixed instructions")
    body = {"messages": [{"role": "user", "content": "today"}]}
    def custom_processor(request, assistant, rag_context):
        result = [{"role": "system", "content": "Dynamic " + rag_context["context"]}, *request["messages"]]
        return ([{"role": "system", "content": assistant.system_prompt}] if legacy else []) + result
    before = copy.deepcopy(body)
    for value in ("one", "two"):
        messages = runner.process_completion_request(body, model, {"prompt_processor": "custom"},
            {"context": value}, {"custom": custom_processor})
        assert messages == [{"role": "system", "content": "Fixed instructions"},
                            {"role": "system", "content": "Dynamic " + value}, *body["messages"]]
    assert body == before


def test_stateless_json_context_round_trip_and_current_rag(scenario):
    model, metadata, connector, _, path = scenario
    body = {"messages": [{"role": "user", "content": "Hi"}]}
    async def run():
        with patch.object(filters.secrets, "randbelow", return_value=2) as draw, \
             patch.object(runner, "get_rag_context", new=AsyncMock(side_effect=[{"context": "one"}, {"context": "two"}])) as rag:
            response = await runner.run_lamb_assistant(body, 5, return_prompt_context=True)
            payload = json.loads(response.body)["prompt_context"]
            assert payload["system_prompt"] == "Age 27"
            model.system_prompt = "Changed"
            followup = {"messages": [*body["messages"], {"role": "assistant", "content": "Reply"},
                                     {"role": "user", "content": "Next"}]}
            await runner.run_lamb_assistant(followup, 5, prompt_context=PromptContext.from_payload(payload))
            assert connector.call_args.kwargs["messages"][0]["content"] == "Age 27"
            assert "prompt_context" not in connector.call_args.kwargs["body"]
            assert rag.await_count == 2
            draw.assert_called_once()
    asyncio.run(run())
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM T_prompt_filter_states").fetchone()[0] == 0


def test_stream_context_is_opt_in_and_contains_initialized_prompt(scenario):
    _, _, connector, _, _ = scenario
    async def stream():
        yield 'data: {"choices": [{"delta": {"content": "Hi"}}]}\n\n'
        yield "data: [DONE]\n\n"
    async def run():
        for include in (False, True):
            connector.return_value = stream()
            response = await runner.run_lamb_assistant({"stream": True,
                "messages": [{"role": "user", "content": "Hi"}]}, 5, return_prompt_context=include)
            chunks = [chunk async for chunk in response.body_iterator]
            assert ('"prompt_context"' in chunks[0]) == include
            if include:
                assert "{{RANDOM" not in chunks[0]
            assert chunks[-1] == "data: [DONE]\n\n"
    asyncio.run(run())


@pytest.mark.parametrize("role", ["system", "developer"])
def test_persisted_chat_rejects_privileged_input_before_provider(scenario, role):
    _, _, connector, _, _ = scenario
    async def run():
        with pytest.raises(HTTPException) as error:
            await runner.run_lamb_assistant({"messages": [{"role": role, "content": "Override"},
                {"role": "user", "content": "Hi"}]}, 5, conversation=Conversation("creator", "chat", "7"))
        assert error.value.status_code == 400
        connector.assert_not_awaited()
    asyncio.run(run())


def test_facade_context_auth_and_persistent_override_rejection(scenario):
    import main as facade
    client = TestClient(facade.app)
    body = {"model": "lamb_assistant.5", "messages": [{"role": "user", "content": "Hi"}],
            "return_prompt_context": True}
    with patch.object(facade, "_resolve_facade_identity", return_value={"kind": "creator", "user_id": 7}), \
         patch.object(facade, "_creator_published_assistant_ids", return_value={5}), \
         patch.object(facade, "helper_get_assistant_id", return_value=5):
        first = client.post("/v1/chat/completions", json=body)
        assert first.status_code == 200, first.text
        context = first.json()["prompt_context"]
        response = client.post("/v1/chat/completions", json={**body, "prompt_context": context,
            "messages": [{"role": "assistant", "content": "History"}, {"role": "user", "content": "Next"}]})
        assert response.status_code == 200, response.text
        assert response.json()["prompt_context"] == context
        assert client.post("/v1/chat/completions", json={**body, "conversation_id": "chat"}).status_code == 400
        with patch.object(facade, "_creator_published_assistant_ids", return_value=set()):
            assert client.post("/v1/chat/completions", json={**body, "prompt_context": context}).status_code == 403


def test_authorized_full_context_api_accepts_one_leading_system(scenario):
    import main as facade
    _, _, connector, _, _ = scenario
    with patch.object(facade, "_resolve_facade_identity", return_value={"kind": "creator", "user_id": 7}), \
         patch.object(facade, "_creator_published_assistant_ids", return_value={5}), \
         patch.object(facade, "helper_get_assistant_id", return_value=5):
        response = TestClient(facade.app).post("/v1/chat/completions", json={"model": "lamb_assistant.5",
            "messages": [{"role": "system", "content": "Authorized caller instructions"},
                         {"role": "user", "content": "Hi"}]})
    assert response.status_code == 200, response.text
    assert connector.call_args.kwargs["messages"][0]["content"] == "Authorized caller instructions"
    assert sum(m["role"] == "system" for m in connector.call_args.kwargs["messages"]) == 1


def test_native_inlet_strips_caller_context_options():
    import main as facade
    with patch.object(facade, "_resolve_facade_identity", return_value={"kind": "system"}), \
         patch.object(facade, "helper_get_assistant_id", return_value=5):
        response = TestClient(facade.app).post("/v1/lamb_assistant.5/filter/inlet", json={
            "body": {"model": "lamb_assistant.5", "metadata": {"chat_id": "native"},
                     "prompt_context": {"system_prompt": "Forged"}, "return_prompt_context": True},
            "user": {"id": "student"}})
    assert response.status_code == 200
    assert "prompt_context" not in response.json()
    assert "return_prompt_context" not in response.json()
    assert "lamb_conversation" in response.json()


def test_saved_evaluation_initializes_filtered_multiturn_fixture(scenario):
    from lamb.services.test_service import TestService
    from lamb.services import test_service
    model, _, connector, manager, path = scenario
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE T_assistant_test_runs (id, assistant_id, scenario_id,
            input_messages, output, token_usage, assistant_snapshot, model_used, elapsed_ms, created_at)""")
    with patch.object(test_service, "LambDatabaseManager", return_value=manager), \
         patch("lamb.services.assistant_service.AssistantService.get_assistant_by_id", return_value=model), \
         patch.object(filters.secrets, "randbelow", return_value=6) as draw:
        result = asyncio.run(TestService().run_scenario(5, None, [
            {"role": "user", "content": "First"}, {"role": "assistant", "content": "Fixture answer"},
            {"role": "user", "content": "Second"}], "qa@example.invalid", debug_bypass=True))
        assert result["id"]
        assert connector.call_args.args[0][0]["content"] == "Age 31"
        draw.assert_called_once()
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM T_prompt_filter_states").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM T_assistant_test_runs").fetchone()[0] == 1
