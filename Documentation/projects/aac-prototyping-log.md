# AAC Agent Prototyping Log

**Status:** In progress
**Started:** 2026-03-28
**Related:** [lamb-agent-assisted-creator.md](./lamb-agent-assisted-creator.md)

---

## Concept

Use Claude Code as a stand-in for the AAC agent, with `lamb-cli` as the tool layer, to empirically validate the AAC design before writing new backend code. This prototyping approach tests real workflows against the live LAMB instance to discover which tools the agent actually needs, what conversation patterns work, and where gaps exist.

## Session 1 — 2026-03-28

### Phase A: Instance Reconnaissance

Surveyed available resources via `lamb-cli`:
- 2 orgs (system + dev), 6 assistants, 5 KBs, 8 rubrics
- Models: gpt-4o-mini, gpt-4o, gpt-5.2, gpt-4.1, grok-4.1-fast
- Pipeline plugins: openai/ollama/bypass connectors, simple_augment PPS, 6 RAG processors

### Findings

**Gap: No CLI access to rubrics.** When inspecting `pestlerubric1` (a rubric-based grading assistant), we couldn't retrieve the rubric it references. This blocked the inspect → understand → test workflow that the AAC agent needs.

**Action taken:**
- Implemented `lamb rubric` commands (list, list-public, get, delete, duplicate, export, import, share, generate) — #323
- Discovered 2 backend bugs: `duplicate` and `visibility` endpoints fail due to missing `LambDatabaseManager` methods — #325
- Discovered rubrics are undocumented in architecture docs — #324

**Key insight for AAC design:** The agent needs read access to all resources an assistant references (rubrics, KBs, templates, org config) to understand what it's working with. The AAC tool set in the design doc lists `get_assistant_state` but that only returns metadata IDs — the agent also needs tools to resolve those IDs into actual content (rubric criteria, KB documents, template text).

## Session 2 — 2026-03-30

### Pastor Prototype (liteshell + agent loop)

Built a standalone prototype ("pastor") to validate the CLI-shaped tool interface concept:

**Liteshell:** A Python module that parses CLI command strings (e.g., `lamb assistant get 4`) and routes them to `LambClient` API calls, returning structured data. No real shell, no subprocess. 20 commands implemented and tested covering assistants, rubrics, KBs, templates, models, analytics, orgs.

**Agent loop:** LLM with tool-use calling the liteshell. Single tool definition (`execute_command`) that accepts CLI strings. Tested with gpt-4.1-mini.

**Skill files:** First skill file `assistant_design.md` drafted — workflow for helping educators design new assistants.

### Architecture Decision: Pastor is a Backend Module

Key decision reached through iterating on the deployment model:

1. **First attempt:** Standalone CLI package (`pastor/`) with its own `OpenAI` client and `LambClient`. Problem: how does it get the org's API key?

2. **Rejected approach:** Add `/creator/provider-config` endpoint to expose API keys. **Security problem** — API keys must never travel over HTTP.

3. **Final architecture:** Pastor runs **inside the LAMB backend** as `backend/lamb/aac/`. It uses `OrganizationConfigResolver` directly for LLM config — API keys stay in-process, never exposed. Frontend and CLI are just clients.

```
Frontend (Svelte)  ──→  /creator/aac/...  ──→  AAC module (backend/lamb/aac/)
lamb-cli (aac)     ──→  /creator/aac/...  ──→       │
                                                OrganizationConfigResolver
                                                     │
                                                OpenAI API (keys stay server-side)
```

**What the liteshell becomes:** Instead of calling `LambClient` (HTTP), the backend liteshell calls LAMB service functions directly (Python imports). Same command parsing, same CLI-shaped interface for the LLM, zero HTTP overhead.

**Testing via lamb-cli:** New `lamb aac` commands (start, message, chat, sessions, history, stats) hit the `/creator/aac/` endpoints. Same pattern as every other lamb-cli command group.

**What we keep from the prototype:**
- Liteshell command parsing and dispatch logic (shell.py)
- Agent loop structure (loop.py)
- Skill file format and loading
- CLI-shaped tool interface concept (proven to work)

**What changes:**
- `pastor/` standalone package → `backend/lamb/aac/` backend module
- `LambClient` HTTP backend → direct Python service calls
- LLM config from env vars/flags → `OrganizationConfigResolver`
- `pastor` CLI → `lamb aac` commands in lamb-cli

### Implementation (2026-03-30)

Built the real AAC module in `backend/lamb/aac/`:

**Backend (`backend/lamb/aac/`):**
- `liteshell/shell.py` — command parser, routes to service layer directly
- `liteshell/commands.py` — 14 handlers (assistant, rubric, kb, template, model, help)
- `agent/loop.py` — async LLM loop with tool calling, integrated session logging
- `session_manager.py` — session CRUD with `aac_sessions` SQLite table
- `session_logger.py` — JSONL file logging per session (configurable via `AAC_SESSION_LOGGING`)
- `router.py` — FastAPI endpoints mounted at `/creator/aac/`
- `skills/assistant_design.md` — first skill file

**CLI (`lamb-cli/src/lamb_cli/commands/aac.py`):**
- `lamb aac start` — create session
- `lamb aac sessions` — list sessions
- `lamb aac get <sid>` — session details
- `lamb aac delete <sid>` — archive session
- `lamb aac message <sid> "text"` — send message, get response
- `lamb aac chat <sid>` — interactive mode
- `lamb aac history <sid>` — show conversation

**Router mounted** in `creator_interface/main.py`.

**Next:** restart backend with Docker, test the full loop via `lamb aac`.
