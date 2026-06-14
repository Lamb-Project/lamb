import json
import pytest

from lamb.completions.plugin_config import parse_plugin_config, process_completion_request


class MockAssistant:
    def __init__(self, metadata="", system_prompt="", prompt_template=""):
        self.metadata = metadata
        self.api_callback = metadata
        self.system_prompt = system_prompt
        self.prompt_template = prompt_template
        self.id = 1
        self.name = "test"
        self.owner = "test_owner"


class TestParsePluginConfigDocumentRag:
    def test_reads_document_rag_from_metadata(self):
        metadata = json.dumps({
            "prompt_processor": "kvcache_augment",
            "connector": "openai",
            "llm": "gpt-4o-mini",
            "rag_processor": "context_aware_rag",
            "document_rag": "library_file_rag",
        })
        assistant = MockAssistant(metadata=metadata)
        config = parse_plugin_config(assistant)
        assert config["document_rag"] == "library_file_rag"

    def test_document_rag_defaults_to_empty(self):
        metadata = json.dumps({
            "prompt_processor": "kvcache_augment",
            "connector": "openai",
            "llm": "gpt-4o-mini",
            "rag_processor": "no_rag",
        })
        assistant = MockAssistant(metadata=metadata)
        config = parse_plugin_config(assistant)
        assert config["document_rag"] == ""

    def test_legacy_single_file_rag_stays_in_rag_processor(self):
        metadata = json.dumps({
            "prompt_processor": "simple_augment",
            "connector": "openai",
            "llm": "gpt-4o-mini",
            "rag_processor": "single_file_rag",
        })
        assistant = MockAssistant(metadata=metadata)
        config = parse_plugin_config(assistant)
        assert config["rag_processor"] == "single_file_rag"
        assert config["document_rag"] == ""


class TestProcessCompletionRequestDocumentContext:
    def test_passes_document_context_to_pps(self):
        captured_kwargs = {}

        def mock_pps(request, assistant=None, rag_context=None, **kwargs):
            captured_kwargs["document_context"] = kwargs.get("document_context")
            captured_kwargs["rag_context"] = rag_context
            return [{"role": "user", "content": "test"}]

        pps = {"kvcache_augment": mock_pps}
        plugin_config = {"prompt_processor": "kvcache_augment"}
        doc_ctx = {"context": "Doc.", "sources": []}

        process_completion_request(
            request={"messages": [{"role": "user", "content": "Hi"}]},
            assistant_details=None,
            plugin_config=plugin_config,
            rag_context=None,
            pps=pps,
            document_context=doc_ctx,
        )

        assert captured_kwargs.get("document_context") == doc_ctx
