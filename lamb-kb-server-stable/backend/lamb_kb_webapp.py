#!/usr/bin/env python3
"""
Lamb Knowledge Base Web Application

A simple web app for interacting with the lamb-kb-server API. 
This app allows users to:
- View all collections for a given user
- View detailed information about a collection
- Query collections with custom parameters
- Debug ChromaDB collections
"""

import os
import json
import requests
import chromadb
import logging
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, List, Optional
import uuid

# Configure logging (respect GLOBAL_LOG_LEVEL or LAMB_KB_LOG_LEVEL)
log_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
log_level = os.getenv("LAMB_KB_LOG_LEVEL", os.getenv("GLOBAL_LOG_LEVEL", "WARNING")).upper()
if log_level not in log_levels:
    log_level = "WARNING"
logging.basicConfig(level=getattr(logging, log_level), format='%(asctime)s - %(levelname)s - %(message)s', force=True)
logger = logging.getLogger(__name__)
logger.info(f"Starting Lamb KB webapp with effective log level: {log_level}")

# Load environment variables
load_dotenv()

# Get API key from environment variable or use default
API_KEY = os.getenv("LAMB_API_KEY", "0p3n-w3bu!")
BASE_URL = os.getenv("LAMB_KB_SERVER_URL", "http://localhost:9090")

# Try to get ChromaDB path from environment or use a few common paths
CHROMADB_PATH = os.getenv("CHROMADB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/chromadb"))
CHROMADB_PATHS = [
    CHROMADB_PATH,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/chromadb"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chromadb"), 
    os.path.join(os.path.abspath("."), "data/chromadb"),
    os.path.join(os.path.abspath(".."), "data/chromadb"),
    os.path.join(os.path.abspath("."), "backend/data/chromadb")
]

# Log all paths we're trying
logger.info(f"Working directory: {os.getcwd()}")
for path in CHROMADB_PATHS:
    if os.path.exists(path):
        logger.info(f"ChromaDB path exists: {path}")
    else:
        logger.warning(f"ChromaDB path does not exist: {path}")

app = Flask(__name__)
app.secret_key = os.urandom(24)

class LambKBClient:
    """Client for interacting with the Lamb KB Server API."""
    
    def __init__(self, base_url: str, api_key: str):
        """Initialize the client with the base URL and API key."""
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}"
        }
    
    def _dict_to_obj(self, data: Dict) -> Any:
        """Convert a dictionary to an object with attribute access."""
        if data and isinstance(data, dict):
            class DictToObject:
                def __init__(self, data_dict):
                    self.__dict__.update(data_dict)
                    # For debugging and compatibility with str.format and f-strings
                    self._data = data_dict
                
                def __getitem__(self, key):
                    return self.__dict__.get(key)
                
                def __str__(self):
                    return str(self._data)
                    
                def __repr__(self):
                    return repr(self._data)
                
                def get(self, key, default=None):
                    return self.__dict__.get(key, default)
                
                def to_dict(self):
                    return self._data
            
            # Handle nested dictionaries and lists
            for key, value in data.items():
                if isinstance(value, dict):
                    data[key] = self._dict_to_obj(value)
                elif isinstance(value, list):
                    data[key] = [self._dict_to_obj(item) if isinstance(item, dict) else item for item in value]
            
            return DictToObject(data)
        return data
    
    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make a request to the API with error handling."""
        url = f"{self.base_url}{path}"
        
        # Add headers
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        kwargs["headers"].update(self.headers)
        
        try:
            response = requests.request(method, url, **kwargs)
            
            # Check for errors
            if response.status_code >= 400:
                error_message = f"API Error ({response.status_code}): {response.text}"
                return {"error": error_message}
            
            # Return the response data
            try:
                return response.json()
            except ValueError:
                return response.text
                
        except Exception as e:
            error_message = f"Request Error: {str(e)}"
            print(f"ERROR: {error_message}")
            return {"error": error_message}
    
    def get_collection(self, collection_id: int) -> Dict[str, Any]:
        """Get details of a specific collection."""
        collection = self._request("get", f"/collections/{collection_id}")
        return self._dict_to_obj(collection)
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections."""
        collections = self._request("get", f"/collections")
        if collections and isinstance(collections, dict) and "items" in collections:
            collections["items"] = [self._dict_to_obj(item) for item in collections["items"]]
            return self._dict_to_obj(collections)
        return collections
    
    def list_files(self, collection_id: int, status=None) -> List[Dict[str, Any]]:
        """List files in a collection."""
        params = {}
        if status:
            params["status"] = status
            
        files = self._request("get", f"/collections/{collection_id}/files", params=params)
        return [self._dict_to_obj(file) for file in files] if isinstance(files, list) else files
    
    def list_query_plugins(self) -> List[Dict[str, Any]]:
        """List all query plugins."""
        plugins = self._request("get", f"/query/plugins")
        return plugins
    
    def list_ingestion_plugins(self) -> List[Dict[str, Any]]:
        """List all ingestion plugins."""
        plugins = self._request("get", f"/ingestion/plugins")
        return plugins
    
    def query_collection(self, collection_id: int, query_text: str, top_k: int = 5, 
                        threshold: float = 0.0, plugin_name: str = "simple_query",
                        plugin_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Query a collection."""
        plugin_params = plugin_params or {}
        
        data = {
            "query_text": query_text,
            "top_k": top_k, 
            "threshold": threshold,
            "plugin_params": plugin_params
        }
        
        response = self._request(
            "post", 
            f"/collections/{collection_id}/query?plugin_name={plugin_name}",
            json=data
        )
        
        # Pre-process response before converting to object
        if isinstance(response, dict):
            # Ensure results is a list
            if "results" not in response or response["results"] is None:
                response["results"] = []
            
            # Ensure count is set
            if "count" not in response or response["count"] is None:
                response["count"] = len(response.get("results", []))
            
            # Ensure each result has valid metadata
            if "results" in response and isinstance(response["results"], list):
                for i, result in enumerate(response["results"]):
                    if "metadata" not in result or result["metadata"] is None:
                        response["results"][i]["metadata"] = {}
            
            # Ensure timing is a dict
            if "timing" in response and not isinstance(response["timing"], dict):
                try:
                    # Handle various timing formats
                    if isinstance(response["timing"], (int, float)):
                        response["timing"] = {"total_seconds": response["timing"]}
                    else:
                        response["timing"] = {"total_time": str(response["timing"])}
                except:
                    response["timing"] = {"total_time": "unknown"}
            elif "timing" not in response:
                response["timing"] = {"total_time": "unknown"}
                
            # Log the pre-processed response for debugging
            logger.info(f"Pre-processed query response: count={response['count']}, results_length={len(response['results'])}")
        else:
            # If response is not a dict, create a valid structure
            logger.warning(f"Query response is not a dictionary: {type(response)}")
            response = {
                "results": [],
                "count": 0,
                "timing": {"total_time": "unknown"},
                "error": str(response) if response else "Empty response"
            }
        
        return self._dict_to_obj(response)
    
    def create_collection(self, collection_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new collection.
        
        Args:
            collection_data: Dictionary with collection properties (name, description, owner, visibility, embeddings_model)
            
        Returns:
            Newly created collection details
            
        Raises:
            Exception: If the API request fails with details about the error
        """
        try:
            # Log that we're creating a collection without exposing API key
            if 'embeddings_model' in collection_data and 'vendor' in collection_data['embeddings_model']:
                vendor = collection_data['embeddings_model'].get('vendor')
                model = collection_data['embeddings_model'].get('model')
                # Log without API key details
                safe_data = json.loads(json.dumps(collection_data))  # Deep copy
                if 'apikey' in safe_data.get('embeddings_model', {}):
                    safe_data['embeddings_model']['apikey'] = '[REDACTED]'
                logger.info(f"Creating collection with {vendor} embeddings using model {model}")
            
            # Send the ORIGINAL data without modification
            response = self._request("post", "/collections", json=collection_data)
            
            # Check for error in response
            if isinstance(response, dict) and "error" in response:
                raise Exception(f"API Error: {response['error']}")
                
            # Log success with details about the ChromaDB UUID if available
            if isinstance(response, dict) and "chromadb_uuid" in response:
                logger.info(f"Collection created successfully with ChromaDB UUID: {response['chromadb_uuid']}")
            
            return response
        except requests.exceptions.HTTPError as e:
            # Extract more detailed error message if available
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_data = e.response.json()
                    if "detail" in error_data:
                        raise Exception(f"API Error: {error_data['detail']}")
                except (ValueError, KeyError):
                    pass
            # If we couldn't extract a detailed error, raise the original exception
            raise
        
    def get_collection_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a collection by its name.
        
        Args:
            name: Name of the collection to find
            
        Returns:
            Collection details or None if not found
        """
        collections = self.list_collections()
        if not collections or 'items' not in collections:
            return None
            
        name_lower = name.lower().strip()
        for col in collections.get("items", []):
            if isinstance(col, dict):
                col_name = col.get("name", "").lower().strip()
            else:
                col_name = getattr(col, "name", "").lower().strip()
                
            if col_name == name_lower:
                return col
        return None
        
    def ingest_file_to_collection(self, collection_id: int, file, plugin_name: str, plugin_params: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest a file into a collection using a specified plugin.
        
        Args:
            collection_id: ID of the collection
            file: File object with filename, stream, and content_type attributes
            plugin_name: Name of the ingestion plugin to use
            plugin_params: Parameters for the plugin
            
        Returns:
            Result of the ingestion operation
        """
        url = f"{self.base_url}/collections/{collection_id}/ingest-file"
        headers = {k: v for k, v in self.headers.items() if k != 'Content-Type'}
        
        # Prepare the form data
        form_data = {
            'plugin_name': plugin_name,
            'plugin_params': json.dumps(plugin_params)
        }
        
        files = {
            'file': (file.filename, file.stream, file.content_type)
        }
        
        response = requests.post(url, headers=headers, data=form_data, files=files)
        response.raise_for_status()
        return response.json()




    def ingest_urls_to_collection(self, collection_id: int, urls: List[str], plugin_params: Dict[str, Any]) -> Dict[str, Any]:
            """Ingest content from URLs into a collection.
            
            Args:
                collection_id: ID of the collection
                urls: List of URLs to ingest
                plugin_params: Parameters for the plugin
                
            Returns:
                Result of the ingestion operation
            """
            url = f"{self.base_url}/collections/{collection_id}/ingest-url"
            
            # Prepare the request data
            data = {
                'urls': urls,
                'plugin_name': 'url_ingest',
                'plugin_params': plugin_params
            }
            
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        
    def preview_url_content(self, url: str) -> Dict[str, Any]:
        """Preview content from a URL without ingesting it.
        
        Args:
            url: URL to preview content from
            
        Returns:
            Extracted content from the URL
        """
        api_url = f"{self.base_url}/preview-url"
        
        # Prepare the request data
        data = {
            'url': url
        }
        
        response = requests.post(api_url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
        
    def get_file_content(self, file_id: int) -> Dict[str, Any]:
        """Get the content of a file, especially for ingested URLs.
        
        Args:
            file_id: ID of the file
            
        Returns:
            Content of the file
        """
        api_url = f"{self.base_url}/files/{file_id}/content"
        
        response = requests.get(api_url, headers=self.headers)
        response.raise_for_status()
        return response.json()



# ChromaDB Helper Class
class ChromaDBHelper:
    """Helper class for directly interacting with ChromaDB."""
    
    def __init__(self, db_paths: List[str]):
        """Initialize the ChromaDB helper.
        
        Args:
            db_paths: Possible paths to the ChromaDB directory
        """
        self.db_paths = db_paths
        self.client = None
        self.db_path = None
        
        # Try to connect to ChromaDB using different paths
        for path in db_paths:
            try:
                logger.info(f"Trying to connect to ChromaDB at: {path}")
                if not os.path.exists(path):
                    logger.warning(f"Path does not exist: {path}")
                    continue
                    
                self.client = chromadb.PersistentClient(path=path)
                # Test connection by listing collections
                collections = self.client.list_collections()
                logger.info(f"Connected to ChromaDB at {path}, found {len(collections)} collections")
                self.db_path = path
                break
            except Exception as e:
                logger.error(f"Error connecting to ChromaDB at {path}: {e}")
        
        if self.client is None:
            logger.error("Failed to connect to ChromaDB with any of the provided paths")
    
    def get_collection_details(self, collection_name: str) -> Dict[str, Any]:
        """Get detailed information about a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dictionary with collection details
        """
        try:
            if self.client is None:
                return {
                    "name": collection_name,
                    "error": "Failed to connect to ChromaDB",
                    "success": False
                }
                
            collection = self.client.get_collection(collection_name)
            
            # Get basic collection info
            count = collection.count()
            
            # Get sample documents with metadata and embeddings
            sample_docs = collection.get(
                include=["embeddings", "documents", "metadatas"],
                limit=5
            )
            
            # Calculate embedding dimensions
            embedding_dims = [len(emb) for emb in sample_docs["embeddings"]] if sample_docs["embeddings"] else []
            
            # Extract unique chunking strategies from metadata
            chunking_strategies = {}
            metadata_keys = set()
            
            for meta in sample_docs["metadatas"]:
                if meta:
                    # Track all metadata keys
                    metadata_keys.update(meta.keys())
                    
                    # Track chunking info
                    if 'chunking_strategy' in meta:
                        strategy = meta['chunking_strategy']
                        if strategy not in chunking_strategies:
                            chunking_strategies[strategy] = 1
                        else:
                            chunking_strategies[strategy] += 1
                    
                    # Also track chunk units
                    if 'chunk_unit' in meta:
                        unit = meta['chunk_unit']
                        key = f"unit_{unit}"
                        if key not in chunking_strategies:
                            chunking_strategies[key] = 1
                        else:
                            chunking_strategies[key] += 1
            
            return {
                "name": collection_name,
                "document_count": count,
                "sample_metadata": sample_docs["metadatas"][:2] if sample_docs["metadatas"] else [],
                "embedding_dimensions": embedding_dims,
                "chunking_strategies": chunking_strategies,
                "metadata_keys": list(metadata_keys),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error getting collection details for {collection_name}: {e}")
            return {
                "name": collection_name,
                "error": str(e),
                "success": False
            }
    
    def list_collections(self) -> List[str]:
        """List all collections in ChromaDB."""
        try:
            if self.client is None:
                logger.error("Cannot list collections: ChromaDB client is None")
                return []
            
            try:
                collections = self.client.list_collections()
                # In ChromaDB v0.6.0+, list_collections returns a list of collection names (strings)
                # In older versions, it returned objects with a name attribute
                if collections and isinstance(collections[0], str):
                    # ChromaDB v0.6.0+ - collections is a list of strings
                    logger.info(f"Found {len(collections)} collections in ChromaDB at {self.db_path}")
                    return collections
                else:
                    # Older ChromaDB - collections is a list of objects with name attribute
                    try:
                        collection_names = [col.name for col in collections]
                        logger.info(f"Found {len(collection_names)} collections in ChromaDB at {self.db_path}")
                        return collection_names
                    except (AttributeError, NotImplementedError):
                        logger.warning(f"Unexpected collection format: {collections[0]}")
                        return []
                    
            except Exception as e:
                logger.error(f"Error listing ChromaDB collections: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error accessing ChromaDB: {e}")
            return []
            
    def get_document_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get document statistics from a collection."""
        try:
            if self.client is None:
                return {"error": "Failed to connect to ChromaDB"}
                
            collection = self.client.get_collection(collection_name)
            
            # Count by metadata values
            all_docs = collection.get(include=["metadatas"])
            
            # Track stats by different metadata fields
            stats = {
                "total_documents": len(all_docs["metadatas"]),
                "by_source": {},
                "by_chunk_unit": {},
                "by_chunking_strategy": {},
                "by_metadata_presence": {}
            }
            
            # Analyze metadata distribution
            for meta in all_docs["metadatas"]:
                if not meta:
                    continue
                    
                # Count by source
                if "source" in meta:
                    source = meta["source"]
                    stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
                
                # Count by chunk unit
                if "chunk_unit" in meta:
                    unit = meta["chunk_unit"]
                    stats["by_chunk_unit"][unit] = stats["by_chunk_unit"].get(unit, 0) + 1
                
                # Count by chunking strategy
                if "chunking_strategy" in meta:
                    strategy = meta["chunking_strategy"]
                    stats["by_chunking_strategy"][strategy] = stats["by_chunking_strategy"].get(strategy, 0) + 1
                
                # Count presence of each metadata field
                for key in meta:
                    stats["by_metadata_presence"][key] = stats["by_metadata_presence"].get(key, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting document stats: {e}")
            return {"error": str(e)}

    def get_advanced_diagnostics(self) -> Dict[str, Any]:
        """Perform advanced diagnostics on ChromaDB and SQLite.
        
        This method analyzes both the ChromaDB internal SQLite database and the 
        main application SQLite database to find inconsistencies and issues.
        
        Returns:
            Dictionary with diagnostic results
        """
        try:
            if self.client is None:
                return {
                    "success": False,
                    "error": "Failed to connect to ChromaDB",
                    "chromadb_path": self.db_path,
                }
            
            # Get ChromaDB collection names via API
            # These are just the raw collection names as strings
            collection_names = self.list_collections()
            
            # Convert to the same format as used in diagnostics
            chromadb_api_collections = [{"name": name, "count": 0} for name in collection_names]
            
            logger.info(f"API Collections: {collection_names}")
            
            # Connect to SQLite database
            sqlite_collections = self._get_sqlite_collections()
            logger.info(f"SQLite Collections: {[c['name'] for c in sqlite_collections]}")
            
            # Connect to ChromaDB SQLite database
            chromadb_internal_collections = self._get_chromadb_collections_from_sqlite()
            logger.info(f"ChromaDB Internal Collections: {[c['name'] for c in chromadb_internal_collections]}")
            
            # Examine UUID directories in ChromaDB
            uuid_dirs = self._examine_chromadb_directories()
            
            # Analyze segment info if available
            segment_info = self._analyze_segments()
            
            # Find mismatches
            mismatches = []
            
            # Check for collections in SQLite but not in ChromaDB
            for col in sqlite_collections:
                # We need to compare by name, not by ID
                col_name = col["name"].lower().strip()
                
                # Check in ChromaDB API collections
                found_in_api = any(name.lower().strip() == col_name for name in collection_names)
                
                # Check in ChromaDB internal collections
                found_in_internal = any(
                    internal_col["name"].lower().strip() == col_name 
                    for internal_col in chromadb_internal_collections
                )
                
                if not (found_in_api or found_in_internal):
                    mismatches.append({
                        "type": "missing_in_chromadb",
                        "name": col["name"],
                        "id": col["id"],
                        "severity": "high",
                        "message": f"Collection '{col['name']}' exists in SQLite but not in ChromaDB"
                    })
                elif not found_in_api and found_in_internal:
                    # Collection exists in internal ChromaDB but not in API
                    mismatches.append({
                        "type": "missing_in_chromadb_api",
                        "name": col["name"],
                        "id": col["id"],
                        "severity": "medium",
                        "message": f"Collection '{col['name']}' exists in SQLite and ChromaDB internal but not in ChromaDB API"
                    })
                elif found_in_api and not found_in_internal:
                    # Collection exists in API but not in internal ChromaDB
                    mismatches.append({
                        "type": "missing_in_chromadb_internal",
                        "name": col["name"],
                        "id": col["id"],
                        "severity": "medium",
                        "message": f"Collection '{col['name']}' exists in SQLite and ChromaDB API but not in internal ChromaDB"
                    })
            
            # Check for collections in ChromaDB but not in SQLite
            for name in collection_names:
                name_lower = name.lower().strip()
                found_in_sqlite = any(
                    sqlite_col["name"].lower().strip() == name_lower
                    for sqlite_col in sqlite_collections
                )
                
                if not found_in_sqlite:
                    mismatches.append({
                        "type": "missing_in_sqlite",
                        "name": name,
                        "severity": "medium",
                        "message": f"Collection '{name}' exists in ChromaDB but not in SQLite"
                    })
            
            # Check for UUID directories that don't match any collection
            for uuid_dir in uuid_dirs:
                uuid_value = uuid_dir['uuid']
                
                # Try to find this UUID in the ChromaDB internal collections
                matching_internal_collection = None
                for col in chromadb_internal_collections:
                    if col.get('id') == uuid_value:
                        matching_internal_collection = col
                        break
                
                if matching_internal_collection:
                    # UUID is associated with a collection in ChromaDB internal
                    # Check if it also exists in SQLite
                    collection_name = matching_internal_collection.get('name', '')
                    if collection_name:
                        matching_sqlite_collection = None
                        for col in sqlite_collections:
                            if col['name'].lower().strip() == collection_name.lower().strip():
                                matching_sqlite_collection = col
                                break
                        
                        if not matching_sqlite_collection:
                            # UUID exists in ChromaDB but not in SQLite
                            mismatches.append({
                                "type": "orphaned_uuid_not_in_sqlite",
                                "uuid": uuid_value,
                                "name": collection_name,
                                "files": uuid_dir["files"],
                                "severity": "medium",
                                "message": f"UUID directory '{uuid_value}' (collection '{collection_name}') exists in ChromaDB but not in SQLite"
                            })
                else:
                    # UUID doesn't match any known collection - truly orphaned
                    mismatches.append({
                        "type": "orphaned_uuid",
                        "uuid": uuid_value,
                        "files": uuid_dir["files"],
                        "severity": "medium",
                        "message": f"UUID directory '{uuid_value}' doesn't match any known ChromaDB collection"
                    })
            
            # Return all diagnostic data
            return {
                "success": True,
                "sqlite_collections": sqlite_collections,
                "chromadb_api_collections": chromadb_api_collections,
                "chromadb_internal_collections": chromadb_internal_collections,
                "uuid_directories": uuid_dirs,
                "segment_info": segment_info,
                "mismatches": mismatches,
                "total_mismatches": len(mismatches),
                "critical_mismatches": sum(1 for m in mismatches if m["severity"] == "high"),
                "medium_mismatches": sum(1 for m in mismatches if m["severity"] == "medium"),
                "minor_mismatches": sum(1 for m in mismatches if m["severity"] == "low")
            }
            
        except Exception as e:
            logger.error(f"Error performing advanced diagnostics: {e}")
            return {
                "success": False,
                "error": str(e),
                "chromadb_path": self.db_path
            }
    
    def _get_sqlite_collections(self) -> List[Dict[str, Any]]:
        """Get collections from the SQLite database"""
        # Define SQLite path
        sqlite_path = os.path.join(os.path.dirname(self.db_path), "lamb-kb-server.db")
        if not os.path.exists(sqlite_path):
            logger.error(f"SQLite database not found at: {sqlite_path}")
            return []
        
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, owner, creation_date, embeddings_model FROM collections")
        collections = [dict(row) for row in cursor.fetchall()]
        
        for collection in collections:
            # Format embeddings model if it's a JSON string
            if isinstance(collection['embeddings_model'], str):
                try:
                    collection['embeddings_model'] = json.loads(collection['embeddings_model'])
                except json.JSONDecodeError:
                    pass
        
        conn.close()
        return collections
    
    def _get_chromadb_collections_from_sqlite(self) -> List[Dict[str, Any]]:
        """Get collections directly from ChromaDB SQLite"""
        chroma_db_path = os.path.join(self.db_path, 'chroma.sqlite3')
        if not os.path.exists(chroma_db_path):
            logger.error(f"ChromaDB SQLite file not found at: {chroma_db_path}")
            return []
        
        conn = sqlite3.connect(chroma_db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        
        # First check the actual columns in the collections table
        try:
            cursor.execute("PRAGMA table_info(collections)")
            available_columns = [row[1] for row in cursor.fetchall()]
            
            if not available_columns:
                logger.warning("No columns found in collections table")
                conn.close()
                return []
            
            # Log available columns
            logger.info(f"Available columns in collections table: {available_columns}")
            
            # Construct a query based on available columns
            # In ChromaDB, the 'id' field is the UUID, not a simple integer ID
            query_columns = []
            if 'id' in available_columns:
                query_columns.append('id')
            if 'name' in available_columns:
                query_columns.append('name')
            
            if not query_columns:
                logger.warning("Required columns 'id' and 'name' not found in collections table")
                conn.close()
                return []
            
            # Execute the query to get collections
            query = f"SELECT {', '.join(query_columns)} FROM collections"
            cursor.execute(query)
            
            collections = []
            for row in cursor.fetchall():
                collection_data = {}
                for i, col_name in enumerate(query_columns):
                    collection_data[col_name] = row[i]
                
                # Validate UUID format if present
                if 'id' in collection_data:
                    try:
                        # Try to parse as UUID to validate
                        uuid_obj = uuid.UUID(collection_data['id'])
                        # It's a valid UUID
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid UUID format for collection {collection_data.get('name', 'unknown')}: {collection_data['id']}")
                
                collections.append(collection_data)
            
            # Log the results
            logger.info(f"Found {len(collections)} collections in ChromaDB SQLite")
            for col in collections:
                logger.info(f"Collection from ChromaDB SQLite: name='{col.get('name', '')}', id='{col.get('id', '')}'")
            
            # Get additional metadata if available
            if 'collection_metadata' in self._get_table_names(conn):
                for collection in collections:
                    if 'id' not in collection:
                        continue
                    
                    try:
                        metadata_cursor = conn.cursor()
                        # Check columns in collection_metadata table first
                        metadata_cursor.execute("PRAGMA table_info(collection_metadata)")
                        metadata_columns = [row[1] for row in metadata_cursor.fetchall()]
                        
                        # Adjust query based on available columns
                        if 'key' in metadata_columns and 'value' in metadata_columns:
                            metadata_cursor.execute("SELECT key, value FROM collection_metadata WHERE collection_id = ?", 
                                                  (collection['id'],))
                            metadata = {row[0]: row[1] for row in metadata_cursor.fetchall()}
                        elif 'key' in metadata_columns and 'str_value' in metadata_columns:
                            # Some versions use 'str_value' instead of 'value'
                            metadata_cursor.execute("SELECT key, str_value FROM collection_metadata WHERE collection_id = ?", 
                                                  (collection['id'],))
                            metadata = {row[0]: row[1] for row in metadata_cursor.fetchall()}
                        else:
                            logger.warning(f"Cannot fetch metadata - columns missing. Available: {metadata_columns}")
                            metadata = {}
                            
                        collection['metadata'] = metadata
                    except Exception as e:
                        logger.error(f"Error fetching metadata for collection {collection.get('id', 'unknown')}: {e}")
            
            conn.close()
            return collections
            
        except Exception as e:
            logger.error(f"Error querying ChromaDB SQLite: {e}")
            conn.close()
            return []
    
    def _get_table_names(self, conn) -> List[str]:
        """Get all table names from a SQLite connection"""
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cursor.fetchall()]
    
    def _examine_chromadb_directories(self) -> List[Dict[str, Any]]:
        """Examine UUIDs in the ChromaDB directory"""
        if not self.db_path or not os.path.exists(self.db_path):
            logger.error(f"ChromaDB directory not found at: {self.db_path}")
            return []
        
        # Get all directory entries that look like UUIDs
        contents = os.listdir(self.db_path)
        uuid_dirs = []
        
        for item in contents:
            # Check if it's a directory and looks like a UUID
            item_path = os.path.join(self.db_path, item)
            if os.path.isdir(item_path):
                try:
                    # Try to parse as UUID to validate
                    uuid_obj = uuid.UUID(item)
                    uuid_dirs.append({
                        'uuid': item,
                        'path': item_path,
                        'files': os.listdir(item_path)
                    })
                except (ValueError, TypeError):
                    # Not a UUID, ignore
                    pass
                    
        return uuid_dirs
    
    def _analyze_segments(self) -> Dict[str, Any]:
        """Analyze ChromaDB segments"""
        chroma_db_path = os.path.join(self.db_path, 'chroma.sqlite3')
        if not os.path.exists(chroma_db_path):
            logger.error(f"ChromaDB SQLite file not found at: {chroma_db_path}")
            return {}
        
        conn = sqlite3.connect(chroma_db_path)
        cursor = conn.cursor()
        
        tables = self._get_table_names(conn)
        
        if 'segments' not in tables or 'embeddings' not in tables:
            conn.close()
            return {"error": "Segments or embeddings table not found"}
        
        # Check segments table structure
        cursor.execute("PRAGMA table_info(segments)")
        segment_columns = [row[1] for row in cursor.fetchall()]
        
        # Check embeddings table structure
        cursor.execute("PRAGMA table_info(embeddings)")
        embedding_columns = [row[1] for row in cursor.fetchall()]
        
        # Get segment data
        segments_data = []
        
        if 'id' in segment_columns and 'collection' in segment_columns:
            cursor.execute("SELECT id, collection FROM segments")
            for row in cursor.fetchall():
                segment_id, collection_id = row
                
                # Count embeddings in this segment
                if 'segment_id' in embedding_columns:
                    cursor.execute("SELECT COUNT(*) FROM embeddings WHERE segment_id = ?", (segment_id,))
                    embedding_count = cursor.fetchone()[0]
                else:
                    embedding_count = "unknown"
                
                segments_data.append({
                    "id": segment_id,
                    "collection_id": collection_id,
                    "embedding_count": embedding_count
                })
        
        conn.close()
        
        return {
            "segment_columns": segment_columns,
            "embedding_columns": embedding_columns,
            "segments": segments_data
        }

# Create client instances
client = LambKBClient(BASE_URL, API_KEY)
chroma_helper = ChromaDBHelper(CHROMADB_PATHS)

@app.route('/')
def index():
    """Home page."""
    try:
        # Check if the API is available
        health = client._request("get", "/health")
        api_status = "Connected" if health.get("status") == "ok" else "Error"
        api_error = None
    except Exception as e:
        api_status = "Error"
        api_error = str(e)
    
    return render_template('index.html', api_status=api_status, api_error=api_error)

@app.route('/collections', methods=['GET'])
def list_collections():
    """List collections, optionally filtered by owner."""
    owner = request.args.get('owner', '')
    try:
        if owner:
            # Use the updated list_collections method without owner parameter
            collections = client.list_collections()
            # Filter by owner in memory instead if needed
            if collections and 'items' in collections:
                collections['items'] = [col for col in collections['items'] if col.get('owner') == owner]
        else:
            collections = client.list_collections()
        return render_template('collections.html', collections=collections.get('items', []), owner=owner)
    except Exception as e:
        flash(f"Error fetching collections: {str(e)}", "error")
        return render_template('collections.html', collections=[], owner=owner)

@app.route('/collections/create', methods=['GET', 'POST'])
def create_collection():
    """Create a new collection."""
    if request.method == 'POST':
        try:
            # Get form data
            collection_data = {
                "name": request.form.get('name'),
                "description": request.form.get('description'),
                "owner": request.form.get('owner'),
                "visibility": request.form.get('visibility')
            }
            
            # Handle embeddings model configuration
            embeddings_type = request.form.get('embeddings_type')
            
            if embeddings_type == 'default':
                # Use 'default' for all embeddings model parameters
                collection_data["embeddings_model"] = {
                    "model": "default",
                    "vendor": "default",
                    "apikey": "default"
                }
            else:
                # Custom embeddings configuration
                vendor = request.form.get('vendor', '')
                model = request.form.get('model', '')
                api_key = request.form.get('apikey', '')
                
                # If using OpenAI but no API key provided, default to environment
                if vendor.lower() == 'openai' and not api_key:
                    api_key = "default"
                    logger.info("Using default OpenAI API key from environment")
                
                # Create a copy of the actual API key for logging
                api_key_for_logging = '****' if api_key else 'None'
                
                collection_data["embeddings_model"] = {
                    "model": model,
                    "vendor": vendor,
                    "apikey": api_key
                }
                
                # Add API endpoint if provided
                api_endpoint = request.form.get('api_endpoint')
                if api_endpoint:
                    collection_data["embeddings_model"]["api_endpoint"] = api_endpoint
            
            # Log the request data for debugging without exposing API key
            safe_data = json.loads(json.dumps(collection_data))  # Deep copy without shared references
            if 'embeddings_model' in safe_data:
                # Replace API key for logging only
                if 'apikey' in safe_data['embeddings_model']:
                    safe_data['embeddings_model']['apikey'] = '[REDACTED]'
            logger.info(f"Creating collection '{safe_data['name']}' with {safe_data['embeddings_model']['vendor']} embeddings model {safe_data['embeddings_model']['model']}")
            
            # Create the collection with the ORIGINAL data
            new_collection = client.create_collection(collection_data)
            
            # Log the full response for debugging
            logger.info(f"API Response: {json.dumps(new_collection) if isinstance(new_collection, dict) else str(new_collection)}")
            
            if isinstance(new_collection, dict) and 'error' in new_collection:
                logger.error(f"API returned error: {new_collection['error']}")
                flash(f"Error creating collection: {new_collection['error']}", "error")
                return render_template('create_collection.html')
                
            # If we have a dictionary response, extract fields safely
            collection_id = None
            collection_name = collection_data.get('name')  # Default to submitted name
            
            if isinstance(new_collection, dict):
                collection_id = new_collection.get('id')
                if 'name' in new_collection:
                    collection_name = new_collection.get('name')
                
                # Log all fields in the response
                logger.info(f"Response fields: {', '.join(new_collection.keys())}")
                
                # Log the ChromaDB UUID if present
                if 'chromadb_uuid' in new_collection:
                    logger.info(f"Collection created with ChromaDB UUID: {new_collection['chromadb_uuid']}")
            else:
                # If it's not a dictionary (possibly an object from _dict_to_obj)
                try:
                    collection_id = getattr(new_collection, 'id', None)
                    if hasattr(new_collection, 'name'):
                        collection_name = new_collection.name
                    logger.info(f"Response object attributes: {dir(new_collection)}")
                except Exception as attr_error:
                    logger.error(f"Error processing response object: {attr_error}")
            
            # Successful creation - flash a message and redirect
            flash(f"Collection '{collection_name}' created successfully!", "success")
            
            try:
                # Try to redirect to the collection details page
                if collection_id:
                    logger.info(f"Redirecting to collection ID: {collection_id}")
                    return redirect(url_for('view_collection', collection_id=collection_id))
                else:
                    # If no ID, try to find by name
                    logger.warning(f"No ID in response, attempting to find collection by name: {collection_name}")
                    found = client.get_collection_by_name(collection_name)
                    if found and (isinstance(found, dict) and 'id' in found or hasattr(found, 'id')):
                        found_id = found.id if hasattr(found, 'id') else found.get('id')
                        logger.info(f"Found collection by name, ID: {found_id}")
                        return redirect(url_for('view_collection', collection_id=found_id))
            except Exception as redirect_error:
                logger.error(f"Error during redirect: {redirect_error}")
                
            # Fall back to collections list
            logger.info("Falling back to collections list")
            return redirect(url_for('list_collections'))
            
        except Exception as e:
            logger.error(f"Exception in create_collection: {str(e)}")
            # Log exception traceback
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            flash(f"Error creating collection: {str(e)}", "error")
            return render_template('create_collection.html')
    
    # For GET requests or if there was an error, show the form
    return render_template('create_collection.html')

@app.route('/collections/<int:collection_id>')
def view_collection(collection_id):
    """View detailed information about a collection."""
    try:
        collection = client.get_collection(collection_id)
        files = client.list_files(collection_id)
        
        # Calculate some statistics - handle both dict and object access
        def get_value(obj, key, default=0):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)
        
        total_documents = sum(get_value(file, 'document_count', 0) for file in files)
        file_count = len(files)
        
        return render_template(
            'collection_details.html', 
            collection=collection, 
            files=files, 
            file_count=file_count,
            total_documents=total_documents
        )
    except Exception as e:
        flash(f"Error fetching collection details: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/collections/<int:collection_id>/ingest-file', methods=['POST'])
def ingest_file(collection_id):
    """Ingest a file to a collection using the SimpleIngestPlugin."""
    try:
        # Get the file from the request
        if 'file' not in request.files:
            flash("No file part in the request", "error")
            return redirect(url_for('view_collection', collection_id=collection_id))
            
        file = request.files['file']
        if file.filename == '':
            flash("No file selected", "error")
            return redirect(url_for('view_collection', collection_id=collection_id))
            
        # Validate file extension
        filename = file.filename
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if file_ext not in {'txt', 'md', 'markdown', 'text'}:
            flash(f"Unsupported file type: .{file_ext}. Only .txt, .md, .markdown, and .text files are supported.", "error")
            return redirect(url_for('view_collection', collection_id=collection_id))
        
        # Get plugin parameters from the form
        plugin_name = request.form.get('plugin_name', 'simple_ingest')
        
        # Parse plugin parameters from form or use defaults
        try:
            plugin_params = request.form.get('plugin_params', '{}')
            params = json.loads(plugin_params)
        except json.JSONDecodeError:
            # If JSON parsing fails, try to get parameters individually
            chunk_size = request.form.get('chunk_size', 1000)
            chunk_unit = request.form.get('chunk_unit', 'char')
            chunk_overlap = request.form.get('chunk_overlap', 200)
            params = {
                'chunk_size': int(chunk_size),
                'chunk_unit': chunk_unit,
                'chunk_overlap': int(chunk_overlap)
            }
        
        # Use the client method to make the API call
        result = client.ingest_file_to_collection(
            collection_id=collection_id,
            file=file,
            plugin_name=plugin_name,
            plugin_params=params
        )
        
        # Show success message
        # Handle different response structures safely with fallbacks
        original_filename = result.get('original_filename', filename)
        documents_added = result.get('documents_added', 0)
        flash(f"Successfully ingested file '{original_filename}' and created {documents_added} documents.", "success")
        
    except requests.exceptions.HTTPError as e:
        error_message = "API Error"
        try:
            error_detail = e.response.json().get('detail', str(e))
            error_message = f"API Error: {error_detail}"
        except:
            error_message = f"API Error: {str(e)}"
        flash(error_message, "error")
    except Exception as e:
        flash(f"Error ingesting file: {str(e)}", "error")
        print(f"Detailed error: {type(e).__name__}: {e}")
    
    return redirect(url_for('view_collection', collection_id=collection_id))



@app.route('/collections/<int:collection_id>/ingest-url', methods=['POST'])
def ingest_url(collection_id):
    """Ingest URLs to a collection using the URLIngestPlugin."""
    try:
        # Get request data
        data = request.json
        if not data or 'urls' not in data:
            return jsonify({"error": "Invalid request data. URLs are required."}), 400
            
        urls = data.get('urls', [])
        if not urls:
            return jsonify({"error": "No URLs provided"}), 400

        # Get plugin parameters from the request or use defaults
        plugin_params = data.get('plugin_params', {})
        if not plugin_params:
            plugin_params = {
                'chunk_size': 1000,
                'chunk_unit': 'char',
                'chunk_overlap': 200
            }
            
        # Forward the API key from the webapp request
        # Use the client method to make the API call
        result = client.ingest_urls_to_collection(
            collection_id=collection_id,
            urls=urls,
            plugin_params=plugin_params
        )
        
        # Return success response
        return jsonify(result)
        
    except requests.exceptions.HTTPError as e:
        error_message = "API Error"
        try:
            error_detail = e.response.json().get('detail', str(e))
            return jsonify({"error": error_detail}), e.response.status_code
        except:
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Detailed error: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500
        
@app.route('/preview-url', methods=['POST'])
def preview_url():
    """Preview content from a URL without ingesting it."""
    try:
        # Get request data
        data = request.json
        if not data or 'url' not in data:
            return jsonify({"error": "Invalid request data. URL is required."}), 400
            
        url = data.get('url', '')
        if not url:
            return jsonify({"error": "No URL provided"}), 400
            
        # Use the client method to make the API call
        result = client.preview_url_content(url=url)
        
        # Return the preview result
        return jsonify(result)
        
    except requests.exceptions.HTTPError as e:
        error_message = "API Error"
        try:
            error_detail = e.response.json().get('detail', str(e))
            return jsonify({"error": error_detail}), e.response.status_code
        except:
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Detailed error: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/files/<int:file_id>/content', methods=['GET'])
def get_file_content(file_id):
    """Get the content of a file, especially for ingested URLs."""
    try:
        # Use the client method to make the API call
        result = client.get_file_content(file_id=file_id)
        
        # Return the file content
        return jsonify(result)
        
    except requests.exceptions.HTTPError as e:
        error_message = "API Error"
        try:
            error_detail = e.response.json().get('detail', str(e))
            return jsonify({"error": error_detail}), e.response.status_code
        except:
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Detailed error: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/collections/<int:collection_id>/query', methods=['GET', 'POST'])
def query_collection(collection_id):
    """Query a collection and display results."""
    try:
        collection = client.get_collection(collection_id)
        
        if request.method == 'POST':
            query_text = request.form.get('query_text', '')
            top_k = int(request.form.get('top_k', 5))
            threshold = float(request.form.get('threshold', 0.0))
            include_all_metadata = request.form.get('include_all_metadata') == 'on'
            
            if not query_text:
                flash("Please enter a query text", "error")
                return render_template('query.html', collection=collection)
            
            # Create plugin params for metadata filtering if needed
            plugin_params = {}
            if include_all_metadata:
                plugin_params["include_metadata"] = True
            
            try:
                # Query the collection
                results = client.query_collection(
                    collection_id, 
                    query_text, 
                    top_k, 
                    threshold,
                    plugin_name="simple_query", 
                    plugin_params=plugin_params
                )
                
                # Log the results for debugging
                logger.info(f"Query results count: {results.count if hasattr(results, 'count') else 0}")
                
                # Ensure results has the _data attribute
                if not hasattr(results, '_data'):
                    # If the results object doesn't have _data, it might not be properly converted
                    # Convert the raw dictionary to our custom object format
                    if isinstance(results, dict):
                        results = client._dict_to_obj(results)
                    else:
                        # Create a basic structure if we have something unexpected
                        results = client._dict_to_obj({
                            "results": [],
                            "count": 0,
                            "timing": {"total_time": "Unknown"}
                        })
                
                # Make sure timing is properly formatted
                if hasattr(results, 'timing'):
                    # Convert timing to a simple dict if it's not already
                    if not isinstance(results.timing, dict):
                        timing_dict = {"total_time": str(results.timing)}
                        results._data['timing'] = timing_dict
                else:
                    results._data['timing'] = {"total_time": "Unknown"}
                
                # Handle case where results.results might be None
                if not hasattr(results, 'results') or results.results is None:
                    results._data['results'] = []
                    results._data['count'] = 0
                
                # Fix the count field if it doesn't match results
                if hasattr(results, 'results') and isinstance(results.results, list):
                    results._data['count'] = len(results.results)
                    
                    # Ensure all results have valid metadata attributes
                    for i, result in enumerate(results.results):
                        if not hasattr(result, 'metadata') or result.metadata is None:
                            results._data['results'][i]['metadata'] = {}
                
                # Render the query results
                return render_template(
                    'query_results.html', 
                    collection=collection, 
                    query_text=query_text,
                    top_k=top_k,
                    threshold=threshold,
                    results=results,
                    include_all_metadata=include_all_metadata
                )
            except requests.exceptions.HTTPError as e:
                error_message = "API Error"
                try:
                    if hasattr(e, "response") and e.response is not None:
                        error_detail = e.response.json().get('detail', str(e))
                        error_message = f"API Error: {error_detail}"
                except:
                    error_message = f"API Error: {str(e)}"
                
                flash(error_message, "error")
                print(f"Query error: {error_message}")
                return render_template('query.html', collection=collection)
            except Exception as e:
                logger.error(f"Error in query processing: {str(e)}")
                logger.error(f"Error type: {type(e).__name__}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                flash(f"Error processing query results: {str(e)}", "error")
                return render_template('query.html', collection=collection)
        
        return render_template('query.html', collection=collection)
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        print(f"Exception in query_collection: {type(e).__name__}: {e}")
        return redirect(url_for('view_collection', collection_id=collection_id))

@app.route('/debug/chromadb')
def debug_chromadb():
    """Debug ChromaDB collections."""
    try:
        # Get path info for debugging
        paths_info = []
        for path in CHROMADB_PATHS:
            exists = os.path.exists(path)
            paths_info.append({
                "path": path,
                "exists": exists,
                "is_current": path == chroma_helper.db_path
            })
        
        # Get collections from different sources
        api_collections = chroma_helper.list_collections()
        logger.info(f"Raw API Collections: {api_collections}")
        
        # Get diagnostics data
        diagnostics = chroma_helper.get_advanced_diagnostics()
        
        sqlite_collections = diagnostics.get('sqlite_collections', [])
        chromadb_internal_collections = diagnostics.get('chromadb_internal_collections', [])
        
        # Create explicit mapping for template
        collection_mapping = []
        
        # First add SQLite collections
        for col in sqlite_collections:
            col_name_lower = col['name'].lower().strip()
            
            # Find in API collections
            found_in_api = False
            api_name = None
            for api_col in api_collections:
                if col_name_lower == api_col.lower().strip():
                    found_in_api = True
                    api_name = api_col
                    break
            
            # Find in internal collections
            found_uuid = None
            for internal_col in chromadb_internal_collections:
                if col_name_lower == internal_col['name'].lower().strip():
                    found_uuid = internal_col['id']
                    break
            
            collection_mapping.append({
                'sqlite_name': col['name'],
                'sqlite_id': col['id'],
                'chroma_name': api_name if found_in_api else None,
                'uuid': found_uuid,
                'found_in_api': found_in_api,
                'found_uuid': found_uuid is not None
            })
        
        # Then add ChromaDB collections not in SQLite
        for api_col in api_collections:
            api_name_lower = api_col.lower().strip()
            
            # Check if this API collection is already in the mapping
            already_mapped = False
            for mapping in collection_mapping:
                if mapping['chroma_name'] and mapping['chroma_name'].lower().strip() == api_name_lower:
                    already_mapped = True
                    break
            
            if not already_mapped:
                # Find in internal collections
                found_uuid = None
                for internal_col in chromadb_internal_collections:
                    internal_name = internal_col.get('name', '').lower().strip() 
                    if api_name_lower == internal_name:
                        found_uuid = internal_col.get('id', '')
                        break
                
                mapping = {
                    'sqlite_name': None,
                    'sqlite_id': None, 
                    'chroma_name': api_col,
                    'uuid': found_uuid,
                    'found_in_api': True,
                    'found_uuid': found_uuid is not None and found_uuid != '',
                    'only_in_chroma': True
                }
                collection_mapping.append(mapping)
        
        # Print some debug info
        logger.info(f"Collection Mapping: {collection_mapping}")
        
        return render_template('debug_chromadb.html', 
                               collections=api_collections,
                               sqlite_collections=sqlite_collections,
                               chromadb_internal_collections=chromadb_internal_collections,
                               collection_mapping=collection_mapping,
                               db_path=chroma_helper.db_path,
                               paths_info=paths_info)
    except Exception as e:
        logger.error(f"Error accessing ChromaDB: {str(e)}")
        return redirect(url_for('index'))

@app.route('/debug/chromadb/<collection_name>')
def debug_collection(collection_name):
    """Debug a specific ChromaDB collection."""
    try:
        collection_details = chroma_helper.get_collection_details(collection_name)
        document_stats = chroma_helper.get_document_stats(collection_name)
        
        # Get all KB collections to map ID to name
        kb_collections = client.list_collections().get('items', [])
        kb_collection_map = {col['name']: col for col in kb_collections}
        
        # Find matching KB collection
        kb_collection = kb_collection_map.get(collection_name, {})
        
        return render_template(
            'debug_collection.html',
            collection_details=collection_details,
            document_stats=document_stats,
            kb_collection=kb_collection
        )
    except Exception as e:
        flash(f"Error inspecting ChromaDB collection: {str(e)}", "error")
        return redirect(url_for('debug_chromadb'))

@app.route('/api/collections')
def api_list_collections():
    """API endpoint to list collections."""
    owner = request.args.get('owner', '')
    try:
        if owner:
            # Use the updated list_collections method without owner parameter
            collections = client.list_collections()
            # Filter by owner in memory instead if needed
            if collections and 'items' in collections:
                collections['items'] = [col for col in collections['items'] if col.get('owner') == owner]
        else:
            collections = client.list_collections()
        return jsonify(collections)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/collections/<int:collection_id>')
def api_get_collection(collection_id):
    """API endpoint to get collection details."""
    try:
        collection = client.get_collection(collection_id)
        files = client.list_files(collection_id)
        
        # Add calculated statistics
        collection['file_count'] = len(files)
        collection['total_documents'] = sum(file.get('document_count', 0) for file in files)
        collection['files'] = files
        
        return jsonify(collection)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/collections/<int:collection_id>/query', methods=['POST'])
def api_query_collection(collection_id):
    """API endpoint to query a collection."""
    try:
        data = request.get_json()
        query_text = data.get('query_text', '')
        top_k = int(data.get('top_k', 5))
        threshold = float(data.get('threshold', 0.0))
        plugin_name = data.get('plugin_name', 'simple_query')
        plugin_params = data.get('plugin_params', {})
        
        if not query_text:
            return jsonify({"error": "Query text is required"}), 400
        
        results = client.query_collection(
            collection_id, 
            query_text, 
            top_k, 
            threshold, 
            plugin_name=plugin_name,
            plugin_params=plugin_params
        )
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/chromadb')
def api_list_chromadb_collections():
    """API endpoint to list ChromaDB collections."""
    try:
        collections = chroma_helper.list_collections()
        return jsonify({"collections": collections, "db_path": chroma_helper.db_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/chromadb/<collection_name>')
def api_debug_collection(collection_name):
    """API endpoint to debug a ChromaDB collection."""
    try:
        collection_details = chroma_helper.get_collection_details(collection_name)
        document_stats = chroma_helper.get_document_stats(collection_name)
        
        return jsonify({
            "collection_details": collection_details,
            "document_stats": document_stats
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/debug/diagnostics')
def advanced_diagnostics():
    """Display advanced diagnostic information about ChromaDB and SQLite."""
    try:
        # Run diagnostics to get basic information
        diagnostics_raw = chroma_helper.get_advanced_diagnostics()
        
        # Get raw collections from different sources
        api_collections = chroma_helper.list_collections()
        logger.info(f"Advanced Diagnostics Raw API Collections: {api_collections}")
        
        sqlite_collections = diagnostics_raw.get('sqlite_collections', [])
        chromadb_internal_collections = diagnostics_raw.get('chromadb_internal_collections', [])
        
        # Print detailed debug info about collections
        logger.info(f"API Collections {len(api_collections)}: {api_collections}")
        logger.info(f"SQLite Collections {len(sqlite_collections)}: {[c['name'] for c in sqlite_collections]}")
        logger.info(f"ChromaDB Internal Collections {len(chromadb_internal_collections)}: {[(c.get('name', ''), c.get('id', '')) for c in chromadb_internal_collections]}")
        
        # Create proper collection mappings (same logic as debug_chromadb)
        collection_mapping = []
        mismatches = []
        
        # First add SQLite collections
        for col in sqlite_collections:
            col_name_lower = col['name'].lower().strip()
            
            # Find in API collections
            found_in_api = False
            api_name = None
            for api_col in api_collections:
                if col_name_lower == api_col.lower().strip():
                    found_in_api = True
                    api_name = api_col
                    break
            
            # Find in internal collections
            found_uuid = None
            matching_internal = None
            for internal_col in chromadb_internal_collections:
                internal_name = internal_col.get('name', '').lower().strip()
                if col_name_lower == internal_name:
                    found_uuid = internal_col.get('id', '')
                    matching_internal = internal_col
                    break
            
            # Log detailed debug info for this mapping
            logger.info(f"SQLite collection '{col['name']}': API match: {api_name}, UUID: {found_uuid}")
            
            mapping = {
                'sqlite_name': col['name'],
                'sqlite_id': col['id'],
                'chroma_name': api_name if found_in_api else None,
                'uuid': found_uuid,
                'found_in_api': found_in_api,
                'found_uuid': found_uuid is not None and found_uuid != '',
                'stored_uuid': col.get('chromadb_uuid'),  # Add stored UUID from SQLite
                'uuid_match': found_uuid == col.get('chromadb_uuid') if found_uuid and col.get('chromadb_uuid') else False
            }
            collection_mapping.append(mapping)
            
            # Add mismatches if necessary
            if not (found_in_api or found_uuid):
                mismatches.append({
                    "type": "missing_in_chromadb",
                    "name": col["name"],
                    "id": col["id"],
                    "severity": "high",
                    "message": f"Collection '{col['name']}' exists in SQLite but not in ChromaDB"
                })
            elif not found_in_api and found_uuid:
                mismatches.append({
                    "type": "missing_in_chromadb_api",
                    "name": col["name"],
                    "id": col["id"],
                    "severity": "medium",
                    "message": f"Collection '{col['name']}' exists in SQLite and ChromaDB internal but not in ChromaDB API"
                })
            elif found_in_api and not found_uuid:
                mismatches.append({
                    "type": "missing_in_chromadb_internal",
                    "name": col["name"],
                    "id": col["id"],
                    "severity": "medium",
                    "message": f"Collection '{col['name']}' exists in SQLite and ChromaDB API but not in internal ChromaDB"
                })
            elif found_uuid and col.get('chromadb_uuid') and found_uuid != col.get('chromadb_uuid'):
                mismatches.append({
                    "type": "uuid_mismatch",
                    "name": col["name"],
                    "id": col["id"],
                    "severity": "high",
                    "message": f"Collection '{col['name']}' has UUID mismatch: SQLite={col.get('chromadb_uuid')}, ChromaDB={found_uuid}"
                })
        
        # Then add ChromaDB collections not in SQLite
        for api_col in api_collections:
            api_name_lower = api_col.lower().strip()
            
            # Check if this API collection is already in the mapping
            already_mapped = False
            for mapping in collection_mapping:
                if mapping['chroma_name'] and mapping['chroma_name'].lower().strip() == api_name_lower:
                    already_mapped = True
                    break
            
            if not already_mapped:
                # Find in internal collections
                found_uuid = None
                for internal_col in chromadb_internal_collections:
                    internal_name = internal_col.get('name', '').lower().strip() 
                    if api_name_lower == internal_name:
                        found_uuid = internal_col.get('id', '')
                        break
                
                mapping = {
                    'sqlite_name': None,
                    'sqlite_id': None, 
                    'chroma_name': api_col,
                    'uuid': found_uuid,
                    'found_in_api': True,
                    'found_uuid': found_uuid is not None and found_uuid != '',
                    'only_in_chroma': True,
                    'stored_uuid': None
                }
                collection_mapping.append(mapping)
                
                # Add mismatch
                mismatches.append({
                    "type": "missing_in_sqlite",
                    "name": api_col,
                    "severity": "medium",
                    "message": f"Collection '{api_col}' exists in ChromaDB but not in SQLite"
                })
        
        # Replace mismatches in diagnostics with our corrected version
        diagnostics = diagnostics_raw.copy()
        diagnostics['mismatches'] = mismatches
        diagnostics['collection_mapping'] = collection_mapping
        diagnostics['total_mismatches'] = len(mismatches)
        diagnostics['critical_mismatches'] = sum(1 for m in mismatches if m["severity"] == "high")
        diagnostics['medium_mismatches'] = sum(1 for m in mismatches if m["severity"] == "medium")
        diagnostics['minor_mismatches'] = sum(1 for m in mismatches if m["severity"] == "low")
        
        # Add UUID-specific statistics
        diagnostics['uuid_stats'] = {
            'total_collections': len(collection_mapping),
            'collections_with_uuid': sum(1 for m in collection_mapping if m['found_uuid']),
            'collections_with_stored_uuid': sum(1 for m in collection_mapping if m['stored_uuid']),
            'uuid_matches': sum(1 for m in collection_mapping if m['uuid_match']),
            'uuid_mismatches': sum(1 for m in collection_mapping if m['found_uuid'] and m['stored_uuid'] and m['found_uuid'] != m['stored_uuid'])
        }
        
        return render_template(
            'advanced_diagnostics.html',
            diagnostics=diagnostics,
            db_path=chroma_helper.db_path
        )
    except Exception as e:
        flash(f"Error running diagnostics: {str(e)}", "error")
        return redirect(url_for('debug_chromadb'))

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    
    # Log ChromaDB connection status
    if chroma_helper.client:
        logger.info(f"Successfully connected to ChromaDB at: {chroma_helper.db_path}")
        collections = chroma_helper.list_collections()
        logger.info(f"Found {len(collections)} collections: {', '.join(collections)}")
    else:
        logger.error("Failed to connect to ChromaDB. Debug paths:")
        for path in CHROMADB_PATHS:
            if os.path.exists(path):
                logger.info(f"  Path exists: {path}")
                try:
                    files = os.listdir(path)
                    logger.info(f"  Contents: {files[:10]}")
                except Exception as e:
                    logger.error(f"  Error listing contents: {e}")
            else:
                logger.warning(f"  Path does not exist: {path}")
    
    # Run the Flask application
    app.run(host='0.0.0.0', port=8080, debug=True) 