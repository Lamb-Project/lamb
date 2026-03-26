#!/usr/bin/env python3
"""
Normalize double-encoded JSON in the KB server collections table.

Some collections have their embeddings_model stored as double-encoded JSON strings
(e.g., "\"{...}\"" instead of "{...}"), which breaks json_extract queries.

This script fixes all affected collections by:
1. Detecting double-encoded JSON (starts with quote character)
2. Parsing and re-saving as proper JSON
"""

import sqlite3
import json
import sys

DB_PATH = "/opt/lamb/lamb-kb-server-stable/backend/data/lamb-kb-server.db"

def normalize_embeddings_json():
    """Normalize all double-encoded embeddings_model JSON in collections table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all collections
    cursor.execute("SELECT id, name, embeddings_model FROM collections")
    collections = cursor.fetchall()
    
    fixed_count = 0
    already_ok = 0
    
    print(f"Found {len(collections)} collections to check...")
    print()
    
    for collection_id, name, embeddings_model in collections:
        if embeddings_model is None:
            print(f"  [{collection_id}] {name}: NULL embeddings_model (skipping)")
            continue
            
        # Check if it's double-encoded (starts with a quote)
        if embeddings_model.startswith('"'):
            print(f"  [{collection_id}] {name}: DOUBLE-ENCODED - fixing...")
            
            try:
                # Parse once to get the JSON string, then parse again to get the object
                json_string = json.loads(embeddings_model)
                json_object = json.loads(json_string)
                
                # Verify it's valid
                apikey = json_object.get('apikey', 'NOT SET')
                model = json_object.get('model', 'NOT SET')
                
                # Re-save as proper JSON (not string)
                normalized_json = json.dumps(json_object)
                
                cursor.execute(
                    "UPDATE collections SET embeddings_model = ? WHERE id = ?",
                    (normalized_json, collection_id)
                )
                
                print(f"      ✓ Fixed! (model: {model}, apikey: {apikey[:20]}...)")
                fixed_count += 1
                
            except Exception as e:
                print(f"      ✗ ERROR: {e}")
        else:
            # Already properly formatted
            try:
                json_object = json.loads(embeddings_model)
                apikey = json_object.get('apikey', 'NOT SET')
                model = json_object.get('model', 'NOT SET')
                print(f"  [{collection_id}] {name}: OK (model: {model}, apikey: {apikey[:20] if apikey != 'NOT SET' else 'NOT SET'}...)")
                already_ok += 1
            except Exception as e:
                print(f"  [{collection_id}] {name}: PARSE ERROR - {e}")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print()
    print("=" * 60)
    print(f"Summary:")
    print(f"  Fixed:      {fixed_count}")
    print(f"  Already OK: {already_ok}")
    print(f"  Total:      {len(collections)}")
    print("=" * 60)
    
    return fixed_count

if __name__ == "__main__":
    print("=" * 60)
    print("Normalizing KB Collections Embeddings JSON")
    print("=" * 60)
    print()
    
    fixed = normalize_embeddings_json()
    
    if fixed > 0:
        print()
        print("✓ Database normalized successfully!")
        print()
        print("You can now verify with:")
        print("  sqlite3 " + DB_PATH + " \\")
        print("    \"SELECT id,name,json_extract(embeddings_model,'$.apikey') AS apikey FROM collections WHERE owner='1' ORDER BY id;\"")
    else:
        print()
        print("✓ No fixes needed - all collections already have properly formatted JSON!")
    
    sys.exit(0)
