"""Conversation scenarios: deterministic draws, durable scope, races and deletion."""
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from lamb.completions import prompt_filters as filters
from lamb.completions.filter_state import Conversation, migrate, resolve
from lamb.completions.conversation_bridge import seal, unseal, facade_conversation


def config(**changes):
    item = dict(id="client-random", type="random", enabled=True,
                target="system_prompt", run_on="conversation_start", options={})
    item.update(changes)
    return {"prompt_processor": "simple_augment", "prompt_filters": {"version": 1, "items": [item]}}


class Assistant(SimpleNamespace):
    def model_copy(self, update):
        return Assistant(**{**vars(self), **update})


def assistant(**changes):
    return Assistant(**{**dict(id=5, organization_id=9, system_prompt="Age {{RANDOM:25-70}}",
                                prompt_template="Raw {{RANDOM:1-2}} {user_input} {context}"), **changes})


def database(path, owi=False):
    prefix = "lamb_" if owi else "T_"
    with sqlite3.connect(path) as conn:
        name = "chat" if owi else "T_lamb_chats"
        conn.execute(f"CREATE TABLE {name} (id TEXT PRIMARY KEY, user_id TEXT, chat TEXT, assistant_id INTEGER, share_id TEXT)")
        migrate(conn.cursor(), prefix, owi=owi)
        conn.execute(f"INSERT INTO {name} VALUES ('a', '7', ?, 5, NULL)", (json.dumps({"history": {"messages": {}}}),))
    return prefix, Conversation("owi" if owi else "creator", "a", "7")


def execute(path, prefix, context, model=None, metadata=None, messages=None):
    with sqlite3.connect(path, timeout=10) as conn:
        return resolve(conn, prefix, context, model or assistant(), metadata if metadata is not None else config(),
                       {"messages": messages or [{"role": "user", "content": "Hello"}]})


def test_replacement_endpoints_negative_reverse_equal_and_independent_occurrences():
    text = "{{RANDOM:25-70}} {{RANDOM:25-70}} {{RANDOM: -9 - -2 }} {{RANDOM:5-1}} {{RANDOM:4-4}}"
    with patch.object(filters.secrets, "randbelow", side_effect=[0, 45, 7, 0, 0]) as draw:
        assert filters.random_integers(text, {}) == "25 70 -2 1 4"
        assert [c.args for c in draw.call_args_list] == [(46,), (46,), (8,), (5,), (1,)]
    assert filters.random_integers("unchanged", {}) == "unchanged"
    assert filters.random_integers("", {}) == ""


@pytest.mark.parametrize("text", ["{{RANDOM:a-b}}", "{{RANDOM:1-}}", "{{RANDOM:1-2}",
    "{{RANDOM:1000000000001-2}}", "{{RANDOM:1.5-3}}", "{{RANDOM:1-2}}" * 101, "x" * 100001])
def test_invalid_and_bounded_syntax(text):
    with pytest.raises(ValueError):
        filters.validate_definition(config(), text)


@pytest.mark.parametrize("changes", [{"type": "missing"}, {"target": "messages"}, {"run_on": "every_request"},
    {"enabled": "yes"}, {"options": {"code": "print(1)"}}, {"id": ""}])
def test_reject_invalid_definitions(changes):
    with pytest.raises(ValueError):
        filters.validate_definition(config(**changes), "plain")


def test_disabled_unknown_filter_preserved_and_incompatible_processor_rejected():
    assert filters.validate_definition(config(type="future", enabled=False), "plain")
    with pytest.raises(ValueError):
        filters.validate_definition({**config(), "prompt_processor": "ignores_system"}, "plain")
    assert filters.validate_definition({}, "{{RANDOM:broken}}") == []


def test_order_and_single_pass(monkeypatch):
    first = Mock(side_effect=lambda text, options: text.replace("one", "two"))
    second = Mock(side_effect=lambda text, options: text.replace("two", "one"))
    monkeypatch.setitem(filters.REGISTRY, "first", first)
    monkeypatch.setitem(filters.REGISTRY, "second", second)
    items = [config(type=name)["prompt_filters"]["items"][0] for name in ("first", "second")]
    assert filters.run_filters("one", items) == "one"
    first.assert_called_once(); second.assert_called_once()


@pytest.mark.parametrize("owi", [False, True])
def test_resume_retries_restart_edits_and_deletion(tmp_path, owi):
    path = tmp_path / "chat.db"
    prefix, context = database(path, owi)
    original = assistant()
    with patch.object(filters.secrets, "randbelow", return_value=5) as draw:
        assert execute(path, prefix, context, original).system_prompt == "Age 30"
        for _ in range(3):
            assert execute(path, prefix, context).system_prompt == "Age 30"
        assert execute(path, prefix, context, assistant(system_prompt="Changed"), {}).system_prompt == "Age 30"
        draw.assert_called_once()
    assert original.system_prompt == "Age {{RANDOM:25-70}}"
    with sqlite3.connect(path) as conn:
        conn.execute(f"DELETE FROM {'chat' if owi else 'T_lamb_chats'} WHERE id='a'")
        assert conn.execute(f"SELECT count(*) FROM {prefix}prompt_filter_states").fetchone()[0] == 0


def test_concurrent_initialization_draws_once(tmp_path):
    path = tmp_path / "chat.db"
    prefix, context = database(path)
    barrier = Barrier(8)
    def worker(_):
        barrier.wait()
        return execute(path, prefix, context).system_prompt
    with patch.object(filters.secrets, "randbelow", return_value=12) as draw, ThreadPoolExecutor(8) as pool:
        assert list(pool.map(worker, range(8))) == ["Age 37"] * 8
        draw.assert_called_once()


def test_ownership_assistant_and_organization_isolation(tmp_path):
    path = tmp_path / "chat.db"
    prefix, context = database(path)
    execute(path, prefix, context)
    for wrong_context, model in [(Conversation('creator', 'a', '8'), assistant()),
                                 (context, assistant(id=6)), (context, assistant(organization_id=10))]:
        with pytest.raises(HTTPException) as error:
            execute(path, prefix, wrong_context, model)
        assert error.value.status_code == 404


def test_new_chat_draws_again_and_native_fork_inherits(tmp_path):
    path = tmp_path / "chat.db"
    prefix, context = database(path, True)
    with patch.object(filters.secrets, "randbelow", side_effect=[3, 9]) as draw:
        assert execute(path, prefix, context).system_prompt == "Age 28"
        with sqlite3.connect(path) as conn:
            conn.execute("INSERT INTO chat VALUES ('fork', '7', ?, 5, NULL)", (json.dumps({"originalChatId": "a"}),))
            # Fork state is copied at insertion, even if its parent is deleted before the next turn.
            conn.execute("DELETE FROM chat WHERE id='a'")
            conn.execute("INSERT INTO chat VALUES ('new', '7', '{}', 5, NULL)")
        assert execute(path, prefix, Conversation("owi", "fork", "7")).system_prompt == "Age 28"
        assert execute(path, prefix, Conversation("owi", "new", "7")).system_prompt == "Age 34"
        assert draw.call_count == 2


def test_older_interview_requires_new_chat(tmp_path):
    path = tmp_path / "chat.db"
    prefix, context = database(path)
    with pytest.raises(HTTPException) as error:
        execute(path, prefix, context, messages=[{"role": "assistant", "content": "Already started"}])
    assert error.value.status_code == 409
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM T_prompt_filter_states").fetchone()[0] == 0


def test_shared_fork_inherits_only_a_current_public_share(tmp_path):
    path = tmp_path / 'shared.db'
    prefix, context = database(path, True)
    result = execute(path, prefix, context).system_prompt
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO chat VALUES ('shared', 'shared-a', '{}', 5, NULL)")
        conn.execute("UPDATE chat SET share_id='shared' WHERE id='a'")
        conn.execute("INSERT INTO chat VALUES ('fork', '8', ?, 5, NULL)", (json.dumps({'originalChatId': 'shared'}),))
        conn.execute("INSERT INTO chat VALUES ('forged', '8', ?, 5, NULL)", (json.dumps({'originalChatId': 'a'}),))
    assert execute(path, prefix, Conversation('owi', 'fork', '8')).system_prompt == result
    with pytest.raises(HTTPException):
        execute(path, prefix, Conversation('owi', 'forged', '8'))


def test_unfiltered_assistants_retain_edit_behavior(tmp_path):
    path = tmp_path / "chat.db"
    prefix, context = database(path)
    assert execute(path, prefix, context, metadata={}).system_prompt == assistant().system_prompt
    assert execute(path, prefix, context, assistant(system_prompt="new"), {}).system_prompt == "new"
    with pytest.raises(HTTPException) as error:
        execute(path, prefix, context)
    assert error.value.status_code == 409


def test_empty_owi_assistant_placeholder_is_a_new_chat(tmp_path):
    path = tmp_path / "chat.db"
    prefix, context = database(path, True)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE chat SET chat=?", (json.dumps({"history": {"messages": {
            "draft": {"role": "assistant", "content": ""}}}}),))
    assert "{{RANDOM" not in execute(path, prefix, context).system_prompt


def test_processor_only_receives_changed_system_prompt(tmp_path):
    from lamb.completions.pps.simple_augment import prompt_processor
    path = tmp_path / "chat.db"
    prefix, context = database(path)
    original = assistant()
    request = {"messages": [{"role": "user", "content": [{"type": "text", "text": "User {{RANDOM:1-2}}"},
                  {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]}]}
    rag = {"content": "Context {{RANDOM:3-4}}", "sources": []}
    before = copy.deepcopy((request, rag))
    resolved = execute(path, prefix, context, original)
    original.api_callback = resolved.api_callback = json.dumps({"capabilities": {"vision": True}})
    original.metadata = resolved.metadata = original.api_callback
    expected = prompt_processor(request, original, rag)
    actual = prompt_processor(request, resolved, rag)
    assert actual[0]["content"] != expected[0]["content"]
    assert actual[1:] == expected[1:]
    assert (request, rag) == before
    assert resolved.prompt_template == original.prompt_template


def test_signed_transport_bound_to_assistant_and_identity():
    token = seal("user", "chat", 5, "secret")
    assert unseal(token, 5, "secret") == Conversation("owi", "chat", "user")
    for value, model, secret in [(token + "x", 5, "secret"), (token, 6, "secret"), (token, 5, "wrong")]:
        with pytest.raises(HTTPException):
            unseal(value, model, secret)
    with patch('lamb.completions.conversation_bridge.time.time', return_value=10**12):
        with pytest.raises(HTTPException):
            unseal(token, 5, "secret")
    assert facade_conversation({"kind": "creator", "user_id": 8},
        {"lamb_conversation": token, "conversation_id": "own"}, 5, "secret") == Conversation("creator", "own", "8")
