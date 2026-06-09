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
import json
from typing import Any, Dict, List, Optional

from creator_interface.knowledge_store_client import KnowledgeStoreClient
from lamb.database_manager import LambDatabaseManager
from lamb.lamb_classes import Assistant
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="RAG")

_client = KnowledgeStoreClient()
_db = LambDatabaseManager()


def _serialize_assistant(assistant: Optional[Assistant]) -> Dict[str, Any]:
    """Best-effort JSON-safe view of the assistant for logging / response."""
    if not assistant:
        return {}
    out: Dict[str, Any] = {}
    for key in (
        "id", "name", "description", "system_prompt", "prompt_template",
        "RAG_collections", "RAG_Top_k", "published", "published_at", "owner",
    ):
        if hasattr(assistant, key):
            try:
                value = getattr(assistant, key)
                json.dumps({key: value})
                out[key] = value
            except (TypeError, OverflowError, Exception):
                out[key] = str(value)
    return out


def _build_user_dict_from_owner(owner_email: str) -> Dict[str, Any]:
    """Build the minimal ``creator_user`` dict the client expects.

    The client only uses ``email`` for org-config resolution, so we keep
    this lightweight rather than fetching the full row.
    """
    return {"email": owner_email}


async def _query_one_ks(
    ks_id: str,
    query_text: str,
    top_k: int,
    owner_email: str,
) -> Dict[str, Any]:
    """Query a single Knowledge Store and return the raw KB Server response.

    Resolves the embedding API key per-KS by looking up the locked vendor
    in LAMB DB and reading the org's provider key.
    """
    ks_entry = _db.get_knowledge_store(ks_id)
    if not ks_entry:
        return {"status": "error", "error": f"Knowledge Store {ks_id} not found in LAMB DB."}

    creator_user = _build_user_dict_from_owner(owner_email)
    embedding_api_key = _client.resolve_embedding_api_key(
        creator_user=creator_user,
        vendor=ks_entry["embedding_vendor"],
    )
    embedding_endpoint = ks_entry.get("embedding_endpoint") or ""

    try:
        response = await _client.query(
            knowledge_store_id=ks_id,
            query_text=query_text,
            top_k=top_k,
            embedding_api_key=embedding_api_key,
            embedding_api_endpoint=embedding_endpoint,
            creator_user=creator_user,
        )
        return {"status": "success", "data": response}
    except Exception as e:
        logger.error(f"Error querying Knowledge Store {ks_id}: {e}")
        return {"status": "error", "error": str(e)}


def _extract_sources(
    ks_id: str,
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build the LAMB-side ``sources`` list from KB Server query results.

    The new KB Server attaches permalink metadata to every chunk (set at
    ingestion time by ``knowledge_store_router.add_content``). Permalinks
    are LAMB-relative URLs into ``/docs/{org}/{lib}/{item}/...``, so they
    resolve through LAMB's ACL-enforced proxy.
    """
    sources: List[Dict[str, Any]] = []
    for chunk in results:
        meta = chunk.get("metadata", {}) or {}
        source: Dict[str, Any] = {
            "knowledge_store_id": ks_id,
            "title": meta.get("source_title")
                     or meta.get("title")
                     or meta.get("library_name")
                     or "Source",
            "score": chunk.get("score"),
            "source_item_id": meta.get("source_item_id"),
        }
        # Permalink URLs are sent into the KB Server as LAMB-relative paths
        # at ingestion time; surface whichever variants are present.
        for key in ("permalink_original", "permalink_markdown", "permalink_page"):
            if meta.get(key):
                source[key] = meta[key]
        if meta.get("library_id"):
            source["library_id"] = meta["library_id"]
        if meta.get("library_name"):
            source["library_name"] = meta["library_name"]
        # Pick a primary URL for renderers that use a single `url` field
        # (matches simple_rag's shape so the chat UI's citation renderer
        # works without changes).
        primary = (
            meta.get("permalink_page")
            or meta.get("permalink_markdown")
            or meta.get("permalink_original")
        )
        if primary:
            source["url"] = primary
        sources.append(source)
    return sources


async def _run(
    messages: List[Dict[str, Any]],
    assistant: Optional[Assistant],
    request: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Async core. The exported ``rag_processor`` wraps this in a sync runner
    if needed so it works under either the sync or async dispatch path."""
    logger.info(
        "Using knowledge_store_rag processor with assistant: %s",
        assistant.name if assistant else "None",
    )

    assistant_dict = _serialize_assistant(assistant)

    # Last user message is the query.
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

    # Run all KS queries concurrently — each is its own httpx call.
    raw_responses = await asyncio.gather(
        *[_query_one_ks(ks_id, last_user_message, top_k, owner_email) for ks_id in ks_ids],
        return_exceptions=False,
    )

    all_responses: Dict[str, Any] = {}
    sources: List[Dict[str, Any]] = []
    contexts: List[str] = []
    any_success = False

    for ks_id, result in zip(ks_ids, raw_responses):
        all_responses[ks_id] = result
        if result.get("status") == "success":
            any_success = True
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
    """RAG processor entry point — discovered automatically by the plugin
    loader (``backend/lamb/completions/main.py:load_plugins('rag')``).

    Async by design: the underlying KB Server client uses ``httpx.AsyncClient``
    and the dispatcher in ``get_rag_context`` already handles both sync and
    async processors.
    """
    return await _run(messages, assistant, request)
