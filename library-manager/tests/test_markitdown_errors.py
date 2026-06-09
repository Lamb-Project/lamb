"""Unit tests for the user-friendly markitdown error translator."""

from __future__ import annotations

import pytest
from plugins._markitdown_errors import humanize_markitdown_error


class _Fake(Exception):
    """Generic exception used to spoof markitdown's exception classes by name."""


class MissingDependencyException(Exception):  # noqa: N818 — mirrors markitdown's name
    pass


class UnsupportedFormatException(Exception):  # noqa: N818
    pass


class FileConversionException(Exception):  # noqa: N818
    pass


def test_missing_dependency_with_ext_hint_in_message():
    exc = MissingDependencyException(
        "PdfConverter recognized the input as a potential .pdf file, but the "
        "dependencies needed to read .pdf files have not been installed."
    )
    msg = humanize_markitdown_error(exc, "report.pdf")
    assert "report.pdf" in msg
    assert ".pdf" in msg
    assert "not installed" in msg
    # Should NOT include pip install hints.
    assert "pip install" not in msg


def test_missing_dependency_falls_back_to_filename_extension():
    exc = MissingDependencyException("no readers available")
    msg = humanize_markitdown_error(exc, "song.mp3")
    assert "song.mp3" in msg
    assert ".mp3" in msg


def test_unsupported_format():
    exc = UnsupportedFormatException("nothing matched")
    msg = humanize_markitdown_error(exc, "blob.bin")
    assert "blob.bin" in msg
    assert "not supported" in msg.lower()


def test_file_conversion_corrupted():
    exc = FileConversionException("Stream error / corrupted")
    msg = humanize_markitdown_error(exc, "broken.docx")
    assert "broken.docx" in msg
    # Should mention readability / corruption (one of: unreadable, corrupted, password)
    assert any(w in msg.lower() for w in ("unreadable", "corrupted", "password"))


def test_generic_fallback_does_not_leak_class_name():
    exc = ValueError("Random internal error xyz")
    msg = humanize_markitdown_error(exc, "doc.txt")
    assert "doc.txt" in msg
    # Generic message: shouldn't echo the original raw error string verbatim
    assert "Random internal error xyz" not in msg
    assert "ValueError" not in msg


def test_empty_file_detection():
    exc = Exception("File is empty")
    msg = humanize_markitdown_error(exc, "x.pdf")
    assert "empty" in msg.lower()
    assert "x.pdf" in msg


@pytest.mark.parametrize("ext,expected", [
    ("report.pdf", ".pdf"),
    ("photo.JPG", ".jpg"),
    ("noext", ""),
])
def test_ext_label(ext, expected):
    from plugins._markitdown_errors import _ext_label

    assert _ext_label(ext) == expected
