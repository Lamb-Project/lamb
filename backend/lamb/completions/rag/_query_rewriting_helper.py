"""Shared query rewriting logic for RAG processors.

Extracted from ``context_aware_rag.py`` so that both the legacy
context-aware processor and the new ``query_rewriting_ks_rag`` can
reuse the same small-fast-model query optimization without duplication.
"""

from __future__ import annotations

from typing import Any, Dict, List

from lamb.completions.small_fast_model_helper import (
    invoke_small_fast_model,
    is_small_fast_model_configured,
)
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="RAG")


def get_last_user_message_text(messages: List[Dict[str, Any]]) -> str:
    """Extract text from the last user message, handling multimodal content."""
    for msg in reversed(messages or []):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
                return " ".join(text_parts)
            return content or ""
    return ""


async def generate_optimal_query(
    messages: List[Dict[str, Any]],
    assistant_owner: str,
) -> str:
    """Use the small-fast-model to generate an optimized RAG query.

    Falls back silently to the last user message when:
    - small-fast-model is not configured
    - the model call fails
    - the model returns an empty response
    """
    if not is_small_fast_model_configured(assistant_owner):
        logger.info("Small-fast-model not configured, using last user message as query")
        return get_last_user_message_text(messages)

    recent_messages = messages[-10:] if len(messages) > 10 else messages
    conversation_summary = []
    for msg in recent_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
            content = " ".join(text_parts)
        if len(content) > 500:
            content = content[:500] + "..."
        conversation_summary.append(f"{role.upper()}: {content}")

    conversation_text = "\n".join(conversation_summary)

    system_prompt = (
        "You are a query optimization assistant for a RAG "
        "(Retrieval-Augmented Generation) system.\n\n"
        "Your task is to analyze the conversation history and generate an "
        "optimal search query that will retrieve the most relevant documents "
        "from a knowledge base.\n\n"
        "Guidelines:\n"
        "1. Consider the full conversation context, not just the last message\n"
        "2. Identify the core information need\n"
        "3. Include relevant keywords and concepts\n"
        "4. If the conversation references previous topics, incorporate them\n"
        "5. Make the query specific and focused\n"
        "6. Keep the query concise (1-3 sentences max)\n"
        "7. Return ONLY the optimized query, nothing else\n\n"
        "Example:\n"
        "CONVERSATION:\n"
        "USER: What is photosynthesis?\n"
        "ASSISTANT: Photosynthesis is the process by which plants convert light energy into chemical energy.\n"
        "USER: How does it work in detail?\n\n"
        "OPTIMAL QUERY: detailed explanation of photosynthesis process mechanism light energy conversion chlorophyll\n\n"
        "Now generate the optimal query for the following conversation:"
    )

    user_prompt = f"CONVERSATION:\n{conversation_text}\n\nOPTIMAL QUERY:"

    enhancement_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        logger.info("Generating optimal query using small-fast-model...")
        response = await invoke_small_fast_model(
            messages=enhancement_messages,
            assistant_owner=assistant_owner,
            stream=False,
        )

        optimized_query = ""
        if isinstance(response, dict):
            if "choices" in response and len(response["choices"]) > 0:
                optimized_query = response["choices"][0]["message"]["content"].strip()
            elif "message" in response:
                optimized_query = response["message"].get("content", "").strip()

        if optimized_query:
            logger.info(f"Optimized query generated: {optimized_query[:100]}...")
            return optimized_query

        logger.warning("Empty response from small-fast-model, falling back to last user message")
        return get_last_user_message_text(messages)

    except Exception as e:
        logger.error(f"Error generating optimal query: {e}", exc_info=True)
        return get_last_user_message_text(messages)
