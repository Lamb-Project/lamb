from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
import json
import re
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="MAIN")

COMPATIBLE_RAG = [
    "library_file_rag",
    "knowledge_store_rag",
    "query_rewriting_ks_rag",
    "rubric_rag",
    "no_rag",
]

DEFAULT_RAG_PROMPT_TEMPLATE = (
    "Use the following context to answer the question. "
    "If the context does not contain the answer, say you do not know.\n\n"
    "Context:\n{context}\n\nQuestion: {user_input}"
)

CITATION_INSTRUCTION = (
    "When you use information from the context above, cite the supporting "
    "source inline using its bracketed number, e.g. [1] or [2][3]. Place the "
    "citation immediately after the statement it supports. Only cite numbers "
    "that appear in the context; do not invent citations."
)


def _build_full_context(rag_context: Any, cite: bool = True) -> str:
    """Build the text that replaces ``{context}``.

    The retrieved context is already prefixed per chunk with ``[N]`` markers by
    the KS RAG processor. When ``cite`` is True we keep those markers and append
    the inline citation instruction so the model cites — the clickable source
    list is then rendered separately (see ``lamb.completions.citation_sources``).

    When ``cite`` is False (the assistant did NOT opt in to exposing sources),
    we strip the ``[N]`` prefixes and omit the instruction, so the answer has no
    citation markers at all — students never see ``[1]`` pointing at a source
    they cannot open.
    """
    if not isinstance(rag_context, dict):
        return str(rag_context) if rag_context else ""
    context = rag_context.get("context", "") or ""
    sources = rag_context.get("sources", []) or []
    if sources and cite:
        return context + "\n\n" + CITATION_INSTRUCTION
    if not cite and context:
        # Drop the per-chunk "[N] " citation prefixes so the model has no cue
        # to emit citation markers it cannot link to.
        context = re.sub(r"(?m)^\[\d+\]\s+", "", context)
    return context


def _exposes_sources(assistant: Assistant) -> bool:
    """Whether this assistant opts in to student-clickable cited sources.

    Mirrors ``_has_vision_capability``; defaults to False so citations are only
    produced when the creator enabled ``capabilities.expose_sources``.
    """
    if not assistant:
        return False
    metadata_str = getattr(assistant, 'metadata', None) or getattr(assistant, 'api_callback', None)
    if not metadata_str:
        return False
    try:
        capabilities = json.loads(metadata_str).get('capabilities', {}) or {}
        return bool(capabilities.get('expose_sources', False))
    except (json.JSONDecodeError, AttributeError):
        return False


def _has_vision_capability(assistant: Assistant) -> bool:
    if not assistant:
        return False
    metadata_str = getattr(assistant, 'metadata', None) or getattr(assistant, 'api_callback', None)
    if not metadata_str:
        return False
    try:
        metadata = json.loads(metadata_str)
        capabilities = metadata.get('capabilities', {})
        return capabilities.get('vision', False)
    except (json.JSONDecodeError, AttributeError):
        return False


def _has_image_generation_capability(assistant: Assistant) -> bool:
    if not assistant:
        return False
    metadata_str = getattr(assistant, 'metadata', None) or getattr(assistant, 'api_callback', None)
    if not metadata_str:
        return False
    try:
        metadata = json.loads(metadata_str)
        capabilities = metadata.get('capabilities', {})
        return capabilities.get('image_generation', False)
    except (json.JSONDecodeError, AttributeError):
        return False


def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None,
    document_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    messages = request.get('messages', [])
    if not messages:
        return messages

    # Only cite (inline [N] markers + clickable sources) when the assistant
    # opted in to exposing sources; otherwise produce no citation markers.
    cite = _exposes_sources(assistant)

    last_message = messages[-1]['content']
    processed_messages = []

    if assistant:
        system_content = assistant.system_prompt or ""
        if document_context and isinstance(document_context, dict):
            doc_text = document_context.get("context", "")
            if doc_text:
                labeled_doc = (
                    "\n\n## REFERENCE DOCUMENT\n\n"
                    "This document has been selected by the assistant creator as a reference "
                    "that will likely be useful for many queries, as it is generally a helpful "
                    "document. Use it as context when answering questions.\n\n"
                    f"{doc_text}"
                    "\n\nIMPORTANT: The reference document above is available for this entire "
                    "conversation. Always consider it alongside any retrieved context when "
                    "answering questions. If the user's question relates to the document's "
                    "content, use it."
                )
                system_content = (labeled_doc + "\n\n" + system_content) if system_content else labeled_doc
        if system_content:
            processed_messages.append({
                "role": "system",
                "content": system_content
            })

        processed_messages.extend(messages[:-1])

        if assistant.prompt_template:
            has_vision = _has_vision_capability(assistant)

            if isinstance(last_message, list) and has_vision:
                augmented_content = []
                text_parts = []
                for item in last_message:
                    if item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                user_input_text = ' '.join(text_parts)

                logger.debug(f"User message: {user_input_text}")
                augmented_text = assistant.prompt_template.replace("{user_input}", "\n\n" + user_input_text + "\n\n")

                if rag_context:
                    full_context = _build_full_context(rag_context, cite)
                    augmented_text = augmented_text.replace("{context}", "\n\n" + full_context + "\n\n")
                else:
                    augmented_text = augmented_text.replace("{context}", "")

                augmented_content.append({"type": "text", "text": augmented_text})
                for item in last_message:
                    if item.get('type') != 'text':
                        augmented_content.append(item)

                processed_messages.append({
                    "role": messages[-1]['role'],
                    "content": augmented_content
                })
            else:
                if isinstance(last_message, list):
                    text_parts = []
                    for item in last_message:
                        if item.get('type') == 'text':
                            text_parts.append(item.get('text', ''))
                    user_input_text = ' '.join(text_parts)
                else:
                    user_input_text = str(last_message)

                logger.debug(f"User message: {user_input_text}")
                prompt = assistant.prompt_template.replace("{user_input}", "\n\n" + user_input_text + "\n\n")

                if rag_context:
                    full_context = _build_full_context(rag_context, cite)
                    prompt = prompt.replace("{context}", "\n\n" + full_context + "\n\n")
                else:
                    prompt = prompt.replace("{context}", "")

                processed_messages.append({
                    "role": messages[-1]['role'],
                    "content": prompt
                })
        else:
            effective_template = None
            if rag_context:
                context_text = (
                    rag_context.get("context", "")
                    if isinstance(rag_context, dict)
                    else str(rag_context)
                )
                if context_text:
                    effective_template = DEFAULT_RAG_PROMPT_TEMPLATE

            if effective_template:
                if isinstance(last_message, list):
                    text_parts = []
                    for item in last_message:
                        if item.get('type') == 'text':
                            text_parts.append(item.get('text', ''))
                    user_input_text = ' '.join(text_parts)
                else:
                    user_input_text = str(last_message)

                prompt = effective_template.replace("{user_input}", "\n\n" + user_input_text + "\n\n")
                full_context = _build_full_context(rag_context, cite)
                prompt = prompt.replace("{context}", "\n\n" + full_context + "\n\n")

                processed_messages.append({
                    "role": messages[-1]['role'],
                    "content": prompt
                })
            else:
                processed_messages.append(messages[-1])

        return processed_messages

    return messages
