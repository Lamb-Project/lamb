"""Deterministic fake plugins for tests.

Extracted from the legacy ``tests/conftest.py`` so unit, integration, and
e2e tiers can all import the same fake without circular dependency on
the conftest module.
"""

from __future__ import annotations

import hashlib

from plugins.base import EmbeddingFunction, EmbeddingRegistry, PluginParameter


class FakeEmbedding(EmbeddingFunction):
    """Deterministic, hash-based fake embedding for tests.

    Uses SHA-256 of the input text to produce a reproducible 16-dimensional
    float vector. Identical text → identical vector → cosine score 1.0.
    No network or external model required.
    """

    name = "fake"
    description = "Deterministic fake embedding for tests"
    _dim = 16

    def __init__(
        self,
        *,
        model: str = "fake-model",
        api_key: str = "",
        api_endpoint: str = "",
    ) -> None:
        super().__init__(model=model, api_key=api_key, api_endpoint=api_endpoint)

    def __call__(self, input: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in input:
            digest = hashlib.sha256(str(text).encode("utf-8")).digest()[: self._dim]
            vec = [b / 255.0 for b in digest]
            norm = (sum(v * v for v in vec)) ** 0.5 or 1.0
            vectors.append([v / norm for v in vec])
        return vectors

    @classmethod
    def class_parameters(cls) -> list[PluginParameter]:
        return [
            PluginParameter("model", "string", "Fake model name", "fake-model"),
        ]


def register_fake_embedding() -> None:
    """Force-register the fake embedding (bypassing DISABLE checks)."""
    EmbeddingRegistry._plugins["fake"] = FakeEmbedding
