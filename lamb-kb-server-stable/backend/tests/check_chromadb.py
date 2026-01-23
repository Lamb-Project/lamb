#!/usr/bin/env python3
"""
Simple script to check ChromaDB collections
"""

import os
import chromadb
import logging
import json
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_chromadb(path):
    """Check ChromaDB collections"""
    
    try:
        logger.info(f"Trying to connect to ChromaDB at: {path}")
        if not os.path.exists(path):
            logger.warning(f"Path does not exist: {path}")
            return False
            
        client = chromadb.PersistentClient(path=path)
        collections = client.list_collections()
        
        logger.info(f"Connected to ChromaDB at {path}")
        logger.info(f"Found {len(collections)} collections:")
        
        # Handle ChromaDB v0.6.0+ API change: list_collections() now returns list of strings
        if collections and isinstance(collections[0], str):
            logger.info("Using ChromaDB v0.6.0+ API (collections are strings)")
            for i, collection_name in enumerate(collections, 1):
                logger.info(f"  {i}. {collection_name}")
                # Try to get a count
                try:
                    collection = client.get_collection(name=collection_name)
                    count = collection.count()
                    logger.info(f"     Documents: {count}")
                except Exception as e:
                    logger.error(f"     Error getting count: {e}")
        else:
            # Older ChromaDB API
            logger.info("Using older ChromaDB API (collections are objects)")
            for i, col in enumerate(collections, 1):
                try:
                    logger.info(f"  {i}. {col.name}")
                    # Try to get a count
                    count = col.count()
                    logger.info(f"     Documents: {count}")
                except Exception as e:
                    logger.error(f"     Error accessing collection: {e}")
        
        # Check directory structure
        logger.info(f"Directory contents of {path}:")
        try:
            contents = os.listdir(path)
            logger.info(f"Files/directories: {contents}")
            
            # Look for collection-specific directories
            for item in contents:
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    logger.info(f"Subdirectory: {item}")
                    sub_contents = os.listdir(item_path)
                    logger.info(f"  Contents: {sub_contents[:20]}")
        except Exception as e:
            logger.error(f"Error listing directory contents: {e}")
        
        # Try to get specific collections
        specific_collections = ["bug_fix", "6"]
        for coll_name in specific_collections:
            try:
                logger.info(f"Attempting to get collection by name: {coll_name}")
                collection = client.get_collection(name=coll_name)
                count = collection.count()
                logger.info(f"Found collection '{coll_name}' with {count} documents")
                
                # Get metadata
                logger.info(f"Getting metadata for collection '{coll_name}'")
                metadata = collection.get(limit=1)
                logger.info(f"Metadata sample: {json.dumps(metadata, indent=2, default=str)[:500]}...")
                
            except Exception as e:
                logger.error(f"Error accessing collection '{coll_name}': {e}")
                
        return True
        
    except Exception as e:
        logger.error(f"Error connecting to ChromaDB at {path}: {e}")
        return False

def main():
    """Main function"""
    # Use command-line argument for path if provided
    if len(sys.argv) > 1:
        manual_path = sys.argv[1]
        logger.info(f"Using command-line specified path: {manual_path}")
        if os.path.exists(manual_path):
            check_chromadb(manual_path)
            return
        else:
            logger.error(f"Specified path does not exist: {manual_path}")
    
    CHROMADB_PATHS = [
        os.path.expanduser(os.environ.get("CHROMADB_PATH", "")),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/chromadb"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chromadb"), 
        os.path.join(os.path.abspath("."), "data/chromadb"),
        os.path.join(os.path.abspath(".."), "data/chromadb"),
        os.path.join(os.path.abspath("."), "backend/data/chromadb")
    ]
    
    # Filter empty paths
    CHROMADB_PATHS = [p for p in CHROMADB_PATHS if p]
    
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Checking {len(CHROMADB_PATHS)} paths")
    
    # Print environment variable
    logger.info(f"CHROMADB_PATH env var: {os.environ.get('CHROMADB_PATH', 'Not set')}")
    
    success = False
    
    for path in CHROMADB_PATHS:
        if os.path.exists(path):
            logger.info(f"Checking existing path: {path}")
            if check_chromadb(path):
                success = True
                break
        else:
            logger.warning(f"Skipping non-existent path: {path}")
    
    if not success:
        logger.error("Failed to connect to ChromaDB with any of the provided paths")
        
if __name__ == "__main__":
    main() 