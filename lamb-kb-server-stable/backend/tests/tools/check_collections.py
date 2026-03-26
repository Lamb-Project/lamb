#!/usr/bin/env python3
"""
Script to check and compare collections in both SQLite and ChromaDB
"""

import os
import sys
import json
import sqlite3
import chromadb
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database paths
DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "data"
SQLITE_DB_PATH = DATA_DIR / "lamb-kb-server.db"
CHROMA_DB_PATH = DATA_DIR / "chromadb"

def check_sqlite_collections():
    """Check collections in SQLite database"""
    
    if not os.path.exists(SQLITE_DB_PATH):
        logger.error(f"SQLite database not found at: {SQLITE_DB_PATH}")
        return []
    
    try:
        # Connect to SQLite database
        logger.info(f"Connecting to SQLite database at: {SQLITE_DB_PATH}")
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if collections table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collections'")
        if not cursor.fetchone():
            logger.error("Collections table not found in SQLite database")
            return []
        
        # Get all collections
        logger.info("Fetching collections from SQLite")
        cursor.execute("SELECT id, name, owner, creation_date, embeddings_model FROM collections")
        collections = [dict(row) for row in cursor.fetchall()]
        
        logger.info(f"Found {len(collections)} collections in SQLite")
        
        # Check if there are files associated with each collection
        for collection in collections:
            cursor.execute(
                "SELECT COUNT(*) FROM file_registry WHERE collection_id=?", 
                (collection['id'],)
            )
            file_count = cursor.fetchone()[0]
            collection['file_count'] = file_count
            
            # Get files for this collection
            cursor.execute(
                "SELECT id, original_filename, plugin_name, status, document_count FROM file_registry WHERE collection_id=?",
                (collection['id'],)
            )
            collection['files'] = [dict(row) for row in cursor.fetchall()]
            
            # Format embeddings model if it's a JSON string
            if isinstance(collection['embeddings_model'], str):
                try:
                    collection['embeddings_model'] = json.loads(collection['embeddings_model'])
                except json.JSONDecodeError:
                    pass
        
        conn.close()
        return collections
        
    except Exception as e:
        logger.error(f"Error checking SQLite database: {e}")
        return []

def check_chromadb_collections():
    """Check collections in ChromaDB"""
    
    if not os.path.exists(CHROMA_DB_PATH):
        logger.error(f"ChromaDB directory not found at: {CHROMA_DB_PATH}")
        return []
    
    try:
        # Connect to ChromaDB
        logger.info(f"Connecting to ChromaDB at: {CHROMA_DB_PATH}")
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        
        # List all collections
        collections = client.list_collections()
        logger.info(f"Found {len(collections)} collections in ChromaDB")
        
        # Get details for each collection
        chroma_collections = []
        for collection in collections:
            try:
                # Get collection info
                collection_info = {
                    'name': collection.name,
                    'metadata': collection.metadata or {},
                }
                
                # Get document count
                try:
                    count = collection.count()
                    collection_info['count'] = count
                except Exception as e:
                    logger.error(f"Error getting count for collection {collection.name}: {e}")
                    collection_info['count'] = -1
                
                # Get sample records
                try:
                    if count > 0:
                        sample = collection.get(limit=1)
                        collection_info['sample'] = sample
                    else:
                        collection_info['sample'] = None
                except Exception as e:
                    logger.error(f"Error getting sample for collection {collection.name}: {e}")
                    collection_info['sample'] = None
                
                chroma_collections.append(collection_info)
                
            except Exception as e:
                logger.error(f"Error processing collection {collection.name}: {e}")
        
        return chroma_collections
        
    except Exception as e:
        logger.error(f"Error checking ChromaDB: {e}")
        return []

def check_chromadb_directory():
    """Check ChromaDB directory structure"""
    
    if not os.path.exists(CHROMA_DB_PATH):
        logger.error(f"ChromaDB directory not found at: {CHROMA_DB_PATH}")
        return {}
    
    try:
        dir_info = {}
        
        # Check contents of ChromaDB directory
        contents = os.listdir(CHROMA_DB_PATH)
        dir_info['contents'] = contents
        
        # Check DB-specific files
        expected_files = ['chroma.sqlite3']
        for file in expected_files:
            file_path = os.path.join(CHROMA_DB_PATH, file)
            if os.path.exists(file_path):
                dir_info[file] = {'exists': True, 'size': os.path.getsize(file_path)}
            else:
                dir_info[file] = {'exists': False}
        
        # Check collection directories
        collections_dir = os.path.join(CHROMA_DB_PATH, 'collections')
        if os.path.exists(collections_dir) and os.path.isdir(collections_dir):
            collection_names = os.listdir(collections_dir)
            dir_info['collections_dir'] = {
                'exists': True,
                'collections': collection_names
            }
            
            # Check each collection directory
            for name in collection_names:
                collection_path = os.path.join(collections_dir, name)
                if os.path.isdir(collection_path):
                    dir_info['collections_dir']['collections_info'] = dir_info.get('collections_dir', {}).get('collections_info', {})
                    dir_info['collections_dir']['collections_info'][name] = os.listdir(collection_path)
        else:
            dir_info['collections_dir'] = {'exists': False}
        
        return dir_info
        
    except Exception as e:
        logger.error(f"Error checking ChromaDB directory: {e}")
        return {'error': str(e)}

def rebuild_collection(collection_id):
    """Example function to rebuild a ChromaDB collection from SQLite data"""
    
    # This is a placeholder - you would need to implement this based on your actual data model
    # The general idea would be:
    # 1. Get the collection info from SQLite
    # 2. Delete the collection from ChromaDB if it exists
    # 3. Recreate the collection in ChromaDB 
    # 4. Get all documents for this collection from your document store
    # 5. Re-add all documents to the ChromaDB collection
    
    logger.info(f"This is a placeholder for rebuilding collection {collection_id}")
    logger.info("To implement this, you would need to:")
    logger.info("1. Get the collection info from SQLite")
    logger.info("2. Delete the collection from ChromaDB if it exists")
    logger.info("3. Recreate the collection in ChromaDB")
    logger.info("4. Get all documents for this collection from your document store")
    logger.info("5. Re-add all documents to the ChromaDB collection")

def compare_collections():
    """Compare collections in SQLite and ChromaDB"""
    
    # Get collections from both databases
    sqlite_collections = check_sqlite_collections()
    chromadb_collections = check_chromadb_collections()
    
    # Exit if we couldn't get collections from either database
    if not sqlite_collections:
        logger.error("No collections found in SQLite database")
        return
    
    # Compare collections
    logger.info("\n--- COMPARING COLLECTIONS ---")
    logger.info(f"SQLite: {len(sqlite_collections)} collections")
    logger.info(f"ChromaDB: {len(chromadb_collections)} collections")
    
    # Create a map of ChromaDB collections by name
    chromadb_map = {col['name']: col for col in chromadb_collections}
    
    # Check for each SQLite collection
    for sqlite_col in sqlite_collections:
        name = sqlite_col['name']
        logger.info(f"\nCollection: {name} (ID: {sqlite_col['id']})")
        logger.info(f"  Owner: {sqlite_col['owner']}")
        logger.info(f"  Files: {sqlite_col['file_count']}")
        logger.info(f"  Documents (from files): {sum(f['document_count'] for f in sqlite_col['files'] if f['document_count'] is not None)}")
        
        # Check if this collection exists in ChromaDB
        if name in chromadb_map:
            chroma_col = chromadb_map[name]
            logger.info(f"  ✅ Found in ChromaDB: {chroma_col['count']} documents")
            # Check document counts match approximately
            sqlite_doc_count = sum(f['document_count'] for f in sqlite_col['files'] if f['document_count'] is not None)
            if abs(sqlite_doc_count - chroma_col['count']) <= 5:  # Allow some discrepancy
                logger.info(f"  ✅ Document counts match approximately: SQLite={sqlite_doc_count}, ChromaDB={chroma_col['count']}")
            else:
                logger.warning(f"  ⚠️ Document counts don't match: SQLite={sqlite_doc_count}, ChromaDB={chroma_col['count']}")
        else:
            logger.error(f"  ❌ NOT found in ChromaDB")
            logger.info(f"  Embedding model: {sqlite_col['embeddings_model']}")
    
    # Check for ChromaDB collections not in SQLite
    sqlite_names = {col['name'] for col in sqlite_collections}
    for name, chroma_col in chromadb_map.items():
        if name not in sqlite_names:
            logger.warning(f"\nCollection found in ChromaDB but not in SQLite: {name}")
            logger.warning(f"  Documents: {chroma_col['count']}")
            logger.warning(f"  Metadata: {chroma_col['metadata']}")

def main():
    """Main function"""
    
    logger.info("Checking SQLite and ChromaDB collections")
    logger.info(f"SQLite path: {SQLITE_DB_PATH}")
    logger.info(f"ChromaDB path: {CHROMA_DB_PATH}")
    
    # Check if paths exist
    if not os.path.exists(SQLITE_DB_PATH):
        logger.error(f"SQLite database not found at: {SQLITE_DB_PATH}")
    
    if not os.path.exists(CHROMA_DB_PATH):
        logger.error(f"ChromaDB directory not found at: {CHROMA_DB_PATH}")
    
    # Check directory structure
    logger.info("\n--- CHECKING DIRECTORY STRUCTURE ---")
    dir_info = check_chromadb_directory()
    if 'error' in dir_info:
        logger.error(f"Error checking ChromaDB directory: {dir_info['error']}")
    else:
        logger.info(f"ChromaDB directory contents: {dir_info.get('contents', [])}")
        
        if dir_info.get('chroma.sqlite3', {}).get('exists', False):
            logger.info(f"ChromaDB SQLite file exists, size: {dir_info['chroma.sqlite3']['size']} bytes")
        else:
            logger.error("ChromaDB SQLite file not found!")
        
        if dir_info.get('collections_dir', {}).get('exists', False):
            collections = dir_info['collections_dir'].get('collections', [])
            logger.info(f"Collections directory contains {len(collections)} directories: {collections}")
        else:
            logger.warning("Collections directory not found!")
    
    # Compare collections
    compare_collections()
    
    # Offer rebuild option if collections are missing
    if len(check_chromadb_collections()) < len(check_sqlite_collections()):
        logger.warning("\nSome collections are missing from ChromaDB.")
        logger.warning("You may need to rebuild the ChromaDB collections from the SQLite data.")
    
if __name__ == "__main__":
    main() 