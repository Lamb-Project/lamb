"""Ollama embedding function plugin.

Wraps ChromaDB's built-in ``OllamaEmbeddingFunction`` so that the same object
is accepted both by the ChromaDB collection API and by the Qdrant backend
(which calls it directly).

Ollama must be running locally (or at the configured ``api_endpoint``) and the
requested model must already be pulled.
"""

from __future__ import annotations

import logging

from plugins.base import EmbeddingFunction, EmbeddingRegistry, PluginParameter

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "nomic-embed-text"
_DEFAULT_ENDPOINT = "http://localhost:11434/api/embeddings"


@EmbeddingRegistry.register
class OllamaEmbedding(EmbeddingFunction):
    """Ollama local embedding vendor.

    Delegates to ``chromadb.utils.embedding_functions.OllamaEmbeddingFunction``
    so collections created with this function remain fully compatible with
    ChromaDB's native query path.
    """

    name = "ollama"
    description = "Ollama local embeddings"

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        api_key: str = "",
        api_endpoint: str = _DEFAULT_ENDPOINT,
    ) -> None:
        super().__init__(model=model, api_key=api_key, api_endpoint=api_endpoint)

        from chromadb.utils.embedding_functions import OllamaEmbeddingFunction  # lazy

        resolved_model = model or _DEFAULT_MODEL
        resolved_endpoint = api_endpoint or _DEFAULT_ENDPOINT

        self._fn = OllamaEmbeddingFunction(
            url=resolved_endpoint,
            model_name=resolved_model,
        )
        logger.debug(
            "OllamaEmbedding initialised with model=%s endpoint=%s",
            resolved_model,
            resolved_endpoint,
        )

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._fn(input)

    @classmethod
    def class_parameters(cls) -> list[PluginParameter]:
        return [
            PluginParameter(
                "model",
                "string",
                "Ollama model name (must be pulled locally)",
                _DEFAULT_MODEL,
            ),
            PluginParameter(
                "api_endpoint",
                "string",
                "Ollama API embeddings endpoint URL",
                _DEFAULT_ENDPOINT,
            ),
        ]
