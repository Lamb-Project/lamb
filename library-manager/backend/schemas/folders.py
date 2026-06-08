"""Pydantic schemas for content folder operations."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from schemas.content import ContentItemSummary

# Server-side validation caps. Folder names are never used as filesystem
# paths, but we still reject path separators and control chars as defense
# in depth against UI/log injection.
_FOLDER_NAME_MAX_LEN = 128
_FOLDER_NAME_FORBIDDEN_CHARS = ("/", "\\", "\x00")


def _validate_folder_name(value: str) -> str:
    """Trim + validate a user-supplied folder name."""
    name = (value or "").strip()
    if not name:
        raise ValueError("Folder name cannot be empty.")
    if len(name) > _FOLDER_NAME_MAX_LEN:
        raise ValueError(f"Folder name cannot exceed {_FOLDER_NAME_MAX_LEN} characters.")
    for ch in _FOLDER_NAME_FORBIDDEN_CHARS:
        if ch in name:
            raise ValueError("Folder name contains forbidden characters.")
    if any(ord(c) < 0x20 for c in name):
        raise ValueError("Folder name contains control characters.")
    return name


class FolderCreateRequest(BaseModel):
    """Body for ``POST /libraries/{lib_id}/folders``."""

    name: str = Field(..., min_length=1, max_length=_FOLDER_NAME_MAX_LEN)
    parent_folder_id: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _validate_folder_name(v)


class FolderRenameRequest(BaseModel):
    """Body for ``PUT /libraries/{lib_id}/folders/{folder_id}``."""

    name: str = Field(..., min_length=1, max_length=_FOLDER_NAME_MAX_LEN)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _validate_folder_name(v)


class FolderMoveRequest(BaseModel):
    """Body for ``PUT /libraries/{lib_id}/folders/{folder_id}/move``."""

    parent_folder_id: str | None = None


class FolderSummary(BaseModel):
    """Compact folder representation for the tree response."""

    id: str
    name: str
    parent_folder_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LibraryTreeResponse(BaseModel):
    """Flat lists of folders and items composing a library's tree.

    The frontend builds the nested structure from these flat lists.
    """

    library_id: str
    folders: list[FolderSummary]
    items: list[ContentItemSummary]


class ItemsMoveRequest(BaseModel):
    """Body for ``POST /libraries/{lib_id}/items/move``."""

    item_ids: list[str] = Field(..., min_length=1, max_length=500)
    folder_id: str | None = None
