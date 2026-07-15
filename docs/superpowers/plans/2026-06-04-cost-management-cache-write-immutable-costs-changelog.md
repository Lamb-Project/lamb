# Changelog — Cost Management: Cache Write, Explicit Cache & Immutable Costs

**PRD:** `docs/superpowers/prd-2026-06-04-cost-management-cache-write-immutable-costs.md`
**Plan:** `docs/superpowers/plans/2026-06-04-cost-management-cache-write-immutable-costs.md`
**Date started:** 2026-06-05
**Date completed:** 2026-06-05

---

## Summary

Extended Cost Management to support three prompt token buckets (non-cached, cache read, cache write) for providers with explicit cache billing (Alibaba Qwen, Anthropic-style). Fixed cost immutability so pricing changes only affect new completions. Added generic explicit-cache connector support driven by `model_pricing.requires_explicit_cache`, replacing the Alibaba experiment env var. Updated admin UI to show three-bucket breakdown and configure cache write rates + explicit cache flag.

---

## Schema Changes

### Migration 19

| Column | Table | Type | Description |
|--------|-------|------|-------------|
| `cache_read_per_1m` | `model_pricing` | REAL | Cache hit rate (migrated from `cached_input_per_1m`) |
| `cache_write_per_1m` | `model_pricing` | REAL | Cache creation rate |
| `requires_explicit_cache` | `model_pricing` | INTEGER | Boolean — connector applies cache markers |
| `cache_read_tokens_total` | `assistant_usage_totals` | INTEGER | Accumulated cache read tokens |
| `cache_write_tokens_total` | `assistant_usage_totals` | INTEGER | Accumulated cache write tokens |
| `cost_usd` | `usage_logs` | REAL | Frozen per-request cost |

**Seed row:** `(provider=openai, model_name=qwen3.6-plus)` with Alibaba rates and `requires_explicit_cache=1`.

### Migration 13 Fix

Removed `cost_usd_total` from the per-startup backfill. Costs are no longer recalculated on backend restart.

---

## Backend Changes

### New Modules

| Module | File | Purpose |
|--------|------|---------|
| `token_repartition` | `backend/lamb/completions/token_repartition.py` | Extract three prompt buckets from `usage_data` |
| `cost_formula` | `backend/lamb/completions/cost_formula.py` | Compute `cost_usd` with auto-cache or explicit-cache formula |
| `explicit_cache` | `backend/lamb/completions/explicit_cache.py` | Generic explicit cache marker transform (replaces `alibaba_cache_experiment.py`) |

### Modified Functions

| Function | File | Change |
|----------|------|--------|
| `log_token_usage` | `database_manager.py` | Freezes `cost_usd` per request; stores three prompt buckets |
| `get_assistant_cost_usd` | `database_manager.py` | Reads `assistant_usage_totals.cost_usd_total` — never recalculates from current pricing |
| `get_assistant_usage_by_model` | `database_manager.py` | Returns `cache_read_tokens`, `cache_write_tokens`, `non_cached_prompt_tokens`; uses `SUM(cost_usd)` |
| `get_model_pricing_row` | `database_manager.py` | **New** — returns pricing dict for `(provider, model_name)` lookup |
| `get_all_assistants_with_usage` | `database_manager.py` | Includes `cache_read_tokens`, `cache_write_tokens` |
| `get_org_scoped_summary` | `database_manager.py` | Returns `cache_read_tokens`, `cache_write_tokens` |
| `list_model_pricing` | `database_manager.py` | Returns `cache_read_per_1m`, `cache_write_per_1m`, `requires_explicit_cache` |
| `create_model_pricing` | `database_manager.py` | Accepts new fields |
| `update_model_pricing` | `database_manager.py` | Accepts new fields |

### Connector Changes

| File | Change |
|------|--------|
| `backend/lamb/completions/connectors/openai.py` | Replaced `alibaba_cache_experiment` import with `explicit_cache`; accepts `requires_explicit_cache` kwarg; added `_usage_to_dict()` helper to normalize non-streaming usage (captures `cache_creation_input_tokens`) |
| `backend/lamb/completions/main.py` | Looks up `requires_explicit_cache` from `model_pricing` and passes to connector (both `create_completion` and `run_lamb_assistant`) |
| `backend/lamb/completions/connectors/ollama.py` | Accepts `requires_explicit_cache` kwarg (no-op) |
| `backend/lamb/completions/connectors/bypass.py` | Accepts `requires_explicit_cache` kwarg (no-op) |
| `backend/lamb/completions/connectors/banana_img.py` | Accepts `requires_explicit_cache` kwarg (no-op) |

### Deleted Files

| File | Reason |
|------|--------|
| `backend/lamb/completions/alibaba_cache_experiment.py` | Replaced by `explicit_cache.py` |

### Docker Compose

| File | Change |
|------|--------|
| `docker-compose-example.yaml` | Removed `LLM_ALIBABA_CACHE_EXPERIMENT=true` env var |

---

## API Changes

### `GET /creator/admin/assistant/{id}/usage-by-model`

**Response shape changed:**

| Old field | New field |
|-----------|-----------|
| `cached_prompt_tokens` | `cache_read_tokens` |
| — | `cache_write_tokens` |
| — | `non_cached_prompt_tokens` |
| `pricing.cached_input_per_1m` | `pricing.cache_read_per_1m` |
| — | `pricing.cache_write_per_1m` |
| — | `pricing.requires_explicit_cache` |

`cost_usd` is now `SUM(usage_logs.cost_usd)` — not recalculated.

### `GET /creator/admin/cost-overview`

**Summary object:**

| Old field | New field |
|-----------|-----------|
| `cached_prompt_tokens` | `cache_read_tokens` |
| — | `cache_write_tokens` |

**Assistant rows:** Added `cache_read_tokens`, `cache_write_tokens`.

### Model Pricing CRUD

`ModelPricingCreate` and `ModelPricingUpdate` Pydantic models now accept `cache_read_per_1m`, `cache_write_per_1m`, `requires_explicit_cache`.

---

## Frontend Changes

### `AssistantUsageBreakdown.svelte`

- Replaced single **Cached** column with **Non-cached**, **Cache read**, **Cache write**
- Removed pricing recalculation disclaimer
- Added identity footnote: "Prompt = non-cached + cache read + cache write"

### `ModelPricingModal.svelte`

- Renamed "Cached $/1M" to "Cache read $/1M"
- Added "Cache write $/1M" column
- Added "Requires explicit cache treatment" checkbox
- Updated helper text to explain immutability

### `CostManagementPanel.svelte`

- Summary card shows "Cache read: N · Cache write: M" instead of "Cached prompt: N"

### `costManagementHelpers.js`

- `computeCostTotals()` now accumulates `cache_read_tokens` and `cache_write_tokens` (with backward-compatible fallback to `cached_prompt_tokens`)

### i18n

- Added keys for `breakdown.nonCachedPrompt`, `breakdown.cacheRead`, `breakdown.cacheWrite`, `breakdown.identityNote`, `pricing.cacheReadRate`, `pricing.cacheWriteRate`, `pricing.explicitCache`, `pricing.explicitCacheLabel`, `pricing.cacheReadHelper`, `pricing.cacheWriteHelper`, `pricing.explicitCacheHelper`, `summary.cacheRead`, `summary.cacheWrite` in `en`

---

## Testing

### Backend Tests (`test_cost_management.py`)

| Test class | Count | Coverage |
|------------|-------|----------|
| `TestMigration19` | 8 | Schema columns, seed row |
| `TestMigration13Fix` | 1 | Cost immutability across restart |
| `TestTokenRepartition` | 6 | Three-bucket extraction, dedup, clamping |
| `TestCostFormula` | 5 | Auto-cache, explicit-cache, fallback rates |
| `TestLogTokenUsageCacheAware` | 5 | Updated for new column names |
| `TestLogTokenUsageImmutable` | 3 | Frozen cost, three-bucket totals |
| `TestGetAssistantCostUsd` | 2 | Frozen total, unknown assistant |
| `TestMigration19Backfill` | 1 | Legacy row backfill |
| `TestUsageByModelBreakdown` | 2 | Stored cost, three-bucket response |
| `TestCostOverviewAPI` | 1 | Summary cache read/write |
| `TestUsageByModelAPI` | 1 | Three-bucket response |
| `TestModelPricingCRUD` | 3 | New fields in CRUD |
| `TestExplicitCache` | 4 | Marker placement, immutability |

**Total tests:** 48
**All passing:** YES

---

## Commits (14 total)

1. `feat: Migration 19 schema — cache write, explicit cache, cost_usd columns`
2. `feat: Migration 19 seed — qwen3.6-plus pricing with explicit cache`
3. `fix: Migration 13 no longer recalculates cost_usd_total on startup`
4. `feat: token repartition — extract three prompt buckets from usage_data`
5. `feat: cost formula — three-bucket and auto-cache cost computation`
6. `feat: log_token_usage freezes cost_usd per request, stores three prompt buckets`
7. `fix: get_assistant_cost_usd reads frozen total, never recalculates`
8. `feat: Migration 19 backfill — compute cost_usd for legacy usage_logs rows`
9. `feat: get_assistant_usage_by_model returns three buckets, uses SUM(cost_usd)`
10. `feat: API returns three prompt buckets, cache read/write in cost-overview, pricing CRUD updated`
11. `feat: explicit_cache module, connector uses model_pricing for cache markers, removes experiment`
12. `chore: remove LLM_ALIBABA_CACHE_EXPERIMENT env var from docker-compose`
13. `fix: non-streaming usage dict captures cache_creation_input_tokens`
14. `feat: frontend — three-bucket breakdown, pricing modal with cache write/explicit cache, summary cards, i18n`
15. `fix: add get_model_pricing_row, delete orphaned experiment, complete i18n, remove duplicate return`
16. `fix: run_lamb_assistant passes requires_explicit_cache to connector`

---

## Acceptance Criteria Status

| Criterion | Status | Notes |
|-----------|--------|-------|
| Usage with `cache_creation_input_tokens=18198` → `cache_write=18198`, `non_cached=958` | DONE | Tested in TestLogTokenUsageImmutable |
| Identity: `prompt = non_cached + cache_read + cache_write` | DONE | Tested in TestTokenRepartition |
| Breakdown shows `cache_write_tokens = 0` for OpenAI | DONE | Tested in TestLogTokenUsageCacheAware |
| Breakdown table shows Non-cached, Cache read, Cache write columns | DONE | UI updated |
| API returns new fields, no `cached_prompt_tokens` | DONE | Response shape updated |
| Sum of breakdown `cost_usd` equals main table cost | DONE | Uses SUM(cost_usd) |
| Pricing change does not affect existing totals | DONE | Tested in TestMigration13Fix, TestLogTokenUsageImmutable |
| Backend restart does not recalculate costs | DONE | Tested in TestMigration13Fix |
| Explicit cache checkbox → `cache_control` in outbound request | DONE | explicit_cache.py + connector |
| No env var required for explicit cache | DONE | LLM_ALIBABA_CACHE_EXPERIMENT removed |
| Migration 13 backfill does not set `cost_usd_total` | DONE | Removed from backfill SQL |
| Qwen seed row exists after migration | DONE | Tested in TestMigration19 |
| `get_assistant_cost_usd` returns frozen total (quota/creator paths) | DONE | Tested in TestGetAssistantCostUsd |
| Migration 19 backfill rebuilds `cache_write_tokens_total` from history | DONE | Backfill loop in Migration 19 |
| Non-streaming responses capture `cache_creation_input_tokens` in usage | DONE | _usage_to_dict helper |
| `run_lamb_assistant` passes `requires_explicit_cache` to connector (UI + Open WebUI chat) | DONE | main.py fix |
