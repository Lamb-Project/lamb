"""Text capability handler: reads ``content/full.md`` and returns it as Markdown."""

from __future__ import annotations

from pathlib import Path

from plugins.content_handlers.capability import (
    Capability,
    CapabilityPayload,
    CapabilityRegistry,
    ContentHandler,
    HandlerUnavailable,
)


@CapabilityRegistry.register
class TextHandler(ContentHandler):
    """Return the full Markdown text of a library item.

    Every successful import writes ``content/full.md`` so virtually all
    items expose this capability.
    """

    capability = Capability.TEXT
    description = "Full Markdown text of the imported item."

    def get(self, item_path: Path) -> CapabilityPayload:
        """Read ``content/full.md`` and return it as ``text/markdown``.

        Args:
            item_path: Path to the item directory.

        Returns:
            CapabilityPayload with the file contents as ``body``.

        Raises:
            HandlerUnavailable: If ``content/full.md`` is missing.
        """
        full_md = item_path / "content" / "full.md"
        if not full_md.is_file():
            raise HandlerUnavailable(
                f"Item at {item_path} has no content/full.md"
            )
        return CapabilityPayload(
            mime="text/markdown",
            body=full_md.read_text(encoding="utf-8"),
        )
