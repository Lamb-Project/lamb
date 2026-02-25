# lamb-cli Tutorial

A hands-on guide to managing your LAMB platform from the terminal.

## Prerequisites

- A running LAMB server (local or remote)
- lamb-cli installed (`pip install -e ".[dev]"` from the `lamb-cli/` directory)
- A creator account on the LAMB platform

## 1. Connect to a Server

First, check that your LAMB server is reachable:

```bash
lamb status
# Server is running at http://localhost:9099
```

If your server is somewhere else, specify the URL:

```bash
lamb status --server-url https://lamb.university.edu
```

**Tip:** You can also set the server URL via environment variable:

```bash
export LAMB_SERVER_URL=https://lamb.university.edu
```

## 2. Log In

```bash
lamb login
```

You'll be prompted for your email and password. To skip the prompts (useful for scripting):

```bash
lamb login --email you@example.com --password yourpassword
```

To connect to a specific server and log in at the same time:

```bash
lamb login --server-url https://lamb.university.edu
```

The server URL is saved — you won't need to pass it again.

Verify your session:

```bash
lamb whoami
```

This shows your user info, role, and organization permissions.

## 3. Where Are My Credentials Stored?

After login, your session token and config are saved locally:

| Platform | Location |
|----------|----------|
| macOS    | `~/Library/Application Support/lamb/` |
| Linux    | `~/.config/lamb/` |
| Windows  | `C:\Users\<you>\AppData\Local\lamb\` |

Two files live there:
- `credentials.toml` — your auth token and user info (permissions restricted to your user)
- `config.toml` — server URL and output preferences

To log out and clear your credentials:

```bash
lamb logout
```

## 4. Working with Assistants

### List your assistants

```bash
lamb assistant list
```

### Check available connectors and models

Before creating an assistant, see what's available on your server:

```bash
lamb assistant config
```

This shows all connectors (e.g. `openai`, `ollama`), their models, prompt processors, RAG processors, and your organization's defaults. For machine-readable output:

```bash
lamb assistant config -o json
```

### Create an assistant — Interactive Wizard

The easiest way to create a fully configured assistant is the interactive wizard. When you run `create` from a terminal without any configuration flags, the wizard starts automatically:

```bash
lamb assistant create "Math Tutor" \
  --description "Helps students with algebra and calculus" \
  --system-prompt "You are a patient math tutor. Explain concepts step by step."
```

The wizard walks you through each setting with numbered menus:

```
--- Assistant Configuration Wizard ---

Select a connector:
  1. openai (default)
  2. ollama
Choose [openai]: 1

Select an LLM model:
  1. gpt-4o
  2. gpt-4o-mini (default)
Choose [gpt-4o-mini]: 2

Select a prompt processor:
  1. simple_augment (default)
  2. context_augment
Choose [simple_augment]:

Select a RAG processor:
  1. no_rag (default)
  2. simple_rag
  3. context_aware_rag
Choose [no_rag]:

Enable vision? [y/N]:
Enable image generation? [y/N]:
```

You can also force the wizard with `--interactive` / `-i`:

```bash
lamb assistant create "My Bot" -i
```

### Create an assistant — Scripting with Flags

For CI/CD and scripts, pass configuration directly as flags:

```bash
lamb assistant create "Math Tutor" \
  --description "Helps with algebra" \
  --system-prompt "You are a math tutor." \
  --connector openai \
  --llm gpt-4o-mini \
  --prompt-processor simple_augment \
  --rag-processor no_rag
```

If you only specify some flags, the rest are filled from your organization's server defaults:

```bash
# Only specify the model — connector, processors come from org defaults
lamb assistant create "Quick Bot" --llm gpt-4o
```

Additional options:

```bash
# Enable vision capability
lamb assistant create "Vision Bot" --connector openai --llm gpt-4o --vision

# Enable image generation
lamb assistant create "Art Bot" --connector openai --llm gpt-4o --image-generation

# Set RAG parameters
lamb assistant create "RAG Bot" --rag-top-k 5 --rag-collections "collection1,collection2"
```

For longer system prompts, use a file:

```bash
lamb assistant create "Essay Coach" \
  --description "Writing feedback assistant" \
  --system-prompt-file ./prompts/essay-coach.txt \
  --connector openai --llm gpt-4o-mini
```

### View assistant details

```bash
lamb assistant get <assistant-id>
```

The detail view shows the full configuration including connector, LLM, prompt processor, and RAG processor extracted from the assistant's metadata.

### Update an assistant

Only the fields you pass will change:

```bash
lamb assistant update <assistant-id> --name "Advanced Math Tutor"
lamb assistant update <assistant-id> --system-prompt "Updated instructions..."
```

You can also update the LLM configuration. The CLI fetches the current metadata and merges your changes:

```bash
# Switch to a different model (keeps connector and processors unchanged)
lamb assistant update <assistant-id> --llm gpt-4o

# Enable vision on an existing assistant
lamb assistant update <assistant-id> --vision

# Change the RAG processor
lamb assistant update <assistant-id> --rag-processor context_aware_rag
```

Or re-configure everything with the interactive wizard:

```bash
lamb assistant update <assistant-id> --interactive
```

### Publish and unpublish

Publishing makes the assistant available to end-users in the chat interface:

```bash
lamb assistant publish <assistant-id>
lamb assistant unpublish <assistant-id>
```

### Delete an assistant

```bash
lamb assistant delete <assistant-id>
```

You'll be asked to confirm. To skip the prompt (useful in scripts):

```bash
lamb assistant delete <assistant-id> --confirm
```

### Export an assistant

Save the full configuration as JSON:

```bash
lamb assistant export <assistant-id> -f backup.json
```

## 5. Working with Knowledge Bases

Knowledge bases let your assistants answer questions using your own documents — lecture notes, textbooks, lab manuals, web pages, videos.

### Create a knowledge base

```bash
lamb kb create "CS101 Readings" --description "Intro to Computer Science course materials"
```

### List your knowledge bases

```bash
lamb kb list
```

### Upload documents

Upload one or more files at once:

```bash
lamb kb upload <kb-id> syllabus.pdf chapter1.pdf chapter2.pdf
```

You'll see a progress bar during upload.

### Ingest from the web

Use ingestion plugins to pull content from URLs or YouTube:

```bash
# See what plugins are available
lamb kb plugins

# Ingest a web page
lamb kb ingest <kb-id> --plugin web_scraper --url https://example.com/article

# Ingest a YouTube video (transcript)
lamb kb ingest <kb-id> --plugin youtube --youtube https://youtube.com/watch?v=abc123
```

Plugins can accept custom parameters:

```bash
lamb kb ingest <kb-id> --plugin custom_scraper --param depth=2 --param format=markdown
```

### Query a knowledge base

Test your KB by searching it directly:

```bash
lamb kb query <kb-id> "What is Big-O notation?"
```

Tune the search:

```bash
lamb kb query <kb-id> "sorting algorithms" --top-k 10 --threshold 0.5
```

### Share a knowledge base

Let other creators in your organization use your KB:

```bash
lamb kb share <kb-id> --enable
```

See shared KBs from others:

```bash
lamb kb list-shared
```

Disable sharing:

```bash
lamb kb share <kb-id> --disable
```

### Delete a file from a KB

```bash
lamb kb delete-file <kb-id> <file-id> --confirm
```

### Delete a knowledge base

```bash
lamb kb delete <kb-id> --confirm
```

## 6. Monitoring Ingestion Jobs

When you upload files or ingest content, LAMB processes them in the background. Use job commands to monitor progress.

### List jobs for a KB

```bash
lamb job list <kb-id>
```

Filter by status:

```bash
lamb job list <kb-id> --status failed
lamb job list <kb-id> --status processing
```

### Watch a job in real time

```bash
lamb job watch <kb-id> <job-id>
```

This shows a live progress bar that updates every 3 seconds. It exits automatically when the job completes, fails, or is cancelled. Change the poll interval:

```bash
lamb job watch <kb-id> <job-id> --interval 1
```

### Get job details

```bash
lamb job get <kb-id> <job-id>
```

### Ingestion status summary

See an overview of all jobs for a KB:

```bash
lamb job status <kb-id>
```

### Retry a failed job

```bash
lamb job retry <kb-id> <job-id>
```

### Cancel a running job

```bash
lamb job cancel <kb-id> <job-id>
```

## 7. Output Formats

Every list and detail command supports three output formats via `-o`:

### Table (default)

```bash
lamb assistant list
```

Produces a formatted table — great for browsing interactively.

### JSON

```bash
lamb assistant list -o json
```

Machine-readable output, ideal for piping to `jq`:

```bash
# Get just the names
lamb assistant list -o json | jq '.[].name'

# Count assistants
lamb assistant list -o json | jq length

# Find published ones
lamb assistant list -o json | jq '[.[] | select(.publish_status == true)]'
```

### Plain

```bash
lamb assistant list -o plain
```

Tab-separated values, one row per line — works with `awk`, `cut`, `grep`:

```bash
# Get the second column (names)
lamb assistant list -o plain | awk -F'\t' '{print $2}'

# Filter by name
lamb kb list -o plain | grep "CS101"
```

**Design note:** Data goes to stdout, messages go to stderr. This means you can safely pipe output without status messages mixing in.

## 8. List Available Models

See which LLM models are configured on the server:

```bash
lamb model list
```

## 9. Scripting and CI/CD

### Environment variables

For automation, use environment variables instead of `lamb login`:

```bash
export LAMB_SERVER_URL=https://lamb.prod.edu
export LAMB_TOKEN=eyJhbGciOiJIUz...

lamb assistant list -o json
```

### Exit codes

The CLI uses specific exit codes for scripting:

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Config or argument error |
| 2    | API error (server returned 4xx/5xx) |
| 3    | Network error (server unreachable) |
| 4    | Authentication error |
| 5    | Resource not found |

Example:

```bash
lamb status || echo "Server is down!"

lamb assistant get "$ID" 2>/dev/null
if [ $? -eq 5 ]; then
  echo "Assistant not found, creating..."
  lamb assistant create "New Bot" --connector openai --llm gpt-4o-mini
fi
```

### Putting it together

A simple script to back up all assistants:

```bash
#!/bin/bash
set -e

mkdir -p backups

for id in $(lamb assistant list -o json | jq -r '.[].assistant_id'); do
  lamb assistant export "$id" -f "backups/${id}.json"
  echo "Exported $id"
done
```

## 10. Getting Help

Every command has built-in help:

```bash
lamb --help
lamb kb --help
lamb kb upload --help
lamb job watch --help
```

The version is printed to stderr on every command execution, so you always know which version you're running.

## 11. Managing Organizations (Admin)

Organization commands require admin privileges. They let you create, configure, and monitor the multi-tenant structure of your LAMB platform.

### List organizations

```bash
lamb org list
```

### Get organization details

```bash
lamb org get university-a
```

### Create an organization

```bash
lamb org create "University A" --slug university-a
```

Assign an admin during creation:

```bash
lamb org create "University A" --slug university-a --admin-user-id user-123
```

Enable self-signup with a key:

```bash
lamb org create "Open Lab" --slug open-lab --signup-enabled --signup-key secret123
```

### Update an organization

```bash
lamb org update university-a --name "University A (Renamed)"
lamb org update university-a --status inactive
```

### Delete an organization

```bash
lamb org delete university-a --confirm
```

### Export an organization

Save the full organization data (members, assistants, etc.) as JSON:

```bash
lamb org export university-a -f backup.json
```

### Set a user's role within an organization

```bash
lamb org set-role university-a user-123 admin
lamb org set-role university-a user-456 member
```

### View organization dashboard

```bash
lamb org dashboard
```

System admins can view a specific org's dashboard:

```bash
lamb org dashboard --org university-a
```

## 12. Managing Users (Admin)

User commands let org admins and system admins manage user accounts. System admins can pass `--org <slug>` to target a specific organization.

### List users

```bash
lamb user list
```

System admin targeting a specific org:

```bash
lamb user list --org university-a
```

### Get user details

```bash
lamb user get <user-id>
```

### Create a user

```bash
lamb user create alice@uni.edu "Alice Smith" password123
```

Create an end-user (instead of the default creator):

```bash
lamb user create student@uni.edu "Student One" pass --user-type end_user
```

Create a user in disabled state:

```bash
lamb user create pending@uni.edu "Pending User" pass --disabled
```

### Update a user

```bash
lamb user update <user-id> --name "Alice Renamed"
```

### Enable and disable users

```bash
lamb user enable <user-id>
lamb user disable <user-id>
```

### Reset a user's password

```bash
lamb user reset-password <user-id> newpassword456
```

### Delete a user

```bash
lamb user delete <user-id> --confirm
```

### Bulk import users

Prepare a JSON file:

```json
{
  "version": "1.0",
  "users": [
    {"email": "a@uni.edu", "name": "User A", "user_type": "creator", "enabled": true},
    {"email": "b@uni.edu", "name": "User B", "user_type": "creator", "enabled": true}
  ]
}
```

Validate first with `--dry-run`:

```bash
lamb user bulk-import users.json --dry-run
```

Then execute the import:

```bash
lamb user bulk-import users.json
```

## 13. Prompt Templates

Prompt templates let you save and reuse system prompts and prompt structures across assistants.

### List your templates

```bash
lamb template list
```

With pagination:

```bash
lamb template list --limit 10 --offset 20
```

### List shared templates

See templates shared by others in your organization:

```bash
lamb template list-shared
```

### Get template details

```bash
lamb template get <template-id>
```

### Create a template

```bash
lamb template create "Socratic Tutor" \
  --description "Ask guiding questions instead of giving answers" \
  --system-prompt "You are a Socratic tutor. Never give direct answers." \
  --prompt-template "Student question: {{question}}"
```

Share it with your organization immediately:

```bash
lamb template create "Essay Feedback" --shared \
  --system-prompt "Provide structured writing feedback."
```

### Update a template

```bash
lamb template update <template-id> --name "Improved Tutor"
lamb template update <template-id> --system-prompt "Updated instructions..."
```

### Duplicate a template

Copy an existing template (yours or shared):

```bash
lamb template duplicate <template-id>
lamb template duplicate <template-id> --new-name "My Copy"
```

### Share a template

```bash
lamb template share <template-id> --enable
lamb template share <template-id> --disable
```

### Export templates

Export one or more templates as JSON:

```bash
# To stdout
lamb template export 1 2 3

# To a file
lamb template export 1 2 3 -f templates-backup.json
```

### Delete a template

```bash
lamb template delete <template-id> --confirm
```

## 14. Assistant Analytics

View chat analytics and usage statistics for your assistants.

### List chats

```bash
lamb analytics chats <assistant-id>
```

Filter by user, content, or date range:

```bash
lamb analytics chats <assistant-id> \
  --user-id u123 \
  --search "algorithm" \
  --start-date 2024-01-01 \
  --end-date 2024-01-31
```

### View chat detail

See the full message history of a chat:

```bash
lamb analytics chat-detail <assistant-id> <chat-id>
```

### Usage statistics

Get aggregate stats for an assistant:

```bash
lamb analytics stats <assistant-id>
```

With a date range:

```bash
lamb analytics stats <assistant-id> --start-date 2024-01-01 --end-date 2024-01-31
```

### Activity timeline

See chat activity over time:

```bash
lamb analytics timeline <assistant-id>
lamb analytics timeline <assistant-id> --period week
lamb analytics timeline <assistant-id> --period month --start-date 2024-01-01
```

## 15. Chat

Chat with a learning assistant directly from the terminal.

### Single message

```bash
lamb chat <assistant-id> --message "What is Big-O notation?"
```

The response streams to stdout in real time.

### Interactive mode

Run without `--message` for a REPL:

```bash
lamb chat <assistant-id>
```

Type messages and see responses. Type `/quit` to exit.

### Continue a conversation

Use `--chat-id` to continue a previous chat:

```bash
lamb chat <assistant-id> --chat-id <chat-id> --message "Tell me more"
```

### Disable chat persistence

By default, chat history is saved on the server. To disable:

```bash
lamb chat <assistant-id> --message "Quick question" --no-persist
```

### Pipe mode

Pipe text from another command:

```bash
echo "Explain this code" | lamb chat <assistant-id>
cat essay.txt | lamb chat <assistant-id>
```
