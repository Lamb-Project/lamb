"""
MarkItDown Plus ingestion plugin for various file formats.

This is an enhanced version of markitdown_ingest that provides:
- LLM-powered image descriptions using OpenAI vision models (optional)
- Image extraction and storage with proper URL references
- Multiple chunking strategies (standard, by_page, by_section, hierarchical)
- Hierarchical parent-child chunking with document outline support
- Cleaner output (single .md file)
- Detailed progress reporting
- Comprehensive processing statistics

Version: 1.3.0

PRIVACY NOTICE:
This plugin processes documents LOCALLY by default. External API calls to OpenAI 
only occur when `image_descriptions` is set to `"llm"`. The MarkItDown library
itself does not call external APIs unless explicitly configured.
"""

import os
import re
import json
import uuid
import base64
import shutil
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from urllib.parse import urlparse, urlunparse

# Import LangChain text splitters
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    TokenTextSplitter
)
from markitdown import MarkItDown
from .base import IngestPlugin, PluginRegistry

# Configure logging
logger = logging.getLogger(__name__)

# Try to import pymupdf for PDF image extraction
try:
    import fitz  # pymupdf
    PYMUPDF_AVAILABLE = True
    logger.info("[markitdown_plus] pymupdf available for PDF image extraction")
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("[markitdown_plus] pymupdf not available - PDF images will not be extracted")

# URL prefix for static files
STATIC_URL_PREFIX = os.getenv("HOME_URL", "http://localhost:9090") + "/static"


class ProcessingStatsTracker:
    """Helper class to track detailed processing statistics during ingestion.
    
    This collects timing, LLM call details, chunk statistics, and output file
    information during document processing.
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.content_length = 0
        self.images_extracted = 0
        self.images_with_llm_descriptions = 0
        self.llm_calls: List[Dict[str, Any]] = []
        self.total_llm_duration_ms = 0
        self.chunking_strategy: Optional[str] = None
        self.chunk_stats: Optional[Dict[str, Any]] = None
        self.stage_timings: List[Dict[str, Any]] = []
        self.output_files: Dict[str, Optional[str]] = {
            "markdown_url": None,
            "images_folder_url": None,
            "original_file_url": None
        }
        self.markdown_preview: Optional[str] = None
        self._stage_start: Optional[float] = None
        self._current_stage: Optional[str] = None
    
    def start_stage(self, stage_name: str):
        """Start timing a processing stage."""
        self._stage_start = time.time()
        self._current_stage = stage_name
    
    def end_stage(self, message: str):
        """End the current stage and record its timing."""
        if self._stage_start and self._current_stage:
            duration_ms = int((time.time() - self._stage_start) * 1000)
            self.stage_timings.append({
                "stage": self._current_stage,
                "duration_ms": duration_ms,
                "message": message,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
            self._stage_start = None
            self._current_stage = None
            return duration_ms
        return 0
    
    def record_llm_call(self, image: str, duration_ms: int, success: bool = True, 
                        error: Optional[str] = None, tokens_used: Optional[int] = None):
        """Record details of an LLM API call for image description."""
        call_detail = {
            "image": image,
            "duration_ms": duration_ms,
            "success": success
        }
        if tokens_used:
            call_detail["tokens_used"] = tokens_used
        if error:
            call_detail["error"] = error
        
        self.llm_calls.append(call_detail)
        self.total_llm_duration_ms += duration_ms
        if success:
            self.images_with_llm_descriptions += 1
    
    def calculate_chunk_stats(self, chunks: List[str]):
        """Calculate statistics about the chunks."""
        if not chunks:
            self.chunk_stats = {
                "count": 0,
                "avg_size": 0.0,
                "min_size": 0,
                "max_size": 0
            }
            return
        
        sizes = [len(c) for c in chunks]
        self.chunk_stats = {
            "count": len(chunks),
            "avg_size": round(sum(sizes) / len(sizes), 1),
            "min_size": min(sizes),
            "max_size": max(sizes)
        }
    
    def set_markdown_preview(self, content: str, max_length: int = 2000):
        """Set the markdown preview (truncated to max_length)."""
        if content:
            self.markdown_preview = content[:max_length]
            if len(content) > max_length:
                self.markdown_preview += "\n\n... [truncated]"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary format for storage."""
        return {
            "content_length": self.content_length,
            "images_extracted": self.images_extracted,
            "images_with_llm_descriptions": self.images_with_llm_descriptions,
            "llm_calls": self.llm_calls,
            "total_llm_duration_ms": self.total_llm_duration_ms,
            "chunking_strategy": self.chunking_strategy,
            "chunk_stats": self.chunk_stats,
            "stage_timings": self.stage_timings,
            "output_files": self.output_files,
            "markdown_preview": self.markdown_preview
        }


@PluginRegistry.register
class MarkItDownPlusPlugin(IngestPlugin):
    """Enhanced plugin for ingesting files with optional LLM image descriptions and multiple chunking strategies.
    
    Key features:
    - LLM-powered image descriptions (optional, requires OpenAI API key)
    - Image extraction and storage with accessible URLs
    - Multiple chunking modes: standard, by_page, by_section, hierarchical
    - Hierarchical parent-child chunking with document outline support
    - Single .md output file
    - Detailed progress reporting
    
    PRIVACY NOTICE:
    This plugin processes documents LOCALLY by default. External API calls only occur 
    when `image_descriptions="llm"` is enabled. Do NOT use "llm" mode for sensitive documents.
    """
    
    name = "markitdown_plus_ingest"
    kind = "file-ingest"
    description = "Enhanced file ingestion with optional LLM image descriptions and multiple chunking strategies"
    supports_progress = True
    
    # Privacy notice (accurate and specific)
    privacy_notice = (
        "ℹ️ PRIVACY: This plugin processes documents locally by default. "
        "External API calls to OpenAI only occur when image_descriptions is set to 'llm'. "
        "Use 'none' or 'basic' modes for sensitive/confidential documents."
    )

    supported_file_types = {
        "pdf", "pptx", "docx", "xlsx", "xls", "mp3", "wav", 
        "html", "csv", "json", "xml", "zip", "epub"
    }
    
    # File types that support page-based chunking
    PAGE_AWARE_TYPES = {"pdf", "docx", "pptx"}
    
    # Patterns for detecting page/slide markers in MarkItDown output
    PAGE_PATTERNS = [
        r'<!-- Page (\d+) -->',
        r'<!-- Slide (\d+) -->',
        r'<!-- Page Break -->',
        r'\[Page (\d+)\]',
    ]
    
    # Patterns for finding images in markdown
    BASE64_IMAGE_PATTERN = r'!\[([^\]]*)\]\(data:image/([^;]+);base64,([^)]+)\)'
    IMAGE_REF_PATTERN = r'!\[([^\]]*)\]\(([^)]+)\)'
    
    # Supported image extensions
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Get the parameters accepted by this plugin with UI metadata.
        
        Returns:
            A dictionary mapping parameter names to their specifications
        """
        return {
            # === PRIVACY NOTICE ===
            "_privacy_notice": {
                "type": "info",
                "description": self.privacy_notice,
                "required": False,
                "ui_hint": "info"
            },
            
            # === IMAGE HANDLING ===
            "image_descriptions": {
                "type": "string",
                "description": "How to handle images in the document",
                "enum": ["none", "basic", "llm"],
                "enum_labels": {
                    "none": "Keep image links only (fastest, no extraction)",
                    "basic": "Extract images with filename-based descriptions (local)",
                    "llm": "Generate AI descriptions (⚠️ sends images to OpenAI)"
                },
                "default": "none",
                "required": False,
                "ui_hint": "select",
                "help_text": "Only 'llm' mode sends data externally. Use 'none' or 'basic' for sensitive documents."
            },
            
            # === CHUNKING MODE ===
            "chunking_mode": {
                "type": "string",
                "description": "Strategy for splitting document into chunks",
                "enum": ["standard", "by_page", "by_section", "hierarchical"],
                "enum_labels": {
                    "standard": "Standard (character-based splitting)",
                    "by_page": "By page (PDF, DOCX, PPTX only)",
                    "by_section": "By section (split on headings)",
                    "hierarchical": "Hierarchical (parent-child with outline)"
                },
                "default": "standard",
                "required": False,
                "ui_hint": "select",
                "help_text": "Each mode has its own specific parameters below."
            },
            
            # ══════════════════════════════════════════════════════════════════
            # STANDARD MODE PARAMETERS
            # ══════════════════════════════════════════════════════════════════
            "chunk_size": {
                "type": "integer",
                "description": "Target size for each chunk (characters)",
                "default": 1000,
                "min": 100,
                "max": 10000,
                "required": False,
                "visible_when": {"chunking_mode": ["standard"]},
                "ui_hint": "slider",
                "help_text": "Larger chunks preserve more context but may exceed LLM token limits."
            },
            "chunk_overlap": {
                "type": "integer",
                "description": "Overlap between consecutive chunks (characters)",
                "default": 200,
                "min": 0,
                "max": 500,
                "required": False,
                "visible_when": {"chunking_mode": ["standard"]},
                "ui_hint": "slider",
                "help_text": "Overlap helps maintain context across chunk boundaries."
            },
            "splitter_type": {
                "type": "string",
                "description": "Text splitting algorithm",
                "enum": ["RecursiveCharacterTextSplitter", "CharacterTextSplitter", "TokenTextSplitter"],
                "default": "RecursiveCharacterTextSplitter",
                "required": False,
                "visible_when": {"chunking_mode": ["standard"]},
                "ui_hint": "select"
            },
            
            # ══════════════════════════════════════════════════════════════════
            # PAGE MODE PARAMETERS
            # ══════════════════════════════════════════════════════════════════
            "pages_per_chunk": {
                "type": "integer",
                "description": "Number of pages to include in each chunk",
                "default": 1,
                "min": 1,
                "max": 10,
                "required": False,
                "visible_when": {"chunking_mode": ["by_page"]},
                "applicable_to": ["pdf", "docx", "pptx"],
                "ui_hint": "number",
                "help_text": "1 = one page per chunk. Increase for shorter pages."
            },
            
            # ══════════════════════════════════════════════════════════════════
            # SECTION MODE PARAMETERS
            # ══════════════════════════════════════════════════════════════════
            "split_on_heading": {
                "type": "integer",
                "description": "Heading level that defines chunk boundaries",
                "default": 2,
                "min": 1,
                "max": 6,
                "required": False,
                "visible_when": {"chunking_mode": ["by_section"]},
                "ui_hint": "number",
                "help_text": "1=H1 (# chapters), 2=H2 (## sections), 3=H3 (### subsections). Parent headings are preserved as context."
            },
            "headings_per_chunk": {
                "type": "integer",
                "description": "Number of sections at the chosen level per chunk",
                "default": 1,
                "min": 1,
                "max": 10,
                "required": False,
                "visible_when": {"chunking_mode": ["by_section"]},
                "ui_hint": "number",
                "help_text": "1 = one section per chunk. Sections from different parents are never mixed."
            },
            
            # ══════════════════════════════════════════════════════════════════
            # HIERARCHICAL MODE PARAMETERS
            # ══════════════════════════════════════════════════════════════════
            "parent_chunk_size": {
                "type": "integer",
                "description": "Size of parent chunks (larger context)",
                "default": 2000,
                "min": 500,
                "max": 8000,
                "required": False,
                "visible_when": {"chunking_mode": ["hierarchical"]},
                "ui_hint": "slider",
                "help_text": "Parent chunks provide broader context for RAG queries."
            },
            "child_chunk_size": {
                "type": "integer",
                "description": "Size of child chunks (used for embedding/search)",
                "default": 400,
                "min": 100,
                "max": 2000,
                "required": False,
                "visible_when": {"chunking_mode": ["hierarchical"]},
                "ui_hint": "slider",
                "help_text": "Child chunks are embedded and used for semantic search."
            },
            "child_chunk_overlap": {
                "type": "integer",
                "description": "Overlap between child chunks",
                "default": 50,
                "min": 0,
                "max": 200,
                "required": False,
                "visible_when": {"chunking_mode": ["hierarchical"]},
                "ui_hint": "slider",
                "help_text": "Overlap helps maintain context across chunk boundaries."
            },
            "split_by_headers": {
                "type": "boolean",
                "description": "Split parent chunks by markdown headers",
                "default": True,
                "required": False,
                "visible_when": {"chunking_mode": ["hierarchical"]},
                "ui_hint": "checkbox",
                "help_text": "When enabled, parent chunks align with document structure."
            },
            "include_outline": {
                "type": "boolean",
                "description": "Append a document outline (TOC) at the end",
                "default": False,
                "required": False,
                "visible_when": {"chunking_mode": ["hierarchical"]},
                "ui_hint": "checkbox",
                "help_text": "Adds a hierarchical table of contents to improve structural queries."
            },
            
            # ══════════════════════════════════════════════════════════════════
            # METADATA
            # ══════════════════════════════════════════════════════════════════
            "description": {
                "type": "long-string",
                "description": "Optional description for the ingested content",
                "required": False,
                "ui_hint": "textarea"
            },
            "citation": {
                "type": "long-string",
                "description": "Optional citation/source reference",
                "required": False,
                "ui_hint": "textarea"
            }
        }
    
    def _validate_params(self, file_extension: str, **kwargs) -> Tuple[Dict[str, Any], List[str]]:
        """Validate parameters and warn about incompatibilities."""
        warnings = []
        params = dict(kwargs)
        
        chunking_mode = params.get('chunking_mode', 'standard')
        
        # Check page-based chunking compatibility
        if chunking_mode == 'by_page' and file_extension.lower() not in self.PAGE_AWARE_TYPES:
            warnings.append(
                f"Page-based chunking not available for .{file_extension} files. "
                f"Falling back to standard chunking."
            )
            params['chunking_mode'] = 'standard'
        
        return params, warnings
    
    def _get_openai_client(self, api_key: str) -> Optional[Any]:
        """Create an OpenAI client if available."""
        if not api_key:
            return None
        
        try:
            from openai import OpenAI
            return OpenAI(api_key=api_key)
        except ImportError:
            logger.warning("OpenAI package not installed, LLM image descriptions unavailable")
            return None
        except Exception as e:
            logger.warning(f"Failed to create OpenAI client: {e}")
            return None
    
    def _get_image_extension(self, img_format: str) -> str:
        """Normalize image format to file extension."""
        format_map = {'jpeg': 'jpg', 'svg+xml': 'svg'}
        return format_map.get(img_format.lower(), img_format.lower())
    
    def _create_images_directory(self, file_path: Path, owner: str, collection_name: str) -> Tuple[Path, str]:
        """Create the images directory for a file."""
        base_name = file_path.stem
        images_dir = file_path.parent / base_name
        images_dir.mkdir(exist_ok=True)
        images_url_prefix = f"{STATIC_URL_PREFIX}/{owner}/{collection_name}/{base_name}"
        logger.info(f"[markitdown_plus] Created images directory: {images_dir}")
        return images_dir, images_url_prefix
    
    def _extract_pdf_with_images(self, file_path: Path, owner: str, collection_name: str,
                                  image_mode: str = "basic",
                                  openai_client: Optional[Any] = None,
                                  stats_tracker: Optional['ProcessingStatsTracker'] = None,
                                  kwargs: Optional[Dict] = None,
                                  stats_callback: Optional[Callable] = None) -> Tuple[str, int]:
        """Extract text and images from PDF using pymupdf.
        
        This method extracts both text and images from each page of a PDF,
        inserting image references at the end of each page's content.
        
        Args:
            file_path: Path to the PDF file
            owner: Collection owner for image storage path
            collection_name: Collection name for image storage path
            image_mode: "none", "basic", or "llm"
            openai_client: OpenAI client for LLM descriptions
            stats_tracker: Optional tracker for recording statistics
            kwargs: Original kwargs for progress reporting
            
        Returns:
            Tuple of (markdown content with images, total image count)
        """
        kwargs = kwargs or {}
        
        if not PYMUPDF_AVAILABLE:
            logger.warning("[markitdown_plus] pymupdf not available, falling back to markitdown")
            self.report_progress(kwargs, 1, 5, "⚠️ pymupdf not available - no image extraction")
            return None, 0
        
        try:
            doc = fitz.open(str(file_path))
        except Exception as e:
            logger.error(f"[markitdown_plus] Failed to open PDF with pymupdf: {e}")
            self.report_progress(kwargs, 1, 5, f"⚠️ Failed to open PDF: {str(e)[:50]}")
            return None, 0
        
        num_pages = len(doc)
        logger.info(f"[markitdown_plus] 🔍 PYMUPDF: Opening PDF with {num_pages} pages")
        print(f"INFO: [markitdown_plus] 🔍 PYMUPDF ACTIVE: Extracting from {num_pages} pages, image_mode={image_mode}")
        self.report_progress(kwargs, 1, 5, f"📄 Using pymupdf for {num_pages}-page PDF (image_mode: {image_mode})")
        
        # Create images directory
        images_dir, images_url_prefix = self._create_images_directory(file_path, owner, collection_name)
        logger.info(f"[markitdown_plus] 📁 Images directory: {images_dir}")
        
        markdown_parts = []
        total_images = 0
        llm_calls_made = 0
        
        for page_num in range(num_pages):
            page = doc[page_num]
            
            # Add page marker
            markdown_parts.append(f"\n<!-- Page {page_num + 1} -->\n")
            
            # Extract text from page
            page_text = page.get_text("text")
            if page_text.strip():
                markdown_parts.append(page_text.strip())
            
            # Extract images from page (only if not "none" mode)
            if image_mode != "none":
                image_list = page.get_images(full=True)
                page_images = []
                
                if image_list:
                    logger.info(f"[markitdown_plus] Page {page_num + 1}: found {len(image_list)} images")
                
                for img_index, img_info in enumerate(image_list):
                    xref = img_info[0]  # Image reference number
                    
                    try:
                        # Extract image
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # Skip very small images (likely icons/decorations)
                        if len(image_bytes) < 1000:
                            logger.debug(f"[markitdown_plus] Skipping small image ({len(image_bytes)} bytes)")
                            continue
                        
                        total_images += 1
                        img_filename = f"page{page_num + 1}_img{img_index + 1}.{image_ext}"
                        img_path = images_dir / img_filename
                        
                        # Save image to disk
                        with open(img_path, "wb") as f:
                            f.write(image_bytes)
                        
                        logger.info(f"[markitdown_plus] ✅ Saved image: {img_filename} ({len(image_bytes):,} bytes)")
                        print(f"INFO: [markitdown_plus] ✅ Extracted image #{total_images}: {img_filename}")
                        
                        # Record image extraction in stats
                        if stats_tracker:
                            stats_tracker.stage_timings.append({
                                "stage": "image_extracted",
                                "duration_ms": 0,
                                "message": f"📷 Image #{total_images}: {img_filename} ({len(image_bytes):,} bytes)",
                                "timestamp": datetime.utcnow().isoformat() + "Z"
                            })
                            stats_tracker.images_extracted = total_images
                            # Report to UI every 10 images
                            if total_images % 10 == 0:
                                if stats_callback and callable(stats_callback):
                                    try:
                                        stats_callback(stats_tracker.to_dict())
                                    except:
                                        pass
                        
                        # Generate description
                        if image_mode == "llm" and openai_client:
                            self.report_progress(kwargs, 1, 5, f"🤖 LLM describing image {total_images}: {img_filename}")
                            llm_calls_made += 1
                        
                        description = self._generate_image_description(
                            img_path, 
                            f"Image from page {page_num + 1}",
                            openai_client, 
                            image_mode,
                            stats_tracker
                        )
                        
                        img_url = f"{images_url_prefix}/{img_filename}"
                        page_images.append(f"![{description}]({img_url})")
                        
                    except Exception as e:
                        logger.warning(f"[markitdown_plus] Failed to extract image {xref} from page {page_num + 1}: {e}")
                        continue
                
                # Add images at end of page content
                if page_images:
                    markdown_parts.append("\n\n**Images from this page:**\n")
                    for img_ref in page_images:
                        markdown_parts.append(f"\n{img_ref}\n")
            
            # Record page processing in stats (every page)
            if stats_tracker and image_mode != "none":
                page_img_count = len(page_images) if 'page_images' in dir() else 0
                if page_img_count > 0:
                    stats_tracker.stage_timings.append({
                        "stage": "page_processed",
                        "duration_ms": 0,
                        "message": f"📄 Page {page_num + 1}/{num_pages}: {page_img_count} images extracted",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })
            
            # Report progress every 10 pages (to progress callback)
            if (page_num + 1) % 10 == 0:
                self.report_progress(kwargs, 1, 5, f"📖 Processed {page_num + 1}/{num_pages} pages, {total_images} images...")
        
        doc.close()
        
        # Final progress report
        summary = f"📊 PDF extracted: {num_pages} pages, {total_images} images"
        if llm_calls_made > 0:
            summary += f", {llm_calls_made} LLM calls"
        logger.info(f"[markitdown_plus] {summary}")
        print(f"INFO: [markitdown_plus] {summary}")
        self.report_progress(kwargs, 1, 5, summary)
        
        # Update stats tracker
        if stats_tracker:
            stats_tracker.images_extracted = total_images
        
        markdown_content = "\n".join(markdown_parts)
        logger.info(f"[markitdown_plus] PDF extraction complete: {len(markdown_content)} chars, {total_images} images")
        
        return markdown_content, total_images
    
    def _generate_image_description(self, image_path: Path, alt_text: str, 
                                     openai_client: Optional[Any] = None,
                                     mode: str = "basic",
                                     stats_tracker: Optional[ProcessingStatsTracker] = None) -> str:
        """Generate a description for an image.
        
        Args:
            image_path: Path to the image file
            alt_text: Original alt text from the document
            openai_client: OpenAI client for LLM descriptions
            mode: "none", "basic", or "llm"
            stats_tracker: Optional tracker for recording LLM call statistics
            
        Returns:
            Description string for the image
        """
        # Use existing alt text if meaningful
        if alt_text and alt_text.strip() and len(alt_text.strip()) > 3:
            if mode == "basic":
                return alt_text.strip()
        
        # Basic mode: generate from filename
        if mode == "basic" or not openai_client:
            filename = image_path.stem
            clean_name = re.sub(r'^[a-f0-9]{8,}_?', '', filename)
            clean_name = re.sub(r'[_-]+', ' ', clean_name).strip()
            
            if clean_name:
                return f"Image: {clean_name}"
            elif alt_text:
                return alt_text
            return "Image from document"
        
        # LLM mode: use OpenAI Vision
        if mode == "llm" and openai_client:
            start_time = time.time()
            img_filename = image_path.name
            
            try:
                with open(image_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                ext = image_path.suffix.lower()
                media_types = {
                    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif', '.webp': 'image/webp',
                }
                media_type = media_types.get(ext, 'image/png')
                
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image in one concise sentence. Be factual and descriptive."},
                            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_data}", "detail": "low"}}
                        ]
                    }],
                    max_tokens=100
                )
                
                description = response.choices[0].message.content.strip()
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Record LLM call in stats tracker
                if stats_tracker:
                    # Try to get token usage from response
                    tokens_used = None
                    if hasattr(response, 'usage') and response.usage:
                        tokens_used = response.usage.total_tokens
                    stats_tracker.record_llm_call(
                        image=img_filename,
                        duration_ms=duration_ms,
                        success=True,
                        tokens_used=tokens_used
                    )
                
                logger.info(f"[markitdown_plus] LLM description ({duration_ms}ms): {description[:50]}...")
                return description
                
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Record failed LLM call
                if stats_tracker:
                    stats_tracker.record_llm_call(
                        image=img_filename,
                        duration_ms=duration_ms,
                        success=False,
                        error=str(e)[:100]
                    )
                
                logger.warning(f"[markitdown_plus] LLM description failed: {e}")
                return self._generate_image_description(image_path, alt_text, None, "basic", stats_tracker)
        
        return alt_text or "Image from document"
    
    def _extract_and_process_images(self, content: str, file_path: Path, 
                                     owner: str, collection_name: str,
                                     mode: str = "none",
                                     openai_client: Optional[Any] = None,
                                     stats_tracker: Optional[ProcessingStatsTracker] = None) -> Tuple[str, int, str]:
        """Extract images from markdown content and save them to disk.
        
        Args:
            content: Markdown content with embedded images
            file_path: Path to the original file
            owner: Collection owner for path building
            collection_name: Collection name for path building
            mode: "none", "basic", or "llm"
            openai_client: OpenAI client for LLM descriptions
            stats_tracker: Optional tracker for recording statistics
            
        Returns:
            Tuple of (updated content, image count, images folder URL)
        """
        if mode == "none":
            return content, 0, ""
        
        images_dir, images_url_prefix = self._create_images_directory(file_path, owner, collection_name)
        image_count = 0
        
        def replace_base64_image(match):
            nonlocal image_count
            alt_text, img_format, img_data = match.group(1), match.group(2), match.group(3)
            
            try:
                image_count += 1
                ext = self._get_image_extension(img_format)
                img_filename = f"image_{image_count:03d}.{ext}"
                img_path = images_dir / img_filename
                
                decoded_data = base64.b64decode(img_data)
                with open(img_path, 'wb') as f:
                    f.write(decoded_data)
                
                logger.info(f"[markitdown_plus] Saved image: {img_path} ({len(decoded_data)} bytes)")
                
                description = self._generate_image_description(
                    img_path, alt_text, openai_client, mode, stats_tracker
                )
                img_url = f"{images_url_prefix}/{img_filename}"
                
                return f"![{description}]({img_url})"
            except Exception as e:
                logger.warning(f"[markitdown_plus] Failed to save image: {e}")
                return match.group(0)
        
        content = re.sub(self.BASE64_IMAGE_PATTERN, replace_base64_image, content)
        
        def replace_image_ref(match):
            nonlocal image_count
            alt_text, img_src = match.group(1), match.group(2)
            
            if img_src.startswith(('http://', 'https://', 'data:')):
                return match.group(0)
            
            src_path = Path(img_src)
            if src_path.suffix.lower() not in self.IMAGE_EXTENSIONS:
                return match.group(0)
            
            try:
                original_dir = file_path.parent
                source_path = None
                for p in [original_dir / img_src, original_dir / src_path.name, Path(img_src)]:
                    if p.exists():
                        source_path = p
                        break
                
                if source_path is None:
                    return match.group(0)
                
                image_count += 1
                ext = source_path.suffix.lower().lstrip('.')
                img_filename = f"image_{image_count:03d}.{ext}"
                img_path = images_dir / img_filename
                
                shutil.copy2(source_path, img_path)
                
                description = self._generate_image_description(
                    img_path, alt_text, openai_client, mode, stats_tracker
                )
                img_url = f"{images_url_prefix}/{img_filename}"
                
                return f"![{description}]({img_url})"
            except Exception as e:
                logger.warning(f"[markitdown_plus] Failed to process image {img_src}: {e}")
                return match.group(0)
        
        simple_image_pattern = r'!\[([^\]]*)\]\((?!data:)([^)]+)\)'
        content = re.sub(simple_image_pattern, replace_image_ref, content)
        
        logger.info(f"[markitdown_plus] Extracted {image_count} images")
        return content, image_count, images_url_prefix
    
    def _chunk_standard(self, content: str, **kwargs) -> List[str]:
        """Apply standard LangChain text splitting."""
        chunk_size = kwargs.get("chunk_size", 1000)
        chunk_overlap = kwargs.get("chunk_overlap", 200)
        splitter_type = kwargs.get("splitter_type", "RecursiveCharacterTextSplitter")
        
        splitter_params = {"chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
        
        if splitter_type == "CharacterTextSplitter":
            text_splitter = CharacterTextSplitter(**splitter_params)
        elif splitter_type == "TokenTextSplitter":
            text_splitter = TokenTextSplitter(**splitter_params)
        else:
            text_splitter = RecursiveCharacterTextSplitter(**splitter_params)
        
        return text_splitter.split_text(content)
    
    def _chunk_by_page(self, content: str, pages_per_chunk: int = 1) -> Tuple[List[str], List[Dict], bool]:
        """Split content by page markers."""
        combined_pattern = '|'.join(self.PAGE_PATTERNS)
        parts = re.split(f'({combined_pattern})', content, flags=re.MULTILINE)
        
        pages = []
        current_page = []
        
        for part in parts:
            if part is None:
                continue
            is_marker = any(re.match(pattern, part) for pattern in self.PAGE_PATTERNS)
            if is_marker:
                if current_page:
                    pages.append('\n'.join(current_page))
                current_page = [part]
            else:
                current_page.append(part)
        
        if current_page:
            pages.append('\n'.join(current_page))
        
        if len(pages) <= 1:
            return [], [], False
        
        chunks = []
        metadata = []
        for i in range(0, len(pages), pages_per_chunk):
            chunk_pages = pages[i:i + pages_per_chunk]
            chunk_text = '\n\n'.join(chunk_pages).strip()
            if chunk_text:
                chunks.append(chunk_text)
                page_start = i + 1
                page_end = min(i + pages_per_chunk, len(pages))
                metadata.append({"page_range": f"{page_start}-{page_end}" if page_start != page_end else str(page_start)})
        
        return chunks, metadata, True
    
    def _chunk_by_section(self, content: str, split_level: int = 2, 
                          sections_per_chunk: int = 1) -> Tuple[List[str], List[Dict], bool]:
        """Split content by heading structure with hierarchical context preservation.
        
        This implements smart section chunking where:
        - Chunks are created at the specified heading level
        - Parent headings (titles only) are preserved for context
        - Sections from different parents are never mixed
        - Intro text before first heading goes to first chunk only
        
        Args:
            content: Markdown content
            split_level: Heading level to split on (1-6)
            sections_per_chunk: Number of sections at that level per chunk
            
        Returns:
            Tuple of (chunks, metadata list, success flag)
        """
        lines = content.split('\n')
        
        # Parse document into a tree structure
        # Each node: {level: int, title: str, content: [], children: [], parent: node}
        root = {'level': 0, 'title': '', 'content': [], 'children': [], 'parent': None}
        current_node = root
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
        
        for line in lines:
            match = heading_pattern.match(line)
            if match:
                level = len(match.group(1))
                title = line
                
                # Find the right parent for this heading
                while current_node['level'] >= level and current_node['parent']:
                    current_node = current_node['parent']
                
                # Create new node
                new_node = {
                    'level': level,
                    'title': title,
                    'content': [],
                    'children': [],
                    'parent': current_node
                }
                current_node['children'].append(new_node)
                current_node = new_node
            else:
                current_node['content'].append(line)
        
        # Collect all nodes at the target level
        def collect_nodes_at_level(node, target_level, path=[]):
            """Collect nodes at target level with their parent path."""
            results = []
            
            new_path = path + [node] if node['level'] > 0 else path
            
            if node['level'] == target_level:
                results.append({
                    'node': node,
                    'path': new_path[:-1],  # Parents only (exclude self)
                    'parent_key': tuple(n['title'] for n in new_path[:-1])  # For grouping
                })
            
            for child in node['children']:
                results.extend(collect_nodes_at_level(child, target_level, new_path))
            
            return results
        
        target_nodes = collect_nodes_at_level(root, split_level)
        
        # If no nodes at target level, fall back
        if not target_nodes:
            logger.warning(f"[markitdown_plus] No H{split_level} headings found, falling back to standard")
            return [], [], False
        
        # Group nodes by parent (never mix sections from different parents)
        from collections import defaultdict
        groups = defaultdict(list)
        for item in target_nodes:
            groups[item['parent_key']].append(item)
        
        # Build chunks
        chunks = []
        metadata = []
        
        def node_to_text(node, include_children=True):
            """Convert a node to text."""
            lines = []
            if node['title']:
                lines.append(node['title'])
            lines.extend(node['content'])
            if include_children:
                for child in node['children']:
                    lines.extend(node_to_text(child, include_children=True).split('\n'))
            return '\n'.join(lines)
        
        def get_context_headers(path, include_intro=False):
            """Get parent headers as context (titles only)."""
            context = []
            for i, node in enumerate(path):
                if node['title']:
                    context.append(node['title'])
                # Include intro text only for first chunk of first parent
                if include_intro and i == 0 and node['content']:
                    # Only include if this is actual intro content
                    intro = '\n'.join(node['content']).strip()
                    if intro:
                        context.append(intro)
            return context
        
        first_chunk = True
        for parent_key, items in groups.items():
            # Process sections in this parent group
            for i in range(0, len(items), sections_per_chunk):
                batch = items[i:i + sections_per_chunk]
                
                chunk_lines = []
                section_titles = []
                
                # Add context headers (parent titles)
                # Only include intro text in the very first chunk
                context = get_context_headers(batch[0]['path'], include_intro=first_chunk)
                chunk_lines.extend(context)
                first_chunk = False
                
                # Add the actual sections
                for item in batch:
                    section_text = node_to_text(item['node'])
                    chunk_lines.append(section_text)
                    section_titles.append(item['node']['title'])
                
                chunk_text = '\n\n'.join(chunk_lines).strip()
                if chunk_text:
                    chunks.append(chunk_text)
                    metadata.append({
                        'section_titles': section_titles,
                        'section_count': len(batch),
                        'parent_path': ' > '.join(n['title'] for n in batch[0]['path'] if n['title'])
                    })
        
        return chunks, metadata, True
    
    def _extract_headers_for_outline(self, content: str) -> List[Tuple[int, str]]:
        """Extract all headers from Markdown content for document outline.
        
        Args:
            content: The Markdown content
            
        Returns:
            List of tuples (header_level, header_text) where header_level is the number of # symbols
        """
        # Pattern to match Markdown headers (#, ##, ###, etc.)
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        headers = []
        for match in header_pattern.finditer(content):
            header_level = len(match.group(1))  # Number of # symbols
            header_text = match.group(2).strip()
            headers.append((header_level, header_text))
        
        return headers
    
    def _generate_document_outline(self, content: str) -> str:
        """Generate a hierarchical document outline section.
        
        Args:
            content: The Markdown content
            
        Returns:
            A formatted document outline as a string
        """
        headers = self._extract_headers_for_outline(content)
        
        if not headers:
            return ""
        
        outline_lines = [
            "",
            "Document Outline",
            "================",
            ""
        ]
        
        # Track the minimum header level to use as the base level
        min_level = min(h[0] for h in headers) if headers else 1
        
        for header_level, header_text in headers:
            # Calculate indent level relative to the minimum level
            indent_level = header_level - min_level
            indent = "  " * indent_level
            outline_lines.append(f"{indent}* <a>{header_text}</a>")
        
        return "\n".join(outline_lines)
    
    def _extract_sections_by_headers(self, content: str) -> List[Tuple[str, str]]:
        """Extract sections from Markdown content based on headers.
        
        Args:
            content: The Markdown content
            
        Returns:
            List of tuples (section_title, section_content)
        """
        # Pattern to match Markdown headers (## or ###)
        header_pattern = re.compile(r'^(#{2,3})\s+(.+)$', re.MULTILINE)
        
        sections = []
        matches = list(header_pattern.finditer(content))
        
        if not matches:
            # No headers found, return entire content as single section
            return [("Document", content)]
        
        # Extract sections between headers
        for i, match in enumerate(matches):
            header_level = len(match.group(1))  # Number of # symbols
            section_title = match.group(2).strip()
            start_pos = match.start()
            
            # Find end position (start of next header or end of document)
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(content)
            
            section_content = content[start_pos:end_pos].strip()
            sections.append((section_title, section_content))
        
        # If there's content before the first header, add it as preamble
        if matches[0].start() > 0:
            preamble = content[:matches[0].start()].strip()
            if preamble:
                sections.insert(0, ("Preamble", preamble))
        
        return sections
    
    def _create_parent_chunks(self, content: str, parent_chunk_size: int, 
                              split_by_headers: bool) -> List[Dict[str, Any]]:
        """Create parent chunks from content.
        
        Args:
            content: The document content
            parent_chunk_size: Maximum size for parent chunks
            split_by_headers: Whether to split by Markdown headers
            
        Returns:
            List of parent chunk dictionaries with text and metadata
        """
        parent_chunks = []
        
        if split_by_headers:
            # Split by headers first
            sections = self._extract_sections_by_headers(content)
            
            for section_title, section_content in sections:
                # If section is larger than parent_chunk_size, split it
                if len(section_content) > parent_chunk_size:
                    # Use RecursiveCharacterTextSplitter for oversized sections
                    splitter = RecursiveCharacterTextSplitter(
                        chunk_size=parent_chunk_size,
                        chunk_overlap=100,
                        separators=["\n\n", "\n", " ", ""]
                    )
                    chunks = splitter.split_text(section_content)
                    
                    for i, chunk in enumerate(chunks):
                        chunk_metadata = {
                            "section_title": section_title
                        }
                        # Only add section_part if there are multiple chunks
                        if len(chunks) > 1:
                            chunk_metadata["section_part"] = i + 1
                        parent_chunks.append({
                            "text": chunk,
                            "metadata": chunk_metadata
                        })
                else:
                    parent_chunks.append({
                        "text": section_content,
                        "metadata": {
                            "section_title": section_title
                        }
                    })
        else:
            # Use simple character-based splitting for parent chunks
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=parent_chunk_size,
                chunk_overlap=100,
                separators=["\n\n", "\n", " ", ""]
            )
            chunks = splitter.split_text(content)
            
            for chunk in chunks:
                parent_chunks.append({
                    "text": chunk,
                    "metadata": {}
                })
        
        return parent_chunks
    
    def _create_child_chunks(self, parent_text: str, parent_index: int,
                            child_chunk_size: int, child_chunk_overlap: int) -> List[str]:
        """Create child chunks from a parent chunk.
        
        Args:
            parent_text: The parent chunk text
            parent_index: Index of the parent chunk
            child_chunk_size: Size of child chunks
            child_chunk_overlap: Overlap between child chunks
            
        Returns:
            List of child chunk texts
        """
        # Use RecursiveCharacterTextSplitter for child chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        child_chunks = splitter.split_text(parent_text)
        return child_chunks
    
    def _chunk_hierarchical(self, content: str, parent_chunk_size: int = 2000,
                           child_chunk_size: int = 400, child_chunk_overlap: int = 50,
                           split_by_headers: bool = True, 
                           include_outline: bool = False) -> Tuple[List[str], List[Dict], bool]:
        """Split content using hierarchical parent-child chunking strategy.
        
        This implements the same strategy as hierarchical_ingest.py where:
        - Parent chunks (larger contexts) are stored in metadata
        - Child chunks (small sections) are used for semantic search/embedding
        - Optionally appends a document outline for better structural understanding
        
        Args:
            content: Markdown content
            parent_chunk_size: Size of parent chunks (default: 2000)
            child_chunk_size: Size of child chunks (default: 400)
            child_chunk_overlap: Overlap between child chunks (default: 50)
            split_by_headers: Whether to split parent chunks by headers (default: True)
            include_outline: Whether to append document outline (default: False)
            
        Returns:
            Tuple of (chunks, metadata list, success flag)
        """
        # Generate and append document outline if requested
        if include_outline:
            outline = self._generate_document_outline(content)
            if outline:
                content = content + "\n\n" + outline
        
        # Step 1: Create parent chunks
        parent_chunks = self._create_parent_chunks(content, parent_chunk_size, split_by_headers)
        
        # Step 2: First pass - create all child chunks to get total count
        all_child_data = []
        global_child_index = 0
        
        for parent_index, parent_chunk in enumerate(parent_chunks):
            parent_text = parent_chunk["text"]
            parent_metadata = parent_chunk["metadata"]
            
            # Create child chunks from this parent
            child_texts = self._create_child_chunks(
                parent_text, parent_index, child_chunk_size, child_chunk_overlap
            )
            
            # Store child data for second pass
            for child_index, child_text in enumerate(child_texts):
                all_child_data.append({
                    "text": child_text,
                    "parent_text": parent_text,
                    "parent_index": parent_index,
                    "child_index": child_index,
                    "global_child_index": global_child_index,
                    "children_in_parent": len(child_texts),
                    "parent_metadata": parent_metadata
                })
                global_child_index += 1
        
        # Step 3: Second pass - create result with metadata
        chunks = []
        metadata_list = []
        total_chunks = len(all_child_data)
        
        for child_data in all_child_data:
            chunk_metadata = {
                # Parent-child relationship
                "parent_chunk_id": child_data["parent_index"],
                "child_chunk_id": child_data["child_index"],
                "chunk_level": "child",
                "parent_text": child_data["parent_text"],  # Store full parent context
                
                # Global indexing
                "chunk_index": child_data["global_child_index"],
                "chunk_count": total_chunks,
                "children_in_parent": child_data["children_in_parent"],
                
                # Additional parent metadata
                **child_data["parent_metadata"]
            }
            
            chunks.append(child_data["text"])
            metadata_list.append(chunk_metadata)
        
        logger.info(f"[markitdown_plus] Hierarchical chunking: {len(parent_chunks)} parents -> {len(chunks)} children")
        
        return chunks, metadata_list, True
    
    def _save_markdown(self, file_path: Path, content: str) -> str:
        """Save the processed markdown content."""
        md_output_path = file_path.with_suffix('.md')
        try:
            with open(md_output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Saved markdown to {md_output_path}")
            return str(md_output_path)
        except Exception as e:
            logger.warning(f"Failed to save markdown: {e}")
            return ""
    
    def ingest(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
        """Ingest a file using MarkItDown with enhanced features.
        
        Args:
            file_path: Path to the file to ingest
            **kwargs: Plugin parameters including:
                - progress_callback: Function(current, total, message) for progress updates
                - stats_callback: Function(stats_dict) to receive processing statistics
            
        Returns:
            List of document chunks with metadata
        """
        # Initialize stats tracker
        stats = ProcessingStatsTracker()
        
        file_path_obj = Path(file_path)
        file_name = file_path_obj.name
        file_extension = file_path_obj.suffix.lstrip(".")
        file_size = os.path.getsize(file_path)
        
        # Validate parameters
        params, warnings = self._validate_params(file_extension, **kwargs)
        for warning in warnings:
            logger.warning(f"[markitdown_plus] {warning}")
        
        # Extract parameters
        image_mode = params.get("image_descriptions", "none")
        chunking_mode = params.get("chunking_mode", "standard")
        chunk_size = params.get("chunk_size", 1000)
        chunk_overlap = params.get("chunk_overlap", 200)
        splitter_type = params.get("splitter_type", "RecursiveCharacterTextSplitter")
        pages_per_chunk = params.get("pages_per_chunk", 1)
        split_on_heading = params.get("split_on_heading", 2)
        headings_per_chunk = params.get("headings_per_chunk", 1)
        # Hierarchical parameters
        parent_chunk_size = params.get("parent_chunk_size", 2000)
        child_chunk_size = params.get("child_chunk_size", 400)
        child_chunk_overlap = params.get("child_chunk_overlap", 50)
        split_by_headers = params.get("split_by_headers", True)
        include_outline = params.get("include_outline", False)
        # Metadata
        description = params.get("description")
        citation = params.get("citation")
        provided_file_url = params.get("file_url", "")
        openai_api_key = params.get("openai_api_key")
        collection_owner = params.get("collection_owner", "")
        collection_name = params.get("collection_name", "")
        stats_callback = kwargs.get("stats_callback")
        
        # Helper to report stats during processing (for real-time updates)
        def report_stats_now():
            """Report current stats to callback for real-time UI updates."""
            if stats_callback and callable(stats_callback):
                try:
                    stats_callback(stats.to_dict())
                except Exception as e:
                    logger.debug(f"[markitdown_plus] Failed to report interim stats: {e}")
        
        # Prepare OpenAI client if needed
        openai_client = None
        if image_mode == "llm":
            if openai_api_key:
                openai_client = self._get_openai_client(openai_api_key)
                if not openai_client:
                    logger.warning("[markitdown_plus] Failed to create OpenAI client, falling back to 'basic' mode")
                    image_mode = "basic"
                    # Record in stats for UI
                    stats.stage_timings.append({
                        "stage": "warning",
                        "duration_ms": 0,
                        "message": "⚠️ OpenAI client failed - using basic image descriptions",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })
            else:
                logger.warning("[markitdown_plus] LLM mode requested but no API key (collection doesn't use OpenAI) - using 'basic' mode")
                image_mode = "basic"
                # Record in stats for UI
                stats.stage_timings.append({
                    "stage": "info",
                    "duration_ms": 0,
                    "message": "ℹ️ Collection doesn't use OpenAI - using basic image descriptions (images still extracted)",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
        
        images_extracted = 0
        images_folder_url = ""
        
        # === PDF SPECIAL HANDLING ===
        # For PDFs, use pymupdf to extract BOTH text AND images with proper positioning
        is_pdf = file_extension.lower() == "pdf"
        use_pymupdf_for_pdf = is_pdf and PYMUPDF_AVAILABLE and collection_owner and collection_name
        
        if use_pymupdf_for_pdf:
            # === STAGE 1+2: PDF EXTRACTION (text + images combined) ===
            self.report_progress(kwargs, 0, 5, f"🚀 Starting PDF extraction with pymupdf (image_mode: {image_mode})...")
            stats.start_stage("pdf_extraction")
            self.report_progress(kwargs, 1, 5, f"📄 Extracting {file_name} with pymupdf...")
            
            try:
                content, images_extracted = self._extract_pdf_with_images(
                    file_path_obj, collection_owner, collection_name,
                    image_mode=image_mode, openai_client=openai_client,
                    stats_tracker=stats, kwargs=kwargs, stats_callback=stats_callback
                )
                
                if content is None:
                    # Fallback to markitdown if pymupdf extraction failed
                    logger.warning("[markitdown_plus] pymupdf extraction failed, falling back to markitdown")
                    use_pymupdf_for_pdf = False
                else:
                    stats.content_length = len(content)
                    
                    # Build images folder URL if images were extracted
                    if images_extracted > 0:
                        base_name = file_path_obj.stem
                        images_folder_url = f"{STATIC_URL_PREFIX}/{collection_owner}/{collection_name}/{base_name}"
                    
                    # Build stage message
                    if images_extracted > 0:
                        if image_mode == "llm" and stats.images_with_llm_descriptions > 0:
                            extract_msg = f"PDF extracted: {len(content):,} chars, {images_extracted} images ({stats.images_with_llm_descriptions} LLM)"
                        else:
                            extract_msg = f"PDF extracted: {len(content):,} chars, {images_extracted} images"
                    else:
                        extract_msg = f"PDF extracted: {len(content):,} chars, no images"
                    
                    stats.end_stage(extract_msg)
                    logger.info(f"[markitdown_plus] {extract_msg}")
                    report_stats_now()  # Update UI with PDF extraction results
                    
            except Exception as e:
                logger.error(f"[markitdown_plus] PDF extraction error: {e}")
                use_pymupdf_for_pdf = False
        
        # === STANDARD FLOW: markitdown conversion + image processing ===
        if not use_pymupdf_for_pdf:
            # === STAGE 1: CONVERT ===
            self.report_progress(kwargs, 0, 5, f"Starting document conversion...")
            stats.start_stage("conversion")
            self.report_progress(kwargs, 1, 5, f"Converting {file_name} to Markdown...")
            
            try:
                md = MarkItDown()
                result = md.convert(file_path)
                content = result.text_content
                stats.content_length = len(content)
                logger.info(f"[markitdown_plus] Converted {file_name}, length: {len(content)}")
            except Exception as e:
                logger.error(f"[markitdown_plus] Conversion error: {e}")
                raise ValueError(f"Error converting file: {str(e)}")
            
            stats.end_stage(f"{file_extension.upper()} → Markdown ({len(content):,} chars)")
            report_stats_now()  # Update UI after conversion
            
            # === STAGE 2: PROCESS IMAGES ===
            self.report_progress(kwargs, 2, 5, f"Processing images...")
            stats.start_stage("image_extraction")
            
            if collection_owner and collection_name and image_mode != "none":
                content, images_extracted, images_folder_url = self._extract_and_process_images(
                    content, file_path_obj, collection_owner, collection_name,
                    mode=image_mode, openai_client=openai_client, stats_tracker=stats
                )
            
            stats.images_extracted = images_extracted
            
            # Build stage message
            if images_extracted > 0:
                if image_mode == "llm" and stats.images_with_llm_descriptions > 0:
                    img_msg = f"Extracted {images_extracted} images ({stats.images_with_llm_descriptions} with LLM descriptions)"
                else:
                    img_msg = f"Extracted {images_extracted} images"
            else:
                img_msg = "No images extracted" if image_mode == "none" else "No images found"
            stats.end_stage(img_msg)
            report_stats_now()  # Update UI after image extraction
        
        # If LLM calls were made, record separate stage for clarity
        if stats.llm_calls:
            # Add a summary stage for LLM processing
            stats.stage_timings.append({
                "stage": "llm_descriptions",
                "duration_ms": stats.total_llm_duration_ms,
                "message": f"{len(stats.llm_calls)} LLM API calls ({stats.images_with_llm_descriptions} successful)",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
        
        # === STAGE 3: CHUNK ===
        self.report_progress(kwargs, 3, 5, f"Applying {chunking_mode} chunking...")
        stats.start_stage("chunking")
        
        chunks = []
        chunk_metadata_list = []
        strategy_metadata = {}
        
        if chunking_mode == "by_page":
            chunks, chunk_metadata_list, success = self._chunk_by_page(content, pages_per_chunk)
            if success:
                strategy_metadata = {
                    "chunking_strategy": "by_page",
                    "pages_per_chunk": pages_per_chunk
                }
                stats.chunking_strategy = "by_page"
            else:
                logger.warning("[markitdown_plus] No page markers, falling back to standard")
                chunking_mode = "standard"
        
        if chunking_mode == "by_section":
            chunks, chunk_metadata_list, success = self._chunk_by_section(
                content, split_on_heading, headings_per_chunk
            )
            if success:
                strategy_metadata = {
                    "chunking_strategy": "by_section",
                    "split_on_heading": split_on_heading,
                    "headings_per_chunk": headings_per_chunk
                }
                stats.chunking_strategy = "by_section"
            else:
                logger.warning("[markitdown_plus] No headings found, falling back to standard")
                chunking_mode = "standard"
        
        if chunking_mode == "hierarchical":
            chunks, chunk_metadata_list, success = self._chunk_hierarchical(
                content,
                parent_chunk_size=parent_chunk_size,
                child_chunk_size=child_chunk_size,
                child_chunk_overlap=child_chunk_overlap,
                split_by_headers=split_by_headers,
                include_outline=include_outline
            )
            if success:
                strategy_metadata = {
                    "chunking_strategy": "hierarchical_parent_child",
                    "parent_chunk_size": parent_chunk_size,
                    "child_chunk_size": child_chunk_size,
                    "child_chunk_overlap": child_chunk_overlap,
                    "split_by_headers": split_by_headers,
                    "include_outline": include_outline
                }
                stats.chunking_strategy = "hierarchical_parent_child"
            else:
                logger.warning("[markitdown_plus] Hierarchical chunking failed, falling back to standard")
                chunking_mode = "standard"
        
        if chunking_mode == "standard" and not chunks:
            chunks = self._chunk_standard(content, chunk_size=chunk_size, 
                                          chunk_overlap=chunk_overlap, splitter_type=splitter_type)
            chunk_metadata_list = [{}] * len(chunks)
            strategy_metadata = {
                "chunking_strategy": f"standard_{splitter_type.lower()}",
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap
            }
            stats.chunking_strategy = f"standard_{splitter_type.lower()}"
        
        # Calculate chunk statistics
        stats.calculate_chunk_stats(chunks)
        stats.end_stage(f"{len(chunks)} chunks ({chunking_mode})")
        report_stats_now()  # Update UI after chunking
        
        logger.info(f"[markitdown_plus] Created {len(chunks)} chunks")
        
        # === STAGE 4: FINALIZE ===
        self.report_progress(kwargs, 4, 5, f"Finalizing {len(chunks)} chunks...")
        stats.start_stage("finalization")
        
        # Save markdown
        md_file_path = self._save_markdown(file_path_obj, content)
        
        # Build URLs
        original_file_url = provided_file_url or ""
        markdown_file_url = ""
        if md_file_path:
            if collection_owner and collection_name:
                md_filename = file_path_obj.with_suffix('.md').name
                markdown_file_url = f"{STATIC_URL_PREFIX}/{collection_owner}/{collection_name}/{md_filename}"
            else:
                markdown_file_url = file_path_obj.with_suffix('.md').name
        
        # Store output file URLs in stats
        stats.output_files = {
            "original_file_url": original_file_url or None,
            "markdown_url": markdown_file_url or None,
            "images_folder_url": images_folder_url or None
        }
        
        # Set markdown preview
        stats.set_markdown_preview(content, max_length=2000)
        
        stats.end_stage(f"Saved markdown and prepared {len(chunks)} chunks")
        
        # Base metadata
        base_metadata = {
            "source": file_path,
            "filename": file_name,
            "extension": file_extension,
            "file_size": file_size,
            "original_file_url": original_file_url,
            "markdown_file_url": markdown_file_url,
            "file_url": original_file_url or markdown_file_url,
            "image_description_mode": image_mode,
            "images_extracted": images_extracted,
        }
        
        if images_extracted > 0 and images_folder_url:
            base_metadata["images_folder_url"] = images_folder_url
        
        base_metadata.update(strategy_metadata)
        
        if description:
            base_metadata["description"] = description
        if citation:
            base_metadata["citation"] = citation
        
        # Build results
        result = []
        for i, chunk_text in enumerate(chunks):
            chunk_meta = base_metadata.copy()
            chunk_meta["chunk_index"] = i
            chunk_meta["chunk_count"] = len(chunks)
            
            # Add chunk-specific metadata
            if i < len(chunk_metadata_list) and chunk_metadata_list[i]:
                chunk_meta.update(chunk_metadata_list[i])
            
            result.append({"text": chunk_text, "metadata": chunk_meta})
        
        # === STAGE 5: COMPLETE ===
        self.report_progress(kwargs, 5, 5, f"Completed: {len(result)} chunks from {file_name}")
        
        # Report stats via callback if provided
        if stats_callback and callable(stats_callback):
            try:
                stats_callback(stats.to_dict())
                logger.info(f"[markitdown_plus] Reported processing stats")
            except Exception as e:
                logger.warning(f"[markitdown_plus] Failed to report stats: {e}")
        
        return result
