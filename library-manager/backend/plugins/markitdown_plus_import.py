"""Enhanced MarkItDown import with image extraction and per-page breakdown.

This is the richest import plugin. It produces:
- Full markdown text
- Per-page breakdown (for PDF, DOCX, PPTX)
- Extracted images with optional LLM descriptions (via OpenAI Vision)

The plugin outputs the common format without chunking — chunking is the
KB Server's responsibility.
"""

import base64
import logging
import re
import time
from pathlib import Path
from typing import Any

from plugins.base import (
    ExtractedImage,
    ImportResult,
    LibraryImportPlugin,
    PageContent,
    PluginParameter,
    PluginRegistry,
)

logger = logging.getLogger(__name__)

_PAGE_AWARE_TYPES = {"pdf", "docx", "pptx"}


@PluginRegistry.register
class MarkItDownPlusPlugin(LibraryImportPlugin):
    """Enhanced document import with image extraction and page awareness."""

    name = "markitdown_plus_import"
    description = (
        "Convert documents to Markdown with image extraction and "
        "optional LLM-generated image descriptions."
    )
    supported_source_types = {"file"}
    supported_file_types = {
        "pdf", "pptx", "docx", "xlsx", "xls",
        "mp3", "wav", "html", "csv", "json",
        "xml", "zip", "epub",
    }
    required_keys = ["openai_vision"]

    def import_content(
        self,
        source_path: str,
        *,
        api_keys: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> ImportResult:
        """Convert a document to structured markdown with images and pages.

        Args:
            source_path: Path to the uploaded file.
            api_keys: May contain ``openai_vision`` key for LLM descriptions.
            **kwargs: Plugin parameters including ``image_descriptions``.

        Returns:
            ImportResult with full text, pages, images, and metadata.
        """
        from markitdown import MarkItDown  # noqa: PLC0415

        path = Path(source_path)
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        image_mode = kwargs.get("image_descriptions", "none")
        api_keys = api_keys or {}
        stats: dict[str, Any] = {
            "images_extracted": 0,
            "images_with_llm_descriptions": 0,
            "llm_calls": [],
            "stage_timings": [],
        }

        total_steps = 4
        self.report_progress(kwargs, 0, total_steps, "Converting to Markdown...")

        t0 = time.monotonic()
        try:
            md = MarkItDown()
            result = md.convert(str(path))
            content = result.text_content or ""
        except Exception as exc:
            raise RuntimeError(
                f"MarkItDown conversion failed for {path.name}: {exc}"
            ) from exc
        stats["stage_timings"].append({
            "stage": "markitdown_conversion",
            "duration_ms": int((time.monotonic() - t0) * 1000),
        })

        self.report_progress(kwargs, 1, total_steps, "Extracting images...")

        images: list[ExtractedImage] = []
        ext = path.suffix.lower().lstrip(".")
        if ext in _PAGE_AWARE_TYPES and image_mode != "none":
            t1 = time.monotonic()
            images = _extract_images(path, image_mode, api_keys, stats)
            stats["stage_timings"].append({
                "stage": "image_extraction",
                "duration_ms": int((time.monotonic() - t1) * 1000),
            })

        stats["images_extracted"] = len(images)

        self.report_progress(kwargs, 2, total_steps, "Splitting pages...")

        t2 = time.monotonic()
        pages = _split_into_pages(content, ext)
        stats["stage_timings"].append({
            "stage": "page_splitting",
            "duration_ms": int((time.monotonic() - t2) * 1000),
        })

        self.report_progress(kwargs, 3, total_steps, "Building metadata...")

        stat = path.stat()
        metadata = {
            "original_filename": path.name,
            "content_type": _guess_mime(path.suffix),
            "file_size": stat.st_size,
            "character_count": len(content),
            "page_count": len(pages),
            "image_count": len(images),
            "import_plugin": self.name,
            "image_descriptions_mode": image_mode,
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

        self.report_progress(kwargs, 4, total_steps, "Import complete.")

        return ImportResult(
            full_text=content,
            pages=pages,
            images=images,
            metadata=metadata,
            source_ref=source_ref,
        )

    def get_parameters(self) -> list[PluginParameter]:
        """Return configurable parameters for this plugin.

        Returns:
            Parameter descriptors.
        """
        return [
            PluginParameter(
                name="image_descriptions",
                type="enum",
                description=(
                    "How to handle images: 'none' = ignore, "
                    "'basic' = extract with filename descriptions, "
                    "'llm' = extract + generate descriptions via OpenAI Vision."
                ),
                default="none",
                choices=["none", "basic", "llm"],
            ),
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


# ---------------------------------------------------------------------------
# Image extraction helpers
# ---------------------------------------------------------------------------


def _extract_images(
    path: Path,
    mode: str,
    api_keys: dict[str, str],
    stats: dict[str, Any],
) -> list[ExtractedImage]:
    """Extract images from a document using PyMuPDF.

    Args:
        path: Path to the document file.
        mode: ``"basic"`` or ``"llm"``.
        api_keys: May contain ``openai_vision`` for LLM descriptions.
        stats: Mutable dict to record processing statistics.

    Returns:
        List of extracted images.
    """
    try:
        import fitz  # noqa: PLC0415 — PyMuPDF (optional dependency)
    except ImportError:
        logger.warning("PyMuPDF not installed — skipping image extraction.")
        return []

    if path.suffix.lower() != ".pdf":
        return []

    images: list[ExtractedImage] = []
    try:
        doc = fitz.open(str(path))
    except Exception:
        logger.exception("Failed to open PDF for image extraction: %s", path.name)
        return []

    try:
        img_counter = 0
        for page_num in range(len(doc)):
            page = doc[page_num]
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                except Exception:
                    continue

                if not base_image or not base_image.get("image"):
                    continue

                img_counter += 1
                ext = base_image.get("ext", "png")
                filename = f"img_{img_counter:03d}.{ext}"
                img_data = base_image["image"]

                description = _describe_image(
                    img_data, filename, ext, mode, api_keys, stats
                )

                images.append(ExtractedImage(
                    filename=filename,
                    data=img_data,
                    page_number=page_num + 1,
                    description=description,
                ))
    finally:
        doc.close()

    return images


def _describe_image(
    img_data: bytes,
    filename: str,
    image_ext: str,
    mode: str,
    api_keys: dict[str, str],
    stats: dict[str, Any],
) -> str | None:
    """Generate a description for an extracted image.

    Args:
        img_data: Raw image bytes.
        filename: Image filename for basic descriptions.
        image_ext: Image file extension (e.g. ``"png"``, ``"jpeg"``).
        mode: ``"basic"`` or ``"llm"``.
        api_keys: API keys dict.
        stats: Mutable stats dict.

    Returns:
        Description string, or ``None`` if unavailable.
    """
    if mode == "basic":
        return f"Image: {filename}"

    if mode != "llm":
        return None

    openai_key = api_keys.get("openai_vision")
    if not openai_key:
        logger.warning("LLM image description requested but no openai_vision key.")
        return f"Image: {filename}"

    try:
        from openai import OpenAI  # noqa: PLC0415

        client = OpenAI(api_key=openai_key)
        b64 = base64.b64encode(img_data).decode("utf-8")
        mime_type = _image_mime(image_ext)

        t0 = time.monotonic()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe this image concisely in one or two "
                            "sentences for use as alt-text in a document."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                    },
                ],
            }],
            max_tokens=200,
        )
        duration_ms = int((time.monotonic() - t0) * 1000)

        description = response.choices[0].message.content.strip()
        stats["images_with_llm_descriptions"] = (
            stats.get("images_with_llm_descriptions", 0) + 1
        )
        stats["llm_calls"].append({
            "image": filename,
            "duration_ms": duration_ms,
            "success": True,
            "tokens_used": getattr(response.usage, "total_tokens", None),
        })
        return description

    except Exception as exc:
        logger.warning("LLM image description failed for %s: %s", filename, exc)
        stats["llm_calls"].append({
            "image": filename,
            "duration_ms": 0,
            "success": False,
            "error": str(exc)[:200],
        })
        return f"Image: {filename}"


# ---------------------------------------------------------------------------
# Page-splitting helpers
# ---------------------------------------------------------------------------

# MarkItDown and PyMuPDF both tend to insert page-break markers.
_PAGE_BREAK_PATTERNS = [
    re.compile(r"^-{3,}\s*$", re.MULTILINE),          # --- (horizontal rule)
    re.compile(r"^\f", re.MULTILINE),                  # form-feed character
    re.compile(r"^<!--\s*page\s*break\s*-->", re.MULTILINE | re.IGNORECASE),
]


def _split_into_pages(content: str, file_ext: str) -> list[PageContent]:
    """Split markdown content into per-page sections.

    Uses page-break markers commonly inserted by MarkItDown. If no markers
    are found, returns an empty list (single-page document).

    Args:
        content: Full markdown text.
        file_ext: File extension without dot (e.g. ``"pdf"``).

    Returns:
        List of ``PageContent`` objects, or empty if no page breaks found.
    """
    if file_ext not in _PAGE_AWARE_TYPES:
        return []

    # Try each pattern until one produces multiple pages.
    for pattern in _PAGE_BREAK_PATTERNS:
        parts = pattern.split(content)
        if len(parts) > 1:
            pages = []
            for i, text in enumerate(parts):
                stripped = text.strip()
                if stripped:
                    pages.append(PageContent(page_number=i + 1, text=stripped))
            if len(pages) > 1:
                return pages

    return []


def _image_mime(ext: str) -> str:
    """Map an image file extension to its MIME type.

    Args:
        ext: Image extension without dot (e.g. ``"png"``, ``"jpeg"``).

    Returns:
        MIME type string.
    """
    mapping = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "webp": "image/webp",
        "tiff": "image/tiff",
        "svg": "image/svg+xml",
    }
    return mapping.get(ext.lower().lstrip("."), "image/png")


def _guess_mime(ext: str) -> str:
    """Map file extension to MIME type."""
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
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
    }
    return mapping.get(ext.lower(), "application/octet-stream")
