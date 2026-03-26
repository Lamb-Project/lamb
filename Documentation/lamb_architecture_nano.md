## LAMB Project — Minimal Context for LLMs

**LAMB** is a **multi-tenant AI assistant platform** for institutions (education-focused) that lets non-technical users create, manage, and deploy LLM-powered assistants with plugins, RAG, analytics, and LMS (LTI) integration.

### Core Architecture

* **Backend:** FastAPI (Python 3.11)
* **Frontend:** SvelteKit (creator/admin UI)
* **Auth & Chat UI:** Open WebUI (OWI)
* **Knowledge Base:** Separate FastAPI service + ChromaDB
* **LLMs:** OpenAI-compatible APIs (OpenAI, Ollama, Anthropic, etc.)

### Services & Ports

* Backend API: `:9099`
* Knowledge Base Server: `:9090`
* Open WebUI: `:8080`
* Frontend (dev): `:5173` (dev server)
* Production frontend build served from `backend/static/frontend/` and is served by the backend in prod

### Docker (dev/prod)
* Dev uses docker-compose to run all services + volumes; env vars LAMB_DB_PATH, OWI_DATA_PATH, KB_SERVER_URL, OPENAI_API_KEY.

### Dual API Design

* **Creator Interface API (`/creator/*`)**

  * User-facing logic, auth, validation, file uploads
  * Proxies to core API
* **LAMB Core API (`/lamb/v1/*`)**

  * Business logic, DB access, completions, org/user/assistant management

### Key Concepts

* **Organization = Tenant**

  * Isolated users, assistants, configs, KBs
  * Roles: `owner`, `admin`, `member`
* **Users**

  * `creator` (can build assistants)
  * `end_user` (chat only, no creation)
* **Assistants**

  * Stored in DB, published to OWI as chat “models”
  * Config includes system prompt, model, temperature, plugins, API key
* **OpenAI API Compatibility**

  * `/v1/chat/completions`
  * Assistants queried via API key like OpenAI models

### Data Stores

* **LAMB DB (SQLite):**

  * organizations, users, assistants, assistant_shares
  * knowledge base registry, prompt templates
  * LTI users, analytics
* **OWI DB (SQLite):**

  * auth, users, sessions, chat history, models
* **ChromaDB:**

  * Vector storage for RAG
  * Collections scoped by org + user

### Authentication

* User login via `/creator/login`
* Tokens validated against OWI DB
* Assistant completions authenticated via **assistant API keys**
* Role & org checks enforced at API layer

### Completion Pipeline (Critical)

1. Validate assistant API key
2. Load assistant + org config
3. Load plugins from `assistant.metadata`
4. **RAG plugin** (optional): query KB, inject context
5. **Prompt Processor (PPS)**: transform messages/templates
6. **Connector**: call LLM provider (OpenAI/Ollama/etc.)
7. Stream or return OpenAI-format response
8. Log usage + analytics

### Plugin System (Extensible)

* **Plugin types:**

  * `connector` (LLM providers)
  * `rag` (knowledge retrieval)
  * `pps` (prompt/message processing)
* Plugins implement hooks:

  * `before_completion`
  * `run_completion`
  * `after_completion`
* Configured per assistant via JSON metadata

### Knowledge Bases (RAG)

* Created per user/org
* Documents chunked, embedded, stored in ChromaDB
* Assistants can reference multiple KBs
* RAG injects retrieved context into prompts
* KB sharing: private / organization

### Publishing & Chat

* Assistants published to OWI appear as chat models
* End users chat via OWI UI
* LTI launches auto-login users and open assistant chat


### LTI (Education)

* LTI 1.1 compliant
* LMS → LAMB → OWI session → assistant chat
* Automatic user provisioning
* Assistant-specific LTI launch URLs

### Frontend (Creator UI)

* Assistant CRUD
* KB management
* Org & user admin
* Analytics dashboards
* Uses REST calls to `/creator/*`

### Analytics

* Tracks chats, messages, usage per assistant
* Only visible to assistant owners
* Optional anonymization of end users

### Key Files / Locations

* `/backend/main.py` – app entry, mounts APIs + SPA
* `/backend/lamb/` – core logic
* `/backend/creator_interface/` – creator API
* `/backend/lamb/completions/` – completion pipeline + plugins
* `/frontend/svelte-app/` – SvelteKit UI

### Design Principles

* Privacy-first
* Modular & replaceable components
* Plugin-driven extensibility
* Strong org isolation
* OpenAI API compatibility
