"""Saved pre-0.9 conversations keep their transcript and initialize plain prompts once."""
import asyncio
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from lamb.completions import main as runner
from lamb.completions.conversation_state import Conversation
from tests.test_prompt_filters import assistant, config, database, execute
from tests.test_prompt_filter_integration import scenario


HISTORY = {"history": {"messages": {
    "u": {"role": "user", "content": "My project is about bees."},
    "a": {"role": "assistant", "content": "Tell me about the hive."}}}}


@pytest.mark.parametrize("owi", [False, True])
@pytest.mark.parametrize("sentinel", [False, True])
def test_legacy_chat_initializes_once_and_preserves_history(tmp_path, owi, sentinel):
    path = tmp_path / "legacy.db"
    prefix, context = database(path, owi)
    table = "chat" if owi else "T_lamb_chats"
    transcript = json.dumps(HISTORY)
    with sqlite3.connect(path) as conn:
        conn.execute(f"UPDATE {table} SET chat=?", (transcript,))
        if sentinel:
            conn.execute(f"INSERT INTO {prefix}prompt_filter_states VALUES ('a',5,'7',9,'','null')")
    assert execute(path, prefix, context, assistant(system_prompt="Current instructions"), {}).system_prompt == "Current instructions"
    # Each execute opens a new connection, including after the assistant has changed.
    assert execute(path, prefix, context, assistant(system_prompt="Later instructions"), {}).system_prompt == "Current instructions"
    with sqlite3.connect(path) as conn:
        assert conn.execute(f"SELECT chat FROM {table}").fetchone()[0] == transcript
        assert conn.execute(f"SELECT system_prompt, definition FROM {prefix}prompt_filter_states").fetchall() == [
            ("Current instructions", json.dumps({"version": 1, "items": []}))]


@pytest.mark.parametrize("owi", [False, True])
def test_concurrent_legacy_continuations_agree(tmp_path, owi):
    path = tmp_path / "concurrent.db"
    prefix, context = database(path, owi)
    barrier = Barrier(6)
    def worker(index):
        barrier.wait()
        return execute(path, prefix, context, assistant(system_prompt=f"Revision {index}"), {},
                       [{"role": "assistant", "content": "Previous reply"}]).system_prompt
    with ThreadPoolExecutor(6) as pool:
        prompts = list(pool.map(worker, range(6)))
    assert len(set(prompts)) == 1
    with sqlite3.connect(path) as conn:
        assert conn.execute(f"SELECT count(*) FROM {prefix}prompt_filter_states").fetchone()[0] == 1


@pytest.mark.parametrize("sentinel", [False, True])
def test_legacy_owi_fork_respects_missing_random_scenario(tmp_path, sentinel):
    path = tmp_path / "fork.db"
    prefix, _ = database(path, True)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE chat SET chat=?", (json.dumps(HISTORY),))
        if sentinel:
            conn.execute("INSERT INTO lamb_prompt_filter_states VALUES ('a',5,'7',9,'','null')")
        conn.execute("INSERT INTO chat VALUES ('fork','7',?,5,NULL)", (json.dumps({"originalChatId": "a"}),))
    context = Conversation("owi", "fork", "7")
    with pytest.raises(HTTPException) as error:
        execute(path, prefix, context, metadata=config())
    assert error.value.status_code == 409
    assert execute(path, prefix, context, assistant(system_prompt="Current"), {}).system_prompt == "Current"


@pytest.mark.parametrize("sentinel", [False, True])
def test_legacy_state_does_not_bypass_ownership(tmp_path, sentinel):
    path = tmp_path / "ownership.db"
    prefix, context = database(path)
    if sentinel:
        with sqlite3.connect(path) as conn:
            conn.execute("INSERT INTO T_prompt_filter_states VALUES ('a',5,'7',9,'','null')")
    for bad_context, model in [(Conversation("creator", "a", "other"), assistant()),
                               (context, assistant(id=6))]:
        with pytest.raises(HTTPException) as error:
            execute(path, prefix, bad_context, model, {})
        assert error.value.status_code == 404
    if sentinel:
        with pytest.raises(HTTPException) as error:
            execute(path, prefix, context, assistant(organization_id=10), {})
        assert error.value.status_code == 404


def test_completion_receives_all_old_messages(scenario):
    model, metadata, connector, _, path = scenario
    metadata.pop("prompt_filters")
    model.system_prompt = "Continue helping with the project."
    body = {"messages": [*HISTORY["history"]["messages"].values(),
                          {"role": "user", "content": "What was my project about?"}]}
    before = copy.deepcopy(body)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE T_lamb_chats SET chat=?", (json.dumps(HISTORY),))
    response = asyncio.run(runner.run_lamb_assistant(body, 5, conversation=Conversation("creator", "chat", "7")))
    assert response.status_code == 200
    sent = connector.call_args.kwargs["messages"]
    assert sent[0]["content"] == model.system_prompt
    assert [(m["role"], m["content"].strip()) for m in sent[1:]] == [(m["role"], m["content"]) for m in body["messages"]]
    assert body == before
