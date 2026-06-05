# Team-Based Resource Ownership for LAMB

> **Architectural Proposal** — Issue [#158](https://github.com/Lamb-Project/lamb/issues/158)
>
> **Status:** Draft for discussion
>
> **Date:** 2025-06-05

---

## 1. Executive Summary

LAMB currently enforces **individual ownership** on all resources — assistants, knowledge bases, and libraries. Sharing exists but is strictly read-only. This proposal introduces **team-based ownership**, allowing resources to be collectively owned and managed by a group of users within an organization. The model is inspired by Google Drive shared folders and Nextcloud group folders: a resource belongs to a team, and all team members have equivalent edit capabilities.

### Why This Matters

The current model creates friction in educational environments:

- **Teacher groups designing learning assistants together** cannot co-edit the same assistant
- **Knowledge bases shared with collaborators** are read-only — colleagues cannot contribute documents
- **When a teacher leaves**, their assistants become orphans — no one else can manage them
- **Admins resort to insecure workarounds** like password resets to transfer ownership

Team ownership solves all of these in one architectural change.

---

## 2. Current Architecture (Baseline)

### 2.1 Ownership Model Today

Every resource has an individual owner:

| Resource | Owner field | Type |
|----------|-----------|------|
| Assistant | `assistants.owner` | `TEXT` (email) |
| Knowledge Base | `kb_registry.owner_user_id` | `INTEGER` (user ID) |
| Library | `libraries.owner_user_id` | `INTEGER` (user ID) |
| Rubric | `rubrics.owner_email` | `TEXT` (email) |
| Prompt Template | `prompt_templates.owner_email` | `TEXT` (email) |
| LTI Activity | `lti_activities.owner_email` | `TEXT` (email) |

### 2.2 Sharing Model Today

| Resource | Sharing Mechanism | Granularity | Write Access |
|----------|------------------|-------------|-------------|
| Assistant | `assistant_shares` table (per-user) | Per-user | ❌ Read only |
| Knowledge Base | `is_shared` boolean | Org-wide | ❌ Read only |
| Library | `is_shared` boolean | Org-wide | ❌ Read only |
| Prompt Template | `is_shared` boolean | Org-wide | ❌ Read only |

### 2.3 Existing Organization Roles

The `organization_roles` table already defines a role hierarchy:

```
owner → admin → member
```

The `AuthContext` already resolves `organization_role` and `is_org_admin` per request. Teams can leverage this existing role system.

### 2.4 Permission Check Paths

```
Request → AuthContext.can_access_*() → database_manager.user_can_access_*()
         → returns: "owner" | "shared" | "org_admin" | "none"
         → Permission enforced in router endpoints
```

The key insight: all permission checks funnel through `AuthContext` methods (`can_access_assistant`, `can_access_kb`, `can_access_library`). Adding team-level access means modifying only these central methods — not every router endpoint.

---

## 3. Proposed Architecture: Teams

### 3.1 Core Concept

A **Team** is a named group of users within an organization that can collectively own and manage resources. When a resource is assigned to a team:

- All team members have **full edit access** (equivalent to today's "owner" level)
- The team persists even when individual members join/leave
- Resources survive member departures — no orphaned assistants

### 3.2 New Database Schema

```sql
-- ── Teams ──────────────────────────────────────────────
CREATE TABLE teams (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    description     TEXT,
    organization_id INTEGER NOT NULL,
    created_by      INTEGER NOT NULL,          -- Creator user ID
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by)      REFERENCES Creator_users(id) ON DELETE SET NULL
);

CREATE INDEX idx_teams_org ON teams(organization_id);

-- ── Team Members ───────────────────────────────────────
CREATE TABLE team_members (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    role       TEXT    NOT NULL DEFAULT 'member'
                       CHECK(role IN ('owner', 'admin', 'member')),
    joined_at  INTEGER NOT NULL,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    UNIQUE(team_id, user_id)
);

CREATE INDEX idx_team_members_team ON team_members(team_id);
CREATE INDEX idx_team_members_user ON team_members(user_id);

-- ── Resource Ownership Extension ───────────────────────
-- Each resource table gains a nullable team_id column.
-- When team_id is set, the individual owner fields become optional
-- (but preserved for audit/backward compatibility).

-- Example for assistants:
ALTER TABLE assistants ADD COLUMN team_id INTEGER
    REFERENCES teams(id) ON DELETE SET NULL;
CREATE INDEX idx_assistants_team ON assistants(team_id);

-- Similarly for: kb_registry, libraries, rubrics,
-- prompt_templates, lti_activities
```

### 3.3 Ownership Resolution Logic

The `AuthContext.can_access_assistant()` method evolves:

```python
def can_access_assistant(self, assistant_id: int) -> str:
    assistant = _db.get_assistant_by_id_with_publication(assistant_id)
    if not assistant:
        return "none"

    # 1. Individual owner
    if assistant.get("owner") == self.user.get("email"):
        return "owner"

    # 2. System admin
    if self.is_system_admin:
        return "org_admin"

    # 3. Org admin for the resource's organization
    if self.is_org_admin and assistant.get("organization_id") == self.organization.get("id"):
        return "org_admin"

    # 4. NEW: Team membership with resource ownership
    team_id = assistant.get("team_id")
    if team_id and _db.is_user_in_team(self.user.get("id"), team_id):
        return "owner"  # Team members get full owner access

    # 5. Shared with user (existing model, kept for backward compat)
    user_id = self.user.get("id")
    if user_id and _db.is_assistant_shared_with_user(assistant_id, user_id):
        return "shared"

    # 6. Same organization (usage/chat access)
    if assistant.get("organization_id") == self.organization.get("id"):
        return "shared"

    return "none"
```

Key design choice: team membership returns `"owner"` — team members get the same access level as the original creator. This is the simplest model and matches the Google Drive "Shared Folder" paradigm.

### 3.4 Team Roles Within a Resource Context

Team members have internal roles, but for resource access these are flattened:

| Team Member Role | Access to Team-Owned Resources |
|-----------------|-------------------------------|
| `owner` | Full edit + manage team + manage sharing |
| `admin` | Full edit + manage team (but can't delete the team) |
| `member` | Full edit |

The distinction between team roles matters only for team management operations (adding/removing members, changing settings), not for the resources themselves. All team members can create, edit, and delete resources owned by the team.

---

## 4. Advantages of Team-Based Ownership

### 4.1 Solves All Reported Pain Points at Once

| Pain Point | How Teams Solve It |
|-----------|-------------------|
| **KB collaborators can't add files** | Team members are owners — full write access |
| **Shared assistants are read-only** | Team members are owners — full edit access |
| **No admin transfer** | Team owns the resource — admin can manage team membership |
| **Teacher leaves, assistant orphaned** | Assistant belongs to the team, not the individual |
| **Password reset workaround** | Org admin adds themselves to the team instead |
| **Multi-teacher course assistants** | Single team owns all course assistants/KBs/library |

### 4.2 Aligns with Educational Use Cases

Educational environments naturally map to teams:

- **Department → Team**: "Computer Science Department" team owns course assistants for CS101, CS201
- **Course instructors → Team**: "CS101 Teaching Team" jointly manages the CS101 assistant and KB
- **Research group → Team**: "AI Ethics Research" team owns experiment assistants and document KBs
- **Administrative → Team**: "Admissions Board" team owns evaluation rubrics

### 4.3 Consistent Across All Resources

With individual ownership + per-sharing, each resource type needs its own permission model (assistants: per-user share table, KBs: org-wide boolean, libraries: org-wide boolean). Teams unify this: every resource type gets a `team_id` column and uses the same resolution logic.

### 4.4 Gracious Degradation

If teams are not used (no `team_id` set), the system behaves identically to today:

```python
team_id = assistant.get("team_id")
if team_id and _db.is_user_in_team(user_id, team_id):
    return "owner"
# Falls through to existing logic
```

Zero impact on organizations that don't use teams.

---

## 5. Architectural Impact

### 5.1 Database Changes

| Change | Impact |
|--------|--------|
| New `teams` table | ✅ Additive only |
| New `team_members` table | ✅ Additive only |
| `team_id` column on 6 resource tables | ⚠️ Schema migration, but nullable and default NULL |
| New indexes | ✅ Additive only |
| Existing data | ✅ No changes — all `team_id` values default to NULL |

### 5.2 API Changes

| Component | New Endpoints | Modified Endpoints |
|-----------|--------------|-------------------|
| **Teams management** | `POST /creator/teams` — create team | — |
| | `GET /creator/teams` — list org teams | |
| | `GET /creator/teams/{id}` — team details | |
| | `PUT /creator/teams/{id}` — update team | |
| | `DELETE /creator/teams/{id}` — delete team | |
| | `POST /creator/teams/{id}/members` — add member | |
| | `DELETE /creator/teams/{id}/members/{user_id}` — remove member | |
| | `PUT /creator/teams/{id}/members/{user_id}` — change role | |
| **Resource endpoints** | — | Each create endpoint adds optional `team_id` |
| | — | Each update endpoint adds optional `team_id` transfer |
| **Auth resolution** | — | `AuthContext.can_access_*()` methods only |

### 5.3 Frontend Changes

| Area | New Components | Modified Components |
|------|---------------|-------------------|
| **Teams management** | `TeamsList.svelte` — list teams in org | — |
| | `TeamDetail.svelte` — team settings + members | |
| | `TeamMemberSelector.svelte` — add/remove members | |
| | `CreateTeamModal.svelte` | |
| **Resource creation** | — | Add "Owner" selector: "Me" or team dropdown |
| **Assistant detail** | — | Show team name in header if team-owned |
| **KB detail** | — | Show team name, hide share toggle if team-owned |
| **Org admin** | New "Teams" tab | — |

### 5.4 Permissions Resolution Changes

Only 3 files need changes in the core auth path:

| File | What Changes |
|------|-------------|
| `backend/lamb/database_manager.py` | `is_user_in_team(user_id, team_id)` — new method |
| | `get_user_teams(user_id)` — new method |
| | `get_team_resources(team_id)` — new method |
| `backend/lamb/auth_context.py` | `can_access_assistant()` — add team check (step 4) |
| | `can_access_kb()` — add team check |
| | `can_access_library()` — add team check |

All router endpoints downstream inherit the new behavior automatically — they already gate on `can_access_*()` / `require_*_access()` return values.

### 5.5 No Changes Required

| Component | Why Not Needed |
|-----------|---------------|
| `lamb-kb-server-stable` | LAMB continues proxying with the acting user's ID; the KB server doesn't need to know about teams |
| Open WebUI | Chat access continues via assistant groups; team membership doesn't change the OWI group | 
| `library-manager` | LAMB proxies with user context; library manager doesn't need team awareness |
| `lamb-cli` | CLI commands use the same API; teams show up as accessible resources |
| RAG pipeline | Uses assistant owner email for org config resolution; works unchanged for team-owned assistants |

---

## 6. Implementation Phases

### Phase 0: Prerequisites (1-2 days)

**Fix existing security gaps before adding new features:**

- [ ] Add `require_assistant_access(level="owner_or_admin")` to `update_assistant_proxy` (currently missing auth check entirely — line 1208 of `assistant_router.py`)
- [ ] Add `require_assistant_access` to file upload endpoints on assistants
- [ ] Audit all write endpoints across the codebase for missing auth checks

### Phase 1: Teams Core (3-5 days)

**Database, API, and auth resolution — no frontend changes yet.**

1. **Database migration** — `database_manager.py`
   - Create `teams` and `team_members` tables with indexes
   - Add nullable `team_id` column to: `assistants`, `kb_registry`, `libraries`, `rubrics`, `prompt_templates`, `lti_activities`
   - All columns default to `NULL` — existing resources are unaffected

2. **Backend service layer** — new `backend/lamb/services/team_service.py`
   - CRUD for teams (scoped to organization)
   - Member management (add, remove, change role)
   - Team resource listing

3. **Router** — new `backend/creator_interface/team_router.py`
   - Full REST endpoints for teams and members
   - Authorization: org admin or team owner/admin for management ops

4. **AuthContext integration** — `auth_context.py`
   - Add team membership check to `can_access_assistant()`, `can_access_kb()`, `can_access_library()`
   - Team members resolve as `"owner"` access level

5. **Resource creation** — modify create endpoints
   - `create_assistant`: accept optional `team_id` (mutually exclusive with per-user sharing)
   - `create_knowledge_base`: accept optional `team_id`
   - `create_library`: accept optional `team_id`

6. **Tests**
   - Unit tests for team CRUD and member management
   - Unit tests for ownership resolution with team resources
   - Integration tests: create team → create resource → member edits → non-member denied

### Phase 2: Frontend Teams UI (3-4 days)

1. **Teams management page** — new route `/teams`
   - List teams in the organization
   - Create/edit/delete teams (org admin / team owner)
   - Add/remove members with role selector

2. **Resource creation UI updates**
   - Assistant creation: "Owner" dropdown with "Me" + team list
   - KB creation: "Owner" dropdown with "Me" + team list
   - Library creation: "Owner" dropdown with "Me" + team list

3. **Resource detail UI updates**
   - Assistant detail: show team name in header when team-owned; hide individual share UI
   - KB detail: show team name; replace share toggle with team info
   - All detail views: replace "Edit (Owner Only)" with "Edit" for team members

4. **Org admin integration**
   - "Teams" tab in org admin panel
   - View all teams, their resources, and member counts
   - Ability to add/remove team members as org admin

### Phase 3: Migration & Polish (2-3 days)

1. **Migration tooling**
   - Admin endpoint to transfer individual-owned resource to a team
   - Admin endpoint to transfer team-owned resource back to individual
   - Batch migration script for bulk operations

2. **UI polish**
   - Team avatars/icons (auto-generated from initials)
   - Inline member avatars in resource headers ("Owned by Team CS101 — 5 members")
   - Activity feed showing team context: "Alice (CS101 Team) edited Assistant X"

3. **Documentation**
   - Update CLAUDE.md with team architecture
   - User-facing documentation for team management
   - API documentation for new endpoints

### Phase 4: Coexistence & Transition (1-2 days)

1. **Coexistence rules**
   - A resource with `team_id` set ignores the `is_shared` flag and per-user shares
   - A resource without `team_id` works exactly as today
   - The `owner` field remains populated on all resources for audit trail

2. **Deprecation path**
   - The existing sharing model is NOT removed — it coexists indefinitely
   - Teams are the preferred model for collaborative work
   - Individual sharing remains for one-off read-access sharing

---

## 7. Risk Assessment

### 7.1 Architectural Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Concurrent edits by team members** | Medium | Last-write-wins (current behavior). Acceptable for MVP. Future: optimistic locking or edit notifications |
| **Team cascading deletes** | High | `ON DELETE CASCADE` on `team_members` but `ON DELETE SET NULL` on resource `team_id`. Deleting a team DOES NOT delete resources — it converts them to individual ownership |
| **KB server unaware of teams** | Low | LAMB proxies file operations under the acting user's ID. The KB server only sees "a user doing an operation" — which is correct |
| **OWI group sync complexity** | Medium | When a team owns an assistant, the OWI group must contain ALL team members. The group sync logic in `AssistantSharingService._sync_assistant_to_owi_group()` must include team members |
| **Performance of team membership check** | Low | `is_user_in_team()` is a simple indexed lookup. Cached in `AuthContext` for the request duration |

### 7.2 UX Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Confusion: teams vs org roles** | Medium | Clear labeling: "Organization Admin" ≠ "Team Owner". Different UI sections |
| **Accidental team deletion** | Medium | Confirmation dialog with resource count warning |
| **Self-removal from last team** | Low | Prevent the last team member from removing themselves |
| **Migration friction** | Low | Teams are additive — no forced migration. Users adopt voluntarily |

### 7.3 Security Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Privilege escalation via team join** | High | Only team owners/admins and org admins can add members. Adding a member is audited |
| **Orphaned resources after org deletion** | Medium | Cascade from `organizations` → `teams` → `team_members`; resources get `team_id = NULL` |
| **Cross-org team access** | High | `team_members` validated against `organization_id` of the team. A user outside the org cannot be added |

---

---

## 8. Open Questions

1. **Should teams have configurable resource limits?** (e.g., max 10 assistants per team)
2. **Should team roles affect resource access?** (e.g., only team owners can delete resources — currently all members are equal)
3. **Should teams span multiple organizations?** (currently scoped to single org)
4. **What happens to existing per-user shares when a resource is assigned to a team?** (proposal: they become inactive; team membership replaces sharing)
5. **Should team membership automatically grant access to all org resources or only team-owned ones?** (current proposal: only team-owned resources)
