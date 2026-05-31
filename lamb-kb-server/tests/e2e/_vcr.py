"""VCR cassette helpers for replaying OpenAI embedding responses.

Use ``@use_cassette("name")`` on tests that exercise the OpenAI plugin.
By default cassettes replay only — pass ``RECORD_CASSETTES=1`` and a
real ``OPENAI_API_KEY`` to re-record.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import vcr  # type: ignore
except ImportError:  # pragma: no cover
    vcr = None  # type: ignore

_CASSETTE_DIR = Path(__file__).resolve().parent / "_cassettes"


def _record_mode() -> str:
    return "new_episodes" if os.environ.get("RECORD_CASSETTES") == "1" else "none"


def use_cassette(name: str):
    """Decorator that wraps a test in a VCR cassette context."""
    if vcr is None:  # pragma: no cover
        import pytest

        return pytest.mark.skip(reason="vcrpy not installed")

    cassette_path = _CASSETTE_DIR / f"{name}.yaml"
    cassette_path.parent.mkdir(parents=True, exist_ok=True)

    return vcr.use_cassette(
        str(cassette_path),
        record_mode=_record_mode(),
        filter_headers=[
            ("authorization", "REDACTED"),
            ("api-key", "REDACTED"),
            ("openai-organization", "REDACTED"),
            ("x-api-key", "REDACTED"),
        ],
        match_on=["method", "scheme", "host", "port", "path", "query", "body"],
    )
