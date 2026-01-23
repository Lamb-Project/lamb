"""
Database models for the Lamb Knowledge Base Server.

This module defines SQLAlchemy models for the application's database schema.
"""

import datetime
import json
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Enum as SQLAlchemyEnum, UniqueConstraint, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Visibility(str, Enum):
    """Enum for collection visibility states."""
    PRIVATE = "private"
    PUBLIC = "public"


class FileStatus(str, Enum):
    """Enum for file/ingestion job status states.
    
    Status Flow:
        PENDING -> PROCESSING -> COMPLETED
                             -> FAILED
                             -> CANCELLED
        
        Any status can transition to DELETED (soft delete)
    """
    PENDING = "pending"        # Job created but not yet started
    PROCESSING = "processing"  # Job is currently running
    COMPLETED = "completed"    # Job finished successfully
    FAILED = "failed"          # Job failed with error
    CANCELLED = "cancelled"    # Job was cancelled by user
    DELETED = "deleted"        # Soft-deleted (file may still exist)


class Collection(Base):
    """Model representing a knowledge base collection.
    
    Each collection has an associated ChromaDB collection.
    """
    __tablename__ = "collections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    creation_date = Column(DateTime, default=datetime.datetime.utcnow)
    owner = Column(String(255), nullable=False, index=True)
    visibility = Column(SQLAlchemyEnum(Visibility), default=Visibility.PRIVATE, nullable=False)
    embeddings_model = Column(JSON, nullable=False, 
                              default=lambda: json.dumps({
                                  "model": "sentence-transformers/all-MiniLM-L6-v2",
                                  "endpoint": None,
                                  "apikey": None
                              }))
    chromadb_uuid = Column(String(36), nullable=True, unique=True, index=True)
    
    __table_args__ = (
        UniqueConstraint('name', 'owner', name='uix_collection_name_owner'),
    )
    
    def __repr__(self):
        return f"<Collection id={self.id}, name={self.name}, owner={self.owner}>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "creation_date": self.creation_date.isoformat() if self.creation_date else None,
            "owner": self.owner,
            "visibility": self.visibility.value,
            "embeddings_model": json.loads(self.embeddings_model) if isinstance(self.embeddings_model, str) else self.embeddings_model,
            "chromadb_uuid": self.chromadb_uuid
        }


class FileRegistry(Base):
    """Model representing files/ingestion jobs in collections.
    
    This tracks each file added to a collection, along with the ingestion parameters,
    status, progress, timing, and error information.
    
    Serves as both a file registry and an ingestion job tracker.
    The `id` field can be used as a `job_id` for tracking ingestion progress.
    
    Attributes:
        id: Primary key, also serves as job_id for ingestion tracking
        collection_id: Foreign key to the parent collection
        original_filename: Original name of the uploaded file
        file_path: Server-side path to the stored file
        file_url: Public URL to access the file
        file_size: Size of the file in bytes
        content_type: MIME type of the file
        plugin_name: Name of the ingestion plugin used
        plugin_params: JSON parameters passed to the plugin
        status: Current status of the ingestion job
        document_count: Number of chunks/documents created from this file
        
        # Timing fields
        created_at: When the job was created
        updated_at: When the job record was last modified
        processing_started_at: When processing actually began
        processing_completed_at: When processing finished (success or failure)
        
        # Progress tracking
        progress_current: Current progress value (e.g., chunks processed)
        progress_total: Total expected value (e.g., total chunks)
        progress_message: Human-readable status message
        
        # Error tracking
        error_message: Short error message (max 500 chars)
        error_details: JSON with detailed error info (traceback, context)
        
        owner: Owner identifier for the file
    """
    __tablename__ = "file_registry"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIMARY FIELDS
    # ═══════════════════════════════════════════════════════════════════════════
    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FILE INFORMATION
    # ═══════════════════════════════════════════════════════════════════════════
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_url = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    content_type = Column(String(100), nullable=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PLUGIN CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════════
    plugin_name = Column(String(100), nullable=False)
    plugin_params = Column(JSON, nullable=False, default=dict)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS & RESULTS
    # ═══════════════════════════════════════════════════════════════════════════
    status = Column(SQLAlchemyEnum(FileStatus), default=FileStatus.PENDING, nullable=False, index=True)
    document_count = Column(Integer, default=0, nullable=False)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TIMING FIELDS
    # ═══════════════════════════════════════════════════════════════════════════
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PROGRESS TRACKING
    # ═══════════════════════════════════════════════════════════════════════════
    progress_current = Column(Integer, default=0, nullable=False)
    progress_total = Column(Integer, default=0, nullable=False)
    progress_message = Column(String(255), nullable=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ERROR TRACKING
    # ═══════════════════════════════════════════════════════════════════════════
    error_message = Column(Text, nullable=True)  # Short error message
    error_details = Column(JSON, nullable=True)  # Detailed error info (traceback, context)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PROCESSING STATISTICS (Added Jan 2026)
    # Detailed statistics collected during ingestion processing
    # ═══════════════════════════════════════════════════════════════════════════
    processing_stats = Column(JSON, nullable=True, default=None)
    # Schema for processing_stats:
    # {
    #     "content_length": int,           # Total characters processed
    #     "images_extracted": int,         # Number of images extracted
    #     "images_with_llm_descriptions": int,  # Images processed by LLM
    #     "llm_calls": [                   # Individual LLM call tracking
    #         {"image": "image_001.png", "duration_ms": 1234, "tokens_used": 150},
    #         ...
    #     ],
    #     "total_llm_duration_ms": int,    # Total time spent on LLM calls
    #     "chunking_strategy": str,        # e.g., "by_section", "standard"
    #     "chunk_stats": {
    #         "count": int,
    #         "avg_size": float,
    #         "min_size": int,
    #         "max_size": int
    #     },
    #     "stage_timings": [               # Timing for each processing stage
    #         {"stage": "conversion", "duration_ms": 2300, "message": "PDF → Markdown"},
    #         {"stage": "image_extraction", "duration_ms": 1200, "message": "Extracted 12 images"},
    #         {"stage": "llm_descriptions", "duration_ms": 15800, "message": "12 LLM calls"},
    #         {"stage": "chunking", "duration_ms": 500, "message": "45 chunks created"},
    #         {"stage": "embedding", "duration_ms": 3100, "message": "Added to collection"}
    #     ],
    #     "output_files": {
    #         "markdown_url": str,         # URL to converted .md file
    #         "images_folder_url": str,    # URL to images folder
    #         "original_file_url": str     # URL to original file
    #     },
    #     "markdown_preview": str          # First ~2000 chars of markdown content
    # }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OWNERSHIP
    # ═══════════════════════════════════════════════════════════════════════════
    owner = Column(String(255), nullable=False, index=True)
    
    def __repr__(self):
        return f"<FileRegistry id={self.id}, collection_id={self.collection_id}, filename={self.original_filename}, status={self.status.value}>"
    
    @property
    def processing_duration_seconds(self) -> Optional[float]:
        """Calculate processing duration in seconds."""
        if self.processing_started_at and self.processing_completed_at:
            delta = self.processing_completed_at - self.processing_started_at
            return delta.total_seconds()
        return None
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage (0-100)."""
        if self.progress_total > 0:
            return round((self.progress_current / self.progress_total) * 100, 2)
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary."""
        # Parse processing_stats if it's a string
        processing_stats = self.processing_stats
        if isinstance(processing_stats, str):
            try:
                processing_stats = json.loads(processing_stats)
            except:
                processing_stats = None
        
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "file_url": self.file_url,
            "file_size": self.file_size,
            "content_type": self.content_type,
            "plugin_name": self.plugin_name,
            "plugin_params": json.loads(self.plugin_params) if isinstance(self.plugin_params, str) else self.plugin_params,
            "status": self.status.value,
            "document_count": self.document_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processing_started_at": self.processing_started_at.isoformat() if self.processing_started_at else None,
            "processing_completed_at": self.processing_completed_at.isoformat() if self.processing_completed_at else None,
            "processing_duration_seconds": self.processing_duration_seconds,
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "progress_percentage": self.progress_percentage,
            "progress_message": self.progress_message,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "processing_stats": processing_stats,
            "owner": self.owner
        }
    
    def to_job_dict(self) -> Dict[str, Any]:
        """Convert to ingestion job response format."""
        base = self.to_dict()
        base["job_id"] = self.id  # Alias for clarity
        base["progress"] = {
            "current": self.progress_current,
            "total": self.progress_total,
            "percentage": self.progress_percentage,
            "message": self.progress_message
        }
        # processing_stats is already included from to_dict()
        return base
