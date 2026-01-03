#!/usr/bin/env python3
"""
Purge a single ingested file from the Lamb KB Server.

Given a file URL (as stored in file_registry.file_url), this script will:
  1) Locate the file entry in SQLite (lamb-kb-server.db)
  2) Find its owning collection and the corresponding ChromaDB collection
  3) Remove all embeddings for that file from ChromaDB (via Chroma Python API)
  4) Delete the physical file from the filesystem (and optionally derived .html)
  5) Remove the file entry from SQLite

Usage:
  python3 purge_file.py \
    --file-url "http://localhost:9090/static/1/convocatoria_ikasiker/a4b140223a3b4a399eca83f023e538a0.pdf"

Optional flags:
  --dry-run       : Show what would be deleted without performing deletions
  --yes           : Skip confirmation prompt

Notes:
  - ChromaDB persistence is at backend/data/chromadb
  - We match embeddings by metadata containing the file's hash (robust across .pdf/.html variants)
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import List, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings


# Paths (adjust if your deployment differs)
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "lamb-kb-server-stable" / "backend" / "data"
SQLITE_DB_PATH = DATA_DIR / "lamb-kb-server.db"
CHROMA_DB_PATH = DATA_DIR / "chromadb"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Purge a single file and its embeddings from Lamb KB Server")
    p.add_argument("--file-url", required=True, help="Exact file URL stored in file_registry.file_url (PDF URL)")
    p.add_argument("--dry-run", action="store_true", help="Print actions without deleting")
    p.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    return p.parse_args()


def get_db_conn() -> sqlite3.Connection:
    return sqlite3.connect(str(SQLITE_DB_PATH))


def fetch_file_entry(conn: sqlite3.Connection, file_url: str) -> Tuple:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, collection_id, original_filename, file_path, file_url, file_size, content_type,
               plugin_name, plugin_params, status, document_count, owner
        FROM file_registry
        WHERE file_url = ?
        """,
        (file_url,),
    )
    row = cur.fetchone()
    if row:
        return row
    # Fallback: search by hash fragment if exact URL not found
    hash_part = Path(file_url).stem  # e.g., a4b14.... from the URL
    cur.execute(
        """
        SELECT id, collection_id, original_filename, file_path, file_url, file_size, content_type,
               plugin_name, plugin_params, status, document_count, owner
        FROM file_registry
        WHERE file_url LIKE ? OR file_path LIKE ?
        ORDER BY id DESC
        """,
        (f"%{hash_part}%", f"%{hash_part}%"),
    )
    row = cur.fetchone()
    return row


def fetch_collection(conn: sqlite3.Connection, collection_id: int) -> Tuple[int, str, str]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, chromadb_uuid
        FROM collections
        WHERE id = ?
        """,
        (collection_id,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Collection id={collection_id} not found in SQLite")
    return row  # (id, name, chromadb_uuid)


def get_chroma_collection(collection_name: str):
    client = chromadb.PersistentClient(
        path=str(CHROMA_DB_PATH),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
    )
    # Prefer name access (used by the backend)
    return client.get_collection(name=collection_name)


def derive_hash_from_url(file_url: str) -> str:
    # Extract basename without extension as a robust hash key
    return Path(file_url).stem


def find_embedding_ids_for_file(chroma_collection, file_hash: str) -> List[str]:
    """
    Try to find all embedding/document ids whose metadata references this file via its hash.
    We attempt a metadata WHERE filter first; if unsupported, fallback to a scan.
    """
    ids: List[str] = []

    # Attempt metadata filter (newer Chroma versions)
    try:
        res = chroma_collection.get(
            where={"$or": [
                {"file_url": {"$contains": file_hash}},
                {"source": {"$contains": file_hash}},
                {"path": {"$contains": file_hash}},
            ]},
            include=["metadatas"],
        )
        if res and res.get("ids"):
            return list(res["ids"])  # type: ignore
    except Exception:
        pass

    # Fallback: scan in chunks to avoid loading everything at once
    offset = 0
    batch = 1000
    while True:
        res = chroma_collection.get(
            include=["metadatas"],
            limit=batch,
            offset=offset,
        )
        got = len(res.get("ids", []))
        if got == 0:
            break
        for idx, mid in enumerate(res.get("metadatas", [])):
            if not isinstance(mid, dict):
                continue
            joined_vals = "|".join(str(v) for v in mid.values())
            if file_hash in joined_vals:
                ids.append(res["ids"][idx])
        offset += got
    return ids


def delete_from_chroma(chroma_collection, ids: List[str], dry_run: bool = False) -> int:
    if not ids:
        return 0
    if dry_run:
        print(f"[dry-run] Would delete {len(ids)} embeddings from Chroma")
        return len(ids)
    chroma_collection.delete(ids=ids)
    return len(ids)


def delete_file(file_path: str, dry_run: bool = False) -> List[str]:
    removed: List[str] = []
    for path in [file_path, file_path.replace(".pdf", ".html")]:
        if os.path.exists(path):
            if dry_run:
                print(f"[dry-run] Would remove file: {path}")
            else:
                os.remove(path)
                removed.append(path)
    # remove directory if empty
    dir_path = os.path.dirname(file_path)
    try:
        if os.path.isdir(dir_path) and not os.listdir(dir_path):
            if dry_run:
                print(f"[dry-run] Would remove empty directory: {dir_path}")
            else:
                os.rmdir(dir_path)
    except Exception:
        pass
    return removed


def delete_sqlite_entry(conn: sqlite3.Connection, file_id: int, dry_run: bool = False) -> None:
    if dry_run:
        print(f"[dry-run] Would delete SQLite entry file_registry.id={file_id}")
        return
    cur = conn.cursor()
    cur.execute("DELETE FROM file_registry WHERE id = ?", (file_id,))
    conn.commit()


def main() -> int:
    args = parse_args()

    if not SQLITE_DB_PATH.exists():
        print(f"ERROR: SQLite DB not found: {SQLITE_DB_PATH}")
        return 2
    if not CHROMA_DB_PATH.exists():
        print(f"ERROR: Chroma DB path not found: {CHROMA_DB_PATH}")
        return 2

    # Confirm destructive action unless --yes
    if not args.yes and not args.dry_run:
        print("This will permanently delete embeddings (Chroma), DB entries, and files.")
        confirm = input("Type 'delete' to proceed: ")
        if confirm.strip().lower() != "delete":
            print("Aborted.")
            return 1

    conn = get_db_conn()
    try:
        row = fetch_file_entry(conn, args.file_url)
        if not row:
            print("ERROR: File entry not found in SQLite file_registry for given file URL")
            return 3

        (file_id, collection_id, original_filename, file_path, file_url, *_rest) = row
        print(f"Found file_registry entry: id={file_id}, collection_id={collection_id}")
        print(f" - original_filename: {original_filename}")
        print(f" - file_path        : {file_path}")
        print(f" - file_url         : {file_url}")

        col_row = fetch_collection(conn, collection_id)
        (_, collection_name, chroma_uuid) = col_row
        print(f"Collection: name='{collection_name}', chromadb_uuid={chroma_uuid}")

        # Connect to Chroma and find embeddings to delete
        collection = get_chroma_collection(collection_name)
        file_hash = derive_hash_from_url(file_url)
        to_delete_ids = find_embedding_ids_for_file(collection, file_hash)
        print(f"Embeddings matched for hash '{file_hash}': {len(to_delete_ids)}")

        # Delete from Chroma
        deleted_count = delete_from_chroma(collection, to_delete_ids, dry_run=args.dry_run)
        print(f"Deleted from Chroma: {deleted_count}")

        # Delete file(s) from filesystem
        removed_files = delete_file(file_path, dry_run=args.dry_run)
        if args.dry_run:
            print(f"[dry-run] Would remove: {file_path} (+ html if exists)")
        else:
            for p in removed_files:
                print(f"Removed file: {p}")

        # Delete entry from SQLite
        delete_sqlite_entry(conn, file_id, dry_run=args.dry_run)
        print("SQLite file_registry entry removed.")

        print("Done.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
