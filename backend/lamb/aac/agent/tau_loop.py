"""AAC agent loop on the vendored tau engine (Phase 3 of the AAC refactoring).

One event-emitting loop replaces the two duplicated legacy loops
(loop.py `_run_agent_loop` / `_run_agent_loop_stream`): `chat()` and
`chat_stream()` both consume the same `run_agent_loop` event stream, so the
terminal-vs-frontend divergence is impossible by construction, `max_tool_rounds`
is actually enforced (the legacy loop only appended a warning message), and
token usage is accounted per LLM call via the vendored usage patch.

Drop-in replacement for `AgentLoop`: same constructor signature, same public
surface (chat / chat_stream / load_skills / reset / get_stats, plus the
conversation / pending_action / tool_audit / session_id attributes the router
persists into the session envelope). The envelope wire format is unchanged —
conversation entries stay OpenAI-style dicts, `chat_stream` yields the legacy
status-dict vocabulary. Selection is by the AAC_LOOP env var (see
`create_agent_loop` in this package's __init__).

What stays AAC's (unchanged, by design): the liteshell and its single
`execute_command` tool, authorization as Python policy (auto/ask/never + the
multilingual confirmation classifier), skills-as-markdown, sessions in LAMB's
database. What the engine provides: the loop, typed events, retry/backoff,
and usage reporting.

Behavioral notes vs legacy, both deliberate:
- The final response is emitted after the model call completes (one call,
  buffered) instead of via the legacy loop's second streamed call — same wire
  grammar, half the LLM calls on the no-tool path. Token-level streaming
  granularity returns with the versioned event protocol (Phase 4).
- While an action awaits user confirmation, further write attempts in the
  same run are refused at the executor instead of queueing a second action.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from lamb._vendor.tau.tau_agent.events import (
    ErrorEvent,
    MessageEndEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnStartEvent,
)
from lamb._vendor.tau.tau_agent.loop import run_agent_loop
from lamb._vendor.tau.tau_agent.messages import (
    AgentMessage,
    AssistantMessage,
    ToolResultMessage,
    UserMessage,
)
from lamb._vendor.tau.tau_agent.tools import AgentTool, AgentToolResult, ToolCall
from lamb._vendor.tau.tau_ai.env import OpenAICompatibleConfig
from lamb._vendor.tau.tau_ai.openai_compatible import OpenAICompatibleProvider
from lamb.aac.authorization import ActionAuthorizer, classify_user_confirmation
from lamb.aac.agent.loop import (
    DEFAULT_SYSTEM_PROMPT,
    TOOL_DEFINITIONS,
    _TOOL_LABELS,
    _extract_artifacts,
    _parse_action_key,
    _summarize_result,
)
from lamb.aac.liteshell.shell import LiteShell
from lamb.aac.session_logger import SessionLogger
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")

_TOOL_NAME = "execute_command"
_TOOL_SCHEMA = TOOL_DEFINITIONS[0]["function"]["parameters"]
_TOOL_DESCRIPTION = TOOL_DEFINITIONS[0]["function"]["description"]


def _describe_command(command: str) -> str:
    key = _parse_action_key(command)
    label = _TOOL_LABELS.get(key, command[:50])
    if "--bypass" in command:
        label += " (pipeline debug)"
    return label


# ---------------------------------------------------------------------------
# Envelope <-> tau transcript mapping. The session envelope keeps the legacy
# OpenAI-dict format on disk; the engine sees typed messages.
# ---------------------------------------------------------------------------

def _to_tau_messages(conversation: List[dict]) -> List[AgentMessage]:
    out: List[AgentMessage] = []
    for msg in conversation:
        role = msg.get("role")
        if role == "user":
            out.append(UserMessage(content=msg.get("content") or ""))
        elif role == "assistant":
            tool_calls = []
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                try:
                    arguments = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                if not isinstance(arguments, dict):
                    arguments = {}
                tool_calls.append(ToolCall(
                    id=tc.get("id") or "call_unknown",
                    name=fn.get("name") or _TOOL_NAME,
                    arguments=arguments,
                ))
            out.append(AssistantMessage(
                content=msg.get("content") or "", tool_calls=tool_calls))
        elif role == "tool":
            out.append(ToolResultMessage(
                tool_call_id=msg.get("tool_call_id") or "call_unknown",
                name=_TOOL_NAME,
                content=msg.get("content") or "",
            ))
        else:
            # Legacy system-marker messages ride as user content upstream too
            out.append(UserMessage(content=msg.get("content") or ""))
    return out


def _from_tau_message(message: AgentMessage) -> dict:
    if isinstance(message, AssistantMessage):
        if message.tool_calls:
            return {
                "role": "assistant",
                "content": message.content or None,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name,
                                  "arguments": json.dumps(tc.arguments,
                                                          ensure_ascii=False)}}
                    for tc in message.tool_calls
                ],
            }
        return {"role": "assistant", "content": message.content}
    if isinstance(message, ToolResultMessage):
        return {"role": "tool", "tool_call_id": message.tool_call_id,
                "content": message.content}
    return {"role": "user", "content": message.content}


@dataclass
class TauAgentLoop:
    """The AAC agent loop, tau engine. Public surface mirrors AgentLoop."""

    shell: LiteShell
    llm_client: Any = None  # AsyncOpenAI; source of api_key/base_url
    model: str = ""
    authorizer: ActionAuthorizer = field(default_factory=ActionAuthorizer)
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_tool_rounds: int = 10
    conversation: List[dict] = field(default_factory=list)
    session_logger: Optional[SessionLogger] = None
    pending_action: Optional[dict] = None
    tool_audit: List[dict] = field(default_factory=list)
    session_id: str = ""
    usage_totals: Dict[str, int] = field(default_factory=lambda: {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "llm_calls": 0})

    # ------------------------------------------------------------------
    # Public surface (parity with AgentLoop)
    # ------------------------------------------------------------------

    def load_skills(self, skills_dir: Path | str) -> None:
        skills_dir = Path(skills_dir)
        if not skills_dir.is_dir():
            return
        skill_texts = []
        for md_file in sorted(skills_dir.glob("*.md")):
            skill_texts.append(f"\n--- Skill: {md_file.stem} ---\n{md_file.read_text()}")
        if skill_texts:
            self.system_prompt += "\n\n# Skills\n" + "\n".join(skill_texts)

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
            "usage": dict(self.usage_totals),
        }

    async def chat(self, user_message: str) -> str:
        """One user turn -> final assistant text. Same engine as chat_stream."""
        if not await self._pre_turn(user_message):
            # Ambiguous reply to a pending action: fall through with the
            # message appended, pending action retained (legacy behavior).
            pass
        final_text = ""
        async for event in self._run_events():
            if isinstance(event, MessageEndEvent):
                msg = event.message
                if isinstance(msg, AssistantMessage) and not msg.tool_calls:
                    final_text = msg.content or ""
        if self.session_logger:
            self.session_logger.log_agent_response(final_text)
        return final_text

    async def chat_stream(self, user_message: str) -> AsyncIterator[dict | str]:
        """One user turn as the legacy status-dict stream.

        Vocabulary (frozen until the Phase-4 protocol): {"status": "thinking"},
        {"status": "tool", "command"}, {"status": "tool_done", "command",
        "success"}, {"status": "responding"}, then text chunks.
        """
        await self._pre_turn(user_message)
        final_text = ""
        current_command = ""
        async for event in self._run_events():
            if isinstance(event, TurnStartEvent):
                yield {"status": "thinking"}
            elif isinstance(event, ToolExecutionStartEvent):
                current_command = str(
                    event.tool_call.arguments.get("command", ""))
                yield {"status": "tool", "command": _describe_command(current_command)}
            elif isinstance(event, ToolExecutionEndEvent):
                yield {"status": "tool_done",
                       "command": _describe_command(current_command),
                       "success": event.result.ok}
            elif isinstance(event, MessageEndEvent):
                msg = event.message
                if isinstance(msg, AssistantMessage) and not msg.tool_calls:
                    final_text = msg.content or ""
                    yield {"status": "responding"}
                    if final_text:
                        yield final_text
            elif isinstance(event, ErrorEvent) and not event.recoverable:
                raise RuntimeError(f"AAC agent error: {event.message}")
        if self.session_logger:
            self.session_logger.log_agent_response(final_text)

    # ------------------------------------------------------------------
    # Engine plumbing
    # ------------------------------------------------------------------

    def _provider_factory(self) -> OpenAICompatibleProvider:
        api_key = getattr(self.llm_client, "api_key", None) or ""
        base_url = str(getattr(self.llm_client, "base_url", "") or
                       "https://api.openai.com/v1").rstrip("/")
        return OpenAICompatibleProvider(OpenAICompatibleConfig(
            api_key=api_key, base_url=base_url,
            provider_name="LAMB AAC (tau loop)"))

    async def _run_events(self):
        """Drive the vendored loop; sync transcript + usage back afterwards."""
        tau_messages = _to_tau_messages(self.conversation)
        baseline = len(tau_messages)
        provider = self._provider_factory()
        tool = AgentTool(
            name=_TOOL_NAME, description=_TOOL_DESCRIPTION,
            input_schema=_TOOL_SCHEMA, executor=self._execute_command)
        try:
            async for event in run_agent_loop(
                    provider=provider, model=self.model,
                    system=self.system_prompt, messages=tau_messages,
                    tools=[tool], max_turns=self.max_tool_rounds + 1,
                    signal=None):
                if isinstance(event, MessageEndEvent):
                    self.usage_totals["llm_calls"] += 1
                    if event.usage:
                        self.usage_totals["prompt_tokens"] += event.usage.prompt_tokens
                        self.usage_totals["completion_tokens"] += event.usage.completion_tokens
                        self.usage_totals["total_tokens"] += event.usage.total_tokens
                yield event
        finally:
            await provider.aclose()
            for message in tau_messages[baseline:]:
                self.conversation.append(_from_tau_message(message))

    async def _pre_turn(self, user_message: str) -> bool:
        """Pending-action resolution + user-message append (legacy semantics).

        Returns True when the turn proceeds normally; False when the message
        was ambiguous against a pending action (pending retained).
        """
        if self.pending_action:
            resolved = await self._resolve_pending_action(user_message)
            if resolved is not None:
                return True
            # Ambiguous: treat as a new message, keep the pending action.
        if self.session_logger:
            self.session_logger.log_user_message(user_message)
        self.conversation.append({"role": "user", "content": user_message})
        return self.pending_action is None

    async def _resolve_pending_action(self, user_message: str) -> Optional[str]:
        """Port of the legacy resolution flow — classifier and side effects
        are identical; only the caller changed."""
        action = self.pending_action
        classification = classify_user_confirmation(user_message)

        if classification == "approve":
            self.pending_action = None
            result = await self.shell.execute(action["command"])
            self._record_audit(action["command"], action.get("action_key"),
                               result.success, result.elapsed_ms, result)
            if self.session_logger:
                self.session_logger.log_user_message(user_message)
                self.session_logger.log_tool_call(
                    command=action["command"], success=result.success,
                    elapsed_ms=result.elapsed_ms, data=result.data,
                    error=result.error)
            self.conversation.append({"role": "user", "content": user_message})
            result_summary = json.dumps(result.to_dict(), default=str,
                                        ensure_ascii=False)
            self.conversation.append({
                "role": "user",
                "content": f"[System: User approved. Action executed. "
                           f"Result: {result_summary}]",
            })
            return ""

        if classification == "reject":
            self.pending_action = None
            if self.session_logger:
                self.session_logger.log_user_message(user_message)
                self.session_logger.log("action_rejected",
                                        {"command": action["command"]})
            self.conversation.append({"role": "user", "content": user_message})
            self.conversation.append({
                "role": "user",
                "content": "[System: User declined the action. "
                           "It was not executed.]",
            })
            return ""

        return None

    # ------------------------------------------------------------------
    # The one tool: the liteshell, with authorization in the scaffolding
    # ------------------------------------------------------------------

    async def _execute_command(self, arguments, signal=None) -> AgentToolResult:
        command = str(arguments.get("command") or "")
        call_id = "call_pending"  # loop rewrites tool_call_id on mismatch
        if not command:
            return AgentToolResult(tool_call_id=call_id, name=_TOOL_NAME,
                                   ok=False, content="No command provided",
                                   error="No command provided")

        action_key = self.authorizer.resolve_action_key(command)
        policy = self.authorizer.check(action_key) if action_key else "auto"

        if action_key == "session.rename" and self.session_id and "--session" not in command:
            command = f"{command} --session {self.session_id}"

        if policy == "never":
            payload = {"success": False,
                       "error": f"Action '{action_key}' is not allowed"}
            return AgentToolResult(
                tool_call_id=call_id, name=_TOOL_NAME, ok=False,
                content=json.dumps(payload, ensure_ascii=False),
                data=payload, error=payload["error"])

        if policy == "ask":
            if self.pending_action:
                payload = {
                    "success": False,
                    "error": "Another action is already awaiting user "
                             "confirmation. Ask the user to resolve it first.",
                }
                return AgentToolResult(
                    tool_call_id=call_id, name=_TOOL_NAME, ok=False,
                    content=json.dumps(payload, ensure_ascii=False),
                    data=payload, error=payload["error"])
            self.pending_action = {"command": command, "action_key": action_key,
                                   "tool_call_id": None}
            self._record_audit(command, action_key, True, 0, None, queued=True)
            if self.session_logger:
                self.session_logger.log("action_queued", {
                    "command": command, "action_key": action_key})
            payload = {
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
            return AgentToolResult(
                tool_call_id=call_id, name=_TOOL_NAME, ok=True,
                content=json.dumps(payload, ensure_ascii=False), data=payload)

        # policy == "auto"
        result = await self.shell.execute(command)
        self._record_audit(command, action_key, result.success,
                           result.elapsed_ms, result)
        if self.session_logger:
            self.session_logger.log_tool_call(
                command=command, success=result.success,
                elapsed_ms=result.elapsed_ms, data=result.data,
                error=result.error)

        # skill.load: assemble skill prompt + startup data through the normal
        # tool-result flow (identical to legacy)
        if action_key == "skill.load" and result.success and isinstance(result.data, dict):
            skill_data = result.data
            parts = [
                f"Skill '{skill_data.get('name', '?')}' loaded MID-CONVERSATION. "
                f"Follow these instructions from now on, but do NOT restart the conversation. "
                f"Do NOT greet the user again. Do NOT repeat any startup analysis. "
                f"Continue naturally from where you were — the user already told you what they need. "
                f"CRITICAL: The skill instructions below are in English for clarity, but you MUST "
                f"CONTINUE responding in the SAME LANGUAGE you were using before. Do NOT switch to English."
            ]
            parts.append(f"\n--- SKILL INSTRUCTIONS ---\n{skill_data.get('prompt', '')}")
            for action in skill_data.get("startup_actions", []):
                startup_result = await self.shell.execute(action)
                startup_key = _parse_action_key(action)
                self._record_audit(action, startup_key, startup_result.success,
                                   startup_result.elapsed_ms, startup_result)
                if startup_result.success:
                    parts.append(
                        f"\n[Startup: {action}]\n"
                        f"{json.dumps(startup_result.data, default=str, ensure_ascii=False)[:3000]}")
            payload = {"success": True, "data": "\n".join(parts)}
            return AgentToolResult(
                tool_call_id=call_id, name=_TOOL_NAME, ok=True,
                content=json.dumps(payload, default=str, ensure_ascii=False),
                data=payload)

        result_dict = result.to_dict()
        return AgentToolResult(
            tool_call_id=call_id, name=_TOOL_NAME, ok=result.success,
            content=json.dumps(result_dict, default=str, ensure_ascii=False),
            data=result_dict if isinstance(result_dict, dict) else None,
            error=result.error if not result.success else None)

    def _record_audit(self, command: str, action_key: Optional[str],
                      success: bool, elapsed_ms: float, result: Any,
                      queued: bool = False) -> None:
        from datetime import datetime
        intent = _TOOL_LABELS.get(action_key or "", command[:50])
        if "--bypass" in command:
            intent += " (pipeline debug)"
        if queued:
            intent += " [awaiting confirmation]"
        self.tool_audit.append({
            "ts": datetime.utcnow().isoformat() + "Z",
            "command": command,
            "action_key": action_key or "",
            "intent": intent,
            "success": success,
            "elapsed_ms": round(elapsed_ms, 1),
            "artifacts": _extract_artifacts(command, result),
            "summary": _summarize_result(action_key or "", result),
        })
