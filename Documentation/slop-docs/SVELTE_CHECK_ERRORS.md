# svelte-check: 556 pre-existing type errors

**Date observed:** 2026-03-13  
**Tool:** `npm run check` (svelte-check) in `frontend/svelte-app/`  
**Total:** 556 errors, 10 warnings across 35 files

These errors pre-date recent feature work (cost management / quota UI). They do not currently cause runtime failures since the project uses JavaScript with JSDoc rather than full TypeScript, but they indicate missing or incorrect type annotations and should be resolved to keep type checking meaningful.

---

## Affected files

```
routes/admin/+page.svelte
routes/assistants/+page.svelte
routes/evaluaitor/+page.svelte
routes/org-admin/+page.svelte
routes/prompt-templates/+page.svelte
lib/components/AssistantsList.svelte
lib/components/ChatInterface.svelte
lib/components/KnowledgeBaseDetail.svelte
lib/components/KnowledgeBasesList.svelte
lib/components/Nav.svelte
lib/components/analytics/ChatAnalytics.svelte
lib/components/assistants/AssistantForm.svelte
lib/components/assistants/AssistantSharing.svelte
lib/components/assistants/AssistantSharingModal.svelte
lib/components/common/FilterBar.svelte
lib/components/common/Pagination.svelte
lib/components/evaluaitor/RubricAIChat.svelte
lib/components/evaluaitor/RubricAIGenerationModal.svelte
lib/components/evaluaitor/RubricEditor.svelte
lib/components/evaluaitor/RubricForm.svelte
lib/components/evaluaitor/RubricMetadataForm.svelte
lib/components/evaluaitor/RubricPreview.svelte
lib/components/evaluaitor/RubricTable.svelte
lib/components/evaluaitor/RubricsList.svelte
lib/components/modals/TemplateSelectModal.svelte
lib/components/promptTemplates/PromptTemplatesContent.svelte
lib/services/analyticsService.js
lib/services/assistantService.js
lib/services/knowledgeBaseService.js
lib/services/rubricService.js
lib/services/templateService.js
lib/stores/rubricStore.svelte.js
lib/stores/templateStore.js
lib/utils/listHelpers.js
lib/utils/orgAdmin.js
```

---

## Error categories (by frequency)

| Count | Error |
|------:|-------|
| 57 | `Parameter 'event' implicitly has an 'any' type` |
| 22 | `'error'/'err'/'e' is of type 'unknown'` (catch block variables not narrowed) |
| 22 | `Property '...' does not exist on type 'never'` (untyped array/object state) |
| 10 | `Parameter 'template' implicitly has an 'any' type` |
| 10 | `Generic type 'Array<T>' requires 1 type argument(s)` |
| 9 | `Element implicitly has an 'any' type because expression of type 'any' can't be used to index type '{}'` |
| 8 | `Parameter 'rubric' implicitly has an 'any' type` |
| 7 | `Type 'string' is not assignable to type '"desc" \| "asc" \| undefined'` |
| 7 | `Parameter 'user' / 'templateId' implicitly has an 'any' type` |
| 5 | `Type 'string' is not assignable to type 'null'` |
| 5 | `Property 'totalPages'/'items'/'filteredCount'/'currentPage' does not exist on type 'Object'` (API responses typed as `Object`) |
| 5 | `Argument of type 'any[]' is not assignable to parameter of type 'never[]'` |
| 4 | `Type 'Object' is not assignable to type 'AxiosHeaders | ...'` (axios headers typing) |
| 4 | `Property 'token' does not exist on type 'object'` |
| 4 | `Property 'rubric' does not exist on type 'Rubric'. Did you mean 'rubricId'?` |

---

## Root causes

1. **Implicit `any` on event/callback parameters** — `$state([])` initialised as empty array infers `never[]`; callbacks typed as `(event) =>` without annotation. Fix: add `/** @type {SomeType[]} */` JSDoc or `/** @param {Event} event */`.

2. **`catch (err)` blocks** — In strict mode `err` is `unknown`. Fix: add `/** @type {any} */` cast or use `instanceof Error` narrowing.

3. **Untyped `$state([])` / `$state({})`** — Svelte 5 infers `never[]` or `{}` for empty initial values. Fix: annotate with JSDoc `@type` or initialise with a typed value.

4. **API responses typed as `Object`** — several service calls return `Object` instead of a concrete interface. Fix: define JSDoc `@typedef` for pagination envelopes (`{ items, currentPage, totalPages, filteredCount }`).

5. **`Array<T>` without type argument** — some files use raw `Array` instead of `Array<SomeType>` or `SomeType[]`.

6. **Axios `headers` shape mismatch** — passing a plain object where AxiosHeaders is expected. Fix: use `axios.defaults.headers.common` or cast via `/** @type {import('axios').AxiosRequestConfig} */`.

---

## Suggested approach

- Fix files in order of impact: services → stores → components → routes.
- `lib/utils/listHelpers.js` and `lib/utils/orgAdmin.js` are likely helpers used everywhere — fixing them may cascade fixes elsewhere.
- The evaluaitor `Rubric*` files share a common `Rubric` / `RubricData` typing problem; fixing `rubricStore.svelte.js` types will likely resolve many downstream errors in one go.
- No runtime breakage is expected; this is purely a type-hygiene clean-up.

---

## How to reproduce

```bash
cd frontend/svelte-app
npm run check 2>&1 | tail -3
# svelte-check found 556 errors and 10 warnings in 35 files
```
