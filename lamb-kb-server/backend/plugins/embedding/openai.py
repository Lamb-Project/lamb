"""OpenAI embedding function plugin.

Uses the openai v1 SDK directly — not chromadb's built-in wrapper, which
targets the old v0 API and raises APIRemovedInV1 with openai>=1.0.0.

API keys are passed per-request (ADR-4). Falls back to the EMBEDDINGS_APIKEY
env var if no key is provided at call time.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from plugins.base import EmbeddingFunction, EmbeddingRegistry, PluginParameter

logger = logging.getLogger(__name__)


@EmbeddingRegistry.register
class OpenAIEmbedding(EmbeddingFunction):
    """OpenAI (or OpenAI-compatible) embedding vendor using the v1 SDK."""

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
        self._model = model or "text-embedding-3-small"
        self._api_key = api_key
        self._api_endpoint = api_endpoint

    def __call__(self, input: list[str]) -> list[list[float]]:
        from openai import APIConnectionError, OpenAI

        resolved_key = self._api_key or os.getenv("EMBEDDINGS_APIKEY", "")
        kwargs: dict[str, Any] = {"api_key": resolved_key or "no-key"}
        endpoint = self._api_endpoint or "https://api.openai.com/v1"
        if self._api_endpoint:
            base = self._api_endpoint.rstrip("/").removesuffix("/embeddings")
            kwargs["base_url"] = base

        client = OpenAI(**kwargs)
        try:
            response = client.embeddings.create(model=self._model, input=input)
        except APIConnectionError as exc:
            raise RuntimeError(
                f"OpenAI embedding: cannot connect to {endpoint} — "
                "check that the endpoint is running and reachable"
            ) from exc
        logger.debug("OpenAIEmbedding: embedded %d texts with model=%s", len(input), self._model)
        return [item.embedding for item in response.data]

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
