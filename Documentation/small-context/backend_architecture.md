# Backend Architecture

**Version:** 1.1  
**Last Updated:** December 17, 2025  
**Purpose:** Overview of LAMB backend structure, dual API design, and core components  
**Related Docs:** `backend_completions_pipeline.md`, `backend_authentication.md`, `backend_organizations.md`, `lamb_architecture.md` (Section 17: Centralized Logging System)

---

## System Overview

LAMB backend is a FastAPI application with a **dual-tier API architecture**:

```
┌───────────────────────────────────────────────────────────────┐
│                    Frontend (Browser)                          │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────────────┐
│         Creator Interface API (/creator)                       │
│         - User authentication & session management             │
│         - File operations (upload/download)                    │
│         - Enhanced request validation                          │
│         - Acts as proxy with additional logic                  │
│         Location: /backend/creator_interface/                  │
└────────────────────────────┬──────────────────────────────────┘
                             │ (Internal HTTP calls)
                             ▼
┌───────────────────────────────────────────────────────────────┐
│         LAMB Core API (/lamb/v1)                               │
│         - Direct database access                               │
│         - Core business logic                                  │
│         - Assistant, user, organization management             │
│         - Completions processing                               │
│         Location: /backend/lamb/                               │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Database/OWI  │
                    └────────────────┘
```

---

## Why Dual API?

**Separation of Concerns:**
- User-facing logic (auth, validation) separated from core operations
- Creator Interface handles HTTP sessions, file uploads, user-specific operations
- Core API focuses on business logic and data management

**Flexibility:**
- Creator Interface can add features without modifying core
- Core API remains stable and focused
- Each layer can evolve independently

**Security:**
- Additional validation layer before core operations
- Token verification happens at Creator Interface
- Core API can be kept internal if needed

---

## Technology Stack

- **FastAPI** - Modern async Python web framework
- **Python 3.11** - Latest stable Python
- **SQLite** - Database for LAMB data
- **Pydantic** - Request/response validation
- **httpx** - Async HTTP client for internal calls

---

## Main Entry Point

**File:** `/backend/main.py`

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="LAMB Platform")

# Mount LAMB Core API
app.mount("/lamb", lamb_app)

# Mount Creator Interface API
app.mount("/creator", creator_app)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# OpenAI-compatible endpoints
@app.get("/v1/models")
async def list_models(request: Request):
    """List assistants as OpenAI models"""
    # Forwards to completions module
    pass

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Generate chat completions"""
    # Forwards to completions module
    pass

# Health check
@app.get("/status")
async def status():
    return {"status": "ok"}

# SPA catch-all
@app.get("/{path:path}")
async def serve_spa(path: str):
    """Serve frontend SPA"""
    return FileResponse("static/frontend/index.html")
```

**Mounted Applications:**
- `/lamb` → LAMB Core API (`backend/lamb/main.py`)
- `/creator` → Creator Interface API (`backend/creator_interface/main.py`)
- `/static` → Static file serving
- `/{path:path}` → SPA catch-all (serves frontend)

**Key Endpoints:**
- `GET /v1/models` - List assistants as OpenAI models
- `POST /v1/chat/completions` - Generate completions (OpenAI-compatible)
- `GET /status` - Health check

---

## LAMB Core API

**File:** `/backend/lamb/main.py`  
**Mount:** `/lamb/v1`

### Mounted Routers

| Router | Prefix | Purpose | File |
|--------|--------|---------|------|
| assistant_router | `/v1/assistant` | Assistant CRUD | `assistant_router.py` |
| lti_users_router | `/v1/lti_users` | LTI user management | `lti_users_router.py` |
| owi_router | `/v1/OWI` | OWI integration | `owi_bridge/owi_router.py` |
| simple_lti_router | `/simple_lti` | LTI launch handling | `simple_lti/simple_lti_main.py` |
| creator_user_router | `/v1/creator_user` | Creator user management | `creator_user_router.py` |
| completions_router | `/v1/completions` | Completion generation | `completions/main.py` |
| config_router | `/v1/config` | System configuration | `config_router.py` |
| mcp_router | `/v1/mcp` | MCP endpoints | `mcp_router.py` |
| organization_router | `/v1` | Organization management | `organization_router.py` |

### Key Features

**Direct Database Access:**
- Uses `LambDatabaseManager` for all database operations
- No additional abstraction layers
- Fast and efficient queries

**Business Logic:**
- Assistant creation, update, deletion
- User management
- Organization operations
- LTI integration

**Internal Use:**
- Primarily called by Creator Interface API
- Can be called directly for system operations
- Not directly exposed to frontend (except completions)

---

## Creator Interface API

**File:** `/backend/creator_interface/main.py`  
**Mount:** `/creator`

### Mounted Routers

| Router | Prefix | Purpose | File |
|--------|--------|---------|------|
| assistant_router | `/creator/assistant` | Assistant operations (proxied) | `assistant_router.py` |
| knowledges_router | `/creator/knowledgebases` | Knowledge Base operations | `knowledges_router.py` |
| organization_router | `/creator/admin` | Organization management | `organization_router.py` |
| learning_assistant_proxy_router | `/creator` | Learning assistant proxy | `learning_assistant_proxy.py` |

### Direct Endpoints

**Authentication:**
- `POST /creator/login` - User login
- `POST /creator/signup` - User signup
- `GET /creator/user/current` - Get current user info

**User Management (Admin):**
- `GET /creator/users` - List users
- `POST /creator/admin/users/create` - Create user
- `PUT /creator/admin/users/update-role-by-email` - Update user role
- `PUT /creator/admin/users/{id}/status` - Enable/disable user

**File Operations:**
- `GET /creator/files/list` - List user files
- `POST /creator/files/upload` - Upload files
- `DELETE /creator/files/delete/{path}` - Delete files

### Proxy Pattern

Creator Interface often proxies requests to Core API:

```python
@router.get("/assistant/list")
async def list_assistants(request: Request):
    # 1. Validate user token
    creator_user = get_creator_user_from_token(request.headers.get("Authorization"))
    if not creator_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # 2. Call Core API
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{LAMB_BASE_URL}/lamb/v1/assistant/list",
            params={"owner": creator_user['email']}
        )
    
    # 3. Return result
    return response.json()
```

**Benefits:**
- User validation happens once at Creator Interface
- Core API receives pre-validated requests
- Additional processing can be added at proxy layer

---

## Database Layer

### LambDatabaseManager

**File:** `/backend/lamb/database_manager.py`

**Purpose:** Centralized database access for LAMB data

**Key Methods:**

```python
class LambDatabaseManager:
    def __init__(self, db_path: str = None):
        """Initialize database connection"""
        self.db_path = db_path or os.getenv("LAMB_DB_PATH")
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        
    # Organizations
    def create_organization(self, slug, name, config) -> int
    def get_organization_by_slug(self, slug) -> dict
    def update_organization_config(self, org_id, config) -> bool
    
    # Users
    def create_creator_user(self, email, name, organization_id, user_type='creator') -> int
    def get_creator_user_by_email(self, email) -> dict
    def update_user_role(self, user_id, role) -> bool
    
    # Assistants
    def create_assistant(self, assistant_data) -> int
    def get_assistant_by_id(self, assistant_id) -> dict
    def list_assistants(self, owner_email) -> list
    def update_assistant(self, assistant_id, updates) -> bool
    def delete_assistant(self, assistant_id) -> bool
    
    # Organization Roles
    def assign_organization_role(self, org_id, user_id, role) -> bool
    def get_user_organization_role(self, org_id, user_id) -> str
```

**Database File:** `$LAMB_DB_PATH/lamb_v4.db` (default: `/opt/lamb/lamb_v4.db`)

See `database_schema.md` for complete schema documentation.

---

## OWI Bridge

**Directory:** `/backend/lamb/owi_bridge/`

**Purpose:** Deep integration with Open WebUI

### Components

| Component | Purpose | File |
|-----------|---------|------|
| `OwiDatabaseManager` | Direct OWI database access | `owi_database.py` |
| `OwiUserManager` | User operations | `owi_users.py` |
| `OwiGroupManager` | Group operations for LTI | `owi_group.py` |
| `OwiModelManager` | Model registration | `owi_model.py` |

### Integration Points

1. **User Authentication:**
   - OWI manages user credentials (bcrypt passwords)
   - OWI generates JWT tokens
   - LAMB validates tokens via OWI bridge

2. **Model Management:**
   - Published assistants registered as OWI models
   - Model ID format: `lamb_assistant.{assistant_id}`
   - Model points to LAMB completion endpoint

3. **Knowledge Base:**
   - OWI's ChromaDB stores document vectors
   - LAMB KB Server manages collections
   - RAG processors query OWI ChromaDB

4. **Group Management:**
   - OWI groups control assistant access
   - LTI users added to groups automatically
   - Group permissions enforced by OWI

**OWI Database:** `$OWI_PATH/webui.db`

See `backend_authentication.md` for auth flow details.

---

## Configuration

### Environment Variables

**Location:** Set in Docker Compose or `.env` file

**Required:**
```bash
# Database paths
LAMB_DB_PATH=/opt/lamb
OWI_PATH=/app/backend/data

# API endpoints
LAMB_BASE_URL=http://localhost:9099
OWI_BASE_URL=http://openwebui:8080
OWI_PUBLIC_BASE_URL=http://localhost:8080

# Authentication
LAMB_BEARER_TOKEN=your-secure-token
SECRET_KEY=your-secret-key

# Signup
SIGNUP_ENABLED=false
SIGNUP_SECRET_KEY=system-signup-key
```

**Optional:**
```bash
# LLM Providers (fallback if not in org config)
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Knowledge Base
KB_SERVER_URL=http://localhost:9090
KB_API_KEY=kb-api-key

# Logging
LOG_LEVEL=INFO
```

### Configuration Priority

1. **Organization Config** (highest priority)
2. **Environment Variables**
3. **Defaults** (lowest priority)

See `backend_organizations.md` for org config details.

---

## Request Flow Examples

### Create Assistant

```
Frontend
  │
  │ POST /creator/assistant/create
  │ Authorization: Bearer {token}
  │ Body: { name, system_prompt, metadata, ... }
  ▼
Creator Interface API
  │
  │ 1. Validate token → get creator_user
  │ 2. Extract organization from user
  │ 3. Proxy to Core API
  ▼
LAMB Core API
  │
  │ 4. Validate data
  │ 5. Insert into database
  │ 6. Return assistant ID
  ▼
Creator Interface API
  │
  │ 7. Return success to frontend
  ▼
Frontend
```

### Generate Completion

```
Open WebUI / Client
  │
  │ POST /v1/chat/completions
  │ Authorization: Bearer {api_key}
  │ Body: { model: "lamb_assistant.1", messages: [...] }
  ▼
Main Entry Point
  │
  │ Route to completions module
  ▼
Completions Pipeline
  │
  │ 1. Validate API key
  │ 2. Parse model ID → assistant_id
  │ 3. Load assistant from database
  │ 4. Load plugins (PPS, Connector, RAG)
  │ 5. Execute RAG (if configured)
  │ 6. Process messages (PPS)
  │ 7. Call LLM (Connector)
  │ 8. Stream/return response
  ▼
Client
```

See `backend_completions_pipeline.md` for detailed completion flow.

---

## Error Handling

### HTTP Exception Pattern

```python
from fastapi import HTTPException

@router.get("/assistant/{id}")
async def get_assistant(id: int, request: Request):
    # Validate user
    user = get_creator_user_from_token(request.headers.get("Authorization"))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Get assistant
    db = LambDatabaseManager()
    assistant = db.get_assistant_by_id(id)
    
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    
    # Check ownership
    if assistant['owner'] != user['email']:
        raise HTTPException(status_code=403, detail="Not authorized to access this assistant")
    
    return assistant
```

### Standard Error Response

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Status Codes:**
- `400` - Bad request (invalid data)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (no permission)
- `404` - Not found (resource doesn't exist)
- `409` - Conflict (duplicate resource)
- `500` - Internal server error

---

## Centralized Logging System

The LAMB backend implements a centralized logging system that provides unified, environment-based configuration for all logging operations.

**See:** `lamb_architecture.md` Section 17 for comprehensive documentation.

#### Basic Usage

```python
from lamb.logging_config import get_logger

# Get a logger for the current module
logger = get_logger(__name__, component="MAIN")

# Use standard Python logging
logger.info("Assistant created successfully")
logger.debug("Processing request for user")
logger.warning("Fallback model used")
logger.error("Failed to connect to KB server")
```

#### Supported Components

| Component | Use Case | Environment Variable |
|-----------|----------|----------------------|
| MAIN | Main application logic | `MAIN_LOG_LEVEL` |
| API | API endpoints and routers | `API_LOG_LEVEL` |
| DB | Database operations | `DB_LOG_LEVEL` |
| RAG | RAG pipeline operations | `RAG_LOG_LEVEL` |
| EVALUATOR | Evaluation/grading components | `EVALUATOR_LOG_LEVEL` |
| OWI | Open WebUI integration | `OWI_LOG_LEVEL` |

#### Environment Configuration

**Global Control (all components):**
```bash
GLOBAL_LOG_LEVEL=WARNING  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Component-Specific Overrides (optional):**
```bash
GLOBAL_LOG_LEVEL=INFO      # Default for all components
DB_LOG_LEVEL=DEBUG         # Override: Database logs at DEBUG
RAG_LOG_LEVEL=DEBUG        # Override: RAG logs at DEBUG
```

#### Development Examples

**Development (All DEBUG):**
```bash
GLOBAL_LOG_LEVEL=DEBUG
```

**Development (Selective Debugging):**
```bash
GLOBAL_LOG_LEVEL=INFO
DB_LOG_LEVEL=DEBUG        # Only database logs at DEBUG
API_LOG_LEVEL=DEBUG       # Only API logs at DEBUG
```

**Production (Clean Logs):**
```bash
GLOBAL_LOG_LEVEL=WARNING
```

**Production (Monitor Specific Issues):**
```bash
GLOBAL_LOG_LEVEL=WARNING
OWI_LOG_LEVEL=INFO        # Watch OWI operations
API_LOG_LEVEL=INFO        # Watch API operations
```

### Implementation Details

#### Centralized Module

**Location:** `/backend/lamb/logging_config.py`

Provides:
- Global log level configuration via `GLOBAL_LOG_LEVEL` environment variable
- Component-specific log level overrides
- `get_logger(name, component)` function for creating configured loggers

#### Migration from Legacy System

The legacy `Timelog` utility has been removed. Migration pattern:

```python
# Old code (REMOVED)
from utils.timelog import Timelog
Timelog("Processing message", 1)

# New code
from lamb.logging_config import get_logger
logger = get_logger(__name__, component="MAIN")
logger.info("Processing message")
```

**Migration Levels:**
- `Timelog(msg, 1)` → `logger.info(msg)` (important messages)
- `Timelog(msg, 2)` → `logger.debug(msg)` (detailed debugging)
- `Timelog(msg, 3)` → `logger.debug(msg)` (very detailed information)

### Best Practices

1. **Use Component Categories:** Always specify the appropriate component when creating loggers
   ```python
   logger = get_logger(__name__, component="DB")  # Database operations
   logger = get_logger(__name__, component="API") # API endpoints
   ```

2. **Environment-Based Configuration:** Avoid hardcoding log levels
   ```bash
   # Good: Set via environment
   DB_LOG_LEVEL=DEBUG
   
   # Avoid: Hardcoding in code
   logger.setLevel(logging.DEBUG)
   ```

3. **Structured Information:** Include relevant context in log messages
   ```python
   # Good: Include IDs, emails, etc.
   logger.info(f"Assistant created: id={assistant_id}, owner={owner_email}")
   
   # Avoid: Vague messages
   logger.info("Assistant created")
   ```

4. **Appropriate Log Levels:**
   - `DEBUG` - Detailed information for diagnosing problems
   - `INFO` - General informational messages about application operation
   - `WARNING` - Something unexpected or configuration issue
   - `ERROR` - Error that needs attention
   - `CRITICAL` - Critical error that may prevent operation

### Output

All logs are written to **stdout** for proper container log aggregation. When running with Docker Compose, logs are captured and available via:

```bash
docker-compose logs -f lamb-backend
```

### Container Deployment

In Docker containers, set log levels via environment variables:

```yaml
# docker-compose.yaml
services:
  lamb-backend:
    environment:
      GLOBAL_LOG_LEVEL: WARNING
      DB_LOG_LEVEL: INFO
      API_LOG_LEVEL: INFO
```

---

## Development Workflow

### Running Backend

```bash
cd /opt/lamb/backend
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 9099
```

### Running with Docker

```bash
docker-compose up -d
```

### Testing Endpoints

```bash
# Health check
curl http://localhost:9099/status

# List models (requires token)
curl http://localhost:9099/v1/models \
  -H "Authorization: Bearer your-token"

# Create assistant
curl -X POST http://localhost:9099/creator/assistant/create \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Assistant",
    "system_prompt": "You are helpful.",
    "metadata": "{\"connector\": \"openai\", \"llm\": \"gpt-4o-mini\"}"
  }'
```

---

## File Structure

```
/backend/
├── main.py                    # Main entry point
├── config.py                  # Configuration loading
├── schemas.py                 # Pydantic schemas
├── requirements.txt           # Python dependencies
├── lamb/                      # Core API
│   ├── main.py
│   ├── database_manager.py
│   ├── assistant_router.py
│   ├── creator_user_router.py
│   ├── organization_router.py
│   ├── completions/           # Completion pipeline
│   │   ├── main.py
│   │   ├── pps/               # Prompt processors
│   │   ├── connectors/        # LLM connectors
│   │   └── rag/               # RAG processors
│   ├── owi_bridge/            # OWI integration
│   │   ├── owi_database.py
│   │   ├── owi_users.py
│   │   ├── owi_group.py
│   │   └── owi_model.py
│   └── simple_lti/            # LTI integration
│       └── simple_lti_main.py
└── creator_interface/         # Creator Interface API
    ├── main.py
    ├── assistant_router.py
    ├── knowledges_router.py
    ├── organization_router.py
    └── user_creator.py
```

---

## Related Documentation

- **Completions Pipeline:** `backend_completions_pipeline.md`
- **Authentication:** `backend_authentication.md`
- **Organizations:** `backend_organizations.md`
- **Knowledge Base:** `backend_knowledge_base.md`
- **LTI Integration:** `backend_lti_integration.md`
- **Database Schema:** `database_schema.md`
- **API Reference:** `api_reference.md`

