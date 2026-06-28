# LAMB ↔ Knowledge Stores (new KB Server) Integration — Plan

**Issue:** [#337](https://github.com/Lamb-Project/lamb/issues/337) — depends on new KB Server microservice landed at `lamb-kb-server/` (issue #334, Phase 2A).

**Reference plan:** [#336](https://github.com/Lamb-Project/lamb/issues/336) — LAMB ↔ Library Manager integration. The structure, ADRs, and CRUD/router/auth/audit/permalink patterns from #336 are the template. This plan adds one phase #336 did not have: end-to-end Library → Knowledge Store → Query verification.

---

## 1. Context

The new KB Server (`lamb-kb-server/`, port 9092) was built per the spec in #334 and is deliberately decoupled from LAMB and from the Library Manager — it is a pure compute service that ingests JSON payloads (text + permalinks) and returns chunks with citation metadata. The server is fully tested and dockerized but **has no LAMB-side surface yet**: no router, no DB, no client, no CLI, no frontend, no RAG path. End users cannot reach it.

The existing stable KB Server (`lamb-kb-server-stable/`, port 9090) and its full LAMB integration (`kb_registry`, `/creator/knowledgebases/*`, `kb_server_manager.py`, RAG processors, lamb-cli `kb` commands, `/knowledgebases` Svelte route, Playwright KB tests) **must continue to work unchanged**. Both servers run simultaneously (NFR-1 in #334).

**The user-visible workflow this plan must enable end-to-end:**

```
LAMB → create Library → import file → get markdown
     → create Knowledge Store → ingest library item(s)
     → KB Server chunks + embeds → poll job → ready
     → assistant queries Knowledge Store → answers cite library permalinks
     → user clicks citation → LAMB /docs proxy serves library content via ACL
```

Every link in that chain must work for both lamb-cli and the Svelte frontend, with Playwright coverage that does not touch the existing stable KB tests.

---

## 2. Decisions (locked)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Coexistence by parallel surfaces.** New router, tables, client, auth helpers, RAG processor, CLI surface, frontend route. `kb_registry` and stable surfaces are not modified. | Marc's #334 spec ("both can run simultaneously"); industry standard for v2-alongside-v1; eliminates hot-path branching in fragile RAG code. |
| D2 | **Naming: "Knowledge Stores".** Route `/creator/knowledge-stores`, table `knowledge_stores`, frontend `/knowledge-stores`, CLI `lamb knowledge-store …` (alias `lamb ks`), client `knowledge_store_client.py`. | User-chosen. Distinct from the stable "Knowledge Bases" label, matches the `KnowledgeStorePlugin` foundation from #203/#229, reads naturally on its own. |
| D3 | **Library-only ingestion.** A Knowledge Store is populated exclusively by linking Library items. No direct file upload path. | Matches new KB Server's API (JSON with text + permalinks, no multipart). Matches FR-6 in #334. Every chunk gets a real ACL-enforced permalink for citations. |
| D4 | **Embedding key reuses existing org provider key.** Resolve `setups.default.providers.{vendor}.api_key` already used for completions/RAG; LAMB sends it per-request to the KB Server, which never persists it (ADR-4 in #334). | Org admins set keys once. No duplicate config. |
| D5 | **Embedding vendor + model chosen at create time, locked thereafter.** User selects from the org's allow-list when creating a Knowledge Store; immutable after creation per the new KB Server's ADR-3. | Allow-list keeps cost/data-residency in admin's hands; per-KS choice keeps experimentation possible. |
| D6 | **FR-10 enforcement: a Library item that is referenced by any Knowledge Store cannot be deleted from the Library.** Enforced in LAMB's library-delete-item endpoint via the `kb_content_links` table. | Spec requirement; prevents stale chunks pointing at gone content. |
| D7 | **Permalinks attached to chunks point at LAMB's `/docs/{org}/{lib}/{item}/...` proxy, not at the Library Manager.** | Citations must be ACL-enforced; users never reach the Library Manager directly. Already the model in #336. |
| D8 | **No migration of existing stable KBs to Knowledge Stores.** Stable KBs continue to exist under their existing surfaces. | Out of scope per #334 non-goals. |

---

## 3. Architecture

```
User → lamb-cli                ─┐
User → Svelte frontend           ┼→ LAMB Backend ─→ Library Manager (port 9091)   [content source]
                                 │   (orchestrator)
                                 │       │
                                 │       └────────→ new KB Server (port 9092)     [chunk + embed + query]
                                 │
                                 │  LAMB DB:
                                 │   • knowledge_stores      ← new
                                 │   • kb_content_links      ← new (library item ↔ KS collection)
                                 │   • audit_log             ← reuse existing table

                  (Stable KB Server on port 9090, kb_registry table,
                   /creator/knowledgebases routes, all untouched)
```

LAMB is the only caller of the new KB Server. Every request:

1. Authenticates the user (JWT) via existing `_build_auth_context`.
2. Checks Knowledge-Store ACL via new `can_access_knowledge_store` / `require_knowledge_store_access` (mirroring `can_access_library`).
3. Resolves org config: KB-Server URL/token from `setups.default.knowledge_store`; embedding API key from `setups.default.providers.{vendor}.api_key`.
4. For ingestion: pulls markdown from Library Manager via existing `LibraryManagerClient`, builds permalink set against LAMB's `/docs/...` proxy, posts to KB Server.
5. Records the result in `knowledge_stores` / `kb_content_links`.
6. Writes `audit_log` for mutating operations.

The KB Server trusts LAMB entirely — single bearer token, no user identity, no library awareness.

---

## 4. LAMB Database — New Tables

All new schema goes in `backend/lamb/database_manager.py` as a new migration (next migration number, additive). No changes to `kb_registry` or any other existing table.

### `knowledge_stores`
LAMB's record of each Knowledge Store. Source of truth for ownership, sharing, and the locked store setup.

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | UUID, sent to KB Server as `collection_id` |
| `organization_id` | INT FK | `organizations(id)` ON DELETE CASCADE |
| `name` | TEXT | UNIQUE with `organization_id` |
| `description` | TEXT | |
| `owner_user_id` | INT FK | `Creator_users(id)` |
| `is_shared` | INT | 0/1, same pattern as `kb_registry.is_shared` |
| `chunking_strategy` | TEXT | locked: 'simple', 'hierarchical', 'by_page', 'by_section' |
| `chunking_params` | TEXT | JSON, locked |
| `embedding_vendor` | TEXT | locked: 'openai', 'ollama', 'local' |
| `embedding_model` | TEXT | locked |
| `embedding_endpoint` | TEXT | optional, locked (for ollama/local) |
| `vector_db_backend` | TEXT | locked: 'chromadb', 'qdrant' |
| `status` | TEXT | 'provisional' \| 'active' (mirrors libraries pattern) |
| `created_at` | INT | unix |
| `updated_at` | INT | unix |

Indexes: `(owner_user_id)`, `(organization_id, is_shared)`.

**Status pattern:** insert as `'provisional'`, call KB Server `POST /collections`, promote to `'active'` on success; on failure delete the LAMB row to avoid orphans (proven safe in #336).

### `kb_content_links`
The bridge table that makes FR-10 enforceable and tracks ingestion state per (library item × KS).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INT PK AUTOINCREMENT | |
| `knowledge_store_id` | TEXT FK | `knowledge_stores(id)` ON DELETE CASCADE |
| `library_id` | TEXT FK | `libraries(id)` |
| `library_item_id` | TEXT FK | `library_items(id)` |
| `organization_id` | INT FK | for fast org-scoped queries |
| `kb_job_id` | TEXT | KB Server's job UUID, for status polling |
| `status` | TEXT | 'pending' \| 'processing' \| 'ready' \| 'failed' |
| `chunks_created` | INT | cached from KB Server job result |
| `error_message` | TEXT | |
| `created_by_user_id` | INT FK | `Creator_users(id)` |
| `created_at` | INT | |
| `updated_at` | INT | |

Indexes: `(knowledge_store_id)`, `(library_item_id)` (fast FR-10 lookup), `(status)`.
UNIQUE: `(knowledge_store_id, library_item_id)` — a given item can only be linked to a given KS once.

### `audit_log` reuse
Reuse the existing `audit_log` table from #336. New `action` values: `knowledge_store.create`, `knowledge_store.update`, `knowledge_store.delete`, `knowledge_store.share`, `knowledge_store.unshare`, `knowledge_store.add_content`, `knowledge_store.remove_content`. New `target_type` value: `'knowledge_store'`.

---

## 5. Organization Config

Add a new block under each setup, parallel to the existing `library` and `knowledge_base` blocks:

```json
{
  "setups": {
    "default": {
      "knowledge_store": {
        "server_url": "http://kb-server-v2:9092",
        "api_token": "service-token",
        "allowed_vector_db_backends": ["chromadb", "qdrant"],
        "allowed_chunking_strategies": ["simple", "hierarchical", "by_page", "by_section"],
        "allowed_embedding_vendors": ["openai", "ollama"],
        "allowed_embedding_models": {
          "openai": ["text-embedding-3-small", "text-embedding-3-large"],
          "ollama": ["nomic-embed-text"]
        }
      },
      "providers": { "openai": { "api_key": "..." }, "ollama": { "endpoint": "..." } }
    }
  }
}
```

For the system organization, fall back to env vars: `LAMB_KB_SERVER_V2`, `LAMB_KB_SERVER_V2_TOKEN` (matching the `LAMB_LIBRARY_SERVER` / `LAMB_LIBRARY_TOKEN` precedent — env-var name is internal-only, the user-facing name is "Knowledge Store").

**Embedding API key resolution (D4):** `OrganizationConfigResolver.get_knowledge_store_config()` returns the KS server config. A separate helper `get_provider_api_key(vendor: str)` returns the embedding key from `setups.default.providers.{vendor}.api_key`. The router/client composes them per call.

---

## 6. Access Control

Mirror `can_access_library` exactly (file: `backend/lamb/auth_context.py`).

```
Owner                           → 'owner'
System admin                    → 'owner'
Org admin (same org)            → 'owner'
is_shared=1 + same org          → 'shared'
otherwise                       → 'none'
```

| Action | Owner | Shared | Org Admin |
|--------|-------|--------|-----------|
| See KS + content links | ✓ | ✓ | ✓ |
| Add content from library | ✓ | ✓ | ✓ |
| Query | ✓ | ✓ | ✓ |
| Remove content | ✓ | – | ✓ |
| Delete KS | ✓ | – | ✓ |
| Toggle share | ✓ | – | – |
| Update name/description | ✓ | – | ✓ |

New helpers in `backend/lamb/auth_context.py`:

- `can_access_knowledge_store(ks_id) -> 'owner' | 'shared' | 'none'`
- `require_knowledge_store_access(ks_id, level: 'any' | 'owner') -> str`

These exist alongside the existing `can_access_kb` / `require_kb_access` (which keep serving stable KBs). No changes to the existing helpers.

---

## 7. Creator Interface Endpoints

New router `backend/creator_interface/knowledge_store_router.py` mounted at `/creator/knowledge-stores`. Standard pattern per endpoint: `auth → ACL → org config → client call → DB update → audit → response`.

**Static-before-parameterized rule** (ADR-10 of #336): `/options`, `/import`, etc. registered before `/{ks_id}` so FastAPI doesn't match literal segments as the id parameter.

| Endpoint | Purpose |
|----------|---------|
| `GET /creator/knowledge-stores/options` | Return the org's allowed vector-DB backends, chunking strategies, embedding vendors, and embedding models so the UI can render a create form. |
| `POST /creator/knowledge-stores` | Generate UUID, validate selections against allow-list, create LAMB row as `provisional`, call KB Server `POST /collections`, promote to `active`. Audit `knowledge_store.create`. |
| `GET /creator/knowledge-stores` | List owned + shared KSes for the user's org. Enrich with content-link counts from `kb_content_links`. |
| `GET /creator/knowledge-stores/{ks_id}` | Detail view: LAMB row + KB Server collection metadata + linked items grouped by library. |
| `PUT /creator/knowledge-stores/{ks_id}` | Update name/description (the only mutable fields per ADR-3). |
| `DELETE /creator/knowledge-stores/{ks_id}` | Owner/admin only. Call KB Server `DELETE /collections/{id}` first; on success, cascade-delete LAMB row (which cascades `kb_content_links`). 404 from KB Server tolerated (Marc's correction in #336 review). Audit. |
| `PUT /creator/knowledge-stores/{ks_id}/share` | Toggle `is_shared`. Audit. |
| `POST /creator/knowledge-stores/{ks_id}/content` | **The core ingestion endpoint.** Body: `{ library_id, item_ids: [...] }`. For each item: check library ACL, fetch item metadata from Library Manager, build the `add-content` payload (text from Library Manager's content endpoint, permalinks pointing at LAMB `/docs`, source_item_id, title, pages if available), resolve the org's embedding key, call KB Server `POST /collections/{id}/add-content`, get back `job_id`, insert `kb_content_links` rows with status `'processing'`. Audit `knowledge_store.add_content`. Returns `{ job_id, links: [...] }`. |
| `GET /creator/knowledge-stores/{ks_id}/content` | List linked items (LAMB-side join across libraries + items + links). |
| `GET /creator/knowledge-stores/{ks_id}/content/{library_item_id}` | Get a single content link's status. Polls KB Server's `GET /jobs/{job_id}` if still processing, syncs status back into `kb_content_links`. |
| `DELETE /creator/knowledge-stores/{ks_id}/content/{library_item_id}` | Owner/admin. Call KB Server `DELETE /collections/{id}/content/{source_item_id}`, delete `kb_content_links` row. Audit `knowledge_store.remove_content`. |
| `POST /creator/knowledge-stores/{ks_id}/query` | Forward query text to KB Server `POST /collections/{id}/query` with the resolved embedding key, return chunks (each carrying permalink metadata). Used by the assistant builder's "test query" feature. |
| `GET /creator/knowledge-stores/{ks_id}/jobs/{job_id}` | Proxy for KB Server `GET /jobs/{job_id}`. Updates affected `kb_content_links` rows on the way through. |

**FR-10 enforcement** lives in the existing `DELETE /creator/libraries/{id}/items/{item_id}` (router file `library_router.py`). Add a check: before forwarding the delete to the Library Manager, query `kb_content_links WHERE library_item_id = ? AND status != 'failed'`. If any rows exist, return **409 Conflict** with the list of referencing Knowledge Stores. This is the only modification to existing code outside of `database_manager.py`/`auth_context.py`.

---

## 8. Files to Create / Modify in LAMB Backend

### Modify (minimal, additive)

| File | Changes |
|------|---------|
| `backend/lamb/database_manager.py` | Add `knowledge_stores` and `kb_content_links` tables (next migration). Add CRUD: `create_knowledge_store`, `get_knowledge_store`, `get_accessible_knowledge_stores`, `update_knowledge_store_status`, `update_knowledge_store`, `toggle_knowledge_store_sharing`, `delete_knowledge_store`, `register_kb_content_link`, `update_kb_content_link_status`, `delete_kb_content_link`, `get_kb_content_links_for_item`, `user_can_access_knowledge_store`. |
| `backend/lamb/auth_context.py` | Add `can_access_knowledge_store`, `require_knowledge_store_access`. Same shape as `can_access_library`. |
| `backend/lamb/completions/org_config_resolver.py` | Add `get_knowledge_store_config()` and `get_provider_api_key(vendor)`. Existing `get_knowledge_base_config()` stays untouched. |
| `backend/creator_interface/library_router.py` | In `DELETE /creator/libraries/{id}/items/{item_id}`: pre-check `kb_content_links` and return 409 if any active link exists (FR-10). |
| `backend/creator_interface/main.py` | Mount the new `knowledge_store_router`. |

### Create

| File | Purpose |
|------|---------|
| `backend/creator_interface/knowledge_store_client.py` | HTTP client for the new KB Server. Per-call `httpx.AsyncClient` (Library Manager pattern, ADR-9 of #336). Methods: `create_collection`, `delete_collection`, `update_collection`, `get_collection`, `add_content`, `delete_content_by_source`, `query`, `get_job_status`, `get_backends`, `get_chunking_strategies`, `get_embedding_vendors`. Org-aware via `OrganizationConfigResolver`. |
| `backend/creator_interface/knowledge_store_router.py` | All `/creator/knowledge-stores/...` endpoints. |
| `backend/lamb/completions/rag/knowledge_store_rag.py` | New RAG processor entry. Reads `assistant.RAG_collections` (which for these assistants holds Knowledge Store IDs), calls KB Server `POST /collections/{id}/query` per id, merges results by score, returns context with citation metadata that downstream PPS plugins render as permalink markdown. **Sibling** of existing `simple_rag.py`; existing processors untouched. Registered in the plugin loader so assistant-builders can pick it. |

The choice of which RAG processor to use is per-assistant (existing `assistant.rag_processor` field). Stable assistants keep `simple_rag`; new Knowledge-Store-backed assistants pick `knowledge_store_rag`. No conditional version-tag logic anywhere.

---

## 9. lamb-cli

Create `lamb-cli/src/lamb_cli/commands/knowledge_store.py`. The **primary command is `lamb ks`** (short, fast to type) with `lamb knowledge-store` registered as an alias for the long form. This matches the convention where `kb` is short for the stable Knowledge Bases — `ks` reads naturally as the short form for Knowledge Stores and reinforces the distinction.

| Command | Endpoint |
|---------|----------|
| `lamb ks options` | GET `/creator/knowledge-stores/options` |
| `lamb ks create <name> --chunking <s> --embedding-vendor <v> --embedding-model <m> --vector-db <b> [--description ...]` | POST `/creator/knowledge-stores` |
| `lamb ks list` | GET `/creator/knowledge-stores` |
| `lamb ks get <ks_id>` | GET `/creator/knowledge-stores/{ks_id}` |
| `lamb ks update <ks_id> [--name ...] [--description ...]` | PUT `/creator/knowledge-stores/{ks_id}` |
| `lamb ks delete <ks_id>` | DELETE `/creator/knowledge-stores/{ks_id}` |
| `lamb ks share <ks_id> [--enable\|--disable]` | PUT `/creator/knowledge-stores/{ks_id}/share` |
| `lamb ks add-content <ks_id> --library <lib_id> --items <id1,id2,...>` | POST `/creator/knowledge-stores/{ks_id}/content` |
| `lamb ks list-content <ks_id>` | GET `/creator/knowledge-stores/{ks_id}/content` |
| `lamb ks remove-content <ks_id> <library_item_id>` | DELETE `/creator/knowledge-stores/{ks_id}/content/{library_item_id}` |
| `lamb ks status <ks_id> [--item <library_item_id>] [--wait]` | Polls content link or job status. `--wait` blocks until ready/failed. |
| `lamb ks query <ks_id> "query text" [--top-k 5]` | POST `/creator/knowledge-stores/{ks_id}/query` |

`lamb knowledge-store …` resolves to the same handlers (alias). Existing `lamb kb …` commands (stable KB Server) are not modified.

---

## 10. Frontend (Svelte)

### 10.1 Top-level navigation

The current navigation has two relevant tabs/entries: **"KB Server"** (stable, hits `/knowledgebases`) and **"Library Manager"** (hits `/libraries`). The change:

- **"KB Server" stays as-is** — same label, same route, same behavior. It remains the entry point for the stable Knowledge Bases. Do not touch.
- **The "Library Manager" tab is restructured.** It is renamed to **"Knowledge"** (or equivalent — see §10.2 naming note) and becomes the entry point for the new unified flow. It exposes both Library management *and* Knowledge Store creation through a guided wizard, because in practice every Knowledge Store needs a Library first (D3, library-only ingestion).

So after this change:

| Nav entry | Route | What it owns |
|-----------|-------|--------------|
| KB Server (unchanged) | `/knowledgebases` | Stable KBs only |
| Knowledge (renamed from "Library Manager") | `/knowledge` (or kept at `/libraries` — see §10.2) | Libraries + Knowledge Stores via wizard |

### 10.2 Naming the renamed tab

The user-facing tab label needs to convey "this is where you turn documents into something an assistant can search". Pick at implementation time, but the recommendation is **"Knowledge"** (singular, generic) with a sub-grouping inside the page for "Libraries" and "Knowledge Stores". The route can stay at `/libraries` to avoid breaking existing bookmarks, or move to `/knowledge` — both work, decided at implementation time. The internal Library Manager service name does NOT change.

### 10.3 The unified wizard — primary creation entry point

Replaces the previous "open the Library Manager tab and figure it out" flow. From the renamed tab, the user clicks **"Create Knowledge"** (single primary action) and is walked through a multi-step wizard. Each step is its own Svelte component; navigation is forward/back with progress indicator; the wizard can be exited at any point and resumed via list view.

**Default wizard steps:**

| # | Step | Purpose | Backend calls |
|---|------|---------|---------------|
| 0 | **Library: choose path** | Radio: "Use an existing Library" vs "Create a new Library". If "existing" is picked, a dropdown appears in the same step listing all libraries the user can access (owned + shared, fetched from `GET /creator/libraries`). User picks one and clicks Next; the wizard then **jumps directly to Step 4** (Knowledge Store path chooser), skipping Steps 1, 2, and 3. If "new" is picked, the wizard proceeds to Step 1. | `GET /creator/libraries` (when "existing" picked) |
| 1 | **Library: name & details** | Name (required), description (optional), shared toggle (default: off). | none yet |
| 2 | **Library: import config** | Plugin allow-list display, default plugin choice, per-plugin parameter inputs (image-descriptions toggle, crawl-depth, etc., gated by what the org allows). Driven by `GET /creator/libraries/plugins`. **Pre-filled with sensible defaults** so the user can click Next without changing anything. | `POST /creator/libraries` (creates the Library and persists this config) |
| 3 | **Library: add initial content** *(optional)* | Upload one or more files / paste a URL / add YouTube. Skippable — the user can come back later and add more. Polls item status until ready before allowing "Next". | `POST /creator/libraries/{id}/upload`, `import-url`, `import-youtube`, `GET /items/{id}/status` |
| 4 | **Knowledge Store: choose path** | Radio: "Use an existing Knowledge Store" vs "Create a new Knowledge Store". If "existing" is picked, a dropdown appears in the same step listing the user's accessible KSes (owned + shared, fetched from `GET /creator/knowledge-stores`, optionally filtered to those whose embedding vendor matches what's reasonable for the chosen library — but in v1 just list all). User picks one and clicks Next; the wizard **jumps directly to Step 7** (pick items), skipping Steps 5 and 6. If "new" is picked, the wizard proceeds to Step 5. | `GET /creator/knowledge-stores` (when "existing" picked) |
| 5 | **Knowledge Store: name & details** | Name (required), description (optional), shared toggle (default: off). | none yet |
| 6 | **Knowledge Store: config** | Driven by `GET /creator/knowledge-stores/options`: chunking strategy, vector DB, embedding vendor, embedding model — each rendered as a radio or dropdown filtered by the org's allow-list. **Every field has a default pre-selected** (the org's first allowed option for each, or the org's recommended default if exposed by `/options`). User can click Next without touching anything. The selection is **immutable after creation** (D5/ADR-KS-5) — show a clear "these settings cannot be changed later" notice with an "expand to customize" affordance for users who want to drill in. | none yet |
| 7 | **Pick items to ingest** | Multi-select picker over the chosen library's items (those already imported in Step 3 + any pre-existing if an existing library was chosen). All items pre-selected by default. Skippable to create/use an empty/unchanged KS. | `GET /creator/libraries/{id}/items` |
| 8 | **Review & create** | Summary card showing: chosen library (name + item count), chosen or new KS (name + locked config), the items being ingested. "Create / Ingest" button kicks off the needed actions: create library if new, create KS if new, then post add-content. | `POST /creator/knowledge-stores` (only if new KS), then `POST /creator/knowledge-stores/{id}/content`. Then poll `/content/{library_item_id}` until each is ready or failed. |
| 9 | **Done** | Success summary with quick links: "Open Knowledge Store", "Open Library", "Create another". | none |

**Skip rules:**
- Existing-Library at Step 0 → skip Steps 1, 2, 3 → land on Step 4.
- New-Library at Step 0 → run Steps 1, 2, optionally 3 → land on Step 4.
- Existing-KS at Step 4 → skip Steps 5 and 6 → land on Step 7.
- New-KS at Step 4 → run Steps 5 and 6 → land on Step 7.
- Step 3 and Step 7 are individually skippable.

The wizard is implemented as a single Svelte page with a `currentStep` reactive variable and per-step components, not separate routes — this keeps the back/forward navigation in-page and avoids URL juggling. The "back" button respects skipped steps: from Step 4, "back" returns to Step 0 (not Step 3) if the user came in via the existing-library path; from Step 7, "back" returns to Step 4 if the user picked an existing KS.

**Defaults-everywhere principle:** every step's form fields must come pre-populated with sensible defaults so a user who clicks Next on every step ends up with a working Library + Knowledge Store + first ingestion. The only required typed input on the happy path is the Library name (Step 1) and the Knowledge Store name (Step 5) — and even those can be auto-suggested ("My Library 2026-05-02", "My Knowledge Store 2026-05-02") with the user free to edit. Every dropdown/radio: first allowed option pre-selected. Every toggle: opinionated default (sharing off, image-descriptions off, all items pre-selected). Customization is one click away ("Edit defaults" / "Expand options") but never required.

The list view of the renamed tab should show **both** existing Libraries and existing Knowledge Stores, side by side or in two collapsible sections, with their own quick-actions. The wizard is the primary creation path; standalone "create just a Library" and "create just a Knowledge Store from existing library" entry points remain accessible from the list view for power users.

### 10.4 Files to create / modify

| File | Action | Purpose |
|------|--------|---------|
| `frontend/svelte-app/src/routes/libraries/+page.svelte` (or `/knowledge` if renamed) | Modify | Add the wizard launcher + Knowledge Stores list section. Existing Library list functionality preserved. |
| `frontend/svelte-app/src/lib/services/knowledgeStoreService.js` | Create | Axios API client mirroring `libraryService.js`. |
| `frontend/svelte-app/src/lib/components/knowledge/CreateKnowledgeWizard.svelte` | Create | Top-level wizard shell: step state, progress indicator, forward/back, abort/resume. |
| `frontend/svelte-app/src/lib/components/knowledge/wizard/Step0_LibraryPath.svelte` | Create | "Existing or new Library" picker with dropdown of accessible libraries when "existing" chosen. |
| `frontend/svelte-app/src/lib/components/knowledge/wizard/Step1_LibraryDetails.svelte` | Create | Library name + description form. Auto-suggested name. |
| `frontend/svelte-app/src/lib/components/knowledge/wizard/Step2_LibraryConfig.svelte` | Create | Library import config with sensible defaults pre-filled; expandable for customization. |
| `frontend/svelte-app/src/lib/components/knowledge/wizard/Step3_LibraryContent.svelte` | Create | Upload/URL/YouTube + status polling. Skippable. |
| `frontend/svelte-app/src/lib/components/knowledge/wizard/Step4_KSPath.svelte` | Create | "Existing or new Knowledge Store" picker with dropdown of accessible KSes when "existing" chosen. |
| `frontend/svelte-app/src/lib/components/knowledge/wizard/Step5_KSDetails.svelte` | Create | Knowledge Store name + share toggle. Auto-suggested name. |
| `frontend/svelte-app/src/lib/components/knowledge/wizard/Step6_KSConfig.svelte` | Create | Chunking + embedding + vector DB selection driven by `/options`, defaults pre-selected, "immutable after creation" notice, "Edit defaults" affordance. |
| `frontend/svelte-app/src/lib/components/knowledge/wizard/Step7_PickItems.svelte` | Create | Library item multi-select for ingestion, all items pre-selected. Skippable. |
| `frontend/svelte-app/src/lib/components/knowledge/wizard/Step8_ReviewCreate.svelte` | Create | Summary + execute (creates library/KS only if "new" was picked, then ingests). |
| `frontend/svelte-app/src/lib/components/knowledge/wizard/Step9_Done.svelte` | Create | Success view with quick links. |
| `frontend/svelte-app/src/lib/components/knowledgeStores/KnowledgeStoresList.svelte` | Create | Standalone KS list (used by the renamed tab + by the wizard's "existing KS" picker). |
| `frontend/svelte-app/src/lib/components/knowledgeStores/KnowledgeStoreDetail.svelte` | Create | Locked-config display, linked-content list with per-item status badges, "add more content" launcher, query test box, share toggle, delete. Uses `$effect(() => loadData())` (Marc's #336 finding). |
| `frontend/svelte-app/src/lib/components/knowledgeStores/AddContentToKSModal.svelte` | Create | Used from the KS detail page when adding more items after the wizard. Library + multi-select item picker. Polls `/content/{library_item_id}` until ready/failed. |
| `frontend/svelte-app/src/lib/components/knowledgeStores/ConfirmDeleteKnowledgeStoreModal.svelte` | Create | Reuses existing confirmation modal pattern. |

The standalone `CreateKnowledgeStoreModal.svelte` from the previous draft is not needed — the wizard subsumes it, and the existing-KS-via-dropdown path inside the wizard handles the "I already have a KS, just ingest more" use case without ever creating a new resource.

### 10.5 i18n

Add `knowledge.*` and `knowledgeStores.*` keys to all four locales (`en.json`, `es.json`, `ca.json`, `eu.json`) on first commit (Marc's #336 critical issue #2 — never ship UI text only in en). Mirror the `libraries.*` key shape, plus wizard-specific keys: `wizard.step{0..9}.title`, `wizard.step{0..9}.description`, `wizard.next`, `wizard.back`, `wizard.skip`, `wizard.create`, `wizard.useExisting`, `wizard.createNew`, `wizard.lockedConfigNotice`, `wizard.editDefaults`, plus modal validation messages. If the tab is renamed to "Knowledge", add a `nav.knowledge` key replacing `nav.libraryManager` (or keep both during the transition).

### 10.6 A11y

Wizard must support keyboard-only operation: Tab cycles through fields, Enter advances to the next step, Esc prompts to abort. Progress indicator must be announced (`aria-live="polite"`). Each step's heading is `<h2>` for screen readers. Same autofocus / focus trap / focus restore rules from #336 apply to every modal opened from any step.

### 10.7 Citation rendering in chat

The chat UI's RAG citation renderer (existing, added during #336) already supports permalink metadata. Verify it renders chunks coming from `knowledge_store_rag` — they carry `permalink_original`, `permalink_markdown`, `permalink_page` via the same metadata shape Library Manager produces. Add nothing new unless a gap is found.

### 10.8 What stays untouched

`/knowledgebases/+page.svelte`, `KnowledgeBasesList.svelte`, `KnowledgeBaseDetail.svelte`, `knowledgeBaseService.js`, the "KB Server" nav entry — all unchanged.

---

## 11. Docker Compose

Add a new service `kb-server` (the new one) to `docker-compose-example.yaml`, alongside the existing `kb` service (stable, unchanged). Use the same image/volume pattern as `library-manager`:

```yaml
kb-server:
  image: python:3.11-slim
  working_dir: ${LAMB_PROJECT_PATH}/lamb-kb-server/backend
  environment:
    - LAMB_API_TOKEN=${KB_SERVER_V2_TOKEN:-change-me}    # rotate in production — see Marc #336
    - DATA_DIR=${LAMB_PROJECT_PATH}/lamb-kb-server/data
    - GLOBAL_LOG_LEVEL=WARNING
    - KB_LOG_LEVEL=WARNING
  volumes:
    - ${LAMB_PROJECT_PATH}:${LAMB_PROJECT_PATH}
    - pip-cache:/root/.cache/pip
  ports:
    - "127.0.0.1:9092:9092"
  healthcheck:
    test: ["CMD", "curl", "-sf", "http://localhost:9092/health"]
    interval: 30s
    timeout: 5s
    retries: 3
  command: >
    sh -lc "apt-get update -qq && apt-get install -y -qq curl > /dev/null 2>&1 && \
    pip install -e '${LAMB_PROJECT_PATH}/lamb-kb-server[all]' && \
    uvicorn main:app --host 0.0.0.0 --port 9092 --reload --log-level $${LOG_LEVEL:-warning} --no-access-log"
```

Backend service receives:
```yaml
- LAMB_KB_SERVER_V2=http://kb-server:9092
- LAMB_KB_SERVER_V2_TOKEN=${KB_SERVER_V2_TOKEN:-change-me}
```

Backend `depends_on` adds `kb-server: condition: service_started`. Existing `kb`, `library-manager`, and other dependencies are unchanged. Inline comment in the compose example reminds operators to rotate `KB_SERVER_V2_TOKEN` (Marc #336 deferred item #10 — fix here pre-emptively).

---

## 12. Phases & Implementation Order

The plan extends #336's order with a dedicated end-to-end verification phase covering the full library→KS pipeline.

### Phase 1A — LAMB backend Knowledge-Store integration
- DB tables + CRUD
- `auth_context` helpers
- `org_config_resolver` additions
- `knowledge_store_client.py`
- `knowledge_store_router.py`
- `library_router.py` FR-10 guard
- Mount router in `main.py`
- Docker Compose `kb-server` service

### Phase 1B — RAG processor + assistant integration
- `knowledge_store_rag.py` plugin file
- Register in plugin loader
- Verify assistant builder UI can already select `rag_processor='knowledge_store_rag'` (existing dropdown reads from registered plugins — no UI change needed if so; otherwise add to the dropdown source)

### Phase 1C — lamb-cli
- `knowledge_store.py` command file with all commands above
- Wire into top-level CLI registry (alias `ks`)

### Phase 1D — Backend Playwright API verification
- New spec `testing/playwright/tests/knowledge_store_api.spec.js`
- API-only, mirrors `library_api.spec.js` structure (test.describe.serial, beforeAll auth, apiCall helper, polling, afterAll cleanup)
- Coverage: create KS, list, detail, share/unshare, update, query options, delete; FR-10 (try to delete linked library item → expect 409)

### Phase 2A — Svelte frontend
- `knowledgeStoreService.js`
- Route + components + modals listed in §10
- i18n keys in all four locales **on first commit**
- A11y: role="alert", autofocus, focus trap, focus restore (Marc #336 issues #11, #12)
- Reactive reload via `$effect` (Marc #336 issue #3)

### Phase 2B — Frontend Playwright UI tests
- New spec `testing/playwright/tests/knowledge_store_ui.spec.js` (UI navigation, modal interactions, list/detail, create/delete flow)
- Existing `kb_detail_modals.spec.js` and `kb_delete_modal.spec.js` are not touched

### Phase 3 — End-to-end Library → Knowledge Store → Query verification (the new phase #336 did not have)
This is the phase that proves the full chain works. New spec `testing/playwright/tests/knowledge_store_e2e_workflow.spec.js`:

1. Login.
2. Create a new Library via `POST /creator/libraries`.
3. Upload a markdown fixture (`testing/playwright/fixtures/sample.md`) via `POST /creator/libraries/{lib}/upload`.
4. Poll `GET /creator/libraries/{lib}/items/{item}/status` until `'ready'` (reuse #336 polling helper).
5. Fetch `GET /creator/knowledge-stores/options` to discover allowed strategies.
6. Create a Knowledge Store with `simple` chunking + the test embedding vendor (use a mock-friendly vendor — `local` if enabled in test env, or a stub OpenAI key).
7. Call `POST /creator/knowledge-stores/{ks}/content` linking the library item.
8. Poll `GET /creator/knowledge-stores/{ks}/content/{library_item_id}` until `'ready'` or `'failed'` with a generous timeout (Marc #336 deferred item #19 — use exponential backoff up to 60 s, not the flaky 15 s hard budget).
9. Call `POST /creator/knowledge-stores/{ks}/query` with a string known to be in the fixture; assert at least one chunk returns and the chunk metadata includes a permalink that starts with `/docs/{org}/{lib}/{item}/`.
10. Issue `GET` against that permalink with the user's bearer token; expect 200 and content matching the fixture (proves the LAMB ACL proxy still works for KS-cited content).
11. Try `DELETE /creator/libraries/{lib}/items/{item}`; expect 409 with the KS in the conflict body (proves FR-10).
12. `DELETE /creator/knowledge-stores/{ks}/content/{library_item_id}`; expect 200.
13. Re-try the library-item delete; expect 200 (FR-10 releases the lock).
14. Cleanup in `afterAll`: delete library, delete KS (idempotent, swallow 404).

The spec runs in parallel-safe isolation (its own org/user fixture) so it does not race the existing library_api.spec.js or kb tests.

### Phase 4 — Documentation & ADRs
- Update `CLAUDE.md` with a section on Knowledge Stores (the LAMB-side surface), making the terminology distinction explicit:
  - **Libraries** import → store markdown
  - **Knowledge Bases** (legacy, stable KB Server, `/knowledgebases`) ingest files directly
  - **Knowledge Stores** (new KB Server, `/knowledge-stores`) ingest *from libraries only*
- Add ADRs to `lamb-kb-server/Documentation/` capturing decisions D1–D8.

---

## 13. ADRs

### ADR-KS-1 — Parallel surfaces, not version flag
Knowledge Stores live on a separate router, separate tables, separate client, separate RAG processor, separate frontend route. The stable `kb_registry` / `/creator/knowledgebases` / `kb_server_manager.py` / `simple_rag.py` surfaces are not modified. This trades a small amount of code duplication for zero regression risk on the live KB path and clean per-feature deprecation later.

### ADR-KS-2 — LAMB owns metadata + ACL; KB Server owns vectors
Same split as #336's ADR-1. `knowledge_stores` is the source of truth for ownership, sharing, and the locked store setup. The KB Server is the source of truth for chunks and embeddings. `kb_content_links` is the bridge.

### ADR-KS-3 — Library-only content path
Knowledge Stores cannot be populated by direct file upload. The only ingestion path is "link library items". This makes every chunk citable via a real ACL-enforced permalink and matches the new KB Server's JSON-only `/add-content` contract.

### ADR-KS-4 — Embedding key reuses existing org provider key
LAMB resolves the embedding API key from `setups.default.providers.{vendor}.api_key` and sends it per-request. The KB Server holds it in memory only. No duplicate config; no per-KS key required for the common case.

### ADR-KS-5 — Locked store setup
Chunking strategy, chunking params, embedding vendor, embedding model, embedding endpoint, and vector DB backend are immutable after creation (KB Server ADR-3). Only `name` and `description` are mutable.

### ADR-KS-6 — Permalinks on chunks point at LAMB, not Library Manager
Permalink URLs sent into the KB Server's `add-content` payload are constructed against LAMB's own `/docs/{org}/{lib}/{item}/...` proxy. Citations resolve via LAMB ACL; users never reach the Library Manager directly.

### ADR-KS-7 — FR-10 enforced in LAMB at library-item delete
Library Manager has no awareness of Knowledge Stores. The check that "this library item is referenced by a KS" lives in LAMB's `/creator/libraries/{lib}/items/{item}` DELETE handler, indexed lookup against `kb_content_links`. Returns 409 on conflict with the list of referencing Knowledge Stores so the UI can render an actionable message.

### ADR-KS-8 — Delete LAMB row last, tolerate 404 from KB Server
For Knowledge Store deletion: call KB Server `DELETE /collections/{id}` first; on 2xx or 404, delete LAMB row + cascade `kb_content_links`; on other 5xx, return 502 and leave LAMB row intact. This is the order Marc explicitly fixed in #336 critical issue #1 — do it right from the start.

### ADR-KS-9 — Provisional create
Inserting into `knowledge_stores` happens before the KB Server call, with `status='provisional'`. Promoted to `'active'` on KB Server success. On failure, the LAMB row is deleted. List endpoints filter `status='active'` so partial-failure rows never appear in the UI.

### ADR-KS-10 — Per-call httpx clients
The Knowledge Store client follows `LibraryManagerClient` and `kb_server_manager.py` patterns: `async with httpx.AsyncClient(timeout=...) as client` per call. Connection pooling is a future optimization.

### ADR-KS-11 — Static routes before parameterized
`/options` and any future `/import` are mounted before `/{ks_id}` (FastAPI routing requirement, copied from #336 ADR-10).

### ADR-KS-12 — Sibling RAG processor, no branching in existing
A new `knowledge_store_rag.py` is added next to `simple_rag.py`. Existing processors are not edited. Assistants that should retrieve from a Knowledge Store have `rag_processor='knowledge_store_rag'` set in their config; everything else keeps using `simple_rag` against stable KBs.

---

## 14. Critical files to modify (summary table)

| File | What |
|------|------|
| `backend/lamb/database_manager.py` | New tables + CRUD methods |
| `backend/lamb/auth_context.py` | `can_access_knowledge_store`, `require_knowledge_store_access` |
| `backend/lamb/completions/org_config_resolver.py` | `get_knowledge_store_config`, `get_provider_api_key` |
| `backend/creator_interface/library_router.py` | FR-10 409 guard in `DELETE …/items/{id}` |
| `backend/creator_interface/main.py` | Mount `knowledge_store_router` |
| `docker-compose-example.yaml` | New `kb-server` service block + backend env vars + `depends_on` |
| `CLAUDE.md` | Terminology section: Libraries vs Knowledge Bases vs Knowledge Stores |

## 15. Critical files to create (summary table)

| File | Purpose |
|------|---------|
| `backend/creator_interface/knowledge_store_client.py` | HTTP client for the new KB Server |
| `backend/creator_interface/knowledge_store_router.py` | `/creator/knowledge-stores/...` |
| `backend/lamb/completions/rag/knowledge_store_rag.py` | RAG processor for KS-backed assistants |
| `lamb-cli/src/lamb_cli/commands/knowledge_store.py` | CLI commands |
| `frontend/svelte-app/src/lib/services/knowledgeStoreService.js` | Axios client |
| `frontend/svelte-app/src/routes/knowledge-stores/+page.svelte` | Top-level page |
| `frontend/svelte-app/src/lib/components/knowledgeStores/*.svelte` | List, detail, modals |
| `testing/playwright/tests/knowledge_store_api.spec.js` | API E2E |
| `testing/playwright/tests/knowledge_store_ui.spec.js` | UI E2E |
| `testing/playwright/tests/knowledge_store_e2e_workflow.spec.js` | Full library→KS→query workflow |
| `testing/playwright/fixtures/sample.md` | Reusable markdown fixture for the workflow test |

---

## 16. Existing functions to reuse (not rewrite)

| Function | File | Why reuse |
|----------|------|-----------|
| `LibraryManagerClient.get_item`, `.proxy_content` | `backend/creator_interface/library_manager_client.py` | Fetch markdown + metadata from Library Manager during ingestion. |
| `LibraryManagerClient`'s per-call `httpx.AsyncClient` lifecycle | same | Copy the exact pattern in `KnowledgeStoreClient`. |
| `OrganizationConfigResolver` | `backend/lamb/completions/org_config_resolver.py` | Add new method, reuse the existing org-config + env-fallback pattern. |
| `database_manager.write_audit_log` | `backend/lamb/database_manager.py` | All KS audit entries go through this. |
| The `_audit(auth, action, target_type, target_id, details)` helper from `library_router.py` | `backend/creator_interface/library_router.py` | Lift into a small shared helper module if we want to dedupe; otherwise copy the 10-line wrapper into the new router. |
| The provisional-status pattern from `library_router.py:124-160` | same | Replicate verbatim for KS create. |
| The permalink proxy at `/docs/{org}/{lib}/{item}/...` | `backend/creator_interface/library_router.py` | KS does not need its own proxy — citations point at the existing one. |
| `apiCall` helper + serial polling pattern from `library_api.spec.js` | `testing/playwright/tests/library_api.spec.js` | Copy into the three new specs. Use exponential backoff (Marc #336 #19) instead of fixed 15 s. |
| Existing chat-side citation renderer | `frontend/svelte-app/src/lib/components/chat/...` | Permalink metadata shape from KS query results matches what the renderer already expects. |

---

## 17. Verification (end-to-end, copy-paste runnable)

After implementation, the following must all pass cleanly:

```bash
# Backend health
docker compose up -d backend kb-server library-manager kb
curl -sf http://localhost:9099/health
curl -sf http://localhost:9092/health
curl -sf http://localhost:9091/health
curl -sf http://localhost:9090/health   # stable KB unchanged

# CLI workflow (proves Phases 1A–1C end-to-end)
LIB=$(lamb library create "ks-test-lib" --json | jq -r '.id')
ITEM=$(lamb library upload $LIB testing/playwright/fixtures/sample.md --json | jq -r '.item_id')
lamb library item $LIB $ITEM --wait                                # status='ready'
KS=$(lamb knowledge-store create "ks-test" \
       --chunking simple \
       --embedding-vendor openai \
       --embedding-model text-embedding-3-small \
       --vector-db chromadb --json | jq -r '.id')
lamb knowledge-store add-content $KS --library $LIB --items $ITEM
lamb knowledge-store status $KS --item $ITEM --wait               # status='ready'
lamb knowledge-store query $KS "what does sample say about X"     # returns chunks + permalinks
lamb library delete-item $LIB $ITEM                               # expect 409 — FR-10
lamb knowledge-store remove-content $KS $ITEM
lamb library delete-item $LIB $ITEM                               # now succeeds
lamb knowledge-store delete $KS
lamb library delete $LIB

# Stable KB regression check (must still work, untouched code path)
lamb kb list
lamb kb create "stable-regress-test"
# … existing stable flow continues to function unchanged.

# Playwright
cd testing/playwright
npx playwright test tests/library_api.spec.js              # existing — must still pass
npx playwright test tests/kb_detail_modals.spec.js         # existing stable — must still pass
npx playwright test tests/kb_delete_modal.spec.js          # existing stable — must still pass
npx playwright test tests/knowledge_store_api.spec.js      # new
npx playwright test tests/knowledge_store_ui.spec.js       # new
npx playwright test tests/knowledge_store_e2e_workflow.spec.js  # the headline new test
```

The plan succeeds when:
1. All four health endpoints return 200.
2. The full CLI script above runs to completion with the expected 409 on the FR-10 step.
3. All existing Playwright specs still pass without modification.
4. The three new Playwright specs pass, including the end-to-end workflow that exercises Library → markdown → Knowledge Store → chunked → queried → cited → permalink-resolved.

---

## 18. Out of scope for this issue

- Migrating existing `kb_registry` rows to `knowledge_stores` (per #334 non-goals).
- Rewriting existing RAG processors to fan out across both server types.
- Cross-org Knowledge Store sharing.
- Knowledge Store re-ingestion / freshness sync when a library item changes (NFR-8 in #334 — KS is a snapshot at ingestion time).
- Internal TLS between LAMB and the new KB Server (deferred per #336's Phase 3).
- UI for assistant-builder picking `knowledge_store_rag` if the dropdown source needs work — that is its own follow-up.
- Marc's deferred items from #336 (rate limiting, hard-cancel timeout fix, etc.) — track separately.

---

## 19. Verification Orchestration

Verification of this plan's implementation is performed by **Opus subagents launched in parallel** by Claude Code. Claude Code is the orchestrator: it reviews each subagent's findings, cross-checks against §4–§16, runs the deterministic test commands itself (Library Manager pytest, KB Server v2 pytest, stable KB pytest, frontend `npm run check`/`lint`/`test:unit`, the §17 CLI smoke script, and all Playwright specs new + existing), and is solely responsible for the final pass/fail verdict.

Two passes are run:

**Static-review pass — four Opus subagents in parallel:**

| Subagent | Scope | Verifies |
|----------|-------|----------|
| **A1 — Backend code review** | `database_manager.py` (migration 17 + 12 CRUD methods), `auth_context.py`, `org_config_resolver.py`, `knowledge_store_client.py`, `knowledge_store_router.py`, `library_router.py` FR-10 guard, `main.py` mount, `knowledge_store_rag.py` | Logic bugs, race conditions, ADR-KS-1…KS-12 compliance (esp. KS-8 delete order, KS-9 provisional rollback, KS-11 static-before-param), audit-log on every mutation, error-handling parity with the Library Manager router |
| **A2 — Frontend code review** | unified `/libraries` page, all 10 wizard steps, KS list/detail/modals, `knowledgeStoreService.js`, all four locale JSONs | Skip-rule correctness across all 4 wizard paths, defaults pre-selection, `$effect` reactive reload (not `onMount`), locale-key parity (en vs es/ca/eu), service URLs match router endpoints exactly |
| **A3 — CLI + cross-cutting consistency** | `lamb-cli/.../knowledge_store.py`, `lamb-cli/.../main.py`, every `/creator/knowledge-stores/*` endpoint | Every router endpoint has a CLI command and vice versa; arg names match request bodies; `lamb ks` and `lamb knowledge-store` both register; existing `lamb kb` untouched |
| **A4 — Test coverage review** | `knowledge_store_api.spec.js`, `knowledge_store_ui.spec.js`, `knowledge_store_e2e_workflow.spec.js`, `fixtures/sample.md`; regression check on `library_api.spec.js`, `kb_detail_modals.spec.js`, `kb_delete_modal.spec.js` | E2E covers all 14 steps from §12 Phase 3; FR-10 409 assertion present; permalink-prefix `/docs/{org}/{lib}/{item}/` assertion present; exponential backoff up to 60 s; `afterAll` cleanup; existing specs unchanged |

Claude Code reviews each report, classifies issues (blocker / minor / nit), and patches blockers before progressing. Minor and nit issues are logged but do not block.

**Test-execution pass — Claude Code runs each suite via Bash and attributes failures directly:**

1. Library Manager pytest (52 tests).
2. KB Server v2 pytest.
3. Stable KB Server pytest (`-m "not slow"`).
4. Frontend `npm run check` + `npm run lint`.
5. Frontend `npm run test:unit`.
6. Docker compose stack health on `/status` (backend, port 9099) and `/health` (kb-server 9092, library-manager 9091, kb 9090).
7. The §17 CLI script end-to-end with the FR-10 409 assertion.
8. Playwright existing specs: `library_api.spec.js`, `kb_detail_modals.spec.js`, `kb_delete_modal.spec.js`.
9. Playwright new specs: `knowledge_store_api.spec.js`, `knowledge_store_ui.spec.js`, `knowledge_store_e2e_workflow.spec.js`.
10. Whole Playwright suite (`npm test`) for regression sanity.

The implementation succeeds when every static-review subagent returns zero blockers and every test command in 1–10 completes green. On failure, Claude Code attempts one targeted fix scoped to the reported issue, re-runs the affected suite, and re-reports. If a failure proves to be a real implementation gap (not environmental), Claude Code halts and surfaces the gap to the user before any further changes.
