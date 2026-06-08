# Server-side pagination for /creator/libraries and /creator/knowledge-stores

## Why this is deferred

- Datasets are small today (typically <100 entries per user); client-side pagination is adequate.
- Adding `limit`/`offset` to the list responses is a **breaking shape change**: the envelope gains
  `total` / `total_count`, which requires coordinated updates to the backend routers, DB helpers,
  frontend services, list components, CLI commands, and integration tests in a single lockstep
  release.
- The UI overhaul that surfaced this need prioritised polish over scaling headroom.

Both upstream services already support `limit`/`offset` today — the gap is entirely in the LAMB
creator-interface layer.

---

## What needs to change

### Backend — creator interface routers

**`backend/creator_interface/library_router.py`, lines 164–174**

Add `limit` / `offset` query params; forward them to the DB helper; wrap the result with `total`.

```python
# Current (line 164)
@router.get("")
async def list_libraries(
    auth: AuthContext = Depends(get_auth_context),
):
    return {
        "libraries": _db.get_accessible_libraries(
            user_id=auth.user.get("id"),
            organization_id=auth.organization.get("id"),
        )
    }

# Proposed
@router.get("")
async def list_libraries(
    auth: AuthContext = Depends(get_auth_context),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = _db.get_accessible_libraries(
        user_id=auth.user.get("id"),
        organization_id=auth.organization.get("id"),
        limit=limit,
        offset=offset,
    )
    return {"libraries": items, "total": total}
```

**`backend/creator_interface/knowledge_store_router.py`, lines 225–233**

Same pattern.

```python
# Current (line 225)
@router.get("")
async def list_knowledge_stores(auth: AuthContext = Depends(get_auth_context)):
    return {
        "knowledge_stores": _db.get_accessible_knowledge_stores(
            user_id=auth.user.get("id"),
            organization_id=auth.organization.get("id"),
        )
    }

# Proposed
@router.get("")
async def list_knowledge_stores(
    auth: AuthContext = Depends(get_auth_context),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = _db.get_accessible_knowledge_stores(
        user_id=auth.user.get("id"),
        organization_id=auth.organization.get("id"),
        limit=limit,
        offset=offset,
    )
    return {"knowledge_stores": items, "total": total}
```

---

### Backend — database layer

**`backend/lamb/database_manager.py`, line 7333** — `get_accessible_libraries`

```python
# Current signature
def get_accessible_libraries(self, user_id: int, organization_id: int) -> List[Dict[str, Any]]:

# Proposed
def get_accessible_libraries(
    self, user_id: int, organization_id: int,
    limit: int = 50, offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
```

Add a `COUNT(*)` query before the paginated `SELECT`, then append `LIMIT ? OFFSET ?` to the
existing query. Return `(rows, total_count)`.

**`backend/lamb/database_manager.py`, line 7806** — `get_accessible_knowledge_stores`

```python
# Current signature
def get_accessible_knowledge_stores(self, user_id: int, organization_id: int) -> List[Dict[str, Any]]:

# Proposed
def get_accessible_knowledge_stores(
    self, user_id: int, organization_id: int,
    limit: int = 50, offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
```

Same pattern: count query + `LIMIT ? OFFSET ?` on the existing SQL, return `(rows, total_count)`.

---

### Existing precedent to follow

**`backend/creator_interface/assistant_router.py`, line 1052** and
**`backend/lamb/database_manager.py`, line 4975**

The assistants endpoint is the canonical example in this codebase:

```python
# assistant_router.py — response model (line 121)
class AssistantListPaginatedResponse(BaseModel):
    assistants: List[AssistantGetResponse]
    total_count: int

# assistant_router.py — endpoint (line 1052)
async def get_assistants_proxy(
    ...
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    assistants_list, total_count = db_manager.get_assistants_by_owner_paginated(
        owner=owner_email, limit=limit, offset=offset
    )
    return {"assistants": assistants_list, "total_count": total_count}

# database_manager.py — DB helper signature (line 4975)
def get_assistants_by_owner_paginated(
    self, owner: str, limit: int, offset: int
) -> Tuple[List[Dict[str, Any]], int]:
```

Mirror this pattern exactly. Note: assistants use `total_count`; for consistency with upstream
services (which use `total`) prefer `total` in the new endpoints — pick one and document it.

---

### Frontend — services

**`frontend/svelte-app/src/lib/services/libraryService.js`, line 98**

```js
// Current
export async function getLibraries() {
    const url = getApiUrl('/libraries');
    const response = await axios.get(url, { headers: authHeaders() });
    return response.data?.libraries ?? [];
}

// Proposed (page-aware variant; keep the 0-arg form for callers that don't paginate yet)
export async function getLibraries({ limit = 50, offset = 0 } = {}) {
    const url = getApiUrl('/libraries');
    const response = await axios.get(url, { headers: authHeaders(), params: { limit, offset } });
    return response.data;   // { libraries: [...], total: N }
}
```

**`frontend/svelte-app/src/lib/services/knowledgeStoreService.js`, line 107**

```js
// Current
export async function getKnowledgeStores() {
    const url = getApiUrl('/knowledge-stores');
    const response = await axios.get(url, { headers: authHeaders() });
    return response.data?.knowledge_stores ?? [];
}

// Proposed
export async function getKnowledgeStores({ limit = 50, offset = 0 } = {}) {
    const url = getApiUrl('/knowledge-stores');
    const response = await axios.get(url, { headers: authHeaders(), params: { limit, offset } });
    return response.data;   // { knowledge_stores: [...], total: N }
}
```

---

### Frontend — list components

These components destructure the service return value directly — they must be updated when the
service signature changes above.

| Component | Path | Current usage |
|-----------|------|---------------|
| Libraries list | `frontend/svelte-app/src/lib/components/libraries/LibrariesList.svelte` | `libraries = await getLibraries()` (line 64) |
| KS list | `frontend/svelte-app/src/lib/components/knowledgeStores/KnowledgeStoresList.svelte` | `stores = await getKnowledgeStores()` (line 68) |
| Add-content modal | `frontend/svelte-app/src/lib/components/knowledgeStores/AddContentToKSModal.svelte` | `libraries = await getLibraries()` (line 41) |
| Create-KS wizard step 0 | `frontend/svelte-app/src/lib/components/knowledge/wizard/Step0_LibraryPath.svelte` | `libraries = await getLibraries()` (line 61) |
| Create-KS wizard step 4 | `frontend/svelte-app/src/lib/components/knowledge/wizard/Step4_KSPath.svelte` | `stores = await getKnowledgeStores()` (line 50) |

For each, change the destructuring from `result` to `result.libraries` / `result.knowledge_stores`
and add a `total` state variable + pagination controls (next/prev or a page-size selector).

---

### CLI consumers

**`lamb-cli/src/lamb_cli/commands/library.py`, line 149** — `list_libraries`

```python
# Current (line 155)
resp = client.get("/creator/libraries")
libraries = resp.get("libraries", []) if isinstance(resp, dict) else resp

# Proposed — no pagination flags needed initially; just tolerate the new shape
libraries = resp.get("libraries", [])
# optionally add --limit / --offset options to typer.command if scripting use-cases need it
```

**`lamb-cli/src/lamb_cli/commands/knowledge_store.py`, line 155** — `list_knowledge_stores`

```python
# Current (line 161)
resp = client.get("/creator/knowledge-stores")
items = resp.get("knowledge_stores", []) if isinstance(resp, dict) else resp

# Proposed — same: tolerate new shape, optionally expose --limit/--offset
items = resp.get("knowledge_stores", [])
```

The `isinstance(resp, dict)` guard already present means the CLI won't crash on the new envelope,
but the `total` field will be silently ignored. No breaking change if `libraries` / `knowledge_stores`
keys are preserved.

---

### Tests to update

**`backend/tests/test_creator_libraries_integration.py`, line 92** — `test_list_libraries_returns_owned_and_shared`

- Update the mock: `lib_db.get_accessible_libraries.return_value` must become a `(list, int)` tuple.
- Assert `payload["total"]` is present.
- Assert `lib_db.get_accessible_libraries` is called with `limit` and `offset` kwargs.

**`backend/tests/test_creator_knowledge_stores_integration.py`** — no list test exists yet; add one
mirroring the libraries test above.

---

## Response shape change — coordination notes

The change is **additive** (new `total` key) but the service function return type changes from
`list` to `dict` in the JS services, which breaks every caller that does `for lib of getLibraries()`.
All five frontend call sites above must be updated in the same PR.

The CLI guard (`resp.get("libraries", [])`) already handles the dict-envelope correctly, so CLI is
safe as long as the `libraries` / `knowledge_stores` keys are preserved — which they are.

Recommended envelope key name: `total` (matches Library Manager and KB Server upstream). If aligning
with the assistants precedent matters more, use `total_count` — pick one before starting.

---

## Estimated effort

| Area | Estimate |
|------|----------|
| DB helpers (2 functions) | 1–2 h |
| Creator interface routers (2 endpoints) | 1 h |
| Frontend services + 5 call sites | 2–3 h |
| CLI (shape tolerance, optional flags) | 0.5 h |
| Tests (update existing + add KS list test) | 1–2 h |
| **Total** | **~6–8 h** |

---

## Order of operations (suggested)

1. Update `get_accessible_libraries` and `get_accessible_knowledge_stores` in `database_manager.py`
   to return `(rows, total)` — add `LIMIT`/`OFFSET` SQL, keep defaults so existing callers compile.
2. Update the two creator-interface routers to accept `limit`/`offset` and return `total`.
3. Update `backend/tests/` — fix the libraries integration test mock; add a KS list test.
4. Update the two JS services (`libraryService.js`, `knowledgeStoreService.js`).
5. Update all five frontend call sites (list components + wizard steps) in the same commit.
6. Verify CLI still works (no code change required, but run `lamb library list` and `lamb ks list`
   against a dev stack).
