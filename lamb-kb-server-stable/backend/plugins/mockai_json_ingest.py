"""
MockAI JSON Ingest Plugin for structured data files.

This plugin handles JSON files and ZIP archives containing JSON files,
preserving all metadata from the structured format and creating searchable chunks.
Supports the MockAI data format with full metadata extraction.
"""

import os
import json
import zipfile
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import tempfile

from .base import IngestPlugin, PluginRegistry


@PluginRegistry.register
class MockAIJSONIngestPlugin(IngestPlugin):
    """Plugin for ingesting MockAI structured JSON data with full metadata preservation."""

    name = "mockai_json_ingest"
    kind = "file-ingest"
    description = "Ingest MockAI structured JSON data with complete metadata preservation"
    supported_file_types = {"json", "zip"}

    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Get the parameters accepted by this plugin.

        Returns:
            A dictionary mapping parameter names to their specifications
        """
        return {
            # No parameters needed - the JSON files contain pre-chunked data
        }

    def _validate_parameters(self, **kwargs) -> None:
        """Validate plugin parameters.

        Args:
            **kwargs: Plugin parameters

        Raises:
            ValueError: If parameters are invalid
        """
        # No parameters to validate - JSON files contain pre-chunked data
        pass

    def _extract_metadata_from_object(self, obj: Dict[str, Any], source_file: str, **kwargs) -> Dict[str, Any]:
        """Extract metadata from a JSON object.

        Args:
            obj: JSON object to extract metadata from
            source_file: Source filename
            **kwargs: Plugin parameters

        Returns:
            Dictionary of extracted metadata
        """
        metadata = {}

        # Add source information
        metadata["source_file"] = source_file
        metadata["ingestion_plugin"] = "mockai_json_ingest"

        # Add timestamp
        metadata["ingestion_timestamp"] = datetime.utcnow().isoformat()

        # Add document ID (will be set by ChromaDB)
        metadata["temp_document_id"] = str(uuid.uuid4())

        # Extract all fields from the object as metadata
        for key, value in obj.items():
            if key == "text":
                # Skip the main text content - it will be the document content
                continue
            elif key == "old_text":
                # Handle old_text specially - might be useful metadata
                metadata[f"original_{key}"] = value
            elif isinstance(value, (dict, list)):
                # Handle complex objects - always flatten for simplicity
                if isinstance(value, list):
                    # Flatten arrays to strings for metadata
                    if len(value) > 10:
                        # Limit array size for metadata
                        metadata[key] = f"[{', '.join(str(v) for v in value[:10])}... ({len(value)-10} more)]"
                    else:
                        metadata[key] = str(value)
                elif isinstance(value, dict):
                    # Flatten nested objects
                    for nested_key, nested_value in value.items():
                        metadata[f"{key}_{nested_key}"] = str(nested_value)
                else:
                    metadata[key] = str(value)
            else:
                # Simple values
                metadata[key] = value

        # Add plugin-specific metadata
        metadata["chunking_strategy"] = "pre_chunked_json"
        metadata["plugin_version"] = "1.0.0"

        return metadata

    def _create_chunks_from_json_data(self, data: Any, source_file: str, **kwargs) -> List[Dict[str, Any]]:
        """Create chunks from JSON data.

        Each JSON object represents a pre-chunked piece of content.
        The 'text' field becomes the chunk content, all other fields become metadata.

        Args:
            data: Parsed JSON data (list or single object)
            source_file: Source filename
            **kwargs: Plugin parameters

        Returns:
            List of document chunks with metadata
        """
        chunks = []

        # Ensure data is a list
        if not isinstance(data, list):
            data = [data]

        for item in data:
            if not isinstance(item, dict):
                continue

            # Skip items without text content
            if "text" not in item:
                continue

            text_content = item.get("text", "")
            metadata = self._extract_metadata_from_object(item, source_file, **kwargs)

            # Each JSON object becomes exactly one chunk (no additional splitting)
            chunks.append({
                "text": text_content,
                "metadata": metadata
            })

        return chunks


    def _process_json_file(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
        """Process a single JSON file.

        Args:
            file_path: Path to JSON file
            **kwargs: Plugin parameters

        Returns:
            List of document chunks
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            source_file = os.path.basename(file_path)
            return self._create_chunks_from_json_data(data, source_file, **kwargs)

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in {file_path}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error processing JSON file {file_path}: {str(e)}")

    def _process_zip_file(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
        """Process a ZIP file containing JSON files.

        Args:
            file_path: Path to ZIP file
            **kwargs: Plugin parameters

        Returns:
            List of document chunks from all JSON files in ZIP
        """
        all_chunks = []

        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Filter for JSON files
                json_files = [f for f in zip_ref.namelist() if f.lower().endswith('.json')]

                for json_file in json_files:
                    try:
                        # Extract JSON content
                        with zip_ref.open(json_file) as f:
                            data = json.load(f)

                        # Create chunks for this file
                        chunks = self._create_chunks_from_json_data(data, json_file, **kwargs)
                        all_chunks.extend(chunks)

                    except Exception as e:
                        print(f"WARNING: [mockai_json_ingest] Error processing {json_file} in ZIP: {str(e)}")
                        continue

        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid ZIP file {file_path}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error processing ZIP file {file_path}: {str(e)}")

        return all_chunks

    def ingest(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
        """Ingest JSON or ZIP file and return structured chunks with metadata.

        Args:
            file_path: Path to the file to ingest (JSON or ZIP)
            **kwargs: Plugin parameters

        Returns:
            A list of dictionaries, each containing:
                - text: The chunk text content
                - metadata: A dictionary of metadata including all JSON fields

        Raises:
            ValueError: If file format is invalid or processing fails
        """
        # Validate parameters
        self._validate_parameters(**kwargs)

        file_path_obj = Path(file_path)
        file_extension = file_path_obj.suffix.lower().lstrip('.')

        if file_extension == 'json':
            return self._process_json_file(file_path, **kwargs)
        elif file_extension == 'zip':
            return self._process_zip_file(file_path, **kwargs)
        else:
            supported_types = ', '.join(self.supported_file_types)
            raise ValueError(f"Unsupported file type '{file_extension}'. Supported types: {supported_types}")

    def _write_debug_output(self, chunks: List[Dict[str, Any]], file_path: str) -> None:
        """Write debug output to JSON file (optional).

        Args:
            chunks: List of chunks to write
            file_path: Original file path for output location
        """
        try:
            output_path = Path(file_path).with_suffix('.processed.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(chunks, f, indent=2, ensure_ascii=False)
            print(f"INFO: [mockai_json_ingest] Debug output written to {output_path}")
        except Exception as e:
            print(f"WARNING: [mockai_json_ingest] Could not write debug output: {str(e)}")
