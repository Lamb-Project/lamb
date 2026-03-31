"""AAC session file logger.

Writes a structured JSON-lines log file per session for post-hoc analysis.
Each line is a timestamped event: user messages, agent responses, tool calls,
tool results, errors, and session lifecycle events.

Log path: {AAC_LOG_PATH}/{user_id}/{session_id}_{datetime}_{user_email}.jsonl

Enable/disable via AAC_SESSION_LOGGING=true|false (default: true).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")

# Default log directory relative to LAMB_DB_PATH (or cwd)
_DEFAULT_LOG_DIR = os.path.join(os.getenv("LAMB_DB_PATH", "."), "aac_logs")


def _is_enabled() -> bool:
    return os.getenv("AAC_SESSION_LOGGING", "true").lower() in ("true", "1", "yes")


def _get_log_dir() -> Path:
    return Path(os.getenv("AAC_LOG_PATH", _DEFAULT_LOG_DIR))


def _sanitize(s: str) -> str:
    """Sanitize a string for use in file/directory names."""
    return re.sub(r"[^\w\-.]", "_", s)


class SessionLogger:
    """Append-only JSONL logger for a single AAC session.

    Usage:
        slog = SessionLogger(session_id, user_email, user_id)
        slog.log("session_start", {"assistant_id": 4})
        slog.log("user_message", {"content": "Build a tutor"})
        slog.log("tool_call", {"command": "lamb assistant list", ...})
        slog.log("agent_response", {"content": "Here are your assistants..."})
    """

    def __init__(self, session_id: str, user_email: str, user_id: int | str):
        self.enabled = _is_enabled()
        self.session_id = session_id
        self.user_email = user_email
        self.user_id = str(user_id)
        self._file_path: Path | None = None

        if self.enabled:
            self._file_path = self._create_log_file()

    def _create_log_file(self) -> Path | None:
        try:
            log_dir = _get_log_dir() / _sanitize(self.user_id)
            log_dir.mkdir(parents=True, exist_ok=True)

            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            short_sid = self.session_id[:8]
            safe_email = _sanitize(self.user_email)
            filename = f"{short_sid}_{ts}_{safe_email}.jsonl"
            path = log_dir / filename
            return path
        except Exception as e:
            logger.error(f"Failed to create AAC session log: {e}")
            return None

    def log(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Append a log entry."""
        if not self.enabled or not self._file_path:
            return
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "session_id": self.session_id,
            "event": event_type,
        }
        if data:
            entry["data"] = data
        try:
            with open(self._file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write AAC session log: {e}")

    def log_user_message(self, content: str) -> None:
        self.log("user_message", {"content": content})

    def log_agent_response(self, content: str) -> None:
        self.log("agent_response", {"content": content})

    def log_tool_call(self, command: str, success: bool, elapsed_ms: float, data: Any = None, error: str | None = None) -> None:
        entry: dict[str, Any] = {
            "command": command,
            "success": success,
            "elapsed_ms": round(elapsed_ms, 1),
        }
        if error:
            entry["error"] = error
        if data is not None and success:
            # Truncate large data to keep logs manageable
            data_str = json.dumps(data, default=str, ensure_ascii=False)
            if len(data_str) > 5000:
                entry["data_truncated"] = True
                entry["data_size"] = len(data_str)
            else:
                entry["data"] = data
        self.log("tool_call", entry)

    def log_session_start(self, assistant_id: int | None = None, model: str = "") -> None:
        self.log("session_start", {
            "assistant_id": assistant_id,
            "model": model,
            "user_email": self.user_email,
        })

    def log_session_end(self, stats: dict | None = None) -> None:
        self.log("session_end", stats or {})

    def log_error(self, error: str, context: str = "") -> None:
        self.log("error", {"error": error, "context": context})

    @property
    def log_path(self) -> str | None:
        return str(self._file_path) if self._file_path else None
