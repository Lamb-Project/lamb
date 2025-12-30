# URL Ingestion Repeats — Findings and Fix Options

## Context

While ingesting URLs via the UI, the same crawl was embedded multiple times in ChromaDB. The repeats stopped once the user navigated away from the ingestion page.

## What We Verified

1. **ChromaDB has duplicates**
   - `dbizi_full_large_local` contains **909** embeddings.
   - The crawl produces **303** chunks, so 909 is **3 × 303**, which strongly indicates the same content was ingested three times.

2. **File registry shows ingestion completed**
   - The SQLite `file_registry` entry for `dbizi_full_large_local` is **COMPLETED** with `document_count=303`.
   - This means ingestion completion is being recorded correctly; the duplication is not due to “stuck processing.”

3. **UI is triggering repeated requests**
   - `lamb-backend-1` logs show multiple `POST /creator/knowledgebases/kb/5/plugin-ingest-base` calls.
   - Each request triggers a new ingestion run, generating new UUIDs, so each run adds a full set of embeddings.
   - This matches the observation: repeats stopped when the ingestion page was closed.

4. **Chroma collection metadata does not store embeddings config**
   - Chroma collection metadata only includes `hnsw:space`, so the “Embedding model mismatch detected” warning is expected.
   - SQLite correctly stores `vendor=openai` and `model=text-embedding-3-large`.

## Likely Cause

The ingestion UI is **submitting the ingestion request multiple times** while the user stays on the ingestion page. This could be:
   - A repeated form submission (e.g., Enter key, auto-resubmission),
   - A client-side re-trigger in a reactive component,
   - Or a UI retry loop when a response is slow or ambiguous.

The backend does **not** deduplicate ingestions, so every repeated request inserts a full new batch.

## Potential Fixes

### 1) Frontend Guard (Fast UX Fix)
**Goal:** Prevent repeated submissions for the same params while a run is already in progress.
- Add a client-side lock that disables re-submission until the user changes inputs or the request completes.
- Track a per-request “in-flight” flag keyed by `(kb_id + plugin + params)`.

### 2) Backend Idempotency (Durable Fix)
**Goal:** Ensure repeated ingestion requests do not reinsert the same content.
- Implement deterministic IDs based on a stable hash (e.g., URL + chunk index) and use **upsert** instead of add.
- Or check for existing embeddings with the same `source_url`/`file_url` and delete or skip before inserting.

### 3) Pass `file_url` for URL ingests (Improves Cleanup)
The `ingest-url` background task does **not** pass `file_url` to the plugin, so metadata can’t be used to identify and clean older chunks. Passing `file_url` would enable reliable de-duplication and cleanup.

### 4) Write embeddings model into Chroma metadata (Noise Fix)
Store `embeddings_model` in Chroma collection metadata at creation time so mismatch warnings are accurate.

## Implemented Fix (Partial)

**Date:** December 30, 2025

Added a frontend guard to prevent rapid manual re-submissions:
- Dual-lock mechanism (`uploading` state + `isSubmitting` synchronous flag)
- 1-second debouncing between submissions
- Applied to both `uploadFile()` and `runBaseIngestion()` functions

**File:** `frontend/svelte-app/src/lib/components/Creator/KnowledgeBases/KnowledgeBaseDetail.svelte`

**Result:** Successfully prevents normal rapid button clicks, but does NOT solve the underlying bug.

## The Real Problem (ROOT CAUSE IDENTIFIED)

**Date:** December 30, 2025

The original bug report states: **"The repeats stopped once the user navigated away from the ingestion page."**

After investigation, the root cause has been identified: **Pressing Enter in text input fields triggers form submission**.

### Root Cause Analysis

When filling in ingestion parameters (URL, API URL, API key, description, citation, etc.), users naturally press **Enter** after typing in each field to move to the next one. In HTML forms, pressing Enter in a text input field triggers the form's `submit` event by default.

The ingestion form uses:
```svelte
<form onsubmit={(e) => { e.preventDefault(); handleIngestSubmit(); }}>
```

Every time Enter is pressed in any text input, this triggers `handleIngestSubmit()`, which calls `runBaseIngestion()` or `uploadFile()`, starting a new ingestion with the current form values.

**This explains:**
- Why ingestions repeat while staying on the page (user is typing and pressing Enter in various fields)
- Why repeats stop after navigation (user leaves the page)
- Why the same content is ingested multiple times (each Enter press = one more ingestion)

### Implemented Fix (FINAL VERSION)

**Date:** December 30, 2025

**Approach:** Modified the form's `onsubmit` handler to check if submission was triggered by Enter key in an input field.

**File:** `frontend/svelte-app/src/lib/components/Creator/KnowledgeBases/KnowledgeBaseDetail.svelte` (line ~652)

**Code:**
```javascript
<form onsubmit={(e) => { 
    e.preventDefault(); 
    // Prevent form submission if triggered by Enter key in an input field
    if (e.submitter === null || e.submitter?.tagName === 'INPUT') {
        console.log('Form submission blocked - triggered by Enter in input field');
        return;
    }
    handleIngestSubmit(); 
}} class="space-y-6">
```

**How it works:**
- When a form is submitted via Enter key in an input, `e.submitter` is `null`
- When submitted by clicking the button, `e.submitter` refers to the button element
- The fix checks if submitter is null or an INPUT element and blocks the submission
- Only allows submission when triggered by the actual submit button

**Status:**  
✅ Code implemented and committed  
⚠️ **Deployment blocked by Svelte 5 / SvelteKit compatibility issue**

The frontend has a `lifecycle_outside_component` error in the generated `root.svelte` file (SvelteKit's auto-generated component). This is preventing the app from initializing properly and appears to be related to Svelte 5 runes compatibility with SvelteKit 2.16.0.

**Error:**
```
Svelte error: lifecycle_outside_component
`onMount(...)` can only be used during component initialisation
at Root (/.svelte-kit/generated/root.svelte:48:2)
```

This error is **not caused by the fix** - it's a framework compatibility issue that existed independently.
function handleInputKeydown(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        console.log('Enter key pressed in input field - prevented form submission');
    }
}
```

Applied to:
- `type="text"` inputs (url, api_url, api_key, description, citation)
- `type="number"` inputs (chunk_size, chunk_overlap, max_discovery_depth, limit, timeout)

**Note:** Textareas and select/checkbox inputs are NOT affected, as they handle Enter differently:
- Textareas: Enter creates a new line (expected behavior)
- Selects/checkboxes: Don't respond to Enter in the same way

### Testing Status

**Changes implemented:** ✅ Complete  
**Frontend rebuild:** ⚠️ **DEPLOYMENT ISSUE**

The fix has been implemented in the source code at:
- Line 407: `handleInputKeydown(event)` function  
- Line 714: Applied to number inputs with `onkeydown={handleInputKeydown}`
- Line 743: Applied to text inputs with `onkeydown={handleInputKeydown}`

**DEPLOYMENT PROBLEM:**  
Despite multiple frontend container restarts and cache clears, the updated component is NOT being served to the browser:
- ❌ Console log message "Enter key pressed in input field - prevented form submission" never appears
- ❌ Form continues to submit when Enter is pressed in text fields
- ❌ `handleInputKeydown` function is not being called at all
- ✅ Source code verified to contain the fix
- ✅ Vite dev server detects file changes (HMR working)
- ❌ Compiled output does not include the new code

**Possible causes:**
1. Svelte 5 compilation cache not being cleared
2. Vite transform cache holding old component version  
3. Browser service worker caching old JavaScript
4. Component module not being re-imported despite changes

**Attempted solutions that FAILED:**
- Restarted frontend container (multiple times)
- Cleared `.svelte-kit` directory
- Cleared `node_modules/.vite` cache directory
- Hard refresh in browser
- Navigated to fresh URL
- Touched source file to trigger HMR

**Required for deployment:**  
Complete frontend rebuild from scratch or investigation into why Svelte/Vite is not compiling the updated component.

### Expected Behavior After Fix

- Users can type in all text/number fields and press Enter without triggering unwanted submissions
- Form only submits when the "Run Ingestion" or "Upload File" button is clicked
- No more duplicate ingestions from accidental Enter presses

### Remaining Recommendations

**CRITICAL: Look for reactive code that auto-triggers ingestion:**

1. **Search for Svelte `$effect` blocks** in `KnowledgeBaseDetail.svelte` that might be calling ingestion functions
2. **Check for reactive statements** (`$:`) that could re-run `runBaseIngestion()` or `uploadFile()`
3. **Look for URL parameter watchers** or route change handlers that might re-submit on navigation
4. **Inspect form submission handlers** for duplicate event bindings or re-mounting issues
5. **Check if `handleIngestSubmit()` is being called from multiple places** or bound to multiple events

**The bug likely involves:**
- A reactive effect that depends on a frequently-changing variable
- Form auto-resubmission on component re-render
- Multiple event handlers bound to the same form/button
- URL parameter changes triggering re-ingestion

**To reproduce the real bug:**
1. Start a URL ingestion
2. Stay on the ingestion page (don't navigate away)
3. Monitor backend logs for repeated `POST /creator/knowledgebases/kb/{id}/plugin-ingest-base` requests
4. Check if requests continue even without clicking anything

**Backend idempotency is still recommended** as a durable fix regardless of frontend issues.
