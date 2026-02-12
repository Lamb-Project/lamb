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

## Commands

```
lamb
  login                    Authenticate with email/password
  logout                   Clear stored credentials
  status                   Check if the server is reachable
  whoami                   Show current user and role info

  assistant
    list                   List all assistants
    get <id>               Get assistant details
    create <name>          Create a new assistant
    update <id>            Update an assistant
    delete <id>            Delete an assistant (with confirmation)
    publish <id>           Publish an assistant
    unpublish <id>         Unpublish an assistant
    export <id>            Export assistant config as JSON

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
| 3     | Organizations + Users (admin commands) | Planned |
| 4     | Templates + Analytics + Chat           | Planned |
| 5     | Shell completions, config profiles     | Planned |

See [Documentation/prd.md](Documentation/prd.md) for the full specification.
