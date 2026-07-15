"""Log full provider request/response payloads when LLM_PROVIDER_LOG is enabled.

Uses a dedicated logger (lamb.provider_io) so output appears even when
GLOBAL_LOG_LEVEL/API_LOG_LEVEL are WARNING — typical in docker-compose-example.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

_ENABLED = os.getenv("LLM_PROVIDER_LOG", "").lower() in ("1", "true", "yes", "on")

_logger = logging.getLogger("lamb.provider_io")
if _ENABLED and not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [PROVIDER-IO] %(message)s")
    )
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False

_SENSITIVE_KEYS = frozenset({
    "api_key", "authorization", "x-api-key", "api-key",
    "credentials", "token", "secret",
})

def is_enabled() -> bool:
    return _ENABLED


def _sanitize_value(key: str, value: Any, depth: int = 0) -> Any:
    if depth > 12:
        return "<max depth>"

    key_lower = key.lower() if isinstance(key, str) else ""
    if key_lower in _SENSITIVE_KEYS:
        return "<redacted>"

    if isinstance(value, str):
        if value.startswith("data:") and ";base64," in value:
            header, _, b64 = value.partition(";base64,")
            return f"{header};base64,<base64 omitted, {len(b64)} chars>"
        if len(value) > 4000:
            return value[:4000] + f"... <truncated, {len(value)} chars total>"
        return value

    if isinstance(value, dict):
        return {k: _sanitize_value(str(k), v, depth + 1) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_sanitize_value("", item, depth + 1) for item in value]

    if isinstance(value, bytes):
        return f"<bytes len={len(value)}>"

    # Pydantic / SDK objects
    if hasattr(value, "model_dump"):
        try:
            return _sanitize_value("", value.model_dump(), depth + 1)
        except Exception:
            pass

    return value


def _serialize(payload: Any) -> str:
    sanitized = _sanitize_value("", payload)
    try:
        return json.dumps(sanitized, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return repr(sanitized)


def log_provider_request(
    provider: str,
    *,
    operation: str,
    payload: Any,
    extra: dict[str, Any] | None = None,
) -> None:
    if not _ENABLED:
        return
    lines = [
        f"{'=' * 72}",
        f"PROVIDER REQUEST  provider={provider}  operation={operation}",
        _serialize(payload),
    ]
    if extra:
        lines.append("--- metadata ---")
        lines.append(_serialize(extra))
    lines.append("=" * 72)
    _logger.info("\n".join(lines))


def log_provider_response(
    provider: str,
    *,
    operation: str,
    payload: Any,
    label: str = "response",
) -> None:
    if not _ENABLED:
        return
    lines = [
        f"{'=' * 72}",
        f"PROVIDER {label.upper()}  provider={provider}  operation={operation}",
        _serialize(payload),
        "=" * 72,
    ]
    _logger.info("\n".join(lines))
