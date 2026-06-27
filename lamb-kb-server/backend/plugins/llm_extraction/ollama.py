"""Ollama chat-completion backend for KG-RAG concept extraction.

Talks to a local Ollama daemon (default http://localhost:11434) via the
official ``ollama`` Python SDK. Sends ``format='json'`` so the model is
required to emit a JSON object.

No API key is needed for a default Ollama install; if a deployment puts
Ollama behind an auth proxy, the per-request token can be passed via
``api_key`` and is forwarded as a Bearer header.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from plugins.base import (
    LLMExtractionFunction,
    LLMExtractionRegistry,
    PluginParameter,
)

logger = logging.getLogger(__name__)


@LLMExtractionRegistry.register
class OllamaExtraction(LLMExtractionFunction):
    """Ollama chat-completion extraction backend (local models)."""

    name = "ollama"
    description = "Ollama local chat-completion extraction (llama3, qwen2, ...)"

    def __init__(
        self,
        *,
        model: str = "llama3.1:8b",
        api_key: str = "",
        api_endpoint: str = "",
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            model=model,
            api_key=api_key,
            api_endpoint=api_endpoint,
            timeout_seconds=timeout_seconds,
        )
        self._model = model or "llama3.1:8b"

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        fallback_model: str | None = None,
    ) -> dict[str, Any]:
        try:
            from ollama import Client  # noqa: PLC0415
        except ImportError:
            logger.warning("Ollama SDK is not installed")
            return {}

        host = (
            self.api_endpoint
            or os.getenv("OLLAMA_HOST")
            or "http://localhost:11434"
        )
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        client = Client(host=host, timeout=self.timeout_seconds, headers=headers)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        try:
            response = client.chat(
                model=self._model,
                messages=messages,
                format="json",
                options={"temperature": 0},
            )
        except Exception as exc:  # noqa: BLE001
            if fallback_model and fallback_model != self._model:
                logger.warning(
                    "Ollama extraction with %s failed (%s); retrying with %s",
                    self._model,
                    exc,
                    fallback_model,
                )
                try:
                    response = client.chat(
                        model=fallback_model,
                        messages=messages,
                        format="json",
                        options={"temperature": 0},
                    )
                except Exception as exc2:  # noqa: BLE001
                    logger.warning("Ollama extraction fallback failed: %s", exc2)
                    return {}
            else:
                logger.warning("Ollama extraction failed: %s", exc)
                return {}

        content = response.get("message", {}).get("content", "{}")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("Ollama extraction returned invalid JSON: %s", exc)
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @classmethod
    def class_parameters(cls) -> list[PluginParameter]:
        return [
            PluginParameter(
                "model",
                "string",
                "Ollama model tag (must be pulled on the Ollama host)",
                "llama3.1:8b",
                choices=[
                    "llama3.1:8b",
                    "llama3.1:70b",
                    "llama3.2:3b",
                    "llama3.3:70b",
                    "qwen2.5:7b",
                    "qwen2.5:14b",
                    "mistral:7b",
                    "mixtral:8x7b",
                    "phi3:medium",
                    "gemma2:9b",
                ],
            ),
            PluginParameter(
                "api_endpoint",
                "string",
                "Ollama host URL (leave empty for http://localhost:11434)",
                "",
            ),
        ]
