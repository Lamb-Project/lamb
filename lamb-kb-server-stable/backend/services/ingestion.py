"""
Document ingestion service.

This module provides services for ingesting documents into collections using various plugins.
"""

import os
import shutil
import uuid
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, BinaryIO, Union

import chromadb
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_embedding_function
from database.models import Collection, FileRegistry, FileStatus, KnowledgeStoreSetup
from database.service import CollectionService
from knowledge_store import get_knowledge_store
from plugins.base import PluginRegistry, IngestPlugin


class IngestionService:
    """Service for ingesting documents into collections."""
    
    # Base directory for storing uploaded files
    STATIC_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "static"
    
    # URL prefix for accessing static files
    STATIC_URL_PREFIX = os.getenv("HOME_URL", "http://localhost:9090") + "/static"
    
    @classmethod
    def _ensure_dirs(cls):
        """Ensure necessary directories exist."""
        cls.STATIC_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def _get_user_dir(cls, owner: str) -> Path:
        """Get the user's root directory for documents.
        
        Args:
            owner: Owner of the documents
            
        Returns:
            Path to the user's document directory
        """
        user_dir = cls.STATIC_DIR / owner
        user_dir.mkdir(exist_ok=True)
        return user_dir
    
    @classmethod
    def _get_collection_dir(cls, owner: str, collection_name: str) -> Path:
        """Get the collection directory for a user.
        
        Args:
            owner: Owner of the collection
            collection_name: Name of the collection
            
        Returns:
            Path to the collection directory
        """
        collection_dir = cls._get_user_dir(owner) / collection_name
        collection_dir.mkdir(exist_ok=True)
        return collection_dir
    
    @classmethod
    def save_uploaded_file(cls, file: UploadFile, owner: str, collection_name: str) -> Dict[str, str]:
        """Save an uploaded file to the appropriate directory.
        
        Args:
            file: The uploaded file
            owner: Owner of the collection
            collection_name: Name of the collection
            
        Returns:
            Dictionary with file path and URL
        """
        print(f"DEBUG: [save_uploaded_file] Starting to save file: {file.filename if file else 'None'}")
        cls._ensure_dirs()
        
        # Create a unique filename to avoid collisions
        original_filename = file.filename or "unknown"
        file_extension = original_filename.split(".")[-1] if "." in original_filename else ""
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}" if file_extension else f"{uuid.uuid4().hex}"
        print(f"DEBUG: [save_uploaded_file] Generated unique filename: {unique_filename}")
        
        # Store original filename as part of the metadata
        sanitized_original_name = os.path.basename(original_filename)
        
        # Get the collection directory and prepare the file path
        collection_dir = cls._get_collection_dir(owner, collection_name)
        file_path = collection_dir / unique_filename
        print(f"DEBUG: [save_uploaded_file] File will be saved to: {file_path}")
        
        try:
            # Save the file
            print(f"DEBUG: [save_uploaded_file] Starting file copy operation")
            with open(file_path, "wb") as f:
                # Read in chunks to avoid memory issues with large files
                print(f"DEBUG: [save_uploaded_file] Reading file content")
                content = file.file.read()
                print(f"DEBUG: [save_uploaded_file] File content read, size: {len(content)} bytes")
                f.write(content)
            print(f"DEBUG: [save_uploaded_file] File saved successfully")
            
            # Create URL path for the file
            relative_path = file_path.relative_to(cls.STATIC_DIR)
            file_url = f"{cls.STATIC_URL_PREFIX}/{relative_path}"
            
            result = {
                "file_path": str(file_path),
                "file_url": file_url,
                "original_filename": sanitized_original_name
            }
            print(f"DEBUG: [save_uploaded_file] File saved, returning result")
            return result
        except Exception as e:
            print(f"DEBUG: [save_uploaded_file] ERROR saving file: {str(e)}")
            import traceback
            print(f"DEBUG: [save_uploaded_file] Stack trace:\n{traceback.format_exc()}")
            raise
    
    @classmethod
    def register_file(cls, 
                     db: Session, 
                     collection_id: int, 
                     file_path: str, 
                     file_url: str, 
                     original_filename: str, 
                     plugin_name: str, 
                     plugin_params: Dict[str, Any],
                     owner: str,
                     document_count: int = 0,
                     content_type: Optional[str] = None,
                     status: FileStatus = FileStatus.COMPLETED) -> FileRegistry:
        """Register a file in the FileRegistry table.
        
        Args:
            db: Database session
            collection_id: ID of the collection
            file_path: Path to the file on the server
            file_url: URL to access the file
            original_filename: Original name of the file
            plugin_name: Name of the plugin used for ingestion
            plugin_params: Parameters used for ingestion
            owner: Owner of the file
            document_count: Number of chunks/documents created
            content_type: MIME type of the file
            status: Status of the file (default: COMPLETED)
            
        Returns:
            The created FileRegistry entry
        """
        # Get file size
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        
        # Ensure plugin_params is a dict, not a string
        if isinstance(plugin_params, str):
            try:
                plugin_params = json.loads(plugin_params)
            except (json.JSONDecodeError, TypeError, ValueError):
                plugin_params = {}
                
        # Create the file registry entry
        file_registry = FileRegistry(
            collection_id=collection_id,
            original_filename=original_filename,
            file_path=file_path,
            file_url=file_url,
            file_size=file_size,
            content_type=content_type,
            plugin_name=plugin_name,
            plugin_params=plugin_params,
            status=status,
            document_count=document_count,
            owner=owner
        )
        
        db.add(file_registry)
        db.commit()
        db.refresh(file_registry)
        
        return file_registry
    
    @classmethod
    def update_file_status(cls, db: Session, file_id: int, status: FileStatus) -> FileRegistry:
        """Update the status of a file in the registry.
        
        Args:
            db: Database session
            file_id: ID of the file registry entry
            status: New status
            
        Returns:
            The updated FileRegistry entry or None if not found
        """
        file_registry = db.query(FileRegistry).filter(FileRegistry.id == file_id).first()
        if file_registry:
            file_registry.status = status
            file_registry.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(file_registry)
        
        return file_registry
        
    @classmethod
    def list_plugins(cls) -> List[Dict[str, Any]]:
        """List all available ingestion plugins.
        
        Returns:
            List of plugin metadata
        """
        return PluginRegistry.list_plugins()
    
    @classmethod
    def get_plugin(cls, plugin_name: str) -> Optional[IngestPlugin]:
        """Get a plugin by name.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin instance if found, None otherwise
        """
        plugin_class = PluginRegistry.get_plugin(plugin_name)
        if plugin_class:
            return plugin_class()
        return None
    
    @classmethod
    def get_file_url(cls, file_path: str) -> str:
        """Get the URL for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            URL for accessing the file
        """
        try:
            file_path_obj = Path(file_path)
            relative_path = file_path_obj.relative_to(cls.STATIC_DIR)
            return f"{cls.STATIC_URL_PREFIX}/{relative_path}"
        except ValueError:
            # If file is not under STATIC_DIR, it's not accessible via URL
            return ""
    
    @classmethod
    def ingest_file(
        cls, 
        file_path: str,
        plugin_name: str,
        plugin_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Ingest a file using the specified plugin.
        
        Args:
            file_path: Path to the file to ingest
            plugin_name: Name of the plugin to use
            plugin_params: Parameters for the plugin
            
        Returns:
            List of document chunks with metadata
            
        Raises:
            HTTPException: If the plugin is not found or ingestion fails
        """
        print(f"DEBUG: [ingest_file] Starting ingestion for file: {file_path}")
        print(f"DEBUG: [ingest_file] Using plugin: {plugin_name}")
        print(f"DEBUG: [ingest_file] Plugin params: {plugin_params}")
        
        # Check file exists
        if not os.path.exists(file_path):
            print(f"DEBUG: [ingest_file] ERROR: File does not exist: {file_path}")
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {file_path}"
            )
        
        # Get file size
        file_size = os.path.getsize(file_path)
        print(f"DEBUG: [ingest_file] File size: {file_size} bytes")
        
        plugin = cls.get_plugin(plugin_name)
        if not plugin:
            print(f"DEBUG: [ingest_file] ERROR: Plugin {plugin_name} not found")
            raise HTTPException(
                status_code=404,
                detail=f"Ingestion plugin '{plugin_name}' not found"
            )
        
        print(f"DEBUG: [ingest_file] Plugin found: {plugin_name}")
        
        try:
            # Get file URL for the document
            file_url = cls.get_file_url(file_path)
            print(f"DEBUG: [ingest_file] File URL: {file_url}")
            
            # Apply plugin mode governance before calling plugin logic.
            governed_plugin_params = PluginRegistry.sanitize_ingest_params(
                plugin_name,
                plugin_params or {}
            )

            # Add file_url to plugin params
            plugin_params_with_url = governed_plugin_params.copy()
            plugin_params_with_url["file_url"] = file_url
            
            # Ingest the file with the plugin
            print(f"DEBUG: [ingest_file] Calling plugin.ingest()")
            documents = plugin.ingest(file_path, **plugin_params_with_url)
            print(f"DEBUG: [ingest_file] Plugin returned {len(documents)} chunks")
            
            return documents
            
        except Exception as e:
            print(f"DEBUG: [ingest_file] ERROR during ingestion: {str(e)}")
            import traceback
            print(f"DEBUG: [ingest_file] Stack trace:\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to ingest file: {str(e)}"
            )
    
    @classmethod
    def add_documents_to_collection(
        cls,
        db: Session,
        collection_id: int,
        documents: List[Dict[str, Any]],
        embeddings_function: Optional[Any] = None,
        file_registry_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Add documents to a collection via the knowledge store plugin.

        Resolves the collection's knowledge store setup to get the appropriate
        plugin, then uses plugin.add_chunks() for technology-agnostic ingestion.

        Args:
            db: Database session
            collection_id: ID of the collection
            documents: List of document chunks with metadata
            embeddings_function: IGNORED — always uses collection config
            file_registry_id: Optional ID of the file registry entry for progress updates

        Returns:
            Status information about the ingestion

        Raises:
            HTTPException: If the collection is not found or adding documents fails
        """
        print(f"DEBUG: [add_documents_to_collection] Starting for collection_id: {collection_id}")
        print(f"DEBUG: [add_documents_to_collection] Number of documents: {len(documents)}")

        # Get the collection from DB
        db_collection = CollectionService.get_collection(db, collection_id)
        if not db_collection:
            raise HTTPException(status_code=404, detail=f"Collection with ID {collection_id} not found")

        collection_name = db_collection['name'] if isinstance(db_collection, dict) else db_collection.name
        print(f"DEBUG: [add_documents_to_collection] Found collection: {collection_name}")

        # ── Resolve knowledge store plugin and backend collection ──
        plugin = None
        plugin_config = None
        vendor = ""
        model_name = ""

        # Determine setup_id from dict or object
        setup_id = (
            db_collection.get('knowledge_store_setup_id')
            if isinstance(db_collection, dict)
            else getattr(db_collection, 'knowledge_store_setup_id', None)
        )

        if setup_id:
            # NEW MODE: resolve via knowledge store plugin
            setup = db.query(KnowledgeStoreSetup).filter(KnowledgeStoreSetup.id == setup_id).first()
            if setup:
                plugin_config = setup.plugin_config
                if isinstance(plugin_config, str):
                    import json as _json
                    plugin_config = _json.loads(plugin_config)
                plugin_config = plugin_config or {}

                vendor = plugin_config.get("vendor", "")
                model_name = plugin_config.get("model", "")

                try:
                    plugin = get_knowledge_store(setup.plugin_type)
                    print(f"DEBUG: [add_documents_to_collection] Using plugin: {setup.plugin_type}")
                except ValueError as e:
                    print(f"WARNING: [add_documents_to_collection] Plugin '{setup.plugin_type}' not found, falling back")

        # ── Get embedding config for logging (OLD MODE fallback) ──
        if not plugin:
            embedding_config = (
                json.loads(db_collection['embeddings_model'])
                if isinstance(db_collection, dict) and isinstance(db_collection.get('embeddings_model'), str)
                else (db_collection.embeddings_model if not isinstance(db_collection, dict)
                      else db_collection.get('embeddings_model', {}))
            )
            if isinstance(embedding_config, str):
                embedding_config = json.loads(embedding_config)
            embedding_config = embedding_config or {}
            vendor = embedding_config.get("vendor", "")
            model_name = embedding_config.get("model", "")

        print(f"DEBUG: [add_documents_to_collection] Using embeddings - vendor: {vendor}, model: {model_name}")

        # ── Obtain the backend collection handle ──
        try:
            if plugin and plugin_config:
                # Plugin-based: use the knowledge store plugin to get the collection
                print(f"DEBUG: [add_documents_to_collection] Getting collection via plugin")
                backend_collection = plugin.get_collection(collection_name, plugin_config)
                print(f"DEBUG: [add_documents_to_collection] Plugin returned collection handle")
            else:
                # OLD MODE fallback: use direct ChromaDB access
                print(f"DEBUG: [add_documents_to_collection] OLD MODE: using direct ChromaDB access")
                from database.connection import get_chroma_client
                chroma_client = get_chroma_client()
                collection_embedding_function = get_embedding_function(db_collection)

                # Verify collection exists
                collections = chroma_client.list_collections()
                if collections and isinstance(collections[0], str):
                    collection_exists = collection_name in collections
                else:
                    try:
                        collection_exists = any(col.name == collection_name for col in collections)
                    except (AttributeError, NotImplementedError):
                        try:
                            chroma_client.get_collection(name=collection_name)
                            collection_exists = True
                        except Exception:
                            collection_exists = False

                if not collection_exists:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Collection '{collection_name}' exists in database but not in ChromaDB. "
                               f"This indicates data inconsistency. Please recreate the collection."
                    )

                backend_collection = chroma_client.get_collection(
                    name=collection_name,
                    embedding_function=collection_embedding_function
                )
                print(f"DEBUG: [add_documents_to_collection] OLD MODE: ChromaDB collection retrieved")

        except HTTPException:
            raise
        except Exception as e:
            print(f"DEBUG: [add_documents_to_collection] ERROR obtaining backend collection: {e}")
            import traceback
            print(f"DEBUG: [add_documents_to_collection] Stack trace:\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to access backend collection: {e}")

        # ── Prepare documents ──
        print(f"DEBUG: [add_documents_to_collection] Preparing documents")
        ids = []
        texts = []
        metadatas = []

        for doc in documents:
            doc_id = f"{uuid.uuid4().hex}"
            ids.append(doc_id)
            texts.append(doc["text"])

            metadata = doc.get("metadata", {}).copy()
            metadata["document_id"] = doc_id
            metadata["ingestion_timestamp"] = datetime.utcnow().isoformat()
            metadata["embedding_vendor"] = vendor
            metadata["embedding_model"] = model_name
            metadatas.append(metadata)

        print(f"DEBUG: [add_documents_to_collection] Prepared {len(ids)} documents")

        # ── Add documents via plugin or direct call ──
        try:
            if len(texts) > 0:
                print(f"DEBUG: [add_documents_to_collection] First document sample: {texts[0][:100]}...")

            start_time = time.time()
            batch_size = 5
            total_docs = len(ids)

            for i in range(0, len(ids), batch_size):
                batch_end = min(i + batch_size, len(ids))
                print(f"DEBUG: [add_documents_to_collection] Processing batch {i//batch_size + 1}/{(len(ids) + batch_size - 1)//batch_size}")

                batch_start_time = time.time()

                if plugin and plugin_config:
                    # Plugin-based add
                    plugin.add_chunks(
                        backend_collection,
                        chunk_ids=ids[i:batch_end],
                        chunk_texts=texts[i:batch_end],
                        chunk_metadata=metadatas[i:batch_end],
                        plugin_config=plugin_config
                    )
                else:
                    # OLD MODE: direct ChromaDB add
                    backend_collection.add(
                        ids=ids[i:batch_end],
                        documents=texts[i:batch_end],
                        metadatas=metadatas[i:batch_end],
                    )

                batch_end_time = time.time()
                print(f"DEBUG: [add_documents_to_collection] Batch {i//batch_size + 1} completed in {batch_end_time - batch_start_time:.2f} seconds")

                # Update progress
                if file_registry_id:
                    file_reg = db.query(FileRegistry).filter(FileRegistry.id == file_registry_id).first()
                    if file_reg:
                        file_reg.progress_current = batch_end
                        file_reg.progress_total = total_docs
                        file_reg.progress_message = f"Adding chunks to collection... ({batch_end}/{total_docs})"
                        file_reg.updated_at = datetime.utcnow()
                        db.commit()
                        print(f"DEBUG: [add_documents_to_collection] Updated progress: {batch_end}/{total_docs}")

            end_time = time.time()
            print(f"DEBUG: [add_documents_to_collection] Add operation completed in {end_time - start_time:.2f} seconds")

            return {
                "collection_id": collection_id,
                "collection_name": collection_name,
                "documents_added": len(documents),
                "success": True,
                "embedding_info": {
                    "vendor": vendor,
                    "model": model_name
                }
            }
        except Exception as e:
            print(f"DEBUG: [add_documents_to_collection] ERROR adding documents: {e}")
            import traceback
            print(f"DEBUG: [add_documents_to_collection] Stack trace:\n{traceback.format_exc()}")

            error_message = str(e)
            if "api_key" in error_message.lower() or "apikey" in error_message.lower():
                raise HTTPException(
                    status_code=500,
                    detail="Failed to add documents: API key issue with embeddings provider."
                )
            elif "timeout" in error_message.lower():
                raise HTTPException(
                    status_code=500,
                    detail="Failed to add documents: Timeout when generating embeddings."
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to add documents to collection: {e}"
                )
