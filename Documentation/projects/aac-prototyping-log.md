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
