from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
import json
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="MAIN")

# Default prompt template used when an assistant is configured with a real
# RAG processor (knowledge_store_rag, simple_rag, …) but no explicit
# prompt_template. Without this default, simple_augment would silently drop
# the retrieved ``rag_context`` because the empty template contains no
# ``{context}`` placeholder, which looks like "RAG retrieves but the LLM
# never sees it" to the user. Kept in sync with the lamb-cli default
# (lifecycle verification 2026-05-03 — see lamb-cli/src/lamb_cli/commands/
# assistant.py).
DEFAULT_RAG_PROMPT_TEMPLATE = (
    "Use the following context to answer the question. "
    "If the context does not contain the answer, say you do not know.\n\n"
    "Context:\n{context}\n\nQuestion: {user_input}"
)


def _has_vision_capability(assistant: Assistant) -> bool:
    """
    Check if the assistant has vision capabilities enabled.

    Args:
        assistant: Assistant object with metadata

    Returns:
        bool: True if vision is enabled, False otherwise
    """
    if not assistant:
        return False

    # Check if assistant has metadata (stored in api_callback column)
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
    """
    Check if the assistant has image generation capabilities enabled.

    Args:
        assistant: Assistant object with metadata

    Returns:
        bool: True if image generation is enabled, False otherwise
    """
    if not assistant:
        return False

    # Check if assistant has metadata (stored in api_callback column)
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
    """
    Simple augment prompt processor that:
    1. Uses system prompt from assistant if available
    2. Replaces last message with prompt template, substituting:
       - {user_input} with the original message
       - {context} with RAG context if available
    """
    messages = request.get('messages', [])
    if not messages:
        return messages

    # Get the last user message
    last_message = messages[-1]['content']

    # Create new messages list
    processed_messages = []

    if assistant:
        # Build system prompt with optional document context
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

        # Add previous messages except the last one
        processed_messages.extend(messages[:-1])

        # If RAG context was produced but the assistant has an empty / missing
        # prompt template, substitute the default template so the retrieved
        # chunks actually reach the LLM. Otherwise the {context} substitution
        # below would silently drop them. (Defect D3 — lifecycle 2026-05-03.)
        effective_template = assistant.prompt_template
        if (not effective_template) and rag_context:
            context_text = (
                rag_context.get("context", "")
                if isinstance(rag_context, dict)
                else str(rag_context)
            )
            if context_text:
                logger.info(
                    "simple_augment: applying DEFAULT_RAG_PROMPT_TEMPLATE "
                    "because assistant has empty prompt_template but "
                    "rag_context is present (defect D3 fallback)."
                )
                effective_template = DEFAULT_RAG_PROMPT_TEMPLATE

        # Process the last message using the prompt template
        if effective_template:
            # Check if assistant has vision capabilities
            has_vision = _has_vision_capability(assistant)

            if isinstance(last_message, list) and has_vision:
                # Multimodal content with vision-enabled assistant
                # Preserve images while applying template augmentations
                augmented_content = []

                # Extract text parts for {user_input} substitution
                text_parts = []
                for item in last_message:
                    if item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))

                user_input_text = ' '.join(text_parts)

                # Create augmented text content with template
                logger.debug(f"User message: {user_input_text}")
                augmented_text = effective_template.replace("{user_input}", "\n\n" + user_input_text + "\n\n")

                # Add RAG context if available
                if rag_context:
                    context = rag_context.get("context", "") if isinstance(rag_context, dict) else str(rag_context)
                    
                    # Format sources if available
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
                    
                    # Combine context with sources
                    full_context = context + sources_text
                    augmented_text = augmented_text.replace("{context}", "\n\n" + full_context + "\n\n")
                else:
                    augmented_text = augmented_text.replace("{context}", "")

                # Add the augmented text as first element
                augmented_content.append({
                    "type": "text",
                    "text": augmented_text
                })

                # Preserve all non-text elements (images, etc.)
                for item in last_message:
                    if item.get('type') != 'text':
                        augmented_content.append(item)

                # Add processed multimodal message
                processed_messages.append({
                    "role": messages[-1]['role'],
                    "content": augmented_content
                })

            else:
                # Text-only processing (legacy format or vision-disabled assistant)
                if isinstance(last_message, list):
                    # Extract text parts only (strips images for security)
                    text_parts = []
                    for item in last_message:
                        if item.get('type') == 'text':
                            text_parts.append(item.get('text', ''))
                    user_input_text = ' '.join(text_parts)
                else:
                    # Legacy string format
                    user_input_text = str(last_message)

                # Replace placeholders in template
                logger.debug(f"User message: {user_input_text}")
                prompt = effective_template.replace("{user_input}", "\n\n" + user_input_text + "\n\n")

                # Add RAG context if available
                if rag_context:
                    context = rag_context.get("context", "") if isinstance(rag_context, dict) else str(rag_context)
                    
                    # Format sources if available
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
                    
                    # Combine context with sources
                    full_context = context + sources_text
                    prompt = prompt.replace("{context}", "\n\n" + full_context + "\n\n")
                else:
                    prompt = prompt.replace("{context}", "")

                # Add processed text message
                processed_messages.append({
                    "role": messages[-1]['role'],
                    "content": prompt
                })
        else:
            # If no template, use original message
            processed_messages.append(messages[-1])
            
        return processed_messages
    
    # If no assistant provided, return original messages
    return messages 