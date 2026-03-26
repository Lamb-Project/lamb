# Debug and Maintenance Tools

This directory contains standalone utility scripts for debugging and maintaining the lamb-kb-server databases.

**These are NOT automated tests** - they are meant to be run manually when diagnosing issues.

## Available Tools

| Tool | Purpose |
|------|---------|
| `check_chromadb.py` | Inspect ChromaDB collections directly |
| `check_collections.py` | Compare SQLite and ChromaDB collections |
| `check_collections_v2.py` | Updated version of collection comparison |
| `debug_collections.py` | Read-only diagnostics for collection issues |
| `debug_embedding_test.py` | Test embedding lifecycle manually |
| `fix_collections.py` | Interactive script to fix collection mapping issues |

## Usage

Run any tool from the `backend/tests/tools/` directory:

```bash
cd /path/to/lamb-kb-server-stable/backend/tests/tools
python check_chromadb.py [optional_path]
```

## Notes

- These scripts access the database directly, bypassing the API
- `fix_collections.py` is interactive and can modify data - use with caution
- All other scripts are read-only
