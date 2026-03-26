# Bulk Update Embeddings API Key

## Overview

This feature allows you to update the embeddings API key for **all collections** belonging to an owner (organization) in a single API call. This is particularly useful when:

- Switching to a new API key for an entire organization
- Rotating API keys across multiple knowledge bases
- Migrating from test to production API keys
- Updating expired API keys across all collections at once

## Endpoint

```
PUT /collections/owner/{owner}/embeddings
```

### Path Parameters

- `owner` (string, required): The owner identifier (e.g., organization ID or user ID)

### Request Body

```json
{
  "embeddings_model": {
    "apikey": "your-new-api-key-here"
  }
}
```

### Response

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

### Response Fields

- `total` (integer): Total number of collections for the owner
- `updated` (integer): Number of collections successfully updated
- `failed` (integer): Number of collections that failed to update
- `collections` (array): List of updated collections with their IDs and names
- `error` (string, optional): Error message if the operation failed

## Usage Examples

### Using curl

```bash
# Update embeddings API key for all collections of owner "1"
curl -X PUT 'http://localhost:9090/collections/owner/1/embeddings' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -H 'Content-Type: application/json' \
  -d '{
    "embeddings_model": {
      "apikey": "sk-test-direct-update"
    }
  }'
```

### Using Python

```python
import requests

url = "http://localhost:9090/collections/owner/1/embeddings"
headers = {
    "Authorization": "Bearer 0p3n-w3bu!",
    "Content-Type": "application/json"
}
payload = {
    "embeddings_model": {
        "apikey": "sk-test-direct-update"
    }
}

response = requests.put(url, headers=headers, json=payload)
result = response.json()

print(f"Updated {result['updated']}/{result['total']} collections")
for coll in result['collections']:
    print(f"  - {coll['name']} (ID: {coll['id']})")
```

### Using JavaScript/Node.js

```javascript
const axios = require('axios');

const url = 'http://localhost:9090/collections/owner/1/embeddings';
const headers = {
  'Authorization': 'Bearer 0p3n-w3bu!',
  'Content-Type': 'application/json'
};
const payload = {
  embeddings_model: {
    apikey: 'sk-test-direct-update'
  }
};

axios.put(url, payload, { headers })
  .then(response => {
    const result = response.data;
    console.log(`Updated ${result.updated}/${result.total} collections`);
    result.collections.forEach(coll => {
      console.log(`  - ${coll.name} (ID: ${coll.id})`);
    });
  })
  .catch(error => {
    console.error('Error:', error.response?.data || error.message);
  });
```

## Complete Workflow Example

### 1. List collections before update

```bash
curl -s -X GET 'http://localhost:9090/collections?owner=1&skip=0&limit=10' \
  -H 'Authorization: Bearer 0p3n-w3bu!'
```

Expected response (API key status is hidden):
```json
{
  "total": 4,
  "items": [
    {
      "id": 1,
      "name": "convocatoria_ikasiker",
      "owner": "1",
      "embeddings_model": {
        "model": "text-embedding-3-small",
        "vendor": "openai",
        "apikey_configured": true
      }
    },
    ...
  ]
}
```

### 2. Verify current API keys in SQLite (optional)

```bash
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/lamb-kb-server.db \
  "SELECT id,name,json_extract(embeddings_model,'$.apikey') AS apikey 
   FROM collections 
   WHERE owner='1' 
   ORDER BY id;"
```

Output:
```
1|convocatoria_ikasiker|sk-test-bulk-999
3|test_main|sk-test-bulk-999
4|youtubeassistant|sk-test-bulk-999
5|ikasiker_test|sk-test-bulk-999
```

### 3. Perform bulk update

```bash
curl -s -X PUT 'http://localhost:9090/collections/owner/1/embeddings' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -H 'Content-Type: application/json' \
  -d '{
    "embeddings_model": {
      "apikey": "sk-test-direct-update"
    }
  }'
```

Expected response:
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

### 4. Verify the update in SQLite

```bash
sqlite3 /opt/lamb/lamb-kb-server-stable/backend/data/lamb-kb-server.db \
  "SELECT id,name,json_extract(embeddings_model,'$.apikey') AS apikey 
   FROM collections 
   WHERE owner='1' 
   ORDER BY id;"
```

Output (updated):
```
1|convocatoria_ikasiker|sk-test-direct-update
3|test_main|sk-test-direct-update
4|youtubeassistant|sk-test-direct-update
5|ikasiker_test|sk-test-direct-update
```

## Important Notes

### What Gets Updated

- **Only the API key** (`apikey` field) in the `embeddings_model` configuration
- Other fields remain **unchanged**:
  - `model` (e.g., "text-embedding-3-small")
  - `vendor` (e.g., "openai", "ollama")
  - `api_endpoint` (custom endpoint URL)

### What Does NOT Change

- The ChromaDB collection structure
- The embeddings function used for future queries
- Existing documents in the collections
- Collection metadata (name, description, visibility)

### When to Use This Endpoint

✅ **Use cases:**
- Rotating API keys for security
- Switching from test to production API keys
- Updating expired API keys
- Migrating to a new API provider (with same model/vendor)

⚠️ **Not for:**
- Changing the embedding model (use individual collection updates)
- Changing the vendor/provider (requires re-embedding)
- Changing the API endpoint (use individual collection updates)

### Authentication

All requests must include the valid API key in the Authorization header:

```
Authorization: Bearer 0p3n-w3bu!
```

The API key is configured via the `LAMB_API_KEY` environment variable (default: `0p3n-w3bu!`).

## Error Handling

### 400 Bad Request

```json
{
  "detail": "API key is required in embeddings_model"
}
```

Occurs when the request body is missing the `apikey` field.

### 401 Unauthorized

```json
{
  "detail": "Invalid or missing authentication token"
}
```

Occurs when the Authorization header is missing or contains an invalid token.

### 500 Server Error

```json
{
  "detail": "An error occurred during the bulk update",
  "error": "database error message"
}
```

Occurs when there's a database error during the update operation.

## Implementation Details

### Database Schema

The `collections` table stores the `embeddings_model` configuration as a JSON column:

```sql
CREATE TABLE collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    embeddings_model JSON NOT NULL,
    ...
);
```

Example `embeddings_model` JSON structure:
```json
{
  "model": "text-embedding-3-small",
  "vendor": "openai",
  "api_endpoint": "https://api.openai.com/v1/embeddings",
  "apikey": "sk-..."
}
```

### Service Method

The endpoint uses the `CollectionService.bulk_update_embeddings_apikey()` method which:

1. Queries all collections for the specified owner
2. Iterates through each collection
3. Updates the `apikey` field in the `embeddings_model` JSON
4. Commits all changes in a single transaction
5. Returns a summary of the operation

### Performance Considerations

- **Atomic operation**: All updates are committed in a single database transaction
- **Rollback on error**: If the commit fails, all changes are rolled back
- **No ChromaDB modification**: This endpoint only updates the SQLite metadata
- **No re-embedding required**: Existing documents remain valid

## Testing

A test script is provided at `/opt/lamb/lamb-kb-server-stable/backend/test_bulk_update_embeddings.py`.

To run the test:

```bash
# Start the server
cd /opt/lamb/lamb-kb-server-stable/backend
python start.py

# In another terminal, run the test
python test_bulk_update_embeddings.py
```

The test script will:
1. List all collections for the owner before the update
2. Perform the bulk update
3. List all collections after the update
4. Display the results

## Related Endpoints

- `GET /collections` - List all collections with optional owner filtering
- `GET /collections/{id}` - Get a specific collection
- `PUT /collections/{id}` - Update a single collection (can also update API key)
- `POST /collections` - Create a new collection

## Support

For issues or questions related to this endpoint, please refer to:

- LAMB Architecture Documentation: `/opt/lamb/Documentation/lamb_architecture_nano.md`
- KB Server API Documentation: `/opt/lamb/lamb-kb-server-stable/lamb-kb-server-api.md`
