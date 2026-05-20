# Documentation Migration Plan

> Splitting documentation between the **main (source code) repository** and a **private repository**.

---

## STAY in Main Repo (source-coupled)

### Root-level

| File | Reason |
|------|--------|
| `CLAUDE.md` | AI agent instructions for working with the codebase |
| `README.md` | Project README — essential for any repo |
| `CONTRIBUTING.md` | How to contribute to the code |
| `LICENSE` | Legal requirement |
| `deployment.md` | Production deployment tied to docker-compose files |
| `PARENT_CHILD_CHUNKING.md` | Feature README for a code-level feature |

### `Documentation/`

| File | Reason |
|------|--------|
| `DOCUMENTATION_INDEX.md` | Navigation hub for dev docs |
| `README.md` | Docs landing page |
| `lamb_architecture.md` | Full architecture reference (v3.0) |
| `lamb_architecture_v2.md` | Main architecture guide (v2.6) |
| `lamb_architecture_small.md` | Condensed architecture (v2.9) |
| `lamb_architecture_nano.md` | Minimal context for LLMs |
| `lamb_cli_manual.md` | Documents `lamb-cli/` code |
| `lamb_aac_cli_manual.md` | Documents AAC feature in `lamb-cli/` |
| `deployment.md` | Docker deployment guide |
| `deployLocal.md` | Local Docker deployment guide |
| `deployNext.md` | Hetzner autonomous deployment guide |
| `deployment.apache.md` | Apache reverse proxy config |
| `deployment.nginx.md` | Nginx reverse proxy config |
| `installationguide.md` | Step-by-step installation |
| `langsmith_tracing.md` | LangSmith integration with this codebase |
| `new_lamb_auth_tldr.md` | AuthContext architecture doc |

### `Documentation/` subdirectories

| Directory | Reason |
|-----------|--------|
| `ER-diagrams/` | Database schema diagrams tied to actual schema |
| `small-context/` | Compact LLM context docs for AI coding agents |

### `lamb-cli/Documentation/`

| File | Reason |
|------|--------|
| `lamb_cli_architecture.md` | CLI architecture docs |
| `tutorial.md` | CLI usage tutorial |

---

## MOVE to Private Repo (business/planning/historical)

### Root-level

| File | Reason |
|------|--------|
| `IMPLEMENTATION_SUMMARY.md` | Completed work report (parent-child chunking) |
| `aac_test_log.md` | Temporary test log |

### `Documentation/`

| File | Reason |
|------|--------|
| `prd.md` | Product Requirements Document (business doc) |
| `about_es.md` | Marketing/introductory content (Spanish) |
| `about_es copy.md` | Duplicate of `about_es.md` |
| `chat_analytics_project.md` | Planning doc — Status: Planning |
| `small_fast_model_implementation.md` | Planning doc — Status: Planning |
| `kb_server_embeddings_setup_proposal.md` | Design proposal — Status: Draft |
| `kb_server_plugin_architecture_v2.md` | Design proposal — Status: Draft |
| `COMPLETE_IMPLEMENTATION_SUMMARY.md` | Completed work report (parent-child chunking) |
| `RELEASE_NOTES_OCT2025_JAN2026_USERS.md` | End-user release notes |
| `fix-hierarchical-rag-ui.md` | Completed bug fix report |
| `hierarchical-rag-ui-fix-visual-guide.md` | Bug fix visualization guide |
| `DELETED_ASSISTANT_SHARING_ROUTER.md` | Historical recovery/analysis doc |
| `multimodality.md` | Implemented multimodal feature docs |
| `i18n.md` | Tracks i18n gaps in the frontend code |
| `logging_offenders.md` | Tracks code quality / logging standard violations |
| `svelte-refactoring.md` | Ongoing frontend refactoring tracker |
| `RELEASE_NOTES_OCT2025_JAN2026_DEVELOPERS.md` | Developer-facing release notes |
| `access_control_roles.md` | Implemented RBAC design |
| `parent-child-chunking.md` | Implemented parent-child chunking feature |
| `lti_landscape.md` | LTI integration (technical deep-dive coupled to code) |
| `352-resilience-fixes-repro.md` | Repro/verification guide for frontend resilience fixes |
| `frontend-parent-child-integration.md` | Feature usage guide for parent-child chunking |
| `using-hierarchical-rag.md` | User guide for hierarchical RAG feature |

### `Documentation/` subdirectories

| Directory | Contents | Reason |
|-----------|----------|--------|
| `attic/` | ~20 files — historical, legacy, archived docs | All archived/obsolete |
| `features/` | `assistant_sharing.md`, `README.md` | Feature specs & proposals |
| `fixes/` | `owi_user_race_condition_fix.md` | Completed bug fix report |
| `projects/` | ~11 files — AAC backlog, evaluaitor project, PhD research, etc. | Project plans, roadmaps, research |
| `slop-docs/` | ~100+ auto-generated docs | Auto-generated temporary docs |
| `training/` | ~8 files — stakeholder summaries, teaching strategies (multi-lang) | Training/stakeholder materials |

### `lamb-cli/Documentation/`

| File | Reason |
|------|--------|
| `prd.md` | Product requirements for CLI |

---

## Migration Steps

1. Create the private repository
2. Copy all "MOVE" files/directories to the private repo, preserving structure
3. Delete the "MOVE" files/directories from the main repo
4. Update `DOCUMENTATION_INDEX.md` to remove references to moved docs
5. Update `CLAUDE.md` if it references any moved docs
6. Commit both repos
