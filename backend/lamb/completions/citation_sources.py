"""Render RAG citations so a student can click through to the cited item.

Open WebUI's backend, on the normal (websocket) chat path, forwards only the
assistant's ``content`` from an external model's stream — it drops any
top-level ``sources`` field (it renders only sources it generates itself). So
to surface clickable citations through OWI we append a Markdown **Sources**
section to the answer content; OWI renders it like any other markdown.

Each source links to a LAMB-served view page via an org-scoped, HMAC-signed
"capability" URL (see ``creator_interface.permalink_signing``) so a logged-out
student can open the cited item. The inline ``[N]`` markers in the body point
at the numbered list.

``build_owi_sources`` (the OWI ``sources`` schema) is kept for non-streaming /
spec-compliant clients that *do* consume the field.
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


def build_sources_markdown(rag_context: Any) -> str:
    """Build a Markdown 'Sources' section appended to the answer content.

    Sources are grouped by library item (chunks are numbered individually by
    the RAG processor, but several chunks often come from the same document).
    Each line lists every citation number that points at the item followed by a
    clickable link, e.g. ``[1][3][5] [cv.pdf](https://…/view?…)`` — so every
    inline ``[N]`` marker in the answer resolves to a clickable entry. Returns
    ``""`` when there are no sources. Lines deliberately avoid the ``[N]: url``
    reference-definition form, which OWI strips.
    """
    if not isinstance(rag_context, dict):
        return ""
    groups: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for src in rag_context.get("sources", []) or []:
        n = src.get("n")
        filename = src.get("title") or "Source"
        url = ""
        parsed = _parse_permalink(src)
        item_key = None
        if parsed:
            org, lib, item, original_filename = parsed
            item_key = f"{org}/{lib}/{item}"
            filename = original_filename or filename
            try:
                url = _signed_view_url(org, lib, item, filename)
            except Exception:  # noqa: BLE001 — never let citation building break a chat
                logger.warning("Failed to sign citation URL for source %s", n)
        key = item_key or f"_{n}"
        if key not in groups:
            groups[key] = {"ns": [], "filename": filename, "url": url}
            order.append(key)
        if n is not None:
            groups[key]["ns"].append(n)

    if not order:
        return ""
    lines: List[str] = []
    for key in order:
        g = groups[key]
        marks = "".join(f"[{n}]" for n in sorted(g["ns"])) or "-"
        link = f"[{g['filename']}]({g['url']})" if g["url"] else g["filename"]
        lines.append(f"{marks} {link}")
    return "\n\n---\n\n**Sources**\n\n" + "\n\n".join(lines) + "\n"


def build_owi_sources(rag_context: Any) -> List[Dict[str, Any]]:
    """Map LAMB RAG sources to Open WebUI's citations schema.

    Kept for non-streaming responses and any spec-compliant client that
    consumes a top-level ``sources`` field. (OWI's websocket chat path drops
    this for external models — the Markdown section above is what reaches the
    student there.)
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
            except Exception:  # noqa: BLE001
                logger.warning("Failed to sign citation URL for source %s", name)
        excerpt = f"**{filename}**\n\n{text}" if text else f"**{filename}**"
        score = src.get("score")
        owi.append({
            "source": {"name": name, "url": url},
            "document": [excerpt],
            "metadata": [{"name": name, "filename": filename}],
            "distances": [score] if isinstance(score, (int, float)) else [],
        })
    return owi
