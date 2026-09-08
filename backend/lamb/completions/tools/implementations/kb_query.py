"""
KB Query tool stub — retrieves relevant context from the knowledge base.

MVP: returns a stub result. Phase 3+ wires the real KB server call.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def run_kb_query(args: dict) -> dict:
    """Search the knowledge base for relevant information.

    Expected args:
        query (str): The search query.

    Returns:
        dict with success bool and results list.
    """
    query = (args.get("query") or "").strip()
    if not query:
        return {"success": False, "error": "No query provided"}

    logger.info("kb_query called: query=%r", query)

    # TODO: Replace with actual RAG/KB server retrieval in Phase 3
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