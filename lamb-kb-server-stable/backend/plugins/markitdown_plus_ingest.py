"""
MarkItDown Plus ingestion plugin for various file formats.

This is an enhanced version of markitdown_ingest that provides:
- LLM-powered image descriptions using OpenAI vision models (optional)
- Image extraction and storage with proper URL references
- Multiple chunking strategies (standard, by_page, by_section)
- Hierarchical section chunking with context preservation
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
    - Multiple chunking modes: standard, by_page, by_section
    - Hierarchical section chunking with parent context preservation
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
                "enum": ["standard", "by_page", "by_section"],
                "enum_labels": {
                    "standard": "Standard (character-based splitting)",
                    "by_page": "By page (PDF, DOCX, PPTX only)",
                    "by_section": "By section (split on headings)"
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
        description = params.get("description")
        citation = params.get("citation")
        provided_file_url = params.get("file_url", "")
        openai_api_key = params.get("openai_api_key")
        collection_owner = params.get("collection_owner", "")
        collection_name = params.get("collection_name", "")
        stats_callback = kwargs.get("stats_callback")
        
        # === STAGE 1: CONVERT ===
        self.report_progress(kwargs, 0, 5, f"Starting document conversion...")
        stats.start_stage("conversion")
        self.report_progress(kwargs, 1, 5, f"Converting {file_name} to Markdown...")
        
        # Prepare OpenAI client if needed
        openai_client = None
        if image_mode == "llm":
            if openai_api_key:
                openai_client = self._get_openai_client(openai_api_key)
                if not openai_client:
                    logger.warning("[markitdown_plus] Failed to create OpenAI client, using 'none' mode")
                    image_mode = "none"
            else:
                logger.warning("[markitdown_plus] LLM mode needs API key, using 'none' mode")
                image_mode = "none"
        
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
        
        # === STAGE 2: PROCESS IMAGES ===
        self.report_progress(kwargs, 2, 5, f"Processing images...")
        stats.start_stage("image_extraction")
        
        images_extracted = 0
        images_folder_url = ""
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
