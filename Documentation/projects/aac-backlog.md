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

### 3b. Side Panel Canvas (Future Enhancement)

**Priority:** Medium — enhances the experience but not essential for MVP
**Depends on:** Item 3 base implementation

The terminal is text-only. For richer visualizations (rubric tables, test result comparisons, pipeline diagrams), the AAC UI gets a **side panel** with a markdown/HTML renderer — a "canvas" the agent can write to.

**How it works:**

- The agent response can include a special directive: `[canvas: content]` or a dedicated tool `show_in_canvas("markdown content")`
- The frontend detects this and renders the content in a resizable side panel next to the terminal
- The canvas persists until the agent updates it or the user closes it
- Use cases: rubric criteria tables, test result comparison grids, pipeline visualization, assistant config summary

**Components:**

```
src/lib/components/aac/
├── AacCanvas.svelte          # Side panel markdown/HTML renderer
└── AacTerminalWithCanvas.svelte  # Layout wrapper: terminal + canvas side-by-side
```

**Liteshell tool (backend):**
```
lamb canvas show "markdown content"    # display content in side panel
lamb canvas clear                      # clear the side panel
```

This is a future enhancement — the terminal works standalone for now.

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
| **Next** | 9 | Session audit log + Agent history UI | |
| **Then** | 3b | Side Panel Canvas | |
| **Pre-merge** | | Cherry-pick #329 + #330 to dev (production RAG broken) | |
| **Pre-merge** | | Revert docker-compose log levels to WARNING | |

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
