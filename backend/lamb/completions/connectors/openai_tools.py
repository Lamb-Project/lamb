"""
OpenAI Connector with Tool/Function Calling Support

This is a proof-of-concept connector that demonstrates how to add tool calling
capabilities to LAMB assistants. It extends the standard OpenAI connector with:

1. Tool definitions (currently just get_weather)
2. Tool call detection and execution
3. Multi-turn conversation support for tool results

USAGE:
1. Configure an assistant to use connector "openai_tools" in metadata
2. The LLM will automatically have access to the get_weather tool
3. When the user asks about weather, the LLM will call the tool and use the result

ARCHITECTURE:
- Tools are defined in /backend/lamb/completions/tools/
- Each tool has a TOOL_SPEC (OpenAI function calling format) and implementation
- The connector handles the tool calling loop automatically
"""

import json
import asyncio
from typing import Dict, Any, AsyncGenerator, Optional, List
import time
import logging
import os
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.completions.tools.weather import get_weather, WEATHER_TOOL_SPEC

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Tool registry - add new tools here
AVAILABLE_TOOLS = [WEATHER_TOOL_SPEC]

# Tool function mapping
TOOL_FUNCTIONS = {
    "get_weather": get_weather
}


def get_available_llms(assistant_owner: Optional[str] = None):
    """
    Return list of available LLMs for this connector.
    Same as the standard OpenAI connector.
    """
    if not assistant_owner:
        if os.getenv("OPENAI_ENABLED", "true").lower() != "true":
            return []
        
        import config
        models = os.getenv("OPENAI_MODELS") or config.OPENAI_MODEL
        if not models:
            return [os.getenv("OPENAI_MODEL") or config.OPENAI_MODEL]
        return [model.strip() for model in models.split(",") if model.strip()]
    
    try:
        config_resolver = OrganizationConfigResolver(assistant_owner)
        openai_config = config_resolver.get_provider_config("openai")
        
        if not openai_config or not openai_config.get("enabled", True):
            return []
            
        models = openai_config.get("models", [])
        if not models:
            import config
            models = [openai_config.get("default_model") or config.OPENAI_MODEL]
            
        return models
    except Exception as e:
        logger.error(f"Error getting OpenAI models for {assistant_owner}: {e}")
        return get_available_llms(None)


async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Execute a tool by name with the provided arguments.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Dictionary of arguments to pass to the tool
        
    Returns:
        Tool result as a string
    """
    if tool_name not in TOOL_FUNCTIONS:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    try:
        tool_func = TOOL_FUNCTIONS[tool_name]
        
        # Check if the function is async
        if asyncio.iscoroutinefunction(tool_func):
            result = await tool_func(**arguments)
        else:
            result = tool_func(**arguments)
            
        logger.info(f"Tool '{tool_name}' executed successfully: {result[:100]}...")
        return result
        
    except Exception as e:
        logger.error(f"Error executing tool '{tool_name}': {e}")
        return json.dumps({"error": str(e)})


async def llm_connect(
    messages: list,
    stream: bool = False,
    body: Dict[str, Any] = None,
    llm: str = None,
    assistant_owner: Optional[str] = None
):
    """
    Connect to OpenAI with tool calling support.
    
    This connector adds the ability for the LLM to call tools (functions).
    When the LLM wants to use a tool:
    1. It returns a tool_calls response instead of content
    2. We execute the tool and get the result
    3. We send the result back to the LLM
    4. The LLM generates the final response
    
    For streaming, this is more complex - we need to collect the full
    tool call before executing it, then stream the final response.
    """
    
    # Get organization-specific configuration
    api_key = None
    base_url = None
    import config
    default_model = config.OPENAI_MODEL
    
    if assistant_owner:
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            openai_config = config_resolver.get_provider_config("openai")
            
            if openai_config:
                api_key = openai_config.get("api_key")
                base_url = openai_config.get("base_url")
                default_model = openai_config.get("default_model") or config.OPENAI_MODEL
        except Exception as e:
            logger.error(f"Error getting org config: {e}")

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")

    if not api_key:
        raise ValueError("No OpenAI API key found")

    resolved_model = llm or default_model
    
    # Create OpenAI client
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    # Prepare parameters with tools
    params = body.copy() if body else {}
    params["model"] = resolved_model
    params["messages"] = messages
    params["tools"] = AVAILABLE_TOOLS
    params["tool_choice"] = "auto"  # Let the model decide when to use tools
    
    logger.info(f"Making tool-enabled API call with model: {resolved_model}")
    logger.info(f"Available tools: {[t['function']['name'] for t in AVAILABLE_TOOLS]}")
    
    if stream:
        return _handle_streaming_with_tools(client, params, messages)
    else:
        return await _handle_non_streaming_with_tools(client, params, messages)


async def _handle_non_streaming_with_tools(
    client: AsyncOpenAI,
    params: Dict[str, Any],
    original_messages: List[Dict]
) -> Dict[str, Any]:
    """
    Handle non-streaming requests with tool calling loop.
    
    The loop:
    1. Call the LLM
    2. If it wants to use tools, execute them
    3. Add tool results to messages
    4. Call the LLM again
    5. Repeat until we get a final response
    """
    messages = original_messages.copy()
    max_tool_iterations = 5  # Prevent infinite loops
    iteration = 0
    
    while iteration < max_tool_iterations:
        iteration += 1
        params["messages"] = messages
        
        logger.info(f"Tool iteration {iteration}/{max_tool_iterations}")
        
        response = await client.chat.completions.create(**params)
        choice = response.choices[0]
        message = choice.message
        
        # Check if the model wants to call tools
        if message.tool_calls:
            logger.info(f"Model requested {len(message.tool_calls)} tool call(s)")
            
            # Add the assistant's response with tool calls to the conversation
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })
            
            # Execute each tool and add results
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}
                
                logger.info(f"Executing tool: {tool_name}({arguments})")
                
                result = await execute_tool(tool_name, arguments)
                
                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        else:
            # No tool calls - this is the final response
            logger.info("Final response received (no more tool calls)")
            return response.model_dump()
    
    # If we hit max iterations, return the last response
    logger.warning(f"Hit max tool iterations ({max_tool_iterations})")
    return response.model_dump()


async def _handle_streaming_with_tools(
    client: AsyncOpenAI,
    params: Dict[str, Any],
    original_messages: List[Dict]
) -> AsyncGenerator[str, None]:
    """
    Handle streaming requests with tool calling support.
    
    For tool calls during streaming:
    1. Collect the full response to detect tool calls
    2. If tools are called, execute them (not streamed)
    3. Make another call and stream that response
    """
    messages = original_messages.copy()
    max_tool_iterations = 5
    iteration = 0
    
    while iteration < max_tool_iterations:
        iteration += 1
        params["messages"] = messages
        params["stream"] = True
        
        logger.info(f"Streaming tool iteration {iteration}/{max_tool_iterations}")
        
        # Collect stream to check for tool calls
        full_content = ""
        tool_calls_data = {}  # {index: {id, name, arguments}}
        finish_reason = None
        response_id = None
        created_time = None
        model_name = None
        
        stream_obj = await client.chat.completions.create(**params)
        
        async for chunk in stream_obj:
            if not response_id:
                response_id = chunk.id
                created_time = chunk.created
                model_name = chunk.model
            
            if chunk.choices:
                choice = chunk.choices[0]
                delta = choice.delta
                finish_reason = choice.finish_reason or finish_reason
                
                # Collect content
                if delta.content:
                    full_content += delta.content
                
                # Collect tool calls
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_data:
                            tool_calls_data[idx] = {
                                "id": tc.id or "",
                                "name": "",
                                "arguments": ""
                            }
                        if tc.id:
                            tool_calls_data[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_data[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_data[idx]["arguments"] += tc.function.arguments
        
        # Check if we have tool calls to process
        if tool_calls_data and finish_reason == "tool_calls":
            logger.info(f"Stream detected {len(tool_calls_data)} tool call(s)")
            
            # Add the assistant message with tool calls
            assistant_message = {
                "role": "assistant",
                "content": full_content,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"]
                        }
                    }
                    for tc in tool_calls_data.values()
                ]
            }
            messages.append(assistant_message)
            
            # Execute tools and add results
            for tc_data in tool_calls_data.values():
                try:
                    arguments = json.loads(tc_data["arguments"])
                except json.JSONDecodeError:
                    arguments = {}
                
                logger.info(f"Executing tool: {tc_data['name']}({arguments})")
                result = await execute_tool(tc_data["name"], arguments)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_data["id"],
                    "content": result
                })
            
            # Continue the loop to get the next response
            continue
        
        else:
            # No tool calls - stream this response
            logger.info("Streaming final response (no more tool calls)")
            
            # We already consumed the stream collecting tool calls,
            # so we need to make another call for the actual stream
            # This time without tools since we're in the final response
            final_params = params.copy()
            # Keep tools in case model wants to use them in follow-up
            
            stream_obj = await client.chat.completions.create(**final_params)
            
            async for chunk in stream_obj:
                yield f"data: {chunk.model_dump_json()}\n\n"
            
            yield "data: [DONE]\n\n"
            return
    
    # If we hit max iterations, yield what we have
    logger.warning(f"Hit max tool iterations ({max_tool_iterations})")
    yield "data: [DONE]\n\n"
