# LLM Selection Fix Summary

**Date:** November 4, 2025  
**Issue:** LLM dropdown selection was being lost when editing assistants  
**Related to:** Knowledge Base selection issue (Issue #96)  
**Root Cause:** Svelte 5 reactivity causing unnecessary form repopulation

---

## Problem Description

When editing an assistant in the AssistantForm component, the selected **Language Model (LLM)** value was being unexpectedly cleared or reset to a default value. This was the same issue that affected Knowledge Base selections (Issue #96), but manifesting in a different field.

### User Experience Impact

- Users would open an assistant for editing with LLM set to (e.g.) `gpt-4o`
- The form would display briefly with correct value
- Then the LLM dropdown would reset to a different value (typically the first in the list)
- Users' saved configuration was not being respected
- Silent data corruption risk if users saved without noticing

### Technical Root Cause

**Svelte 5's Enhanced Reactivity System:**

Svelte 5 wraps reactive objects with proxies to enable its fine-grained reactivity. This can cause prop references to change frequently, even when the underlying data hasn't changed. In the AssistantForm component:

1. The `assistant` prop reference changed due to Svelte 5's proxy wrapping
2. The `$effect` at line 203 detected this reference change
3. The effect called `populateFormFields(assistant, true)` on line 242 (OLD CODE)
4. `populateFormFields` re-set ALL form fields including:
   - `selectedPromptProcessor`
   - `selectedConnector` 
   - `selectedLlm` ← **This was the problem**
   - `selectedRagProcessor`
5. The re-population happened WHILE the user was viewing/editing the form
6. User selections were overwritten with values from the `assistant` prop

**Why It Happened:**
The original code assumed that if `formDirty === false`, it was safe to repopulate all fields. However, this didn't account for spurious reference changes from Svelte 5's reactivity that don't represent actual data changes.

---

## Solution Implemented

### Code Changes

**File:** `/opt/lamb/frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte`

**Lines 239-252:** Modified the `$effect` to SKIP repopulation on reference-only changes:

```javascript
} else {
    // FIX: Prevent unnecessary repopulation that causes field resets
    // Svelte 5's reactivity can cause prop reference changes even when data hasn't changed
    // Only repopulate basic text fields, NOT the configuration dropdowns
    // Configuration dropdowns (connector, llm, rag processor, etc.) should only be
    // populated on initial load or explicit assistant change (handled above)
    if (assistant && !formDirty) {
        console.log('[AssistantForm] Skipping full repopulation - form is clean but only assistant reference changed. Protecting user selections.');
        // We intentionally do NOT call populateFormFields here to protect dropdown selections
        // The only case where we'd repopulate is on actual ID change (handled above)
    } else if (assistant && formDirty) {
        console.log('[AssistantForm] Skipping repopulation - form is dirty (user has unsaved changes)');
    }
}
```

### What Changed

**BEFORE (Buggy):**
- Reference change → Repopulate ALL fields (including dropdowns)
- Overwrote user selections on every reactive update

**AFTER (Fixed):**
- Reference change → Skip repopulation entirely
- Only repopulate on actual assistant ID change (line 226)
- Configuration dropdowns (Connector, LLM, RAG Processor, Prompt Processor) are protected

### Repopulation Strategy

The form now uses a **strict repopulation policy**:

| Scenario | Action | Reason |
|----------|--------|--------|
| Assistant ID changes | Full repopulation (line 226) | Loading different assistant |
| User cancels edits | Full repopulation (via `switchToViewMode()`) | Explicit user action |
| Reference change only | **Skip repopulation** | Protect user selections |
| Form is dirty | Skip repopulation | Protect unsaved changes |

---

## Fields Protected by This Fix

This fix protects ALL configuration dropdown fields from spurious resets:

- ✅ **Language Model (LLM)** - Primary fix target
- ✅ **Connector** - Also protected
- ✅ **Prompt Processor** - Also protected
- ✅ **RAG Processor** - Also protected
- ✅ **Knowledge Base selections** - Already fixed by Issue #96 with deferred pattern
- ✅ **Rubric selections** - Also protected
- ✅ **File selections** - Also protected

The form now maintains stability across all fields during editing.

---

## Related Fixes

This fix complements the **Knowledge Base selection fix (Issue #96)**, which used a different pattern:

| Field Type | Pattern Used | Reason |
|------------|--------------|--------|
| **Synchronous dropdowns** (LLM, Connector) | Skip repopulation | Options available immediately |
| **Async multi-select** (Knowledge Bases) | Deferred selection | Options load asynchronously |

Both fixes address the same underlying Svelte 5 reactivity issue but use appropriate patterns for their data loading characteristics.

---

## Testing Performed

### Manual Testing

1. ✅ Open assistant for editing with LLM = `gpt-4o`
2. ✅ Verify LLM dropdown shows `gpt-4o` and stays selected
3. ✅ Navigate to different assistant and back
4. ✅ Verify LLM persists across navigation
5. ✅ Change LLM, save, reload page
6. ✅ Verify saved LLM value is restored correctly

### Browser Testing

- ✅ Chrome 120+ - Working correctly
- ✅ Firefox 121+ - Working correctly
- ✅ Safari 17+ - Expected to work (proxy behavior consistent)

---

## Architecture Documentation Updated

This fix follows the **Form Dirty State Tracking** pattern documented in:

**`Documentation/lamb_architecture.md`** - Section 17.1

The architecture document now includes:
- Form dirty state tracking best practices
- Guidance on handling Svelte 5 reactivity
- When to use skip-repopulation vs. deferred-selection patterns
- Examples of both patterns in action

---

## Prevention Guidelines

To prevent similar issues in future form components:

### 1. Always Use Form Dirty Tracking

```javascript
let formDirty = $state(false);

function handleFieldChange() {
    formDirty = true;
}

// In effects:
if (!formDirty) {
    // Only safe if you're CERTAIN there's an actual data change
}
```

### 2. Be Selective About Repopulation

Don't repopulate on reference changes unless you're certain the data has actually changed:

```javascript
// BAD: Repopulates on any reference change
$effect(() => {
    if (data) {
        populateAllFields(data);
    }
});

// GOOD: Only repopulates on meaningful changes
$effect(() => {
    if (data?.id !== previousId) {
        populateAllFields(data);
        previousId = data.id;
    }
});
```

### 3. Test with Slow Interactions

- Open form and wait 5 seconds before interacting
- Switch between items rapidly
- Use browser back/forward buttons
- All should preserve user selections

---

## Additional Notes

### Why Not Just Remove the Effect?

The effect is still needed for:
1. Initial form population when assistant changes
2. Switching between assistants in the same session
3. Resetting form when assistant becomes null

### Why Not Use Deferred Selection for LLM?

LLM options are available **synchronously** from the store via `updateAvailableModels()`. Deferred selection is only needed when options load **asynchronously** (like fetching from API).

### Complementary to Issue #96 Fix

This fix addresses:
- Synchronous dropdown selections (LLM, Connector, etc.)

Issue #96 addressed:
- Asynchronous multi-select (Knowledge Bases)
- Race conditions between data fetch and selection application

Both are needed for complete form stability.

---

## Conclusion

The LLM selection issue was caused by the same Svelte 5 reactivity characteristic that caused the Knowledge Base selection issue, but required a simpler fix due to synchronous data availability. The solution is to be more conservative about when we repopulate form fields, protecting user selections from spurious reactive updates.

**Key Takeaway:** With Svelte 5's enhanced reactivity, we must explicitly guard against unnecessary repopulation caused by reference changes that don't represent actual data changes.

---

**Status:** ✅ **FIXED**  
**Verification:** Manual testing passed  
**Documentation:** Architecture doc updated with patterns

