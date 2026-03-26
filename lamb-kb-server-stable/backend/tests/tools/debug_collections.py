#!/usr/bin/env python3
"""
Script to diagnose ChromaDB collection issues by analyzing ChromaDB internals.
This script is read-only and doesn't make any changes to the database.
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
    
    # First check the actual columns in the collections table
    cursor.execute("PRAGMA table_info(collections)")
    available_columns = [row[1] for row in cursor.fetchall()]
    logger.info(f"Available columns in collections table: {available_columns}")
    
    # Construct a query based on available columns
    query_columns = ['id', 'name']
    
    # Only include columns that actually exist
    query = f"SELECT {', '.join(query_columns)} FROM collections"
    
    cursor.execute(query)
    collections = [dict(zip(query_columns, row)) for row in cursor.fetchall()]
    
    # Get additional metadata if available
    if 'collection_metadata' in get_table_names(conn):
        for collection in collections:
            try:
                metadata_cursor = conn.cursor()
                metadata_cursor.execute("SELECT key, value FROM collection_metadata WHERE collection_id = ?", (collection['id'],))
                metadata = {row[0]: row[1] for row in metadata_cursor.fetchall()}
                collection['metadata'] = metadata
            except Exception as e:
                logger.error(f"Error fetching metadata for collection {collection['id']}: {e}")
    
    conn.close()
    return collections

def get_table_names(conn):
    """Get all table names from a SQLite connection"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cursor.fetchall()]

def get_chromadb_collections_api():
    """Get collections from ChromaDB API"""
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        
        # In Chroma v0.6.0, list_collections only returns collection names
        collection_names = client.list_collections()
        logger.info(f"ChromaDB API collection names: {collection_names}")
        
        # Get more details about each collection
        result = []
        for name in collection_names:
            try:
                # Get the collection object
                collection = client.get_collection(name)
                collection_info = {'name': name}
                
                # Get count if possible
                try:
                    count = collection.count()
                    collection_info['count'] = count
                except Exception as e:
                    logger.error(f"Error getting count for collection {name}: {e}")
                
                result.append(collection_info)
            except Exception as e:
                logger.error(f"Error getting collection {name}: {e}")
        
        return result
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

def analyze_collection_uuids():
    """Analyze collection UUIDs and names across databases"""
    # Get collections from both sources
    sqlite_collections = get_sqlite_collections()
    chroma_collections = get_chromadb_collections_from_sqlite()
    chroma_api_collections = get_chromadb_collections_api()
    uuid_dirs = examine_directory_uuids()
    
    # Make lookups by name
    sqlite_by_name = {col['name']: col for col in sqlite_collections}
    chroma_by_name = {col['name']: col for col in chroma_collections}
    chroma_api_by_name = {col['name']: col for col in chroma_api_collections}
    
    # Print SQLite collections
    logger.info("\n--- SQLITE COLLECTIONS ---")
    for col in sqlite_collections:
        logger.info(f"SQLite Collection: {col['name']} (ID: {col['id']})")
    
    # Print ChromaDB collections from internal SQLite
    logger.info("\n--- CHROMADB INTERNAL COLLECTIONS ---")
    for col in chroma_collections:
        logger.info(f"ChromaDB Collection: {col['name']} (ID: {col['id']})")
    
    # Print ChromaDB collections from API
    logger.info("\n--- CHROMADB API COLLECTIONS ---")
    for col in chroma_api_collections:
        count = col.get('count', 'unknown')
        logger.info(f"ChromaDB API Collection: {col['name']} (Count: {count})")
    
    # Print UUID directories
    logger.info("\n--- UUID DIRECTORIES IN CHROMADB ---")
    for uuid_dir in uuid_dirs:
        logger.info(f"UUID Directory: {uuid_dir['uuid']}")
        
    # Analyze mismatches
    logger.info("\n--- ANALYSIS RESULTS ---")
    
    # Check collections in SQLite but not in ChromaDB
    for col in sqlite_collections:
        if col['name'] not in chroma_by_name and col['name'] not in chroma_api_by_name:
            logger.warning(f"❌ SQLite collection '{col['name']}' has no matching ChromaDB collection")
    
    # Check collections in ChromaDB but not in SQLite
    for col in chroma_collections:
        if col['name'] not in sqlite_by_name:
            logger.warning(f"⚠️ ChromaDB collection '{col['name']}' has no matching SQLite record")
    
    # Check for UUID directories with no matching collection
    for uuid_dir in uuid_dirs:
        uuid_value = uuid_dir['uuid']
        found = False
        for col in chroma_collections:
            if col['id'] == uuid_value:
                found = True
                break
        
        if not found:
            logger.warning(f"⚠️ UUID directory '{uuid_value}' doesn't match any known ChromaDB collection")

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
    
    # Examine embeddings table structure first
    if 'embeddings' in tables:
        cursor.execute("PRAGMA table_info(embeddings)")
        columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Embeddings table columns: {columns}")
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        count = cursor.fetchone()[0]
        logger.info(f"Embeddings table count: {count}")
        
        # Try to find which column holds the collection reference
        collection_column = None
        for possible_name in ['collection_id', 'segment_id', 'uuid']:
            if possible_name in columns:
                collection_column = possible_name
                break
        
        if collection_column:
            cursor.execute(f"SELECT {collection_column}, COUNT(*) FROM embeddings GROUP BY {collection_column}")
            collection_counts = cursor.fetchall()
            logger.info(f"Embeddings by {collection_column}:")
            for coll_id, count in collection_counts:
                logger.info(f"  {collection_column} {coll_id}: {count} embeddings")
        else:
            logger.warning("Could not find a column to group embeddings by collection")
            
            # Show a sample row to help understand the structure
            cursor.execute("SELECT * FROM embeddings LIMIT 1")
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                row = cursor.fetchone()
                if row:
                    sample = dict(zip(columns, row))
                    logger.info(f"Sample embedding row: {sample.keys()}")
    
    # Examine segments table to map between segments and collections
    if 'segments' in tables:
        examine_segments_table(conn)
    
    conn.close()

def count_documents_by_collection():
    """Count documents in each ChromaDB collection"""
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        collection_names = client.list_collections()
        
        for name in collection_names:
            try:
                collection = client.get_collection(name)
                count = collection.count()
                logger.info(f"Collection '{name}': {count} documents")
            except Exception as e:
                logger.error(f"Error counting documents in collection '{name}': {e}")
    except Exception as e:
        logger.error(f"Error connecting to ChromaDB API: {e}")

def examine_segments_table(conn):
    """Examine the segments table to find collection-segment relationships"""
    cursor = conn.cursor()
    
    if 'segments' not in get_table_names(conn):
        logger.error("No segments table found")
        return
    
    # Check columns
    cursor.execute("PRAGMA table_info(segments)")
    columns = [row[1] for row in cursor.fetchall()]
    logger.info(f"Segments table columns: {columns}")
    
    # Only proceed if we have the expected columns
    if 'id' in columns and 'collection_id' in columns:
        cursor.execute("SELECT id, collection_id FROM segments")
        segments = cursor.fetchall()
        
        # Map segments to collections
        segment_to_collection = {}
        for segment_id, collection_id in segments:
            segment_to_collection[segment_id] = collection_id
            
        logger.info(f"Found {len(segments)} segments mapped to collections")
        
        # Link segment IDs from embeddings to collections
        if 'embeddings' in get_table_names(conn):
            cursor.execute("SELECT segment_id, COUNT(*) FROM embeddings GROUP BY segment_id")
            segment_counts = cursor.fetchall()
            
            logger.info("Segment-Collection mapping with embedding counts:")
            for segment_id, count in segment_counts:
                collection_id = segment_to_collection.get(segment_id, "unknown")
                logger.info(f"  Segment {segment_id}: {count} embeddings, Collection: {collection_id}")
    else:
        logger.warning("Segments table doesn't have expected columns")

def main():
    """Main function"""
    logger.info("Diagnosing ChromaDB collections (read-only)")
    
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
    
    # Analyze collections with directory UUIDs
    logger.info("\n--- ANALYZING COLLECTIONS ACROSS DATABASES ---")
    analyze_collection_uuids()
    
    logger.info("\nDiagnostic complete. This script is read-only and has not made any changes.")

if __name__ == "__main__":
    main() 