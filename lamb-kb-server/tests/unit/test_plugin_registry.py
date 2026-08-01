"""Unit tests for backend/plugins/base.py.

Covers:
- PluginParameter dataclass construction and field defaults
- Chunk, DocumentInput, QueryResult dataclass behaviour
- _BaseRegistry.register: DISABLE env var suppression
- _BaseRegistry.register: normal registration path
- _BaseRegistry.get: None when missing, instance when present
- _BaseRegistry.get_class: None / class returned correctly
- _BaseRegistry.is_registered: True / False semantics
- _BaseRegistry.list_plugins: exception path when instantiation fails (lines 317-323)
- _class_parameters: callable raises path (lines 358-360)
- EmbeddingRegistry.build: happy path with kwargs
- EmbeddingRegistry.build: ValueError when vendor is missing (lines 391-394)
- ChunkingStrategy.get_parameters default return (line 207)
- EmbeddingFunction.get_parameters default return (line 248)
- VectorDBRegistry.get with None path (lines 286-289)
- VectorDBRegistry.get_class with None path (line 294)
- VectorDBRegistry.is_registered False branch (line 298)
"""

from __future__ import annotations

import pytest

from plugins.base import (
    Chunk,
    ChunkingRegistry,
    ChunkingStrategy,
    DocumentInput,
    EmbeddingFunction,
    EmbeddingRegistry,
    PluginParameter,
    QueryResult,
    VectorDBBackend,
    VectorDBRegistry,
    _class_parameters,
)
from tests._fakes import FakeEmbedding


# ---------------------------------------------------------------------------
# PluginParameter dataclass
# ---------------------------------------------------------------------------


def test_plugin_parameter_required_fields_only() -> None:
    """Construct PluginParameter with only the required positional fields."""
    p = PluginParameter(name="my_param", type="string")
    assert p.name == "my_param"
    assert p.type == "string"
    assert p.description == ""
    assert p.default is None
    assert p.required is False
    assert p.choices is None
    assert p.min_value is None
    assert p.max_value is None


def test_plugin_parameter_all_fields() -> None:
    """Construct PluginParameter with every field specified."""
    p = PluginParameter(
        name="chunk_size",
        type="int",
        description="Chunk size in tokens",
        default=512,
        required=True,
        choices=None,
        min_value=1,
        max_value=4096,
    )
    assert p.name == "chunk_size"
    assert p.type == "int"
    assert p.description == "Chunk size in tokens"
    assert p.default == 512
    assert p.required is True
    assert p.choices is None
    assert p.min_value == 1
    assert p.max_value == 4096


def test_plugin_parameter_enum_type_with_choices() -> None:
    """PluginParameter with enum type stores choices list."""
    p = PluginParameter(
        name="vendor",
        type="enum",
        choices=["openai", "ollama", "local"],
    )
    assert p.type == "enum"
    assert p.choices == ["openai", "ollama", "local"]


def test_plugin_parameter_float_type() -> None:
    """PluginParameter accepts float type with float min/max."""
    p = PluginParameter(
        name="temperature",
        type="float",
        default=0.7,
        min_value=0.0,
        max_value=2.0,
    )
    assert p.type == "float"
    assert p.default == 0.7
    assert p.min_value == 0.0
    assert p.max_value == 2.0


def test_plugin_parameter_bool_type() -> None:
    """PluginParameter accepts bool type."""
    p = PluginParameter(name="verbose", type="bool", default=False, required=False)
    assert p.type == "bool"
    assert p.default is False


# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------


def test_chunk_defaults() -> None:
    """Chunk with only text — metadata defaults to empty dict."""
    c = Chunk(text="hello world")
    assert c.text == "hello world"
    assert c.metadata == {}


def test_chunk_with_metadata() -> None:
    """Chunk carries arbitrary metadata."""
    c = Chunk(text="foo", metadata={"source_item_id": "doc-1", "chunk_index": 0})
    assert c.metadata["source_item_id"] == "doc-1"
    assert c.metadata["chunk_index"] == 0


def test_chunk_metadata_is_independent_across_instances() -> None:
    """Two Chunk instances do not share the same metadata dict."""
    c1 = Chunk(text="a")
    c2 = Chunk(text="b")
    c1.metadata["key"] = "value"
    assert "key" not in c2.metadata


# ---------------------------------------------------------------------------
# DocumentInput dataclass
# ---------------------------------------------------------------------------


def test_document_input_required_only() -> None:
    """DocumentInput with the three required fields — optional fields have sane defaults."""
    doc = DocumentInput(source_item_id="src-1", title="My Doc", text="Some text")
    assert doc.source_item_id == "src-1"
    assert doc.title == "My Doc"
    assert doc.text == "Some text"
    assert doc.permalinks == {}
    assert doc.pages == []
    assert doc.extra_metadata == {}


def test_document_input_all_fields() -> None:
    """DocumentInput with all fields populated."""
    doc = DocumentInput(
        source_item_id="src-2",
        title="Full Doc",
        text="Content here",
        permalinks={"page_1": "https://example.com/page/1"},
        pages=[{"text": "page content", "page_number": 1}],
        extra_metadata={"author": "Alice", "lang": "en"},
    )
    assert doc.permalinks == {"page_1": "https://example.com/page/1"}
    assert len(doc.pages) == 1
    assert doc.extra_metadata["author"] == "Alice"


def test_document_input_defaults_are_independent() -> None:
    """Each DocumentInput instance gets its own mutable defaults."""
    d1 = DocumentInput(source_item_id="a", title="A", text="a")
    d2 = DocumentInput(source_item_id="b", title="B", text="b")
    d1.pages.append({"page_number": 1})
    assert d2.pages == []


# ---------------------------------------------------------------------------
# QueryResult dataclass
# ---------------------------------------------------------------------------


def test_query_result_required_only() -> None:
    """QueryResult with text and score — metadata defaults to empty dict."""
    qr = QueryResult(text="result text", score=0.9)
    assert qr.text == "result text"
    assert qr.score == 0.9
    assert qr.metadata == {}


def test_query_result_with_metadata() -> None:
    """QueryResult carries metadata."""
    qr = QueryResult(
        text="chunk text",
        score=0.75,
        metadata={"source_item_id": "doc-a", "chunk_index": 2},
    )
    assert qr.metadata["source_item_id"] == "doc-a"


def test_query_result_score_zero() -> None:
    """Score of 0 is valid (worst match)."""
    qr = QueryResult(text="no match", score=0.0)
    assert qr.score == 0.0


# ---------------------------------------------------------------------------
# Minimal concrete stub classes for registry tests
# ---------------------------------------------------------------------------


class _StubVectorDB(VectorDBBackend):
    """Minimal concrete VectorDBBackend for registry tests."""

    name = "teststub"
    description = "Stub vector DB for registry tests"

    def create_collection(self, *, collection_id, storage_path, embedding_function):
        return collection_id

    def delete_collection(self, *, collection_id, storage_path):
        pass

    def add_chunks(self, *, collection_id, storage_path, chunks, embedding_function):
        return len(chunks)

    def delete_by_source(self, *, collection_id, storage_path, source_item_id):
        return 0

    def query(self, *, collection_id, storage_path, query_text, top_k, embedding_function):
        return []


class _StubChunking(ChunkingStrategy):
    """Minimal concrete ChunkingStrategy for registry tests."""

    name = "teststub"
    description = "Stub chunking for registry tests"

    def chunk(self, document, params=None):
        return [Chunk(text=document.text)]


class _StubEmbedding(EmbeddingFunction):
    """Minimal concrete EmbeddingFunction for registry tests."""

    name = "teststub"
    description = "Stub embedding for registry tests"

    def __init__(self, *, model="stub", api_key="", api_endpoint=""):
        super().__init__(model=model, api_key=api_key, api_endpoint=api_endpoint)

    def __call__(self, input):
        return [[0.5] for _ in input]


# ---------------------------------------------------------------------------
# Registry: register with DISABLE env var
# ---------------------------------------------------------------------------


def test_register_disables_when_env_var_set(monkeypatch) -> None:
    """When {CATEGORY}_{NAME}=DISABLE, register() does NOT add to _plugins."""
    monkeypatch.setenv("VECTOR_DB_TESTSTUB", "DISABLE")
    # Ensure we're starting clean.
    VectorDBRegistry._plugins.pop("teststub", None)
    try:
        VectorDBRegistry.register(_StubVectorDB)
        assert "teststub" not in VectorDBRegistry._plugins
    finally:
        VectorDBRegistry._plugins.pop("teststub", None)


def test_register_disables_chunking_when_env_var_set(monkeypatch) -> None:
    """CHUNKING_TESTSTUB=DISABLE prevents registration."""
    monkeypatch.setenv("CHUNKING_TESTSTUB", "DISABLE")
    ChunkingRegistry._plugins.pop("teststub", None)
    try:
        ChunkingRegistry.register(_StubChunking)
        assert "teststub" not in ChunkingRegistry._plugins
    finally:
        ChunkingRegistry._plugins.pop("teststub", None)


def test_register_disables_embedding_when_env_var_set(monkeypatch) -> None:
    """EMBEDDING_TESTSTUB=DISABLE prevents registration."""
    monkeypatch.setenv("EMBEDDING_TESTSTUB", "DISABLE")
    EmbeddingRegistry._plugins.pop("teststub", None)
    try:
        EmbeddingRegistry.register(_StubEmbedding)
        assert "teststub" not in EmbeddingRegistry._plugins
    finally:
        EmbeddingRegistry._plugins.pop("teststub", None)


def test_register_disable_returns_original_class(monkeypatch) -> None:
    """When disabled, register() still returns the plugin class unchanged."""
    monkeypatch.setenv("VECTOR_DB_TESTSTUB", "DISABLE")
    VectorDBRegistry._plugins.pop("teststub", None)
    try:
        result = VectorDBRegistry.register(_StubVectorDB)
        assert result is _StubVectorDB
    finally:
        VectorDBRegistry._plugins.pop("teststub", None)


# ---------------------------------------------------------------------------
# Registry: register without DISABLE (normal path)
# ---------------------------------------------------------------------------


def test_register_adds_plugin_when_not_disabled(monkeypatch) -> None:
    """Without a DISABLE env var, register() adds the plugin to _plugins."""
    monkeypatch.delenv("VECTOR_DB_TESTSTUB", raising=False)
    VectorDBRegistry._plugins.pop("teststub", None)
    try:
        result = VectorDBRegistry.register(_StubVectorDB)
        assert "teststub" in VectorDBRegistry._plugins
        assert VectorDBRegistry._plugins["teststub"] is _StubVectorDB
        assert result is _StubVectorDB
    finally:
        VectorDBRegistry._plugins.pop("teststub", None)


def test_register_adds_chunking_plugin(monkeypatch) -> None:
    monkeypatch.delenv("CHUNKING_TESTSTUB", raising=False)
    ChunkingRegistry._plugins.pop("teststub", None)
    try:
        ChunkingRegistry.register(_StubChunking)
        assert "teststub" in ChunkingRegistry._plugins
    finally:
        ChunkingRegistry._plugins.pop("teststub", None)


def test_register_adds_embedding_plugin(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_TESTSTUB", raising=False)
    EmbeddingRegistry._plugins.pop("teststub", None)
    try:
        EmbeddingRegistry.register(_StubEmbedding)
        assert "teststub" in EmbeddingRegistry._plugins
    finally:
        EmbeddingRegistry._plugins.pop("teststub", None)


# ---------------------------------------------------------------------------
# Registry.get
# ---------------------------------------------------------------------------


def test_get_returns_none_for_missing_plugin() -> None:
    """get() returns None when the name is not in _plugins (lines 286-289)."""
    result = VectorDBRegistry.get("nonexistent_plugin_xyz")
    assert result is None


def test_get_returns_instance_when_registered(monkeypatch) -> None:
    """get() instantiates and returns the plugin class when it is registered."""
    monkeypatch.delenv("VECTOR_DB_TESTSTUB", raising=False)
    VectorDBRegistry._plugins.pop("teststub", None)
    try:
        VectorDBRegistry._plugins["teststub"] = _StubVectorDB
        instance = VectorDBRegistry.get("teststub")
        assert instance is not None
        assert isinstance(instance, _StubVectorDB)
    finally:
        VectorDBRegistry._plugins.pop("teststub", None)


def test_get_returns_none_for_missing_chunking() -> None:
    result = ChunkingRegistry.get("nonexistent_chunking_xyz")
    assert result is None


def test_get_returns_none_for_missing_embedding() -> None:
    result = EmbeddingRegistry.get("nonexistent_embedding_xyz")
    assert result is None


# ---------------------------------------------------------------------------
# Registry.get_class
# ---------------------------------------------------------------------------


def test_get_class_returns_none_for_missing(monkeypatch) -> None:
    """get_class() returns None when the plugin is not registered (line 294)."""
    assert VectorDBRegistry.get_class("no_such_backend_xyz") is None


def test_get_class_returns_class_when_registered(monkeypatch) -> None:
    """get_class() returns the raw class without instantiating it."""
    VectorDBRegistry._plugins.pop("teststub", None)
    try:
        VectorDBRegistry._plugins["teststub"] = _StubVectorDB
        cls = VectorDBRegistry.get_class("teststub")
        assert cls is _StubVectorDB
    finally:
        VectorDBRegistry._plugins.pop("teststub", None)


# ---------------------------------------------------------------------------
# Registry.is_registered
# ---------------------------------------------------------------------------


def test_is_registered_false_for_missing() -> None:
    """is_registered() returns False when the plugin is absent (line 298 false branch)."""
    assert VectorDBRegistry.is_registered("nonexistent_xyz") is False


def test_is_registered_true_for_registered() -> None:
    """is_registered() returns True when the plugin is present."""
    VectorDBRegistry._plugins.pop("teststub", None)
    try:
        VectorDBRegistry._plugins["teststub"] = _StubVectorDB
        assert VectorDBRegistry.is_registered("teststub") is True
    finally:
        VectorDBRegistry._plugins.pop("teststub", None)


def test_is_registered_false_for_missing_chunking() -> None:
    assert ChunkingRegistry.is_registered("never_registered_xyz") is False


def test_is_registered_false_for_missing_embedding() -> None:
    assert EmbeddingRegistry.is_registered("never_registered_xyz") is False


# ---------------------------------------------------------------------------
# Registry.list_plugins — exception path (lines 317-323)
# ---------------------------------------------------------------------------


class _BrokenPlugin:
    """A fake plugin class that lacks class_parameters and raises on instantiation."""

    name = "broken_plugin"
    description = "A plugin that fails to instantiate"

    def __init__(self):
        raise RuntimeError("Cannot instantiate this plugin")

    def get_parameters(self):
        return []


def test_list_plugins_skips_broken_instantiation() -> None:
    """list_plugins() catches exceptions during instantiation and uses params=[].

    The broken plugin is still listed but with an empty parameters list.
    Lines 317-323.
    """
    VectorDBRegistry._plugins.pop("broken_plugin", None)
    try:
        VectorDBRegistry._plugins["broken_plugin"] = _BrokenPlugin
        result = VectorDBRegistry.list_plugins()
        names = [p["name"] for p in result]
        assert "broken_plugin" in names
        broken_entry = next(p for p in result if p["name"] == "broken_plugin")
        # Parameters fall back to [] due to the exception.
        assert broken_entry["parameters"] == []
        assert broken_entry["description"] == "A plugin that fails to instantiate"
    finally:
        VectorDBRegistry._plugins.pop("broken_plugin", None)


def test_list_plugins_other_plugins_still_listed_despite_broken_one() -> None:
    """A broken plugin in the registry does not prevent other plugins from being listed."""
    VectorDBRegistry._plugins.pop("broken_plugin", None)
    # Count how many real plugins exist first.
    before = {p["name"] for p in VectorDBRegistry.list_plugins()}
    try:
        VectorDBRegistry._plugins["broken_plugin"] = _BrokenPlugin
        result = VectorDBRegistry.list_plugins()
        names = {p["name"] for p in result}
        # All pre-existing plugin names must still appear.
        assert before.issubset(names)
        # The broken one is also present (with empty params).
        assert "broken_plugin" in names
    finally:
        VectorDBRegistry._plugins.pop("broken_plugin", None)


def test_list_plugins_instantiation_path_with_working_plugin() -> None:
    """A plugin without class_parameters that can be instantiated returns its params."""

    class _GoodPlugin:
        name = "good_plugin"
        description = "A good instantiable plugin"

        def __init__(self):
            pass

        def get_parameters(self):
            return [PluginParameter(name="foo", type="string")]

    VectorDBRegistry._plugins.pop("good_plugin", None)
    try:
        VectorDBRegistry._plugins["good_plugin"] = _GoodPlugin
        result = VectorDBRegistry.list_plugins()
        entry = next((p for p in result if p["name"] == "good_plugin"), None)
        assert entry is not None
        assert len(entry["parameters"]) == 1
        assert entry["parameters"][0]["name"] == "foo"
    finally:
        VectorDBRegistry._plugins.pop("good_plugin", None)


# ---------------------------------------------------------------------------
# _class_parameters: callable raises path (lines 358-360)
# ---------------------------------------------------------------------------


def test_class_parameters_returns_empty_when_callable_raises() -> None:
    """_class_parameters returns [] when class_parameters() raises (lines 358-360)."""

    class _RaisingPlugin:
        @classmethod
        def class_parameters(cls):
            raise RuntimeError("class_parameters blew up")

    result = _class_parameters(_RaisingPlugin)
    assert result == []


def test_class_parameters_returns_list_on_success() -> None:
    """_class_parameters returns the list returned by class_parameters()."""

    class _OkPlugin:
        @classmethod
        def class_parameters(cls):
            return [PluginParameter(name="model", type="string")]

    result = _class_parameters(_OkPlugin)
    assert len(result) == 1
    assert result[0].name == "model"


def test_class_parameters_returns_empty_when_not_callable() -> None:
    """_class_parameters returns [] when class_parameters is not callable (line 360)."""

    class _NonCallablePlugin:
        class_parameters = "not a callable"

    result = _class_parameters(_NonCallablePlugin)
    assert result == []


def test_class_parameters_returns_empty_when_attr_absent() -> None:
    """_class_parameters returns [] when the class has no class_parameters at all."""

    class _NoAttrPlugin:
        pass

    result = _class_parameters(_NoAttrPlugin)
    assert result == []


# ---------------------------------------------------------------------------
# EmbeddingRegistry.build
# ---------------------------------------------------------------------------


def test_embedding_registry_build_happy_path() -> None:
    """build() with a registered vendor constructs it with model/api_key/api_endpoint."""
    # FakeEmbedding is force-registered by the conftest session setup.
    ef = EmbeddingRegistry.build(
        "fake",
        model="test-model",
        api_key="key-123",
        api_endpoint="https://api.example.com",
    )
    assert isinstance(ef, FakeEmbedding)
    assert ef.model == "test-model"
    assert ef.api_key == "key-123"
    assert ef.api_endpoint == "https://api.example.com"


def test_embedding_registry_build_default_kwargs() -> None:
    """build() with only the required model arg uses default empty strings for key/endpoint."""
    ef = EmbeddingRegistry.build("fake", model="default-model")
    assert ef.model == "default-model"
    assert ef.api_key == ""
    assert ef.api_endpoint == ""


def test_embedding_registry_build_unknown_vendor_raises_value_error() -> None:
    """build() raises ValueError for an unknown vendor name (lines 391-394)."""
    with pytest.raises(ValueError, match="not registered"):
        EmbeddingRegistry.build("no_such_vendor_xyz", model="m")


def test_embedding_registry_build_error_message_includes_name() -> None:
    """The ValueError message includes the requested vendor name."""
    with pytest.raises(ValueError, match="no_such_vendor_xyz"):
        EmbeddingRegistry.build("no_such_vendor_xyz", model="m")


# ---------------------------------------------------------------------------
# ChunkingStrategy.get_parameters default (line 207)
# ---------------------------------------------------------------------------


def test_chunking_strategy_get_parameters_default() -> None:
    """ChunkingStrategy.get_parameters() returns [] by default (line 207)."""
    strategy = _StubChunking()
    assert strategy.get_parameters() == []


# ---------------------------------------------------------------------------
# EmbeddingFunction.get_parameters default (line 248)
# ---------------------------------------------------------------------------


def test_embedding_function_get_parameters_default() -> None:
    """EmbeddingFunction.get_parameters() returns [] by default (line 248)."""
    ef = _StubEmbedding(model="test")
    assert ef.get_parameters() == []


# ---------------------------------------------------------------------------
# VectorDBBackend.get_parameters default (line 183)
# ---------------------------------------------------------------------------


def test_vector_db_backend_get_parameters_default() -> None:
    """VectorDBBackend.get_parameters() returns [] by default."""
    backend = _StubVectorDB()
    assert backend.get_parameters() == []


# ---------------------------------------------------------------------------
# list_plugins output structure
# ---------------------------------------------------------------------------


def test_list_plugins_returns_all_parameter_fields() -> None:
    """Each parameter in list_plugins output has all 8 expected fields."""

    class _FullParamPlugin:
        name = "full_param_plugin"
        description = "Plugin with full parameter"

        def __init__(self):
            pass

        def get_parameters(self):
            return [
                PluginParameter(
                    name="size",
                    type="int",
                    description="chunk size",
                    default=512,
                    required=True,
                    choices=None,
                    min_value=1,
                    max_value=4096,
                )
            ]

    VectorDBRegistry._plugins.pop("full_param_plugin", None)
    try:
        VectorDBRegistry._plugins["full_param_plugin"] = _FullParamPlugin
        result = VectorDBRegistry.list_plugins()
        entry = next(p for p in result if p["name"] == "full_param_plugin")
        param = entry["parameters"][0]
        assert param["name"] == "size"
        assert param["type"] == "int"
        assert param["description"] == "chunk size"
        assert param["default"] == 512
        assert param["required"] is True
        assert param["choices"] is None
        assert param["min_value"] == 1
        assert param["max_value"] == 4096
    finally:
        VectorDBRegistry._plugins.pop("full_param_plugin", None)


def test_list_plugins_uses_class_parameters_when_available() -> None:
    """list_plugins prefers class_parameters over instance.get_parameters."""

    class _ClassParamPlugin:
        name = "class_param_plugin"
        description = "Plugin with class_parameters"

        @classmethod
        def class_parameters(cls):
            return [PluginParameter(name="model", type="string", default="gpt-4")]

        def __init__(self):
            raise RuntimeError("Should not be instantiated")

        def get_parameters(self):
            raise RuntimeError("Should not be called on instance")

    EmbeddingRegistry._plugins.pop("class_param_plugin", None)
    try:
        EmbeddingRegistry._plugins["class_param_plugin"] = _ClassParamPlugin
        result = EmbeddingRegistry.list_plugins()
        entry = next((p for p in result if p["name"] == "class_param_plugin"), None)
        assert entry is not None
        assert len(entry["parameters"]) == 1
        assert entry["parameters"][0]["name"] == "model"
    finally:
        EmbeddingRegistry._plugins.pop("class_param_plugin", None)
