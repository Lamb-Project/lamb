# Quick Reference: Bulk Update Embeddings API Key

## One-Line Command

Update all collections for owner `1` with a new API key:

```bash
curl -s -X PUT 'http://localhost:9090/collections/owner/1/embeddings' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -H 'Content-Type: application/json' \
  -d '{"embeddings_model": {"model": "text-embedding-3-small", "vendor": "openai", "apikey": "sk-test-direct-update"}}' | jq
```

**Note:** The `model` and `vendor` fields are required by the API schema, but only the `apikey` will be updated. The model and vendor values must match the existing values in your collections.

## Verify with SQLite

```bash
# Before
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/lamb-kb-server.db \
  "SELECT id,name,json_extract(embeddings_model,'$.apikey') AS apikey 
   FROM collections WHERE owner='1' ORDER BY id;"

# After
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/lamb-kb-server.db \
  "SELECT id,name,json_extract(embeddings_model,'$.apikey') AS apikey 
   FROM collections WHERE owner='1' ORDER BY id;"
```

## List Collections First

```bash
curl -s -X GET 'http://localhost:9090/collections?owner=1&skip=0&limit=10' \
  -H 'Authorization: Bearer 0p3n-w3bu!' | jq
```

## Expected Response

```json
{
  "total": 4,
  "updated": 4,
  "failed": 0,
  "collections": [
    {"id": 1, "name": "convocatoria_ikasiker"},
    {"id": 3, "name": "test_main"},
    {"id": 4, "name": "youtubeassistant"},
    {"id": 5, "name": "ikasiker_test"}
  ]
}
```

## Test Script

```bash
cd /opt/lamb/lamb-kb-server-stable/backend
python test_bulk_update_embeddings.py
```

## Notes

- **Only updates the API key** - model, vendor, and endpoint remain unchanged
- **Affects ALL collections** for the specified owner
- **Atomic operation** - all updates happen in a single transaction
- **No re-embedding needed** - existing documents remain valid
