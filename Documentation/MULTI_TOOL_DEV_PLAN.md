# Multi-Tool Assistant Delivery Plan

**Scope:** Implement backend + frontend support for multi-tool assistants as specified in `Documentation/MULTI_TOOL_ASSISTANT_BACKEND_SPEC.md` and `Documentation/MULTI_TOOL_ASSISTANT_FRONTEND_SPEC.md`, aligned with overall `lamb_architecture.md`.  
**Date:** Dec 9, 2025  
**Owner:** Multi-tool squad  
**Working branch:** `multi-tool` (current)

## Goals
- Enable multiple tools per assistant with dynamic placeholders and plugin architecture (backend + frontend).
- Preserve legacy assistants via migrate-on-access with `_format_version`.
- Ship with test coverage and manual validation checkpoints suitable for incremental rollout / feature flag.
- When streaming, surface per-tool status messages in markdown (e.g., “querying knowledge base {kb}”).
- Add assistant-level `verbose` flag to emit pipeline traces (inputs/outputs, prompt crafting) with safe redaction.

## References
- Backend spec: `Documentation/MULTI_TOOL_ASSISTANT_BACKEND_SPEC.md`
- Frontend spec: `Documentation/MULTI_TOOL_ASSISTANT_FRONTEND_SPEC.md`
- Architecture: `Documentation/lamb_architecture.md`

## Assumptions / Non-Goals
- Backend is source of truth for migrations; frontend assumes new format, only defensive logging on legacy payloads.
- MVP keeps sequential tool execution; optional guarded parallel mode is post-MVP.
- Per-tool execution timeouts are configurable via env vars with sane defaults when unset.
- Tool set in scope: `simple_rag` → `{context}`, `rubric` → `{rubric}`, `single_file` → `{file}`, `no_tool`.
- Open WebUI integration remains unchanged beyond assistant registration.
- Logging captures tool output lengths (not contents) for observability/privacy balance.
- Streaming status messages are human-friendly markdown snippets emitted only when streaming is on; they must not leak sensitive payloads.
- `verbose` assistant flag (metadata) gates detailed pipeline traces; traces must redact secrets (API keys, access tokens, PII).

## High-Level Phases & Checkpoints
Each checkpoint includes recommended manual tests before moving forward.

### Phase 0 — Repo Hygiene & Baseline (0.5d)
- Confirm branch state, run lint/tests, note existing failing tests.
- Capture current `/lamb/completions` behavior for regression baseline.
- Prepare feature flag wiring for frontend (`VITE_FEATURE_MULTI_TOOL`) but keep off.
**Checkpoint 0 Tests**
- `pytest testing/unit-tests -q` (baseline) and note failures.
- Hit `GET /lamb/v1/completions/list` (legacy) to snapshot available rag processors.

### Phase 1 — Backend Foundations (Tools Directory) (1-2d)
- Create `lamb/completions/tools/` with `__init__.py`, `base.py` (ToolDefinition/ToolResult/BaseTool).
- Add `tool_registry.py` with discovery (new + legacy) per spec §8.
- Add `tool_orchestrator.py` with cached module loading and execution per spec §7.1.
- Migrate/rename legacy processors into tools (`no_tool.py`, `simple_rag.py`, `rubric.py`, `single_file.py`) with new `tool_processor` wrapper.
**Checkpoint 1 Tests**
- Unit: add `testing/unit-tests/test_tool_registry.py` (discovery & definitions).
- Manual API: none yet; run `python -m pytest testing/unit-tests/test_tool_registry.py`.

### Phase 2 — Backend Pipeline Integration (1-2d)
- Update `lamb/completions/main.py`: replace `get_rag_context` with `get_tool_contexts`, call orchestrator, aggregate sources.
- Update prompt processor `pps/simple_augment.py` for dynamic placeholder replacement and cleanup of unused placeholders.
- Maintain legacy fallback for assistants lacking `tools[]`.
- Add per-tool timeout handling with env-configurable defaults (e.g., `TOOL_DEFAULT_TIMEOUT_MS`, per-tool override) and clear timeout error reporting.
- When streaming, emit markdown status events per tool step (e.g., “querying knowledge base {kb}”, “merging contexts”), preserving order.
- Add assistant `verbose` flag plumbed through request; when enabled, emit detailed (redacted) trace: tool inputs, outputs length, prompt template after substitution.
**Checkpoint 2 Tests**
- Unit: add `test_multi_tool_pipeline.py` for single/multi tool execution.
- Manual: call completions with mocked assistant metadata via curl/postman:
  - Single tool `{context}` still works (legacy + new format).
  - Multi-tool (context + rubric) returns both placeholders populated.

### Phase 3 — Migration Layer (Backend) (1d)
- Implement migrate-on-access in `database_manager.py` (`migrate_assistant_if_needed`, `_migrate_v1_to_v2`, `_format_version`).
- Ensure legacy DB columns remain read-only, metadata updated in DB on access.
- Add migration logging channel `lamb.migration` with structured payload.
**Checkpoint 3 Tests**
- Manual: seed legacy assistant (rag_processor only), hit `GET /lamb/v1/assistant/{id}` → response includes `_format_version: 2` and `tools[]`; DB row updated.
- Manual: run completion on legacy assistant, verify migration + successful response.
- Log review: migration log entries emitted once per assistant.

### Phase 4 — Backend APIs & Validation (0.5-1d)
- Add `/tools` and `/tools/{tool}` endpoints, `/tools/{tool}/validate`, update `/list` to include tools.
- Ensure `normalize_tool_config` used consistently where metadata read.
**Checkpoint 4 Tests**
- Manual API: `GET /lamb/v1/completions/tools` returns registry items with schemas.
- Manual API: `POST /lamb/v1/completions/tools/simple_rag/validate` with bad payload returns validation errors.

### Phase 5 — Frontend Foundations (1-2d)
- Create tool plugin registry `frontend/.../assistants/tools/plugins/index.js` and toolStore.
- Build shell components: `ToolsManager`, `ToolSelector`, `ToolConfigList`, `ToolConfigCard`, `ToolPlaceholderBadge`.
- Wire feature flag guard in `AssistantForm.svelte` (behind `MULTI_TOOL_UI`).
**Checkpoint 5 Tests**
- Manual (storybook or page scaffold): render ToolsManager with mock tools array; add/remove/enable/disable tool cards; ensure placeholder badges show.

### Phase 6 — Frontend Plugins (1-2d)
- Extract existing per-processor UIs into plugins: `KnowledgeBaseToolConfig`, `RubricToolConfig`, `SingleFileToolConfig`.
- Implement validation hooks and loading states per spec §6.
- Ensure plugin emits `change` events and respects `disabled`.
**Checkpoint 6 Tests**
- Manual: in isolated view, change KB selection, rubric selection, file path → parent receives updates; validation warnings appear when required fields empty.

### Phase 7 — Frontend Integration into AssistantForm (1-2d)
- Replace legacy RAG dropdown with ToolsManager when flag on.
- Update form state load/save paths to use `metadata.tools[]`; remove writes to legacy fields.
- Update prompt template helper buttons to show dynamic placeholders from active tools.
**Checkpoint 7 Tests**
- Manual: load existing assistant (post-migration) → tools render correctly.
- Manual: add multiple tools, save, reopen → configuration persists.
- Manual: disable a tool and confirm placeholder removed from template preview.

### Phase 8 — E2E & Regression (1-2d)
- Add Playwright test `tests/multi-tool-assistant.spec.js` for create/edit flows.
- Add integration tests for legacy assistant loading (defensive).
**Checkpoint 8 Tests**
- Playwright: create assistant with KB + rubric; save; reload; ensure two tool cards present.
- Playwright: open legacy assistant id → see tool card produced by migrated data.

### Phase 9 — Rollout & Hardening (0.5-1d)
- Enable feature flag in staging; run smoke on completions and assistant save.
- Monitor migration logs; sample DB rows for `_format_version`.
- Plan production enablement window and rollback (disable flag + rely on preserved legacy columns).
- Verify per-tool timeout defaults are set from env with safe fallbacks and observability logs emit length-only.
- Validate streaming status messages render in clients and redact sensitive data; ensure `verbose` traces are off by default in prod configs.
**Checkpoint 9 Tests**
- Staging manual: create/edit assistants, run completions across orgs; verify logs clean.
- Ops: confirm dashboards/alerts for migration errors and tool execution errors.

### Post-MVP — Parallel Execution (optional, guarded)
- Add orchestrator option for limited parallelism (configurable worker cap, e.g., `TOOL_MAX_CONCURRENCY=2`) with timeout enforcement per tool.
- Ensure deterministic merge order; document that placeholder substitution order is unaffected.
- Add feature flag `ENABLE_PARALLEL_TOOLS` default off; load test before enabling.
**Parallel Checkpoint**
- Load test with mixed tools; confirm latency improvements and no race regressions.

## Cross-Cutting Tasks
- Logging/Observability: add structured logs around tool execution duration and errors; include tool type and assistant id.
- Error handling: ensure tool errors return empty content but do not break overall completion.
- Security: validate file path traversal in single_file; ensure auth on new endpoints matches completions router patterns.
- Performance: cache tool discovery; keep sequential execution; note future parallelization hook.
- Timeouts: enforce per-tool timeout with env defaults and per-tool override; surface timeout errors in logs/metadata.
- Telemetry privacy: log lengths/metadata only, never tool content; redact secrets in verbose traces.
- Streaming UX: define markdown status message schema and throttle to avoid chat spam; ensure order matches execution.

## Manual Test Scripts (quick reference)
- **MT1:** API `/tools` list returns ≥3 tools with schemas.
- **MT2:** Completion with assistant using `{context}` only returns context unchanged from legacy behavior.
- **MT3:** Completion with tools `[simple_rag, rubric]` returns both `{context}` and `{rubric}` substituted; unreplaced placeholders removed.
- **MT4:** Legacy assistant fetched → response contains `_format_version: 2` and populated `tools[]`; DB row updated.
- **MT5:** AssistantForm (flag on): add KB + rubric + file tools, save, reload form, all configs persist and placeholders shown.
- **MT6:** Disable one tool → placeholder removed from prompt preview; re-enable restores.
- **MT7:** Validation blocks save when required config missing (no KB selected, no rubric id, empty file path).
- **MT8:** Playwright happy-path for multi-tool create/edit passes.
- **MT9:** Streaming mode: observe markdown status updates per tool (“querying knowledge base {kb}”, “merging contexts”) in order; no secrets leaked.
- **MT10:** `verbose` enabled: logs/response metadata show tool inputs (sanitized), outputs lengths, prompt after substitution; `verbose` off suppresses details.

## Risks & Mitigations
- **Migration correctness:** mitigate with migrate-on-access logging and DB backups; keep legacy columns intact.
- **Placeholder drift:** ensure prompt processor cleans unknown placeholders; add tests for mixed templates.
- **Frontend regressions in AssistantForm:** use feature flag, incremental rollout, and Playwright coverage.
- **KB/Rubric fetch latency:** plugin components cache fetches and show loading/error states; consider debounce for search.

## Open Questions (resolved)
1) Per-tool execution timeouts: YES — configurable via env defaults with fallback.  
2) Parallel execution: Defer to post-MVP, optional flag, limited concurrency.  
3) `/tools/{tool}/validate`: Best-effort only; do not hard-block saves.  
4) Legacy UI: No environments require it permanently; feature flag only for rollout.  
5) Logging: Record output lengths/metadata, never contents.

## Suggested Timeline (conservative)
- Week 1: Phases 1-2 (backend foundations/pipeline)
- Week 2: Phases 3-4 (migration + endpoints) and start Phase 5 (frontend shells)
- Week 3: Phases 6-7 (frontend plugins + integration)
- Week 4: Phases 8-9 (E2E, rollout prep, hardening)

## Sketch Timeline (Gantt-style, week blocks)
- **W1:** Backend tools dir, registry, orchestrator, pipeline integration + timeouts.
- **W2:** Migration-on-access + logs, tool APIs, start frontend shells.
- **W3:** Frontend plugins + AssistantForm integration under flag.
- **W4:** E2E/Playwright, staging rollout, hardening, timeout verification.
- **Post-MVP:** Optional parallel execution flag + load testing.
