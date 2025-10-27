# GitHub Issue #62 Comment

## Root Cause Identified: Overly Aggressive Reactivity in AssistantForm

I've diagnosed the issue where users cannot change the Language Model (LLM) dropdown when editing a learning assistant. 

### What's Happening

The problem is caused by **overly aggressive reactivity** in `AssistantForm.svelte`:

1. In Svelte 5, the `assistant` prop object reference can change frequently due to the reactivity system (proxies, parent re-renders, etc.)
2. The component has a `$effect()` (lines 162-197) that watches the `assistant` prop
3. When the reference changes (even if the actual data hasn't), the effect triggers and calls `populateFormFields(assistant, true)`
4. This function **overwrites all form fields** with values from the prop, including any changes the user just made
5. The `preserveDescription` parameter only protects the description field, not the language model or other configuration fields

**Console evidence from testing:**
```
AssistantForm.svelte: $effect (assistant prop) running...
Assistant reference changed, repopulating fields (preserving description).
Populating form fields from: {... selectedLLM: gpt-4o ...}
Form fields populated: {... selectedLLM: gpt-4o ...}
```

### Affected Fields

This bug affects **all configuration fields** in edit mode, not just the language model:
- ❌ Language Model (LLM)
- ❌ Prompt Processor
- ❌ Connector
- ❌ RAG Processor  
- ❌ System Prompt
- ❌ Prompt Template
- ❌ RAG Top K
- ❌ Selected Knowledge Bases
- ❌ Selected Rubrics

### Solution: Form Dirty State Tracking

We're implementing **Form Dirty State Tracking** - a standard UX pattern that:

1. **Tracks when user makes any form changes** with a `formDirty` flag
2. **Prevents automatic repopulation** when the form has unsaved changes
3. **Only resets** when:
   - User explicitly cancels (revert to original)
   - User saves successfully (commit changes)
   - Assistant ID changes (loading different assistant)

This approach:
- ✅ Preserves ALL user edits, not just description
- ✅ Standard UX pattern (matches user expectations)
- ✅ Minimal performance impact
- ✅ Works for all form fields automatically

### Implementation Plan

1. Add `formDirty = $state(false)` state variable
2. Set `formDirty = true` when any input changes (via event handlers)
3. Modify the `$effect` to skip repopulation when `formDirty === true`
4. Reset `formDirty = false` on save, cancel, or when loading a different assistant

### Timeline

Fix is being implemented now and will be included in the next commit.

---

**Note:** This pattern will be documented in our architecture guide as the standard approach for preventing reactivity-related UX issues in forms.


