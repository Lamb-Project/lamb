# Knowledge Base Creation Error Message Fix

## Issue Description

When creating a new Knowledge Base through the UI, users would see an error message even though the KB was successfully created. This confusing UX occurred when:

1. The KB creation API call succeeded
2. The creation modal closed
3. The list refresh triggered
4. The list refresh failed (e.g., due to temporary network issues or KB server being briefly offline)

## Root Cause

The issue was in the `handleKnowledgeBaseCreated` function in `KnowledgeBasesList.svelte`:

```javascript
function handleKnowledgeBaseCreated(event) {
    const { id, name, message } = event.detail;
    
    // Show success message
    successMessage = message || '...';
    
    // Refresh the list - NOT AWAITED!
    loadKnowledgeBases();  // ❌ If this fails, error is shown
}
```

The problem was that `loadKnowledgeBases()` is an async function that was called but **not awaited**. If the async refresh failed, the error state would be set and displayed to the user, even though the KB creation itself was successful.

## Solution

Made the handler async and added proper error handling:

```javascript
async function handleKnowledgeBaseCreated(event) {
    const { id, name, message } = event.detail;
    
    // Show success message
    successMessage = message || '...';
    
    // Refresh the list - catch errors to avoid showing error after successful creation
    try {
        await loadKnowledgeBases();  // ✅ Now awaited
    } catch (err) {
        // KB was created successfully, just log refresh error without showing to user
        console.warn('KB created successfully but list refresh failed:', err);
        // Keep the success message visible
    }
}
```

## Impact

### Before Fix
- User creates KB → sees error message → confused about whether KB was created
- User has to refresh the page to see the newly created KB

### After Fix  
- User creates KB → sees only success message
- If list refresh fails silently, error is logged to console
- User experience is clearer and less confusing

## Testing

To test the fix:
1. Create a new KB
2. Temporarily stop the KB server or introduce a network delay
3. Verify that the success message is shown
4. Check the console for any refresh errors (should be logged as warnings)
5. The new KB should appear in the list when it successfully refreshes

## Files Changed

- `frontend/svelte-app/src/lib/components/KnowledgeBasesList.svelte`
  - Modified `handleKnowledgeBaseCreated` function (lines 285-307)
  - Made function async
  - Added try-catch block around `loadKnowledgeBases()` call
  - Errors during list refresh are now logged instead of displayed to user

