"""
Helpers for routing lightweight completion tasks before the normal pipeline.
"""

from typing import Any, Dict, Optional

from lamb.completions.small_fast_model_helper import invoke_small_fast_model
from lamb.logging_config import get_logger
from utils.langsmith_config import add_trace_metadata, is_tracing_enabled

logger = get_logger(__name__, component="API")


def _debug_print(message: str) -> None:
    """
    Temporary stdout diagnostics that bypass logger level filtering.
    """
    print(f"[task_routing] {message}", flush=True)


def is_task_request(request: Dict[str, Any]) -> bool:
    """
    Detect Open WebUI task requests by the presence of ``request["metadata"]["task"]``.

    Open WebUI sets this field for all auxiliary tasks (title_generation,
    tags_generation, query_generation, etc.) — see open_webui/constants.py.
    Any request carrying this field is routed to the small-fast model.
    """
    task_type = request.get("metadata", {}).get("task", "")
    if task_type:
        _debug_print(f"detected OWI task metadata.task='{task_type}'")
        logger.debug(
            "Detected OWI task request via metadata.task='%s'", task_type)
        return True
    _debug_print("no metadata.task field found")
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

    if not is_task_request(request):
        _debug_print("continuing normal pipeline")
        if is_tracing_enabled():
            add_trace_metadata("request_kind", "chat")
            add_trace_metadata("task_fast_path", False)
        return None

    if not assistant_owner:
        raise ValueError(
            "Assistant owner is required for title-generation fast path")

    task_type = request.get("metadata", {}).get("task", "title_generation")
    _debug_print(f"routing task '{task_type}' through non-streaming fast path")
    logger.info(
        "Routing OWI task '%s' request through non-streaming fast path", task_type)

    if is_tracing_enabled():
        add_trace_metadata("request_kind", task_type)
        add_trace_metadata("task_fast_path", True)
        add_trace_metadata("rag_skipped", True)
        add_trace_metadata("prompt_processor_skipped", True)

    messages = request.get("messages", [])
    response = await invoke_small_fast_model(
        messages=messages,
        assistant_owner=assistant_owner,
        stream=False,
        body=request,
    )

    _debug_print(f"completed fast path for task '{task_type}'")
    logger.info("Completed fast path for OWI task '%s'", task_type)
    return response
