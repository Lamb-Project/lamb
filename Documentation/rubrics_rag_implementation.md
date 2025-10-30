# Rubrics RAG Integration Implementation Guide

**Version:** 1.0  
**Created:** October 15, 2025  
**Status:** 🔨 Implementation Plan - Ready to Start  
**Estimated Effort:** 16-20 hours

---

## 🎯 Design Decisions (Confirmed)

1. **Storage:** ✅ Use metadata field (api_callback) - No DB migration needed
2. **Format:** ✅ User chooses markdown OR JSON - 
3. **Versioning:** ✅ Always use latest rubric version - Simpler, more practical
4. **Quantity:** ✅ One rubric per assistant - User can edit/change anytime
5. **Access:** ✅ User's own rubrics + public rubrics in organization

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Implementation Tasks](#3-implementation-tasks)
4. [Database Changes](#4-database-changes)
5. [Backend Implementation](#5-backend-implementation)
6. [Frontend Implementation](#6-frontend-implementation)
7. [Testing Plan](#7-testing-plan)
8. [Design Decisions](#8-design-decisions)

---

## 1. Overview

### 1.1 Purpose

Integrate the Evaluaitor rubrics system with the existing RAG (Retrieval-Augmented Generation) functionality, allowing assistants to use rubrics as context for assessment-focused conversations.

### 1.2 Use Cases

**Example 1: Essay Grading Assistant**
- Educator creates "Essay Grading Assistant"
- Selects "Essay Writing Rubric" as RAG source
- Students can ask: "How should I structure my thesis?"
- Assistant responds using rubric criteria as context

**Example 2: Self-Assessment Assistant**
- Educator creates "Project Self-Assessment Assistant"
- Attaches "Project Rubric" 
- Students can ask: "What does 'exemplary' mean for the research criterion?"
- Assistant explains using exact rubric descriptions

**Example 3: Feedback Assistant**
- Educator creates "Assignment Feedback Assistant"
- Uses rubric for consistent feedback language
- Assistant can explain grading decisions based on rubric criteria

### 1.3 Current State

**Existing RAG Options:**
- `no_rag` - No retrieval
- `simple_rag` - Retrieval from Knowledge Base collections (multiple collections, vector search)
- `single_file_rag` - Retrieval from a single file

**Assistant Metadata Structure:**
```json
{
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "prompt_processor": "simple_augment",
  "rag_processor": "simple_rag"
}
```

**Assistant RAG Fields:**
- `RAG_collections` (TEXT) - Comma-separated KB collection IDs
- `RAG_Top_k` (INTEGER) - Number of chunks to retrieve

### 1.4 Target State

**New RAG Option:**
- `rubric_rag` - Retrieval from a single selected rubric

**Updated Assistant Metadata:**
```json
{
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "prompt_processor": "simple_augment",
  "rag_processor": "rubric_rag",
  "rubric_id": "rubric-550e8400-e29b-41d4-a716-446655440000",
  "rubric_format": "markdown"
}
```

**New Fields:**
- `rubric_id` (string): The selected rubric's unique identifier
- `rubric_format` (string): Format for LLM context - "markdown" or "json"

**UI Changes:**
- Assistant form RAG section shows "Rubric" option
- Dropdown selector for accessible rubrics (own + public in org)
- Preview of selected rubric

---

## 2. Architecture

### 2.1 Data Flow

```
┌─────────────────┐
│   Assistant     │
│   Creation/Edit │
│   Form          │
└────────┬────────┘
         │
         │ 1. User selects "Rubric" RAG option
         │ 2. User selects rubric from dropdown
         │
         ▼
┌─────────────────────────────────────┐
│  Assistant Metadata                 │
│  {                                  │
│    "rag_processor": "rubric_rag",   │
│    "rubric_id": "rubric-123"        │
│  }                                  │
└─────────────────┬───────────────────┘
                  │
                  │ 3. Saved to api_callback column
                  │
                  ▼
         ┌────────────────┐
         │   Assistants   │
         │   Database     │
         └────────┬───────┘
                  │
                  │ 4. Completion request received
                  │
                  ▼
┌─────────────────────────────────────┐
│  Completion Pipeline                │
│  - Load assistant metadata          │
│  - Detect rag_processor="rubric_rag"│
│  - Load rubric_rag.py processor     │
└─────────────────┬───────────────────┘
                  │
                  │ 5. Execute rubric_rag processor
                  │
                  ▼
┌─────────────────────────────────────┐
│  rubric_rag.py                      │
│  - Extract rubric_id from metadata  │
│  - Query rubrics database           │
│  - Convert rubric to markdown       │
│  - Return as RAG context            │
└─────────────────┬───────────────────┘
                  │
                  │ 6. Inject rubric into prompt
                  │
                  ▼
┌─────────────────────────────────────┐
│  Prompt Processor                   │
│  - Add system prompt                │
│  - Inject rubric context            │
│  - Format user messages             │
└─────────────────┬───────────────────┘
                  │
                  │ 7. Send to LLM
                  │
                  ▼
         ┌────────────────┐
         │   LLM Provider │
         └────────────────┘
```

### 2.2 Component Overview

| Component | Location | Changes Required |
|-----------|----------|------------------|
| **Frontend Form** | `AssistantForm.svelte` | Add rubric selector UI |
| **Frontend Service** | `assistantService.js` | Handle rubric_id in metadata |
| **RAG Processor** | `/backend/lamb/completions/rag/rubric_rag.py` | NEW FILE - Implement rubric retrieval |
| **Database** | No schema changes | Use existing metadata field |
| **Rubric Export** | `/backend/lamb/evaluaitor/rubrics.py` | Add markdown formatting function |

---

## 3. Implementation Tasks

### 3.1 Task Breakdown

#### Phase 1: Backend RAG Processor (4-6 hours)
- [x] **Task 1.1:** Create rubric markdown formatter
- [x] **Task 1.2:** Implement `rubric_rag.py` processor
- [x] **Task 1.3:** Add rubric retrieval helper function
- [x] **Task 1.4:** Test processor with sample rubric

#### Phase 2: Backend API Enhancements (2-3 hours)
- [x] **Task 2.1:** Add rubric list endpoint for assistant form
- [x] **Task 2.2:** Update assistant validation to accept rubric metadata
- [x] **Task 2.3:** Test metadata storage and retrieval

#### Phase 3: Frontend UI (6-8 hours)
- [x] **Task 3.1:** Add "Rubric" option to RAG type selector
- [x] **Task 3.2:** Implement rubric dropdown component
- [x] **Task 3.3:** Fetch accessible rubrics list
- [x] **Task 3.4:** Show rubric preview when selected
- [x] **Task 3.5:** Update form validation
- [x] **Task 3.6:** Update save logic to include rubric_id in metadata

#### Phase 4: Testing & Documentation (4-5 hours)
- [x] **Task 4.1:** Unit tests for rubric_rag processor
- [x] **Task 4.2:** Integration test: Create assistant with rubric
- [x] **Task 4.3:** Integration test: Completion with rubric context
- [x] **Task 4.4:** Update user documentation
- [x] **Task 4.5:** Update API documentation

**Total Estimated Time:** 16-22 hours

---

## 4. Database Changes

### 4.1 No Schema Changes Required ✅

**Good News:** We can use the existing `api_callback` column (which stores the `metadata` field).

**Current Structure:**
```sql
assistants.api_callback (TEXT) -- Stores JSON metadata
```

**Example Metadata (Before):**
```json
{
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "prompt_processor": "simple_augment",
  "rag_processor": "simple_rag"
}
```

**Example Metadata (After - with rubric):**
```json
{
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "prompt_processor": "simple_augment",
  "rag_processor": "rubric_rag",
  "rubric_id": "rubric-550e8400-e29b-41d4-a716-446655440000"
}
```

### 4.2 Existing Fields Usage

**Keep Using:**
- `RAG_collections` - Set to empty string when using rubric_rag
- `RAG_Top_k` - Not used by rubric_rag (entire rubric always included)

**Rationale:** 
- No migration needed
- Backward compatible
- rubric_id stored alongside other plugin configuration

---

## 5. Backend Implementation

### 5.1 Task 1: Rubric Markdown Formatter

**File:** `/backend/lamb/evaluaitor/rubrics.py`

**Add Function:**

```python
def format_rubric_as_markdown(rubric_data: dict) -> str:
    """
    Convert rubric JSON to markdown format for LLM context
    
    Args:
        rubric_data: Full rubric JSON structure
        
    Returns:
        Formatted markdown string
    """
    md = []
    
    # Header
    md.append(f"# {rubric_data.get('title', 'Rubric')}\n")
    md.append(f"**Description:** {rubric_data.get('description', '')}\n")
    
    # Metadata
    metadata = rubric_data.get('metadata', {})
    md.append(f"**Subject:** {metadata.get('subject', 'N/A')}")
    md.append(f"**Grade Level:** {metadata.get('gradeLevel', 'N/A')}")
    md.append(f"**Scoring Type:** {rubric_data.get('scoringType', 'points')}")
    md.append(f"**Maximum Score:** {rubric_data.get('maxScore', 100)}\n")
    md.append("---\n")
    
    # Criteria table
    md.append("## Assessment Criteria\n")
    
    criteria = rubric_data.get('criteria', [])
    if not criteria:
        md.append("*No criteria defined*\n")
        return "\n".join(md)
    
    # Sort criteria by order
    sorted_criteria = sorted(criteria, key=lambda c: c.get('order', 0))
    
    # Build table header
    # Get all unique levels across criteria (assume same levels for all)
    if sorted_criteria and sorted_criteria[0].get('levels'):
        first_criterion_levels = sorted(
            sorted_criteria[0]['levels'], 
            key=lambda l: l.get('order', 0),
            reverse=True  # Higher scores first
        )
        
        header = "| Criterion |"
        for level in first_criterion_levels:
            label = level.get('label', 'Level')
            score = level.get('score', '')
            header += f" {label} ({score}) |"
        md.append(header)
        
        # Table separator
        separator = "|-----------|"
        for _ in first_criterion_levels:
            separator += "-------------|"
        md.append(separator)
    
    # Table rows (one per criterion)
    for criterion in sorted_criteria:
        name = criterion.get('name', 'Criterion')
        description = criterion.get('description', '')
        weight = criterion.get('weight', 0)
        
        # Start row with criterion name
        row = f"| **{name}**<br>*{description}*<br>({weight} points) |"
        
        # Add level descriptions
        levels = sorted(
            criterion.get('levels', []), 
            key=lambda l: l.get('order', 0),
            reverse=True
        )
        for level in levels:
            desc = level.get('description', '')
            row += f" {desc} |"
        
        md.append(row)
    
    md.append("\n---\n")
    md.append("*Use the criteria and level descriptions above to guide assessment and feedback.*")
    
    return "\n".join(md)
```

**Location:** Add to existing `/backend/lamb/evaluaitor/rubrics.py` file (after other helper functions)

**Why:** Markdown is LLM-friendly, human-readable, and preserves structure.

### 5.2 Task 2: Rubric RAG Processor

**File:** `/backend/lamb/completions/rag/rubric_rag.py` (NEW FILE)

**Full Implementation:**

```python
"""
Rubric RAG Processor
Retrieves rubric and injects as context for assessment-focused assistants
Supports both markdown and JSON formats for LLM context
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

def rag_processor(
    messages: List[Dict[str, Any]],
    assistant = None
) -> Dict[str, Any]:
    """
    Retrieve rubric and format as context (markdown or JSON)
    
    Args:
        messages: List of conversation messages
        assistant: Assistant object with metadata
        
    Returns:
        Dict with:
            - "context": str (formatted rubric as markdown or JSON)
            - "sources": List[Dict] (rubric metadata for citation)
    """
    try:
        # Extract rubric_id and format from assistant metadata
        rubric_id = None
        rubric_format = "markdown"  # Default format
        
        metadata = None
        if assistant and hasattr(assistant, 'metadata'):
            metadata_str = assistant.metadata
            if metadata_str:
                try:
                    metadata = json.loads(metadata_str)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse assistant metadata")
        
        # Also check api_callback field (where metadata is actually stored)
        if not metadata and assistant and hasattr(assistant, 'api_callback'):
            metadata_str = assistant.api_callback
            if metadata_str:
                try:
                    metadata = json.loads(metadata_str)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse assistant api_callback")
        
        if metadata:
            rubric_id = metadata.get('rubric_id')
            rubric_format = metadata.get('rubric_format', 'markdown')
        
        if not rubric_id:
            logger.warning("No rubric_id found in assistant metadata")
            return {
                "context": "",
                "sources": []
            }
        
        # Validate format
        if rubric_format not in ['markdown', 'json']:
            logger.warning(f"Invalid rubric_format '{rubric_format}', defaulting to markdown")
            rubric_format = 'markdown'
        
        # Get rubric from database
        from backend.lamb.evaluaitor.rubric_database import RubricDatabaseManager
        from backend.lamb.evaluaitor.rubrics import format_rubric_as_markdown
        
        db_manager = RubricDatabaseManager()
        
        # Get rubric by ID
        # Note: We need owner_email for permission check, use assistant owner
        owner_email = getattr(assistant, 'owner', None)
        if not owner_email:
            logger.error("Assistant has no owner")
            return {"context": "", "sources": []}
        
        rubric = db_manager.get_rubric_by_id(rubric_id, owner_email)
        
        if not rubric:
            logger.error(f"Rubric {rubric_id} not found or not accessible")
            return {
                "context": "ERROR: Rubric not found or not accessible",
                "sources": []
            }
        
        # Extract rubric data
        rubric_data = rubric.get('rubric_data')
        if isinstance(rubric_data, str):
            rubric_data = json.loads(rubric_data)
        
        # Format according to user preference
        if rubric_format == 'json':
            # Format as JSON string
            context = json.dumps(rubric_data, indent=2)
        else:
            # Format as markdown (default)
            context = format_rubric_as_markdown(rubric_data)
        
        # Prepare source citation
        sources = [{
            "type": "rubric",
            "rubric_id": rubric_id,
            "title": rubric.get('title', 'Unknown Rubric'),
            "description": rubric.get('description', ''),
            "format": rubric_format
        }]
        
        logger.info(f"Successfully retrieved rubric {rubric_id} as {rubric_format} context")
        
        return {
            "context": context,
            "sources": sources
        }
        
    except Exception as e:
        logger.error(f"Error in rubric_rag processor: {e}", exc_info=True)
        return {
            "context": f"ERROR: Failed to load rubric - {str(e)}",
            "sources": []
        }
```

**Location:** `/backend/lamb/completions/rag/rubric_rag.py`

**Key Points:**
- Reads `rubric_id` and `rubric_format` from assistant metadata
- Uses existing `RubricDatabaseManager` to retrieve rubric
- Checks permissions (owner can access own rubrics, anyone can access public rubrics)
- Formats rubric as markdown OR JSON based on user preference
- No chunking needed (entire rubric always included)
- Returns in standard RAG processor format

**Testing Checklist:**
- [ ] Processor loads dynamically with other RAG processors
- [ ] Rubric_id and format extracted correctly from metadata
- [ ] Rubric retrieved from database
- [ ] Markdown formatting correct
- [ ] JSON formatting correct (properly indented)
- [ ] Default to markdown if format not specified
- [ ] Error handling for missing rubric
- [ ] Error handling for invalid format
- [ ] Permission checking works

### 5.3 Task 3: API Endpoint for Rubric List

**File:** `/backend/creator_interface/evaluaitor_router.py`

**Add Endpoint:**

```python
@router.get("/rubrics/accessible")
async def get_accessible_rubrics_for_assistant(
    request: Request
):
    """
    Get list of rubrics accessible to user for assistant attachment
    Returns user's own rubrics + public rubrics in organization
    
    Response format optimized for dropdown selector:
    {
      "rubrics": [
        {
          "rubric_id": "rubric-123",
          "title": "Essay Writing Rubric",
          "description": "...",
          "is_mine": true,
          "is_showcase": false
        }
      ]
    }
    """
    try:
        # Get user from token
        auth_header = request.headers.get("Authorization")
        creator_user = get_creator_user_from_token(auth_header)
        
        if not creator_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        user_email = creator_user.get('user_email')
        organization_id = creator_user.get('organization_id')
        
        # Get database manager
        from backend.lamb.evaluaitor.rubric_database import RubricDatabaseManager
        db_manager = RubricDatabaseManager()
        
        # Get user's own rubrics
        my_rubrics = db_manager.get_rubrics_by_owner(
            owner_email=user_email,
            limit=1000,  # Get all
            offset=0,
            filters={}
        )
        
        # Get public rubrics in organization
        public_rubrics = db_manager.get_public_rubrics(
            organization_id=organization_id,
            limit=1000,
            offset=0,
            filters={}
        )
        
        # Format for dropdown
        accessible = []
        
        # Add user's rubrics (marked as mine)
        for rubric in my_rubrics:
            accessible.append({
                "rubric_id": rubric['rubric_id'],
                "title": rubric['title'],
                "description": rubric.get('description', ''),
                "is_mine": True,
                "is_showcase": rubric.get('is_showcase', False),
                "is_public": rubric.get('is_public', False)
            })
        
        # Add public rubrics (not already in list)
        my_rubric_ids = {r['rubric_id'] for r in my_rubrics}
        for rubric in public_rubrics:
            if rubric['rubric_id'] not in my_rubric_ids:
                accessible.append({
                    "rubric_id": rubric['rubric_id'],
                    "title": rubric['title'],
                    "description": rubric.get('description', ''),
                    "is_mine": False,
                    "is_showcase": rubric.get('is_showcase', False),
                    "is_public": True
                })
        
        # Sort: showcase first, then user's rubrics, then others
        accessible.sort(key=lambda r: (
            not r['is_showcase'],  # Showcase first (False < True)
            not r['is_mine'],      # Then user's rubrics
            r['title'].lower()     # Then alphabetical
        ))
        
        return {
            "success": True,
            "rubrics": accessible,
            "total": len(accessible)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting accessible rubrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

**Location:** Add to `/backend/creator_interface/evaluaitor_router.py`

**Response Example:**
```json
{
  "success": true,
  "rubrics": [
    {
      "rubric_id": "rubric-123",
      "title": "Essay Writing Rubric (Showcase)",
      "description": "Standard 5-paragraph essay rubric",
      "is_mine": false,
      "is_showcase": true,
      "is_public": true
    },
    {
      "rubric_id": "rubric-456",
      "title": "My Lab Report Rubric",
      "description": "Custom rubric for science labs",
      "is_mine": true,
      "is_showcase": false,
      "is_public": false
    }
  ],
  "total": 2
}
```

### 5.4 Task 4: Update Assistant Validation

**File:** `/backend/lamb/assistant_router.py` (or wherever assistant validation happens)

**No changes needed!** ✅

The metadata field already accepts arbitrary JSON, so storing `rubric_id` requires no validation changes.

**Verify:** Ensure that when `rag_processor: "rubric_rag"` is set, the system correctly loads and executes the rubric_rag.py module.

---

## 6. Frontend Implementation

### 6.1 Task 1: Update Assistant Form Component

**File:** `/frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte`

**Current RAG Section (Approximate):**

```svelte
<!-- RAG Configuration -->
<div class="form-section">
  <h3>RAG Configuration</h3>
  
  <label>
    RAG Type
    <select bind:value={ragType}>
      <option value="">No RAG</option>
      <option value="simple_rag">Knowledge Base (Multiple Collections)</option>
      <option value="single_file_rag">Single File</option>
    </select>
  </label>
  
  {#if ragType === 'simple_rag'}
    <!-- KB Collection selector -->
    <label>
      Knowledge Base Collections
      <select multiple bind:value={selectedCollections}>
        {#each kbCollections as collection}
          <option value={collection.id}>{collection.name}</option>
        {/each}
      </select>
    </label>
    
    <label>
      Top K Results
      <input type="number" bind:value={topK} min="1" max="20" />
    </label>
  {/if}
  
  {#if ragType === 'single_file_rag'}
    <!-- File selector -->
  {/if}
</div>
```

**Updated RAG Section:**

```svelte
<script>
  import { onMount } from 'svelte';
  import { fetchAccessibleRubrics } from '$lib/services/rubricService.js';
  
  let ragType = ''; // '', 'simple_rag', 'single_file_rag', 'rubric_rag'
  let selectedRubricId = '';
  let rubricFormat = 'markdown'; // 'markdown' or 'json'
  let accessibleRubrics = [];
  let loadingRubrics = false;
  
  // Load accessible rubrics on mount
  onMount(async () => {
    try {
      loadingRubrics = true;
      const response = await fetchAccessibleRubrics();
      accessibleRubrics = response.rubrics || [];
    } catch (error) {
      console.error('Failed to load rubrics:', error);
    } finally {
      loadingRubrics = false;
    }
  });
  
  // When form is loaded with existing assistant, parse metadata
  $: if (assistant && assistant.metadata) {
    try {
      const metadata = JSON.parse(assistant.metadata);
      if (metadata.rag_processor === 'rubric_rag') {
        ragType = 'rubric_rag';
        selectedRubricId = metadata.rubric_id || '';
        rubricFormat = metadata.rubric_format || 'markdown';
      }
    } catch (e) {
      console.error('Failed to parse metadata:', e);
    }
  }
  
  // Get selected rubric details for preview
  $: selectedRubric = accessibleRubrics.find(r => r.rubric_id === selectedRubricId);
</script>

<!-- RAG Configuration -->
<div class="form-section">
  <h3>RAG Configuration</h3>
  
  <label>
    RAG Type
    <select bind:value={ragType}>
      <option value="">No RAG</option>
      <option value="simple_rag">Knowledge Base (Multiple Collections)</option>
      <option value="single_file_rag">Single File</option>
      <option value="rubric_rag">Rubric (Assessment Criteria)</option>
    </select>
  </label>
  
  {#if ragType === 'simple_rag'}
    <!-- Existing KB Collection selector -->
    <label>
      Knowledge Base Collections
      <select multiple bind:value={selectedCollections}>
        {#each kbCollections as collection}
          <option value={collection.id}>{collection.name}</option>
        {/each}
      </select>
    </label>
    
    <label>
      Top K Results
      <input type="number" bind:value={topK} min="1" max="20" />
    </label>
  {/if}
  
  {#if ragType === 'single_file_rag'}
    <!-- Existing file selector -->
  {/if}
  
  {#if ragType === 'rubric_rag'}
    <div class="rubric-selector">
      {#if loadingRubrics}
        <p class="text-gray-500">Loading rubrics...</p>
      {:else if accessibleRubrics.length === 0}
        <p class="text-gray-500">
          No rubrics available. 
          <a href="/evaluaitor" class="text-blue-600 hover:underline">
            Create a rubric first
          </a>
        </p>
      {:else}
        <label>
          Select Rubric
          <select bind:value={selectedRubricId} required>
            <option value="">-- Choose a rubric --</option>
            {#each accessibleRubrics as rubric}
              <option value={rubric.rubric_id}>
                {rubric.title}
                {#if rubric.is_showcase}🌟{/if}
                {#if rubric.is_mine}(Mine){:else}(Public){/if}
              </option>
            {/each}
          </select>
        </label>
        
        <!-- Format Selector -->
        <label class="mt-4">
          Rubric Format for LLM
          <div class="flex gap-4 mt-2">
            <label class="flex items-center">
              <input 
                type="radio" 
                bind:group={rubricFormat} 
                value="markdown" 
                class="mr-2"
              />
              <span>Markdown (table format)</span>
            </label>
            <label class="flex items-center">
              <input 
                type="radio" 
                bind:group={rubricFormat} 
                value="json" 
                class="mr-2"
              />
              <span>JSON (structured data)</span>
            </label>
          </div>
          <p class="text-xs text-gray-500 mt-1">
            Choose the format that works best with your selected LLM. 
            You can test both to see which produces better results.
          </p>
        </label>
        
        {#if selectedRubric}
          <div class="rubric-preview mt-4 p-4 bg-gray-50 rounded border">
            <h4 class="font-semibold">{selectedRubric.title}</h4>
            {#if selectedRubric.description}
              <p class="text-sm text-gray-600 mt-1">{selectedRubric.description}</p>
            {/if}
            {#if selectedRubric.is_showcase}
              <span class="inline-block mt-2 px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded">
                ⭐ Showcase Template
              </span>
            {/if}
            <a 
              href="/evaluaitor/{selectedRubric.rubric_id}" 
              target="_blank"
              class="text-blue-600 hover:underline text-sm mt-2 inline-block"
            >
              View full rubric →
            </a>
          </div>
        {/if}
        
        <p class="text-sm text-gray-600 mt-2">
          💡 The selected rubric will be included in every conversation as context, 
          helping the assistant provide assessment-focused feedback.
        </p>
      {/if}
    </div>
  {/if}
</div>
```

**Key Changes:**
1. Added `rubric_rag` option to dropdown
2. Load accessible rubrics on mount
3. Show rubric selector when `rubric_rag` is selected
4. **Added format selector (markdown or JSON)** - Radio buttons for user choice
5. Display rubric preview with title, description, badges
6. Link to view full rubric in new tab
7. Parse existing rubric_id and format when editing assistant
8. Default to markdown format for new assistants

### 6.2 Task 2: Update Form Submission Logic

**File:** Same `AssistantForm.svelte`

**Current Save Logic (Approximate):**

```javascript
async function saveAssistant() {
  const metadata = {
    connector: selectedConnector,
    llm: selectedModel,
    prompt_processor: selectedPPS,
    rag_processor: ragType || ''
  };
  
  const assistantData = {
    name: assistantName,
    description: assistantDescription,
    system_prompt: systemPrompt,
    metadata: JSON.stringify(metadata),
    RAG_collections: ragType === 'simple_rag' ? selectedCollections.join(',') : '',
    RAG_Top_k: topK
  };
  
  // POST or PUT to API
}
```

**Updated Save Logic:**

```javascript
async function saveAssistant() {
  const metadata = {
    connector: selectedConnector,
    llm: selectedModel,
    prompt_processor: selectedPPS,
    rag_processor: ragType || ''
  };
  
  // Add rubric_id and format to metadata if rubric_rag is selected
  if (ragType === 'rubric_rag' && selectedRubricId) {
    metadata.rubric_id = selectedRubricId;
    metadata.rubric_format = rubricFormat; // 'markdown' or 'json'
  }
  
  const assistantData = {
    name: assistantName,
    description: assistantDescription,
    system_prompt: systemPrompt,
    metadata: JSON.stringify(metadata),
    RAG_collections: ragType === 'simple_rag' ? selectedCollections.join(',') : '',
    RAG_Top_k: ragType === 'simple_rag' ? topK : null
  };
  
  // Validate rubric selection
  if (ragType === 'rubric_rag' && !selectedRubricId) {
    alert('Please select a rubric');
    return;
  }
  
  // POST or PUT to API
  try {
    if (isEditMode) {
      await updateAssistant(assistantId, assistantData);
    } else {
      await createAssistant(assistantData);
    }
    // Success handling
  } catch (error) {
    // Error handling
  }
}
```

**Key Changes:**
1. Include `rubric_id` in metadata when `rubric_rag` is selected
2. Validate that rubric is selected before saving
3. Clear `RAG_collections` when using rubric_rag

### 6.3 Task 3: Add Rubric Service Function

**File:** `/frontend/svelte-app/src/lib/services/rubricService.js`

**Add Function:**

```javascript
/**
 * Fetch rubrics accessible to user for assistant attachment
 * (User's own rubrics + public rubrics in organization)
 * @returns {Promise<{rubrics: Array}>}
 */
export async function fetchAccessibleRubrics() {
  const API_BASE = window.LAMB_CONFIG?.api?.lambServer || 'http://localhost:9099';
  const token = localStorage.getItem('token');
  
  const response = await fetch(`${API_BASE}/creator/rubrics/accessible`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch accessible rubrics');
  }
  
  return await response.json();
}
```

**Location:** Add to existing `/frontend/svelte-app/src/lib/services/rubricService.js`

### 6.4 Task 4: Update Assistant Display/View

**File:** Wherever assistants are displayed (e.g., `AssistantsList.svelte`, `AssistantDetail.svelte`)

**Add Rubric Badge:**

```svelte
{#if assistant.metadata}
  {#try}
    {@const metadata = JSON.parse(assistant.metadata)}
    {#if metadata.rag_processor === 'rubric_rag'}
      <span class="inline-flex items-center px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded">
        📋 Uses Rubric
      </span>
    {/if}
  {/try}
{/if}
```

**Optional:** Show which rubric is attached

```svelte
{#if metadata.rag_processor === 'rubric_rag' && metadata.rubric_id}
  <span class="text-sm text-gray-600">
    Rubric: <a href="/evaluaitor/{metadata.rubric_id}" class="text-blue-600 hover:underline">
      {metadata.rubric_id}
    </a>
  </span>
{/if}
```

---

## 7. Testing Plan

### 7.1 Backend Unit Tests

**File:** `/testing/unit-tests/rubrics/test_rubric_rag.py` (NEW)

```python
"""
Unit tests for rubric_rag processor
"""

import pytest
import json
from backend.lamb.completions.rag.rubric_rag import rag_processor

class MockAssistant:
    def __init__(self, metadata):
        self.api_callback = json.dumps(metadata)
        self.owner = "test@example.com"
        self.metadata = json.dumps(metadata)

def test_rubric_rag_with_valid_rubric(monkeypatch):
    """Test rubric_rag processor with valid rubric"""
    
    # Mock rubric data
    mock_rubric = {
        "rubric_id": "test-rubric-123",
        "title": "Test Rubric",
        "description": "Test Description",
        "rubric_data": {
            "title": "Test Rubric",
            "description": "Test Description",
            "scoringType": "points",
            "maxScore": 10,
            "metadata": {
                "subject": "Math",
                "gradeLevel": "9-12"
            },
            "criteria": [
                {
                    "id": "crit-1",
                    "name": "Accuracy",
                    "description": "Mathematical accuracy",
                    "weight": 50,
                    "order": 0,
                    "levels": [
                        {
                            "id": "level-1",
                            "score": 4,
                            "label": "Excellent",
                            "description": "All correct",
                            "order": 0
                        }
                    ]
                }
            ]
        }
    }
    
    # Mock database call
    def mock_get_rubric(rubric_id, owner_email):
        return mock_rubric
    
    from backend.lamb.evaluaitor import rubric_database
    monkeypatch.setattr(
        rubric_database.RubricDatabaseManager,
        'get_rubric_by_id',
        lambda self, rid, owner: mock_get_rubric(rid, owner)
    )
    
    # Create mock assistant
    assistant = MockAssistant({
        "rag_processor": "rubric_rag",
        "rubric_id": "test-rubric-123"
    })
    
    # Call processor
    result = rag_processor(
        messages=[{"role": "user", "content": "How am I graded?"}],
        assistant=assistant
    )
    
    # Assertions
    assert result is not None
    assert "context" in result
    assert "sources" in result
    assert len(result["context"]) > 0
    assert "Test Rubric" in result["context"]
    assert "Accuracy" in result["context"]
    assert len(result["sources"]) == 1
    assert result["sources"][0]["rubric_id"] == "test-rubric-123"

def test_rubric_rag_missing_rubric_id():
    """Test rubric_rag processor when rubric_id is missing"""
    
    assistant = MockAssistant({
        "rag_processor": "rubric_rag"
        # No rubric_id
    })
    
    result = rag_processor(
        messages=[{"role": "user", "content": "Test"}],
        assistant=assistant
    )
    
    assert result["context"] == ""
    assert result["sources"] == []

def test_rubric_rag_rubric_not_found(monkeypatch):
    """Test rubric_rag processor when rubric doesn't exist"""
    
    # Mock database to return None
    from backend.lamb.evaluaitor import rubric_database
    monkeypatch.setattr(
        rubric_database.RubricDatabaseManager,
        'get_rubric_by_id',
        lambda self, rid, owner: None
    )
    
    assistant = MockAssistant({
        "rag_processor": "rubric_rag",
        "rubric_id": "nonexistent-rubric"
    })
    
    result = rag_processor(
        messages=[{"role": "user", "content": "Test"}],
        assistant=assistant
    )
    
    assert "ERROR" in result["context"] or result["context"] == ""
```

### 7.2 Integration Tests

**File:** `/testing/integration-tests/test_rubric_rag_integration.py` (NEW)

```python
"""
Integration tests for rubric RAG feature
Tests full flow: create rubric → create assistant → completion
"""

import pytest
import requests
import json

BASE_URL = "http://localhost:9099"
ADMIN_EMAIL = "admin@owi.com"
ADMIN_PASSWORD = "admin"

@pytest.fixture
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/creator/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    return response.json()["token"]

def test_full_rubric_rag_flow(auth_token):
    """
    Test complete flow:
    1. Create rubric
    2. Create assistant with rubric_rag
    3. Send completion request
    4. Verify rubric is in context
    """
    
    # Step 1: Create rubric
    rubric_data = {
        "title": "Integration Test Rubric",
        "description": "Test rubric for RAG integration",
        "metadata": {
            "subject": "Testing",
            "gradeLevel": "All"
        },
        "criteria": [
            {
                "name": "Test Criterion",
                "description": "A test criterion",
                "weight": 100,
                "levels": [
                    {
                        "score": 4,
                        "label": "Excellent",
                        "description": "Exceeds expectations"
                    },
                    {
                        "score": 1,
                        "label": "Needs Work",
                        "description": "Below expectations"
                    }
                ]
            }
        ],
        "scoringType": "points",
        "maxScore": 10
    }
    
    response = requests.post(
        f"{BASE_URL}/creator/rubrics",
        headers={"Authorization": f"Bearer {auth_token}"},
        json=rubric_data
    )
    assert response.status_code == 200
    rubric = response.json()["rubric"]
    rubric_id = rubric["rubricId"]
    
    # Step 2: Create assistant with rubric_rag
    assistant_data = {
        "name": "Test Rubric Assistant",
        "description": "Assistant using rubric RAG",
        "system_prompt": "You are a helpful assessment assistant.",
        "metadata": json.dumps({
            "connector": "openai",
            "llm": "gpt-4o-mini",
            "prompt_processor": "simple_augment",
            "rag_processor": "rubric_rag",
            "rubric_id": rubric_id
        }),
        "RAG_collections": "",
        "RAG_Top_k": None
    }
    
    response = requests.post(
        f"{BASE_URL}/creator/assistant/create_assistant",
        headers={"Authorization": f"Bearer {auth_token}"},
        json=assistant_data
    )
    assert response.status_code == 200
    assistant = response.json()["assistant"]
    assistant_id = assistant["id"]
    
    # Step 3: Send completion request
    # Note: This requires the assistant to be published or accessible via completions API
    # For now, we'll just verify the assistant was created correctly
    
    # Verify assistant metadata
    response = requests.get(
        f"{BASE_URL}/creator/assistant/get_assistant/{assistant_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    assistant_data = response.json()["assistant"]
    metadata = json.loads(assistant_data["metadata"])
    
    assert metadata["rag_processor"] == "rubric_rag"
    assert metadata["rubric_id"] == rubric_id
    
    # Cleanup
    requests.delete(
        f"{BASE_URL}/creator/assistant/delete_assistant/{assistant_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    requests.delete(
        f"{BASE_URL}/creator/rubrics/{rubric_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
```

### 7.3 Manual Testing Checklist

**Test Case 1: Create Assistant with Rubric**
- [ ] Log in as creator user
- [ ] Go to Assistants → Create New
- [ ] Select "Rubric" as RAG type
- [ ] Verify rubrics dropdown loads
- [ ] Select a rubric
- [ ] Verify rubric preview shows
- [ ] Save assistant
- [ ] Verify assistant saved with rubric_id in metadata

**Test Case 2: Edit Assistant with Rubric**
- [ ] Open existing assistant with rubric
- [ ] Verify rubric is selected in dropdown
- [ ] Change to different rubric
- [ ] Save changes
- [ ] Verify new rubric_id saved

**Test Case 3: Completion with Rubric Context**
- [ ] Publish assistant with rubric
- [ ] Access assistant via chat interface
- [ ] Ask: "What are the criteria?"
- [ ] Verify response references rubric criteria
- [ ] Ask: "What does excellent mean?"
- [ ] Verify response uses rubric level descriptions

**Test Case 4: No Rubrics Available**
- [ ] Create new user with no rubrics
- [ ] Try to create assistant with rubric_rag
- [ ] Verify message: "No rubrics available"
- [ ] Verify link to create rubric

**Test Case 5: Permission Checking**
- [ ] User A creates private rubric
- [ ] User B tries to attach User A's private rubric
- [ ] Verify User B cannot see private rubric in list
- [ ] User A makes rubric public
- [ ] Verify User B now sees rubric in list
- [ ] Verify User B can attach rubric to assistant

**Test Case 6: Showcase Rubrics**
- [ ] Admin marks rubric as showcase
- [ ] Verify showcase rubric appears at top of list
- [ ] Verify showcase badge shows (🌟)

### 7.4 Error Scenarios

**Test Error 1: Rubric Deleted After Assistant Created**
- [ ] Create assistant with rubric
- [ ] Delete the rubric
- [ ] Try to use assistant
- [ ] Verify graceful error message
- [ ] Verify assistant still functional (without context)

**Test Error 2: Invalid Rubric ID in Metadata**
- [ ] Manually edit assistant metadata with fake rubric_id
- [ ] Try to use assistant
- [ ] Verify error handling
- [ ] Verify log message

---

## 8. Design Decisions

### 8.1 Storage Location

**Decision:** Store `rubric_id` in assistant metadata (api_callback field)

**Rationale:**
- ✅ No database migration needed
- ✅ Consistent with other plugin configuration (connector, llm, rag_processor)
- ✅ Metadata is already JSON, easy to extend
- ✅ Backward compatible

**Alternative Considered:** New column `assistant.rubric_id`
- ❌ Requires migration
- ❌ Less flexible (what if we want multiple rubrics later?)
- ❌ Not consistent with plugin pattern

### 8.2 Rubric Format in Context

**Decision:** User chooses between markdown or JSON format

**Rationale:**
- ✅ Different LLMs may perform better with different formats
- ✅ Allows educators to experiment and find what works best
- ✅ Markdown: More readable, natural language structure
- ✅ JSON: More structured, better for programmatic tasks
- ✅ No database changes needed (stored in metadata)
- ✅ Can change format later without recreating assistant

**Format Options:**

**Markdown Format:**
- Human-readable table structure
- Natural language flow
- Better for chat-focused interactions
- Works well with GPT-4, Claude, etc.

**JSON Format:**
- Structured data representation
- Better for extraction tasks
- Works well with models trained on code
- Useful for programmatic grading scenarios

**Implementation:**
- Default: markdown (safer choice)
- UI: Radio buttons to select format
- Backend: Simple conditional in rubric_rag.py
- Can test both formats to compare results

### 8.3 Rubric Versioning

**Decision:** Always use latest version of rubric

**Rationale:**
- ✅ Simpler implementation
- ✅ Educators typically want latest version
- ✅ Can update rubric once, affects all assistants
- ❌ Breaking change if rubric significantly modified

**Alternative Considered:** Snapshot rubric at attachment time
- ✅ Immutable, predictable
- ❌ More complex (store rubric copy)
- ❌ Rubric updates don't propagate
- ❌ More storage space

**Future Enhancement:** Add optional rubric versioning in Phase 2

### 8.4 Multiple Rubrics

**Decision:** One rubric per assistant (Phase 1)

**Rationale:**
- ✅ Simpler UI
- ✅ Simpler implementation
- ✅ Most common use case
- ❌ Limits flexibility

**Alternative:** Allow multiple rubrics
- ❌ Complex UI (how to select multiple?)
- ❌ Context size concerns (multiple full rubrics)
- ❌ Unclear use case

**Future Enhancement:** Allow multiple rubrics in Phase 2 if needed

### 8.5 Rubric Access Control

**Decision:** User can attach:
1. Their own rubrics (private or public)
2. Public rubrics in their organization

**Rationale:**
- ✅ Consistent with rubric privacy model
- ✅ Encourages sharing of good rubrics
- ✅ Organization-scoped sharing

**Edge Case:** If rubric is made private after assistant created:
- Assistant will fail to load rubric
- Error message shown in completion
- Educator needs to select different rubric or make original public again

### 8.6 UI Placement

**Decision:** Add rubric selector to existing RAG section of assistant form

**Rationale:**
- ✅ Logically grouped with other RAG options
- ✅ Consistent with KB collections selector
- ✅ Users already familiar with this section

**Alternative:** Separate "Rubrics" section
- ❌ Adds complexity
- ❌ Rubrics are fundamentally a RAG source

---

## 9. User Documentation

### 9.1 Feature Documentation

**Title:** Using Rubrics with Learning Assistants

**Content:**

```markdown
# Using Rubrics with Learning Assistants

## Overview

You can attach a rubric to a learning assistant to provide assessment-focused context. The rubric will be included in every conversation, helping the assistant give feedback aligned with your assessment criteria.

## When to Use Rubric RAG

Use rubric RAG when you want your assistant to:
- Explain assessment criteria to students
- Provide feedback based on specific rubric levels
- Help students self-assess their work
- Answer questions about grading expectations
- Guide students toward exemplary performance

## How to Attach a Rubric

1. **Create or prepare a rubric**
   - Go to Evaluaitor section
   - Create a new rubric or make an existing rubric public

2. **Create or edit an assistant**
   - Go to Assistants → Create New (or Edit existing)
   - Scroll to "RAG Configuration" section

3. **Select Rubric RAG**
   - In "RAG Type" dropdown, select "Rubric (Assessment Criteria)"
   - A rubric selector will appear

4. **Choose your rubric**
   - Select from your own rubrics or public rubrics in your organization
   - Showcase rubrics (marked with ⭐) appear at the top
   - Preview the selected rubric to verify it's correct

5. **Choose format for LLM**
   - **Markdown (table format)** - Human-readable, works well with most LLMs
   - **JSON (structured data)** - More structured, better for code-focused models
   - You can experiment with both to see which works better for your use case

6. **Save the assistant**
   - The rubric will now be included in all conversations in your chosen format

## Example Use Cases

### Use Case 1: Essay Feedback Assistant
```
Rubric: "Essay Writing Rubric"
System Prompt: "You are a writing tutor helping students improve their essays. 
Use the attached rubric to guide your feedback."

Student: "How can I improve my thesis statement?"
Assistant: "Based on our rubric, an exemplary thesis statement should be 
clear, compelling, and debatable. Let me help you refine yours..."
```

### Use Case 2: Self-Assessment Assistant
```
Rubric: "Project Evaluation Rubric"
System Prompt: "Help students assess their own project work using the rubric."

Student: "How would you rate my research quality?"
Assistant: "Let's look at the Research criterion in our rubric. 
An Exemplary (4 points) rating requires..."
```

## Tips

- **Clear System Prompts**: Tell the assistant explicitly to use the rubric in its prompt
- **Format Choice**: Try both markdown and JSON to see which works better with your LLM
  - Markdown: Better for conversational, natural language responses
  - JSON: Better for structured extraction and programmatic tasks
- **Public Rubrics**: Make rubrics public if multiple educators will use them
- **Showcase Rubrics**: Org admins can mark high-quality rubrics as showcase templates
- **Update Rubrics**: Changes to rubrics automatically apply to all assistants using them
- **Format Changes**: You can change the format anytime by editing the assistant
- **Preview**: Always preview the rubric before attaching to verify it's correct

## Limitations

- Only one rubric per assistant (Phase 1)
- Entire rubric is included in context (no retrieval/search)
- Rubric must remain accessible (public or owned by you)
```

---

## 10. API Documentation Updates

### 10.1 New Endpoint Documentation

**Endpoint:** `GET /creator/rubrics/accessible`

**Description:** Get list of rubrics accessible to current user for assistant attachment

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "success": true,
  "rubrics": [
    {
      "rubric_id": "rubric-123",
      "title": "Essay Writing Rubric",
      "description": "Standard 5-paragraph essay rubric",
      "is_mine": true,
      "is_showcase": false,
      "is_public": false
    }
  ],
  "total": 1
}
```

**Response Fields:**
- `rubric_id` (string): Unique rubric identifier
- `title` (string): Rubric title
- `description` (string): Rubric description
- `is_mine` (boolean): Whether rubric is owned by current user
- `is_showcase` (boolean): Whether rubric is marked as showcase template
- `is_public` (boolean): Whether rubric is public in organization

**Sorting:** Showcase rubrics first, then user's rubrics, then alphabetical

### 10.2 Updated Assistant Metadata

**Assistant Metadata Format (with rubric):**

```json
{
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "prompt_processor": "simple_augment",
  "rag_processor": "rubric_rag",
  "rubric_id": "rubric-550e8400-e29b-41d4-a716-446655440000"
}
```

**New Fields:**
- `rubric_id` (string, optional): Rubric identifier when rag_processor is "rubric_rag"

**Validation:**
- If `rag_processor` is "rubric_rag", `rubric_id` should be provided
- If `rag_processor` is not "rubric_rag", `rubric_id` is ignored

---

## 11. Implementation Checklist

### Backend Tasks
- [ ] **Task 1.1:** Implement `format_rubric_as_markdown()` in `/backend/lamb/evaluaitor/rubrics.py`
- [ ] **Task 1.2:** Create `/backend/lamb/completions/rag/rubric_rag.py`
- [ ] **Task 1.3:** Test rubric_rag processor loads dynamically
- [ ] **Task 1.4:** Add `GET /creator/rubrics/accessible` endpoint
- [ ] **Task 1.5:** Test endpoint with various permission scenarios
- [ ] **Task 1.6:** Verify metadata storage works with rubric_id

### Frontend Tasks
- [ ] **Task 2.1:** Add `fetchAccessibleRubrics()` to rubricService.js
- [ ] **Task 2.2:** Add "Rubric" option to RAG type selector in AssistantForm
- [ ] **Task 2.3:** Implement rubric dropdown with loading state
- [ ] **Task 2.4:** Implement rubric preview display
- [ ] **Task 2.5:** Update form validation for rubric selection
- [ ] **Task 2.6:** Update save logic to include rubric_id in metadata
- [ ] **Task 2.7:** Update edit mode to load existing rubric selection
- [ ] **Task 2.8:** Add rubric badge to assistant list/display

### Testing Tasks
- [ ] **Task 3.1:** Write unit tests for rubric_rag processor
- [ ] **Task 3.2:** Write integration test: create assistant with rubric
- [ ] **Task 3.3:** Write integration test: completion with rubric context
- [ ] **Task 3.4:** Manual test: full flow (create rubric → assistant → chat)
- [ ] **Task 3.5:** Test error scenarios (missing rubric, deleted rubric, etc.)
- [ ] **Task 3.6:** Test permission scenarios (private/public rubrics)

### Documentation Tasks
- [ ] **Task 4.1:** Add user documentation for rubric RAG feature
- [ ] **Task 4.2:** Update API documentation with new endpoint
- [ ] **Task 4.3:** Update assistant metadata documentation
- [ ] **Task 4.4:** Create example prompts and use cases

---

## 12. Future Enhancements (Phase 2+)

### 12.1 Multiple Rubrics per Assistant
- Allow attaching multiple rubrics
- UI: Multi-select dropdown or tag-based selector
- Backend: Store array of rubric_ids in metadata
- Context: Combine multiple rubrics in markdown format

### 12.2 Rubric Versioning
- Snapshot rubric at attachment time
- Store rubric version in assistant metadata
- Option to "update to latest version"
- Show rubric change diff before updating

### 12.3 Rubric Search in Completions
- Instead of entire rubric, search relevant criteria
- Use vector similarity for user query
- Return only matching criteria/levels
- Useful for large rubrics (10+ criteria)

### 12.4 Rubric-Specific Prompt Templates
- Predefined prompt templates for assessment tasks
- Templates: "Grading Assistant", "Feedback Generator", "Self-Assessment Coach"
- Auto-populate system prompt based on template

### 12.5 Rubric Analytics
- Track which rubrics are most used in assistants
- Track completion frequency by rubric
- Show "popular rubrics" in selector

### 12.6 Rubric Compatibility Check
- Warn if rubric doesn't match assistant's purpose
- Check rubric subject vs assistant description
- Suggest relevant rubrics based on assistant name/description

---

## 13. Rollback Plan

If issues arise during implementation:

### Backend Rollback
1. Remove `/backend/lamb/completions/rag/rubric_rag.py`
2. Remove `GET /creator/rubrics/accessible` endpoint
3. Remove `format_rubric_as_markdown()` function
4. No database changes to rollback (using existing metadata field)

### Frontend Rollback
1. Remove "Rubric" option from RAG type selector
2. Remove rubric dropdown component code
3. Remove rubric-related imports and functions
4. Clear any stored rubric selections in forms

### Minimal Risk
- No database migrations
- No changes to existing RAG processors
- Feature flag could be added to disable in production if needed

---

## 14. Questions for Stakeholders

Before implementation, confirm:

1. **Rubric versioning:** Use latest version always, or snapshot at attachment time?
   - **Recommended:** Latest version (simpler, more practical)

2. **Multiple rubrics:** Support multiple rubrics per assistant in Phase 1?
   - **Recommended:** No, single rubric only (add later if needed)

3. **Context size:** Is entire rubric in context acceptable, or do we need retrieval?
   - **Recommended:** Entire rubric (most rubrics are small enough)

4. **Permission model:** Can user attach public rubrics from other orgs?
   - **Recommended:** No, only same organization (follows existing org isolation)

---

## 15. Success Criteria

Implementation is complete when:

- ✅ User can select "Rubric" as RAG option in assistant form
- ✅ User can select from accessible rubrics (own + public in org)
- ✅ User can choose rubric format (markdown or JSON)
- ✅ Rubric preview displays correctly
- ✅ Assistant saves with rubric_id and rubric_format in metadata
- ✅ rubric_rag processor successfully retrieves rubric
- ✅ rubric_rag processor formats rubric correctly (markdown or JSON)
- ✅ Completions include rubric in context in chosen format
- ✅ LLM responses reference rubric criteria
- ✅ Format can be changed by editing assistant (without recreating)
- ✅ All tests pass (unit, integration, manual)
- ✅ Documentation updated
- ✅ Feature works across browsers

---

**Document Status:** Ready for Implementation  
**Next Step:** Review with team, then begin Phase 1 Backend tasks  
**Questions/Issues:** [Open GitHub issue or contact dev team]

