"""Compatibility imports for #553; lifecycle now belongs to conversation_state."""
from .conversation_state import Conversation, migrate, resolve, prepare_assistant

__all__ = ["Conversation", "migrate", "resolve", "prepare_assistant"]
