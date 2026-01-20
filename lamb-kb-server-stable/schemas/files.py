"""
Pydantic schemas for file registry and ingestion job tracking.

This module provides comprehensive models for:
- File registry responses
- Ingestion job status tracking
- Progress monitoring
- Error reporting
"""

from pydantic import BaseModel, Field, computed_field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class IngestionStatus(str, Enum):
    """
    Status values for ingestion jobs.
    
    Status Flow:
        PENDING -> PROCESSING -> COMPLETED
                             -> FAILED  
                             -> CANCELLED
        
    Any status can transition to DELETED (soft delete).
    """
    PENDING = "pending"        # Job created, waiting to start
    PROCESSING = "processing"  # Job is currently running
    COMPLETED = "completed"    # Job finished successfully
    FAILED = "failed"          # Job failed with error
    CANCELLED = "cancelled"    # Job was cancelled by user
    DELETED = "deleted"        # Soft-deleted


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

class IngestionProgress(BaseModel):
    """
    Progress information for an ingestion job.
    
    Used to track long-running operations like large file processing.
    The percentage is calculated from current/total.
    
    Attributes:
        current: Current progress value (e.g., chunks processed)
        total: Total expected value (e.g., total chunks to process)
        percentage: Calculated completion percentage (0-100)
        message: Human-readable status message describing current activity
    
    Example:
        ```json
        {
            "current": 45,
            "total": 120,
            "percentage": 37.5,
            "message": "Processing chunk 45 of 120..."
        }
        ```
    """
    current: int = Field(0, ge=0, description="Current progress value (e.g., chunks processed)")
    total: int = Field(0, ge=0, description="Total expected value (e.g., total chunks)")
    percentage: float = Field(0.0, ge=0, le=100, description="Completion percentage (0-100)")
    message: Optional[str] = Field(None, max_length=255, description="Current status message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "current": 45,
                "total": 120,
                "percentage": 37.5,
                "message": "Adding chunks to collection..."
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR DETAILS
# ═══════════════════════════════════════════════════════════════════════════════

class IngestionErrorDetails(BaseModel):
    """
    Detailed error information for failed ingestion jobs.
    
    Provides comprehensive error context for debugging and user feedback.
    
    Attributes:
        exception_type: Python exception class name (e.g., "ValueError")
        traceback: Last portion of the stack trace (truncated for storage)
        file_path: Path to the file that caused the error
        plugin_name: Name of the plugin that was processing
        stage: Processing stage where error occurred
        context: Additional context-specific information
    
    Example:
        ```json
        {
            "exception_type": "ValueError",
            "traceback": "Traceback (most recent call last):\\n  ...",
            "file_path": "/app/static/user/collection/abc123.pdf",
            "plugin_name": "markitdown_ingest",
            "stage": "document_conversion",
            "context": {"page_number": 5}
        }
        ```
    """
    exception_type: Optional[str] = Field(None, description="Python exception class name")
    traceback: Optional[str] = Field(None, description="Stack trace (truncated)")
    file_path: Optional[str] = Field(None, description="File path that caused error")
    plugin_name: Optional[str] = Field(None, description="Plugin that was processing")
    stage: Optional[str] = Field(None, description="Processing stage where error occurred")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


# ═══════════════════════════════════════════════════════════════════════════════
# PROCESSING STATISTICS (Added Jan 2026)
# ═══════════════════════════════════════════════════════════════════════════════

class LLMCallDetail(BaseModel):
    """Details of a single LLM API call."""
    image: str = Field(..., description="Image filename that was processed")
    duration_ms: int = Field(..., ge=0, description="Time taken in milliseconds")
    tokens_used: Optional[int] = Field(None, description="Estimated tokens used")
    success: bool = Field(True, description="Whether the call succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")


class ChunkStats(BaseModel):
    """Statistics about chunking results."""
    count: int = Field(..., ge=0, description="Total number of chunks created")
    avg_size: float = Field(..., ge=0, description="Average chunk size in characters")
    min_size: int = Field(..., ge=0, description="Minimum chunk size")
    max_size: int = Field(..., ge=0, description="Maximum chunk size")


class StageTiming(BaseModel):
    """Timing information for a processing stage."""
    stage: str = Field(..., description="Stage name (e.g., 'conversion', 'chunking')")
    duration_ms: int = Field(..., ge=0, description="Duration in milliseconds")
    message: str = Field(..., description="Human-readable description of what happened")
    timestamp: Optional[str] = Field(None, description="ISO timestamp when stage completed")


class OutputFiles(BaseModel):
    """URLs to output files generated during processing."""
    markdown_url: Optional[str] = Field(None, description="URL to converted markdown file")
    images_folder_url: Optional[str] = Field(None, description="URL to extracted images folder")
    original_file_url: Optional[str] = Field(None, description="URL to original uploaded file")


class ProcessingStats(BaseModel):
    """
    Comprehensive statistics collected during ingestion processing.
    
    This model provides detailed information about what happened during
    document processing, useful for debugging, monitoring, and user feedback.
    
    Attributes:
        content_length: Total characters in the processed content
        images_extracted: Number of images extracted from the document
        images_with_llm_descriptions: Images that got LLM-generated descriptions
        llm_calls: Details of individual LLM API calls
        total_llm_duration_ms: Total time spent on LLM calls
        chunking_strategy: Strategy used for chunking (e.g., "by_section")
        chunk_stats: Statistics about the resulting chunks
        stage_timings: Timing breakdown for each processing stage
        output_files: URLs to generated output files
        markdown_preview: First ~2000 chars of converted markdown
    
    Example:
        ```json
        {
            "content_length": 45230,
            "images_extracted": 12,
            "images_with_llm_descriptions": 12,
            "llm_calls": [
                {"image": "image_001.png", "duration_ms": 1234, "success": true}
            ],
            "total_llm_duration_ms": 15800,
            "chunking_strategy": "by_section",
            "chunk_stats": {"count": 45, "avg_size": 1005.1, "min_size": 234, "max_size": 1499},
            "stage_timings": [
                {"stage": "conversion", "duration_ms": 2300, "message": "PDF → Markdown"}
            ],
            "output_files": {"markdown_url": "http://..."},
            "markdown_preview": "# Chapter 1\\n\\nThis document..."
        }
        ```
    """
    # Content metrics
    content_length: int = Field(0, ge=0, description="Total characters processed")
    
    # Image processing
    images_extracted: int = Field(0, ge=0, description="Number of images extracted")
    images_with_llm_descriptions: int = Field(0, ge=0, description="Images with LLM descriptions")
    llm_calls: List[LLMCallDetail] = Field(default_factory=list, description="Individual LLM call details")
    total_llm_duration_ms: int = Field(0, ge=0, description="Total LLM processing time (ms)")
    
    # Chunking
    chunking_strategy: Optional[str] = Field(None, description="Chunking strategy used")
    chunk_stats: Optional[ChunkStats] = Field(None, description="Chunk statistics")
    
    # Timing breakdown
    stage_timings: List[StageTiming] = Field(default_factory=list, description="Stage-by-stage timing")
    
    # Output artifacts
    output_files: Optional[OutputFiles] = Field(None, description="Generated output file URLs")
    
    # Preview
    markdown_preview: Optional[str] = Field(None, max_length=2500, description="Preview of markdown content")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content_length": 45230,
                "images_extracted": 12,
                "images_with_llm_descriptions": 12,
                "llm_calls": [
                    {"image": "image_001.png", "duration_ms": 1234, "tokens_used": 150, "success": True}
                ],
                "total_llm_duration_ms": 15800,
                "chunking_strategy": "by_section",
                "chunk_stats": {"count": 45, "avg_size": 1005.1, "min_size": 234, "max_size": 1499},
                "stage_timings": [
                    {"stage": "conversion", "duration_ms": 2300, "message": "PDF → Markdown", "timestamp": "2026-01-02T10:30:03Z"}
                ],
                "output_files": {
                    "markdown_url": "http://localhost:9090/static/user/kb/abc123.md",
                    "images_folder_url": "http://localhost:9090/static/user/kb/abc123/",
                    "original_file_url": "http://localhost:9090/static/user/kb/abc123.pdf"
                },
                "markdown_preview": "# Chapter 1\n\nThis document covers..."
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FILE REGISTRY RESPONSE (Basic)
# ═══════════════════════════════════════════════════════════════════════════════

class FileRegistryResponse(BaseModel):
    """
    Basic file registry entry response.
    
    This is the original/simple response model for backward compatibility.
    For detailed job tracking, use IngestionJobResponse instead.
    
    Attributes:
        id: Unique identifier (also serves as job_id)
        collection_id: ID of the parent collection
        original_filename: Original name of the uploaded file
        file_path: Server-side storage path
        file_url: Public URL to access the file
        file_size: Size in bytes
        content_type: MIME type
        plugin_name: Ingestion plugin used
        plugin_params: Parameters passed to plugin
        status: Current status
        document_count: Number of chunks created
        created_at: Creation timestamp
        updated_at: Last update timestamp
        owner: Owner identifier
    """
    id: int = Field(..., description="File registry ID (also serves as job_id)")
    collection_id: int = Field(..., description="Parent collection ID")
    original_filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Server-side storage path")
    file_url: str = Field(..., description="Public URL to access file")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    content_type: Optional[str] = Field(None, description="MIME type")
    plugin_name: str = Field(..., description="Ingestion plugin used")
    plugin_params: Dict[str, Any] = Field(default_factory=dict, description="Plugin parameters")
    status: str = Field(..., description="Current status")
    document_count: int = Field(0, ge=0, description="Number of chunks/documents created")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")
    owner: str = Field(..., description="Owner identifier")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 5,
                "collection_id": 1,
                "original_filename": "annual_report.pdf",
                "file_path": "/app/static/user@example.com/my-kb/abc123.pdf",
                "file_url": "http://localhost:9090/static/user@example.com/my-kb/abc123.pdf",
                "file_size": 2456789,
                "content_type": "application/pdf",
                "plugin_name": "markitdown_ingest",
                "plugin_params": {"chunk_size": 1000, "chunk_overlap": 200},
                "status": "completed",
                "document_count": 45,
                "created_at": "2025-12-30T10:30:00",
                "updated_at": "2025-12-30T10:32:15",
                "owner": "user@example.com"
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# INGESTION JOB RESPONSE (Detailed)
# ═══════════════════════════════════════════════════════════════════════════════

class IngestionJobResponse(BaseModel):
    """
    Detailed response for an ingestion job with full tracking information.
    
    This model provides comprehensive information about an ingestion job including:
    - File information
    - Plugin configuration
    - Status and results
    - Timing information
    - Progress tracking
    - Error details (if failed)
    
    Use this for:
    - Polling job status
    - Displaying job details in UI
    - Debugging failed jobs
    - Monitoring processing progress
    
    Attributes:
        id: Unique job identifier (same as file_registry.id)
        job_id: Alias for id (for clarity in job-tracking contexts)
        collection_id: Parent collection ID
        collection_name: Parent collection name (optional, for convenience)
        
        # File Information
        original_filename: Original name of the uploaded file
        file_path: Server-side storage path
        file_url: Public URL to access the file
        file_size: Size in bytes
        content_type: MIME type
        
        # Plugin Configuration
        plugin_name: Ingestion plugin used
        plugin_params: Parameters passed to plugin
        
        # Status & Results
        status: Current job status
        document_count: Number of chunks created (0 if not completed)
        
        # Timing
        created_at: When job was created
        updated_at: When job record was last modified
        processing_started_at: When processing actually began
        processing_completed_at: When processing finished
        processing_duration_seconds: Calculated duration
        
        # Progress
        progress: Current progress information
        
        # Error Information (only if status == "failed")
        error_message: Short error description
        error_details: Detailed error information
        
        owner: Owner identifier
    """
    # Identity
    id: int = Field(..., description="Job ID (same as file_registry.id)")
    job_id: Optional[int] = Field(None, description="Alias for id")
    collection_id: int = Field(..., description="Parent collection ID")
    collection_name: Optional[str] = Field(None, description="Parent collection name")
    
    # File Information
    original_filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Server-side storage path")
    file_url: str = Field(..., description="Public URL to access file")
    file_size: int = Field(0, ge=0, description="File size in bytes")
    content_type: Optional[str] = Field(None, description="MIME type")
    
    # Plugin Configuration
    plugin_name: str = Field(..., description="Ingestion plugin used")
    plugin_params: Dict[str, Any] = Field(default_factory=dict, description="Plugin parameters")
    
    # Status & Results
    status: IngestionStatus = Field(..., description="Current job status")
    document_count: int = Field(0, ge=0, description="Number of chunks/documents created")
    
    # Timing
    created_at: datetime = Field(..., description="Job creation time")
    updated_at: datetime = Field(..., description="Last update time")
    processing_started_at: Optional[datetime] = Field(None, description="Processing start time")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    processing_duration_seconds: Optional[float] = Field(None, ge=0, description="Processing duration in seconds")
    
    # Progress
    progress: Optional[IngestionProgress] = Field(None, description="Current progress")
    
    # Error Information
    error_message: Optional[str] = Field(None, description="Error message (if failed)")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detailed error info")
    
    # Processing Statistics (Added Jan 2026)
    processing_stats: Optional[ProcessingStats] = Field(
        None, 
        description="Detailed processing statistics (available after completion)"
    )
    
    # Ownership
    owner: str = Field(..., description="Owner identifier")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 5,
                "job_id": 5,
                "collection_id": 1,
                "collection_name": "my-knowledge-base",
                "original_filename": "annual_report.pdf",
                "file_path": "/app/static/user@example.com/my-kb/abc123.pdf",
                "file_url": "http://localhost:9090/static/user@example.com/my-kb/abc123.pdf",
                "file_size": 2456789,
                "content_type": "application/pdf",
                "plugin_name": "markitdown_plus_ingest",
                "plugin_params": {"chunk_size": 1000, "chunk_overlap": 200},
                "status": "completed",
                "document_count": 45,
                "created_at": "2026-01-02T10:30:00Z",
                "updated_at": "2026-01-02T10:32:15Z",
                "processing_started_at": "2026-01-02T10:30:01Z",
                "processing_completed_at": "2026-01-02T10:32:15Z",
                "processing_duration_seconds": 134.5,
                "progress": {
                    "current": 45,
                    "total": 45,
                    "percentage": 100.0,
                    "message": "Completed: 45 chunks from annual_report.pdf"
                },
                "error_message": None,
                "error_details": None,
                "processing_stats": {
                    "content_length": 45230,
                    "images_extracted": 12,
                    "images_with_llm_descriptions": 0,
                    "llm_calls": [],
                    "total_llm_duration_ms": 0,
                    "chunking_strategy": "by_section",
                    "chunk_stats": {"count": 45, "avg_size": 1005.1, "min_size": 234, "max_size": 1499},
                    "stage_timings": [
                        {"stage": "conversion", "duration_ms": 2300, "message": "PDF → Markdown"},
                        {"stage": "image_extraction", "duration_ms": 1200, "message": "Extracted 12 images"},
                        {"stage": "chunking", "duration_ms": 500, "message": "45 chunks (by_section)"},
                        {"stage": "embedding", "duration_ms": 3100, "message": "Added to collection"}
                    ],
                    "output_files": {
                        "markdown_url": "http://localhost:9090/static/user@example.com/my-kb/abc123.md",
                        "images_folder_url": "http://localhost:9090/static/user@example.com/my-kb/abc123/",
                        "original_file_url": "http://localhost:9090/static/user@example.com/my-kb/abc123.pdf"
                    },
                    "markdown_preview": "# Annual Report 2025\n\n## Executive Summary\n\nThis report covers..."
                },
                "owner": "user@example.com"
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# LIST RESPONSES
# ═══════════════════════════════════════════════════════════════════════════════

class IngestionJobListResponse(BaseModel):
    """
    Paginated list of ingestion jobs.
    
    Attributes:
        total: Total number of jobs matching the query
        items: List of job responses for the current page
        limit: Maximum items per page
        offset: Current offset
        has_more: Whether there are more items
    """
    total: int = Field(..., ge=0, description="Total jobs matching query")
    items: List[IngestionJobResponse] = Field(default_factory=list, description="Job list")
    limit: int = Field(50, ge=1, le=200, description="Items per page")
    offset: int = Field(0, ge=0, description="Current offset")
    has_more: bool = Field(False, description="Whether more items exist")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 25,
                "items": [],
                "limit": 50,
                "offset": 0,
                "has_more": False
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

class StatusCount(BaseModel):
    """Count of jobs by status."""
    pending: int = Field(0, ge=0)
    processing: int = Field(0, ge=0)
    completed: int = Field(0, ge=0)
    failed: int = Field(0, ge=0)
    cancelled: int = Field(0, ge=0)
    deleted: int = Field(0, ge=0)


class IngestionStatusSummary(BaseModel):
    """
    Summary of ingestion job statuses for a collection.
    
    Provides a quick overview of the ingestion state including:
    - Total job count
    - Breakdown by status
    - Currently processing jobs
    - Recent failures for quick access
    
    Useful for:
    - Dashboard displays
    - Monitoring collection health
    - Quick error detection
    
    Attributes:
        collection_id: Collection ID
        collection_name: Collection name
        total_jobs: Total number of ingestion jobs
        by_status: Count breakdown by status
        currently_processing: Number of active jobs
        recent_failures: List of recent failed jobs (up to 5)
        oldest_processing_job: Oldest job still processing (may indicate stuck job)
    """
    collection_id: int = Field(..., description="Collection ID")
    collection_name: Optional[str] = Field(None, description="Collection name")
    total_jobs: int = Field(0, ge=0, description="Total ingestion jobs")
    by_status: StatusCount = Field(default_factory=StatusCount, description="Count by status")
    currently_processing: int = Field(0, ge=0, description="Jobs currently processing")
    recent_failures: List[IngestionJobResponse] = Field(
        default_factory=list, 
        description="Recent failed jobs (up to 5)"
    )
    oldest_processing_job: Optional[IngestionJobResponse] = Field(
        None,
        description="Oldest job still processing (may indicate stuck job)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "collection_id": 1,
                "collection_name": "my-knowledge-base",
                "total_jobs": 25,
                "by_status": {
                    "pending": 0,
                    "processing": 2,
                    "completed": 21,
                    "failed": 2,
                    "cancelled": 0,
                    "deleted": 0
                },
                "currently_processing": 2,
                "recent_failures": [],
                "oldest_processing_job": None
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# RETRY REQUEST
# ═══════════════════════════════════════════════════════════════════════════════

class RetryIngestionRequest(BaseModel):
    """
    Request to retry a failed ingestion job.
    
    Optionally allows overriding the original plugin parameters.
    
    Attributes:
        override_params: New plugin parameters to use (optional)
                        If not provided, uses original parameters
    """
    override_params: Optional[Dict[str, Any]] = Field(
        None, 
        description="Optional new plugin parameters (uses original if not provided)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "override_params": {
                    "chunk_size": 500,
                    "chunk_overlap": 100
                }
            }
        }
