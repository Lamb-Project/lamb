"""
Collections service module for handling collection-related endpoint logic.

This module provides service functions for handling collection-related API endpoints,
separating the business logic from the FastAPI route definitions.
"""

import json
import os
import signal
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime
from fastapi import HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.models import Collection, Visibility, FileRegistry, FileStatus
from database.service import CollectionService as DBCollectionService
from services.ingestion import IngestionService
from schemas.collection import (
    CollectionCreate, 
    CollectionUpdate, 
    CollectionResponse, 
    CollectionList
)
from database.connection import get_embedding_function
from database.connection import get_chroma_client

# Audit log configuration
AUDIT_LOG_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data" / "audit_logs"
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
VALIDATION_AUDIT_LOG = AUDIT_LOG_DIR / "embeddings_validation.log"

# Validation timeout in seconds
VALIDATION_TIMEOUT = 30

class TimeoutError(Exception):
    """Custom timeout exception for validation."""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutError("Operation timed out")


class CollectionsService:
    """Service for handling collection-related API endpoints."""
    
    @staticmethod
    def _sanitize_embeddings_model(embeddings_model: Any) -> Dict[str, Any]:
        """
        Sanitize embeddings model by removing sensitive API keys before sending to frontend.
        
        Converts:
            {"model": "x", "vendor": "y", "api_endpoint": "z", "apikey": "secret"}
        To:
            {"model": "x", "vendor": "y", "api_endpoint": "z", "apikey_configured": true}
        
        Args:
            embeddings_model: Raw embeddings model dict or JSON string
            
        Returns:
            Sanitized embeddings model dict with apikey replaced by apikey_configured boolean
        """
        # Handle JSON string input
        if isinstance(embeddings_model, str):
            try:
                embeddings_model = json.loads(embeddings_model)
            except (json.JSONDecodeError, TypeError):
                return {"model": "unknown", "vendor": "unknown", "apikey_configured": False}
        
        # Handle None or non-dict
        if not isinstance(embeddings_model, dict):
            return {"model": "unknown", "vendor": "unknown", "apikey_configured": False}
        
        # Create sanitized copy
        sanitized = {
            "model": embeddings_model.get("model", "unknown"),
            "vendor": embeddings_model.get("vendor", "unknown"),
            "api_endpoint": embeddings_model.get("api_endpoint"),
            "apikey_configured": bool(embeddings_model.get("apikey"))  # Convert to boolean
        }
        
        return sanitized
    
    @staticmethod
    def _sanitize_collection(collection: Any) -> Dict[str, Any]:
        """
        Sanitize a collection object before returning to frontend.
        Removes API keys from embeddings_model.
        
        Args:
            collection: Collection object (SQLAlchemy model or dict)
            
        Returns:
            Sanitized collection dict
        """
        # Convert to dict if it's a model object
        if hasattr(collection, '__dict__'):
            # SQLAlchemy model - extract relevant fields
            coll_dict = {
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
                "visibility": collection.visibility.value if hasattr(collection.visibility, 'value') else str(collection.visibility),
                "owner": collection.owner,
                "creation_date": collection.creation_date,
                "embeddings_model": CollectionsService._sanitize_embeddings_model(collection.embeddings_model)
            }
        elif isinstance(collection, dict):
            coll_dict = dict(collection)
            coll_dict["embeddings_model"] = CollectionsService._sanitize_embeddings_model(
                coll_dict.get("embeddings_model", {})
            )
        else:
            return collection  # Return as-is if unknown type
        
        return coll_dict
    
    @staticmethod
    def _log_validation_audit(
        success: bool,
        embeddings_model: Dict[str, Any],
        is_custom_config: bool,
        dimensions: Optional[int] = None,
        error: Optional[str] = None
    ):
        """
        Log embeddings validation attempts to audit file.
        
        Args:
            success: Whether validation succeeded
            embeddings_model: The embeddings configuration
            is_custom_config: True if custom config, False if env defaults
            dimensions: Embedding dimensions if successful
            error: Error message if failed
        """
        try:
            timestamp = datetime.utcnow().isoformat()
            vendor = embeddings_model.get("vendor", "unknown")
            model = embeddings_model.get("model", "unknown")
            api_endpoint = embeddings_model.get("api_endpoint", "")
            config_source = "custom" if is_custom_config else "env_defaults"
            
            # Never log API keys
            log_entry = {
                "timestamp": timestamp,
                "success": success,
                "vendor": vendor,
                "model": model,
                "api_endpoint": api_endpoint,
                "config_source": config_source,
                "dimensions": dimensions,
                "error": error[:200] if error else None  # Limit error length
            }
            
            with open(VALIDATION_AUDIT_LOG, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                
        except Exception as e:
            # Don't fail collection creation if audit logging fails
            print(f"WARNING: Failed to write validation audit log: {str(e)}")
    
    @staticmethod
    def _categorize_embedding_error(
        error: Exception, 
        vendor: str, 
        model: str, 
        api_endpoint: str,
        config_source: str
    ) -> str:
        """
        Categorize embedding validation errors into user-friendly messages.
        
        Returns detailed but safe error message (hides API keys).
        
        Args:
            error: The exception that occurred
            vendor: Embeddings vendor (openai, ollama, etc)
            model: Model name
            api_endpoint: API endpoint URL
            config_source: "custom configuration" or "environment defaults"
            
        Returns:
            User-friendly error message
        """
        error_msg = str(error).lower()
        error_type = type(error).__name__
        
        # Timeout errors
        if isinstance(error, TimeoutError) or "timeout" in error_msg:
            endpoint_info = f"\nEndpoint: {api_endpoint}" if api_endpoint else ""
            return (
                f"Validation timeout for {vendor} embeddings ({config_source}).\n"
                f"Model: {model}{endpoint_info}\n"
                f"The embedding service took longer than {VALIDATION_TIMEOUT} seconds to respond.\n"
                f"Please check if the service is running and responsive."
            )
        
        # Authentication errors
        if any(keyword in error_msg for keyword in ["401", "unauthorized", "api key", "authentication", "invalid_api_key"]):
            return (
                f"Authentication failed for {vendor} embeddings ({config_source}).\n"
                f"Model: {model}\n"
                f"Please check your API key is valid and has not expired.\n"
                f"Original error: {error_type}"
            )
        
        # Network/Connection errors
        if any(keyword in error_msg for keyword in ["connection", "timeout", "network", "refused", "unreachable"]):
            endpoint_info = f"\nEndpoint: {api_endpoint}" if api_endpoint else ""
            return (
                f"Network connection failed for {vendor} embeddings ({config_source}).\n"
                f"Model: {model}{endpoint_info}\n"
                f"Please check:\n"
                f"  - Endpoint is reachable\n"
                f"  - Network connectivity\n"
                f"  - Firewall settings\n"
                f"  - Service is running (for Ollama: 'ollama serve')\n"
                f"Original error: {error_type}: {str(error)}"
            )
        
        # Invalid model errors
        if any(keyword in error_msg for keyword in ["model not found", "invalid model", "unknown model", "does not exist", "model_not_found"]):
            extra_help = ""
            if vendor.lower() == "ollama":
                extra_help = "\n  - For Ollama: Run 'ollama list' to see available models\n  - Pull the model: 'ollama pull " + model + "'"
            return (
                f"Invalid model specified for {vendor} embeddings ({config_source}).\n"
                f"Model: {model}\n"
                f"Please check:\n"
                f"  - Model name is correct\n"
                f"  - Model is available on your {vendor} instance{extra_help}\n"
                f"Original error: {error_type}"
            )
        
        # Rate limit errors
        if any(keyword in error_msg for keyword in ["429", "rate limit", "quota", "too many requests"]):
            return (
                f"Rate limit exceeded for {vendor} embeddings ({config_source}).\n"
                f"Model: {model}\n"
                f"Please check your API quota and try again later.\n"
                f"Original error: {error_type}"
            )
        
        # Generic error with safe details
        endpoint_info = f"\nEndpoint: {api_endpoint}" if api_endpoint else ""
        return (
            f"Failed to validate {vendor} embeddings ({config_source}).\n"
            f"Model: {model}{endpoint_info}\n"
            f"Error: {error_type}: {str(error)[:200]}"  # Limit error message length
        )
    
    @staticmethod
    def validate_embeddings_config(
        embeddings_model: Dict[str, Any],
        is_custom_config: bool = False
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Validate embeddings configuration by testing with a real API call.
        
        This creates a test embedding to verify:
        - API credentials are valid
        - Endpoint is reachable
        - Model exists and is accessible
        - Configuration is correct
        
        Args:
            embeddings_model: Dict with vendor, model, apikey, api_endpoint
            is_custom_config: True if user provided custom values (not from .env)
            
        Returns:
            Tuple of (success, error_message, embedding_dimension)
            
        Raises:
            HTTPException with detailed error information if validation fails
        """
        vendor = embeddings_model.get("vendor", "unknown")
        model = embeddings_model.get("model", "unknown")
        api_endpoint = embeddings_model.get("api_endpoint", "")
        
        config_source = "custom configuration" if is_custom_config else "environment defaults"
        
        # Set up timeout alarm (Unix-like systems only)
        timeout_supported = hasattr(signal, 'SIGALRM')
        
        try:
            if timeout_supported:
                # Set timeout alarm
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(VALIDATION_TIMEOUT)
            
            # Create temporary collection for validation
            temp_collection = Collection(
                id=-1, 
                name="__validation_test__", 
                owner="system", 
                description="Temporary validation object", 
                embeddings_model=json.dumps(embeddings_model)
            )
            
            # Get embedding function
            embedding_function = get_embedding_function(temp_collection)
            
            # Test with descriptive text
            test_text = "Embeddings validation test for collection creation"
            test_result = embedding_function([test_text])
            
            dimensions = len(test_result[0])
            
            print(f"INFO: [validate_embeddings] SUCCESS - {config_source}")
            print(f"INFO:   Vendor: {vendor}, Model: {model}, Dimensions: {dimensions}")
            if api_endpoint:
                print(f"INFO:   Endpoint: {api_endpoint}")
            
            # Log successful validation to audit file
            CollectionsService._log_validation_audit(
                success=True,
                embeddings_model=embeddings_model,
                is_custom_config=is_custom_config,
                dimensions=dimensions,
                error=None
            )
            
            return True, None, dimensions
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Categorize error types
            detailed_error = CollectionsService._categorize_embedding_error(
                e, vendor, model, api_endpoint, config_source
            )
            
            print(f"ERROR: [validate_embeddings] FAILED - {config_source}")
            print(f"ERROR:   Vendor: {vendor}, Model: {model}")
            if api_endpoint:
                print(f"ERROR:   Endpoint: {api_endpoint}")
            print(f"ERROR:   Error Type: {error_type}")
            print(f"ERROR:   Error: {error_msg}")
            
            # Log failed validation to audit file
            CollectionsService._log_validation_audit(
                success=False,
                embeddings_model=embeddings_model,
                is_custom_config=is_custom_config,
                dimensions=None,
                error=f"{error_type}: {error_msg}"
            )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detailed_error
            )
        finally:
            if timeout_supported:
                # Cancel the alarm
                signal.alarm(0)
    
    @staticmethod
    def create_collection(
        collection: CollectionCreate,
        db: Session,
    ) -> Dict[str, Any]:
        """Create a new knowledge base collection.
        
        Args:
            collection: Collection data from request body with resolved default values
            db: Database session
            
        Returns:
            The created collection
            
        Raises:
            HTTPException: If collection creation fails
        """
        # Check if collection with this name already exists
        existing = DBCollectionService.get_collection_by_name(db, collection.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Collection with name '{collection.name}' already exists"
            )
        
        # Convert visibility string to enum
        try:
            visibility = Visibility(collection.visibility)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid visibility value: {collection.visibility}. Must be 'private' or 'public'."
            )
        
        # Create the collection
        try:
            # Handle the embeddings model configuration
            embeddings_model = {}
            if collection.embeddings_model:
                # Get the model values from the request
                # Note: Default values should already be resolved by router
                model_info = collection.embeddings_model.model_dump()
                
                # Determine if this is a custom config or using env defaults
                # Check if any field was explicitly provided (not default/None/empty)
                is_custom_config = any([
                    model_info.get("vendor") not in [None, ""],
                    model_info.get("model") not in [None, ""],
                    model_info.get("apikey") not in [None, "", "default"],
                    model_info.get("api_endpoint") not in [None, "", "default"]
                ])
                
                print(f"INFO: [create_collection] Validating embeddings configuration")
                print(f"INFO:   Config source: {'Custom' if is_custom_config else 'Environment defaults'}")
                print(f"INFO:   Vendor: {model_info.get('vendor')}, Model: {model_info.get('model')}")
                
                # Validate the embeddings configuration with timeout and detailed error handling
                # This will raise HTTPException if validation fails
                # CRITICAL: We must validate because embeddings function cannot be changed after creation
                success, error_msg, dimensions = CollectionsService.validate_embeddings_config(
                    embeddings_model=model_info,
                    is_custom_config=is_custom_config
                )
                
                print(f"INFO: [create_collection] Validation successful, embedding dimensions: {dimensions}")
                print(f"INFO: [create_collection] Collection will be created with immutable embeddings function")
                
                embeddings_model = model_info
            
            # Create the collection in both databases
            db_collection = DBCollectionService.create_collection(
                db=db,
                name=collection.name,
                owner=collection.owner,
                description=collection.description,
                visibility=visibility,
                embeddings_model=embeddings_model
            )
            
            # Ensure embeddings_model is a dictionary before returning
            if isinstance(db_collection.embeddings_model, str):
                try:
                    db_collection.embeddings_model = json.loads(db_collection.embeddings_model)
                except (json.JSONDecodeError, TypeError):
                    # If we can't parse it, return an empty dict rather than failing
                    db_collection.embeddings_model = {}
            
            # Verify the collection was created successfully in both databases
            if not db_collection.chromadb_uuid:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Collection was created but ChromaDB UUID was not stored"
                )
            
            # SECURITY: Sanitize response to remove API keys before returning
            return CollectionsService._sanitize_collection(db_collection)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create collection: {str(e)}"
            )
    
    @staticmethod
    def list_collections(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        owner: Optional[str] = None,
        visibility: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all available knowledge base collections with optional filtering.
        
        Args:
            db: Database session
            skip: Number of collections to skip
            limit: Maximum number of collections to return
            owner: Optional filter by owner
            visibility: Optional filter by visibility
            
        Returns:
            Dict with total count and list of collections
            
        Raises:
            HTTPException: If invalid visibility value is provided
        """
        # Convert visibility string to enum if provided
        visibility_enum = None
        if visibility:
            try:
                visibility_enum = Visibility(visibility)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid visibility value: {visibility}. Must be 'private' or 'public'."
                )
        
        # Get collections with filtering
        collections = DBCollectionService.list_collections(
            db=db,
            owner=owner,
            visibility=visibility_enum,
            skip=skip,
            limit=limit
        )
        
        # Count total collections with same filter
        query = db.query(Collection)
        if owner:
            query = query.filter(Collection.owner == owner)
        if visibility_enum:
            query = query.filter(Collection.visibility == visibility_enum)
        total = query.count()
        
        # SECURITY: Sanitize all collections to remove API keys before returning
        sanitized_collections = [
            CollectionsService._sanitize_collection(c) for c in collections
        ]
        
        return {
            "total": total,
            "items": sanitized_collections
        }
    
    @staticmethod
    def get_collection(
        collection_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """Get details of a specific knowledge base collection.
        
        Args:
            collection_id: ID of the collection to retrieve
            db: Database session
            
        Returns:
            Collection details (sanitized - no API keys)
            
        Raises:
            HTTPException: If collection not found
        """
        collection = DBCollectionService.get_collection(db, collection_id)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection with ID {collection_id} not found"
            )
        # SECURITY: Sanitize response to remove API keys before returning
        return CollectionsService._sanitize_collection(collection)
    
    @staticmethod
    def list_files(
        collection_id: int,
        db: Session,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all files in a collection.
        
        Args:
            collection_id: ID of the collection
            db: Database session
            status: Optional filter by status
            
        Returns:
            List of file registry entries
            
        Raises:
            HTTPException: If collection not found or status invalid
        """
        # Check if collection exists
        collection = DBCollectionService.get_collection(db, collection_id)
        if not collection:
            raise HTTPException(
                status_code=404,
                detail=f"Collection with ID {collection_id} not found"
            )
        
        # Query files
        query = db.query(FileRegistry).filter(FileRegistry.collection_id == collection_id)
        
        # Apply status filter if provided
        if status:
            try:
                file_status = FileStatus(status)
                query = query.filter(FileRegistry.status == file_status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Must be one of: completed, processing, failed, deleted"
                )
        
        # Get results
        files = query.all()
        
        # Convert to response model
        return [file.to_dict() for file in files]
    
    @staticmethod
    def update_file_status(
        file_id: int,
        status: str,
        db: Session
    ) -> Dict[str, Any]:
        """Update the status of a file in the registry.
        
        Args:
            file_id: ID of the file registry entry
            status: New status
            db: Database session
            
        Returns:
            Updated file registry entry
            
        Raises:
            HTTPException: If file not found or status invalid
        """
        # Validate status
        try:
            file_status = FileStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Must be one of: completed, processing, failed, deleted"
            )
        
        # Update file status
        file = IngestionService.update_file_status(db, file_id, file_status)
        if not file:
            raise HTTPException(
                status_code=404,
                detail=f"File with ID {file_id} not found"
            )
        
        return file.to_dict()
        
    @staticmethod
    def get_file_content(file_id: int, db: Session) -> Dict[str, Any]:
        """Get the content of a file.
        
        Args:
            file_id: ID of the file registry entry
            db: Database session
            
        Returns:
            Content of the file with metadata
            
        Raises:
            HTTPException: If file not found or content cannot be retrieved
        """
        # Get file registry entry
        file_registry = db.query(FileRegistry).filter(FileRegistry.id == file_id).first()
        if not file_registry:
            raise HTTPException(
                status_code=404,
                detail=f"File with ID {file_id} not found"
            )
        
        # Get collection
        collection = db.query(Collection).filter(Collection.id == file_registry.collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=404,
                detail=f"Collection with ID {file_registry.collection_id} not found"
            )
            
        # Get ChromaDB client and collection
        chroma_client = get_chroma_client()
        chroma_collection = chroma_client.get_collection(name=collection.name)
        
        source = file_registry.original_filename
        
        # Get content from ChromaDB
        results = chroma_collection.get(
            where={"filename": source}, 
            include=["documents", "metadatas"]
        )

        print(file_registry.to_dict())
        

        print(file_registry.original_filename, results["documents"])
        # If no content in ChromaDB, raise error
        if not results["documents"]:
            raise HTTPException(
                status_code=404,
                detail=f"No content found for file: {source}"
            )
        
        # Reconstruct content from chunks
        chunk_docs = []
        for i, doc in enumerate(results["documents"]):
            if i < len(results["metadatas"]) and results["metadatas"][i]:
                metadata = results["metadatas"][i]
                chunk_docs.append({
                    "text": doc,
                    "index": metadata.get("chunk_index", i),
                    "count": metadata.get("chunk_count", 0)
                })
        
        # Sort chunks by index
        chunk_docs.sort(key=lambda x: x["index"])
        
        # Join all chunks
        full_content = "\n".join(doc["text"] for doc in chunk_docs)
        
        return {
            "file_id": file_id,
            "original_filename": source,
            "content": full_content,
            "content_type": "markdown",  # Always set to markdown
            "chunk_count": len(chunk_docs),
            "timestamp": file_registry.updated_at.isoformat() if file_registry.updated_at else None
        }

    # -------------------- File Deletion (Embeddings + Registry + Filesystem) -------------------- #
    @staticmethod
    def _find_embedding_ids_for_file(chroma_collection, file_hash: str) -> List[str]:
        """Locate all embedding IDs in a Chroma collection that reference a file.

        Strategy:
          1. Attempt a metadata `where` filter using `$contains` (newer Chroma versions)
          2. Fallback to paginated scan of metadatas (older versions / unsupported filter)

        Args:
            chroma_collection: Chroma collection handle
            file_hash: Stem (basename without extension) of file URL or path
        Returns:
            List of embedding/document IDs to delete
        """
        ids: List[str] = []
        # 1. Try metadata query first
        try:
            res = chroma_collection.get(
                where={
                    "$or": [
                        {"file_url": {"$contains": file_hash}},
                        {"source": {"$contains": file_hash}},
                        {"path": {"$contains": file_hash}},
                        {"filename": {"$contains": file_hash}},
                    ]
                },
                include=["metadatas"],
            )
            if res and res.get("ids"):
                return list(res["ids"])  # type: ignore
        except Exception:
            pass

        # 2. Fallback: scan in batches
        offset = 0
        batch = 1000
        while True:
            res = chroma_collection.get(include=["metadatas"], limit=batch, offset=offset)
            got = len(res.get("ids", []))
            if got == 0:
                break
            for idx, md in enumerate(res.get("metadatas", [])):
                if not isinstance(md, dict):
                    continue
                joined_vals = "|".join(str(v) for v in md.values())
                if file_hash in joined_vals:
                    ids.append(res["ids"][idx])
            offset += got
        return ids

    @staticmethod
    def delete_file(
        collection_id: int,
        file_id: int,
        db: Session,
        hard_delete: bool = True
    ) -> Dict[str, Any]:
        """Delete a file and its embeddings from a collection.

        Steps:
          1. Validate collection & file membership
          2. Resolve Chroma collection
          3. Identify embedding ids referencing the file (via hash of URL/path)
          4. Delete embeddings from Chroma
          5. Remove physical file (and derived .html variant) if present
          6. Remove or mark file registry entry

        Args:
            collection_id: Collection owning the file
            file_id: File registry id
            db: DB session
            hard_delete: If True remove DB row, else mark status=deleted
        Returns:
            Dict summarising deletion results
        """
        # 1. Fetch file registry entry
        file_registry = db.query(FileRegistry).filter(FileRegistry.id == file_id).first()
        if not file_registry or file_registry.collection_id != collection_id:
            raise HTTPException(
                status_code=404,
                detail=f"File id={file_id} not found in collection id={collection_id}"
            )

        # 2. Fetch collection
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=404,
                detail=f"Collection with ID {collection_id} not found"
            )

        # 3. Get Chroma collection (embedding function not required for delete)
        chroma_client = get_chroma_client()
        try:
            chroma_collection = chroma_client.get_collection(name=collection.name)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to access Chroma collection '{collection.name}': {e}"
            )

        # 4. Derive hash/stem from file URL (fallback to file_path stem)
        file_url = file_registry.file_url or ""
        file_hash = Path(file_url).stem if file_url else Path(file_registry.file_path).stem

        embedding_ids = CollectionsService._find_embedding_ids_for_file(chroma_collection, file_hash)

        # 5. Delete embeddings
        deleted_embeddings = 0
        if embedding_ids:
            try:
                chroma_collection.delete(ids=embedding_ids)
                deleted_embeddings = len(embedding_ids)
            except Exception as e:
                # Non-fatal: proceed but report error
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed deleting embeddings for file id={file_id}: {e}"
                )

        # 6. Remove physical file(s)
        removed_files: List[str] = []
        def _maybe_remove(path: str):
            if os.path.exists(path):
                try:
                    os.remove(path)
                    removed_files.append(path)
                except Exception:
                    pass

        _maybe_remove(file_registry.file_path)
        # Also remove potential converted HTML/Markdown derivatives
        if file_registry.file_path.endswith('.pdf'):
            _maybe_remove(file_registry.file_path[:-4] + '.html')
        if file_registry.file_path.endswith('.html'):
            _maybe_remove(file_registry.file_path[:-5] + '.pdf')

        # 7. Remove / mark DB entry
        if hard_delete:
            db.delete(file_registry)
        else:
            file_registry.status = FileStatus.DELETED
        db.commit()

        return {
            "file_id": file_id,
            "collection_id": collection_id,
            "deleted_embeddings": deleted_embeddings,
            "removed_files": removed_files,
            "status": "deleted"
        }

    # -------------------- Collection Deletion (Chroma + DB + Files) -------------------- #
    @staticmethod
    def delete_collection(
        collection_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """Delete an entire collection and its embeddings.

        Steps:
          1. Fetch collection (404 if missing)
          2. Attempt to resolve Chroma collection (by chromadb_uuid then name)
          3. Count embeddings (if possible) then delete Chroma collection
          4. Enumerate file_registry entries and remove physical files (+ derived)
          5. Delete DB collection row (cascades file_registry via FK where supported)
          6. Return summary

        Deletion is idempotent regarding Chroma and filesystem missing resources.
        """
        from pathlib import Path as _Path
        from database.connection import get_chroma_client
        from database.models import Collection as DBCollection, FileRegistry as DBFileRegistry

        collection = db.query(DBCollection).filter(DBCollection.id == collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=404,
                detail=f"Collection with ID {collection_id} not found"
            )

        chroma_client = get_chroma_client()
        chroma_deleted = False
        embedding_count = 0
        chroma_collection_name_used = None

        # Try to load collection by chromadb_uuid first, then by name
        potential_names = []
        if collection.chromadb_uuid:
            potential_names.append(collection.chromadb_uuid)
        potential_names.append(collection.name)

        for candidate in potential_names:
            if chroma_deleted:
                break
            try:
                chroma_col = chroma_client.get_collection(name=candidate)
                # Count embeddings if API supports it
                try:
                    embedding_count = chroma_col.count()
                except Exception:
                    embedding_count = 0
                chroma_client.delete_collection(name=candidate)
                chroma_collection_name_used = candidate
                chroma_deleted = True
            except Exception:
                # Ignore and try next
                continue

        # Gather and remove files
        removed_files: List[str] = []
        file_entries = db.query(DBFileRegistry).filter(DBFileRegistry.collection_id == collection_id).all()

        def _maybe_remove(path: str):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    removed_files.append(path)
                except Exception:
                    pass

        for fe in file_entries:
            _maybe_remove(fe.file_path)
            # Also try derived extensions
            if fe.file_path.endswith('.pdf'):
                _maybe_remove(fe.file_path[:-4] + '.html')
            if fe.file_path.endswith('.html'):
                _maybe_remove(fe.file_path[:-5] + '.pdf')

        # Explicitly delete file registry entries (in case FK cascade not active)
        for fe in file_entries:
            db.delete(fe)

        # Delete collection row
        db.delete(collection)
        db.commit()

        return {
            "id": collection_id,
            "name": collection.name,
            "deleted_embeddings": embedding_count,
            "chroma_collection": chroma_collection_name_used,
            "removed_files": removed_files,
            "status": "deleted"
        }

    @staticmethod
    def bulk_update_embeddings_apikey(
        db: Session,
        owner: str,
        apikey: str
    ) -> Dict[str, Any]:
        """Bulk update embeddings API key for all collections of an owner.

        This is a wrapper method that delegates to the database service layer.

        Args:
            db: SQLAlchemy database session
            owner: Owner identifier (e.g., organization ID)
            apikey: New API key to set for all collections

        Returns:
            Dictionary with update results from the database service
        """
        return DBCollectionService.bulk_update_embeddings_apikey(
            db=db,
            owner=owner,
            apikey=apikey
        )