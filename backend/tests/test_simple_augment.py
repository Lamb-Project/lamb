"""
Tests for the simple_augment prompt processor.

Regression test for defect D3 (lifecycle 2026-05-03): when an assistant
has an empty ``prompt_template`` but a non-empty ``rag_context`` is
supplied, simple_augment must apply a default template so the retrieved
chunks actually reach the LLM. Previously it silently dropped them.
"""

from lamb.lamb_classes import Assistant
from lamb.completions.pps.simple_augment import (
    DEFAULT_RAG_PROMPT_TEMPLATE,
    prompt_processor,
)


def _make_assistant(prompt_template: str = "", system_prompt: str = "You are a helper.") -> Assistant:
    """Build a minimal Assistant with default fields."""
    return Assistant(
        id=1,
        organization_id=1,
        name="Test",
        description="",
        owner="user@example.com",
        api_callback="{}",
        system_prompt=system_prompt,
        prompt_template=prompt_template,
        pre_retrieval_endpoint="",
        post_retrieval_endpoint="",
        RAG_endpoint="",
        RAG_Top_k=3,
        RAG_collections="",
    )


def test_empty_template_with_rag_context_uses_default_template():
    """D3 regression: empty prompt_template + non-empty rag_context must
    fall back to the module's DEFAULT_RAG_PROMPT_TEMPLATE so the retrieved
    chunks reach the LLM. The augmented user message must contain both the
    user's question and the retrieved context text."""
    assistant = _make_assistant(prompt_template="")
    request = {"messages": [{"role": "user", "content": "What is mitochondria?"}]}
    rag_context = {"context": "Mitochondria are the powerhouse of the cell."}

    result = prompt_processor(request, assistant=assistant, rag_context=rag_context)

    # System prompt preserved.
    assert result[0]["role"] == "system"
    assert result[0]["content"] == "You are a helper."

    # Last message is the augmented user message.
    last = result[-1]
    assert last["role"] == "user"
    augmented = last["content"]
    assert "Mitochondria are the powerhouse of the cell." in augmented, (
        "RAG context was dropped — defect D3 has regressed."
    )
    assert "What is mitochondria?" in augmented
    # And the default template was used (verifies the fallback path, not
    # accidental string match).
    assert "{context}" not in augmented  # placeholder must be substituted
    assert "{user_input}" not in augmented


def test_empty_template_without_rag_context_passthrough():
    """If the template is empty AND there's no rag_context, the user message
    is passed through unchanged — preserves the prior no-RAG behaviour."""
    assistant = _make_assistant(prompt_template="")
    request = {"messages": [{"role": "user", "content": "Hello"}]}

    result = prompt_processor(request, assistant=assistant, rag_context=None)

    assert result[-1] == {"role": "user", "content": "Hello"}


def test_explicit_template_with_context_placeholder_unchanged():
    """When the assistant defines its own template containing {context},
    the default fallback must NOT kick in — the user-provided template wins.
    """
    custom = "Refer to context: {context}\n\nQ: {user_input}"
    assistant = _make_assistant(prompt_template=custom)
    request = {"messages": [{"role": "user", "content": "Q?"}]}
    rag_context = {"context": "Some chunk."}

    result = prompt_processor(request, assistant=assistant, rag_context=rag_context)

    augmented = result[-1]["content"]
    assert "Refer to context:" in augmented  # custom template preserved
    assert "Some chunk." in augmented


def test_document_context_gets_descriptive_label():
    """Document RAG content should be wrapped with a descriptive REFERENCE DOCUMENT label."""
    assistant = _make_assistant(system_prompt="You are helpful.", prompt_template="Answer: {user_input}")
    request = {
        "messages": [
            {"role": "user", "content": "What is the answer?"}
        ]
    }
    document_context = {"context": "This is the reference document content.", "sources": []}

    result = prompt_processor(request, assistant=assistant, document_context=document_context)

    system_msg = result[0]
    assert system_msg["role"] == "system"
    assert "REFERENCE DOCUMENT" in system_msg["content"]
    assert "This is the reference document content." in system_msg["content"]
    # Should contain the explanation for the LLM
    assert "selected by the assistant creator" in system_msg["content"]
    # Should contain the recency-bias reminder at the end
    assert "available for this entire conversation" in system_msg["content"]
    # Reminder should be at the very end of the system content
    assert system_msg["content"].rstrip().endswith("use it.")
    # Should come after the original system prompt
    assert "You are helpful." in system_msg["content"]
    doc_index = system_msg["content"].index("REFERENCE DOCUMENT")
    sys_index = system_msg["content"].index("You are helpful.")
    assert doc_index > sys_index


def test_default_template_constant_matches_cli():
    """Sanity check: the module-level constant matches the CLI default
    (kept in lamb-cli/src/lamb_cli/commands/assistant.py). If either side
    changes, the other should be updated to match."""
    expected = (
        "Use the following context to answer the question. "
        "If the context does not contain the answer, say you do not know.\n\n"
        "Context:\n{context}\n\nQuestion: {user_input}"
    )
    assert DEFAULT_RAG_PROMPT_TEMPLATE == expected
