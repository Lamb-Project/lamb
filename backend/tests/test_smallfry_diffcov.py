"""Diff-coverage tests for three small feature-added gaps (label: smallfry).

Covers, in one file:

1. ``creator_interface.main`` lines 3-6 — the feature-added
   ``knowledge_store_router`` / ``knowledge_store_graph_router`` import
   lines. See ``test_creator_interface_main_imports`` for why these are
   import-time-only and the fallback handling.
2. ``creator_interface.knowledges_router`` line 237 —
   ``load_dotenv(override=True)`` (module top-level). Reached by importing
   the module.
3. ``lamb.completions.pps.simple_augment`` line 144 — the vision /
   multimodal augmentation branch (``effective_template.replace`` of
   ``{user_input}`` for a list-type message on a vision-capable assistant).
"""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

# Make ``backend/`` importable (mirrors conftest) so ``config`` etc. resolve.
_BACKEND_ROOT = Path(__file__).parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


# ---------------------------------------------------------------------------
# Target 3: simple_augment line 144 (vision multimodal {user_input} replace)
# ---------------------------------------------------------------------------


def _make_vision_assistant(prompt_template: str):
    from lamb.lamb_classes import Assistant

    return Assistant(
        id=1,
        organization_id=1,
        name="Vision Assistant",
        description="",
        owner="user@example.com",
        # metadata maps to api_callback; capabilities.vision=True turns on the
        # multimodal branch in simple_augment.
        api_callback=json.dumps({"capabilities": {"vision": True}}),
        system_prompt="You are a helper.",
        prompt_template=prompt_template,
        pre_retrieval_endpoint="",
        post_retrieval_endpoint="",
        RAG_endpoint="",
        RAG_Top_k=3,
        RAG_collections="",
    )


def test_simple_augment_vision_multimodal_user_input_substitution():
    """Line 144: a vision-enabled assistant whose last message is a list of
    content parts must substitute ``{user_input}`` with the joined text parts
    while preserving non-text (image) parts."""
    from lamb.completions.pps.simple_augment import prompt_processor

    assistant = _make_vision_assistant(
        prompt_template="Answer: {user_input}\nContext: {context}"
    )

    request = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What"},
                    {"type": "text", "text": "is this?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAAA"},
                    },
                ],
            }
        ]
    }

    result = prompt_processor(
        request,
        assistant=assistant,
        rag_context={"context": "Some retrieved context."},
    )

    # Last processed message is the augmented multimodal user message.
    augmented = result[-1]
    assert augmented["role"] == "user"
    content = augmented["content"]
    assert isinstance(content, list)

    # First element is the augmented text with {user_input} replaced (line 144).
    text_part = content[0]
    assert text_part["type"] == "text"
    assert "What is this?" in text_part["text"]
    assert "Some retrieved context." in text_part["text"]

    # Original image part is preserved.
    assert any(part.get("type") == "image_url" for part in content)


def test_simple_augment_vision_multimodal_without_rag_context():
    """Same multimodal branch but with no rag_context, so {context} is
    stripped — still exercises the {user_input} replace on line 144."""
    from lamb.completions.pps.simple_augment import prompt_processor

    assistant = _make_vision_assistant(
        prompt_template="Q: {user_input} / {context}"
    )

    request = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the picture"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,BBBB"},
                    },
                ],
            }
        ]
    }

    result = prompt_processor(request, assistant=assistant, rag_context=None)

    text_part = result[-1]["content"][0]
    assert "Describe the picture" in text_part["text"]
    # No context placeholder left dangling.
    assert "{context}" not in text_part["text"]


# ---------------------------------------------------------------------------
# Target 2: knowledges_router line 237 (load_dotenv(override=True))
# ---------------------------------------------------------------------------


def _ensure_owi_db_exists() -> None:
    """``OwiDatabaseManager.__init__`` blocks in a poll loop until the OWI
    ``webui.db`` file exists. Create an (empty) sqlite file at the configured
    path so importing knowledges_router does not hang. The managers tolerate a
    table-less DB at import time (they only log errors)."""
    import config

    owi_path = config.OWI_PATH
    assert owi_path, "OWI_PATH must be configured for this test"
    os.makedirs(owi_path, exist_ok=True)
    db_path = os.path.join(owi_path, "webui.db")
    if not os.path.exists(db_path):
        sqlite3.connect(db_path).close()


def test_knowledges_router_module_imports():
    """Line 237: importing the module executes the top-level
    ``load_dotenv(override=True)`` and the rest of the module body."""
    os.environ.setdefault("LAMB_KB_SERVER_TOKEN", "test-token")
    _ensure_owi_db_exists()

    mod = importlib.import_module("creator_interface.knowledges_router")
    # Re-import to be explicit even if another test already loaded it.
    importlib.reload(mod) if mod.__name__ in sys.modules else None

    assert mod.router is not None
    assert hasattr(mod, "KB_SERVER_CONFIGURED")


# ---------------------------------------------------------------------------
# Target 1: creator_interface.main lines 3-6 (knowledge_store router imports)
# ---------------------------------------------------------------------------


def test_creator_interface_main_imports():
    """Lines 3-6: feature-added ``knowledge_store_router`` /
    ``knowledge_store_graph_router`` import statements at the top of
    ``creator_interface/main.py``.

    Importing the module executes those lines, but the import chain reaches
    ``creator_interface.evaluaitor_router`` -> ``lamb.evaluaitor.ai_generator``
    -> ``from openai import OpenAI``, and the ``openai`` package is not
    installed in the test environment. If it ever becomes importable here this
    test covers the lines; otherwise it is skipped and the lines carry a
    ``# pragma: no cover`` justified by this exact constraint."""
    os.environ.setdefault("LAMB_KB_SERVER_TOKEN", "test-token")
    _ensure_owi_db_exists()

    try:
        import openai  # noqa: F401
    except Exception:
        pytest.skip(
            "openai package is not installed in the test environment; "
            "creator_interface.main cannot be imported, so lines 3-6 carry "
            "# pragma: no cover."
        )

    mod = importlib.import_module("creator_interface.main")
    assert hasattr(mod, "knowledge_store_router")
    assert hasattr(mod, "knowledge_store_graph_router")
