"""
Hierarchical ingestion plugin for Markdown documents with parent-child chunking.

This plugin implements a parent-child chunking strategy where:
- Child chunks (small sections) are used for semantic search/embedding
- Parent chunks (larger contexts) are stored in metadata and returned to the LLM

The strategy is optimized for documents with hierarchical headers (##, ###, etc.)
and structural queries like "How many steps does X have?" or "List all steps".
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json

from langchain_text_splitters import RecursiveCharacterTextSplitter
from .base import IngestPlugin, PluginRegistry


@PluginRegistry.register
class HierarchicalIngestPlugin(IngestPlugin):
    """Plugin for ingesting Markdown files with parent-child chunking."""
    
    name = "hierarchical_ingest"
    kind = "file-ingest"
    description = "Ingest Markdown files with parent-child chunking strategy for better structural queries"
    supported_file_types = {"*.md"}
    
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
                "required": False
            },
            "child_chunk_size": {
                "type": "integer",
                "description": "Size of child chunks (used for embedding/search)",
                "default": 400,
                "required": False
            },
            "child_chunk_overlap": {
                "type": "integer",
                "default": 50,
                "description": "Overlap between child chunks",
                "required": False
            },
            "split_by_headers": {
                "type": "boolean",
                "description": "Whether to split parent chunks by Markdown headers",
                "default": True,
                "required": False
            }
        }
    
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
        """Ingest a Markdown file with parent-child chunking strategy.
        
        Args:
            file_path: Path to the Markdown file to ingest
            parent_chunk_size: Size of parent chunks (default: 2000)
            child_chunk_size: Size of child chunks (default: 400)
            child_chunk_overlap: Overlap between child chunks (default: 50)
            split_by_headers: Whether to split parent chunks by headers (default: True)
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
        file_url = kwargs.get("file_url", "")
        
        # Read the file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            raise RuntimeError(f"Failed to read file: {str(e)}")
        
        # Get file metadata
        file_path_obj = Path(file_path)
        file_name = file_path_obj.name
        file_extension = file_path_obj.suffix.lstrip(".")
        file_size = os.path.getsize(file_path)
        
        # Create base metadata
        base_metadata = {
            "source": file_path,
            "filename": file_name,
            "extension": file_extension,
            "file_size": file_size,
            "file_url": file_url,
            "chunking_strategy": "hierarchical_parent_child"
        }
        
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
            
            # Filter out None values from metadata (ChromaDB doesn't accept them)
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
            print(f"INFO: [hierarchical_ingest] Successfully wrote {len(result)} child chunks "
                  f"from {len(parent_chunks)} parent chunks to {output_file_path}")
        except Exception as e:
            print(f"WARNING: [hierarchical_ingest] Failed to write chunks to {output_file_path}: {str(e)}")
        
        return result
