"""
Simple ingestion plugin for text files.

This plugin handles plain text files (txt, md) with chunking using LangChain's text splitters.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

# Import LangChain text splitters
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    TokenTextSplitter
)
from .base import IngestPlugin, PluginRegistry


@PluginRegistry.register
class SimpleIngestPlugin(IngestPlugin):
    """Plugin for ingesting simple text files with LangChain's text splitters."""
    
    name = "simple_ingest"
    kind = "file-ingest"
    description = "Ingest text files with configurable chunking options"
    supported_file_types = {"*.txt", "*.md"}
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Get the parameters accepted by this plugin.
        
        Returns:
            A dictionary mapping parameter names to their specifications
        """
        return {
            "chunk_size": {
                "type": "integer",
                "description": "Size of each chunk",
                "default": 1000,
                "required": False
            },
            "chunk_overlap": {
                "type": "integer",
                "default": 200,
                "description": "Number of units to overlap between chunks (uses LangChain default if not specified)",
                "required": False
            },
            "splitter_type": {
                "type": "string",
                "description": "Type of LangChain splitter to use",
                "enum": ["RecursiveCharacterTextSplitter", "CharacterTextSplitter", "TokenTextSplitter"],
                "default": "RecursiveCharacterTextSplitter",
                "required": False
            }
        }
    
    def ingest(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
        """Ingest a text file and split it into chunks using the selected LangChain splitter.
        
        Args:
            file_path: Path to the file to ingest
            chunk_size: Size of each chunk (default: uses LangChain default)
            chunk_overlap: Number of units to overlap between chunks (default: uses LangChain default)
            splitter_type: Type of LangChain splitter to use (default: RecursiveCharacterTextSplitter)
            file_url: URL to access the file (default: None)
            
        Returns:
            A list of dictionaries, each containing:
                - text: The chunk text
                - metadata: A dictionary of metadata for the chunk
        """
        # Extract parameters
        chunk_size = kwargs.get("chunk_size", None)
        chunk_overlap = kwargs.get("chunk_overlap", None)
        splitter_type = kwargs.get("splitter_type", "RecursiveCharacterTextSplitter")
        file_url = kwargs.get("file_url", "")
        
        # Create parameters dict for splitter initialization
        splitter_params = {}
        if chunk_size is not None:
            splitter_params["chunk_size"] = chunk_size
        if chunk_overlap is not None:
            splitter_params["chunk_overlap"] = chunk_overlap
        
        # Read the file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            raise
        
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
            "chunking_strategy": f"langchain_{splitter_type.lower()}"
        }
        
        # Add chunking parameters to metadata if provided
        if chunk_size is not None:
            base_metadata["chunk_size"] = chunk_size
        if chunk_overlap is not None:
            base_metadata["chunk_overlap"] = chunk_overlap
        
        # Dynamically instantiate the selected LangChain splitter
        try:
            if splitter_type == "RecursiveCharacterTextSplitter":
                text_splitter = RecursiveCharacterTextSplitter(**splitter_params)
            elif splitter_type == "CharacterTextSplitter":
                text_splitter = CharacterTextSplitter(**splitter_params)
            elif splitter_type == "TokenTextSplitter":
                text_splitter = TokenTextSplitter(**splitter_params)
            else:
                raise ValueError(f"Unsupported splitter type: {splitter_type}")
        except ImportError as e:
            raise ImportError(f"Failed to import {splitter_type}: {str(e)}")
        
        # Split content into chunks using the selected splitter
        try:
            chunks = text_splitter.split_text(content)
        except Exception as e:
            raise ValueError(f"Error splitting content into chunks: {str(e)}")
        
        # Create result documents with metadata
        result = []
        for i, chunk_text in enumerate(chunks):
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_index": i,
                "chunk_count": len(chunks)
            })
            result.append({
                "text": chunk_text,
                "metadata": chunk_metadata
            })
        
        # Write the result to a JSON file
        output_file_path = file_path_obj.with_suffix(file_path_obj.suffix + '.json')
        try:
            with open(output_file_path, 'w') as f:
                json.dump(result, f, indent=4)
            print(f"INFO: [simple_ingest] Successfully wrote chunks to {output_file_path}")
        except Exception as e:
            print(f"WARNING: [simple_ingest] Failed to write chunks to {output_file_path}: {str(e)}")
            # Optionally, re-raise the exception or handle it as a non-critical error

        return result