import json
import asyncio
from typing import Dict, Any, AsyncGenerator, Optional

def get_available_llms():
    """
    Return list of available LLMs for this connector
    """
    return ["debug-bypass", "simple-bypass", "full-conversation-bypass"]

def format_debug_response(messages: list, body: Dict[str, Any]) -> str:
    """Format debug response showing messages and body"""
    return f"Messages:\n{json.dumps(messages, indent=2)}\n\nBody:\n{json.dumps(body, indent=2)}"

def format_simple_response(messages: list) -> str:
    """Get the last message content"""
    print(messages[-1]["content"])
    return messages[-1]["content"] if messages else "No messages provided"
    

def format_conversation_response(messages: list) -> str:
    """Format all messages as a conversation"""
    return "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

async def llm_connect(messages: list, stream: bool = False, body: Dict[str, Any] = None, llm: str = None, assistant_owner: Optional[str] = None):
    """
    Bypass connector that returns OpenAI-compatible responses
    
    Args:
        messages: List of message dictionaries
        stream: Whether to stream the response
        body: Additional request parameters
        llm: Model name (unused for bypass)
        assistant_owner: Assistant owner email (unused for bypass, but required for interface compatibility)
    """
    # Determine content based on LLM type
    content = "This is a bypass response"  # default
    if llm == "debug-bypass":
        content = format_debug_response(messages, body)
    elif llm == "simple-bypass":
        content = format_simple_response(messages)
    elif llm == "full-conversation-bypass":
        content = format_conversation_response(messages)

    if stream:
        async def generate_stream():
            # Send first chunk with role
            first_chunk = {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1694268762,
                "model": llm or body.get("model", "bypass-model"),
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant"
                    },
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(first_chunk)}\n\n"
            await asyncio.sleep(0.017)  # 3x faster (was 0.05)
            
            # Simulate streaming response
            response_text = content  # Use the formatted content
            for word in response_text.split():
                chunk = {
                    "id": "chatcmpl-123",
                    "object": "chat.completion.chunk",
                    "created": 1694268762,
                    "model": llm or body.get("model", "bypass-model"),
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": word + " "
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.033)  # 3x faster (was 0.1)

            # Send final chunk
            final_chunk = {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1694268762,
                "model": llm or body.get("model", "bypass-model"),
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
        print("generate_stream")
        return generate_stream()
    else:
        # Regular response
        print("regular response")
        return {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1694268762,
            "model": llm or body.get("model", "bypass-model"),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        } 