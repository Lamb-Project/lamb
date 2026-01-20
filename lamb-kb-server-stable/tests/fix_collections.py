#!/usr/bin/env python3
"""
Script to examine and fix ChromaDB collection issues by:
1. Examining ChromaDB internals
2. Identifying collection ID mismatches
3. Providing repair options
"""

import os
import sys
import json
import sqlite3
import chromadb
import logging
import uuid
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database paths
DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "data"
SQLITE_DB_PATH = DATA_DIR / "lamb-kb-server.db"
CHROMA_DB_PATH = DATA_DIR / "chromadb"

def connect_to_sqlite():
    """Connect to the SQLite database"""
    if not os.path.exists(SQLITE_DB_PATH):
        logger.error(f"SQLite database not found at: {SQLITE_DB_PATH}")
        return None
    
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def connect_to_chromadb_sqlite():
    """Connect to the ChromaDB SQLite database"""
    chroma_db_path = os.path.join(CHROMA_DB_PATH, 'chroma.sqlite3')
    if not os.path.exists(chroma_db_path):
        logger.error(f"ChromaDB SQLite file not found at: {chroma_db_path}")
        return None
    
    conn = sqlite3.connect(chroma_db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_sqlite_collections():
    """Get collections from the SQLite database"""
    conn = connect_to_sqlite()
    if not conn:
        return []
    
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

def get_chromadb_collections_from_sqlite():
    """Get collections directly from ChromaDB SQLite"""
    conn = connect_to_chromadb_sqlite()
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, topic, metadata FROM collections")
    collections = [dict(row) for row in cursor.fetchall()]
    
    for collection in collections:
        # Parse metadata JSON if it exists
        if collection['metadata']:
            try:
                collection['metadata'] = json.loads(collection['metadata'])
            except json.JSONDecodeError:
                pass
    
    conn.close()
    return collections

def get_chromadb_collections_api():
    """Get collections from ChromaDB API"""
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        collections = client.list_collections()
        return [{'name': coll.name, 'api_object': coll} for coll in collections]
    except Exception as e:
        logger.error(f"Error connecting to ChromaDB API: {e}")
        return []

def examine_directory_uuids():
    """Examine UUIDs in the ChromaDB directory"""
    if not os.path.exists(CHROMA_DB_PATH):
        logger.error(f"ChromaDB directory not found at: {CHROMA_DB_PATH}")
        return []
    
    # Get all directory entries that look like UUIDs
    contents = os.listdir(CHROMA_DB_PATH)
    uuid_dirs = []
    
    for item in contents:
        # Check if it's a directory and looks like a UUID
        item_path = os.path.join(CHROMA_DB_PATH, item)
        if os.path.isdir(item_path):
            try:
                # Try to parse as UUID to validate
                uuid_obj = uuid.UUID(item)
                uuid_dirs.append({
                    'uuid': item,
                    'path': item_path,
                    'files': os.listdir(item_path)
                })
            except ValueError:
                # Not a UUID, ignore
                pass
                
    return uuid_dirs

def match_collection_uuids():
    """Try to match collection UUIDs with names"""
    # Get collections from both sources
    sqlite_collections = get_sqlite_collections()
    chroma_collections = get_chromadb_collections_from_sqlite()
    uuid_dirs = examine_directory_uuids()
    
    # Make lookups by name and id
    sqlite_by_name = {col['name']: col for col in sqlite_collections}
    chroma_by_name = {col['name']: col for col in chroma_collections}
    
    # Check which UUID directories correspond to which collections
    matches = []
    
    for uuid_dir in uuid_dirs:
        uuid_value = uuid_dir['uuid']
        
        # Check if this UUID matches any ChromaDB collection id
        matched_chroma = None
        for col in chroma_collections:
            if col['id'] == uuid_value:
                matched_chroma = col
                break
        
        if matched_chroma:
            # Try to match with SQLite collection
            matched_sqlite = sqlite_by_name.get(matched_chroma['name'])
            
            matches.append({
                'uuid': uuid_value,
                'chroma_collection': matched_chroma,
                'sqlite_collection': matched_sqlite,
                'status': 'matched' if matched_sqlite else 'chroma_only'
            })
        else:
            # UUID directory exists but doesn't match any known collection
            matches.append({
                'uuid': uuid_value,
                'chroma_collection': None,
                'sqlite_collection': None,
                'status': 'orphaned_uuid'
            })
    
    # Find SQLite collections with no matching ChromaDB collection
    for col in sqlite_collections:
        if col['name'] not in chroma_by_name:
            matches.append({
                'uuid': None,
                'chroma_collection': None, 
                'sqlite_collection': col,
                'status': 'sqlite_only'
            })
    
    return matches

def fix_collection_mappings(dry_run=True):
    """Fix collection mappings between SQLite and ChromaDB"""
    matches = match_collection_uuids()
    
    # Connect to databases if not dry run
    sqlite_conn = None
    if not dry_run:
        sqlite_conn = connect_to_sqlite()
        if not sqlite_conn:
            logger.error("Cannot connect to SQLite database. Aborting.")
            return
    
    # Process each match
    for match in matches:
        status = match['status']
        
        if status == 'matched':
            logger.info(f"✅ Matched: ChromaDB collection '{match['chroma_collection']['name']}' (UUID: {match['uuid']}) matches SQLite ID {match['sqlite_collection']['id']}")
            
        elif status == 'chroma_only':
            logger.warning(f"⚠️ ChromaDB only: Collection '{match['chroma_collection']['name']}' (UUID: {match['uuid']}) exists in ChromaDB but not in SQLite")
            
            # Could add to SQLite
            if not dry_run:
                try:
                    cursor = sqlite_conn.cursor()
                    chroma_col = match['chroma_collection']
                    
                    # Extract metadata for creating in SQLite
                    metadata = chroma_col.get('metadata', {}) or {}
                    owner = metadata.get('owner', 'unknown')
                    description = metadata.get('description', '')
                    visibility = metadata.get('visibility', 'private')
                    
                    # Prepare embeddings model info
                    embeddings_model = json.dumps({
                        "model": "default",
                        "vendor": "default",
                        "apikey": "default"
                    })
                    
                    # Insert into SQLite
                    cursor.execute(
                        "INSERT INTO collections (name, description, visibility, owner, creation_date, embeddings_model) VALUES (?, ?, ?, ?, ?, ?)",
                        (chroma_col['name'], description, visibility, owner, datetime.now().isoformat(), embeddings_model)
                    )
                    sqlite_conn.commit()
                    logger.info(f"  Added ChromaDB collection '{chroma_col['name']}' to SQLite")
                except Exception as e:
                    logger.error(f"  Error adding ChromaDB collection to SQLite: {e}")
            
        elif status == 'sqlite_only':
            logger.error(f"❌ SQLite only: Collection '{match['sqlite_collection']['name']}' (ID: {match['sqlite_collection']['id']}) exists in SQLite but not in ChromaDB")
            
            # Could try to create in ChromaDB if we have embeddings info
            if not dry_run:
                try:
                    sqlite_col = match['sqlite_collection']
                    embeddings_info = sqlite_col.get('embeddings_model', {})
                    
                    # Create ChromaDB collection
                    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
                    
                    # Prepare metadata
                    metadata = {
                        "owner": sqlite_col['owner'],
                        "description": "",
                        "visibility": "private"
                    }
                    
                    # Create collection
                    client.create_collection(
                        name=sqlite_col['name'],
                        metadata=metadata
                    )
                    
                    logger.info(f"  Created ChromaDB collection '{sqlite_col['name']}' (This is an empty shell - documents need to be re-added)")
                except Exception as e:
                    logger.error(f"  Error creating ChromaDB collection: {e}")
            
        elif status == 'orphaned_uuid':
            logger.warning(f"⚠️ Orphaned UUID directory: {match['uuid']} doesn't match any known collection")
    
    # Close connections
    if sqlite_conn:
        sqlite_conn.close()

def examine_chromadb_tables():
    """Examine ChromaDB SQLite tables in detail"""
    conn = connect_to_chromadb_sqlite()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    logger.info(f"ChromaDB SQLite tables: {tables}")
    
    # Examine collections table
    if 'collections' in tables:
        cursor.execute("SELECT * FROM collections LIMIT 10")
        columns = [col[0] for col in cursor.description]
        logger.info(f"Collections table columns: {columns}")
        
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        for row in rows:
            logger.info(f"Collection: {row['name']} (ID: {row['id']})")
    
    # Examine embeddings table if it exists
    if 'embeddings' in tables:
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        count = cursor.fetchone()[0]
        logger.info(f"Embeddings table count: {count}")
        
        cursor.execute("SELECT collection_id, COUNT(*) FROM embeddings GROUP BY collection_id")
        collection_counts = cursor.fetchall()
        logger.info("Embeddings by collection:")
        for collection_id, count in collection_counts:
            logger.info(f"  Collection {collection_id}: {count} embeddings")
    
    conn.close()

def count_documents_by_collection():
    """Count documents in each ChromaDB collection"""
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        collections = client.list_collections()
        
        for collection in collections:
            try:
                count = collection.count()
                logger.info(f"Collection '{collection.name}': {count} documents")
            except Exception as e:
                logger.error(f"Error counting documents in collection '{collection.name}': {e}")
    except Exception as e:
        logger.error(f"Error connecting to ChromaDB: {e}")

def main():
    """Main function"""
    logger.info("Examining ChromaDB collections and fixing issues")
    
    # Make sure paths exist
    if not os.path.exists(SQLITE_DB_PATH):
        logger.error(f"SQLite database not found at: {SQLITE_DB_PATH}")
        return
    
    if not os.path.exists(CHROMA_DB_PATH):
        logger.error(f"ChromaDB directory not found at: {CHROMA_DB_PATH}")
        return
    
    # Examine the tables to understand the structure
    logger.info("\n--- EXAMINING CHROMADB TABLES ---")
    examine_chromadb_tables()
    
    # Count documents by collection
    logger.info("\n--- COUNTING DOCUMENTS BY COLLECTION ---")
    count_documents_by_collection()
    
    # Match collections with directory UUIDs
    logger.info("\n--- MATCHING COLLECTIONS WITH UUID DIRECTORIES ---")
    matches = match_collection_uuids()
    
    # Suggest fixes for collection mapping issues
    logger.info("\n--- SUGGESTED FIXES ---")
    
    # First run in dry-run mode
    fix_collection_mappings(dry_run=True)
    
    # Prompt user to apply fixes
    while True:
        user_input = input("\nDo you want to apply the suggested fixes? (yes/no): ").strip().lower()
        if user_input in ['yes', 'y']:
            logger.info("\n--- APPLYING FIXES ---")
            fix_collection_mappings(dry_run=False)
            break
        elif user_input in ['no', 'n']:
            logger.info("No changes applied. Exiting.")
            break
        else:
            print("Please enter 'yes' or 'no'.")

if __name__ == "__main__":
    main() 