# Changelog: Cost Management — Cache-Aware Token Costs & Model Breakdown

## Summary
Extended the Cost Management system to account for OpenAI prompt cache hits, providing accurate cost estimation, per-model breakdowns, organization-scoped filtering, and model pricing CRUD.

## Backend Changes

### Migration 18
- Added `cached_input_per_1m` column to `model_pricing` table
- Added `cached_prompt_tokens_total` and `non_cached_prompt_tokens_total` columns to `assistant_usage_totals`
- Updated OpenAI seed pricing with official cached input rates

### OpenAI Connector
- Streaming usage capture now includes `prompt_tokens_details.cached_tokens` when available

### `log_token_usage()`
- Extracts cached tokens from `usage_data.prompt_tokens_details.cached_tokens`
- Computes cache-aware cost: `(non_cached × input_rate) + (cached × cached_rate) + (output × output_rate)`
- Falls back to `input_per_1m` when `cached_input_per_1m` is NULL
- Stores full provider `usage` JSON in `usage_logs`
- Bounds cached_tokens to prompt_tokens to prevent negative values

### `get_all_assistants_with_usage()`
- Now returns `organization_id`, `cached_prompt_tokens`, `non_cached_prompt_tokens`

### New DB Methods
- `get_assistant_usage_by_model(assistant_id)` — per-(provider, model) aggregation from `usage_logs`
- `search_organizations(name)` — case-insensitive substring search
- `get_org_scoped_summary(organization_id)` — summary aggregated for one org
- `list_model_pricing()` — all pricing rows
- `create_model_pricing(...)` — insert new pricing row
- `update_model_pricing(id, **fields)` — update rates
- `delete_model_pricing(id)` — delete pricing row

### New/Extended API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/creator/admin/cost-overview` | Extended: `summary` object, `organization_id`, cache fields per assistant |
| `GET` | `/creator/admin/cost-overview/summary?organization_id=` | New: org-scoped summary |
| `GET` | `/creator/admin/organizations/search?name=` | New: org typeahead |
| `GET` | `/creator/admin/assistant/{id}/usage-by-model` | New: per-model breakdown |
| `GET` | `/creator/admin/model-pricing` | New: list pricing |
| `POST` | `/creator/admin/model-pricing` | New: create pricing |
| `PUT` | `/creator/admin/model-pricing/{id}` | New: update pricing |
| `DELETE` | `/creator/admin/model-pricing/{id}` | New: delete pricing |

## Frontend Changes

### `costManagementHelpers.js`
- `computeCostTotals()` now includes `cached_prompt_tokens`

### `adminService.js`
- 8 new functions using `jsonRequest`: `fetchCostOverview`, `fetchCostSummaryByOrg`, `searchOrganizations`, `fetchAssistantUsageByModel`, `fetchModelPricing`, `createModelPricing`, `updateModelPricing`, `deleteModelPricing`

### `CostManagementPanel.svelte`
- Summary cards use server-provided `summary` (not client-computed totals)
- Cache prompt tokens sub-line in Total Tokens card
- Organization filter button + active filter chip with clear
- Table scoped by org filter (search still independent)
- "More details" / "Less details" expandable rows with per-model breakdown
- "Manage model pricing" button in header

### New Components
- `AssistantUsageBreakdown.svelte` — fetches and displays per-model breakdown table with retry on error and pricing divergence note
- `OrganizationFilterModal.svelte` — search typeahead + radio select + apply/clear
- `ModelPricingModal.svelte` — pricing table with inline edit + add form + delete with ConfirmationModal

### i18n
- New keys under `admin.costManagement` for all new UI strings
- All 4 locales updated: en, es, ca, eu

## Tests Added
- `backend/tests/test_cost_management.py` — 16 tests covering migration, logging, all API endpoints
- `AssistantUsageBreakdown.svelte.test.js` — 2 tests
- `OrganizationFilterModal.svelte.test.js` — 2 tests
- `ModelPricingModal.svelte.test.js` — 3 tests (including inline edit)
- Updated `costManagementHelpers.test.js` — 2 new tests for cache fields
- Updated `CostManagementPanel.svelte.test.js` — 3 tests
