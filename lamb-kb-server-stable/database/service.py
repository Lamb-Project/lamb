"""
Database service module for managing collections.

This module provides service functions for managing collections in both SQLite and ChromaDB.
"""

import os
import json
import chromadb
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from sqlalchemy.orm.attributes import flag_modified

from .models import Collection, Visibility
from .connection import get_db, get_chroma_client, get_embedding_function, get_embedding_function_by_params


class CollectionService:
    """Service for managing collections in both SQLite and ChromaDB."""
    
    @staticmethod
    def create_collection(
        db: Session,
        name: str,
        owner: str,
        description: Optional[str] = None,
        visibility: Visibility = Visibility.PRIVATE,
        embeddings_model: Optional[Dict[str, Any]] = None
    ) -> Collection:
        """Create a new collection in both SQLite and ChromaDB.
        
        Args:
            db: SQLAlchemy database session
            name: Name of the collection
            owner: Owner of the collection
            description: Optional description
            visibility: Visibility setting (private or public)
            embeddings_model: Optional custom embeddings model configuration
            
        Returns:
            The created Collection object
        """
        # embeddings_model=None should never happen from the API
        if embeddings_model is None:
            error_msg = "No embeddings model configuration provided. This is required for collection creation."
            print(f"ERROR: [create_collection] {error_msg}")
            raise ValueError(error_msg)
        
        # Create ChromaDB collection
        chroma_client = get_chroma_client()
        
        # Get the appropriate embedding function based on model configuration
        embedding_func = None
        if embeddings_model:
            print(f"DEBUG: [create_collection] Using embedding config from dict - Model: {embeddings_model['model']}, Vendor: {embeddings_model['vendor']}")
            try:
                embedding_func = get_embedding_function_by_params(
                    vendor=embeddings_model['vendor'],
                    model_name=embeddings_model['model'],
                    api_key=embeddings_model.get('apikey', ''),
                    api_endpoint=embeddings_model.get('api_endpoint', '')
                )
            except Exception as e:
                print(f"ERROR: [create_collection] Failed to create embedding function: {str(e)}")
                raise ValueError(f"Failed to create embedding function: {str(e)}")
        
        # Prepare collection parameters
        collection_params = {
            "name": name,
            "metadata": {
                "hnsw:space": "cosine",
            }
        }
        
        if embedding_func:
            collection_params["embedding_function"] = embedding_func
        
        try:
            chroma_collection = chroma_client.create_collection(**collection_params)
            print(f"DEBUG: [create_collection] Successfully created ChromaDB collection")
            
            # Create SQLite record
            db_collection = Collection(
                name=name,
                description=description,
                owner=owner,
                visibility=visibility,
                embeddings_model=embeddings_model,  # SQLAlchemy JSON column handles serialization
                chromadb_uuid=str(chroma_collection.id)
            )
            db.add(db_collection)
            db.commit()
            db.refresh(db_collection)


            return db_collection

        except Exception as e:
            print(f"ERROR: [create_collection] Failed to create ChromaDB collection: {str(e)}")

            raise
    

    @staticmethod
    def get_collection(db: Session, collection_id: int) -> Optional[Dict[str, Any]]:
        """Get a collection by ID.
        
        Args:
            db: SQLAlchemy database session
            collection_id: ID of the collection to retrieve
            
        Returns:
            The Collection as a dictionary if found, None otherwise
        """
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            return None
        
        collection_dict = collection.to_dict()
            
        return collection_dict
    
    @staticmethod
    def get_collection_by_name(db: Session, name: str) -> Optional[Collection]:
        """Get a collection by name.
        
        Args:
            db: SQLAlchemy database session
            name: Name of the collection to retrieve
            
        Returns:
            The Collection object if found, None otherwise
        """
        return db.query(Collection).filter(Collection.name == name).first()
    
    @staticmethod
    def get_collection_by_chromadb_uuid(db: Session, chromadb_uuid: str) -> Optional[Collection]:
        """Get a collection by ChromaDB UUID.
        
        Args:
            db: SQLAlchemy database session
            chromadb_uuid: ChromaDB UUID of the collection to retrieve
            
        Returns:
            The Collection object if found, None otherwise
        """
        return db.query(Collection).filter(Collection.chromadb_uuid == chromadb_uuid).first()
    
    @staticmethod
    def list_collections(
        db: Session,
        owner: Optional[str] = None,
        visibility: Optional[Visibility] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List collections with optional filtering.
        
        Args:
            db: Database session
            owner: Optional filter by owner
            visibility: Optional filter by visibility
            skip: Number of collections to skip
            limit: Maximum number of collections to return
            
        Returns:
            List of collections
        """
        # Build query
        query = db.query(Collection)
        
        # Apply filters if provided
        if owner:
            query = query.filter(Collection.owner == owner)
        if visibility:
            query = query.filter(Collection.visibility == visibility)
        
        # Apply pagination
        collections = query.offset(skip).limit(limit).all()

        return [col.to_dict() for col in collections]
    
    @staticmethod
    def update_collection(
        db: Session,
        collection_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        visibility: Optional[Visibility] = None,
        model: Optional[str] = None,
        vendor: Optional[str] = None,
        endpoint: Optional[str] = None,
        apikey: Optional[str] = None
    ) -> Optional[Collection]:
        """
        Update a collection's SQLite record and rename ChromaDB collection if needed.

        Args:
            db: SQLAlchemy session
            collection_id: ID of the collection to update
            name: New collection name
            description: New description
            visibility: New visibility setting
            model: (NOT SUPPORTED) Attempt to change embeddings model name
            vendor: (NOT SUPPORTED) Attempt to change embeddings vendor
            endpoint: New embeddings-model endpoint
            apikey: New embeddings-model API key
        """
        # Fetch existing record
        db_collection = db.query(Collection).get(collection_id)
        if not db_collection:
            return None

        old_name = db_collection.name

        # Disallow changing model or vendor
        current_conf = db_collection.embeddings_model or {}
        if model is not None and model != current_conf.get('model'):
            print("Changing 'model' is not supported and will be ignored.")
        if vendor is not None and vendor != current_conf.get('vendor'):
            print("Changing 'vendor' is not supported and will be ignored.")

        # Apply permitted updates
        if name is not None:
            db_collection.name = name
        if description is not None:
            db_collection.description = description
        if visibility is not None:
            db_collection.visibility = visibility

        # Only update endpoint and apikey
        if endpoint is not None:
            current_conf['api_endpoint'] = endpoint
        if apikey is not None:
            current_conf['apikey'] = apikey
        db_collection.embeddings_model = current_conf

        # Commit SQLite changes
        db.commit()
        db.refresh(db_collection)

        # Rename ChromaDB collection if name changed
        if name and name != old_name:
            client = get_chroma_client()
            chroma_col = client.get_collection(old_name)
            chroma_col.modify(name=name)

        return db_collection

    
    @staticmethod
    def delete_collection(db: Session, collection_id: int) -> bool:
        """Delete a collection from both SQLite and ChromaDB.

        Args:
            db: SQLAlchemy database session
            collection_id: ID of the collection to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        db_collection = db.query(Collection).filter(Collection.id == collection_id).first()

        if not db_collection:
            return False

        # Delete from ChromaDB
        collection_name = db_collection.name
        chroma_client = get_chroma_client()
        try:
            chroma_client.delete_collection(collection_name)
        except Exception as e:
            print(f"Error deleting ChromaDB collection: {e}")

        # Delete from SQLite
        db.delete(db_collection)
        db.commit()

        return True

    @staticmethod
    def bulk_update_embeddings_apikey(
        db: Session,
        owner: str,
        apikey: str
    ) -> Dict[str, Any]:
        """Bulk update embeddings API key for all collections of an owner.

        Args:
            db: SQLAlchemy database session
            owner: Owner identifier (e.g., organization ID)
            apikey: New API key to set for all collections

        Returns:
            Dictionary with update results:
                - total: Total number of collections for the owner
                - updated: Number of collections successfully updated
                - failed: Number of collections that failed to update
                - collections: List of updated collection IDs and names
        """
        # Get all collections for the owner
        collections = db.query(Collection).filter(Collection.owner == owner).all()

        if not collections:
            return {
                "total": 0,
                "updated": 0,
                "failed": 0,
                "collections": []
            }

        updated_count = 0
        failed_count = 0
        updated_collections = []

        for collection in collections:
            try:
                # Get current embeddings_model config
                current_conf = collection.embeddings_model
                original_was_string = isinstance(current_conf, str)
                
                if isinstance(current_conf, str):
                    current_conf = json.loads(current_conf)
                elif current_conf is None:
                    current_conf = {}

                # Update the API key
                current_conf['apikey'] = apikey

                # Save back to database (preserve the original storage format)
                if original_was_string:
                    collection.embeddings_model = json.dumps(current_conf)
                else:
                    collection.embeddings_model = current_conf
                
                # Flag the column as modified so SQLAlchemy tracks the change
                flag_modified(collection, "embeddings_model")
                
                updated_collections.append({
                    "id": collection.id,
                    "name": collection.name
                })
                updated_count += 1

            except Exception as e:
                print(f"ERROR: [bulk_update_embeddings_apikey] Failed to update collection {collection.id}: {str(e)}")
                failed_count += 1

        # Commit all changes at once
        try:
            db.commit()
        except Exception as e:
            print(f"ERROR: [bulk_update_embeddings_apikey] Failed to commit changes: {str(e)}")
            db.rollback()
            return {
                "total": len(collections),
                "updated": 0,
                "failed": len(collections),
                "collections": [],
                "error": str(e)
            }

        return {
            "total": len(collections),
            "updated": updated_count,
            "failed": failed_count,
            "collections": updated_collections
        }
