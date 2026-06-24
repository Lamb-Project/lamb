"""Tests for the inline-citation handling in the kvcache_augment PPS.

The PPS no longer injects a visible sources list (the OpenWebUI citations panel
renders sources now). It only ensures the numbered context reaches the model
and that the citation instruction is appended when sources exist.
"""

from lamb.completions.pps.kvcache_augment import (
    CITATION_INSTRUCTION,
    _build_full_context,
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


class TestBuildFullContext:
    def test_appends_instruction_when_sources_exist(self):
        rag_context = {
            "context": "[1] some retrieved text",
            "sources": [{"n": 1, "title": "Doc A", "score": 0.9}],
        }
        full = _build_full_context(rag_context)
        assert "[1] some retrieved text" in full
        assert CITATION_INSTRUCTION in full
        # No visible sources list is injected anymore (OWI renders it).
        assert "## Available Sources" not in full

    def test_no_sources_means_no_citation_instruction(self):
        rag_context = {"context": "plain context", "sources": []}
        full = _build_full_context(rag_context)
        assert full == "plain context"
        assert CITATION_INSTRUCTION not in full

    def test_non_dict_context_is_stringified(self):
        assert _build_full_context("raw") == "raw"
        assert _build_full_context(None) == ""


class TestPromptProcessorInjection:
    def test_no_template_branch_injects_instruction(self):
        """Even without a prompt_template, the numbered context + citation
        instruction must reach the model."""
        assistant = _make_assistant(prompt_template="")
        request = {"messages": [{"role": "user", "content": "What is X?"}]}
        rag_context = {
            "context": "[1] X is a thing.",
            "sources": [{"n": 1, "title": "Doc A", "score": 0.9}],
        }
        out = prompt_processor(request, assistant=assistant, rag_context=rag_context)
        user_msg = out[-1]["content"]
        assert CITATION_INSTRUCTION in user_msg
        assert "[1] X is a thing." in user_msg
        assert "## Available Sources" not in user_msg

    def test_template_branch_injects_instruction(self):
        assistant = _make_assistant(
            prompt_template="Context:\n{context}\n\nQ: {user_input}"
        )
        request = {"messages": [{"role": "user", "content": "What is X?"}]}
        rag_context = {
            "context": "[1] X is a thing.",
            "sources": [{"n": 1, "title": "Doc A", "score": 0.9}],
        }
        out = prompt_processor(request, assistant=assistant, rag_context=rag_context)
        user_msg = out[-1]["content"]
        assert CITATION_INSTRUCTION in user_msg
