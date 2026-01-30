#!/usr/bin/env python3
"""
Script to check and compare collections in both SQLite and ChromaDB
(Updated for ChromaDB v0.6.0+)
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
    """Check collections in ChromaDB (for v0.6.0+)"""
    
    if not os.path.exists(CHROMA_DB_PATH):
        logger.error(f"ChromaDB directory not found at: {CHROMA_DB_PATH}")
        return []
    
    try:
        # Connect to ChromaDB
        logger.info(f"Connecting to ChromaDB at: {CHROMA_DB_PATH}")
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        
        # In ChromaDB v0.6.0+, list_collections() returns just the collection names
        collections_list = client.list_collections()
        logger.info(f"Found {len(collections_list)} collections in ChromaDB: {[c.name for c in collections_list]}")
        
        # Get details for each collection
        chroma_collections = []
        for collection in collections_list:
            try:
                collection_name = collection.name
                
                # Try to get the collection to verify it exists and get more info
                coll = client.get_collection(name=collection_name)
                
                # Get collection info
                collection_info = {
                    'name': collection_name,
                    'metadata': coll.metadata or {},
                }
                
                # Get document count
                try:
                    count = coll.count()
                    collection_info['count'] = count
                except Exception as e:
                    logger.error(f"Error getting count for collection {collection_name}: {e}")
                    collection_info['count'] = -1
                
                # Get sample records if collection has documents
                try:
                    if count > 0:
                        sample = coll.get(limit=1, include=['metadatas', 'documents'])
                        collection_info['sample'] = sample
                    else:
                        collection_info['sample'] = None
                except Exception as e:
                    logger.error(f"Error getting sample for collection {collection_name}: {e}")
                    collection_info['sample'] = None
                
                chroma_collections.append(collection_info)
                
            except Exception as e:
                logger.error(f"Error processing collection {collection.name}: {e}")
        
        return chroma_collections
        
    except Exception as e:
        logger.error(f"Error checking ChromaDB: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
        
        # If we have the internal ChromaDB SQLite file, check its contents
        if dir_info.get('chroma.sqlite3', {}).get('exists', True):
            try:
                db_path = os.path.join(CHROMA_DB_PATH, 'chroma.sqlite3')
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # List all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                dir_info['chroma_tables'] = tables
                
                # Check for collections table (if it exists)
                if 'collections' in tables:
                    cursor.execute("SELECT COUNT(*) FROM collections")
                    count = cursor.fetchone()[0]
                    dir_info['collections_count'] = count
                    
                    # Get some collection details
                    cursor.execute("SELECT name, id FROM collections LIMIT 10")
                    collections = [{'name': row[0], 'id': row[1]} for row in cursor.fetchall()]
                    dir_info['collection_names'] = collections
                
                conn.close()
            except Exception as e:
                logger.error(f"Error examining ChromaDB SQLite file: {e}")
        
        return dir_info
        
    except Exception as e:
        logger.error(f"Error checking ChromaDB directory: {e}")
        return {'error': str(e)}

def check_for_collection_name_mismatch():
    """Check if collection names in SQLite match their names in ChromaDB"""
    
    try:
        # Connect to SQLite db
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get collections from SQLite
        cursor.execute("SELECT id, name FROM collections")
        sqlite_collections = {row['id']: row['name'] for row in cursor.fetchall()}
        
        # Connect to ChromaDB SQLite directly
        chroma_db_path = os.path.join(CHROMA_DB_PATH, 'chroma.sqlite3')
        if not os.path.exists(chroma_db_path):
            logger.error(f"ChromaDB SQLite file not found at: {chroma_db_path}")
            return {}
            
        chroma_conn = sqlite3.connect(chroma_db_path)
        chroma_cursor = chroma_conn.cursor()
        
        # Check if collections table exists
        chroma_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collections'")
        if not chroma_cursor.fetchone():
            logger.error("Collections table not found in ChromaDB SQLite")
            return {}
        
        # Get collections from ChromaDB SQLite
        chroma_cursor.execute("SELECT name, id, topic, metadata FROM collections")
        chroma_collections = {}
        
        for row in chroma_cursor.fetchall():
            name, id, topic, metadata = row
            
            # ChromaDB may store collection info in metadata
            meta_info = {}
            if metadata:
                try:
                    meta_info = json.loads(metadata)
                except:
                    pass
            
            # Store collection info
            chroma_collections[name] = {
                'id': id,
                'topic': topic,
                'metadata': meta_info
            }
        
        # Close connections
        conn.close()
        chroma_conn.close()
        
        # Check for matches by name
        matches = {}
        for sqlite_id, sqlite_name in sqlite_collections.items():
            if sqlite_name in chroma_collections:
                matches[sqlite_id] = {
                    'sqlite_name': sqlite_name,
                    'chroma_name': sqlite_name,
                    'match_type': 'exact'
                }
            else:
                # Look for potential matches
                for chroma_name in chroma_collections:
                    if (sqlite_name.lower() == chroma_name.lower() or 
                        sqlite_name in chroma_name or 
                        chroma_name in sqlite_name):
                        matches[sqlite_id] = {
                            'sqlite_name': sqlite_name,
                            'chroma_name': chroma_name,
                            'match_type': 'fuzzy'
                        }
                        break
        
        return {
            'sqlite_collections': sqlite_collections,
            'chroma_collections': chroma_collections,
            'matches': matches
        }
            
    except Exception as e:
        logger.error(f"Error checking for collection name mismatches: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {}

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
            
            # Show ChromaDB SQLite info
            if 'chroma_tables' in dir_info:
                logger.info(f"ChromaDB SQLite tables: {dir_info['chroma_tables']}")
            
            if 'collections_count' in dir_info:
                logger.info(f"ChromaDB collections count (from SQLite): {dir_info['collections_count']}")
            
            if 'collection_names' in dir_info:
                logger.info(f"ChromaDB collection names (from SQLite): {[c['name'] for c in dir_info['collection_names']]}")
        else:
            logger.error("ChromaDB SQLite file not found!")
    
    # Check for collection name mismatches
    logger.info("\n--- CHECKING FOR COLLECTION NAME MISMATCHES ---")
    mismatch_results = check_for_collection_name_mismatch()
    
    if mismatch_results:
        sqlite_collections = mismatch_results.get('sqlite_collections', {})
        chroma_collections = mismatch_results.get('chroma_collections', {})
        matches = mismatch_results.get('matches', {})
        
        logger.info(f"SQLite collections: {len(sqlite_collections)}")
        logger.info(f"ChromaDB collections: {len(chroma_collections)}")
        logger.info(f"Matches found: {len(matches)}")
        
        # Log the collections in ChromaDB that aren't recognized
        sqlite_ids = set(sqlite_collections.keys())
        matched_ids = set(matches.keys())
        unmatched_ids = sqlite_ids - matched_ids
        
        if unmatched_ids:
            logger.warning(f"Unmatched SQLite collections: {len(unmatched_ids)}")
            for id in unmatched_ids:
                name = sqlite_collections[id]
                logger.warning(f"  ID: {id}, Name: {name}")
        
        # Check for potential collection name differences
        logger.info("\nCollection name matches:")
        for sqlite_id, match_info in matches.items():
            sqlite_name = match_info['sqlite_name']
            chroma_name = match_info['chroma_name']
            match_type = match_info['match_type']
            
            if match_type == 'exact':
                logger.info(f"  ✅ SQLite ID {sqlite_id}: '{sqlite_name}' matches ChromaDB name")
            else:
                logger.warning(f"  ⚠️ SQLite ID {sqlite_id}: '{sqlite_name}' fuzzy matches ChromaDB name '{chroma_name}'")
    
    # Compare collections
    compare_collections()
    
    # Offer guidance if collections are missing
    if len(check_chromadb_collections()) < len(check_sqlite_collections()):
        logger.warning("\n--- POSSIBLE SOLUTIONS ---")
        logger.warning("Some collections are missing from ChromaDB. Possible solutions:")
        logger.warning("1. Check for ID/name mismatches between SQLite and ChromaDB")
        logger.warning("2. Verify if ChromaDB is using the correct storage directory")
        logger.warning("3. Consider rebuilding the ChromaDB collections from the SQLite data")
        logger.warning("4. If you're using numeric or integer IDs as collection names in API calls, try using the actual string name")
    
if __name__ == "__main__":
    main() 