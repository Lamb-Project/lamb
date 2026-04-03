"""AAC action authorization.

Determines whether a liteshell command should execute immediately (auto),
require user confirmation (ask), or be blocked (never).

Confirmation is handled at the Python level, not by the LLM. When a command
needs confirmation, the agent loop returns a description and the next user
message is classified as approval/rejection before the action executes.
"""

from __future__ import annotations

import os
import re
from typing import Any

from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")

# Default policy: which commands need confirmation
DEFAULT_POLICY: dict[str, str] = {
    # Reads — always auto
    "assistant.list": "auto",
    "assistant.list-shared": "auto",
    "assistant.get": "auto",
    "assistant.config": "auto",
    "rubric.list": "auto",
    "rubric.list-public": "auto",
    "rubric.get": "auto",
    "rubric.export": "auto",
    "kb.list": "auto",
    "kb.get": "auto",
    "template.list": "auto",
    "template.get": "auto",
    "model.list": "auto",
    "help": "auto",
    # Documentation commands — auto (read-only)
    "docs.index": "auto",
    "docs.read": "auto",
    # Test commands — auto (low risk, user explicitly requests tests)
    "test.scenarios": "auto",
    "test.add": "auto",
    "test.run": "auto",
    "test.runs": "auto",
    "test.run-detail": "auto",
    "test.evaluate": "auto",
    # Debug — auto (read-only, zero tokens for bypass)
    "assistant.debug": "auto",
    # Writes — ask by default
    "assistant.create": "ask",
    "assistant.update": "ask",
    "assistant.delete": "ask",
}

# Words/phrases that indicate approval across supported languages (en, es, ca, eu)
_APPROVAL_WORDS = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "proceed", "confirm",
    "confirmed", "approve", "approved", "absolutely", "affirmative", "right",
    "go", "do",
    "sí", "si", "vale", "claro", "confirmo", "confirmado",
    "endavant", "confirma", "confirmat",
    "bai", "konfirmatu",
}

_APPROVAL_PHRASES = {
    "go ahead", "do it", "go for it", "sounds good", "that works",
    "yes please", "yes do it", "ok go ahead", "yeah sure",
    "por supuesto", "de acuerdo", "hazlo", "adelante", "dale",
    "sí que sí", "está bien", "me parece bien",
    "fes-ho", "d'acord", "tira endavant", "molt bé",
    "aurrera", "egin", "ados",
}

_REJECTION_WORDS = {
    "no", "nope", "nah", "cancel", "stop", "abort", "reject", "rejected",
    "don't", "dont", "negative", "wait",
    "cancela", "para", "detente",
    "cancel·la", "atura",
    "ez", "utzi", "gelditu",
}

_REJECTION_PHRASES = {
    "no thanks", "not now", "hold on", "never mind", "forget it",
    "no gracias", "ahora no", "déjalo", "olvídalo",
    "no gràcies", "ara no", "deixa-ho",
}


class ActionAuthorizer:
    """Check authorization policy for liteshell commands."""

    def __init__(self, policy: dict[str, str] | None = None):
        self.policy = policy or DEFAULT_POLICY.copy()

    def check(self, action_key: str) -> str:
        """Return 'auto', 'ask', or 'never' for the given action.

        Unknown actions default to 'ask' (safe default).
        """
        return self.policy.get(action_key, "ask")

    def resolve_action_key(self, command_str: str) -> str | None:
        """Extract the action key (e.g., 'assistant.create') from a command string."""
        tokens = command_str.strip().split()
        if tokens and tokens[0] == "lamb":
            tokens = tokens[1:]
        if not tokens:
            return None
        if len(tokens) >= 2 and not tokens[1].startswith("-"):
            return f"{tokens[0]}.{tokens[1]}"
        return tokens[0]


def classify_user_confirmation(message: str) -> str:
    """Classify a user message as 'approve', 'reject', or 'other'.

    Strategy: normalize the message, then check against known approval/rejection
    words and phrases. Short messages (< 8 words) that contain approval/rejection
    signals are classified. Longer messages are treated as 'other' since the user
    is probably saying something more nuanced.
    """
    text = message.strip().rstrip("!.,;:").lower()
    words = text.split()

    # Empty
    if not words:
        return "other"

    # Long messages are probably not simple yes/no
    if len(words) > 8:
        return "other"

    # Check exact phrase match first
    if text in _APPROVAL_PHRASES:
        return "approve"
    if text in _REJECTION_PHRASES:
        return "reject"

    # Check if first word is a strong signal
    first = words[0]
    if first in _APPROVAL_WORDS:
        return "approve"
    if first in _REJECTION_WORDS:
        return "reject"

    # Check if any word is a strong approval/rejection signal (for short messages)
    if len(words) <= 4:
        for w in words:
            if w in _APPROVAL_WORDS:
                return "approve"
        for w in words:
            if w in _REJECTION_WORDS:
                return "reject"

    return "other"
