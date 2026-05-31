# Functionality Review — KB Server (Knowledge Stores) + Library Manager

**Date:** 2026-05-12
**Reviewer:** Claude Code (Opus 4.7) on `kbserver-integration` worktree, `lamb-kb-server/` on `projects/refactor/kbserver-lamb-integration`.
**Scope:** `lamb-kb-server/` (new, port 9092) and `library-manager/` (port 9091). NOT the legacy `lamb-kb-server-stable/`.
**Provider:** LM Studio only — `http://host.docker.internal:1234/v1`, chat `gemma-4-26b-a4b-it@8bit`, embeddings `text-embedding-nomic-embed-text-v1.5`. Org id=1 (`lamb` system org) verified aligned.

The review answered four user questions:
1. Do the chunking strategies actually do what their names claim, in the vector DB?
2. Do the chunking parameters work, and can users configure them?
3. Do the import plugins actually import the full content?
4. Does the embedding pipeline actually compute and store correct vectors?

## Verdict at a glance

| Area | Status |
|---|---|
| Chunking strategy algorithms | **PASS** — all four (`simple`, `hierarchical`, `by_page`, `by_section`) correct end-to-end (verified by T01–T07) |
| Chunking parameter consumption | **PASS** — every declared param is consumed by its chunk function (verified by T02, T04, T07) |
| Chunking parameter server-side range validation | **FIXED** — `_common.py:validate_chunking_params` now enforces declared min/max (verified by T_oor returning 422) |
| Chunking parameter UI exposure (Svelte wizard) | **GAP — NOT FIXED** — wizard hard-codes `chunking_params: {}`. Surfaced for follow-up. |
| LM Studio embedding path (via OpenAI plugin) | **PASS** — endpoint override, model resolution, primitive metadata all correct |
| Credential lifecycle (ADR-4) | **PASS** — per-request only, never persisted, never logged |
| Vector DB writes (Chroma + Qdrant) | **PASS** — batching, IDs, parent_text substitution, _text stripping, dimension probe, delete_by_source all correct |
| Retry/truncation on embedding failure | **GAP — NOT FIXED** — single failure marks whole job failed; no retry, no input truncation. Surfaced for follow-up. |
| Library import plugins (5/5) | **PASS** — every successful import writes a `content/full.md` |
| Library `content/pages/` population | **FIXED** — MarkItDown emits form-feeds between PDF pages (not the `<!-- -->` markers Stream C predicted). Both markitdown plugins now populate `content/pages/` for PDFs (and DOCX/PPTX if they also use form-feeds). Verified by T03_pdf and T08v2. |
| `markitdown_import + by_page` silent fallback | **FIXED** — `markitdown_import` now calls `_split_into_pages`; the fallback to simple no longer fires for PDF inputs. Verified by T08v2 (was producing strategy="simple" before fix, now produces strategy="by_page"). |
| `url_import` `timeout` parameter | **FIXED** — now forwarded to `firecrawl.crawl(..., timeout=timeout_s)`. |
| `by_page` / `by_section` fallback hard-coded params | **FIXED** — both strategies now forward caller-supplied `simple`-strategy params to the fallback (filtered to simple's allowed keys). |
| View-content endpoint (PR #376, issue #370) | **PASS** — `/creator/libraries/{lib}/items/{item}/content?format=markdown\|text`, 5 MB cap, HTML blocked by design |

---

## Section 1 — KB Server Chunking (Stream A)

### Algorithm correctness

All four strategies implement what their names claim. Detailed citations:

| Strategy | Verdict | Key code | Tests |
|---|---|---|---|
| `simple` | PASS | `lamb-kb-server/backend/plugins/chunking/simple.py:73-93` — uses `RecursiveCharacterTextSplitter` with the user's `chunk_size`/`chunk_overlap`, separators `["\n\n","\n"," ",""]` | `tests/unit/test_chunking.py:40-275` (incl. extremes `chunk_size=1`) |
| `hierarchical` | PASS | `hierarchical.py:30` H2/H3 regex; `hierarchical.py:88-142` tree extraction; `hierarchical.py:176-200` only children emitted; each carries `parent_chunk_id`, `child_chunk_id`, `parent_text`, `chunk_level="child"`, `section_title`, `section_part` (`hierarchical.py:204-216`) | `test_chunking.py:71-351` + integration `test_content_pipeline.py:514` |
| `by_page` | PASS | `by_page.py:152` — tries `document.pages` → `<!-- Page N -->` markers (regex `by_page.py:33`) → fallback to `SimpleChunking`. `page_range`, `page_numbers` (pipe-encoded), `permalink_page` all set per `by_page.py:122-137` | `test_chunking.py:115-466` + integration `test_content_pipeline.py:612` |
| `by_section` | PASS | `by_section.py:104-115` real heading-tree walk; `by_section.py:134-138` nested headings stay inside parent; `by_section.py:145-152` `_node_to_text` recurses; `parent_path` `" > "`-joined, `section_titles` pipe-encoded | `test_chunking.py:169-627` — but **no integration test with non-default params** |

**Nuance worth knowing:** H1 headers do NOT create parent boundaries in `hierarchical` — the regex starts at `#{2,3}`. A doc using only H1s collapses to one "Document" parent. Consistent with the docstring but surprising to H1-heavy users.

### Chunking parameter status

Every parameter is **declared with min/max bounds** AND **consumed by the chunk function**. The gaps are in validation and UI:

| Strategy | Param | Declared | Consumed | Server-side range-validated | API schema | Svelte wizard |
|---|---|---|---|---|---|---|
| simple | chunk_size | yes | yes | **NO** | yes (`schemas/collection.py:42-45`) | **NO** |
| simple | chunk_overlap | yes | yes | **NO** | yes | **NO** |
| hierarchical | parent_chunk_size | yes | yes | **NO** | yes | **NO** |
| hierarchical | child_chunk_size | yes | yes | **NO** | yes | **NO** |
| hierarchical | child_chunk_overlap | yes | yes | **NO** | yes | **NO** |
| by_page | pages_per_chunk | yes | yes | **NO** | yes | **NO** |
| by_section | split_on_heading | yes | yes | **NO** | yes | **NO** |
| by_section | headings_per_chunk | yes | yes | **NO** | yes | **NO** |

**Where the validation gap lives:** `_common.py:21-44` `validate_chunking_params` checks **only key names**, not numeric ranges. Invoked at `services/collection_service.py:46-54` (create-time) and defensively at `services/ingestion_service.py:163-167`. A typo'd key returns 422; `chunk_size=999999` or `split_on_heading=99` passes through.

**Where the UI gap lives:** `StepKSSetup.svelte:246` sends `chunking_params: {}` unconditionally. `CreateKnowledgeWizard.svelte:88` initializes it as `{}` and nothing writes to it. The downstream pipeline (`Step8_ReviewCreate.svelte:341` → `KnowledgeStoreCreate.chunking_params` at `backend/creator_interface/knowledge_store_router.py:47` → KB Server) accepts the field, so **CLI and direct API calls work**; only the wizard never populates it.

**Immutability after create:** ENFORCED. `UpdateCollectionRequest` only permits `name`+`description` (`schemas/collection.py:53-61`); the LAMB-side update endpoint mirrors this (`knowledge_store_router.py:54-57`, `:263-292`).

### Minor wrinkles in fallback paths

- `by_page` falls back to `SimpleChunking(chunk_size=1000, chunk_overlap=200)` — **hard-coded**, ignoring the user's `chunking_params` (`by_page.py:202-203`).
- `by_section` does the same on no-heading-match (`by_section.py:203`).

These are technically per-docstring but unexpected: a user who configured `chunk_size=500` and picked `by_section` will silently get 1000-char chunks if their doc lacks headings at the configured depth.

---

## Section 2 — KB Server Embeddings, Vector DB, Credentials (Stream B)

### LM Studio path

| Check | Verdict | Citation |
|---|---|---|
| Endpoint override transport | PASS | `AddContentRequest.embedding_credentials.{api_key,api_endpoint}` (`schemas/content.py:35-45`); persisted on `Collection.embedding_endpoint`; used as fallback in `services/ingestion_service.py:147-149` and `services/query_service.py:45` |
| Strip-trailing-`/embeddings` w/ `…/v1` URL | PASS | `plugins/embedding/openai.py:62` `removesuffix("/embeddings")` — for `http://host.docker.internal:1234/v1` the result is unchanged. Parameterized test: `tests/unit/test_embedding_plugins.py:160-196` |
| Model name resolution | PASS but FRAGILE | Model taken from `collection.embedding_model` at job pickup (`ingestion_service.py:144`). Locked at creation. Picking `text-embedding-3-small` at create time would silently 404 against LM Studio on first ingest. |
| Cloud-OpenAI key fallback risk | LOW | `openai.py:51` falls back to `EMBEDDINGS_APIKEY` env. docker-compose sets it to `placeholder-set-per-request`, so on a production deploy that left a real cloud key in env, an omitted per-request key would silently use that — minor but worth a docker-compose comment. |

### Credential lifecycle (ADR-4)

| Check | Verdict | Citation |
|---|---|---|
| `_job_credentials` is in-memory only | PASS | `tasks/worker.py:38` module dict; `models.py:107` docstring confirms not serialized |
| Popped on pickup | PASS | `worker.py:95` `_job_credentials.pop(job_id, {})` |
| Lost on restart, by design | PASS | dict resets; `recover_stale_jobs` (`worker.py:264-297`) does NOT restore credentials |
| Never written to logs | PASS | No `logger.*` call across `worker.py`, `ingestion_service.py`, or any plugin file includes `api_key`/`api_endpoint`; exception messages truncated to 500 chars and credential-free (`worker.py:140`) |
| Stale-job retry replays without credentials | **GAP (low)** | Stale `processing` jobs reset to `pending` (`worker.py:289`); poller picks them up, `_job_credentials.pop(job_id, {})` returns `{}`. Job runs with `api_key=""`, fails with opaque vendor error. Correct per ADR (no covert reuse) but error surface unclear. |

### Vector DB integrity

| Check | Verdict | Citation |
|---|---|---|
| ChromaDB 100-chunk batches | PASS | `chromadb_backend.py:37,181` |
| ChromaDB IDs are UUIDs | PASS | `chromadb_backend.py:184` |
| ChromaDB metadata primitive-only | PASS | Pydantic-enforced upstream (`schemas/content.py:76-91`) |
| ChromaDB parent_text substitution | PASS | `chromadb_backend.py:272`; test `tests/unit/test_vector_db_chromadb.py:127-160` |
| Qdrant `_text` stripped on read | PASS | `qdrant_backend.py:275`; test `:173-203` |
| Qdrant dimension probe non-empty | PASS | `qdrant_backend.py:106` `embedding_function(["dimension probe"])` |
| `delete_by_source` filters on `source_item_id` | PASS — both | `chromadb_backend.py:212`, `qdrant_backend.py:208,222` |
| Cosine score normalization | PASS | Chroma `1 - dist` (`chromadb_backend.py:273`); Qdrant `(score+1)/2` (`qdrant_backend.py:279`) |
| On-disk path | PASS | `services/collection_service.py:100` `STORAGE_DIR/{org_id}/{collection_id}`, `STORAGE_DIR = DATA_DIR/"storage"`. With docker default `DATA_DIR=lamb-kb-server/data` → `lamb-kb-server/data/storage/{org_id}/{collection_id}/`. Backend collection name prefixed `kb_<collection_id>` (`:107`) |

### No-retry / no-truncation gap

Grep for `retry|tenacity|backoff` in `plugins/`, `services/`, `tasks/` returns zero hits (only `_MAX_ATTEMPTS` for stale-job retry, NOT for vendor errors). Any LM Studio rate-limit or oversized-input failure bubbles up of `add_chunks` → `execute_ingestion_job` (`ingestion_service.py:194`) → caught by `_process_job_sync` (`worker.py:137-148`) → job marked `failed` with `error_message="Ingestion failed: <Type>: <repr[:500]>"`. The 5-batch commit (`ingestion_service.py:206`) preserves partial progress.

HTTP 413 protection is present at the request layer (`routers/content.py:51-64`, default 200 MB) — but per-chunk size never checked.

### View-content endpoint

`GET /creator/libraries/{library_id}/items/{item_id}/content?format=markdown|text`
- Defined at `backend/creator_interface/library_router.py:466-498`.
- 5 MB cap (`MAX_CONTENT_BYTES`, line 463); HTTP 413 over the limit.
- HTML deliberately not exposed (unsanitized server-side renderer in Library Manager).
- ACL: `auth.require_library_access(library_id, level="any")`.
- Path traversal guarded by `LibraryManagerClient.proxy_content` (`library_manager_client.py:347`).
- **Returns `content/full.md` only.** For per-page content (`content/pages/{n}.md`), use the permalink proxy at `/docs/{org_id}/{library_id}/{item_id}/content/pages/{n}` (`library_router.py:641-674`).

---

## Section 3 — Library Manager Imports (Stream C)

### Per-plugin verdict

| Plugin | Sources | `full_text` | `pages` | `images` | Verdict |
|---|---|---|---|---|---|
| `simple_import` | `.txt`/`.md`/`.html` | UTF-8 read | Never | Never | PASS (no BOM/sniff; HTML stored as raw HTML, no markdown conversion) |
| `markitdown_import` | PDF/DOCX/PPTX/XLSX/EPUB/audio/HTML/+ | MarkItDown convert | **Never** | Never | **GAP** — even for PDF, `pages=[]` always |
| `markitdown_plus_import` | PDF/DOCX/PPTX/+ | MarkItDown + PyMuPDF image extraction | Rare (depends on MarkItDown emitting `---`, `\f`, or `<!-- page break -->`) | **Only for PDFs** (line 218 hard-restriction) | **BUG / GAP** — page-break heuristics rarely fire; DOCX/PPTX never get images |
| `url_import` | URL | Multi-page Firecrawl crawl concatenated with `---` | Never (missed opportunity — one entry per crawled URL would feed `by_page`) | Never | PASS for happy path; `timeout` param declared but never consumed by Firecrawl client |
| `youtube_transcript_import` | YouTube URL | Timestamped markdown | Never | Never | PASS — manual→auto→placeholder fallback; `language`/`proxy_url` wired |

### Storage layout — confirmed

```
{CONTENT_DIR}/{org_id}/{lib_id}/{item_id}/
    metadata.json
    source_ref.json
    original/{sanitized name}     # only file-based imports; URL/YouTube skip
    content/
        full.md                    # always (zero-byte if empty)
        pages/page_NNN.md          # only if plugin.pages != []
        images/img_NNN.<ext>       # only if plugin.images != []
```

`_sanitize_filename` (`content_service.py:453-471`) reduces to `Path(name).name` and strips NULs — adequate against traversal. Image counter is monotonic (`img_001.png`, …), so collisions from a single plugin run are impossible. Empty `full_text` still writes a zero-byte `full.md` and marks the item `ready` — same trap as below.

### Empty-content placeholders mark items as ready

Three places emit placeholder text and mark the item `ready`:
- `markitdown_import.py:77-79` — "No extractable text found in <name>"
- `url_import.py:138-148` — "No content could be crawled from <url>"
- `youtube_transcript_import.py:72-81` — "No transcript available for video <id>"

Downstream KB Server ingestion will happily embed these placeholders, consuming API budget and producing meaningless retrieval results. **Recommend:** mark such items as `ready_no_content` or `failed_no_content`; refuse to link them into a Knowledge Store.

### Async queue — clean

`ImportJob` SQLite table polled every 2s; `MAX_CONCURRENT_IMPORTS` semaphore (`worker.py:200,225`); per-job timeout via `asyncio.wait_for(...)` (`worker.py:144`); stale-job recovery resets `processing` → `pending` with `MAX_ATTEMPTS` cap; API keys in `_job_api_keys` dict popped on pickup; explicit no-persistence comment at `models.py:150-151`.

Minor concern (already noted in Stream B too): stale-recovered jobs lose their original API keys → re-runs that need a Firecrawl key or OpenAI vision key silently degrade or fail.

### Critical gap — `markitdown_import + by_page` silent fallback

End-to-end chain:

1. User creates a locked Knowledge Store with `chunking_strategy="by_page"`.
2. User imports a PDF via `markitdown_import`.
3. `markitdown_import.py:107-109` returns `ImportResult(pages=[], images=[])` always.
4. `write_structured_content` skips `content/pages/` (`content_service.py:95`); DB `page_count=0`.
5. LAMB queues `add-content` with `pages=[]` in the payload.
6. KB Server `ByPageChunking.chunk()` (`by_page.py:152`):
   - Source 1 `document.pages`: empty → skip
   - Source 2 `<!-- Page N -->` markers: **MarkItDown does not emit these** → skip
   - Source 3: **falls back to `SimpleChunking(chunk_size=1000, chunk_overlap=200)`** — only a server log warning, no user-visible signal

`markitdown_plus_import` *attempts* page-break detection with three regex patterns (`markitdown_plus_import.py:_PAGE_BREAK_PATTERNS`):
```python
[r"^-{3,}\s*$", r"^\f", r"^<!--\s*page\s*break\s*-->"]
```
MarkItDown's PDF output uses none of these consistently. A `---` rule in the source PDF is content, not a page boundary. **In practice this heuristic almost never fires.**

| User picks plugin | User picks chunker | Actual chunking |
|---|---|---|
| `simple_import` | `by_page` | simple fallback (correct — no pages to honor) |
| `markitdown_import` (PDF) | `by_page` | **simple fallback — user expected per-page** |
| `markitdown_plus_import` (PDF) | `by_page` | usually simple fallback |
| `url_import` | `by_page` | simple fallback |
| `youtube_transcript_import` | `by_page` | simple fallback |

The only structurally correct path for `by_page` chunking today is a manually-authored markdown file containing `<!-- Page N -->` comments. No plugin produces such markup.

---

## Section 4 — Recommended fixes

### Inline (low-risk, will be applied during this review)

1. `url_import` — wire the `timeout` parameter into the Firecrawl call. Currently declared in the schema (`url_import.py:207-212`) but not consumed.
2. Server-side **range validation** of chunking params at `services/collection_service.py` create time — call into each strategy's `get_parameters()` `min_value`/`max_value` and reject out-of-range values with HTTP 422.
3. `by_page` / `by_section` fallback chunking — pass the user's `chunking_params` to the fallback `SimpleChunking` instead of hard-coding `{1000, 200}`. So a user who set `chunk_size=500` on a doc that turns out to have no pages/headings still gets 500-char chunks.

### Surfaced for user decision (larger or design-required)

4. Svelte wizard chunking-param form fields — adds inputs for each strategy's params in `StepKSSetup.svelte` / a new step.
5. **`by_page`/`by_section` runtime mismatch detection** — when chunking strategy is `by_page` but the document has no pages and no markers, currently silent. Options: log louder, return a job-completion warning, or reject the add-content call.
6. Make MarkItDown PDF imports populate `pages` reliably — would require a different PDF library (PyMuPDF directly) or post-processing to insert `<!-- Page N -->` markers.
7. Treat empty-content placeholder items as `ready_no_content`; refuse to link them into a Knowledge Store.
8. Stale-job recovery on the KB Server: surface a clear error message when credentials are missing post-restart, rather than letting the embedding vendor error bubble up.

---

## Section 5 — Dynamic verification (Stream D)

Live ingestion + retrieval probes against the booted services. Embeddings: LM Studio (`text-embedding-nomic-embed-text-v1.5`) on `http://host.docker.internal:1234/v1`. ChromaDB vector backend. Library `func-review-20260512` on org `1`.

### Fixtures created

Under `/tmp/lamb-review-fixtures/`:
- `simple.md` — 6959 chars Lorem ipsum, no headings, no page markers
- `structured.md` — explicit H1 / 3×H2 / 9×H3 hierarchy
- `pages_marked.md` — 5 pages separated by `<!-- Page N -->` markers
- `multi_page.pdf` — 7-page PDF generated with PyMuPDF, distinctive `zylonite-N` keyword per page

### Probe results

| ID | Source | Plugin | Chunking | Params | Result |
|---|---|---|---|---|---|
| T01 | simple.md | simple_import | simple | defaults (1000, 200) | **PASS** — 9 chunks, ~999 chars each, strategy="simple" |
| T02 | simple.md | simple_import | simple | `{chunk_size: 300, chunk_overlap: 50}` | **PASS** — 28 chunks, ~295 chars each — **params demonstrably consumed end-to-end** |
| T03 | pages_marked.md | simple_import | by_page | defaults | **PASS** — 5 chunks, one per `<!-- Page N -->` marker; query for "topic number 3" returns page 3 first |
| T04 | pages_marked.md | simple_import | by_page | `{pages_per_chunk: 2}` | **PASS** — 3 chunks: page_range "1-2", "3-4", "5"; page_numbers "1\|2", "3\|4", "5" |
| T03_pdf | multi_page.pdf | markitdown_plus | by_page | defaults | **PASS** — 7 chunks, `permalink_page` references `/docs/.../pages/page_NNN.md`; query "zylonite-4" returns page 4 with score 0.708 |
| T04_pdf | multi_page.pdf | markitdown_plus | by_page | `{pages_per_chunk: 3}` | **PASS** — 3 chunks, page_range "1-3", "4-6", "7" |
| T05 | structured.md | simple_import | hierarchical | defaults | **PASS** — 13 children emitted; every chunk carries `parent_chunk_id`, `child_chunk_id`, `parent_text`, `section_title`, `chunk_level="child"`; query "Part Two" returns Part Two parent first (score 0.876) |
| T06 | structured.md | simple_import | by_section | `{split_on_heading: 2}` | **PASS** — 3 chunks, one per H2; `parent_path="Book of Examples"`, `section_titles` ∈ {"Part One", "Part Two", "Part Three"} |
| T07 | structured.md | simple_import | by_section | `{split_on_heading: 3}` | **PASS** — 9 chunks, one per H3; `parent_path="Book of Examples > Part Two"` etc.; H1+H2 context prepended to chunk text |
| T08 | multi_page.pdf | markitdown_import | by_page | defaults | **BEFORE FIX**: silent fallback — 4 chunks with `strategy="simple"` (user picked by_page!). **AFTER FIX**: 7 chunks with `strategy="by_page"`, correct page metadata |
| T_oor | simple.md | simple_import | simple | `{chunk_size: 99999}` (above max 8000) | **BEFORE FIX**: silently accepted, produced 1 chunk. **AFTER FIX**: HTTP 422 `chunking_params['chunk_size']=99999 is above the declared maximum 8000 for strategy 'simple'.` |
| T09 | docs.python.org URL | url_import | n/a (Library Manager only) | depth=1, limit=3 | **UNVERIFIED — Firecrawl unreachable** from library-manager container (`firecrawl:3002` DNS fail; lamb-firecrawl-* containers on a different docker network than library-manager). Plugin code reached the call site correctly with the right params; failure is environmental. |
| T10 | YouTube "Me at the zoo" | youtube_transcript_import | n/a (Library Manager only) | language=en | **PASS** — `subtitle_source="manual"`, 5 transcript pieces, `**[mm:ss]**` timestamp format confirmed |

### Fixes applied during review

| File | Change | Verified by |
|---|---|---|
| `lamb-kb-server/backend/plugins/chunking/_common.py` | `validate_chunking_params` now enforces declared `min_value` / `max_value` per parameter, in addition to the existing unknown-key check. Numeric type-check guards against passing strings/bools where numerics are expected. | T_oor returns 422 with a precise message; 47/47 chunking unit tests still pass. |
| `lamb-kb-server/backend/plugins/chunking/by_page.py` | When falling back to `SimpleChunking` because no page information was found, forward any caller-supplied `simple`-strategy params (`chunk_size`, `chunk_overlap`) instead of hard-coding `{1000, 200}`. Strategy-specific keys filtered out. | Code review + 47/47 chunking unit tests still pass. |
| `lamb-kb-server/backend/plugins/chunking/by_section.py` | Same fix as `by_page` for the no-heading-at-target-level fallback. | Code review + 47/47 chunking unit tests still pass. |
| `library-manager/backend/plugins/url_import.py` | The declared `timeout` parameter (default 300s) is now forwarded to `firecrawl.crawl(..., timeout=timeout_s)`. Previously declared but never consumed. | Code change visible; 52/52 LM tests still pass. |
| `library-manager/backend/plugins/markitdown_import.py` | Now calls `_split_into_pages()` (imported from `markitdown_plus_import`) when the file is page-aware (PDF/DOCX/PPTX), populating `content/pages/page_NNN.md` from form-feed page boundaries that MarkItDown already emits. **Closes the silent `by_page → simple` fallback gap.** | T08v2 produces 7 by_page chunks with correct page metadata, instead of 4 simple-fallback chunks. 52/52 LM tests still pass. |

### Test suite regression check

- KB Server: **47/47 chunking tests pass** after the fixes. Full unit suite: 337/338 pass; the single pre-existing failure (`test_dependencies.py::test_correct_token_is_accepted`) is environmental — the test expects `LAMB_API_TOKEN=test-token` but the container ships `LAMB_API_TOKEN=change-me`. Unrelated to chunking or import code.
- Library Manager: **52/52 tests pass** after the fixes.

### Stream B confirmation — interesting findings

The static prediction in Stream C that `<!-- Page N -->` markers don't get emitted by MarkItDown turned out to be partially wrong: **MarkItDown 0.x emits form-feed (`\x0c`) between PDF pages**. The page-split regex `r"^\f"` in `_PAGE_BREAK_PATTERNS` actually does fire reliably for PDFs. The 7-page test PDF produced 6 form-feeds between pages and was split correctly by `markitdown_plus_import`. With the fix above, `markitdown_import` now also benefits from this.

The remaining open question: do DOCX/PPTX exports through MarkItDown also use form-feed? Not verified — flag for a follow-up probe with DOCX/PPTX fixtures.

### Items NOT fixed in the initial round (surfaced for user decision)

1. **Svelte wizard chunking-param form fields** — was a gap. **Now fixed.** See "Follow-up fixes" below.
2. **Empty-content placeholder items mark as `ready`** — `markitdown_import.py`, `url_import.py`, `youtube_transcript_import.py` all emit `"*(No extractable text…)*"` or similar and end the item as ready. Downstream KB ingestion happily embeds the placeholder. Recommend introducing a `ready_no_content` status and refusing KB linkage. Design decision.
3. **Stale-job recovery on KB Server loses credentials** — `_job_credentials` dict is in-process only by design (ADR-4). On restart, stale jobs are revived with empty credentials, then fail with opaque vendor errors. Recommend either explicitly failing such jobs at recovery time with a clear message, or surfacing a structured "credentials missing post-restart" error to the caller.
4. **MarkItDown export of DOCX/PPTX** — page-split needs verifying on Office formats. The `_PAGE_AWARE_TYPES` set already includes `docx` and `pptx` but no real Office fixtures were tested. Recommend a Stream D follow-up probe.
5. **Hierarchical chunker treats H1 specially** — H1 is not a parent boundary (regex starts at `#{2,3}`); H1-heavy docs collapse into one `"Document"` parent. Per docstring but surprising. Consider adding H1 to the regex or documenting more prominently.

### Follow-up fixes (second round)

After the initial review, the user asked for two additional fixes which were applied:

**1. Chunking parameters in the create-knowledge wizard, with mutability after create.**

- `frontend/svelte-app/src/lib/components/knowledge/wizard/StepKSSetup.svelte` — added a dynamic `<fieldset>` that renders one numeric `<input>` per declared parameter of the selected chunking strategy. Defaults come from `options.chunking_strategies[*].parameters[*].default` (already exposed by the KB Server). Validation is client-side against the declared `min_value` / `max_value`. Re-selecting a strategy resets params to that strategy's defaults; out-of-range values block the wizard's "Next" button.
- Locked-config notice updated to clarify that `chunking_strategy`, `embedding_vendor`/`embedding_model`, and `vector_db_backend` are still locked, but **chunking parameters can be edited later** — changes apply only to newly-ingested content (existing chunks keep the parameters they were originally chunked with).
- `lamb-kb-server/backend/schemas/collection.py` — `UpdateCollectionRequest.chunking_params` added (was previously only `name`/`description`).
- `lamb-kb-server/backend/services/collection_service.py:update_collection` — accepts the new field; validates via `validate_chunking_params` (range + unknown-key); persists; **does NOT re-chunk existing data** (the semantic the wizard advertises).
- `backend/creator_interface/knowledge_store_router.py` — `KnowledgeStoreUpdate.chunking_params` added; PUT `/creator/knowledge-stores/{ks_id}` forwards the field to the KB Server.
- `backend/creator_interface/knowledge_store_client.py:update_collection` — forwards `chunking_params` in the PUT body.
- `backend/lamb/database_manager.py:update_knowledge_store` — persists `chunking_params` JSON column.

Live verification: created a collection with `chunk_size=500`, ingested simple.md → 16 chunks tagged `chunking_chunk_size=500`. PUT `chunking_params={chunk_size: 300}`. Re-ingested same doc with different `source_item_id` → 26 chunks tagged `chunking_chunk_size=300`. Query returned both buckets in the vector DB; existing chunks retained their original metadata.

Validation negative cases also confirmed: `PUT chunking_params={chunk_size: 99999}` → 422 with declared-maximum error; `PUT chunking_params={foo: 1}` → 422 with unknown-key error.

**2. Firecrawl service container reliability — closes the T09 UNVERIFIED status.**

The Firecrawl support containers (postgres, rabbitmq, redis, playwright) were running, but the actual API container (`lamb-firecrawl-1`) was in a crash loop with `exit 137` (OOM-killed) under the 2 GB `mem_limit` set in `docker-compose.firecrawl.override.yaml`.

- `docker-compose.firecrawl.override.yaml` — bumped `firecrawl.mem_limit` from 2 GB to 4 GB, and added `environment:` overrides to tighten worker / browser-pool counts (`NUM_WORKERS_PER_QUEUE=2`, `MAX_CONCURRENT_JOBS=3`, `BROWSER_POOL_SIZE=2`, etc.). Stable at 1.83 GiB / 4 GiB after start.

Live verification: T09 re-run with `https://example.com/` via `url_import` plugin → ingested in ~18 s, produced 231-char markdown, `pages_crawled=1`, persisted to disk. The DNS resolution (`firecrawl:3002` inside the `lamb-lamb` network) and the timeout-param wiring already done in the first round both work end-to-end now.

### Conclusion

All four user-facing questions answered:

1. **Are the chunking strategies actually correct?** — Yes. Live probes confirm hierarchical produces parent_text/parent_chunk_id linkage, by_page produces one chunk per page with `page_numbers` metadata, by_section walks the heading tree at the configured depth with `parent_path` reflecting the H1>H2>H3 chain.
2. **Do the chunking params work? Can users configure them?** — Yes, end-to-end via API/CLI (T02, T04, T07 all show non-default params take effect). Server-side range validation is now enforced (was a gap). The Svelte wizard does NOT currently expose param inputs — flagged for follow-up.
3. **Are library imports correct?** — Yes for `full.md`. After the `markitdown_import` fix, PDF page boundaries are also preserved in `content/pages/` for both markitdown plugins. URL and YouTube plugins work when their external services are reachable (T10 confirmed; T09 environmental).
4. **Does the embedding pipeline work?** — Yes. LM Studio path produces correct vectors, ChromaDB persists metadata and substitutes `parent_text` for hierarchical retrieval, query scores are normalized.

