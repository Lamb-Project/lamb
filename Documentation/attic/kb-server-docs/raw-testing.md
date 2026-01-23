# Raw CLI Testing Example: File Ingestion and Association

This document shows how to use raw CLI commands to inspect the association between a user-uploaded file (`ikasiker.pdf`) and its internal hash-named storage in the Lamb KB Server, using SQLite and the CLI.

## 1. List Tables in the Database

```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/lamb-kb-server.db ".tables"
```
**Result:**
```
collections    file_registry
```

---

## 2. Find All Entries for `ikasiker.pdf` in `file_registry`

```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/lamb-kb-server.db "SELECT * FROM file_registry WHERE original_filename LIKE '%ikasiker%';"
```
**Result (truncated):**
```
1|1|ikasiker.pdf|/opt/lamb/lamb-kb-server-stable/backend/static/1/convocatoria_ikasiker/a4b140223a3b4a399eca83f023e538a0.pdf|http://localhost:9090/static/1/convocatoria_ikasiker/a4b140223a3b4a399eca83f023e538a0.pdf|336782|application/pdf|markitdown_ingest|{...}|DELETED|94|2025-09-22 08:37:05.578969|2025-09-22 15:59:40.270709|1
2|1|ikasiker.pdf|/opt/lamb/lamb-kb-server-stable/backend/static/1/convocatoria_ikasiker/f44edfae99574815b07ed09b03dc954b.pdf|http://localhost:9090/static/1/convocatoria_ikasiker/f44edfae99574815b07ed09b03dc954b.pdf|336782|application/pdf|markitdown_ingest|{...}|DELETED|94|2025-09-22 08:49:52.813922|2025-09-22 16:01:05.575182|1
... (other entries)
```

---

## 3. Find the Entry for a Specific Hash-Named File

```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/lamb-kb-server.db "SELECT * FROM file_registry WHERE file_path LIKE '%a4b140223a3b4a399eca83f023e538a0.pdf%';"
```
**Result:**
```
1|1|ikasiker.pdf|/opt/lamb/lamb-kb-server-stable/backend/static/1/convocatoria_ikasiker/a4b140223a3b4a399eca83f023e538a0.pdf|http://localhost:9090/static/1/convocatoria_ikasiker/a4b140223a3b4a399eca83f023e538a0.pdf|336782|application/pdf|markitdown_ingest|{...}|DELETED|94|2025-09-22 08:37:05.578969|2025-09-22 15:59:40.270709|1
```

---

## 4. Explanation
- The `file_registry` table links the user-uploaded filename (`original_filename`) to the internal storage path (`file_path`), which is a hash-named PDF file.
- The status column shows if the file is active or deleted.
- You can use these commands to verify ingestion and storage for any file.

---

## 5. Additional: List Recent Files

```sh
ls -lt /opt/lamb/lamb-kb-server-stable/backend/static/1/convocatoria_ikasiker/
```

---

## 6. Additional: Check Collection Info for the File

```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/lamb-kb-server.db "SELECT * FROM collections WHERE id IN (SELECT collection_id FROM file_registry WHERE original_filename LIKE '%ikasiker%');"
```

---

## Notes
- Replace file names and paths as needed for other test cases.
- Use `jq` with curl for API-based checks.

---

## 7. API / curl checks (succinct)

Replace the bearer token and IDs as needed. These use the local KB server at port 9090.

List files in a collection (all statuses):

```sh
curl -s -H 'Authorization: Bearer 0p3n-w3bu!' \
	'http://localhost:9090/collections/1/files' | jq
```

List files in a collection excluding deleted entries:

```sh
curl -s -H 'Authorization: Bearer 0p3n-w3bu!' \
	'http://localhost:9090/collections/1/files' | jq 'map(select(.status != "deleted"))'
```

Get collection metadata:

```sh
curl -s -H 'Authorization: Bearer 0p3n-w3bu!' \
	'http://localhost:9090/collections/1' | jq
```

Mark a file's status (example: mark file id 3 as deleted):

```sh
curl -X PUT -s -H 'Authorization: Bearer 0p3n-w3bu!' \
	'http://localhost:9090/collections/files/3/status?status=deleted' -w '\nHTTP_STATUS:%{http_code}\n'
```

Small example output (files list, truncated):

```json
[
	{"id":1,"original_filename":"ikasiker.pdf","file_path":".../a4b1402...pdf","status":"DELETED", ...},
	{"id":2,"original_filename":"ikasiker.pdf","file_path":".../f44edf...pdf","status":"DELETED", ...}
]
```

Use these commands to verify the same associations you inspected with sqlite3.

==== 

Embeddings and segments are stored in a separate SQLite database used by ChromaDB.

1. Confirm the collection and chroma UUID in the KB SQLite:

```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/lamb-kb-server.db \
  "SELECT id,name,chromadb_uuid,embeddings_model FROM collections WHERE id=1;"
```

2. Show Chroma collections (to verify UUID exists in chroma):

```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/chromadb/chroma.sqlite3 \
  "SELECT * FROM collection_metadata;"
```

3. List Chroma segments and find those tied to the collection UUID:
```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/chromadb/chroma.sqlite3 \
  "SELECT * FROM segments;"
# visually locate the row(s) where the last column equals the collection UUID (38a183d6-...)
```

4. Show embeddings that belong to the metadata segment (replace segment id if different):
```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/chromadb/chroma.sqlite3 \
  "SELECT * FROM embeddings WHERE segment_id='8b0612b6-01e3-4d8d-a20a-7bb040961600' LIMIT 50;"
```


* Output columns: id | segment_id | embedding_id | seq_id | created_at
* embedding_id is the identifier used in embedding_metadata.


5. Inspect embedding metadata for a specific embedding id (example uses the first embedding_id you saw: c59da807ab9b4f19807b8943196dd2b3):

```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/chromadb/chroma.sqlite3 \
  "SELECT * FROM embedding_metadata WHERE embedding_id='c59da807ab9b4f19807b8943196dd2b3';"
```

Or search metadata values containing "ikasiker" or the hash:

```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/chromadb/chroma.sqlite3 \
  "SELECT * FROM embedding_metadata WHERE str_value LIKE '%ikasiker%' OR str_value LIKE '%a4b140223a3b4a399eca83f023e538a0%';"
```

6. Inspect embedding_metadata keys useful for mapping:

```sh
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/chromadb/chroma.sqlite3 \
  "SELECT * FROM embedding_metadata WHERE key IN ('document_id','file_url','file_size','chunk_count','embedding_model','embedding_vendor') LIMIT 200;"
```

# Interpretation / mapping chain (simple)

`file_registry` row links `original_filename=ikasiker.pdf` → `file_path` and `file_url` (hash-named PDF, and a generated HTML representation URL).
Chroma's `embedding_metadata` stores `file_url` and `chroma:document` for each document/chunk.
`embeddings` table stores the per-chunk rows that tie `embedding_id` → `seq_id` (chunk index) and `segment_id`.
The collection UUID (in KB DB) → Chroma collection → Chroma segments → embeddings → embedding_metadata (`file_url`/`document_id`) gives you the full connection back to ikasiker.pdf.