---
name: moodle-cli
description: Set up, run, and troubleshoot the moodle-cli tool for interacting with Moodle LMS instances via the REST API. Use this skill when setting up moodle-cli for the first time, logging into a Moodle instance, troubleshooting connection or profile issues, or running Moodle commands from the CLI.
---

# Moodle CLI Skill

This skill covers setup, authentication, and troubleshooting for `moodle-cli` — a Python CLI for interacting with Moodle LMS instances via Web Services REST API.

## Project Location

```
/opt/lamb/cli-plugins/moodle-cli/
```

## Prerequisites

- **Python 3.11+** (the project uses `.python-version` pinned to 3.11)
- **`uv`** package manager (project uses uv, not pip)
- **OS keyring** available (tokens are stored in the system keychain, never in plaintext config)

## Setup & Installation

```bash
cd /opt/lamb/cli-plugins/moodle-cli
uv sync
```

Verify it works:
```bash
uv run moodle --help
uv run pytest   # 30 tests should pass
```

## ⚠️ VIRTUAL_ENV Warning

If you see:
```
warning: `VIRTUAL_ENV=/opt/lamb/.venv` does not match the project environment path `.venv` and will be ignored
```

This happens because the LAMB backend's venv (`/opt/lamb/.venv`) is active in your shell, and `uv` detects it doesn't match the moodle-cli project's own `.venv`. **Always unset it** before running moodle commands:

```bash
unset VIRTUAL_ENV
uv run moodle <command>
```

Or as a one-liner:
```bash
VIRTUAL_ENV= uv run moodle <command>
```

## Authentication

### Login with username/password

```bash
uv run moodle auth login --url https://moodle.ikasten.io/ --username teacher
# Prompts for password (hidden input)
```

### Login with token (for SSO/CAS sites)

If the Moodle instance uses SSO/CAS and password auth doesn't work, obtain a token manually from `https://<moodle-url>/user/managetoken.php` and use:

```bash
uv run moodle auth login --url https://moodle.ikasten.io/ --username teacher --token YOUR_TOKEN
```

### Login to a named profile

```bash
uv run moodle auth login --url https://moodle.ikasten.io/ --username teacher --profile-name myprofile
```

## Profile Management

Config is stored at `~/.config/moodle-cli/config.toml`.

### List all profiles

```bash
uv run moodle auth profiles
```

### Check current auth status

```bash
uv run moodle auth status
```

### Use a specific profile

```bash
uv run moodle --profile <name> <command>
```

### Switch default profile

The CLI currently has no `set-default` command. Edit the config file directly:

```bash
# Edit ~/.config/moodle-cli/config.toml
# Change: default_profile = "oldname"
# To:     default_profile = "newname"
```

## Common Commands

| Command | Description |
|---------|-------------|
| `moodle site info` | Site name, version, release, current user |
| `moodle user me` | Your user details |
| `moodle enrol my-courses` | Your enrolled courses |
| `moodle course list` | All courses |
| `moodle course search "term"` | Search courses |
| `moodle call <wsfunction>` | Raw WS function call (escape hatch) |

## Troubleshooting

### "Could not connect to https://moodle.example.com"

This means no profile is active or the default profile points to the placeholder URL. Causes and fixes:

1. **No login yet** — Run `moodle auth login` first.
2. **Wrong default profile** — Check `~/.config/moodle-cli/config.toml` and ensure `default_profile` points to the correct profile name.
3. **Use explicit profile** — `moodle --profile <name> <command>` bypasses the default.

### Config file structure

```toml
default_profile = "default"   # <-- active profile name

[profiles.default]
url = "https://moodle.ikasten.io"
username = "teacher"
service = "moodle_mobile_app"
```

### Token not found / re-authentication needed

Tokens are stored in the OS keyring. If `moodle auth status` shows "not authenticated", re-run `moodle auth login`.

## Architecture (for contributors)

```
CLI (Click groups) → Services (typed wrappers) → Client (MoodleHTTPClient.call())
```

- `src/moodle_cli/client/http.py` — core HTTP client
- `src/moodle_cli/services/*.py` — typed service wrappers, return Pydantic models
- `src/moodle_cli/cli/*.py` — Click command groups
- `src/moodle_cli/config/` — TOML profile manager + keyring token store
- `src/moodle_cli/output/` — Rich tables + JSON renderer

## Dev Commands

```bash
uv sync                 # Install dependencies
uv run moodle --help    # CLI help
uv run pytest           # Run tests (30 tests)
uv run ruff check src/  # Lint
uv run mypy src/        # Type check
```
