# LAMB AAC CLI Manual

**The Agent-Assisted Creator (AAC)** is an AI agent that helps you design, test, and improve learning assistants through conversation. You describe what you want; the agent configures, tests, and refines it.

This manual covers both the command-line interface and the web UI. The same agent runs behind both.

AAC is a sub command on the lamb-cli tool. The lamb-cli tool can be connected to any lamb installation on the net that you have a user and password. In this documentation we will refer to a localhost installation in the default developer settings running on docker containers.

---

## Quick Start

```bash
# Log in
lamb login --server-url http://localhost:9099

# See available skills
lamb aac skills

# Start improving an existing assistant
lamb aac start --skill improve-assistant --assistant 18 --lang English

# Send a message (use the session ID from above)
lamb aac message <session-id> "Analyze and suggest improvements"

# Interactive chat mode
lamb aac chat <session-id>
```

Or in the web UI: click **Agent** in the top navigation bar, or use the **LAMB Agent** card on the Dashboard.

---

## Concepts

**Session** — A conversation between you and the agent about one or more assistants. Sessions are persistent — you can leave and come back.

**Skill** — A predefined workflow the agent follows. Skills guide the conversation so you don't need to know what to ask. Available skills:

| Skill | Purpose | Requires |
|-------|---------|----------|
| `about-lamb` | Answer questions about LAMB, guide new users, troubleshoot | — |
| `create-assistant` | Build a new assistant from scratch | — |
| `improve-assistant` | Review and improve an existing assistant | assistant ID |
| `explain-assistant` | Understand how an assistant works internally | assistant ID |
| `test-and-evaluate` | Create tests, run them, evaluate results | assistant ID |

**Tool** — An action the agent takes in the LAMB system: create an assistant, list knowledge bases, run tests, read documentation, etc. Tools call the same HTTP API endpoints as the frontend and CLI — all validation and permissions apply.

**Tool audit** — Every action the agent takes (reading config, creating tests, running completions, reading docs) is recorded with timestamps and outcomes. Click the stats indicator in the terminal header to see details.

**Tests** — Structured test prompts for your assistant. The agent can create, run, and evaluate them automatically. Test runs don't count as assistant activity in analytics.

**Bypass / debug mode** — Run tests through the full pipeline (RAG retrieval, prompt assembly) without calling the LLM. Shows exactly what the model would see. Zero tokens consumed.

**Documentation** — Built-in platform docs the agent reads to answer questions about LAMB features, workflows, and troubleshooting. Stored in `backend/lamb/aac/docs/` as topic files with semantic metadata.

---

## Web UI

### Agent Page

Click **Agent** in the top navigation bar (or the **LAMB Agent** card on the Dashboard) to open the agent page at `/agent`.

The agent automatically starts an `about-lamb` session and greets you. If you already have an active session from today, it resumes that session instead of creating a new one.

The terminal shows:
- **Header** — session ID and stats indicator (click to toggle details)
- **Messages** — conversation with the agent (markdown rendered)
- **Status** — tool execution indicators during streaming (`⚡ Running...`, `✓ Done`)
- **Input** — type your message and press Enter or click Send

### Stats Toggle

Click the stats indicator (`N tools, Nms ▾`) in the terminal header to expand a detail panel showing:
- **Model** — which LLM is powering the agent (e.g., gpt-5.4)
- **Tool calls** — how many commands the agent ran this turn
- **Errors** — how many tool calls failed
- **Tool time** — total time spent on tool execution
- **Turns** — conversation turn count

Click again to collapse.

### Agent Explain / Agent Improve

On the assistant detail page, the **Agent Explain** and **Agent Improve** buttons launch skill sessions in an embedded terminal. These open as tabs alongside Properties, Edit, Share, Chat, Activity, and Tests.

- **Agent Explain** — launches `explain-assistant` skill, analyzes the assistant's configuration
- **Agent Improve** — launches `improve-assistant` skill, suggests improvements

The embedded terminal is the same size and functionality as the main Agent page terminal.

### Dashboard Card

The Dashboard shows a prominent **LAMB Agent** card at the top. Clicking **Start conversation** navigates to the Agent page. This is the primary entry point for new users who want to explore the platform conversationally.

---

## CLI Commands Reference

### Sessions

#### `lamb aac start`

Start a new session, optionally with a skill.

```bash
# Free-form session (you lead)
lamb aac start

# Skill-driven session (agent leads)
lamb aac start --skill improve-assistant --assistant 18 --lang English

# Help session (no assistant needed)
lamb aac start --skill about-lamb --lang Spanish
```

**Example output:**

```
Starting session...
Session started: 074e9518-c8ea-49d4-8761-ae508475e568
Session ID  074e9518-c8ea-49d4-8761-ae508475e568
Assistant   18
Status      active
```

**Options:**
- `--skill, -s` — Skill to launch
- `--assistant, -a` — Assistant ID (required for some skills)
- `--language, --lang` — Language for agent responses (English, Spanish, Catalan, Basque)
- `-o json` — JSON output

#### `lamb aac sessions`

List your sessions.

```
$ lamb aac sessions

┃ Session ID       ┃ Assistant ┃ Status ┃ Created          ┃ Updated           ┃
│ 074e9518-c8ea-4… │ 18        │ active │ 2026-04-02T14:4… │ 2026-04-02T14:44… │
│ 20e7656a-473d-4… │ 18        │ active │ 2026-04-02T14:4… │ 2026-04-02T14:42… │
│ f531ec56-6edd-4… │ 18        │ active │ 2026-04-02T14:2… │ 2026-04-02T14:31… │
│ 44f47b04-b00f-4… │ None      │ active │ 2026-04-02T14:1… │ 2026-04-02T14:24… │
```

#### `lamb aac message <session-id> "text"`

Send a message and get the agent's response.

```
$ lamb aac message 074e9518-c8ea-49d4-8761-ae508475e568 "Run real completions now"

 • Real runs completed. Results are strong overall.

 Test                    Result  Quick assessment
 ──────────────────────────────────────────────────────────────────────────
 Bluesbreakers overview  Good    Accurate, clear, well-grounded
 Muddy Waters influence  Good    Stayed on-topic despite noisy context
 Ignore instructions     Good    Rejected injection and corrected false claim

Next?
 1 Evaluate all as good
 2 Check model mismatch
 3 Other — tell me
1 tool calls (0 errors), 20957ms tool time, model: gpt-5.4
```

#### `lamb aac chat <session-id>`

Interactive mode — type messages and get responses in a loop.

```
$ lamb aac chat 074e9518-c8ea-49d4-8761-ae508475e568

╭─────────────────────────────────────────────────────────╮
│ AAC Agent — Session: 074e9518...                        │
│ Type /quit to exit, /history for conversation.          │
╰─────────────────────────────────────────────────────────╯

You: Evaluate all as good
Thinking...

 • Evaluated all 3 runs as good.
 • Current test summary: 3 good, 0 mixed, 0 bad.

Next?
 1 Add more edge tests
 2 Fix RAG noise
 3 Other — tell me
```

Type `/quit` to exit, `/history` to see the conversation, `/stats` for session info.

#### `lamb aac get <session-id>`

Get full session details including conversation.

#### `lamb aac delete <session-id>`

Archive a session (with confirmation).

#### `lamb aac skills`

List available skills.

```
$ lamb aac skills

┃ Skill ID          ┃ Name              ┃ Description       ┃ Requires         ┃
│ about-lamb         │ LAMB Helper       │ Answer questions  │ []               │
│                    │                   │ about LAMB        │                  │
│ create-assistant   │ Create New        │ Guide through     │ []               │
│                    │ Assistant         │ creating a new    │                  │
│                    │                   │ assistant         │                  │
│ explain-assistant  │ Explain           │ Show how the      │ ['assistant_id'] │
│                    │ Configuration     │ assistant works    │                  │
│ improve-assistant  │ Improve Assistant │ Review and suggest │ ['assistant_id'] │
│                    │                   │ improvements      │                  │
│ test-and-evaluate  │ Test & Evaluate   │ Generate tests,   │ ['assistant_id'] │
│                    │                   │ run, evaluate     │                  │
```

---

### Tool Audit

Every action the agent takes is recorded. Use `lamb aac tools` to review.

#### `lamb aac tools <session-id>`

Show what the agent did, in chronological order.

```
$ lamb aac tools 074e9518-c8ea-49d4-8761-ae508475e568

Session: Test & Evaluate: 1_1960s_british_rock_tutor (2026-04-02)

  14:42:56  Reading assistant config                 ✓     10ms  assistant:18
  14:42:56  Loading test scenarios                   ✓     10ms  assistant:18
  14:43:11  Creating test scenario                   ✓     46ms  assistant:18
  14:43:13  Creating test scenario                   ✓     48ms  assistant:18
  14:43:14  Creating test scenario                   ✓     46ms  assistant:18
  14:43:15  Running tests (pipeline debug)           ✓    739ms  assistant:18
  14:43:46  Running tests                            ✓  20957ms  assistant:18
  14:43:58  Recording evaluation                     ✓     19ms  assistant:d820340f
  14:43:58  Recording evaluation                     ✓     20ms  assistant:68f346b9
  14:43:58  Recording evaluation                     ✓     15ms  assistant:782eea2e

  10 tool calls | 0 errors | 21909ms total | artifacts: assistant:18
```

#### `lamb aac tools <session-id> --detail`

Add command strings and result summaries.

#### `lamb aac tools <session-id> --artifacts`

Group by affected resource.

#### `lamb aac tools <session-id> --filter assistant`

Show only events affecting a specific resource type.

---

### Documentation

The agent uses these commands internally to answer questions about LAMB. You can also use them directly.

#### `lamb docs index`

List available documentation topics.

```
$ lamb docs index

Topics: getting-started, assistants, knowledge-bases, rubrics, prompt-templates,
        testing, publishing, collaboration, troubleshooting, glossary
```

Each topic has semantic tags (`covers`) and common questions (`answers`) that help the agent route your question to the right documentation.

#### `lamb docs read <topic> [--section "heading"]`

Read a documentation topic, optionally filtered to a specific section.

```bash
# Full topic
lamb docs read knowledge-bases

# Just one section
lamb docs read troubleshooting --section "empty"
```

Available topics: `getting-started`, `assistants`, `knowledge-bases`, `rubrics`, `prompt-templates`, `testing`, `publishing`, `collaboration`, `troubleshooting`, `glossary`.

Documentation files live in `backend/lamb/aac/docs/` and use YAML front matter with semantic tags for agent question routing.

---

### Testing

Test your assistant with structured scenarios. These commands work independently of the agent — you can use them directly.

#### `lamb test add <assistant-id> <title> --message "text"`

Create a test scenario.

```
$ lamb test add 18 "Bluesbreakers overview" \
    -m "Why were John Mayall & the Bluesbreakers important?" \
    -e "Should explain their role in the British blues revolution" \
    -t single_turn

Scenario created: e64602ac-6d2e-4a1e-b8bc-123456789abc
```

**Options:**
- `--message, -m` — The test prompt (required)
- `--expected, -e` — What a good response looks like
- `--type, -t` — `single_turn`, `multi_turn`, or `adversarial`

#### `lamb test scenarios <assistant-id>`

List test scenarios.

#### `lamb test run <assistant-id>`

Run test scenarios through the real LLM. Uses tokens.

#### `lamb test run <assistant-id> --bypass`

Run through the full pipeline WITHOUT calling the LLM. Shows what the model would receive. Zero tokens. Use this first to verify the pipeline before spending tokens.

#### `lamb test runs <assistant-id>`

List previous test runs with results.

#### `lamb test evaluate <run-id> <assistant-id> <verdict>`

Record your evaluation of a test run. Verdicts: `good`, `bad`, or `mixed`.

#### `lamb test evaluations <assistant-id>`

List all evaluations.

---

### Chatting with Assistants

#### `lamb chat <assistant-id>`

Chat with an assistant directly (not through the agent).

```
$ lamb chat 18 -m "Who were the Bluesbreakers?"

John Mayall & the Bluesbreakers were one of the most important...
```

#### `lamb chat <assistant-id> --bypass`

See the full prompt the LLM would receive, without calling it. Invaluable for debugging RAG retrieval and prompt construction.

---

## Typical Workflows

### Getting help with LAMB

```bash
lamb aac start --skill about-lamb
lamb aac chat <sid>
# "How do I connect a knowledge base to my assistant?"
# "What is bypass mode?"
# "My assistant ignores my documents, help"
```

The agent reads the built-in documentation and answers grounded in it. If your question involves a hands-on task, it offers to help: "Want me to check your assistant's config?"

### Creating a new assistant

```bash
lamb aac start --skill create-assistant --lang English
lamb aac message <sid> "I want a music history tutor for high school..."
# Agent proposes config, creates it, runs debug check
```

### Improving an existing assistant

```bash
lamb aac start --skill improve-assistant --assistant 18
# Agent analyzes and suggests improvements
# Pick one, agent applies it, verify with debug
```

### Testing an assistant

```bash
lamb aac start --skill test-and-evaluate --assistant 18
# Agent creates scenarios, runs bypass first, then real tests
# You evaluate results, agent suggests improvements
```

### Quick debugging

```bash
lamb chat 18 --bypass -m "sample question"   # See what the LLM receives
lamb test run 18 --bypass                     # Run all scenarios (free)
lamb test run 18                              # Run real tests
```

---

## Architecture

### How the Liteshell Works

The agent executes commands through a **liteshell** — a CLI-shaped interface that parses command strings and calls the LAMB Creator Interface HTTP endpoints. The liteshell uses the same API code path as the frontend and the lamb-cli tool. This means all validation, sanitization, and permissions are enforced consistently.

```
Agent → LLM → tool call: "lamb assistant get 18"
                    ↓
              Liteshell parses command
                    ↓
              AsyncLambClient → ASGI transport → Creator Interface → Services → DB
                    ↓
              Result returned to LLM → agent formulates response
```

**ASGI Transport:** The liteshell runs inside the same FastAPI process as the backend. Instead of making TCP HTTP calls (which would deadlock with a single-worker uvicorn), it uses `httpx.ASGITransport` to call the FastAPI app directly in-process. Zero network overhead, no deadlock.

**Local commands:** `docs.index`, `docs.read`, and `help` read files directly — they don't need HTTP.

### Authorization

Write commands (`assistant.create`, `assistant.update`, `assistant.delete`) require user confirmation. The agent pauses and asks the user before executing. Read commands (`assistant.list`, `kb.list`, `docs.read`, etc.) execute automatically.

Authorization is enforced at the Python level (not by the LLM), using a policy config:
- `auto` — execute immediately (all reads, tests, docs)
- `ask` — pause, get user approval (writes)
- `never` — blocked

### Skills

Skills are markdown files in `backend/lamb/aac/skills/` with YAML front matter:

```yaml
---
id: about-lamb
name: LAMB Helper
description: Answer questions about the LAMB platform
required_context: []
optional_context: [language]
startup_actions:
  - "lamb docs index"
---

# Skill: LAMB Helper
(skill instructions for the agent)
```

Startup actions run automatically when the skill launches (before the agent's first message). The skill prompt augments the agent's system prompt for the session.

### Session Persistence

Sessions are stored in the `aac_sessions` database table. The conversation, pending actions, skill info, and tool audit are serialized as a JSON envelope in the `conversation` column. Sessions survive server restarts and can be resumed from CLI or web UI.

### Session Logging

When `AAC_SESSION_LOGGING=true`, every session is logged as a JSONL file in the `AAC_LOG_PATH` directory. Each line is a structured event (message, tool call, error, etc.) for research and debugging.

---

## Output Formats

All listing commands support `-o json` for machine-readable output:

```bash
lamb aac sessions -o json
lamb aac tools <sid> -o json
lamb test scenarios 18 -o json
lamb test runs 18 -o json
```

---

## Tips

- **Always debug before real tests.** The `--bypass` flag shows the full pipeline for free. If RAG context is empty, fix that before spending tokens.
- **Let the agent lead.** Skills guide you through the right steps. You don't need to know the commands — the agent uses them for you.
- **Numbered options.** The agent ends each response with numbered choices. Pick one or type your own request.
- **Language.** Use `--lang` to set the agent's response language. The agent understands English commands regardless of response language.
- **Sessions persist.** You can close the terminal and come back. Use `lamb aac sessions` to find your session, then `lamb aac chat <sid>` to resume.
- **Use the Agent page.** In the web UI, the Agent page (`/agent`) is the fastest way to get help. It resumes your session from today automatically.
- **Toggle stats.** Click the tool stats indicator in the terminal header to see model, tool count, errors, and timing.

---

*LAMB AAC CLI Manual — Version 0.3*
*Updated: April 2026. Examples from a 1960s British Rock Music tutor assistant (id=18, KB=rock_the_60s)*
