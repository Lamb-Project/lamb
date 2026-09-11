"""Liteshell: parse CLI command strings and route to HTTP endpoints or local handlers.

The LLM sends commands like "lamb assistant get 4" and gets back
structured Python data. HTTP commands call Creator Interface endpoints
via in-process ASGI transport (no TCP, no deadlock). Local commands
(docs, help) read files directly.
"""

from __future__ import annotations

import shlex
import time
from dataclasses import dataclass, field
from typing import Any

from lamb.aac.liteshell.commands import COMMAND_REGISTRY, LOCAL_COMMANDS
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")


# Explicit supported shell surface. Unsupported CLI options fail instead of being ignored.
# key: (minimum positional arguments, maximum, accepted option names)
COMMAND_CONTRACTS = {
    "assistant.list": (0, 0, ""), "assistant.list-shared": (0, 0, ""),
    "assistant.get": (1, 1, ""), "assistant.config": (0, 0, ""),
    "assistant.debug": (1, 1, "message m"),
    "assistant.create": (1, 1, "system_prompt s description d prompt_template rag_top_k rag_collections llm connector prompt_processor rag_processor rubric_id rubric_format"),
    "assistant.update": (1, 1, "name n system_prompt s description d prompt_template rag_top_k rag_collections llm connector prompt_processor rag_processor rubric_id rubric_format"),
    "assistant.delete": (1, 1, ""), "assistant.list-published": (0, 0, ""),
    "assistant.chat": (1, 1, "message m bypass b"),
    "rubric.list": (0, 0, ""), "rubric.list-public": (0, 0, ""),
    "rubric.get": (1, 1, ""), "rubric.export": (1, 1, "format f"),
    "kb.list": (0, 0, ""), "kb.get": (1, 1, ""),
    "template.list": (0, 0, ""), "template.get": (1, 1, ""),
    "test.scenarios": (1, 1, ""), "test.add": (1, 2, "title message m description type t expected e"),
    "test.run": (1, 1, "bypass b scenario s"), "test.runs": (1, 1, ""),
    "test.run-detail": (1, 2, "assistant a"), "test.evaluate": (2, 3, "assistant a notes n"),
    "session.rename": (1, 1, "session s"), "skill.list": (0, 0, ""),
    "skill.load": (1, 1, "assistant a language"), "docs.index": (0, 0, ""),
    "docs.read": (1, 1, "section"), "help": (0, 0, ""),
    "analytics.chats": (1, 1, "page per_page user_id search start_date end_date"),
    "analytics.chat-detail": (2, 2, ""), "analytics.stats": (1, 1, "start_date end_date"),
    "analytics.timeline": (1, 1, "period start_date end_date"),
}


def validate_command(key, args, kwargs):
    minimum, maximum, options = COMMAND_CONTRACTS[key]
    if not minimum <= len(args) <= maximum:
        raise ValueError(f"{key} expects {minimum}..{maximum} positional arguments")
    allowed = set(options.split()) | {"output", "o"}
    unknown = set(kwargs) - allowed
    if unknown:
        raise ValueError(f"Unsupported options for {key}: {', '.join(sorted(unknown))}")
    for option, value in kwargs.items():
        if option in {"bypass", "b"}:
            if value not in (True, "true", "false"):
                raise ValueError(f"Invalid boolean for {option}")
        elif value is True:
            raise ValueError(f"Missing value for {option}")
    if kwargs.get("output", kwargs.get("o", "json")) != "json":
        raise ValueError("The AAC shell returns structured JSON; use -o json")
    if key.startswith("analytics."):
        if int(args[0]) < 1:
            raise ValueError("assistant_id must be positive")
        args[0] = str(int(args[0]))
    if "s" in kwargs and key in {"assistant.create", "assistant.update"}:
        kwargs["system_prompt"] = kwargs.pop("s")
    if "rag_top_k" in kwargs and int(kwargs["rag_top_k"]) < 1:
        raise ValueError("rag_top_k must be positive")

@dataclass
class ShellResult:
    """Result of a liteshell command execution."""
    success: bool
    data: Any = None
    error: str | None = None
    command: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"success": self.success}
        if self.success:
            d["data"] = self.data
        else:
            d["error"] = self.error
        return d


@dataclass
class LiteShell:
    """CLI-shaped command executor for the AAC agent.

    Parses command strings and routes them to Creator Interface HTTP
    endpoints via ASGI transport, or to local handlers for docs/help.

    Attributes:
        server_url: Base URL (unused for ASGI transport, kept for logging).
        token: JWT auth token for the current user.
        user_email: Authenticated user's email.
        organization_id: User's organization ID.
        allowlist: If set, only these top-level command groups are allowed.
        history: Record of executed commands (for session logging).
    """
    server_url: str
    token: str
    user_email: str
    organization_id: int
    user_id: int = 0
    allowlist: set[str] | None = None
    history: list[ShellResult] = field(default_factory=list)
    _http_client: Any = field(default=None, repr=False)

    def _get_http(self):
        """Lazy-init the async ASGI HTTP client."""
        if self._http_client is None:
            from lamb.aac.liteshell.http_client import AsyncLambClient
            self._http_client = AsyncLambClient(token=self.token)
        return self._http_client

    async def close(self):
        """Close the HTTP client if open."""
        if self._http_client is not None:
            await self._http_client.close()
            self._http_client = None

    async def execute(self, command_str: str) -> ShellResult:
        """Parse and execute a CLI-like command string.

        Args:
            command_str: e.g. "lamb assistant get 4"

        Returns:
            ShellResult with structured data or error.
        """
        start = time.monotonic()
        try:
            result = await self._dispatch(command_str)
            result.command = command_str
            result.elapsed_ms = (time.monotonic() - start) * 1000
        except Exception as e:
            logger.error(f"Liteshell error for '{command_str}': {e}")
            result = ShellResult(
                success=False,
                error=str(e),
                command=command_str,
                elapsed_ms=(time.monotonic() - start) * 1000,
            )
        self.history.append(result)
        return result

    async def _dispatch(self, command_str: str) -> ShellResult:
        tokens = shlex.split(command_str.strip())
        if not tokens:
            return ShellResult(success=False, error="Empty command")

        # Strip leading "lamb" if present
        if tokens[0] == "lamb":
            tokens = tokens[1:]
        if not tokens:
            return ShellResult(success=False, error="No command after 'lamb'")

        group = tokens[0]

        # Check allowlist
        if self.allowlist is not None and group not in self.allowlist:
            return ShellResult(
                success=False,
                error=f"Command '{group}' not allowed. Available: {sorted(self.allowlist)}",
            )

        # Resolve command key: "assistant list" → "assistant.list"
        if len(tokens) > 1 and not tokens[1].startswith("-"):
            key = f"{group}.{tokens[1]}"
            arg_tokens = tokens[2:]
        else:
            key = group
            arg_tokens = tokens[1:]

        handler = COMMAND_REGISTRY.get(key)
        if not handler:
            handler = COMMAND_REGISTRY.get(group)
            if handler:
                arg_tokens = tokens[1:]
            else:
                available = [k for k in COMMAND_REGISTRY if k.startswith(f"{group}.")]
                if available:
                    return ShellResult(
                        success=False,
                        error=f"Unknown subcommand '{key}'. Available: {available}",
                    )
                return ShellResult(
                    success=False,
                    error=f"Unknown command '{group}'. Available groups: {sorted(set(k.split('.')[0] for k in COMMAND_REGISTRY))}",
                )

        args, kwargs = _parse_args(arg_tokens)
        if kwargs.pop("help", kwargs.pop("h", False)):
            return ShellResult(success=True, data={"command": key, "help": handler.__doc__ or "",
                "options": COMMAND_CONTRACTS[key][2].split()})
        validate_command(key, args, kwargs)

        # Build context for the handler
        ctx = CommandContext(
            http=None if key in LOCAL_COMMANDS else self._get_http(),
            server_url=self.server_url,
            token=self.token,
            user_email=self.user_email,
            organization_id=self.organization_id,
            user_id=self.user_id,
        )

        # Local commands are sync, HTTP commands are async
        if key in LOCAL_COMMANDS:
            data = handler(ctx, args, kwargs)
        else:
            data = await handler(ctx, args, kwargs)
        return ShellResult(success=True, data=data)

    def get_available_commands(self) -> dict[str, str]:
        """Return available commands and their descriptions."""
        result = {}
        for key, func in sorted(COMMAND_REGISTRY.items()):
            doc = func.__doc__ or ""
            result[f"lamb {key.replace('.', ' ')}"] = doc.split("\n")[0].strip()
        return result


@dataclass
class CommandContext:
    """Context passed to every command handler."""
    http: Any  # AsyncLambClient for HTTP commands
    server_url: str
    token: str
    user_email: str
    organization_id: int
    user_id: int = 0


def _parse_args(tokens: list[str]) -> tuple[list[str], dict[str, Any]]:
    """Parse CLI-style tokens into positional args and keyword kwargs."""
    args: list[str] = []
    kwargs: dict[str, Any] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            if "=" in token:
                key, value = token[2:].split("=", 1)
                kwargs[key.replace("-", "_")] = value
            elif i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                kwargs[token[2:].replace("-", "_")] = tokens[i + 1]
                i += 1
            else:
                kwargs[token[2:].replace("-", "_")] = True
        elif token.startswith("-") and len(token) == 2:
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                kwargs[token[1:]] = tokens[i + 1]
                i += 1
            else:
                kwargs[token[1:]] = True
        else:
            args.append(token)
        i += 1
    return args, kwargs
