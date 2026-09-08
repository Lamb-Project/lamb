"""Default prompt_processor resolution for new assistants."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULTS_JSON_PATHS = (
    Path(__file__).parent.parent / "static" / "json" / "defaults.json",
    Path("/opt/lamb_v4/backend/static/json/defaults.json"),
    Path("static/json/defaults.json"),
    Path("backend/static/json/defaults.json"),
)


def default_prompt_processor() -> str:
    """Return the default PPS for new assistants."""
    return "kvcache_augment"


def load_defaults_json_document() -> dict[str, Any]:
    """Load defaults.json from disk."""
    for path in DEFAULTS_JSON_PATHS:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data.get("config"), dict):
            return data
        if isinstance(data, dict):
            return {"config": data}

    minimal = {
        "connector": "openai",
        "llm": "gpt-4o-mini",
        "prompt_processor": default_prompt_processor(),
        "rag_processor": "No RAG",
    }
    return {"config": minimal}
