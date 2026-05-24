"""Capability enum, payload, base handler and registry.

This module is the **single source of truth** for capability identifiers
across the platform. Adding a new capability is a one-line edit to the
:class:`Capability` enum plus a new handler module in this package.

Design notes
------------
* ``Capability`` is a ``str`` enum so values serialise transparently to JSON
  and so equality checks against route path segments are trivial.
* ``CapabilityRegistry`` mirrors the pattern of :class:`PluginRegistry` in
  ``plugins/base.py`` — a class-level dict populated by a decorator at
  import time.
* ``HandlerUnavailable`` lets a handler signal "this item does not have my
  capability" without raising a generic exception that would mask real
  bugs. The HTTP layer maps it to a 404.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Controlled vocabulary
# ---------------------------------------------------------------------------


class Capability(str, Enum):
    """Controlled vocabulary of content capabilities.

    Add a new value here when introducing a new content type. Do NOT use
    free-form strings elsewhere — always reference this enum so the system
    cannot accumulate "image" vs "picture" vs "img" duplicates.
    """

    TEXT = "text"
    PAGES = "pages"
    IMAGES = "images"
    AUDIO = "audio"
    TRANSCRIPT = "transcript"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HandlerUnavailable(Exception):
    """Raised by a handler when the item does not expose its capability.

    Distinguishes "this item has no images" (expected, → HTTP 404) from
    "the handler crashed" (unexpected, → HTTP 500).
    """


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------


@dataclass
class CapabilityPayload:
    """Return type for ``ContentHandler.get``.

    Attributes:
        mime: MIME type describing how ``body`` should be interpreted.
            Examples: ``"text/markdown"``, ``"application/json"``.
        body: Capability-specific content. May be a string (for text), a
            list of dicts (for pages/images), bytes (for binary payloads),
            or any JSON-serialisable structure.
    """

    mime: str
    body: Any


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class ContentHandler(abc.ABC):
    """Abstract base for content capability handlers.

    Subclasses must set the class attributes :attr:`capability` and
    :attr:`description`, and implement :meth:`get`. Handlers are stateless;
    a fresh instance is created on every call.
    """

    capability: Capability
    description: str = ""

    @abc.abstractmethod
    def get(self, item_path: Path) -> CapabilityPayload:
        """Extract this handler's capability from a stored item.

        Args:
            item_path: Absolute path to the item directory containing
                ``metadata.json``, ``source_ref.json``, ``original/`` and
                ``content/`` subtrees.

        Returns:
            A :class:`CapabilityPayload` carrying the extracted content.

        Raises:
            HandlerUnavailable: When the item does not expose this
                capability (e.g. no images on disk).
        """


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class CapabilityRegistry:
    """Singleton registry for capability handlers.

    Handlers self-register at import time via the
    :meth:`register` class decorator. Discovery and import is performed by
    the main app at startup, so subpackage modules just need to use the
    decorator on their handler class.
    """

    _handlers: dict[Capability, type[ContentHandler]] = {}

    @classmethod
    def register(cls, handler_class: type[ContentHandler]) -> type[ContentHandler]:
        """Register a content handler class.

        Args:
            handler_class: The handler class to register. Must define
                :attr:`ContentHandler.capability` as a :class:`Capability`
                enum member.

        Returns:
            The unmodified handler class (decorator-friendly).

        Raises:
            ValueError: If ``handler_class.capability`` is missing or is
                not a :class:`Capability` enum member.
        """
        capability = getattr(handler_class, "capability", None)
        if not isinstance(capability, Capability):
            raise ValueError(
                f"Handler {handler_class.__name__} must set "
                "`capability: Capability` to a Capability enum member."
            )

        existing = cls._handlers.get(capability)
        if existing is not None and existing is not handler_class:
            logger.warning(
                "Capability %s already registered by %s — replacing with %s",
                capability.value,
                existing.__name__,
                handler_class.__name__,
            )

        cls._handlers[capability] = handler_class
        logger.debug(
            "Registered capability handler: %s → %s",
            capability.value,
            handler_class.__name__,
        )
        return handler_class

    @classmethod
    def get(cls, capability: Capability | str) -> ContentHandler | None:
        """Instantiate and return the handler for a given capability.

        Args:
            capability: Either a :class:`Capability` enum value or its
                string form (matches the enum value).

        Returns:
            A fresh handler instance, or ``None`` if no handler is
            registered for this capability.
        """
        if isinstance(capability, str) and not isinstance(capability, Capability):
            try:
                capability = Capability(capability)
            except ValueError:
                return None
        handler_class = cls._handlers.get(capability)
        if handler_class is None:
            return None
        return handler_class()

    @classmethod
    def list_handlers(cls) -> list[dict[str, str]]:
        """Return metadata for all registered handlers.

        Returns:
            A list of ``{"capability": str, "description": str}`` dicts,
            sorted by capability value for deterministic output.
        """
        rows = [
            {
                "capability": cap.value,
                "description": handler_class.description,
            }
            for cap, handler_class in cls._handlers.items()
        ]
        rows.sort(key=lambda r: r["capability"])
        return rows

    @classmethod
    def registered_capabilities(cls) -> list[Capability]:
        """Return the list of currently registered capability enum values."""
        return list(cls._handlers.keys())

    @classmethod
    def _reset(cls) -> None:
        """Test-only hook to clear the registry."""
        cls._handlers.clear()
