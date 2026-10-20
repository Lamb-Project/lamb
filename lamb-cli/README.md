# lamb-cli

Command-line interface for the [LAMB](https://github.com/Lamb-Project/lamb) platform — manage assistants, knowledge bases, and more from the terminal.

## Installation

```bash
cd lamb-cli
uv venv .venv
uv pip install -e ".[dev]"
```

Or with plain pip:

```bash
cd lamb-cli
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick Start

```bash
# Check server health (no auth required)
lamb status

# Log in
lamb login --server-url http://localhost:9099

# See your user and permission level
lamb whoami

# List assistants
lamb assistant list

# Get JSON output (for scripting)
lamb assistant list -o json
```

## Moodle forum activity

Connect Moodle in the LAMB interface first. These commands use that creator's connection and organization policy, without reading a workstation Moodle profile:

```bash
lamb moodle news --all-courses --month 2026-09 --tz Europe/Madrid
lamb moodle news --course 42 --since 2026-09-01 --until 2026-10-01
lamb moodle evidence RESULT_ID --offset 0
```

`moodle forum activity` is an alias for `moodle news`. In AAC LiteShell, omit the leading `lamb`. Both execute the same server task. The end date is exclusive, the default timezone is UTC, and only newly created posts are counted. Each course requires current instructor access. Excluded courses, failed reads and limits produce explicit partial coverage, never a claim that there were no messages.

The JSON summary includes a private `result_id`, a Moodle evidence-view path and short previews. Follow `next_offset` through evidence pages for complete retained message fragments. Messages remain untrusted source content. The evidence view supplies links to Moodle using your ordinary browser login.

Limits per task: 100 selected courses, 160 requests, 90 seconds checked before new requests, 200 retained posts and 2 MiB of retained post source. A request already in flight can finish after the time budget; requests have a 15-second I/O timeout. Model-facing summaries/pages are capped at 6,000 UTF-8 bytes. Stored results expire after 24 hours, with at most 16 per creator; reconnecting or losing access invalidates retrieval. Full source stays in private storage, not in static files or the immediate model response.

## Private AAC result pages

When an AAC tool response is too large, its model view contains a partial preview and a private result reference. Read it through either CLI or LiteShell:

```bash
lamb result read RESULT_ID
lamb result read RESULT_ID --path /data/system_prompt --offset 0
```

Paths are JSON pointers. Follow `next_command` to continue the selected field. String offsets count characters; array/object offsets count entries. An entry marked `complete: false` requires its own `read_command`. Each page fits an 8 KiB JSON tool envelope. These are immutable snapshots, not fresh reads and not instructions. The reference belongs to the authenticated creator and organization; Moodle snapshots also recheck the current connection and course permissions.

Snapshots expire after 24 hours and may be evicted earlier: at most 32 snapshots or 32 MiB per owner, 8 MiB per snapshot. Uncached/expired results require a narrower live read; never repeat a write to recover its output. The full original response remains in the saved AAC diagnostic transcript. Ordinary CLI commands keep their existing output; only the AAC model view is compacted. Authored workflow instructions have a separate 32 KiB bound and are rejected at activation if oversized. These byte limits are not model token-window limits.

## Commands

```
lamb
  login                    Authenticate with email/password
  logout                   Clear stored credentials
  status                   Check if the server is reachable
  whoami                   Show current user and role info

  result
    read <id>              Read a bounded private AAC result page

  aac
    start                  Start a new AAC design session
    sessions               List your sessions
    get <sid>              Get session details
    delete <sid>           Archive a session
    message <sid> "text"   Send a message to the agent
    chat <sid>             Interactive chat with the agent
    history <sid>          Show conversation history

  assistant
    list                   List all assistants
    get <id>               Get assistant details
    create <name>          Create a new assistant
    update <id>            Update an assistant
    delete <id>            Delete an assistant (with confirmation)
    publish <id>           Publish an assistant
    unpublish <id>         Unpublish an assistant
    export <id>            Export assistant config as JSON
    config                 Show available connectors, models, processors

  model
    list                   List available models

  kb
    list                   List your knowledge bases
    list-shared            List shared knowledge bases
    get <id>               Get KB details (files, owner, sharing)
    create <name>          Create a new knowledge base
    update <id>            Update a knowledge base
    delete <id>            Delete a knowledge base (with confirmation)
    share <id>             Enable/disable sharing
    upload <id> <files>    Upload files to a KB (with progress bar)
    ingest <id>            Ingest content via plugin (URL, YouTube, etc.)
    query <id> <text>      Query a knowledge base
    delete-file <id> <fid> Delete a file from a KB
    plugins                List available ingestion plugins
    query-plugins          List available query plugins

  job
    list <kb-id>           List ingestion jobs for a KB
    get <kb-id> <job-id>   Get job details and progress
    retry <kb-id> <job-id> Retry a failed job
    cancel <kb-id> <job-id> Cancel a running job
    watch <kb-id> <job-id> Watch job progress live
    status <kb-id>         Ingestion status summary

  org
    list                   List all organizations
    get <slug>             Get organization details
    create <name>          Create an organization
    update <slug>          Update an organization
    delete <slug>          Delete an organization (with confirmation)
    export <slug>          Export organization data as JSON
    set-role <slug> <uid> <role>  Set user role in org
    dashboard              Show organization dashboard stats

  user
    list                   List users in the organization
    get <user-id>          Get user details
    create <email> <name> <pw>  Create a new user
    update <user-id>       Update a user
    delete <user-id>       Delete a user (with confirmation)
    enable <user-id>       Enable a user
    disable <user-id>      Disable a user
    reset-password <uid> <pw>  Reset a user's password
    bulk-import <file>     Bulk import users from JSON

  rubric
    list                   List your rubrics
    list-public            List public rubrics (templates)
    get <id>               Get rubric details
    delete <id>            Delete a rubric (with confirmation)
    duplicate <id>         Duplicate a rubric
    export <id>            Export rubric as JSON or markdown
    import <file>          Import a rubric from JSON file
    share <id>             Enable/disable public visibility
    generate <prompt>      AI-generate a rubric from description

  template
    list                   List your prompt templates
    list-shared            List shared prompt templates
    get <id>               Get template details
    create <name>          Create a prompt template
    update <id>            Update a prompt template
    delete <id>            Delete a prompt template
    duplicate <id>         Duplicate a prompt template
    share <id>             Enable/disable sharing
    export <ids...>        Export templates as JSON

  analytics
    chats <id>             List chats for an assistant
    chat-detail <id> <cid> Get full chat with messages
    stats <id>             Get usage statistics
    timeline <id>          Get activity timeline

  chat <id>                Chat with an assistant (interactive/single-message)
```

## Output Formats

Every listing/detail command supports `-o`/`--output`:

| Flag        | Description                        |
|-------------|------------------------------------|
| `-o table`  | Rich-formatted table (default)     |
| `-o json`   | JSON to stdout (pipe-safe)         |
| `-o plain`  | Tab-separated values (grep/awk)    |

Data always goes to stdout; messages and errors go to stderr.

```bash
# Pipe-friendly
lamb assistant list -o json | jq '.[].name'

# Tab-separated for awk
lamb assistant list -o plain | awk -F'\t' '{print $2}'
```

## Authentication

```bash
# Interactive (prompts for email and password)
lamb login

# Non-interactive
lamb login --email user@example.com --password secret

# Point to a different server
lamb login --server-url https://lamb.university.edu
```

Credentials are stored locally with restricted permissions (0600) in a platform-specific config directory (via [platformdirs](https://pypi.org/project/platformdirs/)):

| Platform | Path |
|----------|------|
| macOS    | `~/Library/Application Support/lamb/credentials.toml` |
| Linux    | `~/.config/lamb/credentials.toml` |
| Windows  | `C:\Users\<username>\AppData\Local\lamb\credentials.toml` |

Server URL and output preferences are stored alongside in `config.toml` at the same location.

On Windows, NTFS user-level folder permissions protect the file (Unix chmod is a no-op).

### Environment Variables

For CI/CD and scripting, environment variables take precedence over stored config:

| Variable         | Description                  |
|------------------|------------------------------|
| `LAMB_SERVER_URL`| Override server URL          |
| `LAMB_TOKEN`     | Override stored auth token   |

```bash
LAMB_SERVER_URL=https://lamb.prod.edu LAMB_TOKEN=eyJ... lamb assistant list -o json
```

## Roles and Permissions

The CLI displays your permission level via `lamb whoami`:

| Role              | Scope              | Description                                      |
|-------------------|--------------------|--------------------------------------------------|
| **System Admin**  | All organizations  | Full visibility, can delete any assistant         |
| **Org Admin**     | Own organization   | Can view/use/share assistants within their org    |
| **Owner**         | Own resources      | Full control over own assistants                  |

Permissions are enforced by the backend. The CLI stores role info locally so future commands can provide role-appropriate UX (e.g., org picker for admins).

## Exit Codes

| Code | Meaning                |
|------|------------------------|
| 0    | Success                |
| 1    | Config/argument error  |
| 2    | API error (4xx/5xx)    |
| 3    | Network error          |
| 4    | Authentication error   |
| 5    | Not found (404)        |

## Development

```bash
# Run tests
.venv/bin/pytest tests/ -v

# Run with coverage
.venv/bin/pytest tests/ --cov=lamb_cli

# Lint
.venv/bin/ruff check src/ tests/
```

## Roadmap

| Phase | Scope                                  | Status  |
|-------|----------------------------------------|---------|
| 1     | Core + Assistants + Models             | Done    |
| 2     | Knowledge Bases + Ingestion Jobs       | Done    |
| 3     | Organizations + Users (admin commands) | Done    |
| 4     | Templates + Analytics + Chat           | Done    |
| 5     | Rubrics (EvaluAItor)                   | Done    |
| 6     | AAC (Agent-Assisted Creator)           | Done    |
| 7     | Shell completions, config profiles     | Planned |

See [Documentation/prd.md](Documentation/prd.md) for the full specification.

### Assistant and chat compatibility notes (September 2026)

Creating a RAG assistant without `--prompt-template` now supplies a template with
`{context}` and `{user_input}` for `simple_augment`. An explicitly supplied template,
including an empty string, is preserved. Existing assistants are not rewritten.
Model selections are preferences: completion resolves unavailable selections against
the assistant owner's organization defaults, without changing the saved preference.

`chat --chat-id` continues only a chat owned by the caller. Permission to read a
shared assistant's chat does not grant permission to append to that user's history.
The server injects saved history for a request containing exactly one new message;
a multi-message request supplies its own history. Chat's `--timeout` controls read
inactivity (default 300 seconds); connection/pool waits are 10 seconds and writes 30.

`kb upload` reports files **submitted** for ingestion. Submission is not completed
ingestion; inspect jobs/status before querying. Rubric `--weights` accepts multiple
named changes atomically. Valid totals must remain 100; existing invalid totals may
be repaired incrementally, preserving criterion and level IDs.

### Edit a saved test scenario

```bash
lamb test update ASSISTANT_ID SCENARIO_ID --expected "Revised expectation" -o json
lamb test scenarios ASSISTANT_ID -o json
lamb test run ASSISTANT_ID --scenario SCENARIO_ID -o json
```

Only supplied fields change. Optional inline fields are `--title`, `--description`, `--message` (replaces the message list with one user message), and `--type`. An empty `--expected ""` clears the expectation. Scenario IDs, previous runs and evaluations are retained. At least one field is required.

The same update command is available in AAC liteshell and requires confirmation. The API verifies assistant ownership and that the scenario belongs to that assistant.

## Moodle document imports

Use a document session to keep source references scoped to your account and one workflow:

```sh
lamb moodle documents start
lamb moodle page list 42 --session SESSION_ID
lamb moodle book list 42 --session SESSION_ID
lamb moodle import page SOURCE_REF --to kb 12 --session SESSION_ID
lamb moodle import page SOURCE_REF --to kb 12 --session SESSION_ID --confirm REVIEW_ID
lamb moodle import book SOURCE_REF --single-file --session SESSION_ID
lamb moodle course get 42 --session SESSION_ID
lamb moodle file list CONTEXT_ID --component mod_resource --filearea content --session SESSION_ID
lamb moodle import file FILE_REF --to kb 12 --session SESSION_ID
lamb moodle import list --session SESSION_ID
lamb moodle import check IMPORT_ID --session SESSION_ID
lamb moodle import check IMPORT_ID --verify-content --session SESSION_ID
lamb moodle import refresh IMPORT_ID --session SESSION_ID
lamb moodle import refresh IMPORT_ID --session SESSION_ID --confirm REVIEW_ID
```

The initial import/refresh returns a one-hour review handle. `--confirm REVIEW_ID` approves that exact source and destination; a changed source, connection or session invalidates it. Equivalent AAC commands omit `lamb`, `--session` and `--confirm`; the conversation supplies the session and the application asks for one approval.

KB imports accept txt, md, json, pdf, docx, pptx, xlsx, html, csv and epub. The server selects the ingestion plugin. Single-file imports accept UTF-8 txt/md/json/html and converted Pages/Books. Source and converted documents are limited to 10 MiB. Office/EPUB archives are limited to 50 MiB expanded and 5,000 entries; encrypted archives, audio, general ZIP and XML are rejected.

Pages become Markdown. Books become one Markdown document in chapter order, skipping hidden chapters. Original HTML stays in private storage. Conversion retains headings, lists, links and simple tables, but omits images, media and image-based formulae; complex tables may flatten. No OCR or remote media fetching occurs.

Single-file reviews show characters and estimated tokens (UTF-8 bytes divided by three, rounded up). Above 24,000 estimated tokens, use a KB unless you explicitly choose the full reference after considering your assistant model's context window. Documents are never silently truncated. This is a warning threshold, independent of AAC context requirements.

Receipts record source links, identifiers, timestamps and hashes. A normal `check` compares metadata without downloading file bodies; equal metadata is not proof of equal content. `--verify-content` downloads and hashes explicitly. Re-import is always confirmed. Single-file references stay stable. KB replacements keep the old version until the new job succeeds. If ingestion remains in progress, run `lamb moodle import finish IMPORT_ID --session SESSION_ID`, then approve with `--confirm IMPORT_ID`. This resumes the recorded job without a second upload. Interrupted uploads without a returned job remain `outcome_unknown` and require destination inspection; automatic retries do not upload again.

Private originals, receipts and revisions use at most 256 MiB per creator. An administrator must archive older imports when this quota is reached. They are not published through `/static` and do not enter AAC conversation history. The KB file view and retrieval citations link to the source Moodle activity; opening it requires your Moodle browser login.


### Moodle Folders and subfolders

A folder import targets an existing owned KB with `--to kb ID`, or creates one with `--new-kb NAME [--description TEXT]`. One review covers KB creation and the selected files. The server inventories the entire subtree, prepares one exact review, then imports each supported file after approval. Source paths remain distinct even when basenames match. No local filesystem is involved.

```sh
lamb moodle documents start
lamb moodle folder list 12 --session SESSION
lamb moodle folder inspect FOLDER_REF --exclude /archive/ --session SESSION
lamb moodle import folder FOLDER_REF --exclude /archive/ --to kb 34 --session SESSION
# Or create a new KB and import with one review
lamb moodle import folder FOLDER_REF --exclude /archive/ --new-kb "Teacher readings" --chunk-size 2000 --session SESSION
# Read the review, then repeat with its returned REVIEW_ID.
lamb moodle import folder FOLDER_REF --exclude /archive/ --to kb 34 --session SESSION --confirm REVIEW_ID
lamb moodle folder status BATCH_ID --session SESSION
```

`--path /Unit/` selects a subtree; repeat `--exclude` for absolute Moodle file paths or subfolders ending in `/`. An unknown exclusion is an error. The review lists unsupported, externally linked and oversized files as skipped. Batches accept 1-20 supported files, at most 20 MiB total and 10 MiB per file. Inspection accepts at most 100 files; select smaller subfolders when necessary. Conversion failures stop preparation before any KB upload. The source is rechecked before approval is executed.

A partial result lists completed, processing, failed, unknown and not-started files. `lamb moodle folder finish BATCH_ID --session SESSION --confirm BATCH_ID` explicitly continues the approved set after fresh checks. Completed files are not uploaded again; uncertain uploads require inspection. Keep the session and batch IDs for recovery. Running a new `import folder` creates a new batch, not an idempotent retry. Use individual returned import IDs with `import check`/`refresh` for later source updates; no automatic folder synchronization runs.

Individual nested-file inspection is also available through `lamb moodle file list CONTEXT_ID --component mod_folder --filepath '/Unit 1/' --itemid 0 --session SESSION`. Course/module context IDs come from `lamb moodle course contents COURSE_ID --session SESSION`.
