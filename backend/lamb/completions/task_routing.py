"""
Helpers for routing lightweight completion tasks before the normal pipeline.
"""

import re
from typing import Any, Dict, List, Optional

from lamb.completions.small_fast_model_helper import invoke_small_fast_model
from lamb.logging_config import get_logger
from utils.langsmith_config import add_trace_metadata, is_tracing_enabled

logger = get_logger(__name__, component="API")

TITLE_GENERATION_PATTERNS = [
    r"generate.*title",
    r"create.*title",
    r"suggest.*title",
    r"generate.*tags",
    r"categorizing.*themes",
    r"chat history",
    r"conversation title",
    r"summarize.*conversation",
    r"task:\s*generate",
    r"output:\s*json\s*format",
    r"broad tags",
    r"subtopic tags",
    r"guidelines:",
    r"use the chat's primary language",
]


def _debug_print(message: str) -> None:
    """
    Temporary stdout diagnostics that bypass logger level filtering.
    """
    print(f"[task_routing] {message}", flush=True)


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return " ".join(text_parts)

    return ""


def is_title_generation_request(messages: List[Dict[str, Any]]) -> bool:
    """
    Detect Open WebUI-style title/tag generation requests from raw messages.
    """
    if not messages:
        return False

    last_message = messages[-1]
    content_lower = _extract_text_content(last_message.get("content", "")).lower().strip()
    if not content_lower:
        _debug_print("last message had no text content")
        return False

    preview = content_lower[:200]
    _debug_print(f"checking last message preview: {preview}")

    if content_lower.startswith("### task:") or "### task:" in content_lower:
        _debug_print("matched Open WebUI task marker")
        logger.debug("Detected title-generation request via Open WebUI task marker")
        return True

    for pattern in TITLE_GENERATION_PATTERNS:
        if re.search(pattern, content_lower):
            _debug_print(f"matched title pattern: {pattern}")
            logger.debug("Detected title-generation request via pattern '%s'", pattern)
            return True

    _debug_print("no title-generation pattern matched")
    return False


async def maybe_route_non_streaming_task(
    request: Dict[str, Any],
    assistant_owner: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    Route non-streaming lightweight task requests before RAG and PPS.
    """
    stream = bool(request.get("stream", False))
    _debug_print(f"received request stream={stream}")
    if stream:
        _debug_print("skipping fast path because request is streaming")
        if is_tracing_enabled():
            add_trace_metadata("request_kind", "chat")
            add_trace_metadata("task_fast_path", False)
        return None

    messages = request.get("messages", [])
    if not is_title_generation_request(messages):
        _debug_print("continuing normal pipeline")
        if is_tracing_enabled():
            add_trace_metadata("request_kind", "chat")
            add_trace_metadata("task_fast_path", False)
        return None

    if not assistant_owner:
        raise ValueError("Assistant owner is required for title-generation fast path")

    _debug_print("routing through non-streaming title fast path")
    logger.info("Routing title-generation request through non-streaming fast path")

    if is_tracing_enabled():
        add_trace_metadata("request_kind", "title_generation")
        add_trace_metadata("task_fast_path", True)
        add_trace_metadata("rag_skipped", True)
        add_trace_metadata("prompt_processor_skipped", True)

    response = await invoke_small_fast_model(
        messages=messages,
        assistant_owner=assistant_owner,
        stream=False,
        body=request,
    )

    _debug_print("completed non-streaming title fast path")
    logger.info("Completed title-generation fast path")
    return response
