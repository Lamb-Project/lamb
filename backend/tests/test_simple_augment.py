"""
Tests for the simple_augment prompt processor.
"""

from lamb.lamb_classes import Assistant
from lamb.completions.pps.simple_augment import prompt_processor


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


def test_empty_template_without_rag_context_passthrough():
    """If the template is empty AND there's no rag_context, the user message
    is passed through unchanged — preserves the prior no-RAG behaviour."""
    assistant = _make_assistant(prompt_template="")
    request = {"messages": [{"role": "user", "content": "Hello"}]}

    result = prompt_processor(request, assistant=assistant, rag_context=None)

    assert result[-1] == {"role": "user", "content": "Hello"}


def test_explicit_template_with_context_placeholder_unchanged():
    """When the assistant defines its own template containing {context},
    the template is applied correctly.
    """
    custom = "Refer to context: {context}\n\nQ: {user_input}"
    assistant = _make_assistant(prompt_template=custom)
    request = {"messages": [{"role": "user", "content": "Q?"}]}
    rag_context = {"context": "Some chunk."}

    result = prompt_processor(request, assistant=assistant, rag_context=rag_context)

    augmented = result[-1]["content"]
    assert "Refer to context:" in augmented  # custom template preserved
    assert "Some chunk." in augmented
