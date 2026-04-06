"""Simple import plugin for plain-text documents.

Handles ``.txt``, ``.md``, and ``.html`` files by reading them directly as
UTF-8 text. No conversion is needed — the content is already in a
text-friendly format.
"""

import logging
from pathlib import Path
from typing import Any

from plugins.base import (
    ImportResult,
    LibraryImportPlugin,
    PluginParameter,
    PluginRegistry,
)

logger = logging.getLogger(__name__)


@PluginRegistry.register
class SimpleImportPlugin(LibraryImportPlugin):
    """Import plain text, Markdown, and HTML files."""

    name = "simple_import"
    description = "Import plain text files (.txt, .md, .html) as-is."
    supported_source_types = {"file"}
    supported_file_types = {"txt", "md", "html"}
    required_keys: list[str] = []

    def import_content(
        self,
        source_path: str,
        *,
        api_keys: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> ImportResult:
        """Read a text file and return its contents as markdown.

        Args:
            source_path: Path to the uploaded file.
            api_keys: Not used by this plugin.
            **kwargs: Ignored.

        Returns:
            ImportResult with the file content as ``full_text``.

        Raises:
            FileNotFoundError: If the source file does not exist.
            ValueError: If the file cannot be decoded as UTF-8.
        """
        path = Path(source_path)
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        self.report_progress(kwargs, 0, 2, "Reading file...")

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"File is not valid UTF-8: {path.name}"
            ) from exc

        self.report_progress(kwargs, 1, 2, "Building metadata...")

        metadata = {
            "original_filename": path.name,
            "content_type": _mime_for_extension(path.suffix),
            "file_size": path.stat().st_size,
            "character_count": len(content),
        }

        source_ref = {
            "type": "file",
            "original_filename": path.name,
            "content_type": metadata["content_type"],
        }

        self.report_progress(kwargs, 2, 2, "Import complete.")

        return ImportResult(
            full_text=content,
            pages=[],
            images=[],
            metadata=metadata,
            source_ref=source_ref,
        )

    def get_parameters(self) -> list[PluginParameter]:
        """This plugin has no configurable parameters.

        Returns:
            An empty list.
        """
        return []


def _mime_for_extension(ext: str) -> str:
    """Map a file extension to its MIME type.

    Args:
        ext: File extension including the dot (e.g. ``".md"``).

    Returns:
        The corresponding MIME type string.
    """
    mapping = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".html": "text/html",
    }
    return mapping.get(ext.lower(), "text/plain")
