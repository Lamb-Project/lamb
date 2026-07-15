from __future__ import annotations

import copy
from typing import Any

_CACHE_CONTROL = {"type": "ephemeral"}


def apply_cache_markers(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a deep copy of messages with explicit-cache content shape.

    Marker is placed on the second-to-last message (stable prefix before latest user turn).
    Single-message requests get the marker on that sole message.
    """
    if not messages:
        return messages

    marker_index = len(messages) - 2 if len(messages) >= 2 else 0
    out: list[dict[str, Any]] = []

    for i, msg in enumerate(messages):
        new_msg = copy.deepcopy(msg)
        new_msg["content"] = _to_cacheable_content(
            msg.get("content", ""),
            add_marker=(i == marker_index),
        )
        out.append(new_msg)

    return out


def _to_cacheable_content(content: Any, *, add_marker: bool) -> list[dict[str, Any]]:
    if isinstance(content, str):
        block: dict[str, Any] = {"type": "text", "text": content}
        if add_marker:
            block["cache_control"] = _CACHE_CONTROL.copy()
        return [block]

    if isinstance(content, list):
        parts: list[dict[str, Any]] = []
        last_text_idx = None
        for idx, item in enumerate(content):
            if isinstance(item, dict) and item.get("type") == "text":
                last_text_idx = idx
            parts.append(copy.deepcopy(item) if isinstance(item, dict) else item)

        if add_marker:
            if last_text_idx is not None:
                parts[last_text_idx] = dict(parts[last_text_idx])
                parts[last_text_idx]["cache_control"] = _CACHE_CONTROL.copy()
            else:
                parts.append({
                    "type": "text",
                    "text": "",
                    "cache_control": _CACHE_CONTROL.copy(),
                })
        return parts

    block = {"type": "text", "text": str(content)}
    if add_marker:
        block["cache_control"] = _CACHE_CONTROL.copy()
    return [block]
