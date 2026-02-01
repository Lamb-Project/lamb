"""
MarkItDown Hierarchical ingestion plugin for various file formats.

This plugin combines:
- MarkItDown conversion (PDF, DOC, DOCX, etc. to Markdown)
- Hierarchical parent-child chunking strategy for better RAG performance
- Optional document outline generation for improved structural queries

The plugin converts any supported file format to Markdown and then applies
the hierarchical parent-child chunking strategy where:
- Child chunks (small sections) are used for semantic search/embedding
- Parent chunks (larger contexts) are stored in metadata and returned to the LLM
- Optionally appends a document outline for better structural understanding
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json

from langchain_text_splitters import RecursiveCharacterTextSplitter
from markitdown import MarkItDown
from .base import IngestPlugin, PluginRegistry


@PluginRegistry.register
class MarkItDownHierarchicalIngestPlugin(IngestPlugin):
    """Plugin for ingesting files with MarkItDown conversion and hierarchical parent-child chunking."""
    
    name = "markitdown_hierarchical_ingest"
    kind = "file-ingest"
    description = "Convert files to Markdown with MarkItDown and apply hierarchical parent-child chunking for better RAG"
    supports_progress = True
    
    supported_file_types = {
        "pdf", "pptx", "docx", "xlsx", "xls", "mp3", "wav", 
        "html", "csv", "json", "xml", "zip", "epub"
    }
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Get the parameters accepted by this plugin.
        
        Returns:
            A dictionary mapping parameter names to their specifications
        """
        return {
            "parent_chunk_size": {
                "type": "integer",
                "description": "Size of parent chunks (larger context)",
                "default": 2000,
                "min": 500,
                "max": 8000,
                "required": False
            },
            "child_chunk_size": {
                "type": "integer",
                "description": "Size of child chunks (used for embedding/search)",
                "default": 400,
                "min": 100,
                "max": 2000,
                "required": False
            },
            "child_chunk_overlap": {
                "type": "integer",
                "default": 50,
                "description": "Overlap between child chunks",
                "min": 0,
                "max": 200,
                "required": False
            },
            "split_by_headers": {
                "type": "boolean",
                "description": "Whether to split parent chunks by Markdown headers",
                "default": True,
                "required": False
            },
            "include_outline": {
                "type": "boolean",
                "description": "Whether to append a document outline (TOC) at the end",
                "default": False,
                "required": False
            },
            "description": {
                "type": "long-string",
                "description": "Optional description for the ingested content",
                "required": False
            },
            "citation": {
                "type": "long-string",
                "description": "Optional citation/source reference",
                "required": False
            }
        }
    
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
    
    def ingest(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
        """Ingest a file by converting to Markdown and applying hierarchical parent-child chunking.
        
        Args:
            file_path: Path to the file to ingest
            parent_chunk_size: Size of parent chunks (default: 2000)
            child_chunk_size: Size of child chunks (default: 400)
            child_chunk_overlap: Overlap between child chunks (default: 50)
            split_by_headers: Whether to split parent chunks by headers (default: True)
            include_outline: Whether to append a document outline at the end (default: False)
            file_url: URL to access the file (default: None)
            
        Returns:
            A list of dictionaries, each containing:
                - text: The child chunk text (used for embedding/search)
                - metadata: A dictionary including:
                    - parent_text: The full parent chunk context
                    - parent_chunk_id: Index of the parent chunk
                    - child_chunk_id: Index of child within parent
                    - chunk_level: "child" (for semantic search)
                    - Other standard metadata fields
        """
        # Extract parameters
        parent_chunk_size = kwargs.get("parent_chunk_size", 2000)
        child_chunk_size = kwargs.get("child_chunk_size", 400)
        child_chunk_overlap = kwargs.get("child_chunk_overlap", 50)
        split_by_headers = kwargs.get("split_by_headers", True)
        include_outline = kwargs.get("include_outline", False)
        file_url = kwargs.get("file_url", "")
        description = kwargs.get("description", None)
        citation = kwargs.get("citation", None)
        
        # Get file metadata
        file_path_obj = Path(file_path)
        file_name = file_path_obj.name
        file_extension = file_path_obj.suffix.lstrip(".")
        file_size = os.path.getsize(file_path)
        
        # Report: Starting conversion (stage 1 of 3)
        self.report_progress(kwargs, 0, 3, f"Converting {file_name} to Markdown...")
        
        # Convert the file to Markdown using MarkItDown
        try:
            md = MarkItDown()
            result = md.convert(file_path)
            content = result.text_content
            print(f"INFO: [markitdown_hierarchical_ingest] Converted {file_name}, length: {len(content)}")
        except Exception as e:
            raise ValueError(f"Error converting file to Markdown: {str(e)}")
        
        # Generate and append document outline if requested
        if include_outline:
            outline = self._generate_document_outline(content)
            if outline:
                content = content + "\n\n" + outline
                print(f"INFO: [markitdown_hierarchical_ingest] Added document outline")
        
        # Report: Starting chunking (stage 2 of 3)
        self.report_progress(kwargs, 1, 3, f"Applying hierarchical chunking...")
        
        # Create base metadata
        base_metadata = {
            "source": file_path,
            "filename": file_name,
            "extension": file_extension,
            "file_size": file_size,
            "file_url": file_url,
            "chunking_strategy": "hierarchical_parent_child"
        }
        
        # Add optional metadata fields if provided
        if description is not None:
            base_metadata["description"] = description
        if citation is not None:
            base_metadata["citation"] = citation
        
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
        
        # Report: Finalizing (stage 3 of 3)
        self.report_progress(kwargs, 2, 3, f"Finalizing {len(all_child_data)} chunks...")
        
        # Step 3: Second pass - create result with correct chunk_count
        result = []
        total_chunks = len(all_child_data)
        
        for child_data in all_child_data:
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
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
            })
            
            # Filter out None values from metadata
            chunk_metadata = {k: v for k, v in chunk_metadata.items() if v is not None}
            
            result.append({
                "text": child_data["text"],  # Child chunk used for embedding/search
                "metadata": chunk_metadata
            })
        
        # Write the result to a JSON file for debugging/inspection
        output_file_path = file_path_obj.with_suffix(file_path_obj.suffix + '.hierarchical.json')
        try:
            with open(output_file_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=4)
            print(f"INFO: [markitdown_hierarchical_ingest] Successfully wrote {len(result)} child chunks "
                  f"from {len(parent_chunks)} parent chunks to {output_file_path}")
        except Exception as e:
            print(f"WARNING: [markitdown_hierarchical_ingest] Failed to write chunks to {output_file_path}: {str(e)}")
        
        print(f"INFO: [markitdown_hierarchical_ingest] Created {len(result)} child chunks from {len(parent_chunks)} parent chunks")
        
        return result
