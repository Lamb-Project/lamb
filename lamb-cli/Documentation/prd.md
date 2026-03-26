# LAMB CLI — Product Requirements Document & Technical Specification

## Document Information

- **Project**: `lamb-cli` — Command-Line Interface for the LAMB Platform
- **Version**: 1.0 (Draft)
- **Date**: 2026-02-12
- **Location**: `/opt/lamb/lamb-cli/` (new subfolder in monorepo)

---

## PART 1: PRODUCT REQUIREMENTS DOCUMENT

### 1. Executive Summary

`lamb-cli` is a Python command-line tool that enables LAMB platform administrators and content creators to manage assistants, knowledge bases, organizations, users, prompt templates, rubrics, and analytics from the terminal. It communicates exclusively with the LAMB backend HTTP API (the `/creator/` and `/lamb/v1/` endpoint families on port 9099), requiring no direct database access.

The CLI provides automation-friendly primitives (JSON output, exit codes, piping support) alongside human-friendly defaults (tables, colors, progress bars, interactive prompts for complex operations).

### 2. Goals

1. **Automation**: Enable scripting and CI/CD pipelines that create, configure, and deploy assistants programmatically (e.g., batch-create 50 assistants from a CSV, bulk-ingest documents into knowledge bases).
2. **Power-user Productivity**: Give creators a faster path for repetitive operations: listing, updating, publishing, and inspecting assistants without navigating the web UI.
3. **Admin Operations**: Let administrators manage organizations, users, and bulk-import rosters from the command line.
4. **Parity with Web UI**: Cover the most operationally valuable API endpoints in v1, with a clear path to full coverage.
5. **Ecosystem Fit**: Follow Python packaging conventions (`pyproject.toml`, `pip install`), feel natural alongside tools like `gh`, `docker`, and `kubectl`.

### 3. Target Users

| Persona | Description | Key Use Cases |
|---------|-------------|---------------|
| **Creator (Educator)** | University professor or course designer building AI assistants | Create/update assistants, manage KBs, ingest documents, test with chat, export configs |
| **Platform Admin** | IT staff or department head running the LAMB instance | Manage organizations, bulk-import users, monitor system health, manage all assistants |
| **DevOps/Scripter** | Developer integrating LAMB into automated workflows | CI/CD pipelines, scripted batch operations, health checks, infrastructure monitoring |

### 4. Use Cases (Priority-Ordered)

**P0 — V1 Must-Have:**
1. Authenticate with `lamb login` (email/password) and persist the token locally.
2. List, create, get, update, delete, publish/unpublish assistants.
3. List, create, get, update, delete knowledge bases.
4. Ingest content into a KB (file upload, URL, YouTube) with progress indication.
5. Query a knowledge base.
6. List ingestion jobs, check status, retry/cancel.
7. Export an assistant as JSON.
8. System health check (`lamb status`).
9. List available models (`lamb model list`).

**P1 — V1 Should-Have:**
10. Organization CRUD (list, create, get, update, delete).
11. User management (list, create, enable/disable, delete).
12. Bulk user import from CSV.
13. Analytics: list chats for an assistant, view stats.
14. Prompt template CRUD.
15. Chat with an assistant from the terminal (streaming completions).

**P2 — Future:**
16. Rubric CRUD + AI generation.
17. LTI configuration.
18. Interactive assistant creation wizard.
19. Completion pipeline inspection (list processors/connectors).
20. Bulk assistant operations (batch create from YAML/JSON definitions).
21. Shell completions (bash, zsh, fish).
22. `lamb config` for multi-profile management (multiple servers).

### 5. Success Metrics

- All P0 use cases functional with tests within the v1 release.
- `--output json` flag on every listing/detail command producing machine-parseable output.
- Non-zero exit code on every failure, with structured error messages on stderr.
- Complete `--help` documentation on every command and subcommand.
- Installation via `pip install -e .` from the `lamb-cli/` directory.

### 6. Non-Goals (V1)

- No direct database access. CLI talks only to the HTTP API.
- No GUI or TUI beyond basic terminal output.
- No WebSocket connections (polling for long-running operations instead).
- No management of the KB Server or Open WebUI directly — only through LAMB's creator/admin API.

---

## PART 2: TECHNICAL SPECIFICATION

### 7. CLI Framework: Typer (Recommended)

**Recommendation: Typer** over Click.

| Criteria | Click | Typer |
|----------|-------|-------|
| Type hints | Manual decorators | Native Python type annotations |
| Autocompletion | Manual | Built-in shell completion support |
| Help generation | Good | Excellent (from docstrings + types) |
| Sub-commands | Explicit groups | Automatic from `app.add_typer()` |
| Testing | `CliRunner` | `CliRunner` (inherits from Click) |
| Rich integration | Manual | First-class `rich` support |
| Learning curve | Moderate | Low (Pythonic) |
| Ecosystem | Mature, huge | Growing, backed by Click |

Typer builds on Click internally, so we get Click's battle-tested foundation with a more modern, Pythonic API. The automatic type-annotation-to-CLI-parameter mapping reduces boilerplate significantly. The built-in Rich integration gives us tables, progress bars, and colored output with minimal effort.

### 8. Command Hierarchy

The command structure follows the `noun verb` pattern (like `gh`, `docker`, `kubectl`), grouped by entity.

```
lamb
  login                              # Authenticate (email/password -> store token)
  logout                             # Clear stored credentials
  status                             # Health check (GET /status)
  whoami                             # Show current user info
  config
    show                             # Show current configuration
    set <key> <value>                # Set config value (server-url, default-output, etc.)

  assistant
    list [--limit N] [--offset N]    # GET /creator/assistant/get_assistants
    get <id>                         # GET /creator/assistant/get_assistant/{id}
    create <name> [--description ...] [--system-prompt ...] [--rag-top-k N] [--rag-collections ...]
                                     # POST /creator/assistant/create_assistant
    update <id> [--name ...] [--description ...] [--system-prompt ...]
                                     # PUT /creator/assistant/update_assistant/{id}
    delete <id> [--confirm]          # DELETE /creator/assistant/delete_assistant/{id}
    publish <id>                     # PUT /creator/assistant/publish/{id} {publish_status: true}
    unpublish <id>                   # PUT /creator/assistant/publish/{id} {publish_status: false}
    export <id> [--output-file ...]  # GET /creator/assistant/export/{id}

  kb
    list                             # GET /creator/knowledgebases/user
    list-shared                      # GET /creator/knowledgebases/shared
    get <id>                         # GET /creator/knowledgebases/kb/{id}
    create <name> [--description ...]# POST /creator/knowledgebases/ (create)
    update <id> [--name ...]         # PATCH /creator/knowledgebases/kb/{id}
    delete <id> [--confirm]          # DELETE /creator/knowledgebases/kb/{id}
    ingest <kb-id> --file <path>     # POST /creator/knowledgebases/kb/{id}/ingest (file)
    ingest <kb-id> --url <url>       # POST /creator/knowledgebases/kb/{id}/ingest (URL)
    ingest <kb-id> --youtube <url>   # POST /creator/knowledgebases/kb/{id}/ingest (YouTube)
    query <kb-id> <query-text>       # POST /creator/knowledgebases/kb/{id}/query
    files <kb-id>                    # GET /creator/knowledgebases/kb/{id}/files
    delete-file <kb-id> <file-id>    # DELETE /creator/knowledgebases/kb/{id}/files/{file_id}
    plugins                          # GET /creator/knowledgebases/ingestion-plugins
    query-plugins                    # GET /creator/knowledgebases/query-plugins

  job
    list [--kb-id ...]               # GET /creator/knowledgebases/ingestion-jobs
    get <job-id>                     # GET /creator/knowledgebases/ingestion-jobs/{id}
    retry <job-id>                   # POST /creator/knowledgebases/ingestion-jobs/{id}/retry
    cancel <job-id>                  # POST /creator/knowledgebases/ingestion-jobs/{id}/cancel
    watch <job-id>                   # Poll job status with live progress (custom)

  org
    list                             # GET /creator/admin/organizations
    get <id>                         # GET /creator/admin/organizations/{id}
    create <name> [--slug ...]       # POST /creator/admin/organizations
    update <id> [--name ...]         # PUT /creator/admin/organizations/{id}
    delete <id> [--confirm]          # DELETE /creator/admin/organizations/{id}
    add-user <org-id> <email> [--role ...]
                                     # POST /creator/admin/organizations/{id}/users
    remove-user <org-id> <user-id>   # DELETE /creator/admin/organizations/{id}/users/{uid}
    set-role <org-id> <user-id> <role>
                                     # PUT /creator/admin/organizations/{id}/users/{uid}/role
    bulk-import <org-id> --file <csv># POST /creator/admin/organizations/{id}/users/bulk-import

  user
    list                             # GET /creator/users
    create <email> <name> <password> [--role ...] [--user-type ...] [--org-id ...]
                                     # POST /creator/users (admin)
    get <id>                         # GET /creator/users/{id}/profile
    enable <id>                      # PUT /creator/users/{id}/status
    disable <id>                     # PUT /creator/users/{id}/status
    delete <id> [--confirm]          # DELETE /creator/users/{id}

  template
    list [--page N] [--limit N]      # GET /creator/prompt-templates/list
    get <id>                         # GET /creator/prompt-templates/{id}
    create --name ... [--system-prompt ...] [--prompt-template ...]
                                     # POST /creator/prompt-templates/create
    update <id> [--name ...]         # PUT /creator/prompt-templates/{id}
    delete <id> [--confirm]          # DELETE /creator/prompt-templates/{id}
    duplicate <id> [--new-name ...]  # POST /creator/prompt-templates/{id}/duplicate
    share <id> --enable/--disable    # PUT /creator/prompt-templates/{id}/share
    export <ids...>                  # POST /creator/prompt-templates/export

  analytics
    chats <assistant-id> [--page ...] [--per-page ...]
                                     # GET /creator/analytics/assistant/{id}/chats
    stats <assistant-id>             # GET /creator/analytics/assistant/{id}/stats
    timeline <assistant-id>          # GET /creator/analytics/assistant/{id}/timeline

  chat <assistant-id> [--message ...]# POST /v1/chat/completions (interactive streaming)

  model
    list                             # GET /v1/models

  completion
    list                             # GET /lamb/v1/completions/list
```

### 9. Authentication and Configuration

#### 9.1 Configuration Storage

Configuration lives in `~/.config/lamb/` (XDG-compliant on Linux, `~/Library/Application Support/lamb/` on macOS via `platformdirs`):

```
~/.config/lamb/
  config.toml          # Server URL, default output format, active profile
  credentials.toml     # Token storage (file permissions 0600)
```

**`config.toml` structure:**

```toml
[default]
server_url = "http://localhost:9099"
output = "table"   # "table", "json", "plain"

# Optional: multiple profiles
[profiles.production]
server_url = "https://lamb.university.edu"
output = "table"
```

**`credentials.toml` structure:**

```toml
[default]
token = "eyJhbGciOi..."
email = "creator@example.com"
expires_at = "2026-02-13T10:00:00"

[profiles.production]
token = "eyJhbGciOi..."
email = "admin@university.edu"
```

#### 9.2 Authentication Flow

```
lamb login
```

1. If `--email` and `--password` are provided as flags, use them directly.
2. Otherwise, prompt interactively (email + password with hidden input).
3. POST to `/creator/login` with form-encoded email and password.
4. On success, extract `token` from response and store it in `credentials.toml`.
5. Display: "Logged in as {name} ({email}) [role: {role}]"

The token is sent on all subsequent requests as `Authorization: Bearer <token>`.

**Environment variable overrides** (useful for CI/CD):
- `LAMB_SERVER_URL` — overrides `server_url` from config
- `LAMB_TOKEN` — overrides stored token (skips login entirely)
- `LAMB_PROFILE` — selects a named profile

Priority: ENV vars > CLI flags > config file.

#### 9.3 Token Refresh

The current LAMB auth does not expose a refresh token endpoint. The CLI will:
- Detect 401 responses and print: "Session expired. Please run `lamb login` again."
- Exit with code 4 (auth error) for scripting detection.

### 10. Output Formatting

Every command that produces structured output supports `--output`/`-o` with three modes:

| Mode | Flag | Behavior |
|------|------|----------|
| **table** (default) | `-o table` | Rich-formatted table with colors, truncated fields |
| **json** | `-o json` | Full JSON output to stdout, no colors (pipe-safe) |
| **plain** | `-o plain` | Tab-separated values, no colors (grep/awk-friendly) |

**Rules:**
- Human messages, errors, and progress indicators always go to **stderr**.
- Structured data always goes to **stdout**.
- In `--output json` mode, the output is a valid JSON document (object or array).
- Non-zero exit codes for all errors, even when JSON output contains an error field.

**Example:**

```bash
# Human-readable (default)
$ lamb assistant list
ID    Name                Description          Published   Updated
123   Math_Tutor          Helps with algebra   Yes         2026-02-10
124   History_Helper      WWII study guide     No          2026-02-08

# Machine-readable (for scripting)
$ lamb assistant list -o json
[
  {"id": 123, "name": "Math_Tutor", "description": "Helps with algebra", "published": true, ...},
  {"id": 124, "name": "History_Helper", "description": "WWII study guide", "published": false, ...}
]

# Pipe-friendly
$ lamb assistant list -o json | jq '.[].id'
123
124
```

### 11. Error Handling

#### 11.1 Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General CLI error (invalid arguments, missing config) |
| 2 | API error (server returned 4xx/5xx) |
| 3 | Network error (connection refused, timeout) |
| 4 | Authentication error (401, expired token) |
| 5 | Not found (404) |

#### 11.2 Error Output Format

Errors are always printed to **stderr**. In JSON output mode, errors are also structured:

```bash
# Default mode (stderr)
$ lamb assistant get 999
Error: Assistant not found (HTTP 404)

# JSON mode (stderr gets the human message, stdout gets JSON error)
$ lamb assistant get 999 -o json
# stderr: Error: Assistant not found
# stdout: {"error": true, "status_code": 404, "detail": "Assistant not found"}
```

#### 11.3 Confirmation for Destructive Operations

Commands that delete data require `--confirm` or `-y` for non-interactive use. Without it, the CLI prompts interactively:

```bash
$ lamb assistant delete 123
Are you sure you want to delete assistant 123 'Math_Tutor'? [y/N]: y
Assistant 123 deleted.

# Non-interactive (for scripting):
$ lamb assistant delete 123 --confirm
Assistant 123 deleted.
```

### 12. Progress Indicators

Long-running operations show progress on stderr via Rich:

- **File ingestion**: Progress bar with file name, upload percentage, then a "Processing..." spinner.
- **Job watching** (`lamb job watch <id>`): Live-updating status display that polls every 3 seconds.
- **Bulk imports**: Progress bar with count of processed users.
- **Chat completions**: Streaming tokens printed as received.

All progress indicators are suppressed when stdout is piped (detected via `sys.stdout.isatty()`).

### 13. Project Structure

```
/opt/lamb/lamb-cli/
  pyproject.toml               # Package metadata, dependencies, entry point
  README.md                    # User documentation
  LICENSE                      # Same as parent project
  src/
    lamb_cli/
      __init__.py              # Package init, version
      main.py                  # Typer app root, top-level commands (login, logout, status, whoami)
      config.py                # Config/credentials loading (platformdirs, TOML)
      client.py                # HTTP client wrapper (httpx-based, auth injection, error handling)
      output.py                # Output formatting (table/json/plain), Rich console setup
      errors.py                # Exception classes, exit code mapping
      commands/
        __init__.py
        assistant.py           # lamb assistant *
        kb.py                  # lamb kb *
        job.py                 # lamb job *
        org.py                 # lamb org *
        user.py                # lamb user *
        template.py            # lamb template *
        analytics.py           # lamb analytics *
        chat.py                # lamb chat (streaming completions)
        model.py               # lamb model *
        completion.py          # lamb completion *
  tests/
    __init__.py
    conftest.py                # Shared fixtures (mock server, test config)
    test_config.py             # Config loading tests
    test_client.py             # HTTP client tests (mocked)
    test_output.py             # Output formatting tests
    test_commands/
      __init__.py
      test_assistant.py        # Assistant command tests
      test_kb.py               # KB command tests
      test_job.py              # Job command tests
      test_org.py              # Org command tests
      test_user.py             # User command tests
      test_login.py            # Auth flow tests
```

### 14. Key Dependencies

```toml
[project]
name = "lamb-cli"
version = "0.1.0"
description = "Command-line interface for the LAMB platform"
requires-python = ">=3.10"
dependencies = [
    "typer[all]>=0.12.0",      # CLI framework (includes rich, shellingham)
    "httpx>=0.27.0",            # Async-capable HTTP client (already used by backend)
    "rich>=13.0.0",             # Terminal formatting (tables, progress, colors)
    "platformdirs>=4.0.0",      # XDG-compliant config paths
    "tomli>=2.0.0;python_version<'3.11'",  # TOML parsing (stdlib in 3.11+)
    "tomli-w>=1.0.0",           # TOML writing
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-httpx>=0.30.0",     # Mock httpx requests
    "pytest-cov>=5.0.0",
    "ruff>=0.5.0",              # Linter + formatter
    "mypy>=1.10.0",             # Type checking
]

[project.scripts]
lamb = "lamb_cli.main:app"
```

**Why `httpx` over `requests`:**
- Already in the backend's `requirements.txt` (v0.28.1), so the team knows it.
- Supports both sync and async usage (useful for streaming completions).
- Superior timeout handling and connection pooling.
- Type-annotated API.

### 15. Core Module Design

#### 15.1 `client.py` — HTTP Client

Central module that wraps `httpx.Client` with:

```python
class LambClient:
    """HTTP client for LAMB API with auth injection and error handling."""

    def __init__(self, server_url: str, token: str | None = None):
        self.server_url = server_url.rstrip("/")
        self.token = token
        self._client = httpx.Client(
            base_url=self.server_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self._handle_response(self._client.get(path, **kwargs))

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self._handle_response(self._client.post(path, **kwargs))

    def put(self, path: str, **kwargs) -> httpx.Response:
        return self._handle_response(self._client.put(path, **kwargs))

    def patch(self, path: str, **kwargs) -> httpx.Response:
        return self._handle_response(self._client.patch(path, **kwargs))

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self._handle_response(self._client.delete(path, **kwargs))

    def post_form(self, path: str, data: dict, **kwargs) -> httpx.Response:
        """POST with form-encoded data (used for login)."""
        return self._handle_response(
            self._client.post(path, data=data, **kwargs)
        )

    def upload_file(self, path: str, file_path: str, field: str = "file",
                    extra_data: dict | None = None) -> httpx.Response:
        """Upload a file with multipart/form-data."""
        ...

    def stream_post(self, path: str, **kwargs):
        """POST with streaming response (for chat completions)."""
        ...

    def _handle_response(self, response: httpx.Response) -> httpx.Response:
        """Check response, raise LambApiError on non-2xx."""
        if response.status_code == 401:
            raise AuthenticationError("Session expired. Run `lamb login`.")
        if response.status_code == 404:
            raise NotFoundError(...)
        if response.status_code >= 400:
            raise ApiError(status_code=response.status_code, detail=...)
        return response
```

#### 15.2 `config.py` — Configuration Management

```python
from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("lamb"))
CONFIG_FILE = CONFIG_DIR / "config.toml"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.toml"

def get_server_url() -> str:
    """Resolve server URL: LAMB_SERVER_URL env > config file > default."""
    ...

def get_token() -> str | None:
    """Resolve token: LAMB_TOKEN env > credentials file."""
    ...

def get_output_format() -> str:
    """Resolve output format: --output flag > config file > 'table'."""
    ...

def save_credentials(token: str, email: str) -> None:
    """Write token to credentials file with 0600 permissions."""
    ...

def clear_credentials() -> None:
    """Remove stored token (logout)."""
    ...
```

#### 15.3 `output.py` — Output Formatting

```python
from rich.console import Console
from rich.table import Table

stderr_console = Console(stderr=True)  # For messages, errors, progress
stdout_console = Console()              # For data output

def print_table(data: list[dict], columns: list[tuple[str, str]],
                title: str = "") -> None:
    """Render a Rich table to stdout."""
    ...

def print_json(data: Any) -> None:
    """Print JSON to stdout (no colors)."""
    import json
    print(json.dumps(data, indent=2, default=str))

def print_plain(data: list[dict], columns: list[str]) -> None:
    """Print tab-separated values to stdout."""
    ...

def print_detail(data: dict, fields: list[tuple[str, str]]) -> None:
    """Print a single object's details as key-value pairs."""
    ...

def print_error(message: str) -> None:
    """Print error message to stderr in red."""
    stderr_console.print(f"[red]Error:[/red] {message}")

def print_success(message: str) -> None:
    """Print success message to stderr in green."""
    stderr_console.print(f"[green]{message}[/green]")
```

#### 15.4 Command Example — `commands/assistant.py`

```python
import typer
from typing import Optional
from typing_extensions import Annotated

app = typer.Typer(help="Manage learning assistants.")

@app.command()
def list(
    limit: Annotated[int, typer.Option(help="Max results")] = 10,
    offset: Annotated[int, typer.Option(help="Pagination offset")] = 0,
    output: Annotated[str, typer.Option("-o", "--output",
                                        help="Output format")] = None,
):
    """List your assistants."""
    client = get_client()
    response = client.get("/creator/assistant/get_assistants",
                          params={"limit": limit, "offset": offset})
    data = response.json()
    assistants = data.get("assistants", [])

    fmt = resolve_output_format(output)
    if fmt == "json":
        print_json(assistants)
    elif fmt == "plain":
        print_plain(assistants, ["id", "name", "description", "published"])
    else:
        print_table(
            assistants,
            columns=[
                ("id", "ID"),
                ("name", "Name"),
                ("description", "Description"),
                ("published", "Published"),
                ("updated_at", "Updated"),
            ],
            title="Assistants",
        )

@app.command()
def get(assistant_id: Annotated[int, typer.Argument(help="Assistant ID")]):
    """Get details of an assistant."""
    client = get_client()
    response = client.get(f"/creator/assistant/get_assistant/{assistant_id}")
    data = response.json()
    fmt = resolve_output_format()
    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, fields=[...])

@app.command()
def create(
    name: Annotated[str, typer.Argument(help="Assistant name")],
    description: Annotated[str, typer.Option(help="Description")] = "",
    system_prompt: Annotated[str, typer.Option(help="System prompt")] = "",
    system_prompt_file: Annotated[Optional[str],
        typer.Option(help="Read system prompt from file")] = None,
    rag_top_k: Annotated[int, typer.Option(help="RAG top-k results")] = 3,
    rag_collections: Annotated[str,
        typer.Option(help="KB collection UUIDs, comma-separated")] = "",
):
    """Create a new assistant."""
    if system_prompt_file:
        system_prompt = Path(system_prompt_file).read_text()
    body = {
        "name": name,
        "description": description,
        "system_prompt": system_prompt,
        "RAG_Top_k": rag_top_k,
        "RAG_collections": rag_collections,
    }
    client = get_client()
    response = client.post("/creator/assistant/create_assistant", json=body)
    ...

@app.command()
def delete(
    assistant_id: Annotated[int, typer.Argument(help="Assistant ID")],
    confirm: Annotated[bool,
        typer.Option("--confirm", "-y", help="Skip confirmation")] = False,
):
    """Delete an assistant (soft delete)."""
    if not confirm:
        client = get_client()
        data = client.get(
            f"/creator/assistant/get_assistant/{assistant_id}"
        ).json()
        name = data.get("name", "unknown")
        if not typer.confirm(f"Delete assistant {assistant_id} '{name}'?"):
            raise typer.Abort()
    client = get_client()
    client.delete(f"/creator/assistant/delete_assistant/{assistant_id}")
    print_success(f"Assistant {assistant_id} deleted.")
```

### 16. Streaming Chat

The `lamb chat` command provides interactive streaming completions:

```bash
# Single message (non-interactive):
$ lamb chat 123 --message "What is photosynthesis?"
Photosynthesis is the process by which plants convert sunlight...

# Interactive mode (default when no --message):
$ lamb chat 123
Chatting with assistant 123 (Math_Tutor). Type /quit to exit.

You: What is 2+2?
Assistant: 2 + 2 equals 4.

You: /quit
```

Implementation uses `httpx` streaming response with SSE parsing:

```python
def stream_chat(client: LambClient, model: str, messages: list[dict]):
    """Stream chat completions, printing tokens as they arrive."""
    with client._client.stream(
        "POST",
        "/v1/chat/completions",
        json={"model": model, "messages": messages, "stream": True},
    ) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                payload = line[6:]
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                content = chunk["choices"][0]["delta"].get("content", "")
                if content:
                    sys.stdout.write(content)
                    sys.stdout.flush()
    print()  # Final newline
```

> **Note:** The chat completions endpoint at `/v1/chat/completions` uses the `LAMB_BEARER_TOKEN` (the API key), not the user JWT token. The CLI needs to handle both token types. For v1, `lamb chat` will accept an optional `--api-key` flag, falling back to `LAMB_API_KEY` env var. The `model` field should be `"lamb_assistant.{assistant_id}"`.

### 17. API Path Mapping

Based on the codebase analysis, these are the exact API paths the CLI calls:

| CLI Command | HTTP Method | API Path |
|-------------|-------------|----------|
| `lamb login` | POST | `/creator/login` (form-encoded) |
| `lamb status` | GET | `/status` |
| `lamb model list` | GET | `/v1/models` |
| `lamb assistant list` | GET | `/creator/assistant/get_assistants?limit=&offset=` |
| `lamb assistant get <id>` | GET | `/creator/assistant/get_assistant/{id}` |
| `lamb assistant create` | POST | `/creator/assistant/create_assistant` |
| `lamb assistant update <id>` | PUT | `/creator/assistant/update_assistant/{id}` |
| `lamb assistant delete <id>` | DELETE | `/creator/assistant/delete_assistant/{id}` |
| `lamb assistant publish <id>` | PUT | `/creator/assistant/publish/{id}` |
| `lamb assistant export <id>` | GET | `/creator/assistant/export/{id}` |
| `lamb kb list` | GET | `/creator/knowledgebases/user` |
| `lamb kb list-shared` | GET | `/creator/knowledgebases/shared` |
| `lamb kb get <id>` | GET | `/creator/knowledgebases/kb/{id}` |
| `lamb kb create` | POST | `/creator/knowledgebases/` |
| `lamb kb update <id>` | PATCH | `/creator/knowledgebases/kb/{id}` |
| `lamb kb delete <id>` | DELETE | `/creator/knowledgebases/kb/{id}` |
| `lamb kb ingest <id>` | POST | `/creator/knowledgebases/kb/{id}/ingest` |
| `lamb kb query <id>` | POST | `/creator/knowledgebases/kb/{id}/query` |
| `lamb kb files <id>` | GET | `/creator/knowledgebases/kb/{id}/files` |
| `lamb kb delete-file` | DELETE | `/creator/knowledgebases/kb/{id}/files/{fid}` |
| `lamb job list` | GET | `/creator/knowledgebases/ingestion-jobs` |
| `lamb job get <id>` | GET | `/creator/knowledgebases/ingestion-jobs/{id}` |
| `lamb job retry <id>` | POST | `/creator/knowledgebases/ingestion-jobs/{id}/retry` |
| `lamb job cancel <id>` | POST | `/creator/knowledgebases/ingestion-jobs/{id}/cancel` |
| `lamb org list` | GET | `/creator/admin/organizations` |
| `lamb org create` | POST | `/creator/admin/organizations` |
| `lamb org get <id>` | GET | `/creator/admin/organizations/{id}` |
| `lamb org update <id>` | PUT | `/creator/admin/organizations/{id}` |
| `lamb org delete <id>` | DELETE | `/creator/admin/organizations/{id}` |
| `lamb org add-user` | POST | `/creator/admin/organizations/{id}/users` |
| `lamb org remove-user` | DELETE | `/creator/admin/organizations/{id}/users/{uid}` |
| `lamb org set-role` | PUT | `/creator/admin/organizations/{id}/users/{uid}/role` |
| `lamb org bulk-import` | POST | `/creator/admin/organizations/{id}/users/bulk-import` |
| `lamb user list` | GET | `/creator/users` |
| `lamb user create` | POST | `/creator/users` |
| `lamb user get <id>` | GET | `/creator/users/{id}/profile` |
| `lamb user enable/disable` | PUT | `/creator/users/{id}/status` |
| `lamb user delete <id>` | DELETE | `/creator/users/{id}` |
| `lamb template list` | GET | `/creator/prompt-templates/list` |
| `lamb template get <id>` | GET | `/creator/prompt-templates/{id}` |
| `lamb template create` | POST | `/creator/prompt-templates/create` |
| `lamb template update <id>` | PUT | `/creator/prompt-templates/{id}` |
| `lamb template delete <id>` | DELETE | `/creator/prompt-templates/{id}` |
| `lamb analytics chats <id>` | GET | `/creator/analytics/assistant/{id}/chats` |
| `lamb analytics stats <id>` | GET | `/creator/analytics/assistant/{id}/stats` |
| `lamb analytics timeline <id>` | GET | `/creator/analytics/assistant/{id}/timeline` |
| `lamb chat <id>` | POST | `/v1/chat/completions` (streaming) |
| `lamb completion list` | GET | `/lamb/v1/completions/list` |

### 18. Testing Approach

#### 18.1 Unit Tests (mocked HTTP)

All command tests mock the HTTP layer using `pytest-httpx`. No real server needed.

```python
# tests/test_commands/test_assistant.py
from typer.testing import CliRunner
from lamb_cli.main import app

runner = CliRunner()

def test_assistant_list(httpx_mock):
    httpx_mock.add_response(
        url="http://localhost:9099/creator/assistant/get_assistants"
            "?limit=10&offset=0",
        json={
            "assistants": [
                {"id": 1, "name": "Test", "description": "desc",
                 "published": True}
            ],
            "total_count": 1,
        },
    )
    result = runner.invoke(app, ["assistant", "list"])
    assert result.exit_code == 0
    assert "Test" in result.stdout

def test_assistant_list_json(httpx_mock):
    httpx_mock.add_response(...)
    result = runner.invoke(app, ["assistant", "list", "-o", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1

def test_assistant_delete_requires_confirmation():
    result = runner.invoke(app, ["assistant", "delete", "123"], input="n\n")
    assert result.exit_code != 0  # Aborted
```

#### 18.2 Integration Tests (real server, optional)

A separate test suite (not run by default) hits a real LAMB instance:

```python
# tests/integration/test_assistant_integration.py
import pytest

@pytest.mark.integration
def test_full_assistant_lifecycle():
    """Create -> Get -> Update -> Publish -> Unpublish -> Delete"""
    ...
```

Run with: `pytest -m integration` (requires `LAMB_TEST_SERVER_URL` and `LAMB_TEST_TOKEN` env vars).

#### 18.3 Coverage Target

- 90%+ line coverage for `client.py`, `config.py`, `output.py`, `errors.py`.
- Every command has at least one happy-path and one error-path test.
- All output formats (json/table/plain) tested for listing commands.

### 19. Implementation Phasing

**Phase 1 (Core + Assistants):** ~1 week
- Project scaffolding (`pyproject.toml`, package structure)
- `config.py`, `client.py`, `output.py`, `errors.py`
- `lamb login`, `lamb logout`, `lamb status`, `lamb whoami`
- `lamb assistant` (full CRUD + publish/unpublish/export)
- `lamb model list`
- Unit tests for all above

**Phase 2 (Knowledge Bases + Jobs):** ~1 week
- `lamb kb` (full CRUD + ingest + query + files)
- `lamb job` (list, get, retry, cancel, watch)
- File upload with progress bars
- Job polling with live status updates

**Phase 3 (Admin + Users):** ~3-4 days
- `lamb org` (full CRUD + user management + bulk import)
- `lamb user` (full CRUD)
- CSV bulk import with progress

**Phase 4 (Templates + Analytics + Chat):** ~3-4 days
- `lamb template` (full CRUD + duplicate + share + export)
- `lamb analytics` (chats, stats, timeline)
- `lamb chat` (streaming completions)
- `lamb completion list`

**Phase 5 (Polish):** ~2-3 days
- Shell completions (bash/zsh/fish)
- `lamb config` multi-profile support
- README documentation
- Integration test suite
- PyPI packaging preparation

### 20. Potential Challenges

1. **Auth token type mismatch**: The `/creator/` endpoints use JWT user tokens, while `/v1/chat/completions` uses the `LAMB_BEARER_TOKEN` (API key). The CLI needs to handle both token types. Resolution: store both; the login flow gets the user JWT, and `lamb config set api-key <key>` stores the API key for completions.

2. **File uploads for KB ingestion**: The KB server ingestion endpoint expects multipart form data with potentially large files. The CLI needs streaming uploads with progress indication. `httpx` supports this natively via file-like objects.

3. **SSE parsing for streaming chat**: The completions endpoint returns Server-Sent Events. The CLI needs a lightweight SSE parser (no heavy dependency needed — just line-by-line reading of `data:` prefixed lines).

4. **Inconsistent API response formats**: Some endpoints return `{"success": true, "data": ...}` (e.g., login, user list), while others return the data directly (e.g., assistant CRUD). The `client.py` layer should normalize this.

5. **No OpenAPI client generation**: The backend's OpenAPI spec at `/openapi.json` exists but the endpoints between `/creator/` and `/lamb/v1/` have different patterns. Manual client implementation is more reliable than code generation for v1.

---

### Critical Files for Implementation

When implementing the CLI, these backend files are the source of truth for API contracts:

- `backend/creator_interface/main.py` — Router structure, login endpoint, admin user management endpoints
- `backend/creator_interface/assistant_router.py` — Assistant CRUD API, Pydantic models, auth pattern
- `backend/creator_interface/knowledges_router.py` — KB management, file ingestion, job management
- `backend/creator_interface/organization_router.py` — Admin org/user endpoints, bulk import, role management
- `backend/config.py` — Server configuration, environment variables, dual-token system
