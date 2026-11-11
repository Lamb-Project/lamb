"""Filter authoring must preserve IDs and other metadata; previews are samples."""
import json
import pytest
from typer.testing import CliRunner
from lamb_cli.main import app

runner = CliRunner()
CHAIN = {"version": 1, "items": [
    {"id": "first", "type": "future", "enabled": False, "target": "system_prompt", "run_on": "conversation_start", "options": {}},
    {"id": "stable", "type": "random", "enabled": True, "target": "system_prompt", "run_on": "conversation_start", "options": {}}]}
CURRENT = {"name": "Interview", "system_prompt": "Age {{RANDOM:25-70}}", "metadata": json.dumps({
    "connector": "bypass", "llm": "debug-bypass", "prompt_processor": "simple_augment", "prompt_filters": CHAIN, "rubric_id": "keep"})}


def test_create_random(httpx_mock, mock_token):
    httpx_mock.add_response(json={"assistant_id": 42})
    r = runner.invoke(app, ["assistant", "create", "Interview", "--connector", "bypass", "--llm", "debug-bypass", "--random-filter", "--system-prompt", "Age {{RANDOM:25-70}}"])
    assert r.exit_code == 0, r.output
    body = json.loads(httpx_mock.get_request().content)
    item = json.loads(body["metadata"])["prompt_filters"]["items"][0]
    assert item["type"] == "random" and item["enabled"] is True and item["run_on"] == "conversation_start"
    assert body["system_prompt"] == "Age {{RANDOM:25-70}}"


@pytest.mark.parametrize("args,expected", [(["--no-random-filter"], False), (["--random-filter"], True), (["--llm", "new-model"], True)])
def test_update_preserves_chain_and_other_fields(httpx_mock, mock_token, args, expected):
    httpx_mock.add_response(json=CURRENT)
    httpx_mock.add_response(json={"message": "Updated"})
    r = runner.invoke(app, ["assistant", "update", "42", *args])
    assert r.exit_code == 0, r.output
    body = json.loads(httpx_mock.get_requests()[-1].content)
    md = json.loads(body["metadata"])
    assert md["rubric_id"] == "keep"
    assert [x["id"] for x in md["prompt_filters"]["items"]] == ["first", "stable"]
    assert md["prompt_filters"]["items"][1]["enabled"] is expected
    assert md["prompt_filters"]["items"][0] == CHAIN["items"][0]


@pytest.mark.parametrize("definition", ["null", json.dumps({"version": 1, "items": list(reversed(CHAIN["items"]))})])
def test_replace_or_clear_chain(httpx_mock, mock_token, definition):
    httpx_mock.add_response(json=CURRENT)
    httpx_mock.add_response(json={"message": "Updated"})
    r = runner.invoke(app, ["assistant", "update", "42", "--prompt-filters", definition])
    assert r.exit_code == 0, r.output
    md = json.loads(json.loads(httpx_mock.get_requests()[-1].content)["metadata"])
    assert md["prompt_filters"] == json.loads(definition)
    assert md["rubric_id"] == "keep"


@pytest.mark.parametrize("args", [["--prompt-filters", "invalid"], ["--prompt-filters", "[]"], ["--prompt-filters", "null", "--random-filter"]])
def test_invalid_definition_never_writes(httpx_mock, mock_token, args):
    httpx_mock.add_response(json=CURRENT)
    r = runner.invoke(app, ["assistant", "update", "42", *args])
    assert r.exit_code != 0
    assert all(req.method == "GET" for req in httpx_mock.get_requests())


def test_preview_and_display(httpx_mock, mock_token):
    httpx_mock.add_response(json=CURRENT)
    httpx_mock.add_response(json={"system_prompt": "Age 42"})
    r = runner.invoke(app, ["assistant", "preview-filters", "42", "-o", "json"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["system_prompt"] == "Age 42"
    req = httpx_mock.get_requests()[-1]
    assert req.url.path == "/creator/assistant/prompt-filters/preview"
    assert json.loads(req.content)["metadata"]["prompt_filters"] == CHAIN
    httpx_mock.add_response(json=CURRENT)
    r = runner.invoke(app, ["assistant", "get", "42", "-o", "json"])
    assert json.loads(r.output)["prompt_filters"] == CHAIN
