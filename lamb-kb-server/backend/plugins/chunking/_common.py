"""Shared helpers for chunking plugins.

Provides ``build_base_metadata`` (attaches standard LAMB fields to every chunk)
and ``encode_list`` (encodes Python lists as pipe-separated strings so that
ChromaDB — which only accepts primitive metadata values — never receives a list).
"""

from __future__ import annotations

import json
from typing import Any

from plugins.base import DocumentInput


def build_base_metadata(
    document: DocumentInput,
    strategy: str,
    chunking_params: dict[str, Any],
) -> dict[str, Any]:
    """Return the standard metadata dict shared by every chunk of *document*.

    ChromaDB accepts only primitive values (str, int, float, bool, None).
    Lists must be encoded before being stored — use :func:`encode_list` for
    that purpose.  This function does NOT encode lists; caller-supplied
    ``extra_metadata`` is merged verbatim last so LAMB-provided values win.

    Args:
        document: The source document being chunked.
        strategy: Human-readable strategy name (e.g. ``"simple"``).
        chunking_params: Strategy-specific parameter dict whose entries are
            stored as ``chunking_<key>`` keys for auditability.

    Returns:
        A flat metadata dict containing only primitive-compatible values from
        ``document``; callers may add more keys before attaching to a
        :class:`~plugins.base.Chunk`.
    """
    permalinks: dict[str, Any] = document.permalinks or {}

    md: dict[str, Any] = {
        "source_item_id": document.source_item_id,
        "source_title": document.title,
        "chunking_strategy": strategy,
        "permalink_original": permalinks.get("original", ""),
        "permalink_markdown": permalinks.get("full_markdown", ""),
    }

    # Pages permalinks: store the first one by default; by_page overrides
    # this per-chunk with the matching page permalink.
    pages_list = permalinks.get("pages") or []
    if isinstance(pages_list, list) and pages_list:
        md["permalink_page"] = pages_list[0]

    # Merge chunking params as flat keys for auditability
    if chunking_params:
        for k, v in chunking_params.items():
            md[f"chunking_{k}"] = v

    # Merge extra_metadata LAST so caller-provided values win over defaults
    for k, v in (document.extra_metadata or {}).items():
        md[k] = v

    return md


def encode_list(values: list[Any], sep: str = "|") -> str:
    """Encode a list of values as a single string safe for ChromaDB metadata.

    ChromaDB metadata values must be primitives (str/int/float/bool/None).
    Lists are NOT accepted.  This helper joins the list elements with *sep*
    (default ``"|"``) so the information survives a round-trip through the
    store without requiring a JSON parser on the read side.

    >>> encode_list(["Introduction", "Setup"])
    'Introduction|Setup'
    >>> encode_list([1, 2, 3])
    '1|2|3'
    """
    return sep.join(str(x) for x in values)


def encode_list_json(values: list[Any]) -> str:
    """Encode a list as a compact JSON string — use when ``|`` is ambiguous.

    >>> encode_list_json([1, 3, 5])
    '[1, 3, 5]'
    """
    return json.dumps(values, ensure_ascii=False)
