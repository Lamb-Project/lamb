"""Build the ``sources`` payload that Open WebUI renders as a citations panel.

LAMB controls the full SSE stream to Open WebUI. OWI natively parses a
top-level ``sources`` field out of the stream, renders a clickable, persisted
citations panel, and auto-links inline ``[N]`` markers in the answer to it —
but only when the source's ``name`` is the literal string ``"N"`` and its
``url`` is an absolute ``http(s)`` link. This module maps LAMB's internal RAG
sources to that exact shape, minting org-scoped HMAC-signed "view" URLs so a
student can open the cited item without logging in.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

from config import LAMB_WEB_HOST
from creator_interface.permalink_signing import sign
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="RAG")


def _parse_permalink(source: Dict[str, Any]) -> Optional[tuple]:
    """Extract ``(org, lib, item, original_filename)`` from a source's permalinks.

    Permalinks have the form ``/docs/{org}/{lib}/{item}/...``; the original
    filename (when present) is the last segment of ``permalink_original``.
    """
    for key in ("permalink_markdown", "permalink_page", "permalink_original"):
        permalink = source.get(key)
        if permalink and permalink.startswith("/docs/"):
            parts = permalink.split("/")  # ['', 'docs', org, lib, item, ...]
            if len(parts) >= 5:
                org, lib, item = parts[2], parts[3], parts[4]
                filename = ""
                original = source.get("permalink_original")
                if original:
                    filename = original.rstrip("/").split("/")[-1]
                return org, lib, item, filename
    return None


def _signed_view_url(org: str, lib: str, item: str, filename: str) -> str:
    """Mint the absolute, org-scoped signed URL for a cited item's view page."""
    sig = sign(org, f"{org}/{lib}/{item}/view")
    base = LAMB_WEB_HOST.rstrip("/")
    return f"{base}/docs/public/{org}/{lib}/{item}/view?name={quote(filename)}&sig={sig}"


def build_owi_sources(rag_context: Any) -> List[Dict[str, Any]]:
    """Map LAMB RAG sources to Open WebUI's citations schema.

    Each entry is named with its 1-based citation number so OWI auto-links the
    inline ``[N]`` markers, carries the supporting excerpt under the real
    filename, and points at a signed view URL. Returns ``[]`` when there are no
    sources (so no citations event is emitted).
    """
    if not isinstance(rag_context, dict):
        return []
    owi: List[Dict[str, Any]] = []
    for src in rag_context.get("sources", []) or []:
        n = src.get("n")
        name = str(n) if n is not None else (src.get("title") or "?")
        text = src.get("text") or ""
        filename = src.get("title") or "Source"

        url = ""
        parsed = _parse_permalink(src)
        if parsed:
            org, lib, item, original_filename = parsed
            filename = original_filename or filename
            try:
                url = _signed_view_url(org, lib, item, filename)
            except Exception:  # noqa: BLE001 — never let citation building break a chat
                logger.warning("Failed to sign citation URL for source %s", name)

        excerpt = f"**{filename}**\n\n{text}" if text else f"**{filename}**"
        score = src.get("score")
        owi.append({
            # name == "N" so OWI links the inline [N] marker to this entry.
            "source": {"name": name, "url": url},
            "document": [excerpt],
            "metadata": [{"name": name, "filename": filename}],
            "distances": [score] if isinstance(score, (int, float)) else [],
        })
    return owi
