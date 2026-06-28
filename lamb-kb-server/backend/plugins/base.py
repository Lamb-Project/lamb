"""Plugin base classes and registries for the KB Server.

The server has three plugin families, each with its own abstract base and
its own registry:

* ``VectorDBBackend``      — pluggable vector stores (ChromaDB, Qdrant)
* ``ChunkingStrategy``     — pluggable text splitters (simple, hierarchical,
  by_page, by_section)
* ``EmbeddingFunction``    — pluggable embedding vendors (openai, ollama,
  local)

Every plugin self-registers via a decorator on its class. The registry
reads ``{CATEGORY}_{NAME}`` env vars (e.g. ``VECTOR_DB_CHROMADB``) and
skips plugins set to ``DISABLE``.

Plugins must declare their parameter schema via ``get_parameters()`` so
LAMB (or a future admin UI) can build a form describing what each one
accepts. All parameter schemas converge on a common ``PluginParameter``
dataclass, identical in spirit to the one used by the Library Manager.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from typing import Any

from config import plugin_mode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared data classes
# ---------------------------------------------------------------------------


@dataclass
class PluginParameter:
    """Describes one configurable parameter of a plugin.

    Used by every plugin type so the API can render a uniform parameter
    schema regardless of category.
    """

    name: str
    type: str  # "string", "int", "float", "bool", "enum"
    description: str = ""
    default: Any = None
    required: bool = False
    choices: list[str] | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None


@dataclass
class DocumentInput:
    """One document delivered by LAMB for ingestion.

    LAMB constructs this shape when it calls ``POST /collections/{id}/add-content``.
    The KB server never fetches content itself — everything it needs is here
    (ADR-1).
    """

    source_item_id: str
    title: str
    text: str
    # Permalink URLs are already ACL-enforced LAMB URLs. They are attached
    # verbatim to every chunk produced from this document so query results
    # can cite their source back to the user.
    permalinks: dict[str, Any] = field(default_factory=dict)
    # Optional pre-split pages for multi-page sources (PDFs, slides). When
    # present, the ``by_page`` chunking strategy uses them verbatim instead
    # of scanning ``text`` for page markers.
    pages: list[dict[str, Any]] = field(default_factory=list)
    # Free-form metadata LAMB wants preserved on every chunk (e.g. author,
    # source_type, language). Merged into chunk metadata last (wins ties).
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """A chunk produced by a chunking strategy, ready to be embedded."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """One hit returned by a similarity search."""

    text: str
    score: float  # cosine similarity in [0, 1], higher is better
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract base classes
# ---------------------------------------------------------------------------


class VectorDBBackend(abc.ABC):
    """Abstract base for vector database backends.

    Each concrete backend creates/deletes collections, stores vectors,
    deletes vectors by ``source_item_id``, and executes similarity search.
    Backends own no metadata — the KB server DB tracks which collection
    uses which backend.
    """

    name: str = "base"
    description: str = "Base vector DB backend"

    @abc.abstractmethod
    def create_collection(
        self,
        *,
        collection_id: str,
        storage_path: str,
        embedding_function: EmbeddingFunction,
    ) -> str:
        """Create a new collection inside the backend.

        Args:
            collection_id: Logical ID (used as backend collection name).
            storage_path: Filesystem path for persistent data.
            embedding_function: Wraps the call to the vendor so the backend
                can embed queries consistently.

        Returns:
            A backend-specific identifier (ChromaDB UUID, Qdrant name, ...).
        """

    @abc.abstractmethod
    def delete_collection(self, *, collection_id: str, storage_path: str) -> None:
        """Remove a collection and all its vectors."""

    @abc.abstractmethod
    def add_chunks(
        self,
        *,
        collection_id: str,
        storage_path: str,
        chunks: list[Chunk],
        embedding_function: EmbeddingFunction,
    ) -> int:
        """Embed and store a list of chunks.

        Returns:
            The number of chunks successfully stored.
        """

    @abc.abstractmethod
    def delete_by_source(
        self,
        *,
        collection_id: str,
        storage_path: str,
        source_item_id: str,
    ) -> int:
        """Remove all vectors whose ``source_item_id`` matches.

        Returns:
            The number of vectors deleted.
        """

    @abc.abstractmethod
    def query(
        self,
        *,
        collection_id: str,
        storage_path: str,
        query_text: str,
        top_k: int,
        embedding_function: EmbeddingFunction,
    ) -> list[QueryResult]:
        """Embed ``query_text`` and return the top ``top_k`` similar chunks."""

    def get_parameters(self) -> list[PluginParameter]:
        """Return the backend-specific configuration schema (usually empty)."""
        return []


class ChunkingStrategy(abc.ABC):
    """Abstract base for chunking strategies.

    A strategy turns one :class:`DocumentInput` into a list of :class:`Chunk`.
    Strategies receive per-collection parameters (chunk_size, overlap, ...)
    passed through from the collection's locked store setup.
    """

    name: str = "base"
    description: str = "Base chunking strategy"

    @abc.abstractmethod
    def chunk(
        self,
        document: DocumentInput,
        params: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Split ``document`` into chunks according to the strategy."""

    def get_parameters(self) -> list[PluginParameter]:
        """Return the parameter schema for this strategy."""
        return []


class EmbeddingFunction(abc.ABC):
    """Abstract base for embedding functions.

    Embedders are constructed fresh per ingestion job or query because
    credentials are request-scoped (ADR-4). The concrete implementations
    wrap ChromaDB's built-in ``OpenAIEmbeddingFunction`` /
    ``OllamaEmbeddingFunction`` to stay consistent with the stable KB
    server's defaults.

    Every instance must expose a callable shape accepted by ChromaDB
    (``__call__(input: list[str]) -> list[list[float]]``) so the same
    object can be reused by the vector backend.
    """

    name: str = "base"
    description: str = "Base embedding function"

    def __init__(
        self,
        *,
        model: str,
        api_key: str = "",
        api_endpoint: str = "",
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.api_endpoint = api_endpoint

    @abc.abstractmethod
    def __call__(self, input: list[str]) -> list[list[float]]:
        """Embed a list of strings into a list of float vectors.

        Named ``input`` (not ``texts``) for ChromaDB 0.6+ compatibility;
        ChromaDB inspects the parameter name.
        """

    def get_parameters(self) -> list[PluginParameter]:
        """Return the parameter schema for this vendor (model, endpoint)."""
        return []


# ---------------------------------------------------------------------------
# Registry infrastructure
# ---------------------------------------------------------------------------


class _BaseRegistry:
    """Shared registry machinery for all three plugin families."""

    category: str = ""  # "VECTOR_DB", "CHUNKING", or "EMBEDDING"
    _plugins: dict[str, type] = {}

    @classmethod
    def register(cls, plugin_class: type) -> type:
        """Decorator that registers a plugin class.

        If the env var ``{CATEGORY}_{NAME}`` is set to ``DISABLE``, the
        plugin is silently skipped.
        """
        mode = plugin_mode(cls.category, plugin_class.name)
        if mode == "DISABLE":
            logger.info(
                "Plugin '%s/%s' disabled via environment",
                cls.category,
                plugin_class.name,
            )
            return plugin_class
        cls._plugins[plugin_class.name] = plugin_class
        logger.debug(
            "Registered %s plugin: %s", cls.category, plugin_class.name
        )
        return plugin_class

    @classmethod
    def get(cls, name: str) -> Any | None:
        """Instantiate a plugin by name (no args). Returns ``None`` if absent."""
        plugin_class = cls._plugins.get(name)
        if plugin_class is None:
            return None
        return plugin_class()

    @classmethod
    def get_class(cls, name: str) -> type | None:
        """Return the raw plugin class without instantiation."""
        return cls._plugins.get(name)

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name in cls._plugins

    @classmethod
    def list_plugins(cls) -> list[dict[str, Any]]:
        """Return metadata for every registered plugin in this category.

        Prefer a ``class_parameters`` classmethod when defined — that lets
        embedding plugins expose their schema without instantiating a vendor
        client (which would require network calls or optional SDKs that may
        not be installed in every deployment).
        """
        result = []
        for name, plugin_class in cls._plugins.items():
            if hasattr(plugin_class, "class_parameters"):
                params = _class_parameters(plugin_class)
            else:
                try:
                    instance = plugin_class()
                    params = instance.get_parameters()
                except Exception:  # noqa: BLE001
                    logger.debug(
                        "Could not instantiate plugin '%s' for listing",
                        plugin_class.name,
                        exc_info=True,
                    )
                    params = []
            result.append(
                {
                    "name": name,
                    "description": getattr(
                        plugin_class, "description", ""
                    ),
                    "parameters": [
                        {
                            "name": p.name,
                            "type": p.type,
                            "description": p.description,
                            "default": p.default,
                            "required": p.required,
                            "choices": p.choices,
                            "min_value": p.min_value,
                            "max_value": p.max_value,
                        }
                        for p in params
                    ],
                }
            )
        return result


def _class_parameters(plugin_class: type) -> list[PluginParameter]:
    """Return ``get_parameters`` defined at class level if available.

    Used as a fallback when a plugin can't be instantiated without args
    (most relevant for embedding functions which need ``model=``).
    """
    attr = getattr(plugin_class, "class_parameters", None)
    if callable(attr):
        try:
            return attr()
        except Exception:
            return []
    return []


class VectorDBRegistry(_BaseRegistry):
    category = "VECTOR_DB"
    _plugins: dict[str, type[VectorDBBackend]] = {}


class ChunkingRegistry(_BaseRegistry):
    category = "CHUNKING"
    _plugins: dict[str, type[ChunkingStrategy]] = {}


class EmbeddingRegistry(_BaseRegistry):
    category = "EMBEDDING"
    _plugins: dict[str, type[EmbeddingFunction]] = {}

    @classmethod
    def build(
        cls,
        name: str,
        *,
        model: str,
        api_key: str = "",
        api_endpoint: str = "",
    ) -> EmbeddingFunction:
        """Construct an embedding function for ``name`` with credentials.

        Raises:
            ValueError: If the vendor is not registered.
        """
        plugin_class = cls._plugins.get(name)
        if plugin_class is None:
            raise ValueError(f"Embedding vendor '{name}' is not registered.")
        return plugin_class(model=model, api_key=api_key, api_endpoint=api_endpoint)
