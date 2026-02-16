# LAMB Documentation Index

> **Quick Navigation Guide for Developers, DevOps Engineers, and AI Agents**

This index helps you find exactly what you need in the LAMB documentation. Start here when you're looking for something specific.

---

## 🎯 I Want To...

### Understand the System

| Goal | Document | Section |
|------|----------|---------|
| Get a high-level overview | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §1 System Overview |
| Understand the dual API design | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §3 Dual API Architecture |
| Learn about multi-tenancy | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §7 Organizations |
| Understand the completion pipeline | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §6 Completion Pipeline |

### Set Up Development Environment

| Goal | Document | Section |
|------|----------|---------|
| Quick start with Docker | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §10 Development |
| Configure environment variables | [../backend/ENVIRONMENT_VARIABLES.md](../backend/ENVIRONMENT_VARIABLES.md) | Full doc |
| Deploy to production | [deployment.apache.md](./deployment.apache.md) | Full doc |

### Work with the Backend

| Goal | Document | Section |
|------|----------|---------|
| Add a new API endpoint | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §3 Dual API Architecture |
| Create a custom plugin | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §6.4 Plugin System |
| Understand database schema | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §4 Data Architecture |
| Work with authentication | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §5 Authentication |
| Configure logging | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §11 Logging |

### Work with the Frontend

| Goal | Document | Section |
|------|----------|---------|
| Understand frontend structure | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §9 Frontend Architecture |
| Handle form state (Svelte 5) | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §9.3 UX Patterns |
| Avoid async race conditions | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §9.3 UX Patterns |

### Implement Features

| Goal | Document | Section |
|------|----------|---------|
| Add Knowledge Base support | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §8.1 Knowledge Base |
| Implement LTI integration | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §8.2 LTI Integration |
| Add assistant sharing | [lamb_architecture_v2.md](./lamb_architecture_v2.md) | §8.3 Assistant Sharing |
| View chat analytics | [chat_analytics_project.md](./chat_analytics_project.md) | Full doc |

---

## 📁 Documentation Map

```
Documentation/
├── DOCUMENTATION_INDEX.md      ← YOU ARE HERE
├── lamb_architecture_v2.md     ← Main architecture guide (START HERE)
├── lamb_architecture.md        ← Full detailed reference (legacy)
├── lamb_architecture_small.md  ← Condensed version (legacy)
│
├── chat_analytics_project.md   ← Chat analytics feature spec
├── prd.md                      ← Product requirements
├── deployment.apache.md        ← Apache deployment guide
├── installationguide.md        ← Installation instructions
├── training.md                 ← Training materials
├── multimodality.md            ← Multimodal support docs
│
├── ER-diagrams/                ← Database diagrams
│   ├── creator_users.md
│   ├── assistant_shares.md
│   └── ...
│
├── small-context/              ← Compact docs for LLM context
│   └── ...
│
└── slop-docs/                  ← Auto-generated docs
    └── ...
```

---

## 🗂️ Key File Locations

### Backend (`/backend/`)

```
backend/
├── main.py                           # Main entry point, mounts all routers
├── config.py                         # Configuration management
├── schemas.py                        # Pydantic models
│
├── lamb/                             # LAMB Core API
│   ├── main.py                       # Core router setup
│   ├── database_manager.py           # LAMB database operations
│   ├── assistant_router.py           # Assistant CRUD
│   ├── organization_router.py        # Organization management
│   ├── logging_config.py             # Centralized logging
│   │
│   ├── completions/                  # Completion pipeline
│   │   ├── main.py                   # Pipeline orchestration
│   │   ├── pps/                      # Prompt processors
│   │   │   └── simple_augment.py
│   │   ├── connectors/               # LLM connectors
│   │   │   ├── openai.py
│   │   │   ├── ollama.py
│   │   │   └── banana_img.py
│   │   └── rag/                      # RAG processors
│   │       └── simple_rag.py
│   │
│   ├── owi_bridge/                   # Open WebUI integration
│   │   ├── owi_database.py
│   │   ├── owi_users.py
│   │   ├── owi_group.py
│   │   └── owi_model.py
│   │
│   ├── services/                     # Business logic services
│   │   └── chat_analytics_service.py
│   │
│   └── simple_lti/                   # LTI integration
│       └── simple_lti_main.py
│
├── creator_interface/                # Creator Interface API
│   ├── main.py                       # Creator router setup
│   ├── assistant_router.py           # Proxied assistant ops
│   ├── knowledges_router.py          # KB operations
│   ├── organization_router.py        # Org admin
│   ├── analytics_router.py           # Chat analytics
│   ├── evaluaitor_router.py          # Rubric management
│   ├── prompt_templates_router.py    # Prompt templates
│   └── user_creator.py               # User creation
│
└── utils/                            # Utilities
    ├── main_helpers.py
    └── name_sanitizer.py
```

### Frontend (`/frontend/svelte-app/`)

```
frontend/svelte-app/
├── src/
│   ├── routes/                       # SvelteKit pages
│   │   ├── +layout.svelte            # Root layout
│   │   ├── +page.svelte              # Home (redirects)
│   │   ├── assistants/+page.svelte   # Assistants list
│   │   ├── knowledge-bases/+page.svelte
│   │   ├── admin/+page.svelte        # System admin
│   │   └── org-admin/+page.svelte    # Org admin
│   │
│   ├── lib/
│   │   ├── components/               # UI components
│   │   │   ├── Nav.svelte
│   │   │   ├── Login.svelte
│   │   │   ├── assistants/
│   │   │   │   └── AssistantForm.svelte
│   │   │   └── analytics/
│   │   │       └── ChatAnalytics.svelte
│   │   │
│   │   ├── services/                 # API clients
│   │   │   ├── authService.js
│   │   │   ├── assistantService.js
│   │   │   ├── knowledgeBaseService.js
│   │   │   └── adminService.js
│   │   │
│   │   ├── stores/                   # Svelte stores
│   │   │   ├── userStore.js
│   │   │   └── assistantStore.js
│   │   │
│   │   └── config.js                 # Runtime config
│   │
│   └── app.html                      # HTML template
│
├── static/
│   └── config.js.sample              # Config template
│
└── package.json
```

### Databases

| Database | Location | Purpose |
|----------|----------|---------|
| LAMB DB | `$LAMB_DB_PATH/lamb_v4.db` | Assistants, users, orgs |
| OWI DB | `$OWI_DATA_PATH/webui.db` | Chat history, mirror users, groups, models |
| ChromaDB | `$OWI_DATA_PATH/vector_db/` | KB vectors |

---

## 🔑 Key Concepts Quick Reference

### Dual API Architecture
```
Browser → Creator Interface API (/creator) → LAMB Core API (/lamb/v1) → Database
```
- **Creator Interface**: User-facing, handles auth, file uploads, validation
- **LAMB Core**: Business logic, database operations, completions

### Plugin Types
| Type | Purpose | Location |
|------|---------|----------|
| Prompt Processor | Transform messages | `lamb/completions/pps/` |
| Connector | Call LLM providers | `lamb/completions/connectors/` |
| RAG Processor | Retrieve KB context | `lamb/completions/rag/` |

### User Types
| Type | Access |
|------|--------|
| `creator` | Full creator interface access |
| `end_user` | Redirected to Open WebUI only |

### Organization Roles
| Role | Permissions |
|------|-------------|
| `owner` | Full control |
| `admin` | Manage settings and members |
| `member` | Create assistants |

---

## 🛠️ Common Development Tasks

### Add a New Backend Endpoint

1. **Choose the right router:**
   - User-facing → `creator_interface/*.py`
   - Internal/core → `lamb/*.py`

2. **Add endpoint:**
   ```python
   @router.get("/my-endpoint")
   async def my_endpoint(request: Request):
       # Implementation
   ```

3. **Register in router** (if new file)

### Add a New Frontend Page

1. Create `src/routes/my-page/+page.svelte`
2. Add navigation link in `Nav.svelte`
3. Create service functions in `lib/services/`

### Create a New Plugin

1. Create file in appropriate directory:
   - `lamb/completions/pps/my_pps.py`
   - `lamb/completions/connectors/my_connector.py`
   - `lamb/completions/rag/my_rag.py`

2. Implement required function signature (see §6.4 in architecture doc)

3. Configure assistant to use it via metadata

### Add a Database Field

1. Add migration in `database_manager.py` → `run_migrations()`
2. Update relevant queries
3. Update Pydantic schemas if needed

---

## 📊 API Endpoint Quick Reference

### Authentication
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/creator/login` | User login |
| POST | `/creator/signup` | User signup |
| GET | `/creator/user/current` | Get current user |

### Assistants
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/creator/assistant/list` | List user's assistants |
| POST | `/creator/assistant/create` | Create assistant |
| GET | `/creator/assistant/{id}` | Get assistant |
| PUT | `/creator/assistant/update` | Update assistant |
| DELETE | `/creator/assistant/delete/{id}` | Delete assistant |

### Knowledge Bases
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/creator/knowledgebases/user` | List user's KBs |
| POST | `/creator/knowledgebases/create` | Create KB |
| POST | `/creator/knowledgebases/{id}/upload` | Upload document |
| GET | `/creator/knowledgebases/{id}/query` | Query KB |

### Completions (OpenAI-compatible)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/v1/models` | List available assistants |
| POST | `/v1/chat/completions` | Generate completion |

### Admin
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/creator/admin/users` | List users |
| POST | `/creator/admin/users/create` | Create user |
| PUT | `/creator/admin/users/{id}/status` | Enable/disable user |

---

## 🔗 External Resources

- **GitHub:** https://github.com/Lamb-Project/lamb
- **Website:** https://lamb-project.org
- **Open WebUI:** https://github.com/open-webui/open-webui

---

## 📝 Document Versions

| Document | Purpose | When to Use |
|----------|---------|-------------|
| `lamb_architecture_v2.md` | **Primary reference** | Start here for any task |
| `lamb_architecture.md` | Full detailed reference | Deep implementation details |
| `lamb_architecture_small.md` | Legacy condensed | Deprecated, use v2 |

---

*Last Updated: February 13, 2026*

