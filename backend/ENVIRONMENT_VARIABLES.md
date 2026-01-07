# LAMB Backend Environment Variables

This document describes all environment variables used by the LAMB backend.

## Required Configuration

### Database Configuration

- **`LAMB_DB_PATH`** (required)
  - Path to the LAMB SQLite database file
  - Example: `/opt/lamb/lamb_v4.db`

- **`OWI_PATH`** (required)
  - Path to the Open WebUI **backend data** directory
  - Example: `/opt/lamb/open-webui/backend/data`

## LAMB Host Configuration

### `LAMB_WEB_HOST`

**Purpose**: External/public URL for browser-side requests, and API requests coming from outside the docker network

**Usage**: 
- Used by the frontend for API calls
- Used for generating URLs that browsers need to access (e.g., profile images, static assets)

**Examples**:
- Development: `http://localhost:9099`
- Production: `https://lamb.yourdomain.com`

**Default**: Falls back to `PIPELINES_HOST` (to be deprecated) if not set, otherwise `http://localhost:9099`

### `LAMB_BACKEND_HOST`

**Purpose**: Internal loopback URL for server-side requests, usually originated from docker network

**Usage**:
- Used for internal API calls from Creator Interface to LAMB Core
- Both APIs run in the same container or server, so this should always use "localhost"

**Examples**:
- Development: `http://localhost:9099`
- Production: `http://localhost:9099` or `http://127.0.0.1:9099`

**Default**: `http://localhost:9099`

**Why separate from LAMB_WEB_HOST?**

In production deployments:
- `LAMB_WEB_HOST` points to the public domain (e.g., `https://lamb.yourdomain.com`)
- `LAMB_BACKEND_HOST` uses localhost to avoid unnecessary network hops through load balancers/reverse proxies
- This separation improves performance, security, and reliability

### `PIPELINES_HOST` (Deprecated)

**Status**: Deprecated but still supported for backward compatibility

**Purpose**: Legacy variable that was used for both web and backend URLs

**Migration**: New deployments should use `LAMB_WEB_HOST` and `LAMB_BACKEND_HOST` instead

**Default**: If set, `LAMB_WEB_HOST` will use this as a fallback

## Authentication & Security

### `LAMB_BEARER_TOKEN`

**Purpose**: Bearer token for API authentication

**Default**: `0p3n-w3bu!`

**Security Note**: Change this in production deployments

### `PIPELINES_BEARER_TOKEN` (Deprecated)

**Status**: Deprecated but still supported for backward compatibility

**Purpose**: Legacy variable for bearer token

**Migration**: New deployments should use `LAMB_BEARER_TOKEN` instead

**Default**: If set, `LAMB_BEARER_TOKEN` will use this as a fallback

### `SIGNUP_ENABLED`

**Purpose**: Enable/disable user signup functionality

**Values**: `true` or `false`

**Default**: `false`

### `SIGNUP_SECRET_KEY`

**Purpose**: Secret key for signup token generation

**Default**: `pepino-secret-key`

**Security Note**: Change this in production deployments

## Open WebUI Integration

### `OWI_BASE_URL`

**Purpose**: Internal URL for backend-to-OpenWebUI API calls

**Usage**:
- Used by LAMB backend services for internal API calls (RAG queries, file uploads, model creation, auth)
- Should point to the internal/service-to-service URL

**Examples**:
- Development: `http://localhost:8080`
- Docker Compose: `http://openwebui:8080` (using service name)
- Production: `http://localhost:8080` or internal network URL

**Default**: `http://localhost:8080`

### `OWI_PUBLIC_BASE_URL`

**Purpose**: Public-facing URL for browser redirects and login URLs
**Usage**:
- Used for generating login URLs that browsers need to access
- Used for LTI redirects
- Used for any URL that will be sent to a user's browser

**Examples**:
- Development: `http://localhost:8080` (same as internal)
- Production with reverse proxy: `https://openwebui.yourdomain.com`
- Production without reverse proxy: `http://your-server-ip:8080`

**Default**: Falls back to `OWI_BASE_URL` if not set

**Why separate from OWI_BASE_URL?**

In production deployments with Docker or reverse proxies:
- `OWI_BASE_URL` can use internal service names (e.g., `http://openwebui:8080` in Docker)
- `OWI_PUBLIC_BASE_URL` must use the public URL that browsers can reach (e.g., `https://openwebui.yourdomain.com`)
- This separation allows services to communicate efficiently internally while providing correct URLs to users

### OWI Admin Configuration

These variables are used for initial admin account setup:

- **`OWI_ADMIN_NAME`** - Default: `Admin`
- **`OWI_ADMIN_EMAIL`** - Default: `admin@lamb.com`
- **`OWI_ADMIN_PASSWORD`** - Default: `admin`

**Security Note**: Change the default password in production

## Optional Configuration

### `DEV_MODE`

**Purpose**: Enable development mode features

**Values**: `true` or `false`

**Default**: `false`

### `LAMB_DB_PREFIX`

**Purpose**: Database table prefix for multi-tenant setups

**Default**: Empty string

### `PIPELINES_DIR` (deprecated)

**Purpose**: Directory for storing pipeline/assistant files

**Default**: `./lamb_assistants`

### `GLOBAL_LOG_LEVEL`

**Purpose**: Sets the default logging verbosity for the backend.

**Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Default**: `INFO` (the sample `.env` sets `WARNING`)

### Component-specific log levels

**Purpose**: Override the global level for specific components.

**Variables**: `MAIN_LOG_LEVEL`, `API_LOG_LEVEL`, `DB_LOG_LEVEL`, `RAG_LOG_LEVEL`, `EVALUATOR_LOG_LEVEL`, `OWI_LOG_LEVEL`

**Default**: Unset (each falls back to `GLOBAL_LOG_LEVEL`)

## LLM Configuration

### Ollama

- **`OLLAMA_BASE_URL`** - Default: `http://localhost:11434`
- **`OLLAMA_MODEL`** - Default: `llama3.1:latest`

### OpenAI

- **`OPENAI_API_KEY`** - Required if using OpenAI
- **`OPENAI_BASE_URL`** - Default: `https://api.openai.com/v1`
- **`OPENAI_MODEL`** - Default: `gpt-4o-mini`

### Google Gemini Image Generation

These variables configure the `banana_img` connector for Gemini image generation:

- **`GEMINI_API_KEY`** or **`GOOGLE_API_KEY`** - API key for Google Gen AI
- **`GEMINI_MODELS`** - Comma-separated list of available Gemini image generation models
  - Default: `gemini-2.5-flash-image-preview,gemini-3-pro-image-preview`
  - Use actual Google API model names (no aliases)
- **`GEMINI_DEFAULT_MODEL`** - Default model when assistant specifies an invalid model
  - Default: `gemini-2.5-flash-image-preview`

**Note:** Model names should match the actual Google Gen AI API model IDs. Check [Google's AI documentation](https://ai.google.dev/models) for current model availability.

## Example .env File

```bash
# Required
LAMB_DB_PATH=/path/to/lamb_database.db
OWI_PATH=/path/to/open-webui/backend/data

# Host Configuration
LAMB_WEB_HOST=http://localhost:9099
LAMB_BACKEND_HOST=http://localhost:9099

# Authentication
LAMB_BEARER_TOKEN=your-secure-token-here
SIGNUP_ENABLED=false
SIGNUP_SECRET_KEY=your-secret-key-here

# OWI Integration
OWI_BASE_URL=http://localhost:8080
OWI_PUBLIC_BASE_URL=http://localhost:8080
OWI_ADMIN_EMAIL=admin@lamb.com
OWI_ADMIN_PASSWORD=your-admin-password

# Optional
GLOBAL_LOG_LEVEL=WARNING
# MAIN_LOG_LEVEL=
# API_LOG_LEVEL=
# DB_LOG_LEVEL=
# RAG_LOG_LEVEL=
# EVALUATOR_LOG_LEVEL=
# OWI_LOG_LEVEL=
OLLAMA_BASE_URL=http://localhost:11434

# Gemini Image Generation (optional)
# GEMINI_API_KEY=your-google-api-key
GEMINI_MODELS=gemini-2.5-flash-image-preview,gemini-3-pro-image-preview
GEMINI_DEFAULT_MODEL=gemini-2.5-flash-image-preview
```

## Docker Compose Configuration

When using Docker Compose, the environment variables are loaded from:
1. The `.env` file specified in `env_file` section
2. Individual `environment` settings in `docker-compose.yaml`

The `LAMB_PROJECT_PATH` variable is used in the compose file to mount volumes correctly.

## Production Deployment Notes

For production deployments:

1. **Set `LAMB_WEB_HOST` to your public domain**:
   ```bash
   LAMB_WEB_HOST=https://lamb.yourdomain.com
   ```

2. **Keep `LAMB_BACKEND_HOST` as localhost**:
   ```bash
   LAMB_BACKEND_HOST=http://localhost:9099
   ```

3. **Change all default passwords and tokens**

4. **Set appropriate `GLOBAL_LOG_LEVEL`** (typically `WARNING` or `ERROR` in production)

5. **Disable signup if not needed**:
   ```bash
   SIGNUP_ENABLED=false
   ```

