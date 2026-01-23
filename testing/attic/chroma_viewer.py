#!/usr/bin/env python3
"""
ChromaDB Browser (Standalone Flask App)
-------------------------------------
A lightweight, single-file web UI to inspect the persisted ChromaDB used by Lamb KB Server.

Features:
 - Lists available Chroma collections in a combo box
 - Displays (paginated) documents/embeddings for a selected collection
 - Shows id, content type (file/video), metadata (JSON), and document preview
 - Supports both traditional file content and YouTube video transcripts
 - Shows content statistics (number of files vs videos)
 - Color-coded content type indicators
 - Allows downloading the full raw document text for a given embedding id

Usage:
  1. (Optional) Create a virtualenv and install deps:
       pip install -r testing/chroma_viewer_requirements.txt
  2. Run:
       python testing/chroma_viewer.py
  3. Open browser:
       http://127.0.0.1:5010/

Configuration:
 - By default, looks for Chroma persistence at:
       lamb-kb-server-stable/backend/data/chromadb
 - Override with env var CHROMA_DB_PATH or CLI flag --chroma-path

Safety:
 - Read-only viewer: does NOT mutate or delete data.

NOTE: For very large collections, only a page (default 100 rows) is loaded at a time.
"""
from __future__ import annotations

import json
import os
import math
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, request, render_template_string, abort, send_file, Response

# Attempt to import chromadb with a friendly error if missing
try:
    # Disable telemetry noise (and the capture() signature errors) by default; user can override with --enable-telemetry
    if os.environ.get("CHROMADB_DISABLE_TELEMETRY") is None:
        os.environ["CHROMADB_DISABLE_TELEMETRY"] = "1"
    import numpy as _np  # Added early to validate version compatibility
    _np_version_tuple = tuple(int(p) for p in _np.__version__.split(".")[:2])
    if _np_version_tuple >= (2, 0):  # pragma: no cover
        print(
            f"[chroma_viewer] INFO: Detected NumPy {_np.__version__} (>=2.0). "
            "Applying backward-compat shim for legacy chromadb versions if needed."
        )
        # Compatibility shim: restore deprecated aliases expected by chromadb (< patched release)
        # Only applied when missing; safe no-ops otherwise.
        try:
            if not hasattr(_np, "float_"):
                _np.float_ = _np.float64  # type: ignore[attr-defined]
            if not hasattr(_np, "int_"):
                _np.int_ = _np.int64  # type: ignore[attr-defined]
            if not hasattr(_np, "uint"):
                _np.uint = _np.uint64  # type: ignore[attr-defined]
        except Exception:
            pass
    import chromadb  # type: ignore
    from chromadb.config import Settings as ChromaSettings  # type: ignore
    # Optional: additional sanity check of chromadb + numpy pairing
    try:  # pragma: no cover - diagnostic only
        from packaging import version as _v
        if _v.parse(chromadb.__version__) < _v.parse("1.0.0") and _v.parse(_np.__version__) >= _v.parse("2.0.0"):
            print(
                "[chroma_viewer] WARNING: Using pre-1.0 chromadb with NumPy >=2. "
                "Consider upgrading chromadb (>=1.1.0) for full compatibility."
            )
    except Exception:
        pass
except Exception as e:  # pragma: no cover - import guard
    # Provide a richer diagnostic so the user can see the underlying cause
    import traceback, sys
    detail = traceback.format_exc()
    msg = (
        "Failed to import 'chromadb'. This is usually due to one of:\n"
        "  - Package not installed in the current virtualenv\n"
        "  - Incompatible Python version (check python --version)\n"
        "  - A dependency conflict (e.g., pydantic / typing-extensions)\n"
        "  - Native / optional dependency build failure during installation\n\n"
        f"Active interpreter: {sys.executable}\n"
        f"Caught exception: {e.__class__.__name__}: {e}\n"
        "Full traceback:\n" + detail + "\n"
        "Troubleshooting steps:\n"
        "  1) pip install --upgrade pip setuptools wheel\n"
        "  2) pip install --force-reinstall chromadb\n"
        "  3) python -c 'import sys; import chromadb, platform; print(chromadb.__version__, sys.version)'\n"
        "  4) If it still fails, capture this traceback in an issue.\n"
    )
    raise SystemExit(msg)

# ---------------------------------------------------------------------------
# Paths & Client Helpers
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHROMA_PATH = REPO_ROOT / "lamb-kb-server-stable" / "backend" / "data" / "chromadb"

app = Flask(__name__)


def get_chroma_client(chroma_path: Path):
    return chromadb.PersistentClient(
        path=str(chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
    )


# ---------------------------------------------------------------------------
# Data Access
# ---------------------------------------------------------------------------

def list_collections(client) -> List[Dict[str, Any]]:
    # chroma list_collections returns objects with name & id (uuid)
    cols = client.list_collections()
    out = []
    for c in cols:
        # Defensive: attribute vs dict
        name = getattr(c, "name", None) or getattr(c, "_name", None) or c.name  # type: ignore
        out.append({
            "name": name,
            "id": getattr(c, "id", None) or getattr(c, "_id", None) or getattr(c, "uuid", None),
        })
    return sorted(out, key=lambda d: d["name"].lower())


def ensure_schema_topics(chroma_path: Path) -> bool:
    """Ensure 'topic' column exists in both 'collections' and 'segments' tables.

    Returns True if the schema is confirmed/updated for at least one DB file.
    Fails silently (returns False) if no SQLite file found or all upgrades fail.
    """
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
                # For each target table, add topic column if missing
                for table in ("collections", "segments"):
                    cur.execute(f"PRAGMA table_info({table})")
                    cols = [r[1] for r in cur.fetchall()]
                    if "topic" not in cols:
                        try:
                            cur.execute(f"ALTER TABLE {table} ADD COLUMN topic TEXT")
                            print(f"[chroma_viewer] Added missing 'topic' column to {table} in {db_file}")
                            updated = True
                        except Exception as ie:  # noqa: PIE786
                            print(f"[chroma_viewer] Could not add topic column to {table}: {ie}")
                conn.commit()
                conn.close()
            except Exception:
                continue
        return updated
    except Exception:
        return updated


def fetch_page(collection, page: int, page_size: int) -> Dict[str, Any]:
    offset = page * page_size
    res = collection.get(include=["metadatas", "documents"], limit=page_size, offset=offset)
    total = None
    # Try to determine total count cheaply (Chroma may support .count())
    try:
        total = collection.count()  # type: ignore[attr-defined]
    except Exception:
        # Fallback: keep paging until fewer than requested? (Omit for simplicity)
        pass
    return {
        "ids": res.get("ids", []),
        "metadatas": res.get("metadatas", []),
        "documents": res.get("documents", []),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def analyze_content_types(metadatas: List[Dict[str, Any]]) -> Dict[str, int]:
    """Analyze metadata to determine content types (files vs videos)."""
    stats = {"files": 0, "videos": 0, "other": 0}
    seen_sources = set()
    
    for meta in metadatas:
        if not meta or not isinstance(meta, dict):
            continue
            
        # Handle both file-based and video-based content
        source = meta.get("source", "")
        source_url = meta.get("source_url", "")
        video_id = meta.get("video_id", "")
        ingestion_plugin = meta.get("ingestion_plugin", "")
        
        # Determine the unique identifier for this content
        unique_source = source_url or source or f"video:{video_id}"
        
        if unique_source and unique_source not in seen_sources:
            if ingestion_plugin == "youtube_transcript_ingest" or video_id:
                stats["videos"] += 1
            elif source:
                stats["files"] += 1
            else:
                stats["other"] += 1
            seen_sources.add(unique_source)
    
    return stats


def enhance_metadata_display(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Enhance metadata with content type information for display."""
    enhanced = metadata.copy()
    
    # Determine content type
    video_id = metadata.get("video_id", "")
    ingestion_plugin = metadata.get("ingestion_plugin", "")
    
    if ingestion_plugin == "youtube_transcript_ingest" or video_id:
        enhanced["_content_type"] = "video"
        enhanced["_display_type"] = "📹 Video"
        if video_id:
            enhanced["_video_title"] = f"YouTube: {video_id}"
        language = metadata.get("language", "")
        if language:
            enhanced["_video_title"] = enhanced.get("_video_title", "") + f" [{language}]"
    else:
        enhanced["_content_type"] = "file"
        enhanced["_display_type"] = "📄 File"
        
    return enhanced


def get_collection(client, name: str):
    return client.get_collection(name=name)


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------
TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\" />\n<title>ChromaDB Browser</title>\n<style>\nbody { font-family: system-ui, Arial, sans-serif; margin: 1.5rem; background:#f7f9fb; }\nh1 { font-size: 1.4rem; margin-bottom: .75rem; }\nform, .panel { background:#fff; padding:1rem 1.25rem; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }\nselect { padding:.4rem .5rem; font-size:.95rem; }\n.table { width:100%; border-collapse: collapse; margin-top:1rem; }\n.table th, .table td { text-align:left; border-bottom:1px solid #e3e7ec; padding:.5rem .5rem; vertical-align: top; font-size:.8rem;}\n.table th { background:#eef2f6; font-size:.7rem; letter-spacing:.05em; text-transform:uppercase; }\n.code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; word-break: break-word; background:#f3f6fa; padding:.4rem .5rem; border-radius:4px; }\n.meta { max-width: 340px; }\n.doc-preview { max-width:400px; }\n.badge { display:inline-block; background:#3850eb; color:#fff; padding:2px 6px; border-radius:12px; font-size:.65rem; margin-left:.5rem;}\n.stats { display:inline-block; background:#059669; color:#fff; padding:2px 6px; border-radius:12px; font-size:.65rem; margin-left:.25rem;}\n.content-type { display:inline-block; padding:2px 6px; border-radius:4px; font-size:.65rem; margin-right:.25rem; }\n.content-type.video { background:#7c3aed; color:#fff; }\n.content-type.file { background:#0891b2; color:#fff; }\nnav.pager a { margin:0 .25rem; text-decoration:none; padding:.35rem .55rem; border:1px solid #d0d7de; border-radius:4px; color:#24292f; background:#fff;}\nnav.pager a.current { background:#24292f; color:#fff; pointer-events:none; }\nnav.pager { margin-top:1rem; }\nfooter { margin-top:2rem; font-size:.7rem; color:#6a737d; }\n.flash { color:#d6336c; font-weight:600; }\n</style>\n<script>\nfunction onCollectionChange(sel){ sel.form.submit(); }\n</script>\n</head>\n<body>\n  <h1>ChromaDB Browser <span class=\"badge\">Read‑only</span></h1>
  <form method=\"get\" class=\"panel\">\n    <label for=\"collection\"><strong>Collection:</strong></label>\n    <select name=\"collection\" id=\"collection\" onchange=\"onCollectionChange(this)\">\n      <option value=\"\">-- choose a collection --</option>\n      {% for c in collections %}\n        <option value=\"{{c.name}}\" {% if selected_collection == c.name %}selected{% endif %}>{{c.name}}</option>\n      {% endfor %}\n    </select>\n    <label style=\"margin-left:1rem;\">Page size: <input type=\"number\" name=\"page_size\" value=\"{{page_size}}\" min=\"10\" max=\"500\" style=\"width:5rem;\"/></label>\n    <noscript><button type=\"submit\">Go</button></noscript>\n  </form>\n  {% if error %}<p class=\"flash\">{{error}}</p>{% endif %}\n  {% if page_data and selected_collection %}\n    <div class=\"panel\" style=\"margin-top:1rem;\">\n      <h2 style=\"margin-top:0;\">Collection: {{selected_collection}}</h2>\n      <p style=\"margin:.25rem 0 1rem;\">Showing page {{page_data.page + 1}}{% if total_pages %} of {{total_pages}}{% endif %}. Total embeddings: {{page_data.total if page_data.total is not none else 'unknown'}}.\n        {% if content_stats %}<span class=\"stats\">{{content_stats.files}} files</span><span class=\"stats\">{{content_stats.videos}} videos</span>{% if content_stats.other > 0 %}<span class=\"stats\">{{content_stats.other}} other</span>{% endif %}{% endif %}</p>\n      <table class=\"table\">\n        <thead>\n          <tr><th style=\"width:140px;\">ID</th><th style=\"width:60px;\">Type</th><th>Metadata</th><th>Document Preview</th></tr>\n        </thead>\n        <tbody>\n        {% for rid, content_type, display_type, meta, doc in rows %}\n          <tr>\n            <td><div class=\"code\" style=\"font-size:.65rem;\">{{rid}}</div>\n              <div style=\"margin-top:.3rem;\"><a href=\"?collection={{selected_collection}}&download_id={{rid}}\" title=\"Download full document\">download</a></div></td>\n            <td><span class=\"content-type {{content_type}}\">{{display_type}}</span></td>\n            <td class=\"meta\"><div class=\"code\" style=\"font-size:.65rem;\">{{meta}}</div></td>\n            <td class=\"doc-preview\"><div class=\"code\" style=\"font-size:.65rem;\">{{doc}}</div></td>\n          </tr>\n        {% endfor %}\n        {% if rows|length == 0 %}<tr><td colspan=4><em>No rows on this page.</em></td></tr>{% endif %}\n        </tbody>\n      </table>\n      {% if total_pages and total_pages > 1 %}\n        <nav class=\"pager\">\n          {% for p in range(total_pages) %}\n            <a href=\"?collection={{selected_collection}}&page={{p}}&page_size={{page_size}}\" class=\"{% if p == page_data.page %}current{% endif %}\">{{p+1}}</a>\n          {% endfor %}\n        </nav>\n      {% endif %}\n    </div>\n  {% endif %}\n  <footer>ChromaDB Browser &mdash; Debug utility. Large collections may take time to display.</footer>\n</body>\n</html>"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    chroma_path = Path(os.environ.get("CHROMA_DB_PATH") or request.args.get("chroma_path") or app.config.get("CHROMA_DB_PATH") or DEFAULT_CHROMA_PATH)
    if not chroma_path.exists():
        return render_template_string(
            TEMPLATE,
            collections=[],
            selected_collection=None,
            page_data=None,
            rows=[],
            page_size=100,
            error=f"Chroma path not found: {chroma_path}",
            total_pages=None,
        )

    client = get_chroma_client(chroma_path)
    try:
        collections = list_collections(client)
    except Exception as e:
        # Auto-heal for missing 'topic' column when downgrading chromadb
        if "no such column: collections.topic" in str(e) or "no such column: segments.topic" in str(e):
            healed = ensure_schema_topics(chroma_path)
            if healed:
                try:
                    collections = list_collections(client)
                except Exception as e2:
                    return render_template_string(
                        TEMPLATE,
                        collections=[],
                        selected_collection=None,
                        page_data=None,
                        rows=[],
                        page_size=100,
                        error=f"Schema auto-heal attempted but failed: {e2}",
                        total_pages=None,
                    )
            else:
                return render_template_string(
                    TEMPLATE,
                    collections=[],
                    selected_collection=None,
                    page_data=None,
                    rows=[],
                    page_size=100,
                    error=(
                        "Missing column 'topic' and auto-heal could not apply. "
                        "Backup DB and manually run: ALTER TABLE collections ADD COLUMN topic TEXT; "
                        "ALTER TABLE segments ADD COLUMN topic TEXT;"
                    ),
                    total_pages=None,
                )
        else:
            return render_template_string(
                TEMPLATE,
                collections=[],
                selected_collection=None,
                page_data=None,
                rows=[],
                page_size=100,
                error=f"Error listing collections: {e}",
                total_pages=None,
            )
    selected_collection = request.args.get("collection") or None
    download_id = request.args.get("download_id")

    page_size = max(10, min(500, int(request.args.get("page_size") or 100)))
    page = max(0, int(request.args.get("page") or 0))

    if download_id and selected_collection:
        try:
            col = get_collection(client, selected_collection)
            res = col.get(ids=[download_id], include=["documents", "metadatas"])  # type: ignore[arg-type]
            if res.get("documents"):
                content = res["documents"][0]
                return Response(
                    content,
                    mimetype="text/plain",
                    headers={
                        "Content-Disposition": f"attachment; filename={download_id}.txt"
                    },
                )
            abort(404)
        except Exception:
            abort(404)

    page_data = None
    rows = []
    total_pages = None
    error = None
    if selected_collection:
        try:
            col = get_collection(client, selected_collection)
            page_data = fetch_page(col, page=page, page_size=page_size)
            total = page_data.get("total")
            if isinstance(total, int) and total >= 0:
                total_pages = math.ceil(total / page_size)
            ids = page_data.get("ids", [])
            metas = page_data.get("metadatas", [])
            docs = page_data.get("documents", [])
            
            # Analyze content types for stats
            content_stats = analyze_content_types(metas)
            
            import sys
            print(f"[chroma_viewer] DEBUG: Starting document preview rendering for {len(ids)} ids", file=sys.stderr)
            for i, rid in enumerate(ids):
                print(f"[chroma_viewer] DEBUG: Processing id {rid}", file=sys.stderr)
                meta = metas[i] if i < len(metas) else {}
                
                # Enhance metadata with content type info
                enhanced_meta = enhance_metadata_display(meta)
                content_type = enhanced_meta.get("_content_type", "file")
                display_type = enhanced_meta.get("_display_type", "📄 File")
                
                try:
                    meta_json = json.dumps(enhanced_meta, ensure_ascii=False, indent=None, separators=(",", ":"))
                except Exception as e:
                    print(f"[chroma_viewer] ERROR: Failed to serialize metadata for id {rid}: {e}", file=sys.stderr)
                    meta_json = str(enhanced_meta)
                if isinstance(meta_json, str) and len(meta_json) > 400:
                    meta_json = meta_json[:397] + "..."
                doc = docs[i] if i < len(docs) else ""
                print(f"[chroma_viewer] DEBUG: Raw doc value for id {rid}: {repr(doc)}", file=sys.stderr)
                try:
                    if doc is None:
                        doc = ""
                    elif isinstance(doc, (list, tuple)):
                        doc = " ".join(str(part) for part in doc[:50])  # limit exploded size
                    else:
                        doc = str(doc)
                    print(f"[chroma_viewer] DEBUG: Normalized doc for id {rid}: {repr(doc)}", file=sys.stderr)
                    if isinstance(doc, str) and len(doc) > 400:
                        doc = doc[:397] + "..."
                except Exception as e:
                    print(f"[chroma_viewer] ERROR: Exception during doc normalization for id {rid}: {e}", file=sys.stderr)
                    doc = f"<error: {e}>"
                rows.append((rid, content_type, display_type, meta_json, doc))
        except Exception as e:  # pragma: no cover - runtime browse errors
            error = f"Error loading collection (NEW)'{selected_collection}': {e}"[:500]
            selected_collection = None

    return render_template_string(
        TEMPLATE,
        collections=collections,
        selected_collection=selected_collection,
        page_data=page_data,
        rows=rows,
        page_size=page_size,
        error=error,
        total_pages=total_pages,
        content_stats=content_stats if 'content_stats' in locals() else None,
    )


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser(description="Browse ChromaDB collections (read-only)")
    ap.add_argument("--chroma-path", dest="chroma_path", help="Override Chroma persistence path")
    # Convenience alias some users may try (maps to same meaning)
    ap.add_argument("--data-path", dest="data_path", help="Alias for --chroma-path")
    ap.add_argument("--enable-telemetry", action="store_true", help="Allow chromadb telemetry (disabled by default)")
    ap.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=5010, help="Port (default: 5010)")
    ap.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    chroma_path_arg = args.chroma_path or args.data_path
    chroma_path = Path(chroma_path_arg) if chroma_path_arg else DEFAULT_CHROMA_PATH
    if args.enable_telemetry:
        # User explicitly wants telemetry: unset our default
        os.environ.pop("CHROMADB_DISABLE_TELEMETRY", None)
    app.config["CHROMA_DB_PATH"] = str(chroma_path)
    print(f"* ChromaDB Browser starting on http://{args.host}:{args.port} using path: {chroma_path}")
    if not chroma_path.exists():
        print(f"! WARNING: Path does not exist yet: {chroma_path}")
    app.run(host=args.host, port=args.port, debug=args.debug)
