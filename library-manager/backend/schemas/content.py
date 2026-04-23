"""Pydantic schemas for content items and import operations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# --- Import requests ---


class FileImportParams(BaseModel):
    """Form fields accompanying a file upload to ``POST /libraries/{lib_id}/import/file``.

    The file itself is received as ``UploadFile``; these are the extra
    multipart form fields.
    """

    plugin_name: str = Field(..., min_length=1, description="Import plugin to use.")
    title: str = Field(..., min_length=1, max_length=500, description="Document title.")
    plugin_params: dict[str, Any] | None = Field(
        None, description="Plugin-specific parameters."
    )
    api_keys: dict[str, str] | None = Field(
        None, description="Org API keys needed by this plugin (e.g. openai_vision)."
    )


class UrlImportRequest(BaseModel):
    """Body for ``POST /libraries/{lib_id}/import/url``."""

    url: str = Field(..., min_length=1, description="URL to import.")
    plugin_name: str = Field(
        "url_import", min_length=1, description="Import plugin to use."
    )
    title: str = Field(..., min_length=1, max_length=500, description="Document title.")
    plugin_params: dict[str, Any] | None = None
    api_keys: dict[str, str] | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure the URL starts with http:// or https://."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class YoutubeImportRequest(BaseModel):
    """Body for ``POST /libraries/{lib_id}/import/youtube``."""

    video_url: str = Field(..., min_length=1, description="YouTube video URL.")
    language: str = Field("en", description="Transcript language (ISO 639-1).")
    plugin_name: str = Field(
        "youtube_transcript_import",
        min_length=1,
        description="Import plugin to use.",
    )
    title: str = Field(..., min_length=1, max_length=500, description="Document title.")
    plugin_params: dict[str, Any] | None = None
    api_keys: dict[str, str] | None = None

    @field_validator("video_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Basic check that the URL looks like a YouTube link."""
        if "youtube.com" not in v and "youtu.be" not in v:
            raise ValueError("URL must be a YouTube link.")
        return v


# --- Import response ---


class ImportAcceptedResponse(BaseModel):
    """Returned immediately when an import job is queued."""

    item_id: str
    job_id: str
    status: str = "processing"


# --- Content item responses ---


class ContentItemSummary(BaseModel):
    """Compact representation for list endpoints."""

    id: str
    title: str
    source_type: str
    original_filename: str | None = None
    content_type: str | None = None
    file_size: int | None = None
    import_plugin: str
    status: str
    page_count: int = 0
    image_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContentItemDetail(ContentItemSummary):
    """Full representation including metadata and permalinks."""

    source_url: str | None = None
    import_params: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    processing_stats: dict[str, Any] | None = None
    error_message: str | None = None
    permalink_base: str | None = None


class ContentItemListResponse(BaseModel):
    """Paginated list of content items."""

    items: list[ContentItemSummary]
    total: int


class ContentItemStatusResponse(BaseModel):
    """Import job status for a single item."""

    item_id: str
    status: str
    error_message: str | None = None
    processing_stats: dict[str, Any] | None = None


# --- Content serving ---


class PageListResponse(BaseModel):
    """List of available page files for a content item."""

    pages: list[str]
    count: int


class ImageListResponse(BaseModel):
    """List of available image files for a content item."""

    images: list[str]
    count: int
