"""Shared MIME type detection for import plugins."""

from __future__ import annotations


def guess_mime(ext: str) -> str:
    """Map a file extension to a plausible MIME type.

    Args:
        ext: File extension including the dot.

    Returns:
        MIME type string, or ``application/octet-stream`` if unknown.
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
