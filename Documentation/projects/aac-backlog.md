# AAC Backlog

**Status:** Active
**Last updated:** 2026-04-02
**Related:** [lamb-agent-assisted-creator.md](./lamb-agent-assisted-creator.md) | [aac-prototyping-log.md](./aac-prototyping-log.md) | Issue #172

---

## Overview

This backlog covers the next implementation phases of the Agent-Assisted Creator (AAC). Items are ordered by dependency. The working prototype (liteshell + agent loop + `lamb aac` CLI) was validated in sessions 1-2 (see prototyping log).

---

## 1. Action Authorization System ✅

**Priority:** High — needed before any production use
**Depends on:** Nothing (foundational)
**Status:** DONE (2026-03-31) — implemented as approach B (chat-native, no special endpoints)

### Problem

Currently the LLM decides via prompting whether to ask the user for confirmation on write operations. This is unreliable — the model sometimes auto-confirms deletes, sometimes double-asks. Authorization must be deterministic, not LLM-dependent.

### Design

**Policy config** — a JSON dict mapping action types to authorization modes:

```json
{
    "assistant.create": "ask",
    "assistant.update": "ask",
    "assistant.delete": "ask",
    "assistant.list": "auto",
    "assistant.get": "auto",
    "rubric.get": "auto"
}
```

Modes:
- `auto` — execute immediately, return result to LLM
- `ask` — pause agent loop, return confirmation request to the CLIENT (not the LLM)
- `never` — return error to LLM, action not allowed

**Key principle:** Confirmation is NOT done by the LLM. The Python layer intercepts write commands, pauses the agent loop, and sends a structured confirmation request to the client. The client (CLI or frontend) handles the UX.

### Agent loop flow change

```
LLM calls tool → liteshell executes command
  ↓
Read command → return data to LLM (always auto)
Write command → Authorizer checks policy:
  → "auto": execute, return result to LLM
  → "ask": PAUSE loop, return {needs_confirmation: true, action: {...}} to CLIENT
            CLIENT displays action + asks user
            User approves → POST /confirm → execute action, resume loop
            User rejects → POST /reject → tell LLM "user declined", resume loop
  → "never": return error to LLM
```

### New endpoints

```
POST /creator/aac/sessions/{id}/confirm   — execute pending action, resume agent
POST /creator/aac/sessions/{id}/reject    — cancel pending action, resume agent
```

### CLI behavior

`lamb aac message` returns `{needs_confirmation: true, ...}`. The CLI displays the action description and prompts the user with y/n. On confirmation, calls `/confirm`. On rejection, calls `/reject`.

### Frontend behavior

Same response. The UI shows a confirmation card/modal with Approve/Reject buttons. Same endpoints.

### Files to create/modify

- `backend/lamb/aac/authorization.py` — `ActionAuthorizer` class, policy config
- `backend/lamb/aac/agent/loop.py` — remove all authorization from system prompt, integrate authorizer
- `backend/lamb/aac/router.py` — add `/confirm` and `/reject` endpoints, handle paused loop state
- `lamb-cli/src/lamb_cli/commands/aac.py` — handle `needs_confirmation` responses in `message` and `chat`

### What this removes

- All "pending action" logic from liteshell commands (they just execute or fail)
- All confirmation-related instructions from the agent system prompt
- The `_pending_action` field on `AgentLoop`

---

## 2. Skill-Driven Sessions ✅

**Priority:** High — core differentiator of AAC
**Depends on:** Item 1 (skills need reliable auth)
**Status:** DONE (2026-03-31) — skill loader, 3 skills, startup actions, language directive, includes with loop prevention

### Problem

Currently the user must know what to ask. An educator doesn't know they should say "help me improve the system prompt" — they need the agent to guide them.

### Design

Skills become **session launchers** with predefined goals, context, and conversation starters. The agent leads the conversation, not the user.

**Skill definition** (`.md` with YAML frontmatter or Python):

```yaml
---
id: improve-assistant
name: Improve Assistant
description: Review and improve an existing assistant's configuration
required_context:
  - assistant_id
optional_context:
  - language
initial_prompt: agent_first   # agent speaks first, not the user
---

# Skill: Improve Assistant

## On launch
1. Load the assistant: `lamb assistant get {assistant_id}`
2. If it uses a rubric, load it: `lamb rubric get {rubric_id}`
3. Check available models: `lamb model list`
4. Analyze the current configuration

## First message to user
Greet the user. Summarize what the assistant does. Present 3 concrete
suggestions for improvement with clear reasoning. Ask which they'd like
to start with.

## Workflow
...
```

### Launching a skill

```bash
# CLI
lamb aac start --skill improve-assistant --assistant 4 --language ca
lamb aac chat <session-id>   # agent speaks first

# Frontend
POST /creator/aac/sessions {"skill": "improve-assistant", "context": {"assistant_id": 4}}
```

### What happens on launch

1. Session created with skill metadata stored
2. System prompt augmented with skill instructions
3. Skill's initial actions run (read assistant, rubric, etc.)
4. Agent generates the FIRST message (analysis + suggestions)
5. User responds to agent's suggestions — agent leads

### Planned skills (initial set)

| Skill ID | Name | Context | Description |
|---|---|---|---|
| `improve-assistant` | Improve Assistant | assistant_id, language | Review config, suggest improvements |
| `create-assistant` | Create New Assistant | language | Guide user through creating from scratch |
| `test-and-evaluate` | Test & Evaluate | assistant_id | Generate tests, run, evaluate, refine (depends on item 4) |
| `explain-assistant` | Explain Configuration | assistant_id | Show what the LLM sees, explain pipeline |

### Files to create/modify

- `backend/lamb/aac/skills/` — skill definitions (one file per skill)
- `backend/lamb/aac/skill_loader.py` — load, validate, and resolve skills
- `backend/lamb/aac/agent/loop.py` — support `agent_first` mode, skill context injection
- `backend/lamb/aac/router.py` — accept `skill` + `context` in session creation
- `lamb-cli/src/lamb_cli/commands/aac.py` — `--skill` and `--assistant` flags on `start`

---

## 3. Frontend UI Scaffolding

**Priority:** Medium — can scaffold early, refine after 1+2 stabilize
**Depends on:** Items 1+2 for full functionality, but basic chat works now

### Design

### Design: Terminal-in-Tabs

The AAC frontend is a **terminal emulator component** embedded as tabs in existing pages. No new routes — sessions open as tabs alongside the current view.

**Tab model:**

```
┌──────────────┬───────────────────┬─────────────────────┬─────┐
│ 📋 Assistant │ 🤖 Improve: pest…│ 🤖 Explain: pest…  │  +  │
├──────────────┴───────────────────┴─────────────────────┴─────┤
│                                                              │
│  > El teu assistent "pestlerubric1" està configurat...       │
│                                                              │
│  $ la primera ▌                                              │
│                                        [☀/🌙]  [End Session]│
└──────────────────────────────────────────────────────────────┘
```

- Each session is a tab with a terminal interface
- Multiple sessions can be open (only one active/visible)
- Tab title = session title (auto-generated: `"Improve: pestlerubric1"`)
- Closing a tab ends the session (with confirmation)
- `+` button opens a skill picker or free-form session
- Tabs persist in browser sessionStorage across page navigation

**Terminal component:**

- Monospaced font, markdown-capable (renders agent responses as formatted text)
- Light/dark mode toggle (or follows system preference)
- Input field at the bottom (terminal prompt style)
- Tool call activity shown as subtle inline indicators
- Auto-scroll with scroll-back

**Session resumption:**

When the user returns to an inactive session tab, the frontend prepends a context note to the next message: `"[System: User returned. Resources may have changed since last interaction.]"` — no new endpoint, just a prefix on the `/message` call.

**Skill buttons:**

Skills are launched from context buttons in existing UI pages:
- Assistant detail/edit form: `[Explain]` `[Improve]` buttons
- Each button creates a session via `POST /creator/aac/sessions` with the skill + context
- The tab opens with the agent's first message already loaded

**Session titles:**

Auto-generated from skill + assistant name at creation time. Stored in `aac_sessions.title` column.

### Components

```
src/lib/components/aac/
├── AacTerminal.svelte        # Terminal emulator (monospaced, markdown, input)
├── AacTabBar.svelte          # Tab bar managing open sessions
├── AacSkillButton.svelte     # Button that launches a skill session
└── AacSessionStore.js        # Svelte store: open tabs, active session, persistence
```

Integration points (modify existing pages):
- Assistant detail page: add skill buttons
- Layout: include tab bar component

### Technology

Svelte 5, JavaScript + JSDoc (NOT TypeScript), TailwindCSS 4. Same stack as existing LAMB frontend. i18n via `svelte-i18n`.

### Implementation order

1. Backend: add `title` to sessions (migration) ✅
2. `AacTerminal.svelte` — the terminal component ✅
3. `AacSessionStore.svelte.js` — session/tab state management ✅
4. `AacTabBar.svelte` — tab bar ✅
5. `AacSkillButton.svelte` — wire into assistant detail page ✅
6. Session resumption context injection
7. Side panel canvas (see §3b below)

### 3b. Side Panel Canvas

**Priority:** High — makes structured content (tables, rubrics, comparisons) usable
**Depends on:** Item 3 base implementation (done)
**Related:** Issue #333

### Problem

The AAC terminal renders everything inline as scrolling text. Tables, rubrics, test comparisons, and structured data get squeezed into the terminal's narrow column and scroll away. The user can't see a rubric table AND the agent's commentary at the same time.

### Design Decision: Option C — Markdown Directives

**Evaluated options:**

| Option | Approach | Verdict |
|--------|----------|---------|
| A. Liteshell command | `lamb canvas show --content "..."` | Rejected: long markdown as command arg is awkward |
| B. Second tool definition | `show_canvas(title, content)` tool | Rejected: changes tool interface, multi-tool model support varies |
| **C. Markdown directives** | `<<<CANVAS>>>...<<<END_CANVAS>>>` in response | **Chosen**: most natural for any LLM |
| D. Hybrid | Commands for control, directives for content | Over-engineered |

**Why Option C wins:**
- LLMs are great at writing markdown — wrapping a table in markers is trivial
- No tool interface changes — agent just writes its response
- Content can be arbitrarily long — no shlex/argument limits
- Any LLM works — no multi-tool support needed
- Streaming-friendly — frontend detects opening marker and starts rendering

### How it works

The agent includes canvas directives in its normal response:

```
Here's the rubric analysis.

<<<CANVAS title="Rubric: PESTLE Analysis">>>
| Criteria | Weight | Excel. (1.5) | Notable (1.25) | Aprovat (0.75) | Suspès (0.25) |
|----------|--------|-------------|----------------|----------------|---------------|
| Political | 13% | Identifies clearly | Identifies generally | Generic | Doesn't identify |
| Economic | 13% | Analyzes costs | Analyzes basic costs | Mentions costs | Doesn't analyze |
<<<END_CANVAS>>>

The political and economic criteria look solid. Want to adjust the weights?

**Next?**
1. Adjust weights
2. Add a criterion
3. Other — tell me
```

The frontend splits the response:
- Text before/after canvas markers → terminal
- Content between markers → side panel (rendered as markdown/HTML)

### Frontend implementation

```
┌──────────────────────────┬──────────────────────────┐
│  AAC Terminal            │  Canvas Panel            │
│                          │                          │
│  Agent text response     │  # Rubric: PESTLE        │
│  goes here...            │  | Criteria | Weight |   │
│                          │  |----------|--------|   │
│  **Next?**               │  | Polit.   | 13%    |   │
│  1. Adjust weights       │  | Econ.    | 13%    |   │
│  2. Add criterion        │                          │
│                          │              [✕ Close]   │
│  $ ▌                     │                          │
└──────────────────────────┴──────────────────────────┘
```

**Components:**

```
src/lib/components/aac/
├── AacCanvas.svelte              # Side panel markdown renderer
└── AacTerminal.svelte            # Modified: detects canvas markers, splits content
```

**Terminal layout change:** When canvas content is present, the terminal shrinks to ~60% width and the canvas takes ~40%. When canvas is closed, terminal goes back to full width.

**Canvas behavior:**
- Persists until the agent sends new canvas content (replaces) or `<<<CANVAS_CLEAR>>>` marker
- User can close it manually (✕ button) — terminal goes full width
- Canvas title shown as a header
- Content rendered as markdown → HTML (using `marked`)

### System prompt addition

```
When presenting tables, comparisons, rubrics, or structured data that benefits
from a wider view, wrap it in canvas markers:

<<<CANVAS title="Your Title">>>
(markdown content — tables, lists, code blocks, etc.)
<<<END_CANVAS>>>

The content appears in a side panel next to the terminal. Keep your terminal
response brief — just reference what's in the canvas. The user sees both
simultaneously. Use <<<CANVAS_CLEAR>>> to dismiss the panel.
```

### Parsing logic (frontend)

```javascript
function splitCanvasContent(text) {
    const match = text.match(/<<<CANVAS(?:\s+title="([^"]*)")?>>>([\s\S]*?)<<<END_CANVAS>>>/);
    if (!match) return { text, canvas: null };
    const title = match[1] || '';
    const canvasContent = match[2].trim();
    const cleanText = text.replace(/<<<CANVAS[\s\S]*?<<<END_CANVAS>>>/, '').trim();
    return { text: cleanText, canvas: { title, content: canvasContent } };
}
```

### Implementation order

1. Add `splitCanvasContent()` parser to `AacTerminal.svelte`
2. Create `AacCanvas.svelte` (markdown renderer with title + close button)
3. Modify terminal layout: flex container that shows canvas when content exists
4. Add canvas instructions to system prompt
5. Test with rubric tables, test result comparisons

---

## 4. Assistant Test Prompts & Evaluation ✅

**Priority:** High — independent LAMB feature, can parallel with item 2
**Depends on:** Nothing (standalone feature). AAC skill depends on this.
**Related:** Issue #172 (EVALS), AAC design doc §2.3, Issue #327
**Status:** DONE (2026-03-31) — scenarios CRUD, test runner (real pipeline), evaluation, debug bypass

### Problem

Educators have no structured way to test their assistants with realistic prompts, evaluate responses, and iterate. Issue #172 identified this as a prerequisite before adding more assistant sophistication.

### Design

New LAMB feature (not AAC-specific) — every assistant can have a set of **test scenarios**.

**Data model:**

```sql
-- Test scenarios for an assistant (what to test)
CREATE TABLE assistant_test_scenarios (
    id TEXT PRIMARY KEY,
    assistant_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    scenario_type TEXT DEFAULT 'single_turn',  -- single_turn | multi_turn | adversarial
    messages TEXT NOT NULL,                     -- JSON: input messages to send
    expected_behavior TEXT,                     -- free-text: what good looks like
    tags TEXT,                                  -- JSON: categorization tags
    created_by TEXT NOT NULL,                   -- user email or 'aac_agent'
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Test run results (what happened)
CREATE TABLE assistant_test_runs (
    id TEXT PRIMARY KEY,
    assistant_id INTEGER NOT NULL,
    scenario_id TEXT,                           -- NULL if ad-hoc
    input_messages TEXT NOT NULL,               -- JSON
    output TEXT NOT NULL,                       -- JSON: full response
    token_usage TEXT,                           -- JSON: {prompt, completion, total}
    assistant_snapshot TEXT,                    -- JSON: config at test time
    model_used TEXT,
    created_at TIMESTAMP
);

-- Evaluations (was it good?)
CREATE TABLE assistant_test_evaluations (
    id TEXT PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    evaluator TEXT NOT NULL,                    -- 'user' | 'aac_agent'
    verdict TEXT,                               -- 'good' | 'bad' | 'mixed'
    notes TEXT,
    dimensions TEXT,                            -- JSON: optional structured scoring
    confirmed_by_user BOOLEAN,                 -- for agent evaluations
    created_at TIMESTAMP
);
```

### API endpoints

```
# Scenarios (CRUD)
POST   /creator/assistant/{id}/test-scenarios
GET    /creator/assistant/{id}/test-scenarios
PUT    /creator/assistant/{id}/test-scenarios/{sid}
DELETE /creator/assistant/{id}/test-scenarios/{sid}

# Execution
POST   /creator/assistant/{id}/test-scenarios/run       — run all/selected scenarios
POST   /creator/assistant/{id}/test-scenarios/{sid}/run  — run single scenario

# Results
GET    /creator/assistant/{id}/test-runs
GET    /creator/assistant/{id}/test-runs/{rid}

# Evaluation
POST   /creator/assistant/{id}/test-runs/{rid}/evaluate
GET    /creator/assistant/{id}/test-evaluations
```

### CLI commands

```
lamb test
  scenarios <assistant-id>           List test scenarios
  add <assistant-id> <title>         Add a test scenario
  run <assistant-id>                 Run all scenarios
  runs <assistant-id>                List test runs
  evaluate <run-id>                  Submit evaluation
```

### Test runner

Executes test scenarios through the **real completion pipeline** (same code path as production). This means real tokens, real RAG, real prompt processing. Token usage tracked per run.

### AAC skill: `test-and-evaluate`

Once this feature exists, the AAC agent gets a skill that leverages it:

1. Reads the assistant's purpose, system prompt, and rubric
2. **Generates** test scenarios: happy path, edge cases, adversarial, rubric-coverage
3. Runs them via the test runner
4. Presents results to the educator
5. Educator evaluates (good/bad/notes)
6. Agent analyzes evaluation patterns and suggests prompt/config improvements
7. Loop: refine → test → evaluate → refine

This is the design-test-evaluate cycle from AAC design doc §2.3.

### Research value

Every test run + evaluation produces structured data for the research lines in `phd-research-lines-aac.md`:
- What test patterns reveal problems?
- How many iterations to reach "good"?
- Token cost of testing vs. production use?
- Can agent-generated evaluations match human judgments?

---

## Dependency Graph

```
[1] Authorization System     ← foundational, do first
        ↓
[2] Skill-Driven Sessions    ← needs reliable auth
        ↓
[3] Frontend UI              ← needs 1+2 to be useful

[4] Test Prompts & Eval      ← independent, can parallel with 2
        ↓
    AAC skill: test-and-evaluate  ← needs 2+4
```

## Implementation Order

| Phase | Items | Scope | Status |
|---|---|---|---|
| ~~Done~~ | 1 | Authorization system (approach B: chat-native) | ✅ 2026-03-31 |
| ~~Done~~ | 4 | Test scenarios, runner, evaluation, debug bypass | ✅ 2026-03-31 |
| ~~Done~~ | 2 | Skill-driven sessions (agent leads, context-aware launch) | ✅ 2026-03-31 |
| ~~Done~~ | 3 | Frontend UI scaffold (terminal, streaming, tabs, tests tab) | ✅ 2026-04-02 |
| ~~Done~~ | 2+4 | `test-and-evaluate` skill | ✅ 2026-04-01 |
| ~~Done~~ | 5 | CLI partial update bug (fetch-and-merge) | ✅ 2026-04-01 #328 |
| ~~Done~~ | 6 | Skills: bypass-first workflow (agent follows naturally) | ✅ 2026-04-02 |
| ~~Done~~ | 7 | Comparative testing: CLI vs AAC agent (same 5 scenarios) | ✅ 2026-04-02 |
| ~~Done~~ | 8 | Tests tab in UI + `test-and-evaluate` skill | ✅ 2026-04-01 |
| ~~Done~~ | #329 | simple_augment: clean text extraction instead of JSON dump | ✅ 2026-04-02 |
| ~~Done~~ | #330 | RAG processors: read `results` key from KB server response | ✅ 2026-04-02 |
| ~~Done~~ | 13 | LAMB user manual on website (EN + ES) with 14 UI screenshots | ✅ 2026-04-03 |
| ~~Done~~ | 14a+b | Agent-readable docs (`lamb/aac/docs/`) + `docs.index`/`docs.read` tools | ✅ 2026-04-03 |
| ~~Done~~ | 16 | Liteshell HTTP refactoring — async ASGI transport via Creator Interface | ✅ 2026-04-03 |
| ~~Done~~ | 14c | `about-lamb` skill — reactive platform helper grounded in docs | ✅ 2026-04-03 |
| ~~Done~~ | 15 | LAMB Agent top-level page + dashboard card + nav link | ✅ 2026-04-03 |
| ~~Done~~ | 17 | Remove student anonymization from LTI dashboard #332 | ✅ 2026-04-05 |
| **Partial** | 19 | AAC bugs: 19a ✅ prompt templates, 19c ✅ skill switching, 19b merged into 21 | |
| **In Progress** | 21 | Unified AAC session management (+ merged 9c, 19b): A→B→C→D phases | |
| ~~Done~~ | 22 | Liteshell update merge + metadata defaults on create AND update | ✅ 2026-04-06 |
| **Next** | 24 | Terminal toggle: show/hide tool call details inline | |
| **Next** | 23 | Creator Interface endpoint hardening — server-side validation audit #335 | |
| **Next** | 20 | Missing liteshell commands — publish, KB query, templates, analytics, chat context | |
| **Then** | 18 | AAC terminal file upload widget — attach files to agent conversations | |
| **Next** | 12 | Liteshell comprehensive test suite (26 commands, reuse CLI E2E tests) | |
| **Merged→21** | 9c | Agent History UI — merged into item 21 unified design | |
| ~~Done~~ | 3b | Side Panel Canvas — markdown directives in agent response #333 | ✅ 2026-04-06 |
| ~~Done~~ | 10 | `lamb_aac_cli_manual.md` v0.3 — CLI + web UI + architecture manual | ✅ 2026-04-03 |
| ~~Done~~ | 11 | `assistant.list-shared` + get by name (26 liteshell commands) | ✅ 2026-04-03 |
| **On merge** | | #329 + #330 included in pastor — will land on dev when pastor merges | |

---

## 5. CLI Partial Update Bug — Fetch-and-Merge

**Priority:** High — affects CLI and liteshell, blocks reliable assistant editing
**Depends on:** Nothing (standalone fix)

### Problem

`lamb assistant update` (and the liteshell `assistant.update` command) wipe fields not included in the request. The backend's `prepare_assistant_body` defaults missing fields to empty strings — this is correct for `create` but destructive for `update`.

Example: `lamb assistant update 14 --rag-processor simple_rag` clears `system_prompt`, `prompt_template`, `RAG_collections`, and everything else not explicitly passed.

**Not a frontend bug** — the web UI always sends all fields. But the CLI and liteshell send only changed fields, which triggers the wipe.

### Fix

Two options (choose one):

**A. Fix in the backend** (`prepare_assistant_body` or `update_assistant_proxy`): On update, fetch the current assistant and merge — only override fields present in the request body.

**B. Fix in the CLI and liteshell**: Before sending an update, fetch the current assistant and fill in all unspecified fields from current values. (The CLI already does this for metadata but not for top-level fields like `system_prompt`, `prompt_template`, `RAG_collections`.)

Option A is better — it fixes the problem for any client, not just ours.

### Also fix

- **`assistant create` missing flags**: Add `--rag-collections` and `--prompt-template` to the CLI create command.
- **Double name prefix on update**: The update path re-applies the `{user_id}_` prefix to names that already have it.

---

## 6. Skills: Enforce Bypass-First Testing Workflow

**Priority:** High — prevents wasted tokens on broken pipelines
**Depends on:** Item 5 (skills need reliable updates to fix issues they find)

### Problem

During real testing (2026-04-01), the AAC agent ran real LLM completions on an assistant whose RAG pipeline was silently broken (no prompt template → empty context). The results looked good because gpt-4o-mini answered from training data, masking the RAG failure.

### What the skills should enforce

1. **Bypass first, always.** When testing an assistant, the skill MUST run `lamb assistant debug` or `lamb test run --bypass` BEFORE real completions. No exceptions.
2. **Check the bypass output.** The skill must verify:
   - Is `{context}` populated? If empty → RAG is broken, stop.
   - Does the retrieved content look like actual text? If it's mostly markdown formatting, YouTube embeds, or metadata → warn about chunk quality.
   - Is the prompt template correct? Are `{context}` and `{user_input}` present?
3. **Only then run real completions.** And when presenting results, distinguish between RAG-grounded answers and training-data answers.

### Skills to update

- `improve_assistant.md` — testing workflow section (partially done, needs enforcement language)
- `create_assistant.md` — must set prompt template with `{context}` and `{user_input}` when RAG is enabled, then verify with bypass

---

## 7. Comparative Testing: Same Cases via CLI and AAC Agent

**Priority:** Medium — validates that the AAC agent produces the same results as direct CLI usage
**Depends on:** Items 5 and 6

### Problem

During prototyping, we tested via the CLI (directly running `lamb test run`, `lamb chat --bypass`) and separately via the AAC agent. But we never ran the **exact same test cases** through both paths to compare:

- Does the agent use the correct commands?
- Does it run bypass first?
- Does it correctly interpret bypass output (detect RAG failures)?
- Does it present results accurately?
- Do real completion results match between direct CLI and agent-mediated runs?

### Test plan

Design a fixed test script with 5 scenarios for a RAG-enabled assistant:

1. Run all 5 via `lamb test run <id>` (direct CLI) — record results
2. Run all 5 via AAC agent session — record agent's commands and presented results
3. Compare: command accuracy, result fidelity, bypass interpretation, improvement suggestions

This validates that the agent is a reliable proxy for direct CLI usage.

### Deliverable

A comparison report documenting any discrepancies between the two paths.

---

### Findings from real testing (2026-04-01)

Source: `aac_test_log.md` in repo root

| Finding | Category | Severity |
|---|---|---|
| `assistant update` wipes unspecified fields | CLI bug | High |
| No `--rag-collections` in `assistant create` | CLI missing feature | Medium |
| Double name prefix on update | CLI/backend bug | Medium |
| RAG with no prompt template = silent failure | Skill gap | High |
| Agent ran real completions before verifying RAG | Skill gap | High |
| chunk_size=200 produces garbage retrieval | KB ingestion config | Medium |
| CLI and AAC agent not tested on same cases | Testing gap | Medium |

---

## 9. Session Audit Log + Agent History UI

**Priority:** High — essential for research, transparency, and user trust
**Depends on:** Items 1-4 (core AAC working)

### Problem

AAC sessions currently log to JSONL files (for research) and store conversation in the DB (for session continuity). But there's no structured, queryable record of **what the agent actually did** — which tools it called, what it changed, and what artifacts it affected. The user has no way to review past sessions or understand the agent's actions across time.

### 9a. Structured Tool Use Audit (Backend)

Every tool call during an AAC session gets recorded as a structured event in the session envelope (same blob as conversation, pending_action, skill_info). No new DB table.

**Data per event:**
```json
{
    "ts": "2026-04-02T13:04:12.345Z",
    "command": "lamb assistant get 17",
    "action_key": "assistant.get",
    "intent": "Reading assistant config",
    "success": true,
    "elapsed_ms": 42,
    "artifacts": [{"type": "assistant", "id": "17", "action": "read"}]
}
```

**Implementation:**
- `AgentLoop`: new `tool_audit: list[dict]` field, recorded in `_execute_tool()`
- Intent from `_TOOL_LABELS` (deterministic, no LLM cooperation needed)
- Artifacts extracted by parsing command string + result (resource type, ID, action)
- `_extract_artifacts()`: maps subcommands to actions (get→read, create→create, run→test, etc.)
- Persisted in session envelope via `update_conversation(..., tool_audit=agent.tool_audit)`
- Restored on session rebuild, accumulates across turns
- Also written to JSONL session log
- No new endpoints — `GET /sessions/{id}` returns `tool_audit` for free

### 9b. CLI: Query Session Tool Uses

```
lamb aac history <session-id>                    # conversation (existing)
lamb aac tools <session-id>                      # tool use audit log
lamb aac tools <session-id> --artifacts          # group by affected artifact
lamb aac tools <session-id> --filter assistant   # filter by artifact type
lamb aac sessions --with-stats                   # list sessions with tool counts
```

### 9c. Frontend: Agent History Page

A new top-level page/tab **"Agent"** in the navigation, alongside Assistants, Knowledge Bases, etc.

```
┌──────────────────────────────────────────────────────────────┐
│  Assistants  │  Knowledge Bases  │  Agent  │  Admin          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Your Agent Sessions                                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 🤖 Improve: rock_the_60s          2026-04-02  12 tools │  │
│  │    Artifacts: assistant:17 (read, test), rubric (read)  │  │
│  │    Status: active                            [Resume]   │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ 🤖 Test & Evaluate: pestlerubric1  2026-04-01  8 tools │  │
│  │    Artifacts: assistant:4 (read, test), rubric (read)   │  │
│  │    Status: completed                          [Review]  │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ 🤖 Create New Assistant            2026-04-01  5 tools │  │
│  │    Artifacts: assistant:13 (create)                     │  │
│  │    Status: completed                          [Review]  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Click a session to see full conversation + tool audit log   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Session detail view:**
- Full conversation (same as the terminal but read-only for completed sessions)
- Tool audit timeline: chronological list of tool calls with intent, outcome, and affected artifacts
- Summary: total tools, artifacts touched, time spent, tokens used

**Resume vs Review:**
- Active sessions: "Resume" opens the terminal and continues the conversation
- Completed sessions: "Review" shows read-only conversation + audit log

### Implementation

**Backend:**
- Extend `AgentLoop._execute_tool()` to record structured events
- Add `tool_audit` array to session envelope (same as pending_action/skill_info)
- Extract artifact info from command strings (parser already exists in liteshell)
- Record intent from the LLM's tool_call arguments or preceding message

**CLI:**
- New `lamb aac tools` command
- Extend `lamb aac sessions` with `--with-stats`

**Frontend:**
- New route: `/agent` (or `/aac`)
- Components: `AgentSessionList.svelte`, `AgentSessionDetail.svelte`, `ToolAuditTimeline.svelte`
- Read-only terminal for reviewing completed sessions

---

## 8. Tests Tab in UI + `test-and-evaluate` Skill

**Priority:** High — makes test scenarios visible and actionable for educators
**Depends on:** Item 3 (frontend scaffold), Item 6 (bypass-first workflow)
**Related:** Item 4 (test framework backend — already done), #172 (EVALS)

### 8a. Tests Tab on Assistant Detail Page

A new **Tests** tab alongside Properties, Edit, Share, Chat, Activity.

**What the educator sees:**

```
┌────────────┬──────┬───────┬──────┬──────────┬───────┐
│ Properties │ Edit │ Share │ Chat │ Activity │ Tests │
├────────────┴──────┴───────┴──────┴──────────┴───────┤
│                                                      │
│  Test Scenarios (3)                        [+ Add]   │
│  ┌────────────────────────────────────────────────┐  │
│  │ ✓ Beatles influence      normal     good       │  │
│  │ ✗ Blues roots             normal     bad        │  │
│  │ ? Jazz edge case          edge       not eval   │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  [▶ Run All]  [🔍 Debug All (bypass)]               │
│                                                      │
│  Latest Runs                                         │
│  ┌────────────────────────────────────────────────┐  │
│  │ Run #1  2026-04-01  gpt-4o-mini  2290 tok  8s │  │
│  │  → "The Beatles had a profound influence..."   │  │
│  │  Eval: 👍 good                                │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  [🤖 Test & Evaluate with Agent]                    │
└──────────────────────────────────────────────────────┘
```

**Features:**
- Scenarios list with add/edit/delete
- Run controls: "Run All" (real LLM) and "Debug All" (bypass, zero tokens)
- Run single scenario (real or bypass)
- Results view with response preview, token count, time
- Bypass results show the constructed context (what the LLM sees)
- Inline evaluation: thumbs up/down/mixed + optional notes
- "Test & Evaluate with Agent" button launches the AAC skill

**No new backend needed** — all API endpoints exist at `/creator/assistant/{id}/tests/`.

**Frontend components:**

```
src/lib/components/aac/
├── AssistantTests.svelte         # Main tests tab
├── TestScenarioList.svelte       # Scenarios CRUD
├── TestRunResults.svelte         # Results with bypass/real distinction
├── TestEvaluationBadge.svelte    # Inline verdict badge
└── TestRunDetailModal.svelte     # Full run detail modal

src/lib/services/
└── testService.js                # API client for test endpoints
```

### 8b. `test-and-evaluate` Skill

A dedicated AAC skill for test-driven assistant improvement.

**Skill definition:** `backend/lamb/aac/skills/test_and_evaluate.md`

```yaml
---
id: test-and-evaluate
name: Test & Evaluate
description: Generate tests, run them, evaluate results, suggest improvements
required_context: [assistant_id]
optional_context: [language]
startup_actions:
  - "lamb assistant get {assistant_id}"
  - "lamb test scenarios {assistant_id}"
---
```

**Workflow (agent-led):**

The skill has three phases, each a subskill:

**Phase 1 — Generate test scenarios:**
- Analyze the assistant's purpose, system prompt, RAG config, and rubric (if any)
- Propose a test set: 3-5 normal scenarios covering the core use case, 1-2 edge cases (related but off-center topics), 1 adversarial (prompt injection, off-topic)
- For each scenario: title, message, expected behavior, type
- Present to user for approval, then create via `lamb test add`
- If scenarios already exist, offer to review/extend them instead of starting fresh

**Phase 2 — Run and analyze:**
- **Always bypass first**: run `lamb test run <id> --bypass` to verify the pipeline
  - Check: is `{context}` populated? Is it actual text content?
  - If RAG is broken → stop, diagnose, suggest fixes
  - If RAG looks good → proceed
- **Then real completions**: run `lamb test run <id>` with actual LLM
- Present results in ASCII chat tables
- For each result, give the agent's preliminary assessment

**Phase 3 — Evaluate and improve:**
- Ask the user to evaluate each result (good/bad/mixed)
- Record evaluations via `lamb test evaluate`
- Analyze patterns: which scenarios failed? Why?
- Suggest concrete improvements:
  - System prompt adjustments
  - Model upgrade/downgrade
  - RAG configuration changes
  - Prompt template refinement
- If user approves a change, apply it and offer to re-run the tests

**The cycle:** Generate → Debug → Run → Evaluate → Improve → Re-run

**Integration with Tests tab:** The skill operates on the same test scenarios visible in the Tests tab. Scenarios created by the agent appear in the tab. Evaluations recorded in the tab are visible to the agent. They're the same data.

### Subskills within `test-and-evaluate`

The skill file uses markdown sections for conditional logic:

```markdown
## If no test scenarios exist
Generate a test set based on the assistant's purpose...

## If test scenarios exist but have never been run
Offer to run them (bypass first, then real)...

## If test scenarios exist and have runs but no evaluations
Present the results and ask for evaluations...

## If test scenarios have evaluations
Analyze patterns, suggest improvements, offer to re-run...
```

This means the skill adapts to whatever state the tests are in — whether the user is starting from scratch or picking up where they left off.

---

## 10. AAC CLI & Architecture Manual

**Priority:** Medium — documentation debt, needed before onboarding others
**Depends on:** Items 1-9 (documents what exists)

Full manual covering:

**CLI reference:** Every `lamb aac` and `lamb test` command with examples, flags, output formats.

**Architecture:** How the pieces fit together — liteshell, agent loop, authorization, skills, streaming, session management, tool audit. Enough for a developer to understand and extend the system.

**Skills reference:** How to write skills (frontmatter, startup actions, subskills, includes, language directive). How the agent uses them.

**Testing workflows:** bypass-first pattern, test scenarios lifecycle, evaluation recording, the design-test-evaluate cycle.

**Configuration:** Env vars (AAC_SESSION_LOGGING, AAC_LOG_PATH), authorization policy, org config resolution.

**Troubleshooting:** Common issues (RAG empty context, skill not triggering, double confirmation, streaming not working).

**File:** `Documentation/lamb_aac_cli_manual.md`

---

## 11. CLI: Shared Assistants Visibility + Get by Name

**Priority:** Medium — usability gap discovered during manual writing
**Depends on:** Nothing

### Problem

- `lamb assistant list` only shows assistants owned by the current user. No way to see assistants shared with you.
- `lamb assistant get` requires the numeric ID. No way to get by name.
- The backend supports shared access via `can_access_assistant()`, but the list endpoint only queries by owner.

### Fix

- Add `lamb assistant list-shared` — list assistants shared with you (not owned, but accessible)
- Add `lamb assistant get` by name — look up by name instead of ID
- The backend endpoint `get_assistants_proxy` needs a mode that includes shared assistants, or a new endpoint

### Get by name syntax

Currently: `lamb assistant get 18` (numeric ID only)

Proposed: detect if the argument is a number or a name:

```bash
lamb assistant get 18                        # by ID (current behavior)
lamb assistant get rock_the_60s              # by name (new — search by exact name)
lamb assistant get "1960s british rock"      # by name with spaces
```

Implementation: if the argument is not a pure integer, treat it as a name. Query the backend by name (needs a new endpoint or query param on `get_assistants`). If multiple matches (unlikely since names are unique per owner), return the first or error.

This also benefits the AAC skills — `lamb assistant get rock_the_60s` is more readable in tool audit logs than `lamb assistant get 18`.

---

## 12. Liteshell Comprehensive Test Suite

**Priority:** High — the AAC agent is only as reliable as its toolset
**Depends on:** Nothing (tests what already exists)
**Related:** Item 7 (comparative testing), lamb-cli docs

### Problem

The liteshell is the AAC agent's only interface to the LAMB platform — 24 commands across 7 categories (assistant, rubric, kb, template, model, test, utility). These commands call the service layer directly (no HTTP), bypassing the creator interface validation that the real CLI goes through. We have no systematic test coverage verifying that:

1. Every command parses arguments correctly (positional + kwargs)
2. Every command calls the right service function with the right parameters
3. Return values are structured consistently (the agent parses these)
4. Error cases produce useful messages (the agent needs to recover)
5. Commands behave equivalently to their lamb-cli counterparts where overlap exists

If a liteshell command silently returns wrong data or crashes on an edge case, the agent gives bad advice to educators.

### Scope — What to Test

The liteshell currently has 24 registered commands:

| Category | Commands | Notes |
|----------|----------|-------|
| **Assistant** (8) | `list`, `get`, `config`, `debug`, `create`, `update`, `delete` | Core CRUD + config discovery. `create` and `update` have complex metadata handling. `debug` calls TestService with bypass. |
| **Rubric** (4) | `list`, `list-public`, `get`, `export` | Export has format flag (json/md). |
| **KB** (2) | `list`, `get` | Read-only. Access check on `get`. |
| **Template** (2) | `list`, `get` | Read-only. |
| **Model** (1) | `list` | Reads org config. |
| **Test** (6) | `scenarios`, `add`, `run`, `runs`, `run-detail`, `evaluate` | `run` is async and handles both single/all scenarios. `add` has many optional flags. |
| **Utility** (1) | `help` | Returns command registry. |

### Test Categories

#### A. Argument Parsing Tests (unit, no services)
Test the `shlex.split()` → handler dispatch for each command:
- Positional arguments in correct order
- `--flag value` and `--flag=value` both work
- Short flags (`-m`, `-d`, `-t`, etc.)
- Boolean flags (`--bypass`, `-b`) set to True
- Missing required arguments → clear error
- Extra/unknown arguments → handled gracefully
- Quoted strings with spaces (`--system-prompt "long text with spaces"`)
- Special characters in values (quotes, newlines, unicode)

#### B. Command Execution Tests (integration, mocked services)
For each command, mock the service layer and verify:
- Correct service function called
- Arguments passed correctly (types, defaults)
- Return value structure matches what the agent expects
- `CommandContext` (user_email, org_id, user_id) threaded correctly

Key scenarios per command group:

**Assistant commands:**
- `assistant.create` — verify metadata dict construction (llm, connector, prompt_processor, rag_processor, rubric_id, rubric_format packed correctly)
- `assistant.create` — name sanitization with user prefix
- `assistant.create` — duplicate name detection via `check_exists` callback
- `assistant.update` — fetch-then-merge: only changed fields overwritten
- `assistant.update` — metadata merge (existing metadata preserved when not overriding)
- `assistant.delete` — calls `soft_delete_assistant_by_id`
- `assistant.config` — plugin loading, connector → LLM mapping, defaults
- `assistant.debug` — creates bypass run via TestService

**Test commands:**
- `test.add` — all flag combinations (title positional vs --title, --type, --expected, --description)
- `test.run` — single scenario vs all scenarios dispatch
- `test.run --bypass` — debug_bypass flag forwarded
- `test.run` — async handling (event loop detection)
- `test.evaluate` — verdict validation (good/bad/mixed only)

**Rubric commands:**
- `rubric.export --format json` vs `--format md` — different service calls
- `rubric.get` — access control (user_email passed)

**KB commands:**
- `kb.get` — access check (`user_can_access_kb`) before returning data

#### C. CLI Parity Tests (comparison)
For commands that exist in both liteshell and lamb-cli, verify equivalent behavior:
- Same input → same logical output (structure may differ since liteshell returns dicts, CLI formats for terminal)
- Same error conditions → same error semantics
- Commands to compare: `assistant.list/get/create/update/delete`, `rubric.list/get/export`, `kb.list/get`, `template.list/get`, `model.list`, `test.*`

#### D. Agent Integration Tests (end-to-end)
Test the liteshell through the `LiteShell.execute()` interface (the entry point the agent loop uses):
- Command string → parsed → dispatched → result returned
- Unknown command → error dict with available commands
- Service exception → error dict with message (not Python traceback)
- Result format is JSON-serializable (agent receives it as tool output)

### Coverage Gaps to Investigate

While building the test suite, document any gaps found:

1. **Commands the real CLI has but liteshell doesn't** — are any needed for skills?
   - Known missing: `chat` (interactive), `analytics.*`, `org.*`, `user.*`, `kb.create/update/delete/upload/query`, `template.create/update/delete`
   - Assess: does any skill need these? Should we add them?
2. **Liteshell-specific behaviors** — things the liteshell does that the CLI doesn't:
   - `assistant.create` name sanitization (adds user prefix)
   - `assistant.update` fetch-and-merge (CLI fixed in #328, liteshell has its own impl)
   - `assistant.config` loads plugins directly instead of hitting `/creator/assistant/config`
3. **Return value contracts** — document what each command returns so skills/agent can rely on it

### Implementation

**Test file:** `backend/tests/aac/test_liteshell_commands.py`

**Framework:** pytest with service mocking (unittest.mock or pytest-mock). No running server needed.

**Fixtures:**
- `mock_context` — `CommandContext(user_email="admin@owi.com", organization_id="org1", user_id="1")`
- `shell` — `LiteShell()` instance
- Service mocks for `AssistantService`, `TestService`, `rubric_service`, `LambDatabaseManager`, `OrganizationConfigResolver`

**Estimated scope:** ~80-100 test cases across the 24 commands.

### Deliverables

1. `backend/tests/aac/test_liteshell_commands.py` — comprehensive test file
2. Gap analysis document: commands missing from liteshell that skills might need
3. Return value contract documentation (can go in the AAC manual, item 10)

---

## 13. LAMB User Manual on Project Website ✅

**Priority:** Medium — user-facing documentation
**Depends on:** Nothing
**Status:** DONE (2026-04-03)

### What was done

Created a comprehensive LAMB User Manual targeting the teacher/creator persona. Published on the project Hugo website at [lamb-project.org](https://lamb-project.org).

**Content:** 11 sections covering the full educator workflow — login, dashboard, assistants (create/edit/share/test/publish), knowledge bases (RAG), rubrics (EvaluAItor), prompt templates, testing (debug bypass + scenarios), activity analytics, LMS publishing (LTI), collaboration, tips & best practices, glossary.

**Screenshots:** 14 UI screenshots captured from a live LAMB instance using Playwright MCP:
01-login, 02-dashboard, 03-assistants-list, 04-create-assistant, 05-assistant-detail, 06-assistant-edit, 07-assistant-share, 08-assistant-tests, 09-assistant-activity, 10-knowledge-bases, 11-kb-detail, 12-rubrics, 13-assistant-published, 14-prompt-templates.

**Languages:** English + Spanish (Spanish reuses English UI screenshots for now).

**Hugo structure:** Page bundle at `content/{en,es}/manual/index.md` with colocated images.

**Repository:** [Lamb-Project/Lamb-Project-Website](https://github.com/Lamb-Project/Lamb-Project-Website), commits `a08308c` (EN) and `aa89d27` (ES).

---

## 14. `about-lamb` AAC Skill + Agent-Readable Documentation + Liteshell Tools

**Priority:** High — foundational for user onboarding and self-service help
**Depends on:** Item 13 (documentation content exists), existing skill infrastructure
**Related:** Item 10 (AAC manual), LAMB user manual on website

### Problem

The AAC agent currently knows how to manipulate assistants (create, improve, test, explain) but **cannot answer questions about the LAMB platform itself**. When an educator asks "how do I connect a knowledge base?" or "what is RAG?" or "how does publishing work?", the agent has no documentation to draw from — it either guesses from its training data or says it doesn't know.

This is a critical gap for onboarding: the first thing a new educator asks is "what can I do here?" not "improve my assistant."

### Design

Three components working together:

#### 14a. Agent-Readable Documentation (`backend/static/aac_docs/`)

A copy of the LAMB user manual optimized for agent consumption, stored server-side where the liteshell can read it. NOT a raw copy of the website markdown — restructured for efficient agent retrieval.

**Location:** `backend/static/aac_docs/`

**Structure:**
```
backend/static/aac_docs/
├── index.md                    # Table of contents with section summaries
├── getting-started.md          # Login, dashboard, navigation
├── assistants.md               # Creating, editing, configuring assistants
├── knowledge-bases.md          # RAG concept, KB management, connecting to assistants
├── rubrics.md                  # EvaluAItor, creating rubrics, rubric-based assistants
├── prompt-templates.md         # Templates management and usage
├── testing.md                  # Direct chat, bypass/debug, test scenarios
├── publishing.md               # LTI publishing, Moodle integration, Unified LTI
├── collaboration.md            # Sharing assistants, KBs, templates
├── troubleshooting.md          # Common issues and solutions
├── glossary.md                 # Term definitions
└── images/                     # Key screenshots (subset, not all 14)
    ├── dashboard.png
    ├── create-assistant.png
    ├── assistant-edit-rag.png
    ├── kb-detail.png
    └── tests-tab.png
```

**Agent optimization strategy:**

The website manual is written for humans reading top-to-bottom. Agent docs need a different structure:

1. **Index-first architecture.** `index.md` has a structured table of contents with one-line summaries per section and per subsection. The agent reads the index first, then fetches only the relevant section. This avoids loading 500+ lines when the user asks about one topic.

2. **Chunked by topic, not by flow.** Each file covers one self-contained topic. A human manual says "after creating the assistant, go to Knowledge Bases"; agent docs have each as a standalone file with cross-references.

3. **Front matter with semantic tags.** Each file has YAML front matter with:
   ```yaml
   ---
   topic: knowledge-bases
   covers: [rag, documents, upload, ingestion, query, sharing, chunking, embeddings]
   answers: [
     "how do I add documents",
     "what is RAG",
     "why is my assistant not using my documents",
     "how to connect a KB to an assistant"
   ]
   ---
   ```
   The `answers` field lists common questions this doc answers. The agent (or the index tool) can use these to route queries.

4. **Imperative, task-oriented paragraphs.** Instead of "The Share tab lets you grant other educators access", write "To share an assistant: click Share tab > Manage Shared Users > select users. Shared users can view and chat but cannot edit or publish."

5. **No decorative content.** Remove motivational text, redundant screenshots descriptions, "here is an example" phrasing. Keep only: what it is, how to do it, what to watch out for.

6. **Troubleshooting section.** A dedicated file with problem → cause → fix triples. This is what users actually ask the agent about:
   - "My assistant ignores my documents" → RAG not configured / no prompt template / wrong KB selected
   - "Context is empty in bypass" → KB not ingested / wrong collection ID / prompt template missing `{context}`
   - "I can't see the Share tab" → Sharing disabled at org level
   - "Students can't access my assistant" → Not published / LTI misconfigured

7. **Images are optional context.** The agent doesn't "see" images, but the file paths are included so the agent can reference them when helping users: "You should see a screen like the one in `images/create-assistant.png`". If the AAC frontend later supports the canvas (item 3b), these images could be displayed.

#### 14b. Liteshell Tools for Documentation Access

Two new liteshell commands that let the agent read documentation on demand:

**`docs.index`** — Returns the table of contents with section summaries
```
lamb docs index
→ {
    "sections": [
      {"file": "getting-started.md", "topic": "getting-started", 
       "summary": "Login, dashboard overview, navigation",
       "covers": ["login", "dashboard", "navigation", "signup"]},
      {"file": "assistants.md", "topic": "assistants",
       "summary": "Creating, editing, configuring learning assistants",
       "covers": ["create", "edit", "system-prompt", "llm", "rag", "vision"]},
      ...
    ]
  }
```

**`docs.read`** — Returns the content of a specific documentation section
```
lamb docs read getting-started
→ {"file": "getting-started.md", "content": "## Login\n\nOpen your LAMB..."}

lamb docs read assistants --section "creating"
→ {"file": "assistants.md", "section": "creating", "content": "## Creating an Assistant\n\n1. Click..."}
```

The `--section` flag is optional. Without it, the full file is returned. With it, only the matching `##` section is returned (parsed by heading). This keeps token usage minimal.

**Authorization policy:** Both commands are `auto` (read-only, no confirmation needed).

**Implementation:**

```python
# In backend/lamb/aac/liteshell/commands.py

@register("docs.index")
def docs_index(ctx, args, kwargs):
    """Return the documentation index with section summaries."""
    index_path = Path(__file__).parents[3] / "static" / "aac_docs" / "index.md"
    # Parse YAML front matter from index.md or each file's front matter
    # Return structured JSON with file, topic, summary, covers, answers
    ...

@register("docs.read") 
def docs_read(ctx, args, kwargs):
    """Read a specific documentation section."""
    topic = args[0] if args else None
    section = kwargs.get("section")
    # Load file from aac_docs/{topic}.md
    # If section specified, extract only that ## heading block
    # Return content as string
    ...
```

#### 14c. `about-lamb` Skill

**Skill file:** `backend/lamb/aac/skills/about_lamb.md`

```yaml
---
id: about-lamb
name: LAMB Helper
description: Answer questions about the LAMB platform, guide educators through features
required_context: []
optional_context: [language]
startup_actions:
  - "lamb docs index"
---
```

**Behavior:**

This skill is different from the existing ones — it's **reactive**, not workflow-driven. The agent doesn't lead with a plan; it answers whatever the educator asks about LAMB.

**On startup:**
1. Load the docs index via `lamb docs index`
2. Greet the user briefly: "I can help you understand LAMB's features. What would you like to know about?"
3. Do NOT dump the full index. Wait for the user's question.

**On user question:**
1. Match the question against the index's `covers` and `answers` fields
2. Fetch the relevant section via `lamb docs read <topic>` (or `--section` for targeted retrieval)
3. Answer in the user's language, using the documentation as ground truth
4. If the question involves a hands-on task ("how do I create an assistant?"), offer to switch to the appropriate skill: "Would you like me to guide you through creating one? I can launch the Create Assistant workflow."

**Key behaviors:**
- **Ground answers in documentation**, not LLM training data. Always read the doc first.
- **Adapt language** to the user's language setting (same as other skills)
- **Cross-reference to actions**: when explaining a feature, offer to do it. "Knowledge bases let your assistant use your documents. Want me to help you set one up?"
- **Handle troubleshooting**: if the user describes a problem, check `troubleshooting.md` first
- **Stay concise**: 3-5 lines per answer unless the user asks for detail

**How it's launched:**
- From the frontend: a "Help" or "About LAMB" button (new, simple)
- From the CLI: `lamb aac start --skill about-lamb`
- Automatically: when the agent detects a "what is" / "how do I" / "why doesn't" question that's about the platform rather than a specific assistant

### Implementation Order

1. **Create `backend/static/aac_docs/`** — transform the website manual into agent-optimized chunked docs with front matter
2. **Add `docs.index` and `docs.read` liteshell commands** — simple file-reading tools
3. **Create the `about-lamb` skill** — reactive, doc-grounded question answering
4. **Add `docs.*` to authorization policy** — both `auto`
5. **Add "Help" button to frontend** — launches `about-lamb` skill session
6. **Test with real educator questions** — verify grounding, cross-skill handoff, troubleshooting

### Deliverables

1. `backend/static/aac_docs/` — 10-12 agent-optimized markdown files + index + images subset
2. `backend/lamb/aac/liteshell/commands.py` — `docs.index` and `docs.read` handlers
3. `backend/lamb/aac/skills/about_lamb.md` — skill definition
4. Frontend: "Help" / "About LAMB" button that launches the skill
5. Authorization policy update for `docs.*` commands

---

## 15. Dashboard "LAMB Agent" Button — Agentic Entry Point

**Priority:** High — transforms the first-use experience into a conversational one
**Depends on:** Item 14 (`about-lamb` skill + docs tooling must exist first)
**Related:** Item 3 (frontend UI scaffold), Item 14 (about-lamb skill)

### Problem

The dashboard is currently a static summary of resources (assistants, KBs, rubrics, templates). An educator who lands here for the first time sees numbers and categories but gets no guidance. They have to figure out the navigation themselves — click around, explore menus, read documentation externally.

The AAC agent already exists and can guide educators through everything, but it's hidden behind the assistant detail page (Explain/Improve buttons) or requires knowing about `lamb aac start`. There is no prominent, zero-friction entry point.

### Design

A large, visually prominent **"LAMB Agent"** button on the Dashboard that launches the AAC terminal with the `about-lamb` skill. One click → the agent greets the user and offers to help with anything.

#### Dashboard Layout Change

```
┌──────────────────────────────────────────────────────────────┐
│  Welcome back, Admin User!                                    │
│  LAMB System Organization  |  Role: Admin  |  Member since... │
│                                                                │
│  ┌─────────────────────────────────────┐  ┌────────────────┐  │
│  │                                     │  │ MY RESOURCES   │  │
│  │     🤖  LAMB Agent                  │  │                │  │
│  │                                     │  │ ASSISTANTS     │  │
│  │     Talk to the AI assistant to     │  │ 10 · 3 pub     │  │
│  │     get help, create assistants,    │  │                │  │
│  │     learn about LAMB, or manage     │  │ KNOWLEDGE BASES│  │
│  │     your resources.                 │  │ 6 · 0 shared   │  │
│  │                                     │  │                │  │
│  │          [ Start conversation ]     │  │ RUBRICS        │  │
│  │                                     │  │ 9 · 0 public   │  │
│  └─────────────────────────────────────┘  │                │  │
│                                            │ TEMPLATES      │  │
│  SHARED WITH ME                            │ 2 · 1 shared   │  │
│  Nothing shared with you yet               └────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

The button occupies the left/center area, visually dominant. The resources summary moves to the right column. The message is brief and action-oriented.

#### What Happens on Click

1. **Create an AAC session** via `POST /creator/aac/sessions` with `skill: "about-lamb"` (no `assistant_id` needed — this skill has no required context)
2. **Navigate to the assistants page** with the AAC terminal open in a new tab (reuses the existing tab infrastructure from item 3)
3. **The agent speaks first** — the `about-lamb` skill has `startup_actions` that load the docs index, then the agent sends a short greeting:

```
Hi! I'm the LAMB assistant. I can help you with:

1. Creating and configuring learning assistants
2. Setting up knowledge bases with your documents
3. Building evaluation rubrics
4. Publishing assistants to your LMS
5. Troubleshooting any issues

What would you like to do?
```

The greeting adapts to the user's language setting and to their resource state (e.g., if they have 0 assistants: "I see you haven't created any assistants yet. Want me to walk you through creating your first one?").

#### Frontend Implementation

**Component:** New `AgentLaunchCard.svelte` in `src/lib/components/aac/`

```
src/lib/components/aac/
└── AgentLaunchCard.svelte    # Big button card for dashboard
```

**Integration point:** Dashboard page (`src/routes/+page.svelte` or equivalent)

**Behavior:**
- Renders as a card with icon, description, and CTA button
- On click: calls the AAC session API, then navigates to `/assistants` with the session tab open
- Shows a loading spinner during session creation
- If the `about-lamb` skill doesn't exist yet (e.g., backend not updated), gracefully falls back to a free-form session

**Styling:**
- Uses the existing brand colors (blue primary)
- Robot/agent icon (consistent with the AAC terminal styling)
- Responsive: stacks vertically on mobile
- i18n: title, description, and CTA text via `svelte-i18n`

#### Session Creation Details

The session is created with:
```json
{
  "skill": "about-lamb",
  "context": {},
  "title": "LAMB Agent"
}
```

No `assistant_id` — this is the first skill that operates without a target assistant. The session manager already supports optional `assistant_id` (it's nullable in the schema), so no backend change needed for session creation.

#### Returning Users

If the user already has an active `about-lamb` session (created today, not archived), the button should **resume** it instead of creating a new one. Check via `GET /creator/aac/sessions` filtered by skill.

This avoids orphaned sessions from users who click the button multiple times.

### What This Enables

The agentic entry point changes the user journey from:

**Before:** Dashboard → navigate menus → find feature → figure out how to use it → (stuck) → look for docs externally

**After:** Dashboard → "LAMB Agent" → "I want to create a tutor for my biology class" → agent walks them through it end-to-end

This is the **conversational-first onboarding** vision: the platform becomes usable through dialogue, not just through forms and menus.

### Implementation Order

1. Create `AgentLaunchCard.svelte` component
2. Integrate into dashboard layout (left/center position)
3. Wire up session creation → tab navigation
4. Add session resumption logic (check for active `about-lamb` session)
5. Add i18n strings (en, es, ca, eu)
6. Test the full flow: dashboard → click → agent greets → user asks question → agent answers from docs

### Deliverables

1. `frontend/svelte-app/src/lib/components/aac/AgentLaunchCard.svelte`
2. Dashboard layout modification (resource summary to right column)
3. i18n strings for the card (4 languages)
4. Session resumption logic in the card component

---

## 16. Liteshell HTTP Refactoring — Single Code Path via Creator Interface ✅

**Priority:** High — eliminates code duplication and validation bypass between CLI and agent
**Status:** DONE (2026-04-03)
**Depends on:** Nothing (refactoring of existing infrastructure)
**Related:** Item 12 (liteshell tests — can now reuse CLI E2E tests)

### Problem

The liteshell currently bypasses the Creator Interface and calls LAMB service layer functions directly. This means:

1. **Validation divergence** — the Creator Interface adds validation, sanitization, and permission checks that the liteshell skips
2. **Duplicated logic** — `assistant.create` reimplements name sanitization, `assistant.update` reimplements fetch-and-merge, both diverge from the HTTP path
3. **Maintenance burden** — new API features or bug fixes in Creator Interface endpoints don't automatically apply to the liteshell
4. **System prompt coupling** — new liteshell commands must also be manually added to the agent's system prompt command list (discovered during docs.index/docs.read work)

### Solution

Refactor the liteshell to call the Creator Interface HTTP endpoints using `LambClient` from `lamb-cli`. The lamb-cli already has a clean HTTP client (`lamb_cli/client.py` — 188 lines, pure httpx) that handles auth headers, error mapping, and JSON parsing.

**Architecture change:**

```
BEFORE:
  lamb-cli ──HTTP──► Creator Interface ──► Services ──► DB
  liteshell ─────────────────────────────► Services ──► DB

AFTER:
  lamb-cli  ──► LambClient ──HTTP──► Creator Interface ──► Services ──► DB
  liteshell ──► LambClient ──HTTP──► Creator Interface ──► Services ──► DB
```

### How LambClient Becomes Available

At container launch, install lamb-cli as an editable package:

```bash
pip install -e /opt/lamb/lamb-cli
```

This makes `from lamb_cli.client import LambClient` available inside the backend. Since lamb-cli is volume-mounted in docker-compose, changes to lamb-cli are reflected immediately. No file copying, no symlinks, no gitignore entries.

lamb-cli dependencies are lightweight (`httpx`, `typer`, `rich`, `platformdirs`, `tomli-w`) — `httpx` is already a backend dependency, the rest are harmless.

### Token Propagation

The AAC router already receives the user's JWT. Pass it through to the liteshell:

```python
# CommandContext gets token + server_url
@dataclass
class CommandContext:
    server_url: str       # "http://localhost:9099"
    token: str            # user's JWT from AAC request
    user_email: str
    organization_id: int
    user_id: int = 0
    http: LambClient      # initialized from server_url + token
```

The liteshell calls localhost with the real user's token — same auth path as the frontend and CLI.

### What Changes

| Component | Change |
|-----------|--------|
| Container startup | Add `pip install -e /opt/lamb/lamb-cli` |
| `LiteShell` class | Add `server_url`, `token` fields; create `LambClient` on init |
| `CommandContext` | Add `token`, `server_url`, `http` (LambClient instance) |
| 22 command handlers | Rewrite from direct service calls to `ctx.http.get/post/put/delete` |
| `router.py` | Extract token from request, pass to LiteShell |
| `agent/loop.py` | No changes |
| `authorization.py` | No changes |
| `lamb-cli` | **No changes** |
| `docs.index`, `docs.read`, `help` | **No changes** (local file reads, no HTTP equivalent) |

### Command Mapping

Each liteshell command maps to a Creator Interface endpoint:

| Command | HTTP Call |
|---------|----------|
| `assistant.list` | `GET /creator/assistant/get_assistants` |
| `assistant.get <id>` | `GET /creator/assistant/get_assistant/{id}` |
| `assistant.config` | `GET /creator/assistant/config` |
| `assistant.debug <id> -m "text"` | `POST /creator/assistant/{id}/tests/scenarios/run` with debug_bypass |
| `assistant.create <name> ...` | `POST /creator/assistant/create_assistant` |
| `assistant.update <id> ...` | `PUT /creator/assistant/update_assistant/{id}` |
| `assistant.delete <id>` | `DELETE /creator/assistant/delete_assistant/{id}` |
| `rubric.list` | `GET /creator/rubrics/` |
| `rubric.get <id>` | `GET /creator/rubrics/{id}` |
| `rubric.export <id>` | `GET /creator/rubrics/{id}/export` |
| `rubric.list-public` | `GET /creator/rubrics/public` |
| `kb.list` | `GET /creator/knowledgebases/` |
| `kb.get <id>` | `GET /creator/knowledgebases/{id}` |
| `template.list` | `GET /creator/prompt-templates/` |
| `template.get <id>` | `GET /creator/prompt-templates/{id}` |
| `model.list` | `GET /creator/models` |
| `test.scenarios <id>` | `GET /creator/assistant/{id}/tests/scenarios` |
| `test.add <id> ...` | `POST /creator/assistant/{id}/tests/scenarios` |
| `test.run <id>` | `POST /creator/assistant/{id}/tests/scenarios/run` |
| `test.runs <id>` | `GET /creator/assistant/{id}/tests/runs` |
| `test.run-detail <rid>` | `GET /creator/assistant/{id}/tests/runs/{rid}` |
| `test.evaluate <rid> ...` | `POST /creator/assistant/{id}/tests/runs/{rid}/evaluate` |

### Testing Strategy

The existing CLI E2E test suite (`testing/cli/`) tests the same HTTP endpoints against a running backend. Since the liteshell now calls the same endpoints:

1. **CLI tests validate the endpoints** — if CLI tests pass, the endpoints work
2. **Liteshell tests validate the command parsing + HTTP mapping** — a lighter test layer
3. **AAC agent tests validate the full chain** — agent → liteshell → HTTP → service

The `testing/cli/helpers/cli_runner.py` pattern (CLIResult assertions) can be adapted for liteshell testing by replacing subprocess calls with direct `LiteShell.execute()` calls.

### Performance Impact

| Call type | Expected latency |
|-----------|-----------------|
| Current (direct service) | 4-30ms |
| HTTP to localhost via LambClient | 10-50ms |
| Typical AAC session (10-15 calls) | Extra 100-300ms total |

Acceptable — LLM calls take 2-20 seconds each, so HTTP overhead is noise.

### Implementation Order

1. Add `pip install -e /opt/lamb/lamb-cli` to container startup
2. Refactor `CommandContext` and `LiteShell` to carry `LambClient`
3. Update `router.py` to pass token through
4. Rewrite all 22 HTTP commands
5. Test each command against running backend
6. Run existing CLI E2E tests to confirm endpoint compatibility

### Deliverables

1. Updated `LiteShell` and `CommandContext` with HTTP client support
2. Rewritten command handlers (22 of 25)
3. Container startup update
4. All existing CLI E2E tests still passing

### Implementation Notes (2026-04-03)

**Key discovery:** Calling localhost over TCP from a single-worker uvicorn process deadlocks — the worker is busy handling the AAC `/message` request and can't handle the liteshell's inner HTTP request. Solution: **httpx.ASGITransport** calls the FastAPI app directly in-process with zero TCP overhead.

**Files changed:**
- `backend/lamb/aac/liteshell/http_client.py` — new `AsyncLambClient` using `httpx.AsyncClient` + `ASGITransport`
- `backend/lamb/aac/liteshell/shell.py` — `execute()` now async, lazy-inits `AsyncLambClient`, distinguishes local vs HTTP commands
- `backend/lamb/aac/liteshell/commands.py` — 22 HTTP commands are `async def`, 3 local commands (`docs.index`, `docs.read`, `help`) marked with `local=True`
- `backend/lamb/aac/agent/loop.py` — `_execute_tool()` and `_resolve_pending_action()` now async with `await`
- `backend/lamb/aac/router.py` — extracts bearer token from request, `_prepare_agent_and_message()` and `_build_agent_with_skill()` now async, `await shell.execute()` in skill startup actions

**Tested via UI (Playwright):**
- Explain skill: agent read assistant config (13ms ASGI), ran debug bypass (1153ms ASGI), read docs (54ms local+ASGI) — all in one conversation
- Mixed HTTP + local commands work seamlessly
- No deadlocks, no errors

**Requires:** `pip install -e /opt/lamb/lamb-cli` in backend container at startup

---

## 17. Remove Student Anonymization from LTI Dashboard

**Priority:** High — current anonymization gives a false sense of privacy; the LMS handles this natively
**Depends on:** Nothing
**Related:** Issue #332

### Problem

The LTI Unified Activity dashboard anonymizes student names ("Student 1", "Student 2") in chat transcripts and the student list. This was implemented as a privacy feature, but it's the wrong layer for this concern:

1. **The LMS already handles anonymization.** Moodle and other LMS platforms have their own privacy controls for external tools. Instructors can configure whether student identity is passed to LTI tools at the LMS level.
2. **Our anonymization is cosmetic, not real.** The student's OWI user ID, access times, and chat content are all stored. An instructor with DB access could de-anonymize trivially. The "Student N" labels create a false sense of privacy.
3. **Instructors need to identify students.** When reviewing chat transcripts for pedagogical purposes (e.g., spotting a struggling student, grading participation), anonymized names are useless. The instructor already knows the students — they're in their class.
4. **The consent flow is unnecessary friction.** Students must accept a consent notice that says their chats "may be reviewed anonymously." This is confusing (the instructor can already see the chat content) and adds a click barrier.

### What to Change

**Remove all anonymization logic.** Show real student names (as provided by the LMS) in the dashboard. Remove the consent flow. Update all documentation.

### Files to Modify

**Backend:**

| File | Change |
|------|--------|
| `backend/lamb/lti_activity_manager.py` | `get_dashboard_students()`: return real names instead of "Student N". `get_dashboard_chats()`: return real student names. `get_dashboard_chat_detail()`: return real name. Remove `_build_anonymization_map()`. Remove `check_student_consent()` and `record_student_consent()`. |
| `backend/lamb/lti_router.py` | Remove consent page redirect. Remove `GET/POST /consent` endpoints. Simplify student launch flow (no consent check). |
| `backend/lamb/templates/lti_dashboard.html` | Show real student names in the student list and chat transcript views. Remove "anonymized" labels. |
| `backend/lamb/templates/lti_activity_setup.html` | Remove the "anonymized chat transcripts" checkbox text. Simplify to just "Allow instructors to review chat transcripts". Remove the "identities are never revealed" claim. |
| `backend/lamb/templates/lti_consent.html` | Delete entirely (or keep as a simple "welcome" page without consent). |
| `backend/lamb/database_manager.py` | `lti_activity_users.consent_given_at` column becomes unused. Keep for backward compat but stop writing to it. |

**Documentation:**

| File | Change |
|------|--------|
| `Documentation/lamb_architecture_v2.md` | Section 8.2.1: remove "all transcripts anonymized", "consent page", "Student 1, Student 2" references. Update flow diagram. |
| `Documentation/lti_landscape.md` | Update Unified LTI section: remove anonymization mentions, consent flow, "identities are never revealed" claim. |
| `/opt/Lamb-Project-Website/content/en/manual/index.md` | Section 8: update LTI publishing description, remove "anonymized transcripts" mention. |
| `/opt/Lamb-Project-Website/content/es/manual/index.md` | Same changes in Spanish. |

**Database schema (no migration needed):**
- `lti_activities.chat_visibility_enabled` — keep as-is (still controls whether instructors can see chats at all)
- `lti_activity_users.consent_given_at` — stop writing to it, ignore on read

### What Stays

- **`chat_visibility_enabled`** — the instructor still chooses at setup whether chat transcripts are visible to instructors. This is about feature access, not anonymization.
- **Student identity isolation per activity** — students still get synthetic OWI emails per `resource_link_id`. This prevents cross-activity data leakage and is unrelated to anonymization.
- **The instructor dashboard** — still shows stats, student list, chat transcripts. Just with real names now.

### Implementation Order

1. Remove anonymization from `lti_activity_manager.py` (show real names)
2. Remove consent flow from `lti_router.py` (simplify student launch)
3. Update templates (setup page text, dashboard labels)
4. Delete or simplify consent template
5. Update architecture docs and LTI landscape
6. Update website manuals (EN + ES)
7. Create GitHub issue #332

---

## 18. AAC Terminal File Upload Widget

**Priority:** Medium — enables fully agentic Library/KB workflows
**Depends on:** Library Manager (issue #331) being operational

### Problem

The AAC terminal is text-only. When the Library Manager is ready, users will want to upload files to libraries through the agent conversation ("upload this PDF to my biology library"). The agent can't handle binary files through a text command.

### Solution

Add a file upload widget (📎 button) next to the Send button in the AAC terminal. When the user selects/drops a file:

1. Frontend uploads it to a staging endpoint (e.g., `POST /creator/aac/upload`)
2. Backend stores it temporarily and returns a reference ID
3. The reference is injected into the conversation context
4. The agent can use liteshell commands to import the staged file into a library

This works for both the `/agent` page and the assistant detail AAC terminals (same `AacTerminal.svelte` component).

### Interim Approach

Until this is built:
- **CLI users:** `lamb library upload <id> file.pdf` (standard multipart, works immediately)
- **Web users:** Upload via Library UI, then ask the agent to work with the imported content
- **AAC agent:** Can list and reference already-imported library items via liteshell commands

---

## 19. AAC Bugs

### 19a. Agent is clueless about prompt templates ✅ (2026-04-04)

The AAC agent doesn't understand how the LAMB prompt template system works. When creating or editing assistants, it doesn't know that:

- **`{context}`** is the RAG insertion point — required in the prompt template for any RAG-enabled assistant. Without it, retrieved KB content has nowhere to go and is silently discarded.
- **`{user_input}`** is the user message insertion point — required in ALL prompt templates. Without it, the student's question isn't included in the final prompt.

The agent creates assistants with empty `prompt_template` or templates missing these placeholders, leading to broken pipelines.

**Fix:** Add prompt template rules to the system prompt in `loop.py` and to the `create-assistant` and `improve-assistant` skills. The agent must:
- Always set a prompt template containing `{user_input}` when creating an assistant
- Add `{context}` when RAG is enabled
- Warn when it detects a RAG assistant without `{context}` in the template
- Know the placeholder syntax: `{context}` and `{user_input}` (curly braces, no dashes)

### 19c. Agent cannot list or switch skills mid-conversation ✅ (2026-04-04)

The agent has no way to:
- Show the user what skills are available (no `skill.list` liteshell command)
- Load a different skill mid-conversation (no `skill.load` liteshell command)

When a user starts with `about-lamb` and says "help me create an assistant", the agent should be able to load the `create-assistant` skill and guide them — without requiring a new session.

**Fix:** Add two liteshell commands:

- `skill.list` — returns available skills with descriptions and required context. Authorization: `auto`.
- `skill.load <skill-id> [--assistant <id>]` — loads a skill's prompt into the current session as a system message, runs its startup actions. Authorization: `auto` (it's just adding instructions, not a write). The conversation history is preserved.

Update the system prompt so the agent knows it can switch skills. When the user asks something that matches a skill, the agent should offer: "I can switch to the Create Assistant workflow. Want me to?"

Also consider adding a `/skills` shortcut in the terminal UI — but this is optional since the agent can handle it conversationally via `skill.list`.

### 19b. No session history on the Agent page

The `/agent` page auto-creates or resumes today's `about-lamb` session, but there's no way to:
- See a list of past agent sessions
- Resume an older session from a previous day
- Browse conversation history

Currently the page shows a single terminal. If the user wants to review what they discussed yesterday, they have no way to get there.

**Fix:** Add a session list/history panel to the `/agent` page. Options:
- A sidebar or dropdown showing past sessions (title, date, tool count)
- Click to resume any session
- Matches the design from backlog item 9c (Agent History UI) but scoped to the `/agent` page

---

## 20. Missing Liteshell Commands

**Priority:** Medium-High — limits what the agent can do for the user
**Depends on:** Nothing (endpoints already exist)

### Current state (29 commands)

The liteshell covers: assistant CRUD + config + debug + chat + list-shared + list-published, rubric list/get/export, KB list/get, template list/get, test CRUD + run + evaluate, docs index/read, skill list/load, help.

### What's missing (grouped by impact)

#### 20a. Assistant publish/unpublish — HIGH

The agent can create and configure assistants but can't publish them to the LMS. The user has to leave the conversation and do it from the UI. This breaks the end-to-end agentic workflow.

```
lamb assistant publish <id>
lamb assistant unpublish <id>
```

Endpoints: `PUT /creator/assistant/publish/{id}` with `{"publish_status": true/false}`.
Authorization: `ask` (write operation — publishes to students).

#### 20b. Assistant chat with full context — HIGH

The current `assistant.chat` command sends a single message. But a real conversation has context — previous messages, the system prompt override, etc. The agent should be able to:

1. **Send multi-turn conversations** — feed a list of messages (system + user + assistant turns) to simulate a full conversation. This lets the agent test how the assistant handles follow-up questions, context retention, and conversation flow.

2. **Override system prompt** — test a system prompt change without actually updating the assistant. "What if the system prompt said X instead?" → run the chat with the modified prompt → compare.

3. **Pass chat history** — when debugging a reported problem ("my student said X and the assistant said Y, then when they said Z it broke"), the agent needs to replay the full conversation.

```
lamb assistant chat <id> --message "text"                    # current: single message
lamb assistant chat <id> --messages '[{"role":"user","content":"hi"},{"role":"assistant","content":"hello"},{"role":"user","content":"follow up"}]'  # multi-turn
lamb assistant chat <id> --message "text" --system-prompt "override for testing"  # system prompt override
```

The completions endpoint already supports `messages` as a list — the liteshell command just needs to expose it.

Authorization: `auto` (read-like, uses tokens but user explicitly requests it).

#### 20c. KB query — MEDIUM

Test what a knowledge base retrieves for a query, without going through an assistant. Essential for debugging RAG issues: "is the KB finding the right content?"

```
lamb kb query <kb_id> --query "text" [--top-k 5]
```

Endpoint: `POST /creator/knowledgebases/kb/{id}/query`.
Authorization: `auto`.

#### 20d. Template create/update/share — MEDIUM

The agent can read templates but can't create or share them. After helping an educator write a good system prompt, it should be able to save it as a reusable template.

```
lamb template create "Name" --system-prompt "..." --prompt-template "..."
lamb template update <id> --name "..." 
lamb template share <id>
```

Endpoints: `POST /creator/prompt-templates/create`, `PUT /creator/prompt-templates/{id}`, `PUT /creator/prompt-templates/{id}/share`.
Authorization: `ask` for create/update (writes), `auto` for share.

#### 20e. Analytics stats — LOW

Check how a published assistant is being used (total chats, unique users, messages). Useful when the agent is helping improve an assistant — "how many students are using this?"

```
lamb analytics stats <assistant_id>
lamb analytics chats <assistant_id>
```

Endpoints: `GET /creator/analytics/assistant/{id}/stats`, `GET /creator/analytics/assistant/{id}/chats`.
Authorization: `auto`.

#### 20f. Assistant export — LOW

Export an assistant's configuration as JSON for backup or sharing across instances.

```
lamb assistant export <id>
```

Endpoint: `GET /creator/assistant/export/{id}`.
Authorization: `auto`.

#### 20g. Rubric generate/share — LOW

AI-generate a rubric from a description, share with organization.

```
lamb rubric generate "description" --lang en
lamb rubric share <id>
```

Endpoints: `POST /creator/rubrics/ai-generate`, `PUT /creator/rubrics/{id}/visibility`.
Authorization: `auto` for generate (preview only), `ask` for share.

### Not needed in liteshell

- **org/user admin commands** — admin-only, low frequency, UI is fine
- **job management** — KB-related, deferred to Library Manager (#331)
- **aac commands** — the agent IS the AAC, doesn't need to manage itself
- **interactive chat** — the agent runs single inferences, not interactive REPL sessions

### Implementation order

1. **20a** publish/unpublish — completes the assistant lifecycle
2. **20b** chat with full context — essential for real testing
3. **20c** KB query — debugging RAG
4. **20d** templates — saving good work
5. **20e-g** analytics, export, rubric — nice to have

---

## 21. Unified AAC Session Management (+ merged items 9c, 19b)

**Priority:** High — current AAC session UX is broken
**Depends on:** Nothing (frontend + small backend changes)

**Note (2026-04-05):** Items **9c** (Agent history UI) and **19b** (session history on /agent page) are merged here. They're the same feature viewed from different angles — see the unified design below.

### Bugs discovered (2026-04-05)

1. **`/agent` page doesn't reload previous messages.** When resuming a session, the terminal shows empty even though the session has history in the DB. The terminal resumed mode isn't fetching/displaying the stored conversation.

2. **No way to close a session from the UI.** Once opened, sessions stay forever. User has to manually delete from CLI or leave them as clutter.

3. **No visibility into multiple active sessions.** `/agent` shows one session at a time with no way to see or switch to other active sessions.

4. **Fragmented tab system.** The assistants page has its own AAC tab system (Agent Explain/Improve open inline). The `/agent` page is separate. Sessions created in one view don't appear in the other.

5. **Session titles are opaque.** Current titles: "Session", "LAMB Helper", "Improve Configuration: 1_history_of_vikings". Some are hashes or defaults. **Users don't parse hashes.**

6. **No "user returned" context refresh.** When a user switches tabs or comes back after time, the agent doesn't know the user might have changed things elsewhere.

7. **Agent can't rename sessions.** Sessions have fixed titles from creation.

### Solution: Unified Session Tab System

#### 21a. Fix conversation reload on `/agent` page

When resuming a session (via URL param or store), the terminal MUST load and display the stored conversation history BEFORE showing the input field. Currently `AacTerminal.svelte` has a `resumed={true}` prop but doesn't properly display prior messages.

#### 21b. Global session tab bar

A persistent tab bar showing ALL active AAC sessions across the entire app. Lives in the layout (above the main content area, below the nav bar). Tabs show:
- Skill icon + readable title ("Improve: history_of_vikings")
- Close button (✕)
- Active indicator

Clicking a tab switches to that session's terminal. The terminal view is rendered in a consistent location.

Unify `aacStore.svelte.js` to be the single source of truth for open tabs — both `/agent` and assistant detail pages read/write to it.

#### 21c. Session titles that humans parse

Auto-generated titles based on skill + target:

| Skill | Title format |
|-------|-------------|
| about-lamb | "LAMB Helper" |
| create-assistant | "Create: {proposed_name}" (agent updates when name is chosen) |
| improve-assistant | "Improve: {assistant_name}" (agent fills in on startup) |
| explain-assistant | "Explain: {assistant_name}" |
| test-and-evaluate | "Test: {assistant_name}" |

The agent should be able to update the title mid-session via a new liteshell command (see 21d).

#### 21d. New liteshell command: `session.rename`

Allow the agent to rename the current session when it learns more context.

```
lamb session rename "New title here"
```

Authorization: `auto` (cosmetic change).

Endpoint: `PUT /creator/aac/sessions/{id}/title` with `{"title": "..."}`.

Agent system prompt update: "When you learn the target assistant's real name or the user's intent, rename the session so it's findable later."

#### 21e. User-returned context refresh

When the user returns to an active session tab after being away, on their NEXT message, inject a system note:

```
[System: User returned. Data may have changed since the last message — 
 re-check anything you showed earlier before claiming it's still accurate.]
```

Frontend tracks timestamp of last message and the current tab's last activity. If user switches tabs or closes the window and comes back, the flag is set. Next `POST /message` includes `user_returned: true` in the body. Backend injects the system note before the user's actual message.

If the user doesn't send a message, no note is injected. The note is invisible to the user — it only affects the agent.

#### 21f. Unify assistant-detail AAC tabs with global tab bar

Currently Agent Explain/Improve on the assistants page open as inline tabs specific to that assistant. Unify these into the global tab bar — the session appears in the tab bar, clicking the Learning Assistants nav or switching tabs works the same way.

Implementation: when Agent Explain is clicked, it calls `openTab()` with `assistantId` set. The global tab bar shows all open tabs regardless of where they were opened from.

### Files affected

**Frontend:**
- `src/lib/stores/aacStore.svelte.js` — already has tab state, extend with last-activity tracking
- `src/lib/components/aac/AacTabBar.svelte` — create (or enhance existing) global tab bar
- `src/routes/+layout.svelte` — mount the tab bar
- `src/lib/components/aac/AacTerminal.svelte` — fix conversation reload, add user-returned hook
- `src/routes/agent/+page.svelte` — use global tab bar
- `src/routes/assistants/+page.svelte` — use global tab bar for AAC tabs

**Backend:**
- `backend/lamb/aac/router.py` — add `PUT /sessions/{id}/title` endpoint, accept `user_returned` in message body
- `backend/lamb/aac/liteshell/commands.py` — add `session.rename` command
- `backend/lamb/aac/authorization.py` — `session.rename: auto`
- `backend/lamb/aac/agent/loop.py` — inject "user returned" note when flag set

### Implementation order

1. **21a** Fix conversation reload — critical bug fix (small) ✅ DONE 2026-04-05
2. **Phase A: 21c + 21d** Better titles + rename command
3. **Phase B: 9c + 19b** Agent History page + review detail view
4. **Phase C: 21b + 21f** Global tab bar unification
5. **Phase D: 21e** User-returned context refresh

---

## Unified Design (2026-04-05)

### Core insight

Items 9c, 19b, and 21b-f are the same feature viewed from different angles:
- **21b** = global tab bar (active sessions workspace)
- **9c** = history page (all sessions archive)
- **19b** = session history on /agent (subset of 9c)
- **21c/d/e** = supporting plumbing (titles, rename, context refresh)
- **21f** = unify assistant-detail AAC tabs with global bar

### Two UI concepts

| Concept | What | Where |
|---------|------|-------|
| **Workspace** | Active sessions you're working on | Global tab bar (always visible) |
| **Archive** | All sessions you can review or resume | Dedicated history page |

A session moves between these based on user intent: Open → appears in tab bar. Close tab → archived, falls off bar (still in archive). Resume from archive → re-opens in tab bar.

### Components

#### 1. Global AAC Tab Bar

Location: Between top nav and page content, always visible when at least one session is open.

```
┌──────────────────────────────────────────────────────────┐
│  [LAMB]  Assistants  Agent  Agent History  Admin  ...   │
├──────────────────────────────────────────────────────────┤
│  🤖 LAMB Helper ✕  │ ✨ Improve: rock_60s ✕  │ + New    │
├──────────────────────────────────────────────────────────┤
│       (active session's terminal)                        │
```

Each tab: skill icon, title, close button. Click = switch. Close = archive.
State in sessionStorage. Unifies `/agent` AND assistant-detail Agent Explain/Improve.

#### 2. Agent History Page (`/agent/history`)

Table of all sessions (active + archived). Filters: date, skill, assistant, status, errors. Per-row actions: Resume (opens in tab bar) / Review (read-only) / Delete.

#### 3. Session Review View (`/agent/history/:id`)

Read-only detail: full transcript, tool audit timeline, stats, Resume button (if still active).

#### 4. Terminal header changes

- Editable title (click to edit) → calls `session.rename`
- Existing stats toggle stays

#### 5. `session.rename` liteshell command

```
lamb session rename "Improve: rock_the_60s"
```

Endpoint: `PUT /creator/aac/sessions/{id}/title`. Authorization: `auto`.
System prompt: *"When you learn the assistant name or user's intent, rename so the session is findable."*

#### 6. Auto-generated titles at creation

Router resolves assistant name when creating sessions:

| Skill | Title format | Resolution |
|-------|-------------|------------|
| about-lamb | `LAMB Helper` | Fixed |
| create-assistant | `Create: (new)` | Agent renames when name chosen |
| improve-assistant | `Improve: {asst_name}` | From assistant_id |
| explain-assistant | `Explain: {asst_name}` | From assistant_id |
| test-and-evaluate | `Test: {asst_name}` | From assistant_id |

#### 7. User-returned context refresh

Frontend tracks `lastActivityAt` per tab. If idle >5min before next message, POST body includes `user_returned: true`. Backend injects a system note before the user's message:
```
[User returned after being away. Data may have changed. Re-check anything you
showed earlier before claiming it's still accurate.]
```

### Phase A deliverables (next)

1. `PUT /creator/aac/sessions/{id}/title` endpoint
2. `session.rename` liteshell command
3. Session creation resolves assistant name for title
4. System prompt instructs agent to rename when appropriate
