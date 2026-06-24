"""Tests for the inline-citation rendering in the kvcache_augment PPS."""

from lamb.completions.pps.kvcache_augment import (
    CITATION_INSTRUCTION,
    _build_full_context,
    _format_sources_block,
    prompt_processor,
)
from lamb.lamb_classes import Assistant


def _make_assistant(**overrides):
    defaults = {
        "id": 1,
        "name": "Test",
        "description": "",
        "system_prompt": "You are helpful.",
        "prompt_template": "",
        "RAG_collections": "ks-1",
        "RAG_Top_k": 3,
        "owner": "user@test.com",
        "api_callback": "",
        "pre_retrieval_endpoint": "",
        "post_retrieval_endpoint": "",
        "RAG_endpoint": "",
    }
    defaults.update(overrides)
    return Assistant(**defaults)


class TestFormatSourcesBlock:
    def test_empty_sources_returns_empty(self):
        assert _format_sources_block([]) == ""

    def test_uses_citation_number_and_renders_score(self):
        sources = [{"n": 1, "title": "Doc A", "url": "/docs/a.md", "score": 0.873}]
        block = _format_sources_block(sources)
        assert "## Available Sources" in block
        assert "[1] [Doc A](/docs/a.md)" in block
        # The relevance score (the KS `score` field) renders — not 0.000.
        assert "relevance: 0.873" in block

    def test_missing_score_is_omitted_gracefully(self):
        sources = [{"n": 1, "title": "Doc A", "url": "/docs/a.md", "score": None}]
        block = _format_sources_block(sources)
        assert "[1] [Doc A](/docs/a.md)" in block
        assert "relevance" not in block

    def test_falls_back_to_enumeration_when_n_absent(self):
        sources = [{"title": "Doc A", "url": ""}]
        block = _format_sources_block(sources)
        assert "[1] Doc A" in block


class TestBuildFullContext:
    def test_appends_sources_block_and_instruction(self):
        rag_context = {
            "context": "[1] some retrieved text",
            "sources": [{"n": 1, "title": "Doc A", "url": "/docs/a.md", "score": 0.9}],
        }
        full = _build_full_context(rag_context)
        assert "[1] some retrieved text" in full
        assert "## Available Sources" in full
        assert CITATION_INSTRUCTION in full

    def test_no_sources_means_no_citation_instruction(self):
        rag_context = {"context": "plain context", "sources": []}
        full = _build_full_context(rag_context)
        assert full == "plain context"
        assert CITATION_INSTRUCTION not in full

    def test_non_dict_context_is_stringified(self):
        assert _build_full_context("raw") == "raw"
        assert _build_full_context(None) == ""


class TestPromptProcessorInjection:
    def test_no_template_branch_injects_sources_and_instruction(self):
        """Even without a prompt_template, the sources block + citation
        instruction must reach the model."""
        assistant = _make_assistant(prompt_template="")
        request = {"messages": [{"role": "user", "content": "What is X?"}]}
        rag_context = {
            "context": "[1] X is a thing.",
            "sources": [{"n": 1, "title": "Doc A", "url": "/docs/a.md", "score": 0.9}],
        }
        out = prompt_processor(request, assistant=assistant, rag_context=rag_context)
        user_msg = out[-1]["content"]
        assert "## Available Sources" in user_msg
        assert CITATION_INSTRUCTION in user_msg
        assert "[1] X is a thing." in user_msg

    def test_template_branch_injects_sources_and_instruction(self):
        assistant = _make_assistant(
            prompt_template="Context:\n{context}\n\nQ: {user_input}"
        )
        request = {"messages": [{"role": "user", "content": "What is X?"}]}
        rag_context = {
            "context": "[1] X is a thing.",
            "sources": [{"n": 1, "title": "Doc A", "url": "/docs/a.md", "score": 0.9}],
        }
        out = prompt_processor(request, assistant=assistant, rag_context=rag_context)
        user_msg = out[-1]["content"]
        assert "## Available Sources" in user_msg
        assert CITATION_INSTRUCTION in user_msg
