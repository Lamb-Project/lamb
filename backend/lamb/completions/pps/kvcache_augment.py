from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
import json
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

    last_message = messages[-1]['content']
    processed_messages = []

    if assistant:
        system_content = assistant.system_prompt or ""
        if document_context and isinstance(document_context, dict):
            doc_text = document_context.get("context", "")
            if doc_text:
                system_content = (system_content + "\n\n" + doc_text) if system_content else doc_text
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
                    context = rag_context.get("context", "") if isinstance(rag_context, dict) else str(rag_context)
                    sources_text = ""
                    if isinstance(rag_context, dict) and "sources" in rag_context:
                        sources = rag_context["sources"]
                        if sources:
                            sources_text = "\n\n## Available Sources\n\n"
                            for i, source in enumerate(sources, 1):
                                title = source.get("title", "Unknown")
                                url = source.get("url", "")
                                similarity = source.get("similarity", 0)
                                sources_text += f"{i}. [{title}]({url}) (similarity: {similarity:.3f})\n"
                    full_context = context + sources_text
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
                    context = rag_context.get("context", "") if isinstance(rag_context, dict) else str(rag_context)
                    sources_text = ""
                    if isinstance(rag_context, dict) and "sources" in rag_context:
                        sources = rag_context["sources"]
                        if sources:
                            sources_text = "\n\n## Available Sources\n\n"
                            for i, source in enumerate(sources, 1):
                                title = source.get("title", "Unknown")
                                url = source.get("url", "")
                                similarity = source.get("similarity", 0)
                                sources_text += f"{i}. [{title}]({url}) (similarity: {similarity:.3f})\n"
                    full_context = context + sources_text
                    prompt = prompt.replace("{context}", "\n\n" + full_context + "\n\n")
                else:
                    prompt = prompt.replace("{context}", "")

                processed_messages.append({
                    "role": messages[-1]['role'],
                    "content": prompt
                })
        else:
            processed_messages.append(messages[-1])

        return processed_messages

    return messages
