# LAMB Assistant Versioning

**Status:** Research & Design
**Date:** 2026-03-27
**Version:** 0.1 (Draft)

> **Scope note:** This is an independent subproject. It adds version tracking to assistants regardless of how they are created (traditional form, AAC, or API). The [Agent-Assisted Creator](./lamb-agent-assisted-creator.md) can integrate with versioning once available, but does not depend on it.

---

## 1. Problem

Today, when an assistant is updated, the previous state is lost. There is no way to:

- See what an assistant looked like last week
- Know which configuration was active when a specific student conversation happened
- Compare two states of an assistant to understand what changed
- Roll back a bad edit
- Audit who changed what and when

This matters for quality assurance, research, regulatory compliance (in educational settings), and basic operational confidence.

---

## 2. Design

### 2.1 Core Model

A **version** is an immutable snapshot of the full assistant configuration at a point in time.

```python
{
    "id": "uuid",
    "assistant_id": 123,
    "version_number": 5,              # Sequential per assistant, auto-incremented
    "source": "manual_save",          # "manual_save" | "aac_agent" | "api" | "revert"
    "source_ref": "aac_session_xyz",  # Optional: reference to what created this version
    "created_by": "user@example.com",
    "created_at": "2026-03-27T...",
    "comment": "",                    # Optional annotation (developer-facing)
    "is_active": true,                # This is the version currently in production

    "snapshot": {
        "name": "Biology Tutor",
        "system_prompt": "You are...",
        "metadata": { ... },          # model, connector, processors, capabilities
        "rag_collections": "kb1,kb2",
        # ... all assistant fields
    }
}
```

**Key rules:**
- Versions are **immutable** — once created, never modified.
- Reverting creates a **new version** (copy-forward), preserving linear history.
- Exactly one version per assistant is marked `is_active` — this is what production completions use.
- Creating a version from the traditional edit form is transparent: save = new version + set active.

### 2.2 Active Version & Production Linking

The `is_active` flag determines which version serves production traffic:

```
Completion request for assistant 123
  → Look up active version for assistant 123
  → Use that version's snapshot for system prompt, metadata, etc.
  → Log the version_id alongside the completion
```

This requires a small change to the completion pipeline: instead of reading the assistant row directly, read the active version's snapshot. Fallback: if no versions exist (legacy assistant), read the assistant row as before.

### 2.3 Version Promotion

"Promoting" a version means setting it as active. This decouples editing from deploying:

- An educator can save a new version (new system prompt) without it going live immediately.
- They can test it (via AAC or manually) and then promote it when satisfied.
- Or they can save-and-promote atomically (same as today's behavior, for simplicity).

The MVP should default to **save-and-promote** (no behavior change for existing users) with an option to save-without-promoting for advanced users.

---

## 3. Database

```sql
CREATE TABLE assistant_versions (
    id TEXT PRIMARY KEY,
    assistant_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    source TEXT NOT NULL,               -- 'manual_save' | 'aac_agent' | 'api' | 'revert'
    source_ref TEXT,                    -- Optional reference (e.g., AAC session ID)
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    comment TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT false,
    snapshot TEXT NOT NULL,             -- JSON: full assistant state
    UNIQUE(assistant_id, version_number)
);

-- Index for fast active-version lookup (completion hot path)
CREATE INDEX idx_versions_active ON assistant_versions(assistant_id, is_active)
    WHERE is_active = true;
```

Migration adds a `current_version_id` column to the `assistants` table for fast lookup (denormalized, updated when active version changes).

---

## 4. API Endpoints

Added to Creator Interface router:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/creator/assistant/{id}/versions` | List version history |
| GET | `/creator/assistant/{id}/versions/{v}` | Get specific version snapshot |
| GET | `/creator/assistant/{id}/versions/{v1}/diff/{v2}` | Diff two versions |
| POST | `/creator/assistant/{id}/versions/{v}/revert` | Create new version from old snapshot |
| POST | `/creator/assistant/{id}/versions/{v}/promote` | Set version as active |

Existing endpoints change:
- `PUT /creator/assistant/update` — now creates a version behind the scenes (save-and-promote by default).

Completion pipeline change:
- Completion log entries include `version_id` field.

---

## 5. Frontend

**Minimal UI addition to existing assistant edit page:**

- "Version History" expandable section or sidebar tab
- Shows list: version number, date, source, comment
- Click to view snapshot / compare with current
- "Revert to this version" action
- "Promote this version" action (if save-without-promote is supported)

No new pages needed — this integrates into the existing assistant detail view.

---

## 6. Implementation Phases

### Phase A: Version Storage
- Database table + migration
- Create version on every assistant save (transparent to user)
- Active version tracking
- List/get version endpoints

### Phase B: Completion Linking
- Modify completion pipeline to read active version
- Log version_id in completion records
- Fallback for unversioned legacy assistants

### Phase C: Version UI
- Version history in assistant edit page
- Diff view
- Revert action

### Phase D: AAC Integration
- AAC agent edits create versions (source="aac_agent", source_ref=session_id)
- Test runs reference version IDs instead of inline snapshots
- Promote action available from AAC UI

### Phase E: Analytics Integration
- Filter chat analytics by version
- Version comparison in analytics ("version 3 vs version 5 engagement")

---

## 7. Integration Points

| Component | Integration |
|-----------|-------------|
| **Assistant CRUD** | `update` creates a version transparently |
| **Completion Pipeline** | Reads active version, logs version_id |
| **AAC** | Agent edits create versions; test runs linked to versions |
| **Chat Analytics** | Filter/group by version |
| **Admin Panel** | Version history visible to org admins |

---

## 8. Open Questions

| # | Question |
|---|----------|
| 1 | **Storage growth.** Full snapshots per version could grow. Compress? Store diffs? (Probably premature — snapshots are small JSON.) |
| 2 | **Version limit per assistant?** Archive old versions after N? |
| 3 | **Save-without-promote in MVP?** Or always save-and-promote for simplicity? |
| 4 | **Should version diffs be computed on-demand or stored?** (On-demand is simpler.) |

---

*Prepared: 2026-03-27*
