"""RAG processor backed by the new KB Server (Knowledge Stores).

Sibling of ``simple_rag.py`` — kept entirely separate so the legacy stable
KB Server retrieval path (port 9090) is not touched (ADR-KS-12 of the plan).

How it differs from simple_rag:

- Targets the new KB Server (port 9092) via the ``KnowledgeStoreClient``
  with per-request embedding credentials (ADR-4 of issue #334).
- Each KS has its own locked embedding vendor / model, so the processor
  looks up the LAMB ``knowledge_stores`` row per collection ID to know
  which provider's API key to send.
- Citations carry permalinks pointing at LAMB's ``/docs/...`` proxy (set
  by the router when ingesting), so links resolve via LAMB ACL.

Assistants opt into this by setting ``rag_processor='knowledge_store_rag'``
in their plugin config; legacy assistants keep ``simple_rag`` and continue
to hit the stable server unchanged.
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

logger = get_logger(__name__, component="RAG")


async def _run(
    messages: List[Dict[str, Any]],
    assistant: Optional[Assistant],
    request: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Async core."""
    logger.info(
        "Using knowledge_store_rag processor with assistant: %s",
        assistant.name if assistant else "None",
    )

    assistant_dict = serialize_assistant(assistant)

    last_user_message = ""
    for msg in reversed(messages or []):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "") or ""
            break

    if not assistant or not getattr(assistant, "RAG_collections", None):
        return {
            "context": "No Knowledge Stores specified in the assistant configuration",
            "sources": [],
            "assistant_data": assistant_dict,
        }

    if not last_user_message:
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
    owner_email = getattr(assistant, "owner", "") or ""

    logger.info(
        f"knowledge_store_rag: querying {len(ks_ids)} KS(es) for assistant "
        f"{getattr(assistant, 'id', '?')} (top_k={top_k})"
    )

    raw_responses = await asyncio.gather(
        *[query_one_ks(ks_id, last_user_message, top_k, owner_email) for ks_id in ks_ids],
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
