# LAMB AAC CLI Manual

**The Agent-Assisted Creator (AAC)** is an AI agent that helps you design, test, and improve learning assistants through conversation. You describe what you want; the agent configures, tests, and refines it.

This manual covers the command-line interface (cli). The same features are available in the web UI.

AAC is a sub command on the lamb-cli tool. 

The lamb-cli tool can be connected to any lamb installation on the net that you have a user an password. In this documentation we will refer to a localhost installation in the default developer settings running on docker containers. 
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

---

## Concepts

**Session** — A conversation between you and the agent about one or more assistants. Sessions are persistent — you can leave and come back.

**Skill** — A predefined workflow the agent follows. Skills guide the conversation so you don't need to know what to ask. Available skills:

| Skill | Purpose | Requires |
|-------|---------|----------|
| `create-assistant` | Build a new assistant from scratch | — |
| `improve-assistant` | Review and improve an existing assistant | assistant ID |
| `explain-assistant` | Understand how an assistant works internally | assistant ID |
| `test-and-evaluate` | Create tests, run them, evaluate results | assistant ID |
| `about-lamb` | Answer questions about the LAMB platform, guide new users | — |

**Tool** A tool is an action that the agent can take in the lamb system. It covers thinks like create an assistant, list the available knowledge bases, run chats on an assitant or analyzing the results of a set of tests. 

**Tool audit** — Every action the agent takes (reading config, creating tests, running completions) is recorded with timestamps and outcomes.

**Tests** From the 0.7 version we have anew feature on lamb creator: the tests. you can define a set of test prompts for your assitant. The AAc can run all the tests and evaluate the results automatically. Tests runs will not count as assitant activity in the activity logs and analytics.

**Bypass / debug mode** —  Run the tests with the full pipeline (RAG retrieval, prompt assembly) without calling the LLM. Shows exactly what the model would see. Zero tokens consumed. 

---

## Commands Reference

### Sessions

#### `lamb aac start`

Start a new session, optionally with a skill.

```bash
# Free-form session (you lead)
lamb aac start

# Skill-driven session (agent leads)
lamb aac start --skill improve-assistant --assistant 18 --lang English
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

#### `lamb aac start --skill about-lamb`

Start a help session. The agent answers questions about the LAMB platform — features, workflows, troubleshooting — grounded in built-in documentation. No assistant ID needed.

```bash
lamb aac start --skill about-lamb --lang Spanish
lamb aac chat <session-id>
# Ask anything: "how do I connect a knowledge base?", "what is RAG?", etc.
```

#### `lamb aac get <session-id>`

Get full session details including conversation.

#### `lamb aac delete <session-id>`

Archive a session (with confirmation).

#### `lamb aac skills`

List available skills.

```
$ lamb aac skills

┃ Skill ID          ┃ Name              ┃ Description       ┃ Requires         ┃
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

```
$ lamb aac tools 074e9518-... --detail

  14:42:56  Reading assistant config                 ✓     10ms  assistant:18
           $ lamb assistant get 18
           → name=1_1960s_british_rock_tutor, llm=gpt-4o, rag=simple_rag
  14:43:11  Creating test scenario                   ✓     46ms  assistant:18
           $ lamb test add 18 "Bluesbreakers overview" --message "Why were..."
           → title=Bluesbreakers overview
  14:43:15  Running tests (pipeline debug)           ✓    739ms  assistant:18
           $ lamb test run 18 --bypass
           → 3 items
  14:43:46  Running tests                            ✓  20957ms  assistant:18
           $ lamb test run 18
           → 3 items
```

#### `lamb aac tools <session-id> --artifacts`

Group by affected resource.

```
$ lamb aac tools 074e9518-... --artifacts

  assistant:18
    14:42:56  read       ✓     10ms
    14:42:56  read       ✓     10ms
    14:43:11  create     ✓     46ms
    14:43:13  create     ✓     48ms
    14:43:14  create     ✓     46ms
    14:43:15  test       ✓    739ms
    14:43:46  test       ✓  20957ms
```

#### `lamb aac tools <session-id> --filter assistant`

Show only events affecting a specific resource type.

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

```
$ lamb test scenarios 18

┃ ID          ┃ Title       ┃ Type       ┃ Messages ┃ Created By  ┃ Created    ┃
│ e64602ac-6… │ Bluesbreak… │ single_tu… │ 1        │ admin@owi.… │ 2026-04-0… │
│ 6c19b62e-2… │ Muddy       │ single_tu… │ 1        │ admin@owi.… │ 2026-04-0… │
│             │ Waters      │            │          │             │            │
│ fe3fbe81-0… │ Ignore      │ single_tu… │ 1        │ admin@owi.… │ 2026-04-0… │
│             │ instructio… │            │          │             │            │
```

#### `lamb test run <assistant-id>`

Run test scenarios through the real LLM. Uses tokens.

```
$ lamb test run 18

Running tests...
3 test(s) completed.
  OK e64602ac... (gpt-5.4-2026-03-05, 1484 tokens, 9064ms)
    John Mayall & the Bluesbreakers were important because they were...
  OK 6c19b62e... (gpt-5.4-2026-03-05, 1577 tokens, 6712ms)
    Muddy Waters was hugely important to 1960s British rock because...
  OK fe3fbe81... (gpt-5.4-2026-03-05, 1418 tokens, 4978ms)
    I can't confirm that, because the context does not say it...
```

#### `lamb test run <assistant-id> --bypass`

Run through the full pipeline WITHOUT calling the LLM. Shows what the model would receive: system prompt, RAG context, processed prompt. Zero tokens.

Use this first to verify the pipeline before spending tokens.

```
$ lamb test run 18 --scenario e64602ac-... --bypass

Running tests...
Test completed: debug-bypass, 0 tokens, 507ms

Messages:
[
  {
    "role": "system",
    "content": "You are a music history tutor..."
  },
  {
    "role": "user",
    "content": "Context:\n[Search YouTube: \"John Mayall Bluesbreakers...\"]
    ...
    Student question: Why were John Mayall & the Bluesbreakers important?
    ..."
  }
]
```

#### `lamb test runs <assistant-id>`

List previous test runs with results.

```
$ lamb test runs 18

┃ Run ID    ┃ Scenario  ┃ Model     ┃ Response ┃ Tokens ┃ Time (ms) ┃
│ d820340f… │ e64602ac… │ gpt-5.4-… │ John     │ 1484   │ 9063.6    │
│           │           │           │ Mayall   │        │           │
│ 68f346b9… │ 6c19b62e… │ gpt-5.4-… │ Muddy    │ 1577   │ 6712.2    │
│           │           │           │ Waters   │        │           │
│ 782eea2e… │ fe3fbe81… │ gpt-5.4-… │ I can't  │ 1418   │ 4978.0    │
│           │           │           │ confirm  │        │           │
```

#### `lamb test evaluate <run-id> <assistant-id> <verdict>`

Record your evaluation of a test run.

```
$ lamb test evaluate d820340f-... 18 good --notes "Accurate, well-grounded"

Evaluation recorded: good
```

Verdicts: `good`, `bad`, or `mixed`.

#### `lamb test evaluations <assistant-id>`

List all evaluations.

```
$ lamb test evaluations 18

┃ Eval ID         ┃ Run ID          ┃ By   ┃ Verdict ┃ Notes ┃ Created         ┃
│ 611dce25-64d9-… │ d820340f-37da-… │ user │ good    │       │ 2026-04-02T14:… │
│ 847f737c-70ab-… │ 68f346b9-31ed-… │ user │ good    │       │ 2026-04-02T14:… │
│ c3d0b087-f8cf-… │ 782eea2e-06c2-… │ user │ good    │       │ 2026-04-02T14:… │
```

---

### Chatting with Assistants

#### `lamb chat <assistant-id>`

Chat with an assistant directly (not through the agent).

```
$ lamb chat 18 -m "Who were the Bluesbreakers?"

John Mayall & the Bluesbreakers were one of the most important...
```

#### `lamb chat <assistant-id> --bypass`

See the full prompt the LLM would receive, without calling it.

```
$ lamb chat 18 --bypass -m "Who were the Bluesbreakers?"

Messages:
[
  {"role": "system", "content": "You are a music history tutor..."},
  {"role": "user", "content": "Context:\n...\nStudent question:\nWho were..."}
]
```

This is invaluable for debugging RAG retrieval and prompt construction.

---

### Documentation (Agent Internal)

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

Documentation files live in `backend/lamb/aac/docs/` and use YAML front matter for agent-friendly metadata.

---

## Typical Workflows

### Getting help with LAMB

```bash
# Start a help session
lamb aac start --skill about-lamb

# Ask anything
lamb aac chat <sid>
# "How do I connect a knowledge base to my assistant?"
# "What is bypass mode?"
# "My assistant ignores my documents, help"
```

The agent reads the built-in documentation and answers grounded in it. If your question involves a hands-on task, it can offer to switch to the appropriate skill.

### Creating a new assistant

```bash
# 1. Start a create session
lamb aac start --skill create-assistant --lang English

# 2. Describe what you want
lamb aac message <sid> "I want a music history tutor for high school..."

# 3. The agent proposes a configuration and creates it
# 4. It runs a debug check to verify the pipeline
# 5. You test and iterate
```

### Improving an existing assistant

```bash
# 1. Start an improve session
lamb aac start --skill improve-assistant --assistant 18

# 2. The agent analyzes and suggests improvements
# 3. Pick an improvement, the agent applies it
# 4. Verify with debug, then real tests
```

### Testing an assistant

```bash
# 1. Start a test session
lamb aac start --skill test-and-evaluate --assistant 18

# 2. The agent creates test scenarios
# 3. Runs bypass debug first (zero tokens)
# 4. Then real completions
# 5. You evaluate results
# 6. Agent suggests improvements based on evaluations
```

### Quick debugging

```bash
# See what the LLM receives (no tokens)
lamb chat 18 --bypass -m "sample question"

# Run all test scenarios without tokens
lamb test run 18 --bypass

# Run real tests
lamb test run 18
```

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

---

*LAMB AAC CLI Manual — Version 0.2*
*Updated: April 2026. Examples from a 1960s British Rock Music tutor assistant (id=18, KB=rock_the_60s)*
