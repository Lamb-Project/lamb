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
import anyio
from contextlib import aclosing
import time
import uuid
from dataclasses import dataclass, field
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from lamb.aac.authorization import ActionAuthorizer, DEFAULT_POLICY, classify_user_confirmation
from lamb.aac.liteshell.shell import LiteShell, CommandContext, ShellResult, prepare_command
from lamb.aac.context_metrics import ContextSizeError, is_context_rejection, request_sizes, usage_counts
from lamb.aac.session_logger import SessionLogger
from lamb.aac.skill_routing import SkillRouting, catalogue_prompt
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")

from lamb.aac.pack_loader import load_pack
DEFAULT_SYSTEM_PROMPT = load_pack(version='1.0.0').text('persona.md')

# Bounded process-local capability cache, keyed by endpoint and model, never token.
_STREAM_USAGE_UNSUPPORTED = OrderedDict()

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
    "test.cases": "Loading test cases",
    "test.case-detail": "Reading test case",
    "test.delete-case": "Deleting test case",
    "test.scenarios": "Loading test cases",
    "test.add": "Creating test case",
    "test.update": "Updating test case",
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
        elif action_key in {"test.scenarios", "test.cases"}:
            return f"{len(d)} test cases" if isinstance(d, list) else ""
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

    if tokens[:3] in (['moodle', 'chart', 'submissions'], ['moodle','analytics','run']) and getattr(result, 'success', False):
        return [{'type': 'chart', 'id': result.data['chart_id'], 'title': result.data['title']}]
    if tokens[0] == 'moodle':
        from lamb.moodle.audit import command_artifacts
        return command_artifacts(cmd, result)

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
    approval_owner: str | None = None
    approval_preferences: dict = field(default_factory=dict)
    approval_decision: str | None = None
    interactive_approvals: bool = False
    tool_audit: list[dict] = field(default_factory=list)
    skill_state: dict | None = None
    pack: Any = None
    session_id: str = ""  # current AAC session ID (for self-referencing commands like session.rename)

    _turn_id: str = field(default="", init=False)
    _tool_rounds: int = field(default=0, init=False)

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

        if self.skill_state is not None:
            self.skill_state['last_user_input'] = user_message
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
                async with aclosing(self._run_agent_loop_stream()) as events:
                    async for event in events:
                        yield event
                return

        if self.skill_state is not None:
            self.skill_state['last_user_input'] = user_message
        if self.session_logger:
            self.session_logger.log_user_message(user_message)
        self.conversation.append({"role": "user", "content": user_message})
        async with aclosing(self._run_agent_loop_stream()) as events:
            async for event in events:
                yield event

    async def _run_agent_loop_stream(self) -> AsyncIterator[dict | str]:
        async with aclosing(self._run_agent_events(streaming=True)) as events:
            async for event in events:
                yield event

    async def _request_message(self, messages: list[dict], tools_enabled: bool,
                               streaming: bool) -> AsyncIterator[dict | str]:
        """One provider request, with the same message result for both consumers."""
        self.record_request_prefix(messages, TOOL_DEFINITIONS if tools_enabled else None)
        kwargs = {"model": self.model, "messages": messages}
        if tools_enabled:
            kwargs.update(tools=TOOL_DEFINITIONS, tool_choice="auto")
        # GPT-5.6 defaults to medium reasoning, which rejects function tools
        # on Chat Completions. Scope this compatibility option to that provider
        # and model family; Ollama and older OpenAI models keep their contract.
        driver = getattr(self.llm_client, '_lamb_aac_driver', {})
        if (tools_enabled and isinstance(driver, dict) and driver.get('provider') == 'openai'
                and (self.model == 'gpt-5.6' or self.model.startswith('gpt-5.6-'))):
            kwargs['reasoning_effort'] = 'none'
        if streaming:
            kwargs['stream'] = True
            endpoint = getattr(self.llm_client, 'base_url', None)
            driver_key = (str(endpoint), self.model) if endpoint is not None else None
            if not getattr(self.llm_client, '_lamb_no_stream_usage', False) and driver_key not in _STREAM_USAGE_UNSUPPORTED:
                kwargs['stream_options'] = {"include_usage": True}
        request_id = str(uuid.uuid4())
        observation = {'usage': None, 'request_id': request_id}
        started = time.monotonic()
        outcome = 'interrupted'
        slog = self.session_logger
        if slog and slog.enabled:
            slog.log('context_request', {**request_sizes(kwargs, [{}] + self.conversation), 'request_id': request_id,
                'turn_id': self._turn_id, 'model': self.model, 'streaming': streaming,
                'tool_round': self._tool_rounds, 'tools_enabled': tools_enabled})
        try:
            async with aclosing(self._provider_message(kwargs, tools_enabled, streaming, observation)) as events:
                async for event in events:
                    yield event
            outcome = 'completed'
        except Exception as error:
            outcome = 'context_rejected' if is_context_rejection(error) else 'error'
            if outcome == 'context_rejected':
                raise ContextSizeError(self.skill_state) from error
            raise
        finally:
            if slog:
                slog.log('context_response', {'request_id': observation['request_id'], 'turn_id': self._turn_id,
                    'elapsed_ms': round((time.monotonic()-started)*1000, 1),
                    'outcome': outcome, 'usage': observation['usage']})

    async def _provider_message(self, kwargs, tools_enabled, streaming, observation):
        if not streaming:
            response = await self.llm_client.chat.completions.create(**kwargs)
            observation['usage'] = usage_counts(getattr(response, 'usage', None))
            message = response.choices[0].message
            yield {"_message": {
                "role": "assistant", "content": message.content or "",
                "tool_calls": [{"id": tc.id, "type": "function", "function": {
                    "name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in (message.tool_calls or [])],
            }}
            return

        try:
            stream = await self.llm_client.chat.completions.create(**kwargs)
        except Exception as error:
            from lamb.aac.context_metrics import unsupported_stream_usage
            if 'stream_options' not in kwargs or not unsupported_stream_usage(error):
                raise
            self.llm_client._lamb_no_stream_usage = True
            endpoint = getattr(self.llm_client, 'base_url', None)
            if endpoint is not None:
                _STREAM_USAGE_UNSUPPORTED[(str(endpoint), self.model)] = True
                while len(_STREAM_USAGE_UNSUPPORTED) > 128:
                    _STREAM_USAGE_UNSUPPORTED.popitem(last=False)
            if self.session_logger:
                self.session_logger.log('context_response', {'request_id': observation['request_id'],
                    'turn_id': self._turn_id, 'outcome': 'unsupported_stream_options', 'usage': None})
            observation['request_id'] = str(uuid.uuid4())
            kwargs = {k: v for k, v in kwargs.items() if k != 'stream_options'}
            if self.session_logger and self.session_logger.enabled:
                self.session_logger.log('context_request', {**request_sizes(kwargs, [{}] + self.conversation),
                    'request_id': observation['request_id'], 'turn_id': self._turn_id, 'model': self.model,
                    'streaming': streaming, 'tool_round': self._tool_rounds, 'tools_enabled': tools_enabled})
            stream = await self.llm_client.chat.completions.create(**kwargs)
        text = ""
        calls = {}
        try:
            async for chunk in stream:
                usage = usage_counts(getattr(chunk, "usage", None))
                if usage is not None:
                    observation["usage"] = usage
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    text += delta.content
                    # A tool-bearing message can claim success before its command
                    # is even authorized. Hold prose until we know whether this
                    # message is an answer or a tool proposal.
                    if not tools_enabled:
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
            with anyio.CancelScope(shield=True):
                await stream.close()
        yield {"_message": {"role": "assistant", "content": text,
                             "tool_calls": list(calls.values())}}

    async def _run_agent_events(self, streaming: bool) -> AsyncIterator[dict | str]:
        """Preserve interrupted output and keep tool-call history resumable."""
        from lamb.aac.language import append_turn_language
        self._turn_id = str(uuid.uuid4())
        self._tool_rounds = 0
        self.announce_linked_context()
        append_turn_language(self)
        partial = ''
        completed = False
        outcome = 'interrupted'
        start = len(self.conversation)
        events = self._generate_agent_events(streaming)
        try:
            async for event in events:
                if isinstance(event, str):
                    partial += event
                elif event.get('status') in ('thinking', 'tool', 'tool_done'):
                    partial = ''
                yield event
            completed = True
            outcome = 'completed'
        except Exception:
            outcome = 'error'
            raise
        finally:
            if self.session_logger:
                self.session_logger.log('context_turn', {'turn_id': self._turn_id, 'outcome': outcome,
                    'tool_rounds': self._tool_rounds, 'round_limit': self.max_tool_rounds,
                    'round_limit_reached': self._tool_rounds >= self.max_tool_rounds})
            try:
                with anyio.CancelScope(shield=True):
                    await events.aclose()
            finally:
                if not completed:
                    messages = self.conversation[start:]
                    answered = {m.get('tool_call_id') for m in messages if m.get('role') == 'tool'}
                    for message in messages:
                        for call in message.get('tool_calls', []):
                            if call['id'] not in answered:
                                self.conversation.append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps({
                                    'success': False, 'interrupted': True,
                                    'error': 'Turn interrupted. Execution outcome may be unknown. Read back state before retrying a write.'})})
                                answered.add(call['id'])
                    last = self.conversation[-1] if self.conversation else {}
                    if partial and not (last.get('role') == 'assistant' and last.get('content') == partial):
                        self.conversation.append({'role': 'assistant', 'content': partial})

    async def _generate_agent_events(self, streaming: bool) -> AsyncIterator[dict | str]:
        """Shared legacy turn control; transport does not change tool semantics."""
        tool_rounds = 0
        analytics_evidence = None
        analytics_repair = None
        while True:
            if self.pending_action:
                from lamb.aac.approvals import explain_pending_action
                yield {"status": "thinking"}
                await explain_pending_action(self)
                from lamb.aac.language import confirmation_fallback, translation_confirmation, documentation_fallback_notice
                text = confirmation_fallback(self) + documentation_fallback_notice(self) + translation_confirmation(self)
                self.conversation.append({"role": "assistant", "content": text})
                if self.session_logger:
                    self.session_logger.log_agent_response(text)
                yield text
                from lamb.aac.approval_controls import card
                yield {"status": "approval", "approval": card(self.pending_action, self.skill_state)}
                return
            yield {"status": "thinking"}
            tools_enabled = tool_rounds < self.max_tool_rounds and not self.pending_action and analytics_repair is None
            from lamb.aac.result_store import provider_messages
            conversation = provider_messages(self.conversation)
            if self.pack and self.skill_state.get('brief'):
                from lamb.aac.glossary import model_messages
                conversation = model_messages(conversation, self.skill_state['brief']['glossary'])
            messages = [{"role": "system", "content": self.system_prompt}] + conversation
            if analytics_repair:
                messages += analytics_repair
            message = None
            # Guarded prose must not reach either SSE or saved history before
            # validation, including when the ordinary tool budget is exhausted.
            async with aclosing(self._request_message(messages, tools_enabled, streaming and analytics_evidence is None)) as events:
                async for event in events:
                    if isinstance(event, dict) and "_message" in event:
                        message = event["_message"]
                    else:
                        yield event
            if message is None:
                raise ValueError("Provider returned no assistant message")
            calls = message.pop("tool_calls", [])
            if calls and tools_enabled:
                tool_rounds += 1
                self._tool_rounds = tool_rounds
                # Retain calls/results for the provider, without retaining an
                # unverified tool preamble as if it were a completed action.
                self.conversation.append({**message, "content": "", "tool_calls": calls})
                waiting = False
                for call in calls:
                    tc = SimpleNamespace(id=call["id"], function=SimpleNamespace(**call["function"]))
                    command = _describe_tool_call(tc)
                    yield {"status": "tool", "command": command}
                    if waiting:
                        result = {"success": False, "error": "Not executed: confirmation or a newly loaded workflow requires a new decision."}
                    else:
                        result = await self._execute_tool(tc)
                    from lamb.aac.analytics_response import contract
                    new_contract = contract(result)
                    if new_contract:
                        new_contract['publication_unknown'] = (new_contract['publication_unknown'] or
                            bool(analytics_evidence and analytics_evidence['publication_unknown']))
                        analytics_evidence = new_contract
                    waiting = waiting or bool(result.get("awaiting_user_confirmation") or result.get("skill_loaded"))
                    try:
                        model_command = json.loads(tc.function.arguments).get('command', '')
                        if not isinstance(model_command, str): model_command = ''
                    except (ValueError, AttributeError, TypeError):
                        model_command = ''
                    self.conversation.append(self._result_message(result, model_command, role="tool", tool_call_id=tc.id))
                    yield {"status": "tool_done", "command": command, "success": result.get("success", False),
                           "awaiting_user_confirmation": bool(result.get("awaiting_user_confirmation"))}
                if tool_rounds >= self.max_tool_rounds:
                    self.conversation.append({"role": "user", "content":
                        "[System: Maximum tool rounds reached. Respond using the results already available. No further tools are allowed this turn.]"})
                continue

            # A provider that ignores the no-tools request must not execute more work.
            text = message["content"]
            if analytics_evidence and not calls:
                from lamb.aac.analytics_response import violations, repair_instruction, failure_notice
                errors = violations(text, analytics_evidence)
                if errors:
                    if self.session_logger:
                        self.session_logger.log('analytics_response_rejected', {'reasons':errors, 'repair':analytics_repair is not None})
                    if analytics_repair is None:
                        analytics_repair = [{'role':'assistant','content':text},
                                            {'role':'system','content':repair_instruction(errors)}]
                        continue
                    text = failure_notice((self.skill_state or {}).get('ui_language','en'))
            if calls:
                if self.pending_action:
                    from lamb.aac.language import confirmation_fallback
                    text = confirmation_fallback(self)
                else:
                    text = "This turn reached its tool limit. No additional action was executed. Ask me to continue from the saved results."
                yield text
            elif not streaming or tools_enabled or analytics_evidence:
                yield text
            from lamb.aac.language import translation_confirmation, documentation_fallback_notice
            interpretation_notice = documentation_fallback_notice(self) + translation_confirmation(self)
            if interpretation_notice:
                yield interpretation_notice
                text += interpretation_notice
            self.conversation.append({"role": "assistant", "content": text})
            if self.session_logger:
                self.session_logger.log_agent_response(text)
            return

    def _result_message(self, payload, command, *, role, tool_call_id=None, prefix='', suffix=''):
        from lamb.aac.result_store import encode
        message = {'role':role, 'content':prefix + json.dumps(payload, default=str, ensure_ascii=False).encode('utf-8', errors='backslashreplace').decode() + suffix}
        try: result_key = prepare_command(command)[0]
        except (ValueError, TypeError): result_key = 'unknown'
        message['_aac_result_command'] = result_key
        message['_aac_result_kind'] = ('workflow' if payload.get('skill_loaded') or payload.get('code') == 'workflow_required' else 'command')
        if tool_call_id is not None:
            message['tool_call_id'] = tool_call_id
        projector = getattr(self.shell, 'model_result', None)
        if callable(projector):
            from lamb.aac.result_store import encode
            projected = projector(command, payload)
            message['_aac_model_content'] = prefix + encode(projected).decode() + suffix
            if projected.get('context_result') and self.session_logger:
                try: key = prepare_command(command)[0]
                except (ValueError, TypeError): key = 'unknown'
                self.session_logger.log('context_result', {'command':key,
                    'original_bytes':projected['context_result']['original_bytes'],
                    'model_bytes':len(encode(projected)), 'stored':projected['context_result']['stored']})
        return message

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
        allowed = getattr(self.shell, 'allowed_commands', None)
        if allowed is not None and action_key not in allowed:
            return {'success':False, 'error':'This command is outside your role; ask the appropriate administrator'}
        policy = "auto" if help_requested else self.authorizer.check(action_key)
        interpretations = (self.skill_state or {}).get('translation_interpretations', [])
        # Even otherwise automatic resource writes require a reviewed interpretation.
        translated_writes = {key for key, value in DEFAULT_POLICY.items() if value == 'ask'} | {
            'test.add', 'test.run', 'test.evaluate', 'assistant.chat', 'session.rename'}
        if interpretations and policy == 'auto' and not help_requested and action_key in translated_writes:
            policy = 'ask'

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
            review = None
            if action_key == 'moodle.folder.finish':
                import shlex
                current = await self.shell.execute('moodle folder status ' + shlex.quote(parsed_kwargs['batch_id']))
                if not current.success or current.data.get('status') == 'completed':
                    # A completed batch has no remaining write to authorize.
                    self._record_audit(command, action_key, current.success, current.elapsed_ms, current)
                    return dict(current.to_dict(), action_executed=False)
            if action_key == "moodle.assign.grade":
                import asyncio
                try:
                    review = await asyncio.to_thread(self.shell.moodle.prepare_grade, parsed_kwargs)
                except Exception as exc:
                    return {"success": False, "error": str(exc)}
            from lamb.moodle.document_contract import IMPORT_KEYS
            if action_key.removeprefix('moodle.') in IMPORT_KEYS and action_key.startswith('moodle.'):
                import asyncio
                try:
                    review = await asyncio.to_thread(self.shell.moodle.prepare_import, action_key.removeprefix('moodle.'), parsed_kwargs)
                except Exception as exc:
                    return {'success': False, 'error': str(exc)}
            # Queue the command, don't execute
            import uuid
            self.pending_action = {
                "nonce": str(uuid.uuid4()),
                "command": command,
                "action_key": action_key,
                "machine_translation_interpretations": [dict(item) for item in interpretations],
                "tool_call_id": tool_call.id,
            }
            if review is not None:
                self.pending_action['moodle_review'] = review
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
                "machine_translation_interpretations": interpretations,
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
        try:
            result = await self.shell.execute(command)
        except BaseException:
            self._record_interrupted(command, action_key)
            raise
        self._record_audit(command, action_key, result.success, result.elapsed_ms, result)
        if self.session_logger:
            self.session_logger.log_tool_call(
                command=command,
                success=result.success,
                elapsed_ms=result.elapsed_ms,
                data=result.data,
                error=result.error,
            )

        # Special handling for skill.load — return the skill prompt to legacy direct callers
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
        classification = self.approval_decision or classify_user_confirmation(user_message)
        self.approval_decision = None
        if classification in {'reject', 'edit'} and action.get('moodle_review') and getattr(self.shell, 'moodle', None):
            from lamb.moodle.imports import discard_preparation
            try:
                await anyio.to_thread.run_sync(discard_preparation, self.shell.moodle, action['moodle_review'])
            except (OSError, ValueError, PermissionError, KeyError, TypeError):
                # Refusing an action must succeed even when its store is busy.
                # Unused preparations still expire; attempted work stays pinned.
                logger.warning('Unused Moodle preparation retained for scheduled cleanup')
        if classification == 'edit':
            self.pending_action = None
            self.conversation.append({'role': 'user', 'content':
                '[System: The user is revising the proposal. Nothing was executed. Prepare a new action with their changes; do not ask for a preliminary approval.]'})
            return None

        if classification == "approve":
            # Execute the queued command
            self.pending_action = None
            try:
                if action.get("action_key") == "moodle.assign.grade" or action.get("moodle_review") is not None:
                    result = await self.shell.execute(action["command"], confirmed=True, review=action.get('moodle_review'))
                elif (action.get("action_key") or "").startswith("moodle."):
                    result = await self.shell.execute(action["command"], confirmed=True)
                else:
                    result = await self.shell.execute(action["command"])
            except BaseException:
                self._record_interrupted(action["command"], action.get("action_key"))
                self.conversation.append({"role": "user", "content": user_message})
                self.conversation.append({"role": "user", "content":
                    "[System: Approved action interrupted. Outcome may be unknown. Read back state before retrying: " + action['command'] + "]"})
                raise
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
            self.conversation.append(self._result_message(result.to_dict(), action['command'], role='user',
                prefix='[System: User approved. Action executed. Result: ', suffix=']'))
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

    def _record_interrupted(self, command, action_key):
        result = ShellResult(False, error='Interrupted; outcome unknown. Read back state before retrying.', command=command)
        self._record_audit(command, action_key, False, 0, result)
        self.tool_audit[-1]['outcome'] = 'unknown'
        self.tool_audit[-1]['phase'] = 'interrupted'
        self.tool_audit[-1]['interrupted'] = True

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
            "phase": "awaiting_confirmation" if queued else "completed" if success else "failed",
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
