"""
KB Query tool — retrieves relevant context from the assistant's knowledge base.

Uses the same KB server retrieval path as ``simple_rag``: the assistant's
comma-separated ``RAG_collections`` + ``RAG_Top_k``, resolved against the
owner's organization KB config (with a global env fallback). When the
assistant has no collections configured, falls back to the legacy stub so the
tool never hard-fails the conversation.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _stub_result(query: str) -> dict:
    """Backward-compatible placeholder when no KB is configured."""
    return {
        "success": True,
        "results": [
            {
                "content": f"[Stub result for query: {query}]",
                "similarity": 0.95,
                "source": "knowledge_base",
            }
        ],
    }


async def run_kb_query(
    args: dict,
    *,
    assistant: Any = None,
    request: Optional[dict] = None,
) -> dict:
    """Search the assistant's knowledge base for relevant information.

    Expected args:
        query (str): The search query.

    Args:
        assistant: Assistant object (carries RAG_collections / RAG_Top_k / owner).
        request: Original completion request (unused; kept for tool-loop symmetry).

    Returns:
        dict with success bool and results list. Each result carries
        ``content`` (chunk text), ``similarity`` and ``metadata``.
    """
    query = (args.get("query") or "").strip()
    if not query:
        return {"success": False, "error": "No query provided"}

    logger.info("kb_query called: query=%r", query)

    collections_str = getattr(assistant, "RAG_collections", None) if assistant else None
    collections = [
        cid.strip() for cid in (collections_str or "").split(",") if cid.strip()
    ]
    if not collections:
        logger.info("kb_query: no RAG_collections configured — returning stub result")
        return _stub_result(query)

    top_k = getattr(assistant, "RAG_Top_k", None) or 3
    owner = getattr(assistant, "owner", None)

    # Late import: keeps the tool importable without pulling creator_interface.
    from lamb.modules.workshop.kb import config_for_owner, query_kb_collection

    try:
        config = config_for_owner(owner)
    except Exception as e:
        logger.error("kb_query: KB config resolution failed: %s", e)
        return {"success": False, "error": f"KB not configured: {e}"}

    results = []
    try:
        for collection_id in collections:
            response = await query_kb_collection(
                config, collection_id, query, top_k)
            for item in response.get("results", []):
                results.append({
                    "content": item.get("data", ""),
                    "similarity": item.get("similarity"),
                    "metadata": item.get("metadata", {}),
                })
    except Exception as e:
        logger.error("kb_query: KB retrieval failed: %s", e)
        return {"success": False, "error": f"KB query failed: {e}"}

    return {"success": True, "results": results, "count": len(results)}
