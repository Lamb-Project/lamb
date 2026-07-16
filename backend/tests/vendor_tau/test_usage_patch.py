"""Tests for the LAMB usage patch on the vendored tau provider layer.

The patch (see lamb/_vendor/tau/VENDORED.md, modification 4) captures the
token-usage payload that upstream requests but drops, and emits it on
ProviderResponseEndEvent. These tests feed the two stream parsers raw wire
chunks — no network, no provider.
"""

import json

from lamb._vendor.tau.tau_ai.events import ProviderResponseEndEvent, TokenUsage
from lamb._vendor.tau.tau_ai.openai_compatible import (
    _ChatStreamParser,
    _ResponsesStreamParser,
)


def _end_event(events):
    ends = [e for e in events if isinstance(e, ProviderResponseEndEvent)]
    assert len(ends) == 1
    return ends[0]


def _chat_chunk(**kwargs):
    return json.dumps(kwargs)


class TestChatCompletionsUsage:
    def test_usage_chunk_with_empty_choices_is_captured(self):
        parser = _ChatStreamParser()
        parser.feed(_chat_chunk(choices=[{"delta": {"content": "hola"}}]))
        parser.feed(_chat_chunk(choices=[{"delta": {}, "finish_reason": "stop"}]))
        # OpenAI sends the usage chunk last, with an empty choices array —
        # exactly the shape upstream's first-choice guard used to drop.
        parser.feed(_chat_chunk(
            choices=[],
            usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        ))
        end = _end_event(parser.finalize())
        assert end.usage == TokenUsage(
            prompt_tokens=11, completion_tokens=7, total_tokens=18)

    def test_no_usage_chunk_yields_none(self):
        parser = _ChatStreamParser()
        parser.feed(_chat_chunk(choices=[{"delta": {"content": "hi"}}]))
        assert _end_event(parser.finalize()).usage is None

    def test_malformed_usage_is_telemetry_not_failure(self):
        parser = _ChatStreamParser()
        parser.feed(_chat_chunk(choices=[{"delta": {"content": "x"}}]))
        parser.feed(_chat_chunk(choices=[], usage={"prompt_tokens": "not-a-number"}))
        end = _end_event(parser.finalize())  # must not raise
        assert end.usage is None
        assert end.message.content == "x"


class TestResponsesApiUsage:
    def test_terminal_event_usage_is_captured(self):
        parser = _ResponsesStreamParser()
        parser.feed(json.dumps({
            "type": "response.output_text.delta", "delta": "hola"}))
        parser.feed(json.dumps({
            "type": "response.completed",
            "response": {"status": "completed",
                         "usage": {"input_tokens": 21, "output_tokens": 4}},
        }))
        end = _end_event(parser.finalize())
        assert end.usage == TokenUsage(
            prompt_tokens=21, completion_tokens=4, total_tokens=25)

    def test_no_usage_yields_none(self):
        parser = _ResponsesStreamParser()
        parser.feed(json.dumps({
            "type": "response.output_text.delta", "delta": "hi"}))
        parser.feed(json.dumps({
            "type": "response.completed", "response": {"status": "completed"}}))
        assert _end_event(parser.finalize()).usage is None
