"""Unit tests for the user-friendly markitdown error translator.

Covers ``humanize_markitdown_error`` across each exception/message branch,
plus the ``_ext_label`` and ``_guess_format_from_message`` helpers.
"""

from __future__ import annotations

import pytest
from plugins._markitdown_errors import (
    _ext_label,
    _guess_format_from_message,
    humanize_markitdown_error,
)


class MissingDependencyException(Exception):  # noqa: N818 — mirrors markitdown's name
    pass


class UnsupportedFormatException(Exception):  # noqa: N818
    pass


class FileConversionException(Exception):  # noqa: N818
    pass


# ---------------------------------------------------------------------------
# humanize_markitdown_error
# ---------------------------------------------------------------------------


def test_missing_dependency_with_ext_hint_in_message():
    """MissingDependency with a .pdf hint names the format and hides pip hints."""
    exc = MissingDependencyException(
        "PdfConverter recognized the input as a potential .pdf file, but the "
        "dependencies needed to read .pdf files have not been installed."
    )
    msg = humanize_markitdown_error(exc, "report.pdf")
    assert "report.pdf" in msg
    assert ".pdf" in msg
    assert "not installed" in msg
    assert "pip install" not in msg


def test_missing_dependency_falls_back_to_filename_extension():
    """Without a message hint, the filename extension supplies the format."""
    exc = MissingDependencyException("no readers available")
    msg = humanize_markitdown_error(exc, "song.mp3")
    assert "song.mp3" in msg
    assert ".mp3" in msg


def test_missing_dependency_no_ext_anywhere_uses_generic_reader_message():
    """No message hint and no filename extension yields the generic reader text."""
    exc = MissingDependencyException("no readers available")
    msg = humanize_markitdown_error(exc, "noextfile")
    assert "noextfile" in msg
    assert "required reader for this file" in msg


def test_missing_dependency_detected_by_message_substring():
    """Detection also works when only the message mentions the exception name."""
    exc = Exception("wrapped: MissingDependencyException for .docx")
    msg = humanize_markitdown_error(exc, "doc.docx")
    assert "doc.docx" in msg
    assert "not installed" in msg


def test_unsupported_format():
    """UnsupportedFormat yields the 'not supported / try a different plugin' text."""
    exc = UnsupportedFormatException("nothing matched")
    msg = humanize_markitdown_error(exc, "blob.bin")
    assert "blob.bin" in msg
    assert "not supported" in msg.lower()


def test_unsupported_format_detected_by_message():
    """UnsupportedFormat is detected via the 'unsupportedformat' message token."""
    exc = Exception("internal unsupportedformat raised")
    msg = humanize_markitdown_error(exc, "x.bin")
    assert "not supported" in msg.lower()


def test_file_conversion_corrupted():
    """FileConversion yields the unreadable/corrupted/password text."""
    exc = FileConversionException("Stream error / corrupted")
    msg = humanize_markitdown_error(exc, "broken.docx")
    assert "broken.docx" in msg
    assert any(w in msg.lower() for w in ("unreadable", "corrupted", "password"))


def test_file_conversion_detected_by_message():
    """FileConversion is detected via the 'fileconversion' message token."""
    exc = Exception("a fileconversion problem occurred")
    msg = humanize_markitdown_error(exc, "y.docx")
    assert any(w in msg.lower() for w in ("unreadable", "corrupted", "password"))


def test_empty_file_detection():
    """An 'empty' message produces the dedicated empty-file message."""
    exc = Exception("File is empty")
    msg = humanize_markitdown_error(exc, "x.pdf")
    assert "empty" in msg.lower()
    assert "x.pdf" in msg


def test_zero_bytes_detection():
    """A '0 bytes' message is also classified as an empty file."""
    exc = Exception("file has 0 bytes")
    msg = humanize_markitdown_error(exc, "z.pdf")
    assert "empty" in msg.lower()


def test_generic_fallback_does_not_leak_class_name():
    """An unrecognised error falls back without leaking the raw string or class."""
    exc = ValueError("Random internal error xyz")
    msg = humanize_markitdown_error(exc, "doc.txt")
    assert "doc.txt" in msg
    assert "Random internal error xyz" not in msg
    assert "ValueError" not in msg
    assert "could not be converted to" in msg


# ---------------------------------------------------------------------------
# _ext_label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("report.pdf", ".pdf"),
        ("photo.JPG", ".jpg"),
        ("noext", ""),
        ("archive.tar.gz", ".gz"),
        ("trailingdot.", ""),
    ],
)
def test_ext_label(filename, expected):
    """_ext_label returns the lowercase dotted extension or '' when absent."""
    assert _ext_label(filename) == expected


# ---------------------------------------------------------------------------
# _guess_format_from_message
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message,expected",
    [
        ("recognized the input as a potential .pdf file", ".pdf"),
        ("as a potential .DOCX file, but", ".docx"),
        ("no format hint here", ""),
    ],
)
def test_guess_format_from_message(message, expected):
    """_guess_format_from_message extracts the '.ext' hint or returns ''."""
    assert _guess_format_from_message(message) == expected
