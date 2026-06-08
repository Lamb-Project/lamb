import pytest
from lamb.completions.pps.kvcache_augment import prompt_processor, COMPATIBLE_RAG


class MockAssistant:
    def __init__(self, system_prompt="", prompt_template="", metadata=None):
        self.system_prompt = system_prompt
        self.prompt_template = prompt_template
        self.metadata = metadata
        self.api_callback = metadata


def _make_request(messages):
    return {"messages": messages}


class TestCompatibleRag:
    def test_declares_compatible_rag_list(self):
        assert isinstance(COMPATIBLE_RAG, list)
        assert "library_file_rag" in COMPATIBLE_RAG
        assert "no_rag" in COMPATIBLE_RAG

    def test_does_not_include_legacy_rags(self):
        assert "simple_rag" not in COMPATIBLE_RAG
        assert "single_file_rag" not in COMPATIBLE_RAG


class TestDocumentContextInSystemPrompt:
    def test_document_context_appended_to_system_prompt(self):
        assistant = MockAssistant(
            system_prompt="You are a tutor.",
            prompt_template="Answer: {user_input}\nContext: {context}",
        )
        request = _make_request([{"role": "user", "content": "What is 2+2?"}])
        doc_ctx = {"context": "# Reference Document\nSome content here.", "sources": []}

        result = prompt_processor(request, assistant=assistant, document_context=doc_ctx)

        system_msg = result[0]
        assert system_msg["role"] == "system"
        assert "You are a tutor." in system_msg["content"]
        assert "# Reference Document\nSome content here." in system_msg["content"]

    def test_document_context_as_system_prompt_when_none_exists(self):
        assistant = MockAssistant(
            system_prompt="",
            prompt_template="Answer: {user_input}\nContext: {context}",
        )
        request = _make_request([{"role": "user", "content": "Hello"}])
        doc_ctx = {"context": "Document content.", "sources": []}

        result = prompt_processor(request, assistant=assistant, document_context=doc_ctx)

        system_msg = result[0]
        assert system_msg["role"] == "system"
        assert system_msg["content"] == "Document content."

    def test_no_document_context_leaves_system_prompt_unchanged(self):
        assistant = MockAssistant(
            system_prompt="Original prompt.",
            prompt_template="{user_input}",
        )
        request = _make_request([{"role": "user", "content": "Hi"}])

        result = prompt_processor(request, assistant=assistant)

        system_msg = result[0]
        assert system_msg["content"] == "Original prompt."

    def test_empty_document_context_ignored(self):
        assistant = MockAssistant(
            system_prompt="Original.",
            prompt_template="{user_input}",
        )
        request = _make_request([{"role": "user", "content": "Hi"}])
        doc_ctx = {"context": "", "sources": []}

        result = prompt_processor(request, assistant=assistant, document_context=doc_ctx)

        system_msg = result[0]
        assert system_msg["content"] == "Original."

    def test_document_sources_not_in_user_message(self):
        assistant = MockAssistant(
            system_prompt="Sys.",
            prompt_template="Q: {user_input}\nCtx: {context}",
        )
        request = _make_request([{"role": "user", "content": "Question?"}])
        doc_ctx = {
            "context": "Doc text.",
            "sources": [{"title": "Doc", "url": "/docs/1/2", "similarity": 1.0}],
        }

        result = prompt_processor(request, assistant=assistant, document_context=doc_ctx)

        last_msg = result[-1]
        assert "Doc text." not in last_msg["content"]
        assert "## Available Sources" not in last_msg["content"]

    def test_document_context_and_rag_context_coexist(self):
        assistant = MockAssistant(
            system_prompt="Sys.",
            prompt_template="Q: {user_input}\nCtx: {context}",
        )
        request = _make_request([{"role": "user", "content": "Question?"}])
        doc_ctx = {"context": "Reference doc.", "sources": []}
        rag_ctx = {"context": "RAG chunks.", "sources": [{"title": "KB", "url": "/kb/1", "similarity": 0.9}]}

        result = prompt_processor(
            request, assistant=assistant, rag_context=rag_ctx, document_context=doc_ctx
        )

        system_msg = result[0]
        assert "Reference doc." in system_msg["content"]

        last_msg = result[-1]
        assert "RAG chunks." in last_msg["content"]
        assert "Reference doc." not in last_msg["content"]

    def test_no_assistant_document_context_ignored(self):
        request = _make_request([{"role": "user", "content": "Hi"}])
        doc_ctx = {"context": "Doc.", "sources": []}

        result = prompt_processor(request, document_context=doc_ctx)

        assert len(result) == 1
        assert result[0]["role"] == "user"
