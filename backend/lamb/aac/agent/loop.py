"""Agent loop: LLM reasoning + liteshell tool execution + authorization.

The loop:
1. Check for pending action from previous turn — if user approved, execute it
2. User sends message
3. Build context: system prompt + conversation history + user message
4. Call LLM with tool definitions
5. If LLM returns tool calls:
   a. For each tool call, check authorization policy
   b. "auto" → execute immediately
   c. "ask" → queue action, return description to LLM, STOP loop after LLM responds
   d. "never" → return error to LLM
6. If LLM returns text → return to user
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from lamb.aac.authorization import ActionAuthorizer, classify_user_confirmation
from lamb.aac.liteshell.shell import LiteShell, CommandContext
from lamb.aac.session_logger import SessionLogger
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")

DEFAULT_SYSTEM_PROMPT = """\
You are an AI assistant designer for the LAMB platform. You help educators \
create, configure, test, and refine AI learning assistants.

You have access to the LAMB platform via CLI commands. Use the \
`execute_command` tool to run commands. Commands follow the `lamb` CLI syntax.

## Available commands

READ (information retrieval):
- lamb assistant list — list user's assistants
- lamb assistant get <id> — get assistant details
- lamb assistant config — show available models, connectors, processors
- lamb rubric list / list-public — list rubrics
- lamb rubric get <uuid> — get rubric details and criteria
- lamb rubric export <uuid> [--format json|md] — export rubric
- lamb kb list — list knowledge bases
- lamb kb get <id> — get KB details
- lamb template list / get <id> — list/get prompt templates
- lamb model list — list available models
- lamb help — show all commands

WRITE (modifications):
- lamb assistant create <name> [--system-prompt "..."] [--llm model] \
[--connector openai] [--prompt-processor simple_augment] [--rag-processor rubric_rag] \
[--rubric-id uuid] [--rubric-format markdown] [--prompt-template "..."] [--description "..."]
- lamb assistant update <id> [--system-prompt "..."] [--llm model] [--name "..."]
- lamb assistant delete <id>

When a write command needs user approval, the system will handle it — you will \
receive an "awaiting_user_confirmation" result. In that case, explain to the \
user WHAT will happen and WHY, so they can make an informed decision. Use \
clear, non-technical language — the user is an educator, not a developer.

## Guidelines
- Start by understanding what the educator wants to build
- Inspect existing resources before suggesting configurations
- When proposing changes, explain the pedagogical reasoning
- After confirmed changes, verify by reading back the assistant state
- Be concise and direct
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "Execute a LAMB CLI command. Returns structured JSON data. "
                "Examples: 'lamb assistant list', 'lamb rubric get <uuid>', "
                "'lamb assistant create \"My Tutor\" --system-prompt \"You are...\" --llm gpt-4o-mini'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The CLI command to execute",
                    }
                },
                "required": ["command"],
            },
        },
    }
]


@dataclass
class AgentLoop:
    """The AAC agent loop.

    Attributes:
        shell: LiteShell instance for command execution.
        llm_client: AsyncOpenAI client (configured with org's API key).
        model: Model identifier.
        authorizer: Action authorization policy.
        system_prompt: Agent system prompt.
        max_tool_rounds: Max consecutive tool-call rounds.
        conversation: Full conversation history.
        session_logger: Optional JSONL logger.
        pending_action: Queued write command awaiting user confirmation.
    """
    shell: LiteShell
    llm_client: AsyncOpenAI
    model: str
    authorizer: ActionAuthorizer = field(default_factory=ActionAuthorizer)
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_tool_rounds: int = 10
    conversation: list[dict] = field(default_factory=list)
    session_logger: SessionLogger | None = None
    pending_action: dict | None = None

    def load_skills(self, skills_dir: Path | str) -> None:
        """Append skill files (.md) to the system prompt."""
        skills_dir = Path(skills_dir)
        if not skills_dir.is_dir():
            return
        skill_texts = []
        for md_file in sorted(skills_dir.glob("*.md")):
            skill_texts.append(f"\n--- Skill: {md_file.stem} ---\n{md_file.read_text()}")
        if skill_texts:
            self.system_prompt += "\n\n# Skills\n" + "\n".join(skill_texts)

    async def chat(self, user_message: str) -> str:
        """Send a user message and return the assistant's text response.

        Handles pending actions, authorization, and the full tool-calling loop.
        """
        # Step 1: Handle pending action from previous turn
        if self.pending_action:
            result_text = self._resolve_pending_action(user_message)
            if result_text is not None:
                # The pending action was resolved (approved or rejected).
                # Now run the agent loop so the LLM can react to the result.
                return await self._run_agent_loop()

        # Step 2: Normal flow — add user message and run loop
        if self.session_logger:
            self.session_logger.log_user_message(user_message)
        self.conversation.append({"role": "user", "content": user_message})
        return await self._run_agent_loop()

    async def _run_agent_loop(self) -> str:
        """Run the LLM tool-calling loop until a text response is produced."""
        tool_rounds = 0

        while True:
            messages = [{"role": "system", "content": self.system_prompt}] + self.conversation

            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )

            choice = response.choices[0]
            message = choice.message

            if message.tool_calls:
                tool_rounds += 1
                self.conversation.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                })

                # Process each tool call
                should_stop = False
                for tc in message.tool_calls:
                    result = self._execute_tool(tc)
                    logger.info(f"Tool: {tc.function.arguments} → {result.get('success', '?')}")
                    self.conversation.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str, ensure_ascii=False),
                    })
                    # If we queued a pending action, stop after LLM responds
                    if result.get("awaiting_user_confirmation"):
                        should_stop = True

                if tool_rounds >= self.max_tool_rounds:
                    self.conversation.append({
                        "role": "user",
                        "content": "[System: Maximum tool rounds reached. Please respond.]",
                    })

                if should_stop:
                    # Let LLM produce one more response explaining the pending action,
                    # then stop the loop
                    messages = [{"role": "system", "content": self.system_prompt}] + self.conversation
                    final = await self.llm_client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                    )
                    text = final.choices[0].message.content or ""
                    self.conversation.append({"role": "assistant", "content": text})
                    if self.session_logger:
                        self.session_logger.log_agent_response(text)
                    return text

                continue

            # No tool calls — text response
            text = message.content or ""
            self.conversation.append({"role": "assistant", "content": text})
            if self.session_logger:
                self.session_logger.log_agent_response(text)
            return text

    def _execute_tool(self, tool_call: Any) -> dict:
        """Execute a tool call, checking authorization policy."""
        try:
            fn_args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid JSON in tool arguments"}

        command = fn_args.get("command", "")
        if not command:
            return {"success": False, "error": "No command provided"}

        # Check authorization
        action_key = self.authorizer.resolve_action_key(command)
        policy = self.authorizer.check(action_key) if action_key else "auto"

        if policy == "never":
            return {"success": False, "error": f"Action '{action_key}' is not allowed"}

        if policy == "ask":
            # Queue the command, don't execute
            self.pending_action = {
                "command": command,
                "action_key": action_key,
                "tool_call_id": tool_call.id,
            }
            if self.session_logger:
                self.session_logger.log("action_queued", {
                    "command": command,
                    "action_key": action_key,
                })
            return {
                "success": True,
                "awaiting_user_confirmation": True,
                "action": action_key,
                "command": command,
                "message": "This action needs user approval. Explain what will happen and why.",
            }

        # policy == "auto" — execute directly
        result = self.shell.execute(command)
        if self.session_logger:
            self.session_logger.log_tool_call(
                command=command,
                success=result.success,
                elapsed_ms=result.elapsed_ms,
                data=result.data,
                error=result.error,
            )
        return result.to_dict()

    def _resolve_pending_action(self, user_message: str) -> str | None:
        """Check if user approved/rejected the pending action.

        Returns a string (can be empty) if the action was resolved,
        None if the message is unrelated to the pending action.
        """
        action = self.pending_action
        classification = classify_user_confirmation(user_message)

        if classification == "approve":
            # Execute the queued command
            self.pending_action = None
            result = self.shell.execute(action["command"])

            if self.session_logger:
                self.session_logger.log_user_message(user_message)
                self.session_logger.log_tool_call(
                    command=action["command"],
                    success=result.success,
                    elapsed_ms=result.elapsed_ms,
                    data=result.data,
                    error=result.error,
                )

            # Inject into conversation: user message + system result
            self.conversation.append({"role": "user", "content": user_message})
            result_summary = json.dumps(result.to_dict(), default=str, ensure_ascii=False)
            self.conversation.append({
                "role": "user",
                "content": f"[System: User approved. Action executed. Result: {result_summary}]",
            })
            return ""

        elif classification == "reject":
            self.pending_action = None

            if self.session_logger:
                self.session_logger.log_user_message(user_message)
                self.session_logger.log("action_rejected", {"command": action["command"]})

            self.conversation.append({"role": "user", "content": user_message})
            self.conversation.append({
                "role": "user",
                "content": "[System: User declined the action. It was not executed.]",
            })
            return ""

        else:
            # Ambiguous message — treat as a new message, keep pending action
            # The agent will respond to whatever the user said, and the
            # pending action remains for the next turn
            return None

    def reset(self) -> None:
        self.conversation.clear()
        self.pending_action = None

    def get_stats(self) -> dict:
        tool_calls = len(self.shell.history)
        total_time = sum(r.elapsed_ms for r in self.shell.history)
        errors = sum(1 for r in self.shell.history if not r.success)
        return {
            "turns": len([m for m in self.conversation if m["role"] == "user"]),
            "tool_calls": tool_calls,
            "tool_errors": errors,
            "total_tool_time_ms": round(total_time, 1),
            "model": self.model,
        }
