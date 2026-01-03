#!/usr/bin/env python3
"""
ChromaDB CLI Viewer
------------------
A command-line utility to inspect ChromaDB collections and list content from metadata.

Features:
 - Lists available Chroma collections
 - Extracts and displays unique files and videos from document metadata
 - Supports both traditional file content and YouTube video transcripts
 - Supports filtering by collection name
 - Shows video details like language, timestamps, and video IDs
 - Read-only access to ChromaDB

Usage:
  python chroma_viewer_cli.py [options]

Examples:
  python chroma_viewer_cli.py                    # List all collections and their content
  python chroma_viewer_cli.py -c my_collection   # Show content for specific collection
  python chroma_viewer_cli.py --list-collections # Only list collection names
  python chroma_viewer_cli.py --show-videos      # Show video content details
  python chroma_viewer_cli.py --debug            # Show all metadata details

Configuration:
 - By default, looks for Chroma persistence at:
       lamb-kb-server-stable/backend/data/chromadb
 - Override with env var CHROMA_DB_PATH or CLI flag --chroma-path
"""
from __future__ import annotations

import json
import os
import argparse
from pathlib import Path
from typing import Any, Dict, List, Set

# Attempt to import chromadb with a friendly error if missing
try:
    # Disable telemetry noise by default
    if os.environ.get("CHROMADB_DISABLE_TELEMETRY") is None:
        os.environ["CHROMADB_DISABLE_TELEMETRY"] = "1"
    import numpy as _np
    _np_version_tuple = tuple(int(p) for p in _np.__version__.split(".")[:2])
    if _np_version_tuple >= (2, 0):
        # Compatibility shim for NumPy 2.0+ with older chromadb versions
        try:
            if not hasattr(_np, "float_"):
                _np.float_ = _np.float64
            if not hasattr(_np, "int_"):
                _np.int_ = _np.int64
            if not hasattr(_np, "uint"):
                _np.uint = _np.uint64
        except Exception:
            pass
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except Exception as e:
    import traceback, sys
    detail = traceback.format_exc()
    msg = (
        "Failed to import 'chromadb'. This is usually due to one of:\n"
        "  - Package not installed: pip install chromadb\n"
        "  - Incompatible Python version\n"
        "  - Dependency conflict\n\n"
        f"Active interpreter: {sys.executable}\n"
        f"Error: {e}\n"
        f"Full traceback:\n{detail}\n"
    )
    raise SystemExit(msg)

# Paths
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHROMA_PATH = REPO_ROOT / "lamb-kb-server-stable" / "backend" / "data" / "chromadb"


def get_chroma_client(chroma_path: Path):
    """Create a ChromaDB client for the given path."""
    return chromadb.PersistentClient(
        path=str(chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
    )


def list_collections(client) -> List[Dict[str, Any]]:
    """List all collections in the ChromaDB."""
    cols = client.list_collections()
    out = []
    for c in cols:
        name = getattr(c, "name", None) or getattr(c, "_name", None) or c.name
        out.append({
            "name": name,
            "id": getattr(c, "id", None) or getattr(c, "_id", None) or getattr(c, "uuid", None),
        })
    return sorted(out, key=lambda d: d["name"].lower())


def get_collection(client, name: str):
    """Get a specific collection by name."""
    return client.get_collection(name=name)


def extract_filenames_from_collection(collection, batch_size: int = 1000, debug: bool = False) -> List[Dict[str, Any]]:
    """Extract filenames and metadata from a collection, including video content."""
    files_info = []
    seen_sources = set()  # Track unique sources to avoid duplicates
    offset = 0
    
    if debug:
        print("DEBUG: Sample metadata inspection...")
    
    while True:
        try:
            # Get a batch of documents with metadata
            result = collection.get(
                include=["metadatas"], 
                limit=batch_size, 
                offset=offset
            )
            
            metadatas = result.get("metadatas", [])
            if not metadatas:
                break
            
            # Debug: Show sample metadata structure
            if debug and offset == 0 and metadatas:
                print(f"DEBUG: First metadata keys: {list(metadatas[0].keys())}")
                print(f"DEBUG: Sample metadata: {metadatas[0]}")
                
            # Extract filenames and relevant info
            for metadata in metadatas:
                if metadata and isinstance(metadata, dict):
                    # Handle both file-based and video-based content
                    source = metadata.get("source", "")
                    source_url = metadata.get("source_url", "")
                    video_id = metadata.get("video_id", "")
                    ingestion_plugin = metadata.get("ingestion_plugin", "")
                    
                    # Determine the unique identifier for this content
                    unique_source = source_url or source or f"video:{video_id}"
                    
                    # Only process unique sources to avoid duplicates
                    if unique_source and unique_source not in seen_sources:
                        # Handle video content
                        if ingestion_plugin == "youtube_transcript_ingest" or video_id:
                            # This is video content
                            language = metadata.get("language", "")
                            chunk_count = metadata.get("chunk_count", "unknown")
                            start_timestamp = metadata.get("start_timestamp", "")
                            end_timestamp = metadata.get("end_timestamp", "")
                            
                            display_name = f"YouTube Video ({video_id})"
                            if language:
                                display_name += f" [{language}]"
                            
                            files_info.append({
                                "display_name": display_name,
                                "filename": f"{video_id}.video",
                                "source": source_url,
                                "description": f"YouTube video transcript in {language}",
                                "citation": f"YouTube: {video_id}",
                                "extension": "video",
                                "content_type": "video",
                                "video_id": video_id,
                                "language": language,
                                "chunk_count": chunk_count,
                                "start_timestamp": start_timestamp,
                                "end_timestamp": end_timestamp,
                                "ingestion_plugin": ingestion_plugin
                            })
                        else:
                            # This is file-based content (original logic)
                            original_filename = metadata.get("filename", "")
                            description = metadata.get("description", "")
                            citation = metadata.get("citation", "")
                            extension = metadata.get("extension", "")
                            
                            # Use the most descriptive name available
                            display_name = citation or description or original_filename
                            if not display_name:
                                display_name = os.path.basename(source)
                            
                            files_info.append({
                                "display_name": display_name,
                                "filename": original_filename,
                                "source": source,
                                "description": description,
                                "citation": citation,
                                "extension": extension,
                                "content_type": "file",
                            })
                        
                        seen_sources.add(unique_source)
            
            # Check if we got fewer results than requested (end of data)
            if len(metadatas) < batch_size:
                break
                
            offset += batch_size
            
        except Exception as e:
            print(f"Error processing batch at offset {offset}: {e}")
            break
    
    return files_info


def ensure_schema_topics(chroma_path: Path) -> bool:
    """Ensure 'topic' column exists in both 'collections' and 'segments' tables."""
    updated = False
    try:
        candidates = list(chroma_path.glob("*.sqlite*"))
        if not candidates:
            candidates = list(chroma_path.glob("**/*.sqlite*"))
        if not candidates:
            return False
        import sqlite3
        for db_file in candidates:
            try:
                conn = sqlite3.connect(str(db_file))
                cur = conn.cursor()
                for table in ("collections", "segments"):
                    cur.execute(f"PRAGMA table_info({table})")
                    cols = [r[1] for r in cur.fetchall()]
                    if "topic" not in cols:
                        try:
                            cur.execute(f"ALTER TABLE {table} ADD COLUMN topic TEXT")
                            print(f"Added missing 'topic' column to {table} in {db_file}")
                            updated = True
                        except Exception:
                            pass
                conn.commit()
                conn.close()
            except Exception:
                continue
        return updated
    except Exception:
        return updated


def main():
    parser = argparse.ArgumentParser(
        description="CLI tool to browse ChromaDB collections and extract filenames and video content",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--chroma-path", 
        help="Path to ChromaDB persistence directory"
    )
    parser.add_argument(
        "-c", "--collection", 
        help="Show filenames for specific collection only"
    )
    parser.add_argument(
        "--list-collections", 
        action="store_true",
        help="Only list collection names (no filenames)"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=1000,
        help="Batch size for processing large collections (default: 1000)"
    )
    parser.add_argument(
        "--enable-telemetry", 
        action="store_true",
        help="Allow ChromaDB telemetry (disabled by default)"
    )
    parser.add_argument(
        "--show-count", 
        action="store_true",
        help="Show document count for each collection"
    )
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Show debug information about metadata structure"
    )
    parser.add_argument(
        "--show-videos", 
        action="store_true",
        help="Show video content details (timestamps, language, etc.)"
    )
    
    args = parser.parse_args()
    
    # Handle telemetry setting
    if args.enable_telemetry:
        os.environ.pop("CHROMADB_DISABLE_TELEMETRY", None)
    
    # Determine ChromaDB path
    chroma_path = Path(args.chroma_path) if args.chroma_path else DEFAULT_CHROMA_PATH
    
    if not chroma_path.exists():
        print(f"Error: ChromaDB path not found: {chroma_path}")
        return 1
    
    print(f"Using ChromaDB path: {chroma_path}")
    
    try:
        # Create client and list collections
        client = get_chroma_client(chroma_path)
        collections = list_collections(client)
        
    except Exception as e:
        # Auto-heal for missing 'topic' column
        if "no such column: collections.topic" in str(e) or "no such column: segments.topic" in str(e):
            print("Attempting to fix missing 'topic' column...")
            healed = ensure_schema_topics(chroma_path)
            if healed:
                try:
                    client = get_chroma_client(chroma_path)
                    collections = list_collections(client)
                except Exception as e2:
                    print(f"Schema auto-heal failed: {e2}")
                    return 1
            else:
                print("Could not auto-heal schema. Manual intervention required.")
                return 1
        else:
            print(f"Error connecting to ChromaDB: {e}")
            return 1
    
    if not collections:
        print("No collections found in ChromaDB.")
        return 0
    
    print(f"\nFound {len(collections)} collection(s):")
    
    # If only listing collections
    if args.list_collections:
        for i, col in enumerate(collections, 1):
            if args.show_count:
                try:
                    collection = get_collection(client, col["name"])
                    count = collection.count()
                    print(f"  {i}. {col['name']} ({count} documents)")
                except Exception as e:
                    print(f"  {i}. {col['name']} (count error: {e})")
            else:
                print(f"  {i}. {col['name']}")
        return 0
    
    # Process collections for filenames
    target_collections = [col for col in collections if col["name"] == args.collection] if args.collection else collections
    
    if args.collection and not target_collections:
        print(f"Collection '{args.collection}' not found.")
        available = [col["name"] for col in collections]
        print(f"Available collections: {', '.join(available)}")
        return 1
    
    for col_info in target_collections:
        col_name = col_info["name"]
        print(f"\n--- Collection: {col_name} ---")
        
        try:
            collection = get_collection(client, col_name)
            
            if args.show_count:
                try:
                    count = collection.count()
                    print(f"Total documents: {count}")
                except Exception:
                    print("Total documents: unknown")
            
            print("Extracting filenames and sources...")
            files_info = extract_filenames_from_collection(collection, args.batch_size, args.debug)
            
            if files_info:
                # Separate files and videos for better organization
                file_items = [f for f in files_info if f.get("content_type") == "file"]
                video_items = [f for f in files_info if f.get("content_type") == "video"]
                
                # Sort by display name
                sorted_files = sorted(file_items, key=lambda x: x["display_name"].lower())
                sorted_videos = sorted(video_items, key=lambda x: x["display_name"].lower())
                all_items = sorted_files + sorted_videos
                
                print(f"Found {len(all_items)} unique item(s): {len(sorted_files)} file(s), {len(sorted_videos)} video(s)")
                
                if all_items:
                    # Calculate max lengths for alignment
                    max_name_len = max(len(f["display_name"]) for f in all_items) if all_items else 0
                    max_name_len = max(max_name_len, 15)  # minimum width for header
                    
                    # Print header
                    print(f"  {'#':>3} {'Document/Citation':<{max_name_len}} {'Type':<5} {'Ext':<4} Source")
                    print(f"  {'-' * 3} {'-' * max_name_len} {'-' * 5} {'-' * 4} {'-' * 30}")
                    
                    # Print items with info
                    for i, item_info in enumerate(all_items, 1):
                        display_name = item_info["display_name"]
                        content_type = item_info.get("content_type", "file")
                        extension = item_info["extension"] or "?"
                        source_short = item_info["source"]
                        
                        # Truncate source if too long
                        if len(source_short) > 40:
                            source_short = "..." + source_short[-37:]
                        
                        type_display = content_type[:5]  # Truncate to fit column
                        
                        print(f"  {i:3d} {display_name:<{max_name_len}} {type_display:<5} {extension:<4} {source_short}")
                
                # Show additional details if requested
                if args.debug or args.show_videos:
                    print(f"\nDETAILED INFO:")
                    for i, item_info in enumerate(all_items, 1):
                        # Skip file details unless debug mode is on
                        if item_info.get("content_type") == "file" and not args.debug:
                            continue
                            
                        print(f"\n{i}. {item_info['display_name']}")
                        
                        if item_info.get("content_type") == "video":
                            # Video-specific details
                            print(f"   Video ID: {item_info.get('video_id', 'N/A')}")
                            print(f"   Language: {item_info.get('language', 'N/A')}")
                            print(f"   Plugin: {item_info.get('ingestion_plugin', 'N/A')}")
                            if item_info.get('start_timestamp') and item_info.get('end_timestamp'):
                                print(f"   Time Range: {item_info['start_timestamp']} - {item_info['end_timestamp']}")
                            print(f"   Full Source: {item_info['source']}")
                        else:
                            # File-specific details (debug mode only)
                            print(f"   Filename: {item_info.get('filename', 'N/A')}")
                            print(f"   Description: {item_info.get('description', 'N/A')}")
                            print(f"   Citation: {item_info.get('citation', 'N/A')}")
                            print(f"   Full Source: {item_info['source']}")
            else:
                print("No files or videos found in metadata.")
                
        except Exception as e:
            print(f"Error processing collection '{col_name}': {e}")
    
    return 0


if __name__ == "__main__":
    exit(main())