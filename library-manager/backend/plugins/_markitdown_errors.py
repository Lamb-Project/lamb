"""User-friendly error translation for MarkItDown conversion failures.

The worker stores ``str(exc)[:500]`` verbatim as the item's
``error_message`` — that string is what the UI displays in the
"Markdown" tab when an import lands in the ``failed`` state. The
markitdown library raises a long, technical chain on dependency or
format problems (``MissingDependencyException`` listing pip install
hints, ``FileConversionException`` with stack-like detail) that is
useless to end users.

This helper inspects the exception (by class name and message) and
returns a short, plain message tailored to the failure mode. The full
chain is still in the operator log via ``logger.exception`` upstream.
"""

from __future__ import annotations


def humanize_markitdown_error(exc: BaseException, filename: str) -> str:
    """Translate a markitdown failure into a short user-facing message.

    Falls back to a generic message if the exception doesn't match a
    known pattern, so unknown failures don't leak a raw stack chain.

    Args:
        exc: The exception raised by ``MarkItDown.convert``.
        filename: The user-facing filename (for inclusion in the message).
    """
    cls = type(exc).__name__
    msg = str(exc)
    lower = msg.lower()

    # MarkItDown raises this when an optional reader (pdf, docx, audio, ...)
    # isn't installed. The raw message includes a long pip-install hint.
    if cls == "MissingDependencyException" or "missingdependencyexception" in lower:
        fmt = _guess_format_from_message(msg) or _ext_label(filename)
        if fmt:
            return (
                f"Cannot import {filename}: support for {fmt} files is not "
                "installed on the server. Ask an administrator to install "
                "the missing import dependency."
            )
        return (
            f"Cannot import {filename}: a required reader for this file "
            "type is not installed on the server. Ask an administrator."
        )

    if cls == "UnsupportedFormatException" or "unsupportedformat" in lower:
        return (
            f"Cannot import {filename}: this file format is not supported "
            "by the importer. Try a different plugin (e.g. URL import for "
            "a web page, or a different document format)."
        )

    if cls == "FileConversionException" or "fileconversion" in lower:
        return (
            f"Cannot import {filename}: the file is unreadable, corrupted, "
            "or password-protected. Verify the file opens in its native "
            "application and try again."
        )

    # Empty or zero-byte files
    if "empty" in lower or "0 bytes" in lower:
        return f"Cannot import {filename}: the file is empty."

    # Generic fallback — keep it short and avoid leaking the class name.
    return (
        f"Cannot import {filename}: the file could not be converted to "
        "Markdown. Try a different import plugin or contact an administrator."
    )


def _guess_format_from_message(msg: str) -> str:
    """Pull the ``.ext`` hint out of MarkItDown's MissingDependency message."""
    # MarkItDown writes lines like "as a potential .pdf file" — pluck the ext.
    import re

    m = re.search(r"potential\s+\.([a-z0-9]{1,8})\s+file", msg, re.IGNORECASE)
    if m:
        return f".{m.group(1).lower()}"
    return ""


def _ext_label(filename: str) -> str:
    if "." not in filename:
        return ""
    ext = filename.rsplit(".", 1)[-1].lower()
    return f".{ext}" if ext else ""
