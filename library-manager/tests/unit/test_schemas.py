"""Unit tests for the Pydantic schemas under ``backend/schemas/``.

Covers ``common``, ``libraries``, ``content``, and ``folders``: valid input
constructs, and boundary / bad-type / missing-field cases raise
``pydantic.ValidationError``.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError
from schemas.common import MessageResponse, PaginationParams
from schemas.content import (
    ContentItemDetail,
    ContentItemSummary,
    FileImportParams,
    ImportAcceptedResponse,
    UrlImportRequest,
    YoutubeImportRequest,
)
from schemas.folders import (
    _FOLDER_NAME_MAX_LEN,
    FolderCreateRequest,
    FolderMoveRequest,
    FolderRenameRequest,
    ItemsMoveRequest,
    _validate_folder_name,
)
from schemas.libraries import LibraryCreate, LibraryResponse, LibraryUpdate


class TestCommon:
    """``PaginationParams`` bounds and ``MessageResponse``."""

    def test_pagination_defaults(self):
        """Defaults are limit=20, offset=0."""
        p = PaginationParams()
        assert p.limit == 20 and p.offset == 0

    def test_pagination_bounds_ok(self):
        """Edge values within bounds are accepted (limit 1..100, offset >=0)."""
        assert PaginationParams(limit=1, offset=0).limit == 1
        assert PaginationParams(limit=100, offset=5).limit == 100

    @pytest.mark.parametrize(
        "kwargs",
        [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "x"}],
    )
    def test_pagination_invalid(self, kwargs):
        """Out-of-range or wrong-typed pagination values are rejected."""
        with pytest.raises(ValidationError):
            PaginationParams(**kwargs)

    def test_message_response(self):
        """MessageResponse requires a string message."""
        assert MessageResponse(message="hi").message == "hi"
        with pytest.raises(ValidationError):
            MessageResponse()


class TestLibrarySchemas:
    """LibraryCreate/Update/Response validation."""

    def test_library_create_valid(self):
        """A full valid body constructs successfully."""
        m = LibraryCreate(id="lib-1", organization_id="org-1", name="Docs")
        assert m.name == "Docs" and m.import_config is None

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"organization_id": "o", "name": "n"},  # missing id
            {"id": "i", "name": "n"},  # missing org
            {"id": "i", "organization_id": "o"},  # missing name
            {"id": "i", "organization_id": "o", "name": ""},  # empty name
            {"id": "i", "organization_id": "o", "name": "x" * 256},  # too long
        ],
    )
    def test_library_create_invalid(self, kwargs):
        """Missing required fields or name length violations are rejected."""
        with pytest.raises(ValidationError):
            LibraryCreate(**kwargs)

    def test_library_update_all_optional(self):
        """LibraryUpdate accepts an empty body (partial update)."""
        assert LibraryUpdate().name is None

    def test_library_update_name_bounds(self):
        """LibraryUpdate enforces name length when provided."""
        with pytest.raises(ValidationError):
            LibraryUpdate(name="")
        with pytest.raises(ValidationError):
            LibraryUpdate(name="x" * 256)

    def test_library_response_from_attrs(self):
        """LibraryResponse builds with defaults and a datetime."""
        m = LibraryResponse(
            id="l", organization_id="o", name="n", created_at=datetime.now()
        )
        assert m.item_count == 0


class TestContentImportSchemas:
    """File/URL/YouTube import request validation."""

    def test_file_import_valid(self):
        """A valid file-import params body constructs."""
        m = FileImportParams(plugin_name="simple", title="Doc")
        assert m.api_keys is None

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"plugin_name": "", "title": "t"},  # empty plugin
            {"plugin_name": "p", "title": ""},  # empty title
            {"plugin_name": "p", "title": "x" * 501},  # title too long
            {"plugin_name": "p"},  # missing title
        ],
    )
    def test_file_import_invalid(self, kwargs):
        """Empty/oversize/missing fields are rejected."""
        with pytest.raises(ValidationError):
            FileImportParams(**kwargs)

    def test_url_import_valid_and_default_plugin(self):
        """URL import accepts http(s) and defaults plugin_name."""
        m = UrlImportRequest(url="https://example.com", title="Page")
        assert m.plugin_name == "url_import"

    @pytest.mark.parametrize("url", ["ftp://x", "example.com", "", "javascript:1"])
    def test_url_import_rejects_non_http(self, url):
        """URLs not starting with http:// or https:// are rejected."""
        with pytest.raises(ValidationError):
            UrlImportRequest(url=url, title="t")

    def test_youtube_import_valid(self):
        """A valid YouTube URL constructs with default language/plugin."""
        m = YoutubeImportRequest(
            video_url="https://youtu.be/abc", title="Vid"
        )
        assert m.language == "en"
        assert m.plugin_name == "youtube_transcript_import"
        m2 = YoutubeImportRequest(
            video_url="https://www.youtube.com/watch?v=z", title="Vid"
        )
        assert m2.video_url.endswith("v=z")

    @pytest.mark.parametrize(
        "url", ["https://vimeo.com/1", "https://example.com", "not-a-url"]
    )
    def test_youtube_import_rejects_non_youtube(self, url):
        """Non-YouTube links are rejected by the validator."""
        with pytest.raises(ValidationError):
            YoutubeImportRequest(video_url=url, title="t")

    def test_import_accepted_defaults(self):
        """ImportAcceptedResponse defaults status to 'processing'."""
        m = ImportAcceptedResponse(item_id="i", job_id="j")
        assert m.status == "processing"


class TestContentItemSchemas:
    """ContentItemSummary / ContentItemDetail validation."""

    def _summary_kwargs(self):
        return {
            "id": "i",
            "title": "T",
            "source_type": "file",
            "import_plugin": "simple",
            "status": "ready",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

    def test_summary_valid_with_defaults(self):
        """Summary constructs with required fields and defaulted counts."""
        m = ContentItemSummary(**self._summary_kwargs())
        assert m.page_count == 0 and m.image_count == 0
        assert m.source_url is None

    def test_summary_missing_required(self):
        """Omitting a required field raises ValidationError."""
        kwargs = self._summary_kwargs()
        del kwargs["status"]
        with pytest.raises(ValidationError):
            ContentItemSummary(**kwargs)

    def test_detail_extends_summary(self):
        """Detail adds optional metadata/permalink fields over the summary."""
        m = ContentItemDetail(
            **self._summary_kwargs(),
            metadata={"a": 1},
            permalink_base="/docs/x",
        )
        assert m.metadata == {"a": 1}
        assert m.permalink_base == "/docs/x"


class TestFolderSchemas:
    """Folder create/rename/move and items-move validation."""

    def test_validate_folder_name_over_length_branch(self):
        """``_validate_folder_name`` rejects names longer than the cap.

        Exercised directly because the Field's ``max_length`` would otherwise
        reject the value before the validator's length check is reached.
        """
        with pytest.raises(ValueError, match="cannot exceed"):
            _validate_folder_name("x" * (_FOLDER_NAME_MAX_LEN + 1))

    def test_folder_create_valid_and_trims(self):
        """A valid name is accepted and surrounding whitespace trimmed."""
        m = FolderCreateRequest(name="  Reports  ")
        assert m.name == "Reports", "name should be trimmed"
        assert m.parent_folder_id is None

    @pytest.mark.parametrize(
        "name",
        ["", "   ", "a/b", "a\\b", "a\x00b", "a\x01b", "x" * 129],
    )
    def test_folder_create_invalid_names(self, name):
        """Empty, separator, control-char, and oversize names are rejected."""
        with pytest.raises(ValidationError):
            FolderCreateRequest(name=name)

    def test_folder_rename_valid_and_invalid(self):
        """Rename applies the same name validation as create."""
        assert FolderRenameRequest(name=" Ok ").name == "Ok"
        with pytest.raises(ValidationError):
            FolderRenameRequest(name="bad/name")

    def test_folder_move_optional_parent(self):
        """FolderMoveRequest allows a null parent (move to root)."""
        assert FolderMoveRequest().parent_folder_id is None
        assert FolderMoveRequest(parent_folder_id="f1").parent_folder_id == "f1"

    def test_items_move_valid(self):
        """ItemsMoveRequest requires 1..500 item ids."""
        m = ItemsMoveRequest(item_ids=["a", "b"], folder_id="f")
        assert m.item_ids == ["a", "b"]

    @pytest.mark.parametrize(
        "item_ids",
        [[], ["x"] * 501],
    )
    def test_items_move_invalid_length(self, item_ids):
        """Empty or oversize item_ids lists are rejected."""
        with pytest.raises(ValidationError):
            ItemsMoveRequest(item_ids=item_ids)
