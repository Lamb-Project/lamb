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
You are an AI assistant designer for the LAMB platform. Help educators \
create, configure, test, and refine AI learning assistants.

## Commands

READ: lamb assistant list | list-shared | list-published | get <id_or_name> | config | debug <id> --message "text"
READ: lamb rubric list | get <uuid> | export <uuid> [--format md]
READ: lamb kb list | get <id>
READ: lamb template list | get <id>

To see available LLM models (gpt-4o, gpt-4o-mini, etc.), use: lamb assistant config
It returns connectors, their models, and organization defaults. ALWAYS use this for model selection.
DOCS: lamb docs index | read <topic> [--section "heading"]
SKILLS: lamb skill list | load <skill-id> [--assistant <id>]
TEST: lamb test scenarios <id> | add <id> <title> --message "text" | run <id> [--bypass] | runs <id> | evaluate <run_id> <good|bad|mixed>
WRITE: lamb assistant create <name> [--system-prompt "..." --llm model ...] | update <id> [...] | delete <id>

debug and --bypass = inspect mode. It runs the full prompt assembly (system prompt + RAG context + template)
WITHOUT calling the LLM. It returns the constructed messages array — this IS the expected output.
An empty or minimal response from debug is NORMAL for non-RAG assistants (no KB content to inject).
For RAG assistants, debug shows what context was retrieved — useful for verifying KB content.
run without --bypass = real LLM completion (uses tokens, gets an actual response).
When running a full test suite on a RAG assistant, suggest checking with debug first.
For casual single questions or non-RAG assistants, just run directly.

## CRITICAL: Prompt Template Rules

The prompt_template controls how the final prompt is assembled before sending to the LLM.
It uses two placeholders:

- `{user_input}` — where the student's message is inserted. REQUIRED in ALL assistants.
- `{context}` — where RAG-retrieved KB content is inserted. REQUIRED when RAG is enabled.

EVERY assistant MUST have a prompt_template containing at least `{user_input}`.
If RAG is enabled (rag_processor is NOT no_rag), it MUST also contain `{context}`.

When CREATING or UPDATING an assistant, ALWAYS set --prompt-template. Examples:

Non-RAG: --prompt-template "{user_input}"
RAG:     --prompt-template "Context:\n{context}\n\nStudent question: {user_input}\n\nAnswer using the provided context."

If you see an assistant with an empty prompt_template, WARN the user — the pipeline will fail.
If you see a RAG assistant without {context} in the template, WARN — KB content will be silently discarded.

## Style rules

BE CONCISE. Maximum 5-6 lines per response unless the user asks for detail.
Short sentences. No filler. No repeating what the user already knows.
Use bullet points, not paragraphs.

SPEAK LIKE A HELPFUL COLLEAGUE, NOT A DEVELOPER.
The user is an educator, not an engineer. Do NOT mention:
- "pipeline", "debug", "bypass" — say "test" or "check" instead
- "prompt processor", "simple_augment" — just skip these internal details
- "RAG_collections", "api_callback" — say "knowledge base" or "connected documents"
- "prompt_template" — say "how the question is assembled" if they need to know
Only use technical terms if the user used them first or explicitly asks for internals.

NEVER switch language mid-conversation. If the user speaks Spanish, respond in Spanish. Always.
NEVER refuse a user's explicit request. If they want to run a real test, run it. You may suggest bypass first, but if the user insists, do what they ask.

When the user asks to do something covered by a specific skill (create, improve, explain, test an assistant),
use `lamb skill load <skill-id>` to switch. Available skills: about-lamb, create-assistant, improve-assistant,
explain-assistant, test-and-evaluate. Use `lamb skill list` if unsure.

End EVERY response with numbered options. EXACTLY this format, no variations:

**Next?**
1. Option text
2. Option text
3. Other — tell me

RULES for numbering:
- Always start at 1
- Always sequential (1, 2, 3)
- Last option is always "Other — tell me"
- No text before "**Next?**" on that line
- No text after the last option
- 2-4 options total, keep each under 8 words

For test results: compact markdown table, offer details on request.

Write commands: briefly state what changes. One sentence max.
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

# Human-readable descriptions for tool calls shown during streaming
_TOOL_LABELS = {
    "assistant.list": "Loading assistants",
    "assistant.list-shared": "Loading shared assistants",
    "assistant.get": "Reading assistant config",
    "assistant.config": "Checking available options",
    "assistant.debug": "Running pipeline debug",
    "assistant.create": "Creating assistant",
    "assistant.update": "Updating assistant",
    "assistant.delete": "Deleting assistant",
    "rubric.list": "Loading rubrics",
    "rubric.get": "Reading rubric",
    "kb.list": "Loading knowledge bases",
    "kb.get": "Reading knowledge base",
    "assistant.list-published": "Loading published assistants",
    "template.list": "Loading templates",
    "test.scenarios": "Loading test scenarios",
    "test.add": "Creating test scenario",
    "test.run": "Running tests",
    "test.runs": "Loading test results",
    "test.evaluate": "Recording evaluation",
    "skill.list": "Loading available skills",
    "skill.load": "Switching to skill",
    "docs.index": "Loading documentation index",
    "docs.read": "Reading documentation",
}


def _parse_action_key(cmd: str) -> str:
    """Extract action key (e.g., 'assistant.get') from a command string."""
    tokens = cmd.strip().split()
    if tokens and tokens[0] == "lamb":
        tokens = tokens[1:]
    if len(tokens) >= 2 and not tokens[1].startswith("-"):
        return f"{tokens[0]}.{tokens[1]}"
    elif tokens:
        return tokens[0]
    return ""


def _describe_tool_call(tc: Any) -> str:
    """Extract a human-readable description from a tool call."""
    try:
        args = json.loads(tc.function.arguments)
        cmd = args.get("command", "")
        key = _parse_action_key(cmd)
        label = _TOOL_LABELS.get(key, cmd[:50])
        # Add bypass note if present
        if "--bypass" in cmd:
            label += " (pipeline debug)"
        return label
    except Exception:
        return "Executing command"


def _summarize_result(action_key: str, result: Any) -> str:
    """Generate a one-line summary of a tool call result."""
    if result is None:
        return ""
    if hasattr(result, "error") and result.error:
        return f"error: {result.error[:80]}"
    if not hasattr(result, "data") or result.data is None:
        return ""

    d = result.data
    if not isinstance(d, dict):
        if isinstance(d, list):
            return f"{len(d)} items"
        return str(d)[:80]

    try:
        if action_key == "assistant.get":
            return f"name={d.get('name','?')}, llm={d.get('llm','?')}, rag={d.get('rag_processor','none')}"
        elif action_key == "assistant.create":
            return f"created id={d.get('assistant_id','?')}, name={d.get('name','?')}"
        elif action_key == "assistant.update":
            return f"updated {', '.join(d.get('updated_fields', []))}" if 'updated_fields' in d else "updated"
        elif action_key == "assistant.delete":
            return d.get("message", "deleted")
        elif action_key == "assistant.config":
            caps = d.get("capabilities", d)
            connectors = caps.get("connectors", {})
            models = sum(len(v) if isinstance(v, list) else 0 for v in connectors.values())
            return f"{len(connectors)} connectors, {models} models"
        elif action_key == "assistant.debug":
            resp = d.get("response", "")
            return f"context: {len(resp)} chars" if resp else "empty response"
        elif action_key == "rubric.get":
            rd = d.get("rubric_data", {})
            criteria = rd.get("criteria", [])
            return f"title={d.get('title','?')}, {len(criteria)} criteria"
        elif action_key == "test.run":
            if isinstance(d, list):
                return f"{len(d)} runs"
            tok = d.get("token_usage", {}).get("total_tokens", 0)
            return f"tokens={tok}, {d.get('elapsed_ms',0):.0f}ms" if tok else f"{d.get('elapsed_ms',0):.0f}ms"
        elif action_key == "test.scenarios":
            return f"{len(d)} scenarios" if isinstance(d, list) else ""
        elif action_key == "test.add":
            return f"title={d.get('title', '?')}"
        elif action_key == "test.evaluate":
            return f"verdict={d.get('verdict', '?')}"
        elif action_key == "model.list":
            return f"{len(d)} models" if isinstance(d, list) else ""
        elif action_key == "kb.list":
            return f"{len(d)} knowledge bases" if isinstance(d, list) else ""
        elif action_key == "kb.get":
            files = d.get("files", [])
            return f"name={d.get('name','?')}, {len(files)} files"
    except Exception:
        pass

    # Fallback: show key count or first key
    if isinstance(d, dict):
        keys = list(d.keys())[:3]
        return f"keys: {', '.join(keys)}"
    return ""


def _extract_artifacts(cmd: str, result: Any) -> list[dict]:
    """Extract affected LAMB resources from a command string + result."""
    tokens = cmd.strip().split()
    if tokens and tokens[0] == "lamb":
        tokens = tokens[1:]
    if len(tokens) < 2:
        return []

    resource_type = tokens[0]  # assistant, rubric, kb, test, template, model
    subcommand = tokens[1] if not tokens[1].startswith("-") else ""

    # Map subcommands to actions
    action_map = {
        "get": "read", "list": "read", "list-public": "read",
        "config": "read", "debug": "debug", "export": "read",
        "create": "create", "update": "update", "delete": "delete",
        "run": "test", "runs": "read", "run-detail": "read",
        "add": "create", "evaluate": "evaluate",
        "scenarios": "read",
    }
    action = action_map.get(subcommand, "read")

    # Find the resource ID (first positional arg after subcommand)
    resource_id = None
    for t in tokens[2:]:
        if not t.startswith("-"):
            resource_id = t
            break

    # For create actions, try to get the ID from the result
    if action == "create" and result and hasattr(result, "data") and isinstance(result.data, dict):
        created_id = result.data.get("assistant_id") or result.data.get("id")
        if created_id:
            resource_id = str(created_id)

    # For test commands, the resource type is the assistant being tested
    if resource_type == "test" and resource_id:
        return [{"type": "assistant", "id": resource_id, "action": action}]

    if resource_id:
        return [{"type": resource_type, "id": resource_id, "action": action}]
    elif resource_type != "help":
        return [{"type": resource_type, "id": None, "action": action}]

    return []


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
    tool_audit: list[dict] = field(default_factory=list)

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
            result_text = await self._resolve_pending_action(user_message)
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
                    result = await self._execute_tool(tc)
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

    async def chat_stream(self, user_message: str) -> AsyncIterator[dict | str]:
        """Like chat() but streams events.

        Yields:
            dict: status events {"status": "...", "command": "..."}
            str: text content chunks from the final LLM response
        """
        if self.pending_action:
            result_text = await self._resolve_pending_action(user_message)
            if result_text is not None:
                async for event in self._run_agent_loop_stream():
                    yield event
                return

        if self.session_logger:
            self.session_logger.log_user_message(user_message)
        self.conversation.append({"role": "user", "content": user_message})
        async for event in self._run_agent_loop_stream():
            yield event

    async def _run_agent_loop_stream(self) -> AsyncIterator[dict | str]:
        """Run tool-calling loop with status events, then stream final response."""
        tool_rounds = 0

        while True:
            yield {"status": "thinking"}

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
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in message.tool_calls
                    ],
                })

                should_stop = False
                for tc in message.tool_calls:
                    # Emit status before executing
                    cmd = _describe_tool_call(tc)
                    yield {"status": "tool", "command": cmd}

                    result = await self._execute_tool(tc)
                    ok = result.get("success", False)
                    logger.info(f"Tool: {tc.function.arguments} → {ok}")

                    yield {"status": "tool_done", "command": cmd, "success": ok}

                    self.conversation.append({
                        "role": "tool", "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str, ensure_ascii=False),
                    })
                    if result.get("awaiting_user_confirmation"):
                        should_stop = True

                if tool_rounds >= self.max_tool_rounds:
                    self.conversation.append({
                        "role": "user",
                        "content": "[System: Maximum tool rounds reached. Please respond.]",
                    })

                if should_stop:
                    yield {"status": "responding"}
                    messages = [{"role": "system", "content": self.system_prompt}] + self.conversation
                    full_text = ""
                    stream = await self.llm_client.chat.completions.create(
                        model=self.model, messages=messages, stream=True,
                    )
                    async for chunk in stream:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if delta and delta.content:
                            full_text += delta.content
                            yield delta.content
                    self.conversation.append({"role": "assistant", "content": full_text})
                    if self.session_logger:
                        self.session_logger.log_agent_response(full_text)
                    return

                continue

            # No tool calls — stream the final text response
            yield {"status": "responding"}
            messages = [{"role": "system", "content": self.system_prompt}] + self.conversation
            full_text = ""
            stream = await self.llm_client.chat.completions.create(
                model=self.model, messages=messages, stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    full_text += delta.content
                    yield delta.content
            self.conversation.append({"role": "assistant", "content": full_text})
            if self.session_logger:
                self.session_logger.log_agent_response(full_text)
            return

    async def _execute_tool(self, tool_call: Any) -> dict:
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
            self._record_audit(command, action_key, True, 0, None, queued=True)
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
                "message": (
                    "This action needs user approval. Briefly describe what will change (1-2 lines). "
                    "Then ask for confirmation IN THE USER'S LANGUAGE using a yes/no format. "
                    "Do NOT use numbered options. Examples by language:\n"
                    "  English: **Approve? (y)es / (n)o / tell me more**\n"
                    "  Spanish: **Confirmar? (s)i / (n)o / cuéntame más**\n"
                    "  Catalan: **Confirmar? (s)í / (n)o / explica'm més**\n"
                    "  Basque: **Onartu? (b)ai / (e)z / gehiago kontatu**\n"
                    "Use the language you have been speaking in this conversation."
                ),
            }

        # policy == "auto" — execute directly
        result = await self.shell.execute(command)
        self._record_audit(command, action_key, result.success, result.elapsed_ms, result)
        if self.session_logger:
            self.session_logger.log_tool_call(
                command=command,
                success=result.success,
                elapsed_ms=result.elapsed_ms,
                data=result.data,
                error=result.error,
            )

        # Special handling for skill.load — build a rich result with skill prompt + startup data
        # The actual injection happens through the normal tool result flow (no direct conversation manipulation)
        if action_key == "skill.load" and result.success and isinstance(result.data, dict):
            skill_data = result.data
            parts = []
            parts.append(
                f"Skill '{skill_data.get('name', '?')}' loaded MID-CONVERSATION. "
                f"Follow these instructions from now on, but do NOT restart the conversation. "
                f"Do NOT greet the user again. Do NOT repeat any startup analysis. "
                f"Continue naturally from where you were — the user already told you what they need. "
                f"CRITICAL: The skill instructions below are in English for clarity, but you MUST "
                f"CONTINUE responding in the SAME LANGUAGE you were using before. Do NOT switch to English."
            )
            parts.append(f"\n--- SKILL INSTRUCTIONS ---\n{skill_data.get('prompt', '')}")

            # Run startup actions and collect results
            for action in skill_data.get("startup_actions", []):
                startup_result = await self.shell.execute(action)
                startup_key = _parse_action_key(action)
                self._record_audit(action, startup_key, startup_result.success, startup_result.elapsed_ms, startup_result)
                if startup_result.success:
                    parts.append(f"\n[Startup: {action}]\n{json.dumps(startup_result.data, default=str, ensure_ascii=False)[:3000]}")

            return {"success": True, "data": "\n".join(parts)}

        return result.to_dict()

    async def _resolve_pending_action(self, user_message: str) -> str | None:
        """Check if user approved/rejected the pending action.

        Returns a string (can be empty) if the action was resolved,
        None if the message is unrelated to the pending action.
        """
        action = self.pending_action
        classification = classify_user_confirmation(user_message)

        if classification == "approve":
            # Execute the queued command
            self.pending_action = None
            result = await self.shell.execute(action["command"])

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

    def _record_audit(
        self, command: str, action_key: str | None,
        success: bool, elapsed_ms: float, result: Any,
        queued: bool = False,
    ) -> None:
        """Record a structured tool use event."""
        from datetime import datetime
        intent = _TOOL_LABELS.get(action_key or "", command[:50])
        if "--bypass" in command:
            intent += " (pipeline debug)"
        if queued:
            intent += " [awaiting confirmation]"

        event = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "command": command,
            "action_key": action_key or "",
            "intent": intent,
            "success": success,
            "elapsed_ms": round(elapsed_ms, 1),
            "artifacts": _extract_artifacts(command, result),
            "summary": _summarize_result(action_key or "", result),
        }
        self.tool_audit.append(event)

    def reset(self) -> None:
        self.conversation.clear()
        self.pending_action = None
        self.tool_audit.clear()

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
