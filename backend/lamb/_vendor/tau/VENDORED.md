# Vendored: tau core (tau_ai + tau_agent)

| | |
|---|---|
| **Source** | https://github.com/huggingface/tau |
| **Version / commit** | v0.1.5 / `b344d3ebd91d39a16e656fad83da2bd70308f43c` |
| **Vendored on** | 2026-07-16 |
| **License** | MIT (Expat) — see `LICENSE` in this directory. Copyright (c) 2026 Alejandro AO. |
| **Why vendored, not pip** | The published `tau-ai` package declares the full TUI stack (`textual`, `typer`, `rich`) as core dependencies. The two packages taken here need only `httpx` + `pydantic`, both already LAMB dependencies. |

## What is taken — and what is deliberately not

**Taken:** all of `tau_ai/` (provider protocol, typed event stream, retry/backoff,
five adapters + FakeProvider) and `tau_agent/` **minus `session/`** (loop,
harness, events, messages, tools, types).

**Not taken:** `tau_agent/session/` (JSONL session-tree persistence — AAC
sessions live in LAMB's own database) and `tau_coding/` (the terminal app).

## Local modifications (the complete list)

1. **Import rewrite** (mechanical): absolute `tau_ai.*` / `tau_agent.*` imports
   → `lamb._vendor.tau.tau_ai.*` / `lamb._vendor.tau.tau_agent.*`.
2. **Provenance header** (2 comment lines) prepended to every `.py` file.
3. **`tau_agent/__init__.py`:** the `tau_agent.session` re-export block removed
   (see the inline comment there); `__all__` trimmed accordingly.
4. **The usage patch** — the one substantive change. Upstream requests token
   usage from providers (`stream_options.include_usage`) but never parses the
   reply. Added, all sites marked `# LAMB addition`:
   - `tau_ai/events.py`: `TokenUsage` model; `usage: TokenUsage | None` field
     on `ProviderResponseEndEvent`.
   - `tau_ai/openai_compatible.py`: both stream parsers capture usage (the
     Chat Completions final chunk arrives with an empty `choices` list and
     upstream drops it; the Responses API reports it on the terminal event)
     and emit it on the response-end event. Two tolerant extraction helpers.
   - `tau_ai/__init__.py`: `TokenUsage` re-exported.
   - Propagated to loop consumers (Phase 3): `tau_agent/events.py` adds
     `usage: TokenUsage | None` on `MessageEndEvent` (late import + rebuild,
     avoiding an import-order change) and `tau_agent/loop.py` forwards it
     from `ProviderResponseEndEvent`.
   - Offered upstream: intended as a PR to huggingface/tau once proven in the
     multiai connector (plan decision M-6).

## Re-vendor procedure

1. Clone upstream at the new tag; diff `src/tau_ai src/tau_agent` against this
   tree ignoring the header lines and import prefixes.
2. Re-apply modifications 1–3 (mechanical; the sed lines live in the Phase-1
   commit message) and re-apply or rebase modification 4.
3. Update the version/commit/date table above.
4. Run the vendored test suite: `pytest backend/tests/vendor_tau/` (adopted
   from upstream, network-free via FakeProvider and mocked httpx).
5. Check upstream's `tau_agent/__init__.py` for new re-exports and its
   packages for new inter-package imports before assuming the cut still holds.

## Consumers

- Phase 2: `lamb/completions/connectors/multiai.py` (provider layer).
- Phase 3: the AAC agent loop (`lamb/aac/`) via `AgentHarness`/`run_agent_loop`.
