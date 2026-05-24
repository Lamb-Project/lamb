"""Ollama embedding function plugin.

Uses the ollama SDK directly — not chromadb's built-in OllamaEmbeddingFunction,
which has compatibility issues with newer ollama SDK versions.
"""

from __future__ import annotations

import logging
import os

from plugins.base import EmbeddingFunction, EmbeddingRegistry, PluginParameter

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "nomic-embed-text"
_DEFAULT_ENDPOINT = os.environ.get(
    "OLLAMA_DEFAULT_ENDPOINT", "http://localhost:11434/api/embeddings"
)


@EmbeddingRegistry.register
class OllamaEmbedding(EmbeddingFunction):
    """Ollama local embedding vendor."""

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
        self._model = model or _DEFAULT_MODEL
        self._api_endpoint = api_endpoint or _DEFAULT_ENDPOINT

    def __call__(self, input: list[str]) -> list[list[float]]:
        import ollama

        base_url = self._api_endpoint.rstrip("/")
        for suffix in ("/api/embeddings", "/api/embed"):
            if base_url.endswith(suffix):
                base_url = base_url[: -len(suffix)]
                break

        client = ollama.Client(host=base_url)

        try:
            response = client.embed(model=self._model, input=input)
            embeddings = response.embeddings
        except AttributeError:
            embeddings = [
                client.embeddings(model=self._model, prompt=text)["embedding"]
                for text in input
            ]

        logger.debug(
            "OllamaEmbedding: embedded %d texts with model=%s", len(input), self._model
        )
        return embeddings

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
