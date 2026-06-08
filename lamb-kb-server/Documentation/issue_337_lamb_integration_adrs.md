# LAMB ↔ Knowledge Stores Integration — Architecture Decision Records

**Issue:** [#337](https://github.com/Lamb-Project/lamb/issues/337)
**Depends on:** [#334](https://github.com/Lamb-Project/lamb/issues/334) — new KB Server microservice (`lamb-kb-server/`).
**Reference plan:** [#336](https://github.com/Lamb-Project/lamb/issues/336) — LAMB ↔ Library Manager integration. The patterns from #336 are the template for this integration; only the differences specific to the new KB Server are documented here.

These ADRs capture the design decisions made when wiring the new KB Server (port 9092) into LAMB. The legacy stable KB Server integration (port 9090, `kb_registry`, `/creator/knowledgebases`) is preserved entirely unchanged.

---

## ADR-KS-1 — Parallel surfaces, not a version flag on `kb_registry`

**Status:** Accepted.

**Context.** Two KB Servers must coexist: the stable one on port 9090 (already integrated end-to-end) and the new one on port 9092 (this issue). Three coexistence designs were considered:

1. Add a `kb_server_version` discriminator column on the existing `kb_registry` table and branch routing per row.
2. Per-org flag selecting which server an entire organization uses.
3. Parallel surfaces: separate router, separate tables, separate client, separate RAG processor, separate frontend route.

**Decision.** Option 3.

**Rationale.** The two servers differ in fundamental invariants: the new server has locked store setup, library-only ingestion (no file upload), per-request embedding credentials, per-org filesystem isolation, and async job processing. Forcing both shapes through one surface would mean nullable columns, hot-path branching in every endpoint and RAG processor, and a high risk of regressing the live retrieval path (which is exactly the code Marc opened bug #330 against). Industry-standard versioning practice (AWS, Stripe, GitHub) for redesigned services is parallel surfaces, not a discriminator column. The Library Manager integration in #336 is itself an instance of this pattern — repeat it.

**Consequence.** Some duplication (auth helpers, audit-log call site, polling pattern) — accepted for zero regression risk on the legacy KB path and for clean per-feature deprecation later.

---

## ADR-KS-2 — LAMB owns metadata + ACL; KB Server owns vectors

**Status:** Accepted (mirrors #336 ADR-1).

**Decision.** `knowledge_stores` is the source of truth for ownership, sharing, and the locked store setup. The KB Server is the source of truth for chunks and embeddings. `kb_content_links` is the bridge that records which Library items are linked into which Knowledge Stores, plus per-link ingestion status.

**Consequence.** The KB Server has no notion of users, organizations, libraries, or library items. It only sees collection IDs (= LAMB's `knowledge_store_id`) and source item IDs (= LAMB's `library_item_id`). All access control is enforced before any KB Server call.

---

## ADR-KS-3 — Library-only content path

**Status:** Accepted.

**Decision.** A Knowledge Store can ONLY be populated by linking Library items. There is no direct file-upload path on the Knowledge Store surface.

**Rationale.** The new KB Server's `/add-content` endpoint accepts JSON with text + permalinks, not files. The user-visible workflow is "Library → import file → get markdown → ingest into KS → query → cite", and citations resolve through LAMB's `/docs/{org}/{lib}/{item}/...` permalink proxy. Bypassing the Library would mean either (a) introducing a hidden Library concept inside LAMB or (b) accepting that those chunks would have no citable source — both worse than just requiring users to upload to a Library first.

**Consequence.** The frontend wizard's library-creation steps are not optional skips for KS creation; if no Library exists, the user is walked through creating one.

---

## ADR-KS-4 — Embedding key reuses existing org provider key

**Status:** Accepted.

**Decision.** LAMB resolves the embedding API key from `organizations.config.setups.default.providers.{vendor}.api_key` — the same slot already used by chat completions and RAG. It is sent in every `/add-content` and `/query` request to the KB Server, which holds it in memory only and never persists it (#334 ADR-4).

**Rationale.** Org admins already configure provider keys for chat. Adding a separate `knowledge_store.embedding_credentials` block would duplicate config and increase the chance of drift. If an org needs different keys for embedding vs. completions (rare), they can override per Knowledge Store via locked-setup `embedding_endpoint` plus a per-vendor distinct key — the existing provider config supports multiple vendors.

**Consequence.** Knowledge Store creation does not prompt for keys at the point of creation. The only typed input on the wizard's happy path is the Library and KS names.

---

## ADR-KS-5 — Locked store setup

**Status:** Accepted (mirrors #334 ADR-3).

**Decision.** Chunking strategy, chunking parameters, embedding vendor, embedding model, embedding endpoint, and vector DB backend are immutable after creation. Only `name` and `description` are mutable through `PUT /creator/knowledge-stores/{ks}`.

**Rationale.** Changing any of these after ingestion has occurred would silently invalidate stored vectors (different dimensions, different chunk boundaries, different similarity contracts). Industry standard (Qdrant, Pinecone, Weaviate, ChromaDB) is to lock these per-collection.

**Consequence.** "Want different settings? Create a new KS." The wizard's Step 6 surfaces a clear "these settings cannot be changed later" notice with an "Edit defaults" expand affordance for users who want to drill in.

---

## ADR-KS-6 — Permalinks on chunks point at LAMB, not Library Manager

**Status:** Accepted.

**Decision.** Permalink URLs sent into the KB Server's `add-content` payload are constructed against LAMB's own `/docs/{org}/{lib}/{item}/...` proxy.

**Rationale.** Citations must be ACL-enforced. If chunks pointed directly at the Library Manager, anyone with a chunk's permalink could bypass LAMB's library access checks. The LAMB proxy validates the user's organization, the user's library access, and that the library belongs to the claimed org before forwarding to the Library Manager.

**Consequence.** The KB Server is permalink-format-agnostic — it stores whatever LAMB sends and returns it verbatim in query results. If LAMB ever changes its permalink format, existing chunks become harder to resolve; the workaround is re-ingestion (acceptable per #334 NFR-8: "A KB is a snapshot at ingestion time").

---

## ADR-KS-7 — FR-10 enforced in LAMB at library-item delete

**Status:** Accepted.

**Decision.** The check that "this library item is referenced by a Knowledge Store" lives in LAMB's `DELETE /creator/libraries/{lib}/items/{item}` handler. It queries `kb_content_links WHERE library_item_id = ? AND status != 'failed'` and returns **HTTP 409 Conflict** with the list of referencing Knowledge Stores when any active link exists.

**Rationale.** The Library Manager has no awareness of Knowledge Stores, so the constraint cannot live there. The KB Server has no awareness of Libraries, so it cannot live there either. LAMB owns both relations and is the only place where the cross-service invariant can be enforced.

**Consequence.** Users see an actionable error message naming the Knowledge Stores that block deletion. The frontend `LibraryDetail` can render this as a "remove from these Knowledge Stores first" link list. Failed (`status='failed'`) links do not block deletion — those are dead references.

---

## ADR-KS-8 — Delete KB Server first, tolerate 404

**Status:** Accepted (corrects Marc's #336 critical issue #1 pre-emptively).

**Decision.** For Knowledge Store deletion: call KB Server `DELETE /collections/{id}` first; on 2xx or 404, delete the LAMB row (which cascades `kb_content_links`); on 5xx, return 502 and leave the LAMB row intact so the user can retry.

**Rationale.** Reverse order risks orphaning a KB Server collection that LAMB no longer references — content nobody can find. Marc explicitly flagged the symmetric bug in the Library Manager integration (#336 #1); this ADR fixes the same shape for Knowledge Stores from day one.

**Consequence.** A failure on the KB Server side blocks the LAMB-side deletion until the KB Server recovers. Acceptable: the row stays intact and user can retry.

---

## ADR-KS-9 — Provisional create

**Status:** Accepted (mirrors #336's create rollback).

**Decision.** The LAMB `knowledge_stores` row is inserted with `status='provisional'` BEFORE the KB Server `POST /collections` call. On KB Server success, the row is promoted to `status='active'`. On failure, the LAMB row is deleted. The `GET /creator/knowledge-stores` listing filters `status='active'` so partial-failure rows never appear in user listings.

**Rationale.** Without this pattern, a process crash between the LAMB insert and the KB Server call leaves an orphan LAMB row with no corresponding collection. With this pattern, the worst case is an orphan provisional row that a sweep job can clean up later.

**Consequence.** Eventual cleanup of stuck provisional rows (>N minutes old, no `active` promotion) is a future maintenance task. Not implemented in this issue but tracked.

---

## ADR-KS-10 — Per-call httpx clients

**Status:** Accepted (mirrors #336 ADR-9 and the existing `kb_server_manager.py` pattern).

**Decision.** `KnowledgeStoreClient` creates a fresh `httpx.AsyncClient` per call inside an `async with` context manager. No connection pooling.

**Rationale.** Matches existing LAMB-side HTTP-client patterns (`LibraryManagerClient`, `kb_server_manager.py`). Connection pooling is a future optimization if KB Server latency becomes a bottleneck — defer until measured.

---

## ADR-KS-11 — Static routes before parameterized

**Status:** Accepted (mirrors #336 ADR-10).

**Decision.** Routes like `/options` are registered before `/{ks_id}` in `knowledge_store_router.py` so FastAPI does not match the literal segment `options` as the `ks_id` parameter.

**Consequence.** Any new static endpoint added later (e.g., `/import`, `/export`) must be inserted before the parameterized routes in the file.

---

## ADR-KS-12 — Sibling RAG processor; no branching in existing

**Status:** Accepted.

**Decision.** A new RAG processor file `backend/lamb/completions/rag/knowledge_store_rag.py` is added next to the existing processors (`simple_rag.py`, `context_aware_rag.py`, etc.). The existing processors are not modified. Assistants that should retrieve from a Knowledge Store have `rag_processor='knowledge_store_rag'` set in their plugin config; everything else continues to use `simple_rag` or other existing processors against the legacy stable KB Server.

**Rationale.** The RAG path is the most failure-sensitive code in LAMB — bugs there break chat for every assistant. Adding a v1/v2 branch inside `simple_rag.py` would create exactly the kind of conditional Marc flagged in #336. A sibling file is auto-discovered by the plugin loader, requires no edits to existing processors, and surfaces in the assistant-builder dropdown automatically via the existing `/capabilities` endpoint.

**Consequence.** Some duplication of citation-source extraction code between `simple_rag.py` and `knowledge_store_rag.py`. Accepted for zero blast-radius on the legacy retrieval path.

---

## ADR-KS-13 — CLI primary command is `lamb ks`, with `lamb knowledge-store` as alias

**Status:** Accepted.

**Decision.** The new CLI surface is registered under both `lamb ks` (primary, short) and `lamb knowledge-store` (long-form alias) — both resolve to the same Typer app.

**Rationale.** Mirrors the existing `lamb kb` precedent for the legacy KB Server. `ks` reads naturally as the short form for Knowledge Stores and reinforces the visual distinction from `kb` in muscle memory.

---

## ADR-KS-14 — Frontend renames the Library Manager tab to "Knowledge"; "KB Server" tab unchanged

**Status:** Accepted.

**Decision.** The existing `/libraries` route is restructured into a unified "Knowledge" page with two sub-tabs ("Libraries" and "Knowledge Stores") and a primary "Create Knowledge" wizard launcher. The legacy "KB Server" navigation entry pointing at `/knowledgebases` is left untouched.

**Rationale.** Most user flows that create a Knowledge Store will also touch a Library (D3 / ADR-KS-3). Putting both surfaces on one page with a unified wizard makes the relationship explicit and reduces navigation. The legacy "KB Server" tab serves the legacy stable KB Server only and has no reason to change.

**Consequence.** Existing bookmarks `/libraries` and `/libraries?view=detail&id=X` continue to work via back-compat URL handling. A direct entry point at `/knowledge-stores` redirects to `/libraries?section=knowledge-stores` for power users who type the route by hand.

---

## ADR-KS-15 — Defaults-everywhere wizard

**Status:** Accepted.

**Decision.** Every form field in the unified create wizard comes pre-populated with sensible defaults so a user who clicks Next on every step ends up with a working Library + Knowledge Store + first ingestion. The only required typed input on the happy path is the Library name (Step 1) and the Knowledge Store name (Step 5) — and even those are auto-suggested with a date-stamped default.

**Rationale.** The wizard subsumes what was previously a multi-page workflow (open Libraries → create → upload → open Knowledge Bases → create → link). Forcing the user to make N decisions across 9 steps would defeat the point. Customisation is one click away ("Edit defaults" expander on Steps 2 and 6) but never required.

**Consequence.** Org admins control the defaults indirectly via the allow-list in `setups.default.knowledge_store.allowed_*` — the wizard pre-selects the first allowed option for each locked-setup field.

---

## ADR-KS-16 — Existing-resource skip rules in the wizard

**Status:** Accepted.

**Decision.** The wizard's Step 0 lets users pick an existing Library from a dropdown; doing so skips Steps 1–3 (Library creation) and lands on Step 4. Step 4 lets users pick an existing Knowledge Store from a dropdown; doing so skips Steps 5–6 (KS creation) and lands on Step 7 (item picker). The Back button respects skipped steps in both directions.

**Rationale.** Frequent flows are "I have a Library, I just want to ingest it into a new KS" or "I have a KS, I want to ingest more items". Forcing a 9-step wizard for these is friction. Branching at Steps 0 and 4 with explicit "Use existing / Create new" radios is fast for power users and obvious for first-timers.

---

## ADR-KS-17 — Polling uses exponential backoff, not fixed window

**Status:** Accepted (replaces Marc's #336 review #19 finding pre-emptively).

**Decision.** All polling — content-link status in the CLI, the frontend detail panel, and the Playwright workflow spec — uses exponential backoff (1s → 2s → 4s → 8s → 16s, capped) with a generous total budget (60s default, 90s for the workflow test, 600s for the CLI `--wait` flag). The fixed 15-second polling window pattern Marc flagged in the Library Manager integration (#336 #19) is not used anywhere.

**Rationale.** Embedding ingestion can be slow under load; a 15-second hard window flakes in CI environments without a working warm cache. Backoff stays responsive on quick jobs (1s first poll) while gracefully waiting on slow ones.

---

## Out of scope for issue #337

- Migrating existing `kb_registry` rows to `knowledge_stores` — explicitly out of scope per #334 non-goals.
- Cross-org Knowledge Store sharing.
- Re-ingestion / freshness sync when a Library item changes — KS is a snapshot at ingestion time per #334 NFR-8.
- Internal TLS between LAMB and the new KB Server — deferred per #336's Phase 3.
- Marc's deferred items from #336 (rate limiting on import endpoints, hard-cancel job timeout, etc.) — tracked separately.
