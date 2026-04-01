# AAC Backlog

**Status:** Active
**Last updated:** 2026-03-31 (end of day)
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
| **Next** | 3 | Frontend UI scaffold (chat panel, confirmation cards) | |
| **Then** | 2+4 combined | `test-and-evaluate` skill | |
