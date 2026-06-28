"""Shared helpers for Knowledge Store RAG processors.

Extracted from ``knowledge_store_rag.py`` so that sibling processors
(e.g. ``query_rewriting_ks_rag``) can reuse the same query and
source-extraction logic without code duplication.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from creator_interface.knowledge_store_client import KnowledgeStoreClient
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="RAG")

_client = KnowledgeStoreClient()
_db = LambDatabaseManager()


def serialize_assistant(assistant) -> Dict[str, Any]:
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
            except Exception:
                out[key] = str(value)
    return out


def build_user_dict_from_owner(owner_email: str) -> Dict[str, Any]:
    """Build the minimal ``creator_user`` dict the client expects."""
    return {"email": owner_email}


async def query_one_ks(
    ks_id: str,
    query_text: str,
    top_k: int,
    owner_email: str,
) -> Dict[str, Any]:
    """Query a single Knowledge Store and return the raw KB Server response."""
    ks_entry = _db.get_knowledge_store(ks_id)
    if not ks_entry:
        return {"status": "error", "error": f"Knowledge Store {ks_id} not found in LAMB DB."}

    creator_user = build_user_dict_from_owner(owner_email)
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


def _build_source(ks_id: str, chunk: Dict[str, Any]) -> Dict[str, Any]:
    """Build a single LAMB-side ``source`` dict from one KB Server chunk."""
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
    for key in ("permalink_original", "permalink_markdown", "permalink_page"):
        if meta.get(key):
            source[key] = meta[key]
    if meta.get("library_id"):
        source["library_id"] = meta["library_id"]
    if meta.get("library_name"):
        source["library_name"] = meta["library_name"]
    primary = (
        meta.get("permalink_page")
        or meta.get("permalink_markdown")
        or meta.get("permalink_original")
    )
    if primary:
        source["url"] = primary
    return source


def _extract_sources(
    ks_id: str,
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build the LAMB-side ``sources`` list from KB Server query results."""
    return [_build_source(ks_id, chunk) for chunk in results]


def build_context_and_sources(
    ks_results: List[tuple],
) -> tuple:
    """Build the numbered RAG context and an aligned ``sources`` list.

    ``ks_results`` is a list of ``(ks_id, chunks)`` pairs for the Knowledge
    Stores that returned successfully. Every chunk that carries text is given
    a stable 1-based citation number ``n``: its context block is prefixed with
    ``[n]`` and the matching source dict carries the same ``n``. This lets the
    LLM cite inline with ``[N]`` markers while the caller renders a numbered
    sources list that lines up exactly with those markers.

    Returns ``(combined_context, sources)``.
    """
    context_parts: List[str] = []
    sources: List[Dict[str, Any]] = []
    n = 0
    for ks_id, chunks in ks_results:
        for chunk in chunks or []:
            text = (chunk.get("text") or "").strip()
            if not text:
                continue
            n += 1
            context_parts.append(f"[{n}] {text}")
            source = _build_source(ks_id, chunk)
            source["n"] = n
            # Keep the chunk text on the source so the citation UI can show the
            # supporting excerpt (e.g. OWI's citations panel).
            source["text"] = text
            sources.append(source)
    combined_context = "\n\n".join(context_parts) if context_parts else ""
    return combined_context, sources
