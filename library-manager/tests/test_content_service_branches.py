"""Branch tests for ``services.content_service`` added by the feature.

Covers the pages/images write loops, list_pages/list_images, capability
detection from disk, and the mkdir PermissionError / OSError handlers.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from plugins.base import ExtractedImage, PageContent
from services import content_service as cs


def _ids():
    return uuid4().hex, uuid4().hex, "org-cs"


def test_write_pages_images_then_list_and_detect():
    item_id, lib_id, org_id = _ids()
    base = cs.write_structured_content(
        item_id=item_id,
        library_id=lib_id,
        organization_id=org_id,
        title="Doc",
        full_text="# Full\n\nbody text",
        pages=[PageContent(page_number=1, text="page one"),
               PageContent(page_number=2, text="page two")],
        images=[ExtractedImage(filename="img_001.png", data=b"PNGBYTES")],
        item_metadata={"k": "v"},
        source_ref={"type": "file"},
    )
    assert cs.list_pages(org_id, lib_id, item_id) == ["page_001.md", "page_002.md"]
    assert cs.list_images(org_id, lib_id, item_id) == ["img_001.png"]
    caps = cs.detect_capabilities(base)
    assert {"text", "pages", "images"} <= set(caps)


def test_write_permission_error_is_translated(monkeypatch):
    def boom_mkdir(self, *a, **k):
        raise PermissionError("not writable")

    monkeypatch.setattr(Path, "mkdir", boom_mkdir)
    item_id, lib_id, org_id = _ids()
    with pytest.raises(RuntimeError, match="not writable"):
        cs.write_structured_content(
            item_id=item_id, library_id=lib_id, organization_id=org_id,
            title="T", full_text="x", pages=[], images=[],
            item_metadata={}, source_ref={},
        )


def test_write_oserror_is_translated(monkeypatch):
    def boom_mkdir(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "mkdir", boom_mkdir)
    item_id, lib_id, org_id = _ids()
    with pytest.raises(RuntimeError, match="storage is"):
        cs.write_structured_content(
            item_id=item_id, library_id=lib_id, organization_id=org_id,
            title="T", full_text="x", pages=[], images=[],
            item_metadata={}, source_ref={},
        )
