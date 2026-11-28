"""What the model is told about where a retrieved passage comes from (#584).

A knowledge base returns passages with their text and their metadata. Until 0.9 only the text
reached the model, so an assistant could not say which document a passage came from, whatever
its instructions said. Each passage is now preceded by the name of its source, the same way
in every retrieval type.
"""
import re

# A file is stored under a name of 32 hexadecimal characters. That name means nothing to the
# teacher who uploaded the file, and is never shown.
_STORED_NAME = re.compile(r"^[0-9a-f]{32}(\.[A-Za-z0-9]{1,10})?$")
MAX_NAME = 200


def _clean(value) -> str:
    """One line, no brackets: the name sits inside a marker the model reads."""
    text = re.sub(r"[\x00-\x1f\x7f\[\]]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:MAX_NAME]


def source_name(metadata) -> str:
    """The name a teacher knows the source by, or '' when none is known: the title of a video,
    the title or the address of a web page, the name a file was uploaded with."""
    if not isinstance(metadata, dict):
        return ""
    if metadata.get("video_id"):
        title = _clean(metadata.get("video_title"))
        return title if title and title != "Unknown" else _clean(f"YouTube: {metadata['video_id']}")
    if metadata.get("page_url"):
        return _clean(metadata.get("title")) or _clean(metadata.get("page_url"))
    for key in ("original_filename", "filename"):
        name = _clean(metadata.get(key))
        if name and name != "Unknown" and not _STORED_NAME.match(name):
            return name
    return ""


def passage(document) -> str:
    """The text of one retrieved passage as the model receives it."""
    text = document.get("data") or ""
    name = source_name(document.get("metadata"))
    return f"[Source: {name}]\n{text}" if name else text


def source_title(metadata) -> str:
    """The title of a source in the list shown beside an answer."""
    return source_name(metadata) or metadata.get("filename", metadata.get("original_filename", "Unknown"))
