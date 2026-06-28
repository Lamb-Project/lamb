"""Unit tests for the content-handler capability layer.

Covers ``plugins.content_handlers.capability`` (enum, payload, registry)
plus the three concrete handlers (text, pages, images). Registry-mutating
tests use ``fresh_capability_registry`` so handler registrations never
leak into other tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from plugins.content_handlers.capability import (
    Capability,
    CapabilityPayload,
    ContentHandler,
    HandlerUnavailable,
)
from plugins.content_handlers.images_handler import ImagesHandler
from plugins.content_handlers.pages_handler import PagesHandler
from plugins.content_handlers.text_handler import TextHandler


def _item_dir(tmp_storage: Path) -> Path:
    """Create a CONTENT_DIR/{org}/{library}/{item} style item directory."""
    item = tmp_storage / "org1" / "lib1" / "item1"
    (item / "content").mkdir(parents=True)
    return item


# ---------------------------------------------------------------------------
# Capability enum + CapabilityPayload
# ---------------------------------------------------------------------------


def test_capability_enum_values():
    """Capability is a str enum with the documented controlled vocabulary."""
    assert Capability.TEXT == "text"
    assert Capability.PAGES == "pages"
    assert Capability.IMAGES == "images"
    assert Capability.AUDIO == "audio"
    assert Capability.TRANSCRIPT == "transcript"
    assert {c.value for c in Capability} == {
        "text", "pages", "images", "audio", "transcript"
    }


def test_capability_payload_fields():
    """CapabilityPayload stores mime and arbitrary body."""
    payload = CapabilityPayload(mime="text/markdown", body="# hi")
    assert payload.mime == "text/markdown"
    assert payload.body == "# hi"


# ---------------------------------------------------------------------------
# CapabilityRegistry.register
# ---------------------------------------------------------------------------


def test_register_rejects_non_enum_capability(fresh_capability_registry):
    """register raises ValueError when capability is not a Capability enum."""

    class BadHandler(ContentHandler):
        capability = "text"  # plain string, not the enum

        def get(self, item_path):
            return CapabilityPayload(mime="text/plain", body="")

    with pytest.raises(ValueError, match="Capability enum member"):
        fresh_capability_registry.register(BadHandler)


def test_register_warns_and_replaces_on_duplicate(fresh_capability_registry, caplog):
    """register warns and replaces when a capability is registered twice."""

    class FirstAudio(ContentHandler):
        capability = Capability.AUDIO

        def get(self, item_path):
            return CapabilityPayload(mime="audio/mpeg", body=b"")

    class SecondAudio(ContentHandler):
        capability = Capability.AUDIO

        def get(self, item_path):
            return CapabilityPayload(mime="audio/mpeg", body=b"")

    fresh_capability_registry.register(FirstAudio)
    with caplog.at_level("WARNING"):
        fresh_capability_registry.register(SecondAudio)

    assert fresh_capability_registry._handlers[Capability.AUDIO] is SecondAudio
    assert any("already registered" in (r.getMessage() or "") for r in caplog.records)


def test_register_same_class_twice_no_warning(fresh_capability_registry, caplog):
    """Re-registering the identical class is idempotent and does not warn."""

    class SameAudio(ContentHandler):
        capability = Capability.AUDIO

        def get(self, item_path):
            return CapabilityPayload(mime="audio/mpeg", body=b"")

    fresh_capability_registry.register(SameAudio)
    with caplog.at_level("WARNING"):
        fresh_capability_registry.register(SameAudio)
    assert not any("already registered" in (r.getMessage() or "") for r in caplog.records)


def test_register_returns_class(fresh_capability_registry):
    """register returns the handler class unchanged (decorator-friendly)."""

    class RetAudio(ContentHandler):
        capability = Capability.AUDIO

        def get(self, item_path):
            return CapabilityPayload(mime="audio/mpeg", body=b"")

    assert fresh_capability_registry.register(RetAudio) is RetAudio


# ---------------------------------------------------------------------------
# CapabilityRegistry.get
# ---------------------------------------------------------------------------


def test_get_by_enum_returns_fresh_instance(fresh_capability_registry):
    """get returns a fresh handler instance keyed by enum value."""

    class TranscriptH(ContentHandler):
        capability = Capability.TRANSCRIPT

        def get(self, item_path):
            return CapabilityPayload(mime="text/plain", body="")

    fresh_capability_registry.register(TranscriptH)
    a = fresh_capability_registry.get(Capability.TRANSCRIPT)
    b = fresh_capability_registry.get(Capability.TRANSCRIPT)
    assert isinstance(a, TranscriptH)
    assert a is not b


def test_get_by_string(fresh_capability_registry):
    """get accepts the string form of a capability."""

    class TranscriptH(ContentHandler):
        capability = Capability.TRANSCRIPT

        def get(self, item_path):
            return CapabilityPayload(mime="text/plain", body="")

    fresh_capability_registry.register(TranscriptH)
    assert isinstance(fresh_capability_registry.get("transcript"), TranscriptH)


def test_get_unknown_string_returns_none(fresh_capability_registry):
    """get returns None for a string that is not a Capability value."""
    assert fresh_capability_registry.get("nonsense") is None


def test_get_unregistered_capability_returns_none(fresh_capability_registry):
    """get returns None when nothing is registered for a valid capability."""
    fresh_capability_registry._handlers.clear()
    assert fresh_capability_registry.get(Capability.AUDIO) is None


# ---------------------------------------------------------------------------
# list_handlers / registered_capabilities / _reset
# ---------------------------------------------------------------------------


def test_list_handlers_sorted(fresh_capability_registry):
    """list_handlers returns rows sorted by capability value."""
    fresh_capability_registry._handlers.clear()

    class ImagesH(ContentHandler):
        capability = Capability.IMAGES
        description = "imgs"

        def get(self, item_path):
            return CapabilityPayload(mime="application/json", body=[])

    class AudioH(ContentHandler):
        capability = Capability.AUDIO
        description = "aud"

        def get(self, item_path):
            return CapabilityPayload(mime="audio/mpeg", body=b"")

    fresh_capability_registry.register(ImagesH)
    fresh_capability_registry.register(AudioH)
    rows = fresh_capability_registry.list_handlers()
    caps = [r["capability"] for r in rows]
    assert caps == sorted(caps)
    assert {"capability": "audio", "description": "aud"} in rows


def test_registered_capabilities(fresh_capability_registry):
    """registered_capabilities lists the currently registered enum keys."""
    fresh_capability_registry._handlers.clear()

    class AudioH(ContentHandler):
        capability = Capability.AUDIO

        def get(self, item_path):
            return CapabilityPayload(mime="audio/mpeg", body=b"")

    fresh_capability_registry.register(AudioH)
    assert fresh_capability_registry.registered_capabilities() == [Capability.AUDIO]


def test_reset_clears_handlers(fresh_capability_registry):
    """_reset empties the handler registry."""

    class AudioH(ContentHandler):
        capability = Capability.AUDIO

        def get(self, item_path):
            return CapabilityPayload(mime="audio/mpeg", body=b"")

    fresh_capability_registry.register(AudioH)
    fresh_capability_registry._reset()
    assert fresh_capability_registry._handlers == {}


# ---------------------------------------------------------------------------
# TextHandler
# ---------------------------------------------------------------------------


def test_text_handler_returns_full_md(tmp_storage):
    """TextHandler reads content/full.md and returns it as text/markdown."""
    item = _item_dir(tmp_storage)
    (item / "content" / "full.md").write_text("# Title\nBody", encoding="utf-8")
    payload = TextHandler().get(item)
    assert payload.mime == "text/markdown"
    assert payload.body == "# Title\nBody"


def test_text_handler_unavailable_without_file(tmp_storage):
    """TextHandler raises HandlerUnavailable when full.md is missing."""
    item = _item_dir(tmp_storage)
    with pytest.raises(HandlerUnavailable):
        TextHandler().get(item)


# ---------------------------------------------------------------------------
# PagesHandler
# ---------------------------------------------------------------------------


def test_pages_handler_returns_sorted_pages(tmp_storage):
    """PagesHandler lists content/pages/*.md ordered by page number."""
    item = _item_dir(tmp_storage)
    pages = item / "content" / "pages"
    pages.mkdir()
    (pages / "page_002.md").write_text("two", encoding="utf-8")
    (pages / "page_010.md").write_text("ten", encoding="utf-8")
    (pages / "page_001.md").write_text("one", encoding="utf-8")
    (pages / "notes.txt").write_text("ignored", encoding="utf-8")  # non-md ignored
    payload = PagesHandler().get(item)
    assert payload.mime == "application/json"
    assert payload.body == [
        {"page": 1, "markdown": "one"},
        {"page": 2, "markdown": "two"},
        {"page": 10, "markdown": "ten"},
    ]


def test_pages_handler_filename_without_number_falls_back_to_zero(tmp_storage):
    """A page file with no embedded number is treated as page 0 (sorts first)."""
    item = _item_dir(tmp_storage)
    pages = item / "content" / "pages"
    pages.mkdir()
    (pages / "intro.md").write_text("intro", encoding="utf-8")
    (pages / "page_001.md").write_text("one", encoding="utf-8")
    payload = PagesHandler().get(item)
    assert payload.body == [
        {"page": 0, "markdown": "intro"},
        {"page": 1, "markdown": "one"},
    ]


def test_pages_handler_unavailable_without_dir(tmp_storage):
    """PagesHandler raises HandlerUnavailable when the pages dir is absent."""
    item = _item_dir(tmp_storage)
    with pytest.raises(HandlerUnavailable):
        PagesHandler().get(item)


def test_pages_handler_unavailable_when_empty(tmp_storage):
    """PagesHandler raises HandlerUnavailable when no .md page files exist."""
    item = _item_dir(tmp_storage)
    pages = item / "content" / "pages"
    pages.mkdir()
    (pages / "readme.txt").write_text("x", encoding="utf-8")
    with pytest.raises(HandlerUnavailable):
        PagesHandler().get(item)


# ---------------------------------------------------------------------------
# ImagesHandler
# ---------------------------------------------------------------------------


def test_images_handler_returns_gallery(tmp_storage):
    """ImagesHandler lists images with filename, public URL and MIME type."""
    item = _item_dir(tmp_storage)
    images = item / "content" / "images"
    images.mkdir()
    (images / "img_001.png").write_bytes(b"\x89PNG")
    (images / "photo.JPG").write_bytes(b"\xff\xd8")
    (images / "notes.txt").write_text("ignored", encoding="utf-8")  # non-image ignored
    payload = ImagesHandler().get(item)
    assert payload.mime == "application/json"
    # Sorted by filename: img_001.png before photo.JPG.
    assert payload.body == [
        {
            "filename": "img_001.png",
            "url": "/libraries/lib1/items/item1/content/images/file/img_001.png",
            "mime": "image/png",
        },
        {
            "filename": "photo.JPG",
            "url": "/libraries/lib1/items/item1/content/images/file/photo.JPG",
            "mime": "image/jpeg",
        },
    ]


def test_images_handler_recognised_ext_uses_mapped_mime(tmp_storage):
    """A recognised image extension resolves to its mapped MIME type."""
    item = _item_dir(tmp_storage)
    images = item / "content" / "images"
    images.mkdir()
    (images / "scan.pnm").write_bytes(b"P6")
    payload = ImagesHandler().get(item)
    assert payload.body[0]["mime"] == "image/pnm"


def test_images_handler_unavailable_without_dir(tmp_storage):
    """ImagesHandler raises HandlerUnavailable when the images dir is absent."""
    item = _item_dir(tmp_storage)
    with pytest.raises(HandlerUnavailable):
        ImagesHandler().get(item)


def test_images_handler_unavailable_when_no_images(tmp_storage):
    """ImagesHandler raises HandlerUnavailable when only non-image files exist."""
    item = _item_dir(tmp_storage)
    images = item / "content" / "images"
    images.mkdir()
    (images / "readme.txt").write_text("x", encoding="utf-8")
    with pytest.raises(HandlerUnavailable):
        ImagesHandler().get(item)
