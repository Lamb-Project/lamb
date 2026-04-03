# LAMB CLI Manual

**lamb-cli** is the command-line tool for managing the LAMB platform — assistants, knowledge bases, rubrics, templates, and more. It connects to any LAMB installation.

For the Agent-Assisted Creator (AAC) features, see the [AAC CLI Manual](lamb_aac_cli_manual.md).

---

## Installation

```bash
cd lamb-cli
uv venv .venv
uv pip install -e ".[dev]"
```

Or with pip:

```bash
cd lamb-cli
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running the CLI

After installation, the `lamb` command is available inside the virtual environment. You have two options:

**Option 1: Activate the venv first (recommended for interactive use)**

```bash
source .venv/bin/activate   # now 'lamb' is in your PATH
lamb status
lamb assistant list
```

**Option 2: Run directly without activation (good for scripting)**

```bash
.venv/bin/lamb status
.venv/bin/lamb assistant list
```

All examples in this manual use `lamb` assuming the venv is activated.

---

## Connecting to a LAMB Server

### Login

```
$ lamb login --server-url http://localhost:9099
Email: admin@owi.com
Password: ****
Logged in as Admin User (admin@owi.com)
```

You can also pass credentials directly for scripting:

```bash
lamb login --server-url http://localhost:9099 --email admin@owi.com --password admin
```

Credentials are stored locally in your platform's config directory:
- macOS: `~/Library/Application Support/lamb/credentials.toml`
- Linux: `~/.config/lamb/credentials.toml`

### Environment Variables

For CI/CD or scripting, environment variables take precedence:

| Variable | Description |
|----------|-------------|
| `LAMB_SERVER_URL` | Override server URL |
| `LAMB_TOKEN` | Override stored auth token |

```bash
LAMB_SERVER_URL=https://lamb.university.edu LAMB_TOKEN=eyJ... lamb assistant list -o json
```

### Check Connection

```
$ lamb status
Server is running at http://localhost:9099
```

### See Your Identity

```
$ lamb whoami
ID         1
Email      admin@owi.com
Name       Admin User
Role       admin
User Type  creator
Org Role   admin
```

### Logout

```bash
lamb logout
```

---

## Output Formats

Every listing command supports `-o` / `--output`:

| Flag | Description |
|------|-------------|
| `-o table` | Rich-formatted table (default) |
| `-o json` | JSON to stdout (pipe-safe) |
| `-o plain` | Tab-separated values |

```bash
# Pipe-friendly
lamb assistant list -o json | jq '.[].name'

# Tab-separated for awk
lamb assistant list -o plain | awk -F'\t' '{print $2}'
```

Data always goes to stdout; messages and errors go to stderr.

---

## Assistants

### List Your Assistants

Shows assistants you own. Does not include assistants shared with you by other users (this is a known limitation — see backlog item 11).

```
$ lamb assistant list

┃ ID ┃ Name                         ┃ Description                  ┃ Published ┃
│    │ 1_1960s_british_rock_tutor   │                              │           │
│    │ rock_the_60s                 │ Asistente especializado en   │           │
│    │                              │ el rock & roll de los años   │           │
│    │                              │ 60 en Inglaterra...          │           │
│    │ 1_pestlerubric1              │ Nom: pestle-rubric-1...      │           │
│    │ 1_rubrica01                  │ rubrica01 es un asistente... │           │
│    │ 1_Test                       │                              │           │
```

### Get Assistant Details

Get a single assistant by its numeric ID. Works for assistants you own, assistants shared with you, or (if you're an org admin) any assistant in your organization. Returns 404 if you don't have access.

```
$ lamb assistant get 18

ID
Name              1_1960s_british_rock_tutor
Description
System Prompt     You are a music history tutor for high school students. Teach
                  1960s British rock with a focus on the British blues revolution...
Published
Owner             admin@owi.com
Connector         openai
LLM               gpt-4o
Prompt Processor  simple_augment
RAG Processor     simple_rag
RAG Top-K
RAG Collections
```

### Show Available Configuration

Before creating an assistant, check what models, connectors, and processors are available in your organization:

```
$ lamb assistant config

Connectors & Models
  openai: gpt-5.4-mini, gpt-5.4, gpt-5.4-nano
  ollama: nomic-embed-text
  bypass: debug-bypass, simple-bypass, full-conversation-bypass

Prompt Processors
  simple_augment

RAG Processors
  context_aware_rag, simple_rag, rubric_rag, no_rag, ...

Organization Defaults
  connector: openai
  llm: gpt-5.4-mini
```

If your assistant will use a knowledge base, check what's available:

```
$ lamb kb list

┃ ID ┃ Name               ┃ Description ┃ Owner ┃ Shared ┃
│ 7  │ rock_the_60s       │             │ True  │ False  │
│ 6  │ test_advanced_shit │             │ True  │ False  │
```

You can also check rubrics if you plan to build an evaluator assistant:

```bash
lamb rubric list
```

### Create an Assistant

**Simple assistant (no RAG)** — the model answers from its training data:

```bash
lamb assistant create "History Tutor" \
  --system-prompt "You are a history tutor for high school students. Explain concepts clearly and quiz students to check understanding." \
  --llm gpt-5.4-mini \
  --connector openai \
  -d "General history tutor"
```

**Assistant with a knowledge base (RAG)** — the model uses your documents to answer:

```bash
# First, check which KB to use
lamb kb list
lamb kb get 7       # see files in KB 7

# Create the assistant, connecting it to the KB
lamb assistant create "60s Rock Tutor" \
  --system-prompt "You are a music history tutor. Use the provided context to answer questions about 1960s British rock." \
  --llm gpt-5.4-mini \
  --connector openai \
  --rag-processor simple_rag \
  --rag-collections "7" \
  --prompt-template "Context:\n{context}\n\nStudent question: {user_input}\n\nAnswer clearly and cite your sources." \
  -d "Music tutor grounded in KB documents"
```

When using RAG, the `--prompt-template` must include `{context}` (where KB content is inserted) and `{user_input}` (where the student's question goes). Without these placeholders, RAG content has nowhere to go.

**Evaluator assistant with rubric** — for grading student work:

```bash
lamb assistant create "PESTLE Evaluator" \
  --system-prompt "You evaluate student submissions using a rubric." \
  --llm gpt-5.4-mini \
  --connector openai \
  --rag-processor rubric_rag \
  --rubric-id "ed658548-11ab-494a-9d32-5b4b6e19b910" \
  --prompt-template "Rubric:\n{context}\n\nStudent work: {user_input}\n\nEvaluate using the rubric criteria."
```

**Interactive wizard** — if you prefer a guided setup:

```bash
lamb assistant create "My Assistant" --interactive
```

### Update an Assistant

Update only the fields you want to change. Other fields are preserved.

```bash
lamb assistant update 18 --llm gpt-4o --rag-processor context_aware_rag
```

### Delete an Assistant

```bash
lamb assistant delete 18
# Prompts for confirmation. Use --confirm/-y to skip.
```

### Publish / Unpublish

```bash
lamb assistant publish 18
lamb assistant unpublish 18
```

### Export

```bash
lamb assistant export 18 -o json
```

---

## Chat

Chat directly with an assistant from the terminal.

### Single Message

```
$ lamb chat 18 -m "Who were the Bluesbreakers?"

The Bluesbreakers were John Mayall's band, one of the most important groups
in the 1960s British blues revolution. Think of them as a training ground
for future rock legends...
```

### Interactive Mode

```
$ lamb chat 18

You: Who played guitar in the Bluesbreakers?
Assistant: The Bluesbreakers had several famous guitarists...

You: /quit
```

### Debug Bypass

See exactly what the LLM receives — system prompt, RAG context, processed prompt — without calling the model. Zero tokens.

```
$ lamb chat 18 --bypass -m "Who were the Bluesbreakers?"

Messages:
[
  {"role": "system", "content": "You are a music history tutor..."},
  {"role": "user", "content": "Context:\n...[KB content about Bluesbreakers]...\n
   Student question:\nWho were the Bluesbreakers?..."}
]
```

This is invaluable for verifying that RAG retrieval is working and the prompt template is correctly assembled.

---

## Knowledge Bases

### List

```
$ lamb kb list

┃ ID ┃ Name               ┃ Description ┃ Owner ┃ Shared ┃
│ 7  │ rock_the_60s       │             │ True  │ False  │
│ 6  │ test_advanced_shit │             │ True  │ False  │
│ 5  │ test_new_kb_dev    │             │ True  │ False  │
```

### Get Details

```
$ lamb kb get 7

ID           7
Name         rock_the_60s
Files        2
```

### Query

Test what a knowledge base returns for a given query:

```
$ lamb kb query 7 "British blues revolution"

┃ Similarity         ┃ Data                                                    ┃
│ 0.7152             │ The scene transformed American blues into British       │
│                    │ blues-rock, which then conquered the world...           │
│ 0.7114             │ ## The circular influence: British blues returns to     │
│                    │ America...                                              │
│ 0.7042             │ # The British Blues Revolution: From Chicago to London  │
│                    │ and Back Again...                                       │
```

### Other KB Commands

```bash
lamb kb create "My KB"              # Create
lamb kb update 7 --name "New Name"  # Rename
lamb kb delete 7                    # Delete (with confirmation)
lamb kb share 7 --enable            # Share with organization
lamb kb upload 7 document.pdf       # Upload files
lamb kb ingest 7                    # Ingest via plugin (URL, YouTube, etc.)
lamb kb plugins                     # List ingestion plugins
```

---

## Rubrics

Manage evaluation rubrics used by the EvaluAItor system.

### List

```
$ lamb rubric list

┃ Rubric ID     ┃ Title        ┃ Description   ┃ Criteria ┃ Max Score ┃ Public ┃
│ ed658548-11a… │ Rúbrica      │ Avaluació de  │ 7        │ 10.0      │ 0      │
│               │ d'Avaluació  │ l'anàlisi     │          │           │        │
│               │ - Anàlisi    │ PESTLE...     │          │           │        │
│ 13cc8a19-eda… │ Project      │ Assessment    │ 4        │ 10.0      │ 0      │
│               │ Presentation │ rubric for... │          │           │        │
```

### Get Details

```
$ lamb rubric get ed658548-11ab-494a-9d32-5b4b6e19b910

Rubric ID     ed658548-11ab-494a-9d32-5b4b6e19b910
Title         Rúbrica d'Avaluació - Anàlisi PESTLE del Robot Optimus de Tesla
Subject       Aspectes Socials i Medioambientals de la Informàtica
Scoring Type  points
Max Score     10.0
Criteria      Aspectes Polítics (13%) | Aspectes Econòmics (13%) | ... | Conclusió (22%)
```

### Export

```bash
# As JSON
lamb rubric export ed658548-... --format json --file rubric.json

# As markdown
lamb rubric export ed658548-... --format md
```

### AI-Generate

Generate a rubric from a natural language description (preview only, doesn't save):

```bash
lamb rubric generate "Rubric for evaluating oral presentations on climate change" --lang en --save-to rubric.json
```

### Other Rubric Commands

```bash
lamb rubric list-public         # Public rubrics (templates)
lamb rubric import rubric.json  # Import from file
lamb rubric share <id> --enable # Make public
lamb rubric delete <id>         # Delete
```

---

## Templates

Manage reusable prompt templates.

```
$ lamb template list

┃ ID ┃ Name                      ┃ Description                ┃ Shared ┃ Owner ┃
│ 1  │ Socratic Math Tutor       │ Guide students through     │ False  │ True  │
│    │                           │ mathematical problem-      │        │       │
│    │                           │ solving with questions      │        │       │
│ 2  │ Copy of Socratic Math     │ Guide students through     │ True   │ True  │
│    │ Tutor                     │ mathematical...            │        │       │
```

### Commands

```bash
lamb template get <id>                 # Details
lamb template create "Name"            # Create
lamb template update <id> --name "..."  # Update
lamb template delete <id>              # Delete
lamb template duplicate <id>           # Copy
lamb template share <id> --enable      # Share
lamb template export <ids...>          # Export as JSON
```

---

## Models

List models available for your organization:

```
$ lamb model list

┃ ID                ┃ Name ┃ Owned By                 ┃
│ lamb_assistant.1  │      │ LAMB System Organization │
│ lamb_assistant.4  │      │ LAMB System Organization │
│ lamb_assistant.18 │      │ LAMB System Organization │
```

Use `lamb assistant config` to see models by connector (openai, ollama, etc.).

---

## Analytics

View usage statistics for published assistants.

```
$ lamb analytics stats 4

Total Chats        5
Unique Users       2
Total Messages     10
Avg Messages/Chat  2.0
```

```
$ lamb analytics chats 4

┃ ID              ┃ Title           ┃ User       ┃ Messages ┃ Created At       ┃
│ 6b385e8f-aa35-… │ hola - Dec 30   │ Admin User │ 2        │ 2025-12-30T17:5… │
│ 2db03895-2a1e-… │ # Evaluación... │ Admin User │ 2        │ 2025-12-30T17:4… │
```

### Commands

```bash
lamb analytics stats <assistant-id>              # Usage stats
lamb analytics chats <assistant-id>              # Chat list
lamb analytics chat-detail <assistant-id> <cid>  # Full chat
lamb analytics timeline <assistant-id>           # Activity over time
```

---

## Testing Assistants

Create test scenarios, run them through the real pipeline, and evaluate results. See the [AAC CLI Manual](lamb_aac_cli_manual.md) for details.

```bash
lamb test add 18 "My test" -m "Sample question"  # Add scenario
lamb test scenarios 18                            # List scenarios
lamb test run 18                                  # Run all (real LLM)
lamb test run 18 --bypass                         # Run all (debug, 0 tokens)
lamb test runs 18                                 # List results
lamb test evaluate <run-id> 18 good               # Record evaluation
lamb test evaluations 18                          # List evaluations
```

---

## Agent-Assisted Creator (AAC)

The AI agent that helps you design, test, and improve assistants through conversation. See the [AAC CLI Manual](lamb_aac_cli_manual.md) for the full guide.

```bash
lamb aac skills                                        # Available skills
lamb aac start --skill improve-assistant --assistant 18 # Start session
lamb aac start --skill about-lamb                      # Get help about LAMB
lamb aac message <sid> "your message"                   # Send message
lamb aac chat <sid>                                     # Interactive mode
lamb aac tools <sid> --detail                           # Tool audit log
lamb aac sessions                                       # List sessions
lamb docs index                                         # List documentation topics
lamb docs read troubleshooting                          # Read a doc topic
```

---

## Organizations (Admin)

Manage organizations. Requires admin role.

```bash
lamb org list                                   # List orgs
lamb org get <slug>                             # Org details
lamb org create "Name"                          # Create
lamb org update <slug> --name "New Name"        # Update
lamb org delete <slug>                          # Delete
lamb org set-role <slug> <user-id> <role>       # Set user role
lamb org dashboard                              # Stats
lamb org export <slug>                          # Export as JSON
```

---

## Users (Admin)

Manage users. Requires admin role.

```bash
lamb user list                                  # List users
lamb user get <id>                              # User details
lamb user create email name password            # Create
lamb user update <id> --name "New Name"         # Update
lamb user delete <id>                           # Delete
lamb user enable <id>                           # Enable
lamb user disable <id>                          # Disable
lamb user reset-password <id> newpass           # Reset password
lamb user bulk-import users.json                # Bulk import
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Config/argument error |
| 2 | API error (4xx/5xx) |
| 3 | Network error |
| 4 | Authentication error |
| 5 | Not found (404) |

---

## Tips

- **Use `-o json` for scripting.** All commands support JSON output.
- **Debug your RAG pipeline.** `lamb chat <id> --bypass` shows what the LLM sees for free.
- **Let the agent help.** `lamb aac start --skill improve-assistant --assistant <id>` analyzes and suggests fixes.
- **Test before publishing.** `lamb test run <id>` runs your scenarios through the real pipeline.
- **Sessions persist.** AAC sessions are saved — use `lamb aac sessions` to find and resume them.

---

*LAMB CLI Manual — Version 0.7*
*All examples from a live LAMB instance running on localhost:9099*
