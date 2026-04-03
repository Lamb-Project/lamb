"""Liteshell: parse CLI command strings and route to service functions.

The LLM sends commands like "lamb assistant get 4" and gets back
structured Python data. No real shell — just argument parsing and dispatch
to LAMB Creator Interface HTTP endpoints via LambClient (from lamb-cli).

Local-only commands (docs.index, docs.read, help) read files directly.
"""

from __future__ import annotations

import shlex
import time
from dataclasses import dataclass, field
from typing import Any

from lamb.aac.liteshell.commands import COMMAND_REGISTRY
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")


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
    endpoints via LambClient, or to local handlers for docs/help commands.

    Attributes:
        server_url: Base URL of the LAMB backend (e.g., "http://localhost:9099").
        token: JWT auth token for the current user.
        user_email: Authenticated user's email (for convenience/logging).
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
        """Lazy-init the HTTP client."""
        if self._http_client is None:
            from lamb_cli.client import LambClient
            self._http_client = LambClient(
                server_url=self.server_url,
                token=self.token,
                timeout=60.0,
            )
        return self._http_client

    def close(self):
        """Close the HTTP client if open."""
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def execute(self, command_str: str) -> ShellResult:
        """Parse and execute a CLI-like command string.

        Args:
            command_str: e.g. "lamb assistant get 4"

        Returns:
            ShellResult with structured data or error.
        """
        start = time.monotonic()
        try:
            result = self._dispatch(command_str)
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

    def _dispatch(self, command_str: str) -> ShellResult:
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
        if self.allowlist and group not in self.allowlist:
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

        # Build context for the handler
        ctx = CommandContext(
            http=self._get_http(),
            server_url=self.server_url,
            token=self.token,
            user_email=self.user_email,
            organization_id=self.organization_id,
            user_id=self.user_id,
        )

        data = handler(ctx, args, kwargs)
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
    http: Any  # LambClient instance for HTTP commands
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
