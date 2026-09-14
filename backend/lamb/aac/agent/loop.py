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
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from lamb.aac.authorization import ActionAuthorizer, classify_user_confirmation
from lamb.aac.liteshell.shell import LiteShell, CommandContext, ShellResult, prepare_command
from lamb.aac.session_logger import SessionLogger
from lamb.aac.skill_routing import SkillRouting, catalogue_prompt
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")

DEFAULT_SYSTEM_PROMPT = """\
You are an AI assistant designer for the LAMB platform. Help educators \
create, configure, test, and refine AI learning assistants.

## Commands

Publishing in LAMB is supported with lamb assistant publish/unpublish ID, after user confirmation. External LMS course setup is a separate guided user action. Offer only actions supported by your tools; label guidance as guidance.
READ: lamb assistant list | list-shared | list-published | get <id_or_name> | config | debug <id> --message "text"
READ: lamb rubric list | get <uuid> | export <uuid> [--format md]
READ: lamb kb list | get <id> | query <id> "text" [--top-k N]
WRITE (approval): lamb kb create NAME [--description TEXT] | upload KB_ID OWNED_FILE_REFERENCE [--plugin NAME]
WRITE (approval): lamb rubric create TITLE --criteria JSON | update ID [--title TEXT] [--criteria JSON | --weights JSON]
READ: lamb test evaluations ASSISTANT_ID
Assistant bindings: --file-path OWNED_TEXT_REFERENCE | --rubric-id ID --rubric-format markdown
Use the attachment references supplied by the user; never invent paths.
READ: lamb template list | get <id>
READ: lamb analytics chats <assistant_id> | chat-detail <assistant_id> <chat_id> | stats <assistant_id> | timeline <assistant_id> [--period day|week|month]

To see configured organization models and defaults, use: lamb assistant config
It returns connectors, their models, and organization defaults. ALWAYS use this for model selection.
DOCS: lamb docs index | read <topic> [--section "heading"]
SKILLS: lamb skill list | load <skill-id> [--assistant <id>]
SESSION: lamb session rename "New title"  (update the current session's title — do this when you learn the user's intent or target assistant name, so the session is findable later)
CHAT: lamb assistant chat <id> --message "text" [--persist] [--chat-id ID]
For multi-turn conversations use --persist on EVERY turn, retain the returned chat_id, and pass --chat-id on later turns. Without --persist a quick test is not saved and returns no chat_id.
TEST: lamb test scenarios <id> | add <id> <title> --message "text" --expected "expected behavior" | run <id> [--bypass] | runs <id> | evaluate <run_id> <good|bad|mixed> <assistant_id>
Persist every approved test expectation with --expected. Read scenarios back and compare all approved fields before claiming creation is complete.
WRITE: lamb assistant create <name> [--system-prompt "..." --llm model ...] | update <id> [...] | delete <id>

debug and --bypass = inspect mode. It runs the full prompt assembly (system prompt + RAG context + template)
WITHOUT calling the LLM. It returns the constructed messages array — this IS the expected output.
An empty or minimal response from debug is NORMAL for non-RAG assistants (no KB content to inject).
For RAG assistants, debug shows what context was retrieved — useful for verifying KB content.
run without --bypass = real LLM completion (uses tokens, gets an actual response).
When running a full test suite on a RAG assistant, suggest checking with debug first.
For casual single questions or non-RAG assistants, just run directly.

## CRITICAL: Prompt Template Rules

For the built-in simple_augment processor, a non-empty prompt_template replaces the
last user message. Include `{user_input}` to retain that message and `{context}`
to include retrieved KB, file or rubric content. Inspect custom processors before
making claims about their template semantics.

An empty template passes the original user message through unchanged. It is valid
for no_rag; do not claim that it drops the question or breaks the pipeline. It does
not inject RAG context, so flag it on RAG assistants and verify with debug.

When creating a simple_augment RAG assistant, use a template containing both fields
or omit the template so the server supplies its context-bearing creation default.
Examples:
Non-RAG: --prompt-template "{user_input}"
RAG: --prompt-template "Context:\n{context}\n\nStudent question: {user_input}"

When updating, preserve the existing template unless changing it is part of the
user-approved request. Flag a grounding problem and propose a separate correction;
do not silently replace it during an unrelated description or model edit.
Debug/bypass shows the actual assembled messages. If rubric or KB content is absent
there, do not claim it will be injected later or infer grounding from a plausible answer.

## Style rules

BE CONCISE. Maximum 5-6 lines per response unless the user asks for detail.
Short sentences. No filler. No repeating what the user already knows.
Use bullet points, not paragraphs.

UI TUTORIALS (0.7): When the user asks how to operate the UI, or needs to choose
files from their own computer, read the relevant ui-* documentation with lamb docs
index / read before giving steps. The user operates the existing UI: do not ask for
a local filesystem path, invent an upload reference, or treat file selection as
something you can do for them. Guide KB ingestion through the Knowledge Bases UI.
Do not substitute the AAC Attach button or CLI commands for that UI tutorial.
Read the whole relevant guide first. Use --section only with an exact heading
already returned by that guide; do not invent section names.
Exact tutorial topic map (do not guess names or headings):
- KB creation, document ingestion, processing and queries: ui-knowledge-bases.
- Assistant creation/editing, single-file upload, KB binding: ui-assistants.
- Assistant chat, test questions/expectations, runs/evaluations: ui-testing.
- Rubric criteria, weights and rubric binding: ui-rubrics.
Single File Rag uses the assistant form's Upload New File control; it does NOT
use the KB Ingest Content tab. Read ui-assistants for this case.
Include the documented full-size screenshot link so small-screen users can open
it. Do not repeat the same image within a response.
Show the next useful steps, then wait for the user's report; do not execute writes
while teaching those steps. A request for a tutorial is not permission to do it.
When asked to show where/how, include the relevant documentation screenshot using
its exact Markdown image URL and descriptive alt text, outside code fences.
Tutorial URLs are root-relative: /img/aac-tutorials/FILE.png. Copy the entire
Markdown image and full-size link verbatim from docs.read. NEVER add a hostname,
change /img/ to /images/, or turn the path into an external URL. No example
hostname is available. A made-up link will not display the screenshot. Show
one or two relevant images, not the whole manual. Never invent screenshot URLs.
Screenshots are examples, not the user's current state. Preserve button labels
from the guide; explain them in the user's language. If their UI differs, ask
what they see. Only claim completion after checking real saved state or clearly
attribute it to the user's report. A timeout or 'processing' is not completion.
For explicit CLI help, retain the documented CLI workflow. These tutorial rules
do not remove existing tools for separately requested, authorized agent actions.

SPEAK LIKE A HELPFUL COLLEAGUE, NOT A DEVELOPER.
The user is an educator, not an engineer. Do NOT mention:
- "pipeline", "debug", "bypass" — say "test" or "check" instead
- "prompt processor", "simple_augment" — just skip these internal details
- "RAG_collections", "api_callback" — say "knowledge base" or "connected documents"
- "prompt_template" — say "how the question is assembled" if they need to know
Only use technical terms if the user used them first or explicitly asks for internals.

When showing assistant details, HIDE these internal fields (never show to user):
- group_id, group_name, owi_group_id — internal OWI integration
- organization_id, organization — internal tenant ID
- api_callback — same as metadata (internal field name)
- access_level, is_owner — internal permission data
- Unix timestamps — convert to readable dates or skip
- owner email — skip unless user asks "who owns this?"
Show only: name, description, model, RAG status, connected KB, system prompt, prompt template, published status.

NEVER switch language mid-conversation. If the user speaks Spanish, respond in Spanish. Always.
NEVER refuse a user's explicit request. If they want to run a real test, run it. You may suggest bypass first, but if the user insists, do what they ask.

When the user asks to do something covered by a specific skill (create, improve, explain, test an assistant),
use `lamb skill load <skill-id>` to switch. Select from the workflow catalogue; use `lamb skill list` if unsure.

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

## Canvas (side panel)

When presenting tables, comparisons, rubrics, or structured data that benefits from a wider view,
wrap it in canvas markers in your response:

<<<CANVAS title="Your Title">>>
(markdown content — tables, lists, code blocks)
<<<END_CANVAS>>>

The content appears in a side panel next to the terminal. The user sees both simultaneously.
Keep your terminal text brief — just reference what's in the canvas.
Use <<<CANVAS_CLEAR>>> to dismiss the panel.
Only use canvas for content that genuinely needs space (tables with 3+ columns, comparisons).
Do NOT use canvas for simple bullet points or short text.

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
                "'lamb assistant create \"My Tutor\" --system-prompt \"You are...\" --llm MODEL_FROM_CONFIG'."
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
    "analytics.chats": "Reading assistant chats",
    "analytics.chat-detail": "Reading assistant chat-detail",
    "analytics.stats": "Reading assistant stats",
    "analytics.timeline": "Reading assistant timeline",
    "assistant.list": "Loading assistants",
    "assistant.list-shared": "Loading shared assistants",
    "assistant.get": "Reading assistant config",
    "assistant.config": "Checking available options",
    "assistant.debug": "Running pipeline debug",
    "assistant.create": "Creating assistant",
    "assistant.update": "Updating assistant",
    "assistant.publish": "Publishing assistant",
    "assistant.unpublish": "Unpublishing assistant",
    "assistant.delete": "Deleting assistant",
    "rubric.list": "Loading rubrics",
    "rubric.get": "Reading rubric",
    "kb.list": "Loading knowledge bases",
    "kb.get": "Reading knowledge base",
    "assistant.list-published": "Loading published assistants",
    "template.list": "Loading templates",
    "assistant.chat": "Chatting with assistant",
    "test.scenarios": "Loading test scenarios",
    "test.add": "Creating test scenario",
    "test.run": "Running tests",
    "test.runs": "Loading test results",
    "test.evaluate": "Recording evaluation",
    "skill.list": "Loading available skills",
    "skill.load": "Switching to skill",
    "session.rename": "Renaming session",
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
        elif action_key in {"assistant.publish", "assistant.unpublish"}:
            return f"assistant {d.get('id', '?')}: published={d.get('published')}"
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
        "publish": "publish", "unpublish": "unpublish",
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
class AgentLoop(SkillRouting):
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
    skill_state: dict | None = None
    session_id: str = ""  # current AAC session ID (for self-referencing commands like session.rename)

    def load_skills(self, skills_dir: Path | str) -> None:
        """Load the compact catalogue only; workflow bodies are activated on demand."""
        self.system_prompt += catalogue_prompt()

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
        parts = []
        async for event in self._run_agent_events(streaming=False):
            if isinstance(event, str):
                parts.append(event)
        return "".join(parts)

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
        async for event in self._run_agent_events(streaming=True):
            yield event

    async def _request_message(self, messages: list[dict], tools_enabled: bool,
                               streaming: bool) -> AsyncIterator[dict | str]:
        """One provider request, with the same message result for both consumers."""
        self.record_request_prefix(messages, TOOL_DEFINITIONS if tools_enabled else None)
        kwargs = {"model": self.model, "messages": messages}
        if tools_enabled:
            kwargs.update(tools=TOOL_DEFINITIONS, tool_choice="auto")
        started = time.monotonic()
        if not streaming:
            response = await self.llm_client.chat.completions.create(**kwargs)
            if self.session_logger:
                usage = getattr(response, "usage", None)
                self.session_logger.log("provider_response", {"elapsed_ms": round((time.monotonic()-started)*1000,1),
                    "usage": usage.model_dump() if hasattr(usage, "model_dump") else None})
            message = response.choices[0].message
            yield {"_message": {
                "role": "assistant", "content": message.content or "",
                "tool_calls": [{"id": tc.id, "type": "function", "function": {
                    "name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in (message.tool_calls or [])],
            }}
            return

        stream = await self.llm_client.chat.completions.create(**kwargs, stream=True)
        text = ""
        calls = {}
        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    text += delta.content
                    yield delta.content
                for part in (getattr(delta, "tool_calls", None) or []):
                    index = getattr(part, "index", None)
                    if index is not None:
                        key = ("index", index)
                    elif getattr(part, "id", None):
                        key = next((k for k,v in calls.items() if v["id"] == part.id), ("id", part.id))
                    elif len(calls) == 1:
                        key = next(iter(calls))
                    else:
                        raise ValueError("Ambiguous streaming tool call: provider omitted both index and id")
                    call = calls.setdefault(key, {
                        "id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                    if part.id:
                        call["id"] = part.id
                    if part.function:
                        if part.function.name:
                            call["function"]["name"] += part.function.name
                        if part.function.arguments:
                            call["function"]["arguments"] += part.function.arguments
        finally:
            await stream.close()
        yield {"_message": {"role": "assistant", "content": text,
                             "tool_calls": list(calls.values())}}

    async def _run_agent_events(self, streaming: bool) -> AsyncIterator[dict | str]:
        """Shared legacy turn control; transport does not change tool semantics."""
        tool_rounds = 0
        while True:
            yield {"status": "thinking"}
            tools_enabled = tool_rounds < self.max_tool_rounds and not self.pending_action
            messages = [{"role": "system", "content": self.system_prompt}] + self.conversation
            message = None
            async for event in self._request_message(messages, tools_enabled, streaming):
                if isinstance(event, dict) and "_message" in event:
                    message = event["_message"]
                else:
                    yield event
            if message is None:
                raise ValueError("Provider returned no assistant message")
            calls = message.pop("tool_calls", [])
            if calls and tools_enabled:
                tool_rounds += 1
                self.conversation.append({**message, "tool_calls": calls})
                waiting = False
                for call in calls:
                    tc = SimpleNamespace(id=call["id"], function=SimpleNamespace(**call["function"]))
                    command = _describe_tool_call(tc)
                    yield {"status": "tool", "command": command}
                    if waiting:
                        result = {"success": False, "error": "Not executed: confirmation or a newly loaded workflow requires a new decision."}
                    else:
                        result = await self._execute_tool(tc)
                    waiting = waiting or bool(result.get("awaiting_user_confirmation") or result.get("skill_loaded"))
                    self.conversation.append({"role": "tool", "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str, ensure_ascii=False)})
                    yield {"status": "tool_done", "command": command, "success": result.get("success", False)}
                if tool_rounds >= self.max_tool_rounds:
                    self.conversation.append({"role": "user", "content":
                        "[System: Maximum tool rounds reached. Respond using the results already available. No further tools are allowed this turn.]"})
                continue

            # A provider that ignores the no-tools request must not execute more work.
            text = message["content"]
            if calls:
                text = "No further tools were executed. The tool limit was reached or an action awaits confirmation."
                yield text
            elif not streaming:
                yield text
            self.conversation.append({"role": "assistant", "content": text})
            if self.session_logger:
                self.session_logger.log_agent_response(text)
            return

    async def _execute_tool(self, tool_call: Any) -> dict:
        """Execute a tool call, checking authorization policy."""
        if tool_call.function.name != "execute_command":
            return {"success": False, "error": "Unknown tool function"}
        try:
            fn_args = json.loads(tool_call.function.arguments)
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "error": "Invalid JSON in tool arguments"}

        if not isinstance(fn_args, dict):
            return {"success": False, "error": "Tool arguments must be a JSON object"}
        command = fn_args.get("command", "")
        if not isinstance(command, str) or not command.strip():
            return {"success": False, "error": "No command provided"}

        # Reject unsupported/malformed commands before they can become pending writes.
        try:
            action_key, parsed_args, parsed_kwargs, help_requested = prepare_command(command, getattr(self.shell, "allowlist", None))
        except ValueError as error:
            result = ShellResult(False, error=str(error), command=command)
            self._record_audit(command, None, False, 0, result)
            if self.session_logger:
                self.session_logger.log_tool_call(command=command, success=False, elapsed_ms=0, error=result.error)
            return result.to_dict()
        policy = "auto" if help_requested else self.authorizer.check(action_key)

        if self.skill_state is not None and not help_requested:
            if self.pending_action and action_key == "skill.load":
                return {"success": False, "error": "Resolve the pending confirmation before switching workflows."}
            try:
                if action_key == "skill.load":
                    context = dict(self.skill_state.get("context", {}))
                    if "assistant" in parsed_kwargs or "a" in parsed_kwargs:
                        context["assistant_id"] = parsed_kwargs.get("assistant", parsed_kwargs.get("a"))
                    if "language" in parsed_kwargs:
                        context["language"] = parsed_kwargs["language"]
                    text = self.activate_skill(parsed_args[0], context)
                    self._record_audit(command, action_key, True, 0, ShellResult(True, data={"skill_id": self.skill_state["skill_id"]}))
                    return {"success": True, "data": text, "action_executed": False, "skill_loaded": self.skill_state["skill_id"]}
                if policy != "never" and not self.pending_action:
                    instructions = self.required_skill(action_key, parsed_args, parsed_kwargs)
                    if instructions:
                        self._record_audit(command, action_key, False, 0, ShellResult(False, error="Required workflow loaded; command not executed."))
                        return {"success": False, "error": "Required workflow loaded. The requested command was NOT executed. Read the recipe and reconsider the command before retrying.",
                                "skill_loaded": self.skill_state["skill_id"], "instructions": instructions}
            except ValueError as error:
                return {"success": False, "error": str(error)}

        # Self-referencing commands: inject current session_id
        if action_key == "session.rename" and self.session_id and "--session" not in command:
            command = f"{command} --session {self.session_id}"

        if policy == "never":
            return {"success": False, "error": f"Action '{action_key}' is not allowed"}

        if policy == "ask" and self.pending_action:
            return {"success": False, "awaiting_user_confirmation": True,
                    "error": "An action is already awaiting confirmation"}
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
                if self.authorizer.check(self.authorizer.resolve_action_key(action) or "") != "auto":
                    parts.append(f"\n[Startup skipped: {action}] Requires explicit authorization.")
                    continue
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
        # Older sessions may already contain an unsupported proposal. Recover on
        # the next message without executing it or requiring meaningless approval.
        try:
            prepare_command(action["command"], getattr(self.shell, "allowlist", None))
        except ValueError as error:
            self.pending_action = None
            result = ShellResult(False, error=str(error), command=action["command"])
            self._record_audit(action["command"], action.get("action_key"), False, 0, result)
            self.conversation.append({"role": "user", "content": f"[System: Removed invalid pending action; nothing executed. {error}]"})
            return None
        classification = classify_user_confirmation(user_message)

        if classification == "approve":
            # Execute the queued command
            self.pending_action = None
            result = await self.shell.execute(action["command"])
            self._record_audit(action["command"], action.get("action_key"), result.success, result.elapsed_ms, result)

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
