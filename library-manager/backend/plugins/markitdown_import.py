"""MarkItDown import plugin for office and document formats.

Uses the ``markitdown`` library to convert PDF, DOCX, PPTX, XLSX, and
other formats into Markdown. No image extraction or LLM features — for
those, use ``markitdown_plus_import``. Page boundaries that MarkItDown
emits in its output (form-feeds for PDFs, etc.) are preserved into
``content/pages/`` so that downstream consumers like the KB Server's
``by_page`` chunking strategy can use them.
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
from plugins.content_handlers.capability import Capability
from plugins.markitdown_plus_import import _PAGE_AWARE_TYPES, _split_into_pages

logger = logging.getLogger(__name__)


@PluginRegistry.register
class MarkItDownImportPlugin(LibraryImportPlugin):
    """Convert document files to Markdown via MarkItDown."""

    name = "markitdown_import"
    description = "Convert documents (PDF, DOCX, PPTX, XLSX, etc.) to Markdown using MarkItDown."
    supported_source_types = {"file"}
    required_keys: list[str] = []
    # Emits full markdown plus per-page splits for paginated formats.
    produces_capabilities = [Capability.TEXT, Capability.PAGES]
    file_extensions = [
        "pdf",
        "pptx",
        "docx",
        "xlsx",
        "xls",
        "mp3",
        "wav",
        "html",
        "csv",
        "json",
        "xml",
        "zip",
        "epub",
        "txt",
        "md",
    ]
    human_label = "Document import (Markitdown converter)"

    def import_content(
        self,
        source_path: str,
        *,
        api_keys: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> ImportResult:
        """Convert a document file to Markdown.

        Args:
            source_path: Path to the uploaded file.
            api_keys: Not used by this plugin.
            **kwargs: Optional ``description`` and ``citation`` strings.

        Returns:
            ImportResult with the converted Markdown as ``full_text``.

        Raises:
            FileNotFoundError: If the source file does not exist.
            RuntimeError: If MarkItDown conversion fails.
        """
        from markitdown import MarkItDown  # noqa: PLC0415

        path = Path(source_path)
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        self.report_progress(kwargs, 0, 3, "Converting to Markdown...")

        try:
            md = MarkItDown()
            result = md.convert(str(path))
            content = result.text_content
        except Exception as exc:
            # Translate to a short, user-facing message; full chain in the
            # worker log.
            from plugins._markitdown_errors import humanize_markitdown_error  # noqa: PLC0415

            logger.exception("MarkItDown conversion failed for %s", path.name)
            raise RuntimeError(humanize_markitdown_error(exc, path.name)) from exc

        if not content or not content.strip():
            logger.warning("MarkItDown produced empty content for %s", path.name)
            content = f"*(No extractable text found in {path.name})*"

        self.report_progress(kwargs, 1, 3, "Building metadata...")

        ext = path.suffix.lower().lstrip(".")
        pages = _split_into_pages(content, ext) if ext in _PAGE_AWARE_TYPES else []

        stat = path.stat()
        metadata = {
            "original_filename": path.name,
            "content_type": _guess_mime(path.suffix),
            "file_size": stat.st_size,
            "character_count": len(content),
            "page_count": len(pages),
            "import_plugin": self.name,
        }

        if kwargs.get("description"):
            metadata["description"] = kwargs["description"]
        if kwargs.get("citation"):
            metadata["citation"] = kwargs["citation"]

        source_ref = {
            "type": "file",
            "original_filename": path.name,
            "content_type": metadata["content_type"],
        }

        self.report_progress(kwargs, 2, 3, "Import complete.")

        return ImportResult(
            full_text=content,
            pages=pages,
            images=[],
            metadata=metadata,
            source_ref=source_ref,
        )

    def get_parameters(self) -> list[PluginParameter]:
        """Return configurable parameters.

        Returns:
            Parameter descriptors for optional description and citation.
        """
        return [
            PluginParameter(
                name="description",
                type="string",
                description="Optional description of the document.",
                advanced=True,
            ),
            PluginParameter(
                name="citation",
                type="string",
                description="Optional citation reference.",
                advanced=True,
            ),
        ]


def _guess_mime(ext: str) -> str:
    """Map a file extension to a plausible MIME type.

    Args:
        ext: File extension including the dot.

    Returns:
        MIME type string.
    """
    mapping = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".html": "text/html",
        ".csv": "text/csv",
        ".json": "application/json",
        ".xml": "application/xml",
        ".zip": "application/zip",
        ".epub": "application/epub+zip",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
    }
    return mapping.get(ext.lower(), "application/octet-stream")
