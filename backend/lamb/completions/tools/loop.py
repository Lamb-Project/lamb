"""
Tool execution loop for Workshop assistants.

Event-driven loop:
  1. LLM(full conversation + tools) → tool_calls
  2. Execute each tool call
  3. Feed results back with role:"tool"
  4. Repeat until LLM produces a text reply or max rounds reached.

All events are yielded as dicts for SSE integration.
"""

import json
import logging
from types import SimpleNamespace
from typing import Any, AsyncIterator, Callable, Optional

logger = logging.getLogger(__name__)


def _normalize_response(response: Any) -> Any:
    """
    Normalize a connector response to an object with .choices[0].message.tool_calls.

    Accepts both:
    - OpenAI SDK ChatCompletion object (has .choices)
    - Plain dict (OpenAI-compatible format, e.g. from Ollama)
    """
    if isinstance(response, dict):
        # Convert dict response to namespace object
        choice = response.get("choices", [{}])[0]
        msg = choice.get("message", {})
        tool_calls_data = msg.get("tool_calls") or []
        tool_calls = []
        for tc in tool_calls_data:
            tool_calls.append(SimpleNamespace(
                id=tc.get("id"),
                function=SimpleNamespace(
                    name=tc.get("function", {}).get("name"),
                    arguments=tc.get("function", {}).get("arguments"),
                ),
            ))
        msg_ns = SimpleNamespace(
            content=msg.get("content", ""),
            tool_calls=tool_calls or None,
        )
        choice_ns = SimpleNamespace(message=msg_ns)
        return SimpleNamespace(choices=[choice_ns])
    return response


class ToolLoop:
    """Orchestrates tool-calling rounds between the LLM and local tool implementations."""

    DEFAULT_MAX_ROUNDS = 5

    def __init__(self, max_rounds: int = DEFAULT_MAX_ROUNDS):
        self.max_rounds = max_rounds

    async def run(
        self,
        messages: list,
        tools: list,
        tool_choice: Any,
        llm_call_fn: Callable,
    ) -> AsyncIterator[dict]:
        """
        Run the tool loop.

        Yields event dicts:
            {"type": "thinking"}
            {"type": "tool", "name": str, "args": str}
            {"type": "tool_done", "name": str, "success": bool}
            {"type": "result", "messages": [...]}   ← terminal event

        Args:
            messages: The conversation so far (list of dicts with role/content).
            tools: List of tool definitions in OpenAI function-calling format.
            tool_choice: Tool choice strategy ("auto", "none", or {"type":"function","function":{...}}).
            llm_call_fn: Async callable(messages, tools, tool_choice) returning an
                         OpenAI-compatible ChatCompletion response object.

        Yields:
            Event dicts (see above). The caller is responsible for SSE formatting.
        """
        messages = list(messages)  # local copy
        rounds = 0

        while True:
            yield {"type": "thinking"}

            try:
                response = await llm_call_fn(messages, tools, tool_choice)
                response = _normalize_response(response)
            except Exception as e:
                logger.error("ToolLoop LLM call failed: %s", e)
                messages.append({
                    "role": "user",
                    "content": f"[System: LLM call failed: {e}. Respond with what you have.]",
                })
                yield {"type": "result", "messages": messages}
                return

            choice = response.choices[0]
            msg = choice.message

            # No tool_calls → we're done; yield result and exit loop
            if not msg.tool_calls:
                yield {"type": "result", "messages": messages}
                return

            rounds += 1

            # Append assistant message with tool_calls
            assistant_entry = {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
            messages.append(assistant_entry)

            # Execute each tool call
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = tc.function.arguments
                yield {"type": "tool", "name": fn_name, "args": fn_args}

                result = await self._execute_tool(fn_name, fn_args)
                success = result.get("success", False)
                yield {"type": "tool_done", "name": fn_name, "success": success}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

            if rounds >= self.max_rounds:
                logger.warning("ToolLoop: max rounds (%d) reached", self.max_rounds)
                messages.append({
                    "role": "user",
                    "content": "[System: max tool rounds reached. Respond with what you have.]",
                })
                yield {"type": "result", "messages": messages}
                return

    async def _execute_tool(self, name: str, args_json: str) -> dict:
        """
        Dispatch a tool call to the appropriate implementation.

        Args:
            name: Tool name ("calculator", "kb_query", "sandbox_exec").
            args_json: JSON string of arguments.

        Returns:
            dict with at least {"success": bool}.
        """
        try:
            args = json.loads(args_json) if args_json else {}
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid JSON arguments"}

        if name == "calculator":
            from .implementations.calculator import run_calculator
            return run_calculator(args)
        elif name == "kb_query":
            from .implementations.kb_query import run_kb_query
            return await run_kb_query(args)
        elif name == "sandbox_exec":
            from .implementations.sandbox_exec import run_sandbox_exec
            return await run_sandbox_exec(args)
        else:
            return {"success": False, "error": f"Unknown tool: {name}"}