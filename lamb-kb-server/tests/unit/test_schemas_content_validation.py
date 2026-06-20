"""Unit tests for ``schemas.content`` validators (extra_metadata guards)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.content import AddContentRequest, DocumentInputPayload


def _doc(**over):
    base = dict(source_item_id="i1", title="T", text="body")
    base.update(over)
    return base


def test_extra_metadata_accepts_primitives():
    doc = DocumentInputPayload(**_doc(extra_metadata={
        "s": "x", "i": 1, "f": 1.5, "b": True,
    }))
    assert doc.extra_metadata["i"] == 1


def test_extra_metadata_rejects_none_value():
    # pydantic's typed-dict value union rejects None before the custom
    # validator's defensive check is reached.
    with pytest.raises(ValidationError):
        DocumentInputPayload(**_doc(extra_metadata={"k": None}))


def test_extra_metadata_rejects_non_primitive():
    with pytest.raises(ValidationError):
        DocumentInputPayload(**_doc(extra_metadata={"k": ["a", "b"]}))


def test_add_content_request_requires_documents():
    # Field(min_length=1) rejects an empty documents list.
    with pytest.raises(ValidationError):
        AddContentRequest(documents=[])


def test_add_content_request_valid():
    req = AddContentRequest(documents=[DocumentInputPayload(**_doc())])
    assert len(req.documents) == 1
