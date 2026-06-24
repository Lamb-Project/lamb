"""Tests for the citation handling in the kvcache_augment PPS.

Citations are opt-in per assistant via ``capabilities.expose_sources``. When
off (the default), no inline ``[N]`` markers or instruction reach the model and
the ``[N]`` context prefixes are stripped. When on, the numbered context and
the cite instruction are kept (the clickable source list is rendered
separately).
"""

import json

from lamb.completions.pps.kvcache_augment import (
    CITATION_INSTRUCTION,
    _build_full_context,
    _exposes_sources,
    prompt_processor,
)
from lamb.lamb_classes import Assistant


def _make_assistant(expose_sources=False, **overrides):
    defaults = {
        "id": 1,
        "name": "Test",
        "description": "",
        "system_prompt": "You are helpful.",
        "prompt_template": "",
        "RAG_collections": "ks-1",
        "RAG_Top_k": 3,
        "owner": "user@test.com",
        "api_callback": json.dumps({"capabilities": {"expose_sources": expose_sources}}),
        "pre_retrieval_endpoint": "",
        "post_retrieval_endpoint": "",
        "RAG_endpoint": "",
    }
    defaults.update(overrides)
    return Assistant(**defaults)


class TestExposesSources:
    def test_defaults_false(self):
        assert _exposes_sources(_make_assistant()) is False
        assert _exposes_sources(None) is False

    def test_true_when_enabled(self):
        assert _exposes_sources(_make_assistant(expose_sources=True)) is True

    def test_false_on_missing_or_bad_metadata(self):
        assert _exposes_sources(_make_assistant(api_callback="")) is False
        assert _exposes_sources(_make_assistant(api_callback="not json")) is False


class TestBuildFullContext:
    def test_cite_true_appends_instruction_and_keeps_markers(self):
        rag_context = {
            "context": "[1] some retrieved text",
            "sources": [{"n": 1, "title": "Doc A", "score": 0.9}],
        }
        full = _build_full_context(rag_context, cite=True)
        assert "[1] some retrieved text" in full
        assert CITATION_INSTRUCTION in full
        assert "## Available Sources" not in full

    def test_cite_false_strips_markers_and_omits_instruction(self):
        rag_context = {
            "context": "[1] first chunk\n\n[2] second chunk",
            "sources": [{"n": 1}, {"n": 2}],
        }
        full = _build_full_context(rag_context, cite=False)
        assert CITATION_INSTRUCTION not in full
        # The [N] prefixes are removed so the model has no cue to cite.
        assert "[1]" not in full and "[2]" not in full
        assert "first chunk" in full and "second chunk" in full

    def test_no_sources_means_no_instruction(self):
        rag_context = {"context": "plain context", "sources": []}
        assert _build_full_context(rag_context, cite=True) == "plain context"

    def test_non_dict_context_is_stringified(self):
        assert _build_full_context("raw") == "raw"
        assert _build_full_context(None) == ""


class TestPromptProcessorGating:
    _RAG = {
        "context": "[1] X is a thing.",
        "sources": [{"n": 1, "title": "Doc A", "score": 0.9}],
    }

    def test_opted_in_assistant_gets_citation_instruction(self):
        assistant = _make_assistant(expose_sources=True, prompt_template="")
        request = {"messages": [{"role": "user", "content": "What is X?"}]}
        out = prompt_processor(request, assistant=assistant, rag_context=self._RAG)
        user_msg = out[-1]["content"]
        assert CITATION_INSTRUCTION in user_msg
        assert "[1] X is a thing." in user_msg

    def test_default_assistant_gets_no_citation_markers(self):
        assistant = _make_assistant(expose_sources=False, prompt_template="")
        request = {"messages": [{"role": "user", "content": "What is X?"}]}
        out = prompt_processor(request, assistant=assistant, rag_context=self._RAG)
        user_msg = out[-1]["content"]
        assert CITATION_INSTRUCTION not in user_msg
        # The [1] prefix is stripped; the underlying text remains.
        assert "[1]" not in user_msg
        assert "X is a thing." in user_msg

    def test_template_branch_respects_opt_in(self):
        assistant = _make_assistant(
            expose_sources=True, prompt_template="Context:\n{context}\n\nQ: {user_input}"
        )
        request = {"messages": [{"role": "user", "content": "What is X?"}]}
        out = prompt_processor(request, assistant=assistant, rag_context=self._RAG)
        assert CITATION_INSTRUCTION in out[-1]["content"]
