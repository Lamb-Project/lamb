# LAMB CLI — Architecture Document

## Overview

`lamb-cli` is a Python command-line tool for the LAMB platform. It communicates exclusively with the LAMB backend HTTP API (`/creator/` and `/lamb/v1/` endpoint families on port 9099). No direct database access.

Built with **Typer** (CLI framework), **httpx** (HTTP client), **Rich** (terminal formatting), and **platformdirs** (XDG-compliant config paths).

## Project Layout

```
lamb-cli/
  pyproject.toml                 # Package metadata, deps, entry point
  .venv/                         # Local virtualenv (managed via uv)
  Documentation/
    prd.md                       # Full PRD & technical specification
    lamb_cli_architecture.md     # This file
  src/lamb_cli/
    __init__.py                  # Version string
    main.py                      # Typer app root + top-level commands
    config.py                    # Config/credentials (TOML + platformdirs)
    client.py                    # HTTP client wrapper (httpx)
    output.py                    # Output formatting (table/json/plain)
    errors.py                    # Exception hierarchy + exit codes
    commands/
      __init__.py
      assistant.py               # lamb assistant *
      model.py                   # lamb model *
  tests/
    conftest.py                  # Shared fixtures
    test_config.py
    test_client.py
    test_output.py
    test_commands/
      test_login.py              # login, logout, status, whoami
      test_assistant.py
      test_model.py
```

## Module Dependency Graph

```
main.py
  ├── config.py ──── errors.py
  ├── client.py ──┬─ config.py
  │               └─ errors.py
  ├── output.py
  └── commands/
        ├── assistant.py ──┬─ client.py
        │                  └─ output.py
        └── model.py ─────┬─ client.py
                           └─ output.py
```

## Core Modules

### `errors.py` — Exception Hierarchy

All CLI-specific exceptions inherit from `LambCliError`. Each carries an `exit_code`:

| Exception            | Exit Code | Trigger                        |
|----------------------|-----------|--------------------------------|
| `ConfigError`        | 1         | Bad config, missing file       |
| `ApiError`           | 2         | Server 4xx/5xx (non-auth/404)  |
| `NetworkError`       | 3         | Connection refused, timeout    |
| `AuthenticationError`| 4         | 401/403, missing token         |
| `NotFoundError`      | 5         | 404                            |

The `_cli()` entry point in `main.py` catches `LambCliError` and exits with the appropriate code.

### `config.py` — Configuration & Credentials

**Storage location:** `platformdirs.user_config_dir("lamb")`
- macOS: `~/Library/Application Support/lamb/`
- Linux: `~/.config/lamb/`

**Files:**
- `config.toml` — server URL, output format preferences
- `credentials.toml` — token, email, role info (file permissions 0600)

**Resolution order** (highest priority first):
1. Environment variables (`LAMB_SERVER_URL`, `LAMB_TOKEN`)
2. Config/credentials files
3. Defaults (`http://localhost:9099`, format `table`)

**Stored user profile fields** (from login response):
- `token`, `email`, `name`
- `role` — platform-level role (e.g., `admin`, `user`)
- `user_type` — `creator` or `end_user`
- `organization_role` — org-scoped role (e.g., `owner`, `admin`, `member`)

### `client.py` — HTTP Client

`LambClient` wraps `httpx.Client` with:
- Base URL + auth header injection (`Authorization: Bearer <token>`)
- 30s default timeout, redirect following
- Automatic error mapping: HTTP status codes to typed exceptions
- Methods: `get()`, `post()`, `put()`, `patch()`, `delete()`, `post_form()`, `upload_file()`, `stream_post()`
- Context manager support (`with get_client() as client:`)

`get_client(require_auth=True)` is the module-level factory that reads config and builds a client.

### `output.py` — Formatting

All user-facing data goes to **stdout**; status/error messages go to **stderr** (via Rich Console).

Three output modes (selectable via `-o`/`--output`):

| Mode    | Format                    | Use Case          |
|---------|---------------------------|--------------------|
| `table` | Rich-formatted table      | Human reading      |
| `json`  | Indented JSON             | Scripting, piping  |
| `plain` | Tab-separated values      | grep/awk pipelines |

`format_output()` dispatches to the correct renderer based on data shape (list vs dict) and format.

## Command Structure

```
lamb
  --version / -v           Show version
  login                    Authenticate (email/password -> store token + role info)
  logout                   Clear stored credentials
  status                   Health check (no auth required)
  whoami [-o]              Show current user + permission level
  assistant
    list [--limit] [--offset] [-o]
    get <id> [-o]
    create <name> [--description] [--system-prompt] [--system-prompt-file]
                  [--rag-top-k] [--rag-collections]
    update <id> [--name] [--description] [--system-prompt] [--rag-top-k]
               [--rag-collections]
    delete <id> [--confirm/-y]
    publish <id>
    unpublish <id>
    export <id> [--output-file]
  model
    list [-o]
```

## Role-Based Access Control (RBAC)

The CLI is aware of the RBAC model defined in issue #252. Backend endpoints enforce permissions; the CLI stores role information locally for UX decisions and user awareness.

### Permission Model

| Role              | Scope                   | Key Capabilities                                                    |
|-------------------|-------------------------|----------------------------------------------------------------------|
| **System Admin**  | Any organization        | View/delete/share any assistant, view all chat history, manage orgs  |
| **Org Admin**     | Own organization only   | View/use/share assistants in org, see aggregate stats (no chat logs) |
| **Owner**         | Own resources           | Full CRUD on own assistants, view own chat history                   |
| **Shared User**   | Shared resources only   | Use shared assistants, view own chat history                         |

### Key Constraints

- **System Admin cannot edit** other users' assistants (view + delete only) — prevents accidental damage to prompts/KB config.
- **Org Admin cannot see chat history** — respects student privacy. Can see anonymized aggregate stats only.
- **Publish/unpublish is owner-only** — even system admin cannot publish on behalf of another user.

### How the CLI Uses Role Info

1. **Login** stores `role`, `user_type`, `organization_role` in `credentials.toml`.
2. **`whoami`** displays the full permission profile so users understand their access level.
3. **Future phases** (org/user commands) will use stored role to:
   - Show an org picker for system admins (can administer any org).
   - Auto-scope org admins to their own organization.
   - Surface appropriate warnings when a user attempts an action beyond their role.

## API Communication

The CLI talks to two endpoint families on the LAMB backend (port 9099):

- **`/creator/`** — User-facing API with JWT auth (login, assistants, KBs, orgs, analytics)
- **`/lamb/v1/`** — Internal API (completions, models)

### Key Endpoints (Phase 1)

| Command                  | Method | Path                                      |
|--------------------------|--------|-------------------------------------------|
| `lamb login`             | POST   | `/creator/login` (form-encoded)           |
| `lamb status`            | GET    | `/status`                                 |
| `lamb whoami`            | GET    | `/creator/user/current`                   |
| `lamb model list`        | GET    | `/creator/models`                         |
| `lamb assistant list`    | GET    | `/creator/assistant/get_assistants`       |
| `lamb assistant get`     | GET    | `/creator/assistant/get_assistant/{id}`   |
| `lamb assistant create`  | POST   | `/creator/assistant/create_assistant`     |
| `lamb assistant update`  | PUT    | `/creator/assistant/update_assistant/{id}`|
| `lamb assistant delete`  | DELETE | `/creator/assistant/delete_assistant/{id}`|
| `lamb assistant publish` | PUT    | `/creator/assistant/publish/{id}`         |
| `lamb assistant export`  | GET    | `/creator/assistant/export/{id}`          |

## Testing

All tests use **pytest** + **pytest-httpx** (mocked HTTP, no real server needed).

```bash
cd /opt/lamb/lamb-cli
.venv/bin/pytest tests/ -v          # 75 tests
.venv/bin/pytest tests/ --cov       # with coverage
```

**Test strategy:**
- Every command has at least one happy-path and one error-path test.
- All three output formats (table/json/plain) tested for listing commands.
- Config tests verify env var precedence, credential storage, and file permissions.
- Client tests verify auth header injection, error mapping, and network error handling.

## Development Setup

```bash
cd /opt/lamb/lamb-cli
uv venv .venv
uv pip install -e ".[dev]"
.venv/bin/lamb --help
```

## Implementation Phases

| Phase | Scope                                  | Status      |
|-------|----------------------------------------|-------------|
| **1** | Core + Assistants + Models             | Done        |
| 2     | Knowledge Bases + Ingestion Jobs       | Planned     |
| 3     | Organizations + Users (admin commands) | Planned     |
| 4     | Templates + Analytics + Chat           | Planned     |
| 5     | Shell completions, config profiles     | Planned     |

See `Documentation/prd.md` for full specification of all phases.
