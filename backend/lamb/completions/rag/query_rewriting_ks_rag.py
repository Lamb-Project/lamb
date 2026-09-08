"""RAG processor with query rewriting backed by Knowledge Stores.

Combines the query-optimization logic from ``_query_rewriting_helper.py``
(small-fast-model generates an optimal search query from the full
conversation) with the Knowledge Store query pipeline from
``_ks_query_helpers.py`` (async httpx, per-request embedding
credentials, permalink-based citations).

When the small-fast-model is not configured for the organization, the
processor silently falls back to using the last user message as the
query — identical to ``knowledge_store_rag.py`` behavior.

Assistants opt into this by setting
``rag_processor='query_rewriting_ks_rag'`` in their plugin config.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from lamb.lamb_classes import Assistant
from lamb.logging_config import get_logger
from lamb.completions.rag._ks_query_helpers import (
    serialize_assistant,
    query_one_ks,
    _extract_sources,
)
from lamb.completions.rag._query_rewriting_helper import generate_optimal_query

logger = get_logger(__name__, component="RAG")


async def _run(
    messages: List[Dict[str, Any]],
    assistant: Optional[Assistant],
    request: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Async core."""
    logger.info(
        "Using query_rewriting_ks_rag processor with assistant: %s",
        assistant.name if assistant else "None",
    )

    assistant_dict = serialize_assistant(assistant)

    if not assistant or not getattr(assistant, "RAG_collections", None):
        return {
            "context": "No Knowledge Stores specified in the assistant configuration",
            "sources": [],
            "assistant_data": assistant_dict,
        }

    owner_email = getattr(assistant, "owner", "") or ""
    optimal_query = await generate_optimal_query(messages, owner_email)

    if not optimal_query:
        return {
            "context": "No user message found to use for the query",
            "sources": [],
            "assistant_data": assistant_dict,
        }

    ks_ids = [
        cid.strip()
        for cid in (assistant.RAG_collections or "").split(",")
        if cid.strip()
    ]
    if not ks_ids:
        return {
            "context": "RAG_collections is empty or improperly formatted",
            "sources": [],
            "assistant_data": assistant_dict,
        }

    top_k = getattr(assistant, "RAG_Top_k", 3) or 3

    logger.info(
        f"query_rewriting_ks_rag: querying {len(ks_ids)} KS(es) with query "
        f"'{optimal_query[:80]}...' (top_k={top_k})"
    )

    raw_responses = await asyncio.gather(
        *[query_one_ks(ks_id, optimal_query, top_k, owner_email) for ks_id in ks_ids],
        return_exceptions=False,
    )

    all_responses: Dict[str, Any] = {}
    sources: List[Dict[str, Any]] = []
    contexts: List[str] = []

    for ks_id, result in zip(ks_ids, raw_responses):
        all_responses[ks_id] = result
        if result.get("status") == "success":
            data = result.get("data", {}) or {}
            chunks = data.get("results", []) or []
            logger.info(f"KS {ks_id}: {len(chunks)} chunks returned")
            sources.extend(_extract_sources(ks_id, chunks))
            for chunk in chunks:
                text = chunk.get("text") or ""
                if text:
                    contexts.append(text)
        else:
            logger.warning(f"KS {ks_id}: {result.get('error', 'unknown error')}")

    combined_context = "\n\n".join(contexts) if contexts else ""

    return {
        "context": combined_context,
        "sources": sources,
        "assistant_data": assistant_dict,
        "raw_responses": all_responses,
    }


async def rag_processor(
    messages: List[Dict[str, Any]],
    assistant: Assistant = None,
    request: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """RAG processor entry point."""
    return await _run(messages, assistant, request)
