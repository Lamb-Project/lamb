# Fix for 404 Error When Deleting Files from Knowledge Base

## Issue Description
When attempting to delete files from a knowledge base through the frontend, users encounter a 404 error:
```
File not found in knowledge base. File ID: 1, KB ID: 1
DELETE http://localhost:8000/creator/knowledgebases/kb/1/files/1 404 (Not Found)
```

## Root Cause Analysis

### The Problem
The backend was trying to call a **DELETE endpoint that doesn't exist** in the lamb-kb-server. The backend code was attempting:
```
DELETE /collections/{kb_id}/files/{file_id}
```

However, the lamb-kb-server API only supports:
```
PUT /collections/files/{file_id}/status?status=deleted
```

### Architecture Understanding
- **Backend (port 9099)**: Handles creator authentication and business logic
- **lamb-kb-server (port 9090)**: Manages actual knowledge base operations
- **Frontend**: Calls backend API, which then communicates with lamb-kb-server

## Investigation Steps

### 1. Test Direct API Calls
First, verify what endpoints are available:

```bash
# Check files in knowledge base
curl -X GET 'http://localhost:9090/collections/1/files' \
  -H 'Authorization: Bearer BEARER' | jq

# Test DELETE endpoint (this will fail with 404)
curl -X DELETE 'http://localhost:9090/collections/1/files/1' \
  -H 'Authorization: Bearer BEARER'

# Test status update endpoint (this works)
curl -X PUT 'http://localhost:9090/collections/files/1/status?status=deleted' \
  -H 'Authorization: Bearer BEARER'
```

### 2. Review API Documentation
Check `/opt/lamb/lamb-kb-server-stable/lamb-kb-server-api.md` to confirm available endpoints:
- ✅ `PUT /collections/files/{file_id}/status` - Update file status
- ❌ `DELETE /collections/{kb_id}/files/{file_id}` - Does not exist

## Solution Implementation

### Step 1: Update Backend File Deletion Logic

Edit `/opt/lamb/backend/creator_interface/kb_server_manager.py` in the `delete_file_from_kb` method:

**Replace this code block:**
```python
# Now delete the file from KB server
delete_url = f"{self.kb_server_url}/collections/{kb_id}/files/{file_id}"
logger.info(f"Deleting file from KB server at: {delete_url}")

delete_response = await client.delete(delete_url, headers=headers)
logger.info(f"KB server delete file response status: {delete_response.status_code}")

if delete_response.status_code == 200 or delete_response.status_code == 204:
    # Successfully deleted file
    logger.info(f"Successfully deleted file {file_id} from knowledge base {kb_id}")
    
    return {
        "message": "File deleted successfully",
        "knowledge_base_id": kb_id,
        "file_id": file_id
    }
elif delete_response.status_code == 404:
    logger.error(f"File {file_id} not found in knowledge base {kb_id}")
    raise HTTPException(
        status_code=404,
        detail=f"File not found in knowledge base"
    )
else:
    # Handle other errors
    logger.error(f"KB server returned error status during file deletion: {delete_response.status_code}")
    error_detail = "Unknown error"
    try:
        error_data = delete_response.json()
        error_detail = error_data.get('detail', str(error_data))
    except Exception:
        error_detail = delete_response.text or "Unknown error"
    
    raise HTTPException(
        status_code=delete_response.status_code,
        detail=f"KB server file deletion error: {error_detail}"
    )
```

**With this corrected code:**
```python
# Now mark the file as deleted in KB server using the correct endpoint
status_url = f"{self.kb_server_url}/collections/files/{file_id}/status?status=deleted"
logger.info(f"Marking file as deleted in KB server at: {status_url}")

status_response = await client.put(status_url, headers=headers)
logger.info(f"KB server status update response status: {status_response.status_code}")

if status_response.status_code == 200:
    # Successfully marked file as deleted
    logger.info(f"Successfully marked file {file_id} as deleted in knowledge base {kb_id}")
    
    return {
        "message": "File deleted successfully",
        "knowledge_base_id": kb_id,
        "file_id": file_id
    }
elif status_response.status_code == 404:
    logger.error(f"File {file_id} not found in knowledge base {kb_id}")
    raise HTTPException(
        status_code=404,
        detail=f"File not found in knowledge base"
    )
else:
    # Handle other errors
    logger.error(f"KB server returned error status during file deletion: {status_response.status_code}")
    error_detail = "Unknown error"
    try:
        error_data = status_response.json()
        error_detail = error_data.get('detail', str(error_data))
    except Exception:
        error_detail = status_response.text or "Unknown error"
    
    raise HTTPException(
        status_code=status_response.status_code,
        detail=f"KB server file deletion error: {error_detail}"
    )
```

### Step 2: Filter Out Deleted Files from Frontend

In the same file, in the `get_knowledge_base_details` method, add filtering logic:

**Find this loop:**
```python
for file in files_data:
    # Improved mapping with fallbacks for different field names
```

**Replace with:**
```python
for file in files_data:
    # Skip files that are marked as deleted
    if file.get('status') == 'deleted':
        logger.info(f"Skipping deleted file: {file.get('original_filename')} (ID: {file.get('id')})")
        continue
        
    # Improved mapping with fallbacks for different field names
```

### Step 3: Enhanced Error Messages (Optional)

Edit `/opt/lamb/frontend/svelte-app/src/lib/services/knowledgeBaseService.js` for better debugging:

**Find:**
```javascript
} else if (error.response?.status === 404) {
    errorMessage = 'File not found in knowledge base.';
```

**Replace with:**
```javascript
} else if (error.response?.status === 404) {
    errorMessage = `File not found in knowledge base. File ID: ${fileId}, KB ID: ${kbId}`;
```

### Step 4: Restart Services

```bash
cd /opt/lamb
docker-compose restart backend
```

## Verification Steps

### 1. Test File Status Update Directly
```bash
# Mark a file as deleted
curl -X PUT 'http://localhost:9090/collections/files/1/status?status=deleted' \
  -H 'Authorization: Bearer 0p3n-w3bu!'

# Verify only non-deleted files are returned
curl -X GET 'http://localhost:9090/collections/1/files' \
  -H 'Authorization: Bearer 0p3n-w3bu!' | jq 'map(select(.status != "deleted"))'
```

### 2. Test Through Frontend
1. Open the knowledge base detail page
2. Try to delete a file
3. File should disappear from the UI without 404 error
4. Check backend logs for confirmation

## Key Implementation Details

### Why This Approach Works
1. **Uses Correct API**: Calls the actual endpoint that exists in lamb-kb-server
2. **Soft Delete**: Files are marked as "deleted" rather than physically removed
3. **Data Integrity**: Preserves file data and metadata for potential recovery
4. **UI Consistency**: Deleted files are filtered out from frontend display

### Important Notes
- Files are **soft deleted** (status changed to "deleted"), not physically removed
- The approach maintains referential integrity in the database
- Backend filtering ensures deleted files don't appear in API responses
- Frontend doesn't need changes beyond error message improvements

## Testing Commands

```bash
# Check file statuses
curl -X GET 'http://localhost:9090/collections/1/files' \
  -H 'Authorization: Bearer BEARER' | jq '.[].status'

# Count non-deleted files
curl -X GET 'http://localhost:9090/collections/1/files' \
  -H 'Authorization: Bearer BEARER' | jq 'map(select(.status != "deleted")) | length'

# Delete a file (change ID as needed)
curl -X PUT 'http://localhost:9090/collections/files/2/status?status=deleted' \
  -H 'Authorization: Bearer BEARER'
```

## Files Modified
1. `/opt/lamb/backend/creator_interface/kb_server_manager.py` - Main fix for deletion logic
2. `/opt/lamb/frontend/svelte-app/src/lib/services/knowledgeBaseService.js` - Error messages
3. `/opt/lamb/frontend/svelte-app/src/lib/components/KnowledgeBaseDetail.svelte` - Debug logging
4. `/opt/lamb/lamb-kb-server-stable/backend/start.py` - Hot-reload exclusions fix

## Additional Fix: Hot-Reload Issue

### Problem
After implementing the file deletion fix, users reported getting "Knowledge base server offline" errors even though deletion worked correctly. The issue was that the lamb-kb-server was hot-reloading when it detected changes in the static files directory.

### Root Cause
The `start.py` file in lamb-kb-server had `reload=True` without any exclusions, causing the server to restart whenever files in the static directory were modified (even when just updating file status).

### Solution
Updated `/opt/lamb/lamb-kb-server-stable/backend/start.py` to exclude static and data directories from hot-reload monitoring:

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=9090, 
        reload=True,
        reload_excludes=["static/*", "static/**/*", "data/*", "data/**/*"]
    )
```

### Verification
```bash
# Test file deletion - should work without "server offline" error
curl -X PUT 'http://localhost:9090/collections/files/3/status?status=deleted' \
  -H 'Authorization: Bearer 0p3n-w3bu!'

# Check for restart messages (should be empty)
cd /opt/lamb/lamb-kb-server-stable && docker-compose logs backend --tail=50 | grep -i "restart\|reload"
```

## Result
✅ File deletion now works without 404 errors  
✅ Deleted files are hidden from the UI  
✅ Data integrity is maintained  
✅ Backend logs show successful operations