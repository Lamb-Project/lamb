"""OpenAI embedding function plugin.

Wraps ChromaDB's built-in ``OpenAIEmbeddingFunction`` so that the same object
is accepted both by the ChromaDB collection API and by the Qdrant backend
(which calls it directly).

API keys are passed per-request and held in memory only (ADR-4).  If an
``api_key`` is not provided at construction time the plugin falls back to the
``EMBEDDINGS_APIKEY`` environment variable via :mod:`config`.

The ``api_endpoint`` parameter accepts a full OpenAI-compatible base URL (e.g.
``"https://api.openai.com/v1"`` or a self-hosted proxy).  If the URL ends with
``"/embeddings"`` that suffix is stripped because
``OpenAIEmbeddingFunction`` appends ``/embeddings`` itself.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from plugins.base import EmbeddingFunction, EmbeddingRegistry, PluginParameter

logger = logging.getLogger(__name__)


@EmbeddingRegistry.register
class OpenAIEmbedding(EmbeddingFunction):
    """OpenAI (or OpenAI-compatible) embedding vendor.

    Delegates to ``chromadb.utils.embedding_functions.OpenAIEmbeddingFunction``
    so collections created with this function remain fully compatible with
    ChromaDB's native query path.
    """

    name = "openai"
    description = "OpenAI embeddings"

    def __init__(
        self,
        *,
        model: str = "text-embedding-3-small",
        api_key: str = "",
        api_endpoint: str = "",
    ) -> None:
        super().__init__(model=model, api_key=api_key, api_endpoint=api_endpoint)

        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction  # lazy

        resolved_key = api_key or os.getenv("EMBEDDINGS_APIKEY", "")
        resolved_model = model or "text-embedding-3-small"

        kwargs: dict[str, Any] = {
            "api_key": resolved_key,
            "model_name": resolved_model,
        }

        if api_endpoint:
            # OpenAIEmbeddingFunction appends /embeddings itself; strip it if
            # the caller supplied the full embeddings URL by mistake.
            base = api_endpoint.rstrip("/").removesuffix("/embeddings")
            kwargs["api_base"] = base

        self._fn = OpenAIEmbeddingFunction(**kwargs)
        logger.debug("OpenAIEmbedding initialised with model=%s", resolved_model)

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._fn(input)

    @classmethod
    def class_parameters(cls) -> list[PluginParameter]:
        return [
            PluginParameter(
                "model",
                "string",
                "Embedding model name",
                "text-embedding-3-small",
            ),
            PluginParameter(
                "api_endpoint",
                "string",
                "Custom OpenAI-compatible base URL (leave empty for api.openai.com)",
                "",
            ),
        ]
