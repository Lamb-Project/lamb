"""OpenAI chat-completion backend for KG-RAG concept extraction.

Uses the openai v1 SDK directly with ``response_format=json_object`` to
extract structured entity / relationship lists from text chunks. Falls
back to a secondary model when the primary refuses JSON mode (older
models or third-party OpenAI-compatible endpoints).

API keys are passed per-request (ADR-4). Falls back to
``KG_RAG_OPENAI_API_KEY`` / ``OPENAI_API_KEY`` env var if none is provided
at call time.
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
class OpenAIExtraction(LLMExtractionFunction):
    """OpenAI (or OpenAI-compatible) chat-completion extraction backend."""

    name = "openai"
    description = "OpenAI chat-completion extraction (gpt-4o-mini, gpt-4o, ...)"

    def __init__(
        self,
        *,
        model: str = "gpt-4o-mini",
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
        self._model = model or "gpt-4o-mini"

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        fallback_model: str | None = None,
    ) -> dict[str, Any]:
        try:
            from openai import OpenAI  # noqa: PLC0415
        except ImportError:
            logger.warning(
                "OpenAI SDK is not installed; install kb-server with [kg-rag]"
            )
            return {}

        resolved_key = (
            self.api_key
            or os.getenv("KG_RAG_OPENAI_API_KEY")
            or os.getenv("OPENAI_API_KEY", "")
        )
        if not resolved_key:
            logger.warning("OpenAI extraction: no API key configured")
            return {}

        kwargs: dict[str, Any] = {
            "api_key": resolved_key,
            "timeout": self.timeout_seconds,
        }
        if self.api_endpoint:
            kwargs["base_url"] = self.api_endpoint.rstrip("/")

        client = OpenAI(**kwargs)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )
        except Exception as exc:  # noqa: BLE001
            if fallback_model and fallback_model != self._model:
                logger.warning(
                    "OpenAI extraction with %s failed (%s); retrying with %s",
                    self._model,
                    exc,
                    fallback_model,
                )
                try:
                    response = client.chat.completions.create(
                        model=fallback_model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0,
                    )
                except Exception as exc2:  # noqa: BLE001
                    logger.warning("OpenAI extraction fallback failed: %s", exc2)
                    return {}
            else:
                logger.warning("OpenAI extraction failed: %s", exc)
                return {}

        content = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("OpenAI extraction returned invalid JSON: %s", exc)
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @classmethod
    def class_parameters(cls) -> list[PluginParameter]:
        return [
            PluginParameter(
                "model",
                "string",
                "Chat-completion model name",
                "gpt-4o-mini",
                choices=[
                    "gpt-4o-mini",
                    "gpt-4o",
                    "gpt-4-turbo",
                    "gpt-5-nano",
                    "gpt-3.5-turbo",
                ],
            ),
            PluginParameter(
                "api_endpoint",
                "string",
                "Custom OpenAI-compatible base URL (leave empty for api.openai.com)",
                "",
            ),
        ]
