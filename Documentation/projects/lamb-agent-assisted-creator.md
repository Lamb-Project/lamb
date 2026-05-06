# LAMB Agent-Assisted Creator (AAC) — MVP

**Status:** Research & Design
**Date:** 2026-03-27
**Version:** 0.4 (Draft)

> **Scope note:** This document covers the **MVP of the agentic assistant creator and evaluator**. Assistant versioning is a related but independent subproject documented separately in [lamb-assistant-versioning.md](./lamb-assistant-versioning.md). The AAC MVP works without versioning — it operates on the assistant's current state. Versioning can be integrated later as an enhancement.

---

## 1. Vision

The current assistant creation flow in LAMB is a static form: fill in a system prompt, pick a model, toggle some settings, save. This was state-of-the-art in 2023. It puts the full burden of prompt engineering, configuration, and quality assurance on the educator — who is typically not an AI specialist.

The **Agent-Assisted Creator (AAC)** provoides an alternative creation edit way) this with a conversational design session. The educator describes what they want in natural language. A purpose-built agent — running a proper agent loop on the LAMB backend — iterates with them: drafting system prompts, configuring the assistant, generating test conversations, running evaluations, and refining based on feedback.

The agent is a **design tool, an educational tool, and a profiling tool**:
- **Design:** It drafts, edits, and refines the assistant configuration through conversation.
- **Education:** It can show the user how the completion context is constructed — what the LLM actually sees — so they understand how system prompts, RAG context, and prompt processors combine.
- **Profiling:** It generates test queries, runs trials, collects evaluation data, and feeds results back into refinement.

The meta-layer is intentional: LAMB uses an AI agent to help educators build AI assistants.

---

## 2. Core Concepts

### 2.1 The Design Agent

The agent is **developer-defined, not user-configurable**. It is built and maintained by the LAMB development team. Its behavior is defined by:

- **Skill files** (`.md`) — declarative descriptions of what the agent can do and how, loaded at runtime. Similar to how Claude Code uses skill definitions.
- **Tool definitions** — explicit, typed tool-use schemas the agent can invoke. Each tool maps to a backend operation (e.g., `update_system_prompt`, `run_test_conversation`, `show_context_preview`).
- **Guardrails** — strict constraints on what the agent can and cannot do. The agent operates within a sandbox: it can modify the assistant being designed, but nothing else.

The agent is **not** a general-purpose LLM chat. It is a constrained agent loop with specific tools, clear boundaries, and a defined purpose.

### 2.2 Design Sessions

A **design session** is the unit of work. When a creator starts the Agent-Assisted Creator, a session is created. The session contains:

- The full conversation history between the user and the agent
- A reference to the assistant being designed (new or existing)
- Test conversations run during the session
- Evaluation results

Sessions are persisted server-side. A user can pause and resume a session. Sessions are recorded for developer research and product improvement but are **not shared** with other org members.

### 2.3 Test Queries & Evaluation

The agent can generate **synthetic test conversations** based on the assistant's purpose:

- **Single-turn prompts** — quick checks ("Ask about X")
- **Multi-turn conversations** — realistic student interaction patterns
- **Edge cases** — adversarial or unexpected inputs

Test conversations are run against the real LLM (real tokens, real behavior). Token consumption is tracked per test run as a first-class metric.

**Evaluation** is a progressive system:

1. **User-driven initially** — The educator reviews test outputs and gives assessments (good/bad, notes, corrections).
2. **Agent learns from user assessments** — Over time, the agent can propose its own evaluations based on patterns it observes in the user's judgments.
3. **Agent suggests, user decides** — The agent may say "Based on your previous feedback, this response seems weak on X. Want me to adjust?" but the user always has final say.

Eval results feed back into the agent's next suggestions, creating a refinement loop:

```
Design → Test → Evaluate → Refine → Test again → ...
```

---

## 3. Architecture

### 3.1 Where It Fits in LAMB

```
┌─────────────────────────────────────────────────────────────────────┐
│                      LAMB Platform (existing)                        │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Frontend   │  │   Backend    │  │  Open WebUI  │              │
│  │   (Svelte)   │  │   (FastAPI)  │  │   (Chat)     │              │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘              │
│         │                  │                                          │
│         │    ┌─────────────┴──────────────┐                          │
│         │    │                             │                          │
│         │    ▼                             ▼                          │
│         │  ┌──────────────┐  ┌──────────────────────────┐           │
│         │  │ Creator API  │  │  LAMB Core API            │           │
│         │  │ /creator     │  │  /lamb/v1                 │           │
│         │  └──────────────┘  └──────────────────────────┘           │
│         │                                                             │
│         │  ┌──────────────────────────────────────────┐  ◄── NEW    │
│         └─►│  Agent-Assisted Creator (AAC)            │              │
│            │                                          │              │
│            │  ┌────────────┐  ┌─────────────────┐    │              │
│            │  │ Agent Loop │  │ Test Runner      │    │              │
│            │  │            │  │ Eval Collector   │    │              │
│            │  │ Skills .md │  │                   │    │              │
│            │  │ Tools      │  │                   │    │              │
│            │  │ Guardrails │  │                   │    │              │
│            │  └────────────┘  └─────────────────┘    │              │
│            └──────────────────────────────────────────┘              │
│                     │               │                                 │
│                     ▼               ▼                                 │
│              ┌────────────┐  ┌────────────┐                          │
│              │ LLM Provider│  │ LAMB DB    │                          │
│              │ (for agent) │  │ (sessions, │                          │
│              └────────────┘  │  tests)     │                          │
│                              └────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 New Backend Components

#### 3.2.1 Agent Runtime (`backend/lamb/aac/agent/`)

The core agent execution engine. This is a **new subsystem** in LAMB — it does not reuse the existing completion pipeline (which is designed for end-user chat, not agent loops).

```
aac/agent/
├── loop.py              # Agent loop: receive message → think → tool call → respond
├── skill_loader.py      # Load and parse skill .md files
├── tool_registry.py     # Register and validate tool definitions
├── guardrails.py        # Constraint enforcement (what the agent can/cannot do)
├── context_builder.py   # Build agent context from session state
└── skills/
    ├── system_prompt_design.md
    ├── rag_configuration.md
    ├── test_generation.md
    ├── context_visualization.md
    ├── evaluation.md
    └── ...
```

**Agent loop** (simplified):

```
1. User sends message
2. Build context: conversation history + current assistant state + session metadata
3. Call LLM with context + tool definitions + skill instructions
4. If LLM returns tool calls:
   a. Validate against guardrails
   b. Execute tool(s)
   c. Append tool results to context
   d. Go to 3 (loop until LLM produces a text response)
5. Return agent response to user
6. Persist conversation turn + any assistant changes
```

**Key design decisions:**

- The agent LLM is configured at the **system level** (not per-org). It needs to be a capable model (Sonnet/Opus class) since it's doing complex reasoning.
- The agent's system prompt and skill files are **developer-maintained** — versioned in the LAMB codebase, not editable by users.
- The loop has a **maximum iteration count** (guardrail against runaway tool-call loops).
- All tool calls are **logged** for developer research.

#### 3.2.2 Agent Tools (`backend/lamb/aac/tools/`)

Explicit tool definitions the agent can invoke. Each tool is a Python function with a JSON schema for its parameters.

**Assistant Configuration Tools:**

| Tool | Description |
|------|-------------|
| `get_assistant_state` | Read current assistant configuration |
| `update_system_prompt` | Modify the system prompt |
| `update_metadata` | Change model, connector, processor settings |
| `update_rag_collections` | Add/remove knowledge base references |
| `list_available_models` | List models available in the user's org |
| `list_available_kbs` | List knowledge bases the user can access |
| `list_available_processors` | List prompt processors and RAG processors |
| `save_assistant` | Persist current assistant state to the database |

**Visualization Tools:**

| Tool | Description |
|------|-------------|
| `preview_completion_context` | Show exactly what the LLM would see for a given input — system prompt + RAG context + prompt processor output, rendered as text |
| `preview_rag_retrieval` | Show what documents/chunks would be retrieved for a given query |
| `explain_pipeline` | Describe the current completion pipeline configuration in plain language |

**Testing Tools:**

| Tool | Description |
|------|-------------|
| `generate_test_queries` | Create synthetic test prompts based on the assistant's purpose |
| `generate_test_conversation` | Create a multi-turn synthetic conversation |
| `run_test_completion` | Execute a single completion against the current assistant config, return response + token count |
| `run_test_batch` | Execute multiple test completions, return responses + aggregate metrics |

**Evaluation Tools:**

| Tool | Description |
|------|-------------|
| `record_user_evaluation` | Store the user's assessment of a test result |
| `get_evaluation_history` | Retrieve past evaluations for this session |
| `suggest_evaluation` | Agent proposes an evaluation based on learned patterns (user must confirm) |

#### 3.2.3 Test Runner (`backend/lamb/aac/testing/`)

Executes test conversations against the assistant's **current configuration**. Uses LAMB's existing completion pipeline (same code path as production) so tests are realistic.

```
testing/
├── test_runner.py        # Execute test completions via the completion pipeline
├── test_generator.py     # Generate synthetic test queries/conversations
└── token_tracker.py      # Track token consumption per test run
```

Each test run records:

```python
{
    "id": "uuid",
    "session_id": "uuid",
    "assistant_id": 123,
    "test_type": "single_turn",   # "single_turn" | "multi_turn" | "batch"
    "input_messages": [ ... ],
    "output": { ... },
    "token_usage": {
        "prompt_tokens": 1200,
        "completion_tokens": 350,
        "total_tokens": 1550
    },
    "assistant_snapshot": { ... }, # Lightweight: system_prompt + metadata at time of test
    "created_at": "2026-03-27T...",
    "evaluations": [ ... ]        # User and agent evaluations, added later
}
```

> **Note on snapshots:** The test run stores a lightweight snapshot of the assistant config at test time (system prompt + metadata). This is not a full versioning system — it's just enough to know what was tested. When the versioning subproject is integrated, this field can be replaced with a `version_id` foreign key.

#### 3.2.4 Evaluation Collector (`backend/lamb/aac/evaluation/`)

```
evaluation/
├── eval_store.py         # Persist evaluations
├── eval_analyzer.py      # Analyze patterns across evaluations (for agent learning)
└── eval_models.py        # Evaluation data structures
```

Evaluation records are intentionally flexible:

```python
{
    "id": "uuid",
    "test_run_id": "uuid",
    "evaluator": "user",          # "user" | "agent"
    "verdict": "good",            # "good" | "bad" | "mixed" — simple to start
    "notes": "Response was too verbose and missed the key concept",
    "dimensions": {               # Optional structured scoring, evolves over time
        "relevance": 4,
        "accuracy": 5,
        "tone": 3
    },
    "confirmed_by_user": true,    # For agent evaluations: did the user agree?
    "created_at": "2026-03-27T..."
}
```

### 3.3 New API Endpoints

New router: `/creator/aac/` — mounted under the Creator Interface, protected by standard `AuthContext`.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| **Sessions** | | |
| POST | `/creator/aac/sessions` | Start a new design session (new or existing assistant) |
| GET | `/creator/aac/sessions` | List user's sessions |
| GET | `/creator/aac/sessions/{id}` | Get session details + conversation history |
| DELETE | `/creator/aac/sessions/{id}` | Archive a session |
| **Agent Interaction** | | |
| POST | `/creator/aac/sessions/{id}/message` | Send a message to the agent, get response (SSE stream) |
| **Testing** | | |
| GET | `/creator/aac/sessions/{id}/tests` | List test runs in a session |
| GET | `/creator/aac/sessions/{id}/tests/{tid}` | Get test run details |
| **Evaluations** | | |
| POST | `/creator/aac/tests/{tid}/evaluate` | Submit a user evaluation for a test run |
| GET | `/creator/aac/sessions/{id}/evaluations` | List all evaluations in a session |

### 3.4 New Database Tables

```sql
-- Design sessions
CREATE TABLE aac_sessions (
    id TEXT PRIMARY KEY,
    assistant_id INTEGER,              -- NULL if designing a new assistant (created on first save)
    user_email TEXT NOT NULL,
    organization_id INTEGER NOT NULL,
    status TEXT DEFAULT 'active',      -- 'active' | 'paused' | 'completed' | 'archived'
    conversation TEXT DEFAULT '[]',    -- JSON: full conversation history
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Test runs
CREATE TABLE aac_test_runs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    assistant_id INTEGER NOT NULL,
    test_type TEXT NOT NULL,           -- 'single_turn' | 'multi_turn' | 'batch'
    input_messages TEXT NOT NULL,      -- JSON
    output TEXT NOT NULL,              -- JSON
    token_usage TEXT,                  -- JSON: {prompt_tokens, completion_tokens, total_tokens}
    assistant_snapshot TEXT,           -- JSON: lightweight config snapshot at test time
    created_at TIMESTAMP
);

-- Evaluations
CREATE TABLE aac_evaluations (
    id TEXT PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    evaluator TEXT NOT NULL,           -- 'user' | 'agent'
    verdict TEXT,                      -- 'good' | 'bad' | 'mixed'
    notes TEXT,
    dimensions TEXT,                   -- JSON: optional structured scoring
    confirmed_by_user BOOLEAN,
    created_at TIMESTAMP
);
```

### 3.5 Frontend Components

New route: `/assistants/design` (new assistant) or `/assistants/{id}/design` (refine existing).

```
routes/
└── assistants/
    └── design/
        ├── +page.svelte              # Main design session page
        └── components/
            ├── AgentChat.svelte       # Conversation panel (left side)
            ├── AssistantPreview.svelte # Live preview of current assistant state (right side)
            ├── TestPanel.svelte        # Test results and evaluation
            └── ContextPreview.svelte   # "What the LLM sees" visualization
```

**Proposed layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  Design Session: "Biology Tutor"              [Save] [Exit] │
├───────────────────────────────┬─────────────────────────────┤
│                               │                             │
│   Agent Conversation          │   Assistant State           │
│                               │                             │
│   Agent: What kind of         │   Name: Biology Tutor       │
│   assistant are you           │   Model: gpt-4o             │
│   building?                   │   System Prompt:            │
│                               │   ┌───────────────────────┐ │
│   User: A biology tutor       │   │ You are a biology     │ │
│   for high school students    │   │ tutor specialized in  │ │
│   studying genetics...        │   │ genetics for high...  │ │
│                               │   └───────────────────────┘ │
│   Agent: I've drafted a       │                             │
│   system prompt focused       │   RAG: [Genetics KB]        │
│   on genetics. I also         │   Connector: openai         │
│   generated 5 test queries.   │   PP: simple_augment        │
│   Want to review them?        │                             │
│                               ├─────────────────────────────┤
│   [________________] [Send]   │   Test Results    [Run All] │
│                               │   ✓ Q1: Good (you rated)   │
│                               │   ✗ Q2: Bad — too verbose  │
│                               │   ? Q3: Not evaluated       │
└───────────────────────────────┴─────────────────────────────┘
```

---

## 4. Agent LLM Configuration

The design agent needs its own LLM configuration, separate from the assistants being designed:

| Concern | Decision |
|---------|----------|
| Which LLM? | System-level config, not per-org. Needs a strong model (Claude Sonnet/Opus, GPT-4o). |
| Who pays? | System-level API key. Token cost is a platform cost. (Open question: should orgs see their AAC usage?) |
| Configuration | New env vars: `AAC_LLM_PROVIDER`, `AAC_LLM_MODEL`, `AAC_API_KEY` (or reuse system org config) |
| Streaming | Agent responses should stream to the frontend (SSE), same pattern as completions |

---

## 5. Guardrails

The agent operates under strict constraints:

| Guardrail | Enforcement |
|-----------|-------------|
| Can only modify the assistant in the current session | Tool implementations scope all writes to `session.assistant_id` |
| Cannot access other users' assistants or data | Tools use `AuthContext` — same access control as Creator API |
| Cannot modify org settings, users, or system config | No tools exist for these operations |
| Cannot execute arbitrary code | Tool registry is closed — only registered tools can be called |
| Maximum tool calls per turn | Configurable limit (e.g., 10) to prevent runaway loops |
| Maximum turns per session | Configurable limit to bound token consumption |
| Cannot publish an assistant directly | Publishing remains a manual user action outside AAC |
| All tool calls are logged | Every invocation recorded in the session for auditability |

---

## 6. Data Flow: End to End

### 6.1 New Assistant Creation

```
1. User clicks "Create with Agent" in Creator Interface
2. POST /creator/aac/sessions → creates session (assistant_id=NULL)
3. User: "I want a biology tutor for high school genetics"
4. POST /creator/aac/sessions/{id}/message
5. Agent thinks, calls tools:
   - save_assistant(name="Biology Tutor", system_prompt="You are a biology tutor...")
   - Assistant created in DB, session.assistant_id updated
6. Agent responds: "I've created a draft. Here's what I set up..."
7. User: "Can you show me what the LLM would see?"
8. Agent calls preview_completion_context(input="What is DNA?")
9. Agent responds with a text visualization of the full context
10. User: "Let's test it"
11. Agent calls generate_test_queries(count=5)
12. Agent calls run_test_batch(queries=[...])
    → assistant_snapshot captured automatically
13. Agent shows results with token counts
14. User evaluates: "Q1 is good, Q3 is too verbose"
15. Agent calls record_user_evaluation(...) for each
16. Agent: "Based on your feedback, I'll tighten the prompt..."
17. Agent calls update_system_prompt(...), save_assistant()
18. ... cycle continues ...
19. User satisfied → exits session, publishes from main assistant page
```

### 6.2 Refining an Existing Assistant

```
1. User selects existing assistant → "Refine with Agent"
2. POST /creator/aac/sessions with assistant_id=123
3. Agent loads current assistant state, conversation begins
4. ... same design-test-evaluate loop ...
5. Changes saved to the same assistant record
```

---

## 7. MVP Implementation Plan

### Phase 1: Agent Runtime Foundation
**Goal:** User can have a conversation with the agent that creates/edits an assistant.

- Agent loop (loop.py, context_builder.py)
- Skill loader + initial skill files (system_prompt_design.md, rag_configuration.md)
- Tool registry with guardrail enforcement
- Core tools: `get_assistant_state`, `update_system_prompt`, `update_metadata`, `update_rag_collections`, `save_assistant`, `list_available_models`, `list_available_kbs`
- Session management: create, persist conversation, resume
- Database tables: `aac_sessions`
- API endpoints: session CRUD + `/message` (SSE streaming)
- Frontend: AgentChat panel + AssistantPreview panel (basic)
- Agent LLM config (env vars)

### Phase 2: Testing & Context Visualization
**Goal:** User can test the assistant and see what the LLM sees.

- Test runner integration with existing completion pipeline
- Token tracking per test run
- Tools: `preview_completion_context`, `explain_pipeline`, `preview_rag_retrieval`
- Tools: `generate_test_queries`, `run_test_completion`, `run_test_batch`
- Database tables: `aac_test_runs`
- API endpoints: test listing/details
- Frontend: TestPanel + ContextPreview components

### Phase 3: Evaluation Loop
**Goal:** User can evaluate test results, agent learns from evaluations.

- Evaluation storage and retrieval
- Tools: `record_user_evaluation`, `get_evaluation_history`, `suggest_evaluation`
- Evaluation pattern analysis (feed evaluation history into agent context)
- Database tables: `aac_evaluations`
- API endpoints: evaluation submission/listing
- Frontend: evaluation UI in TestPanel (thumbs up/down, notes, dimensions)

---

## 8. Open Questions

| # | Question | Impact |
|---|----------|--------|
| 1 | **Which LLM for the agent?** Claude, GPT-4o, or configurable? Provider lock-in vs. quality. | Phase 1 |
| 2 | **Token budget controls?** Should sessions have a token limit? Who monitors AAC costs? | Phase 1 |
| 3 | **Conversation storage format?** Raw message list vs. structured turns with tool calls? | Phase 1 |
| 4 | **Concurrent sessions?** Can a user have multiple active sessions for different assistants? | Phase 1 |
| 5 | **Eval framework details.** What dimensions? What scales? How does agent learning work mechanistically? | Phase 3 |
| 6 | **Session data retention policy.** How long are sessions kept? Anonymization for research? | Post-MVP |
| 7 | **Integration with versioning subproject.** When versioning ships, how do test runs link to versions instead of snapshots? | Post-MVP |

---

## 9. Relationship to Other LAMB Components

| Component | Relationship |
|-----------|-------------|
| **Completion Pipeline** | AAC's test runner invokes the existing pipeline — no duplication. Tests are real completions. |
| **Creator Interface** | AAC is a new router under `/creator`. Uses `AuthContext` for auth. Respects org scoping. |
| **Assistant CRUD** | Existing form-based flow remains unchanged. AAC uses the same DB operations to create/update assistants. |
| **Knowledge Bases** | Agent can list and reference existing KBs. KB creation/upload remains separate. |
| **EvaluAItor (rubrics)** | Future integration point. AAC evaluations could feed into or use rubric definitions. |
| **Versioning Subproject** | Independent. When available, AAC can adopt it: test runs link to version IDs, agent edits create versions automatically. See [lamb-assistant-versioning.md](./lamb-assistant-versioning.md). |
| **OWI Bridge** | AAC does not interact with OWI. Test completions go through LAMB's pipeline, not OWI chat. |

---

## 10. Research Value

Every AAC session produces structured data about how educators design AI assistants:

- What do they ask for first?
- How many iterations does it take to reach a "good" assistant?
- What kinds of test queries reveal problems?
- Which evaluation dimensions do users care about most?
- What's the token cost of the design process vs. the assistant's production use?

This data — properly anonymized — is valuable for AI education research and for improving the AAC agent itself. See [phd-research-lines-aac.md](./phd-research-lines-aac.md) for research lines built on this data.

---

## 11. Prototyping Findings (2026-03-30)

> This section captures architectural decisions validated during hands-on prototyping. See [aac-prototyping-log.md](./aac-prototyping-log.md) for the full session log.

### 11.1 CLI-Shaped Tool Interface (Liteshell)

Instead of building custom tool schemas, the agent uses a **single tool** that accepts CLI command strings:

```
Tool: execute_command
Input: "lamb assistant get 4"
Output: { structured JSON }
```

**Why:** LLMs already know CLI syntax from training data. This eliminates the need to teach the agent a custom API. The same commands can be run by a human with `lamb-cli` to verify agent behavior.

**Implementation:** A Python module ("liteshell") parses the command string, routes it to the correct service function, and returns structured data. No real shell, no subprocess. The command vocabulary matches `lamb-cli` exactly: `assistant`, `rubric`, `kb`, `template`, `model`, `analytics`.

### 11.2 Agent LLM Uses Organization Config

The agent's LLM is configured from the **authenticated user's organization**, using `OrganizationConfigResolver` — the same mechanism the completion pipeline uses. This replaces the env-var approach proposed in §4.

| Original proposal (§4) | Revised |
|---|---|
| System-level env vars: `AAC_LLM_PROVIDER`, `AAC_API_KEY` | User's org config: `OrganizationConfigResolver(user_email)` |
| Separate API key for the agent | Reuses the org's existing provider keys |
| Platform cost | Org cost (same pool as completions) |

**Security:** API keys stay in-process on the backend. They are never sent to the frontend or CLI.

### 11.3 Backend Module, Not Separate Service

The AAC runs as `backend/lamb/aac/` — a Python module inside the existing backend process. It shares the database, auth (`AuthContext`), and service layer with the rest of LAMB.

```
backend/lamb/aac/
├── liteshell/
│   ├── shell.py          # Parse CLI strings → dispatch
│   └── commands.py       # Handlers calling service layer directly
├── agent/
│   ├── loop.py           # LLM tool-calling loop
│   └── skills/           # Skill .md files
├── router.py             # FastAPI endpoints: /creator/aac/*
└── session_manager.py    # Session CRUD
```

### 11.4 Testing via lamb-cli

New `lamb aac` command group in lamb-cli, hitting the `/creator/aac/` endpoints:

```
lamb aac
  start                  Start a design session
  sessions               List sessions
  message <sid> "text"   Send a message
  chat <sid>             Interactive mode
  history <sid>          Show conversation
  stats <sid>            Session statistics
```

This enables rapid testing without the frontend and provides a scriptable interface for benchmarking different LLMs.

### 11.5 Session Logging

Every AAC session is logged to a JSONL file for post-hoc analysis. One file per session:

```
{AAC_LOG_PATH}/{user_id}/{session_id}_{datetime}_{email}.jsonl
```

Each line is a timestamped event:
- `session_start` — model, assistant_id, user
- `user_message` — what the educator said
- `tool_call` — command, success, elapsed_ms, data (truncated if >5KB)
- `agent_response` — what the agent replied
- `turn_complete` — per-turn stats
- `error` — any failures
- `session_end` — final stats

Configuration via `backend/.env`:
| Variable | Default | Purpose |
|---|---|---|
| `AAC_SESSION_LOGGING` | `true` | Enable/disable file logging |
| `AAC_LOG_PATH` | `$LAMB_DB_PATH/aac_logs` | Log directory |

JSONL format is research-friendly — works with grep, jq, pandas. This feeds directly into the research value described in §10.

### 11.6 Frontend: Terminal-in-Tabs

The original design doc (§3.5) proposed a split-panel layout with a chat panel and preview panel. After prototyping, the revised frontend approach is a **terminal emulator embedded as tabs** in the existing UI.

**Key decisions:**

| Original (§3.5) | Revised |
|---|---|
| New route `/assistants/design` | No new routes — tabs overlay existing pages |
| Split panel (chat + preview) | Single terminal panel per session tab |
| Custom chat UI | Terminal emulator (monospaced, markdown) |
| Separate page for design sessions | Skills launched from context buttons on assistant detail page |

**Why terminal?** The agent interaction is conversational and text-heavy. A terminal-style interface is familiar, lightweight, and maps directly to the CLI experience (same markdown output). The monospaced font makes code, prompts, and structured output (rubrics, debug bypass) readable.

**Tab model:** Multiple sessions open as tabs, each with its own terminal. Sessions persist in the database and can be resumed. When resuming, the agent is notified that resources may have changed since the last interaction.

**Session titles:** Auto-generated from skill + assistant name (e.g., "Improve: pestlerubric1"). Stored in the session record.

See [aac-backlog.md](./aac-backlog.md) item 3 for full component list and implementation plan.

### 11.7 Gaps Found

| Gap | Issue | Impact |
|---|---|---|
| No CLI rubric access | #323 (fixed) | Agent couldn't inspect rubric-based assistants |
| Rubric duplicate/share broken | #325 | Backend missing `LambDatabaseManager` methods |
| Rubrics undocumented | #324 | Architecture docs incomplete |

---

*Version 0.4 — Added frontend design, skills, test framework, authorization*
*Prepared: 2026-03-31*
