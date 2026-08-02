#!/usr/bin/env python3
"""Bundle and restore a complete LAMB installation state.

A checkpoint is not a file. It is the LAMB database, Open WebUI's own database
with its uploads and vector store, the knowledge-base vector store, the Library
Manager's data, and user content under static. Miss one and a restored baseline
is subtly wrong in ways the tests above it cannot see — which is worse than
having no baseline at all.

Two traps this handles:

* **Write-ahead logs.** Copying a `.db` file while its `-wal` sibling holds
  recent commits loses those commits silently. Databases are snapshotted with
  SQLite's backup API, which produces one consistent file and needs no
  stop-the-world.
* **Services holding files open.** Restore replaces files underneath running
  processes, so it refuses unless the stack is down (or `--force` is given).

Usage:
    python3 testing/baseline/bundle.py save base-enchilada
    python3 testing/baseline/bundle.py list
    python3 testing/baseline/bundle.py verify base-enchilada
    python3 testing/baseline/bundle.py restore base-enchilada
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

LAMB = Path("/opt/lamb")
CHECKPOINTS = Path(__file__).resolve().parent / "checkpoints"

# What makes up a LAMB installation's state. Order is irrelevant; completeness
# is everything. Paths that do not exist yet (the new KB server before its first
# ingestion) are recorded as absent rather than treated as an error.
DATABASES = {
    "lamb": "lamb_v4.db",
    "owi": "open-webui/backend/data/webui.db",
    "kb_legacy": "lamb-kb-server-stable/backend/data/lamb-kb-server.db",
    "library": "library-manager/data/library-manager.db",
    "kb_v2": "lamb-kb-server/backend/data/kb-server.db",
}

TREES = {
    "kb_vectors": "lamb-kb-server-stable/backend/data/chromadb",
    "library_content": "library-manager/data/content",
    "owi_uploads": "open-webui/backend/data/uploads",
    "owi_vectors": "open-webui/backend/data/vector_db",
    "static_json": "backend/static/json",
    "static_md": "backend/static/md",
}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _snapshot_db(src: Path, dest: Path) -> dict:
    """Consistent single-file copy, write-ahead log included."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Not mode=ro: a write-ahead-log database cannot be opened read-only without
    # its shared-memory file, and SQLite refuses. The backup API only reads.
    source = sqlite3.connect(str(src))
    target = sqlite3.connect(dest)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return {"present": True, "bytes": dest.stat().st_size, "sha256_16": _sha(dest)}


def _integrity(path: Path) -> str:
    """SQLite's own verdict on a database file. Cheap, and the only way to know
    a copy is usable rather than merely present."""
    try:
        con = sqlite3.connect(str(path))
        try:
            return con.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            con.close()
    except sqlite3.DatabaseError as e:
        return f"unreadable: {e}"


def _stack_running() -> list[str]:
    try:
        out = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return []
    return [n for n in out.split() if n.startswith("lamb-")]


def save(name: str, force: bool = False) -> Path:
    running = _stack_running()
    if running and not force:
        raise SystemExit(
            "refusing to save while the stack is running.\n"
            "These databases sit on the host and reach the containers through a\n"
            "Docker bind mount. SQLite coordinates access with POSIX advisory locks,\n"
            "and those are not reliably shared across that boundary — a host process\n"
            "reading while a containerised process writes is two parties with no\n"
            "common view of the locks. That corrupted a table here on 2026-08-02.\n"
            f"running: {', '.join(running)}\n"
            f"stop them first (docker stop {' '.join(running)}), or pass --force")
    dest = CHECKPOINTS / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    manifest: dict = {
        "name": name,
        "created_at": int(time.time()),
        "git_commit": subprocess.run(
            ["git", "-C", str(LAMB), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip(),
        "git_branch": subprocess.run(
            ["git", "-C", str(LAMB), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True).stdout.strip(),
        "databases": {}, "trees": {},
    }

    for key, rel in DATABASES.items():
        src = LAMB / rel
        if not src.exists():
            manifest["databases"][key] = {"present": False, "path": rel}
            print(f"  - {key}: absent ({rel})")
            continue
        info = _snapshot_db(src, dest / "db" / f"{key}.db")
        info["path"] = rel
        verdict = _integrity(dest / "db" / f"{key}.db")
        info["integrity"] = verdict
        manifest["databases"][key] = info
        if verdict != "ok":
            raise SystemExit(
                f"refusing to save: {key} is not intact ({verdict}).\n"
                f"A checkpoint of a damaged database is worse than none — it looks\n"
                f"like a safety net and is not one.")
        print(f"  ✓ {key}: {info['bytes']:,} bytes, integrity ok")
        if key == "lamb":
            con = sqlite3.connect(dest / "db" / "lamb.db")
            try:
                manifest["schema_version"] = con.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM LAMB_schema_version").fetchone()[0]
            except sqlite3.Error:
                manifest["schema_version"] = None
            finally:
                con.close()

    for key, rel in TREES.items():
        src = LAMB / rel
        if not src.exists():
            manifest["trees"][key] = {"present": False, "path": rel}
            print(f"  - {key}: absent ({rel})")
            continue
        shutil.copytree(src, dest / "trees" / key, dirs_exist_ok=True)
        files = sum(1 for _ in (dest / "trees" / key).rglob("*") if _.is_file())
        size = sum(f.stat().st_size for f in (dest / "trees" / key).rglob("*") if f.is_file())
        manifest["trees"][key] = {"present": True, "path": rel, "files": files, "bytes": size}
        print(f"  ✓ {key}: {files} files, {size:,} bytes")

    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2))
    total = sum(d.get("bytes", 0) for d in manifest["databases"].values()) + \
        sum(t.get("bytes", 0) for t in manifest["trees"].values())
    print(f"\nsaved '{name}' — schema v{manifest.get('schema_version')}, "
          f"{total/1e6:.1f} MB, from {manifest['git_branch']}@{manifest['git_commit']}")
    return dest


def restore(name: str, force: bool = False) -> None:
    src = CHECKPOINTS / name
    if not src.exists():
        raise SystemExit(f"no checkpoint '{name}' — run: bundle.py save {name}")
    manifest = json.loads((src / "manifest.json").read_text())

    running = _stack_running()
    if running and not force:
        raise SystemExit(
            "refusing to restore while the stack is running — files would be replaced\n"
            "underneath open handles and the result would be inconsistent.\n"
            f"running: {', '.join(running)}\n"
            f"stop them first (docker stop {' '.join(running)}), or pass --force")

    for key, info in manifest["databases"].items():
        if not info.get("present"):
            continue
        target = LAMB / info["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        # Remove the write-ahead siblings: a stale -wal against a restored
        # database is how a "successful" restore silently serves old rows.
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(target) + suffix)
            if p.exists():
                p.unlink()
        shutil.copy2(src / "db" / f"{key}.db", target)
        print(f"  ✓ {key} -> {info['path']}")

    for key, info in manifest["trees"].items():
        if not info.get("present"):
            continue
        target = LAMB / info["path"]
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src / "trees" / key, target)
        print(f"  ✓ {key} -> {info['path']} ({info['files']} files)")

    print("\nchecking the restored databases:")
    damaged = []
    for key, info in manifest["databases"].items():
        if not info.get("present"):
            continue
        verdict = _integrity(LAMB / info["path"])
        print(f"  {'✓' if verdict == 'ok' else '✗'} {key}: {verdict[:60]}")
        if verdict != "ok":
            damaged.append(key)
    if damaged:
        raise SystemExit(f"restore produced damaged databases: {', '.join(damaged)}")

    print(f"\nrestored '{name}' — schema v{manifest.get('schema_version')}, "
          f"captured from {manifest['git_branch']}@{manifest['git_commit']}")
    print("start the stack again, then wait for it to be healthy before testing.")
    print("SQLite rebuilds its -wal/-shm on first open; writes issued during that")
    print("window can fail with 'disk I/O error' while reads already succeed —")
    print("check a write, not just a read, before trusting a restored instance.")


def verify(name: str) -> None:
    src = CHECKPOINTS / name
    manifest = json.loads((src / "manifest.json").read_text())
    bad = 0
    for key, info in manifest["databases"].items():
        if not info.get("present"):
            continue
        actual = _sha(src / "db" / f"{key}.db")
        ok = actual == info["sha256_16"]
        bad += not ok
        print(f"  {'✓' if ok else '✗'} {key}: {actual}")
    print("bundle intact" if not bad else f"{bad} database(s) differ from the manifest")


def list_checkpoints() -> None:
    if not CHECKPOINTS.exists():
        print("no checkpoints yet")
        return
    for d in sorted(CHECKPOINTS.iterdir()):
        mf = d / "manifest.json"
        if not mf.is_dir() and mf.exists():
            m = json.loads(mf.read_text())
            dbs = sum(1 for v in m["databases"].values() if v.get("present"))
            print(f"  {m['name']}: schema v{m.get('schema_version')}, {dbs} databases, "
                  f"{m['git_branch']}@{m['git_commit']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["save", "restore", "list", "verify"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--force", action="store_true",
                    help="restore even while the stack is running (inconsistent)")
    a = ap.parse_args()
    if a.action == "list":
        list_checkpoints()
    elif not a.name:
        raise SystemExit("a checkpoint name is required")
    elif a.action == "save":
        save(a.name, a.force)
    elif a.action == "verify":
        verify(a.name)
    else:
        restore(a.name, a.force)
