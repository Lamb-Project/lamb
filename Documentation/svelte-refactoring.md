# LAMB Frontend Refactoring Plan

**Document Version:** 1.2  
**Date:** January 18, 2026  
**Status:** Phase 1 Complete - Phase 2 In Progress

### Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.2 | 2026-01-18 | Completed Phase 1. Removed orphaned `AssistantAccessManager` feature (component, page, service functions). Investigation revealed it was superseded by `AssistantSharingModal`. |
| 1.1 | 2026-01-18 | Initial analysis complete, Phase 1 quick wins implemented |

---

## ⚠️ MANDATORY REFACTORING METHODOLOGY

> **CRITICAL**: The coding agent MUST follow this methodology for EVERY refactoring task.
> No code may be modified or removed without completing all preparation steps first.

### Overview

This methodology ensures safe, verified refactoring by requiring comprehensive testing BEFORE and AFTER any code changes. The user maintains control at key checkpoints.

```
┌─────────────────────────────────────────────────────────────────┐
│  REFACTORING WORKFLOW                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. PREPARATION (before touching ANY code)                      │
│     ├─ 1.0 Choose limited scope                                 │
│     ├─ 1.1 Identify affected UI areas                           │
│     ├─ 1.2 Agent tests current functionality (browser)          │
│     ├─ 1.3 User confirms it works ← USER CHECKPOINT             │
│     ├─ 1.4 Write Playwright test                                │
│     └─ 1.5 User runs Playwright test ← USER CHECKPOINT          │
│                                                                 │
│  2. IMPLEMENTATION                                              │
│     └─ Do the actual fix/refactoring                            │
│                                                                 │
│  3. VERIFICATION                                                │
│     ├─ 3.1 Agent tests with browser                             │
│     ├─ 3.2 User tests manually ← USER CHECKPOINT                │
│     └─ 3.3 User runs Playwright tests ← USER CHECKPOINT         │
│                                                                 │
│  4. ITERATE                                                     │
│     └─ Only proceed to next item when ALL tests pass            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Step-by-Step Instructions

#### Phase 1: PREPARATION (Before Touching ANY Code)

##### 1.0 Choose Limited Scope
- Select ONE specific, well-defined refactoring task
- Keep the scope small and manageable
- Document exactly what will be changed

##### 1.1 Identify Affected UI Areas
- List all routes/pages that use the code being modified
- List all components that depend on it
- Document the user-facing functionality

##### 1.2 Agent Tests Current Functionality
- Use `cursor-ide-browser` MCP tool to navigate to affected areas
- **URL for testing**: `http://localhost:5173` (development frontend)
- Take screenshots to document current behavior
- Verify all functionality works BEFORE any changes
- Document the expected behavior

> **Note**: The agent uses Cursor's internal browser (`cursor-ide-browser` MCP) 
> to test the application at `http://localhost:5173`. This provides visual 
> verification of functionality before and after changes.

##### 1.3 User Confirmation Checkpoint ⏸️
```
┌────────────────────────────────────────────────────────────┐
│ 🛑 STOP - USER CHECKPOINT                                  │
│                                                            │
│ Agent must ask the user:                                   │
│ "I have tested [feature] in the browser. Please confirm   │
│  that [specific functionality] is working correctly       │
│  before I proceed."                                        │
│                                                            │
│ DO NOT PROCEED until user confirms.                        │
└────────────────────────────────────────────────────────────┘
```

##### 1.4 Write Playwright Test
- Write a Playwright test that covers the functionality being modified
- Test should verify the CURRENT working behavior
- Follow patterns from existing tests in `/testing/playwright/tests/`
- Place new test file appropriately

##### 1.5 User Runs Playwright Test ⏸️
```
┌────────────────────────────────────────────────────────────┐
│ 🛑 STOP - USER CHECKPOINT                                  │
│                                                            │
│ Agent must instruct the user:                              │
│ "Please run the Playwright test to verify it passes:      │
│                                                            │
│   cd testing/playwright                                    │
│   npx playwright test tests/[test_file].spec.js           │
│                                                            │
│ Let me know when the test passes."                         │
│                                                            │
│ DO NOT PROCEED until user confirms test passes.            │
└────────────────────────────────────────────────────────────┘
```

#### Phase 2: IMPLEMENTATION

##### 2.0 Make the Changes
- Only NOW may the agent modify/remove code
- Make changes incrementally
- Keep changes focused on the defined scope
- Do not introduce unrelated changes

#### Phase 3: VERIFICATION

##### 3.1 Agent Tests with Browser
- Use `cursor-ide-browser` MCP tool to test the modified functionality
- **URL for testing**: `http://localhost:5173` (development frontend)
- Take screenshots to document the new behavior
- Verify all functionality still works as expected
- Compare with pre-change screenshots if helpful

##### 3.2 User Manual Testing ⏸️
```
┌────────────────────────────────────────────────────────────┐
│ 🛑 STOP - USER CHECKPOINT                                  │
│                                                            │
│ Agent must ask the user:                                   │
│ "I have completed the changes and tested them. Please     │
│  manually verify that [specific functionality] still      │
│  works correctly in your browser."                         │
│                                                            │
│ DO NOT PROCEED until user confirms.                        │
└────────────────────────────────────────────────────────────┘
```

##### 3.3 User Runs Playwright Tests ⏸️
```
┌────────────────────────────────────────────────────────────┐
│ 🛑 STOP - USER CHECKPOINT                                  │
│                                                            │
│ Agent must instruct the user:                              │
│ "Please run ALL Playwright tests to verify nothing broke: │
│                                                            │
│   cd testing/playwright                                    │
│   npm test                                                 │
│                                                            │
│ Let me know the results."                                  │
│                                                            │
│ DO NOT PROCEED until all tests pass.                       │
└────────────────────────────────────────────────────────────┘
```

#### Phase 4: ITERATE

- Only when ALL tests pass (Playwright + manual) may the agent proceed
- If any test fails:
  - Fix the issue
  - Return to Phase 3 verification
- Select the next refactoring task and return to Phase 1

### Development Environment Setup

The application runs in Docker containers. For testing and refactoring, ensure the following services are running:

#### Docker Services (from `docker-compose.yaml`)

| Service | Port | Description |
|---------|------|-------------|
| `frontend` | **5173** | Development frontend (Vite dev server with hot reload) |
| `backend` | **9099** | LAMB backend API (FastAPI) |
| `openwebui` | 8080 | Open WebUI service |
| `kb` | 9090 | Knowledge Base server |

#### Starting the Development Environment

```bash
# From repository root
docker-compose up -d

# Or start specific services
docker-compose up -d frontend backend kb
```

#### URLs for Testing

| Purpose | URL |
|---------|-----|
| **Frontend (dev)** | http://localhost:5173 |
| **Backend API** | http://localhost:9099 |
| **Playwright tests** | Uses http://localhost:9099 by default |

#### Admin Credentials (Development)

The Playwright tests use these default credentials (from `global-setup.js`):

```
Email:    admin@owi.com
Password: admin
```

These can be overridden with environment variables:
- `LOGIN_EMAIL` - Admin email
- `LOGIN_PASSWORD` - Admin password

The actual credentials for your environment are in `backend/.env`.

#### Playwright Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:9099/` | Base URL for tests |
| `LOGIN_EMAIL` | `admin@owi.com` | Admin login email |
| `LOGIN_PASSWORD` | `admin` | Admin login password |
| `FORCE_RELOGIN` | (unset) | Set to force re-authentication |
| `CI` | (unset) | Set in CI environments for headless mode |

### Testing Commands Reference

```bash
# Navigate to test directory
cd testing/playwright

# Install dependencies (first time only)
npm install
npx playwright install
npx playwright install-deps

# Run all tests
npm test

# Run specific test file
npx playwright test tests/[filename].spec.js

# Run tests with UI (interactive mode)
npm run test:ui

# View HTML report after test run
npm run report

# Force re-login (clear cached auth state)
FORCE_RELOGIN=1 npm test
```

#### Verifying the Environment

Before starting any refactoring work, verify the environment is working:

```bash
# 1. Check Docker containers are running
docker-compose ps

# 2. Check frontend is accessible
curl -I http://localhost:5173

# 3. Check backend is accessible  
curl -I http://localhost:9099

# 4. Run Playwright tests to verify everything works
cd testing/playwright
npm test
```

### Example Refactoring Session

```
Agent: "I will now refactor the AssistantsList component to remove 
       the commented PublishModal code.
       
       1.1 AFFECTED UI: /assistants page, assistant list view
       
       1.2 Let me test the current functionality..."
       [Agent uses browser to navigate and test]
       [Agent takes screenshots]
       
Agent: "🛑 USER CHECKPOINT: I have verified the assistants list 
       displays correctly with View, Export, and Delete buttons.
       Please confirm this is working correctly before I proceed."

User:  "Confirmed, it works."

Agent: "1.4 I will now write a Playwright test for this functionality..."
       [Agent writes test]
       
Agent: "🛑 USER CHECKPOINT: Please run the test:
       cd testing/playwright
       npx playwright test tests/assistants_list.spec.js"

User:  "Test passed."

Agent: "2.0 Now implementing the change..."
       [Agent removes commented code]
       
Agent: "3.1 Testing the changes..."
       [Agent uses browser to verify]
       
Agent: "🛑 USER CHECKPOINT: Changes complete. Please manually verify
       the assistants list still works correctly."

User:  "Looks good."

Agent: "🛑 USER CHECKPOINT: Please run all Playwright tests:
       cd testing/playwright && npm test"

User:  "All tests passed."

Agent: "✅ Refactoring complete. Ready to proceed to next task."
```

---

## Executive Summary

This document outlines a comprehensive refactoring plan for the LAMB frontend (`/frontend/svelte-app/`). The analysis identified several categories of issues including unused code, oversized components, inconsistent patterns, and opportunities for improved component architecture. The plan includes specific recommendations, new component proposals, and testing strategies using Playwright.

---

## Table of Contents

1. [Analysis Checklist](#1-analysis-checklist)
2. [Codebase Architecture Overview](#2-codebase-architecture-overview)
3. [Critical Issues - Offenders](#3-critical-issues---offenders)
4. [Unused Code Inventory](#4-unused-code-inventory)
5. [Spaghetti Code Hotspots](#5-spaghetti-code-hotspots)
6. [Proposed Component Extractions](#6-proposed-component-extractions)
7. [New Components to Develop](#7-new-components-to-develop)
8. [Code Quality Improvements](#8-code-quality-improvements)
9. [Testing Strategy](#9-testing-strategy)
10. [Implementation Phases](#10-implementation-phases)
11. [Risk Assessment](#11-risk-assessment)

---

## 1. Analysis Checklist

### Routes Analyzed ✅

| File | Status | Size | Issues |
|------|--------|------|--------|
| `src/routes/+layout.svelte` | ✅ Analyzed | Small | Minor - commented TODOs |
| `src/routes/+layout.js` | ✅ Analyzed | Small | Clean |
| `src/routes/+page.svelte` | ✅ Analyzed | Medium | Clean |
| `src/routes/admin/+page.svelte` | ✅ Analyzed | **~181KB** | **CRITICAL - needs splitting** |
| `src/routes/assistants/+page.svelte` | ✅ Analyzed | Large | Medium complexity |
| `src/routes/chat/+page.svelte` | ❌ **REMOVED** | — | Was: Hardcoded API_KEY, security risk, orphaned page |
| `src/routes/evaluaitor/+page.svelte` | ✅ Analyzed | Medium | Clean |
| `src/routes/evaluaitor/[rubricId]/+page.svelte` | ✅ Analyzed | Small | Clean |
| `src/routes/knowledgebases/+page.svelte` | ✅ Analyzed | Medium | Clean |
| `src/routes/org-admin/+page.svelte` | ✅ Analyzed | **Large** | **Needs splitting** |
| `src/routes/org-admin/assistants/+page.svelte` | ❌ **REMOVED** | — | Redundant page (functionality in org-admin) |
| `src/routes/prompt-templates/+page.svelte` | ✅ Analyzed | Medium | Clean |

### Components Analyzed ✅

| File | Status | Issues |
|------|--------|--------|
| `lib/components/Nav.svelte` | ✅ Analyzed | Commented Help System code |
| `lib/components/Footer.svelte` | ✅ Analyzed | Clean |
| `lib/components/Login.svelte` | ✅ Analyzed | Clean |
| `lib/components/Signup.svelte` | ✅ Analyzed | Clean |
| `lib/components/AssistantsList.svelte` | ✅ Analyzed | Commented PublishModal, placeholder handleClone |
| `lib/components/AssistantAccessManager.svelte` | ❌ **REMOVED** | Orphaned feature - access control not needed |
| `lib/components/ChatInterface.svelte` | ✅ Analyzed | Large but manageable |
| `lib/components/KnowledgeBasesList.svelte` | ✅ Analyzed | Clean |
| `lib/components/KnowledgeBaseDetail.svelte` | ✅ Analyzed | **~117KB - needs splitting** |
| `lib/components/PublishModal.svelte` | ✅ Analyzed | Clean |
| `lib/components/LanguageSelector.svelte` | ✅ Analyzed | Clean |
| **assistants/** | | |
| `lib/components/assistants/AssistantForm.svelte` | ✅ Analyzed | Large, well-structured |
| `lib/components/assistants/AssistantSharingModal.svelte` | ✅ Analyzed | Extensive inline styles |
| `lib/components/assistants/AssistantSharing.svelte` | ✅ Analyzed | Need to verify usage |
| **analytics/** | | |
| `lib/components/analytics/ChatAnalytics.svelte` | ✅ Analyzed | Need to verify usage |
| **common/** | | |
| `lib/components/common/FilterBar.svelte` | ✅ Analyzed | Clean, reusable |
| `lib/components/common/Pagination.svelte` | ✅ Analyzed | Clean, reusable |
| **evaluaitor/** | | |
| `lib/components/evaluaitor/RubricsList.svelte` | ✅ Analyzed | Clean |
| `lib/components/evaluaitor/RubricForm.svelte` | ✅ Analyzed | Clean |
| `lib/components/evaluaitor/RubricEditor.svelte` | ✅ Analyzed | Large |
| `lib/components/evaluaitor/RubricTable.svelte` | ✅ Analyzed | Clean |
| `lib/components/evaluaitor/RubricPreview.svelte` | ✅ Analyzed | Clean |
| `lib/components/evaluaitor/RubricMetadataForm.svelte` | ✅ Analyzed | Clean |
| `lib/components/evaluaitor/RubricAIGenerationModal.svelte` | ✅ Analyzed | Clean |
| `lib/components/evaluaitor/RubricAIChat.svelte` | ✅ Analyzed | Clean |
| **modals/** | | |
| `lib/components/modals/DeleteConfirmationModal.svelte` | ✅ Analyzed | Clean |
| `lib/components/modals/CreateKnowledgeBaseModal.svelte` | ✅ Analyzed | Clean |
| `lib/components/modals/TemplateSelectModal.svelte` | ✅ Analyzed | Clean |
| **promptTemplates/** | | |
| `lib/components/promptTemplates/PromptTemplatesContent.svelte` | ✅ Analyzed | Large but well-organized |

### Services Analyzed ✅

| File | Status | Issues |
|------|--------|--------|
| `lib/services/assistantService.js` | ✅ Analyzed | **Many commented-out functions, debug logs** |
| `lib/services/authService.js` | ✅ Analyzed | Clean |
| `lib/services/adminService.js` | ✅ Analyzed | Clean |
| `lib/services/knowledgeBaseService.js` | ✅ Analyzed | Clean |
| `lib/services/organizationService.js` | ✅ Analyzed | Clean |
| `lib/services/rubricService.js` | ✅ Analyzed | Clean |
| `lib/services/templateService.js` | ✅ Analyzed | Clean |
| `lib/services/analyticsService.js` | ✅ Analyzed | Clean |

### Stores Analyzed ✅

| File | Status | Issues |
|------|--------|--------|
| `lib/stores/userStore.js` | ✅ Analyzed | Clean |
| `lib/stores/assistantStore.js` | ✅ Analyzed | Clean |
| `lib/stores/assistantConfigStore.js` | ✅ Analyzed | Clean |
| `lib/stores/assistantPublish.js` | ✅ Analyzed | Clean |
| `lib/stores/templateStore.js` | ✅ Analyzed | Clean |
| `lib/stores/rubricStore.svelte.js` | ✅ Analyzed | Clean |

### Utilities Analyzed ✅

| File | Status | Issues |
|------|--------|--------|
| `lib/config.js` | ✅ Analyzed | **Debug console.logs present** |
| `lib/utils/listHelpers.js` | ✅ Analyzed | Clean, well-documented |
| `lib/utils/nameSanitizer.js` | ✅ Analyzed | Clean |
| `lib/i18n/index.js` | ✅ Analyzed | Clean |

### Tests Analyzed ✅

| File | Status | Coverage |
|------|--------|----------|
| `testing/playwright/tests/creator_flow.spec.js` | ✅ Analyzed | KB, Assistant CRUD, Chat |
| `testing/playwright/tests/admin_and_sharing_flow.spec.js` | ✅ Analyzed | Admin, Users, Orgs, Sharing |
| `testing/playwright/tests/moodle_lti.spec.js` | ✅ Analyzed | LTI integration |

---

## 2. Codebase Architecture Overview

### Current Structure

```
src/
├── routes/                    # SvelteKit routes
│   ├── admin/                 # System admin interface
│   ├── assistants/            # Assistant management
│   ├── chat/                  # Direct chat interface
│   ├── evaluaitor/            # Rubric management
│   ├── knowledgebases/        # KB management
│   ├── org-admin/             # Organization admin
│   └── prompt-templates/      # Template management
├── lib/
│   ├── components/            # Reusable components
│   │   ├── analytics/         # Analytics components
│   │   ├── assistants/        # Assistant-specific components
│   │   ├── common/            # Shared UI components
│   │   ├── evaluaitor/        # Rubric components
│   │   ├── modals/            # Modal dialogs
│   │   └── promptTemplates/   # Template components
│   ├── services/              # API service layer
│   ├── stores/                # Svelte stores
│   ├── utils/                 # Utility functions
│   └── i18n/                  # Internationalization
└── app.css                    # Global styles
```

### Technology Stack
- **Framework**: Svelte 5 with SvelteKit
- **Language**: JavaScript with JSDOC (NOT TypeScript)
- **Styling**: TailwindCSS + component-scoped CSS
- **HTTP**: Axios + native fetch
- **i18n**: svelte-i18n
- **State**: Svelte stores + Svelte 5 runes

---

## 3. Critical Issues - Offenders

### 🔴 CRITICAL: Oversized Components

#### 3.1 `admin/+page.svelte` (~181KB, ~4500+ lines estimated)

**Problem**: This single file contains ALL admin functionality including:
- Dashboard view
- User management (list, create, edit, enable/disable, change password, bulk operations)
- Organization management (list, create, delete)
- Multiple modals and forms
- Extensive inline styles

**Impact**: 
- Extremely difficult to maintain
- Cannot be code-split effectively
- Testing individual features is complex
- High cognitive load for developers

**Severity**: 🔴 CRITICAL

---

#### 3.2 `KnowledgeBaseDetail.svelte` (~117KB, ~3000+ lines estimated)

**Problem**: Monolithic component handling:
- Files tab (file listing, uploads)
- Ingest tab (plugin selection, parameter configuration, job management)
- Query tab (search interface, results display)
- Complex state for ingestion parameters with conditional visibility

**Impact**:
- Poor separation of concerns
- Difficult to test individual features
- Performance impact from large component tree

**Severity**: 🔴 CRITICAL

---

#### 3.3 `org-admin/+page.svelte` (Large, ~500+ lines)

**Problem**: Similar issues to admin page but scoped to organizations:
- Dashboard, users, assistants, settings views
- Complex model selection UI
- Change tracking for unsaved settings
- Multiple inline form patterns

**Severity**: 🟠 HIGH

---

### 🟠 HIGH: Inconsistent Patterns

#### 3.4 Mixed Svelte Syntax

**Components using legacy `$:` reactive syntax:**
- ~~`AssistantAccessManager.svelte`~~ - REMOVED (was orphaned feature)

**Impact**: Inconsistency makes the codebase harder to maintain and reason about.

#### 3.5 Mixed Styling Approaches

Some components use:
- TailwindCSS classes (preferred)
- Inline `<style>` blocks with scoped CSS
- Inline style attributes
- Mixed approaches within the same component

**Examples**:
- `AssistantSharingModal.svelte` - extensive inline `<style>` block
- ~~`AssistantAccessManager.svelte`~~ - REMOVED
- ~~`org-admin/assistants/+page.svelte`~~ - REMOVED (redundant page)

---

## 4. Unused Code Inventory

### 4.1 Code to Remove (Confirmed)

| Location | Code | Decision | Reason |
|----------|------|----------|--------|
| ~~`AssistantsList.svelte`~~ | ~~`PublishModal` import commented out~~ | ✅ **DONE** | Publishing done elsewhere |
| ~~`AssistantsList.svelte`~~ | ~~`handleClone` function placeholder~~ | ✅ **DONE** | Feature not planned |
| ~~`Nav.svelte`~~ | ~~Help System related TODOs~~ | ✅ **DONE** | Feature not planned |
| ~~`+layout.svelte`~~ | ~~Help System TODOs~~ | ✅ **DONE** | Feature not planned |
| ~~`assistantService.js`~~ | ~~Multiple commented functions~~ | ✅ **DONE** | Dead code |
| ~~**`routes/chat/+page.svelte`**~~ | ~~**ENTIRE FILE**~~ | ✅ **DONE** | Orphaned test page with hardcoded API key |

### 4.2 Detailed: `chat/+page.svelte` Removal ✅ COMPLETED

~~**Why this must be removed:**~~
- ~~Contains hardcoded API key: `const API_KEY = '0p3n-w3bu!';`~~
- ~~Displays API key openly in the UI~~
- ~~Not linked from any navigation (orphaned route)~~
- ~~Bypasses normal authentication~~
- ~~Development/testing page that should never have been deployed~~
- ~~Security risk: accessible by typing `/chat` in URL~~

~~**Files to delete:**~~
- ~~`frontend/svelte-app/src/routes/chat/+page.svelte`~~

**Status:** ✅ Removed in Phase 1.1

### 4.3 Debug Code to Remove ✅ PARTIALLY COMPLETE

| Location | Code | Action |
|----------|------|--------|
| ~~`config.js`~~ | ~~`console.log('[DEBUG] getConfig...')`~~ | ✅ DONE - Removed debug logs |
| `assistantService.js` | Multiple `console.log` statements with debugging info | Remove or convert to conditional |
| Various components | `console.log` statements | Audit and remove non-essential |

### 4.3 Unused/Partially Used Components

| Component | Status | Action |
|-----------|--------|--------|
| `PublishModal.svelte` | Exists but commented out in usage | Verify if still needed |
| `AssistantSharing.svelte` | May overlap with `AssistantSharingModal.svelte` | Consolidate or clarify purpose |
| ~~`chat/+page.svelte`~~ | ~~Has hardcoded `API_KEY`~~ | ✅ REMOVED in Phase 1 |
| ~~`AssistantAccessManager.svelte`~~ | ~~Orphaned feature~~ | ✅ REMOVED in Phase 1 |

---

## 5. Spaghetti Code Hotspots

### 5.1 State Management Anti-patterns

#### Location: `org-admin/+page.svelte`

**Issue**: Complex nested state with multiple interdependent `$effect` blocks

```javascript
// Example of complex state
let selectedTab = $state('dashboard');
let hasUnsavedChanges = $state(false);
let pendingChanges = $state({});
// Multiple $effect blocks watching various state combinations
```

**Recommendation**: Extract into dedicated stores or use composition pattern.

---

#### Location: `admin/+page.svelte`

**Issue**: Inline form handling with complex validation scattered throughout

**Recommendation**: Extract form logic into composable functions or dedicated form components.

---

### 5.2 Duplicate Locale Checking Pattern

**Issue**: Multiple components repeat this pattern:

```javascript
let localeLoaded = $state(false);
$effect(() => {
    localeUnsubscribe = locale.subscribe(value => {
        localeLoaded = !!value;
    });
    return () => localeUnsubscribe();
});
```

**Recommendation**: Create a `useLocaleReady()` composable or derive from store.

---

### 5.3 Modal Pattern Inconsistency

**Issue**: Different modal patterns used across the codebase:
- Some use `$bindable(isOpen)` prop
- Some use internal `$state(isOpen)` with `export function open()`
- Some use store-based control (`publishModalOpen`)

**Recommendation**: Standardize on one pattern, preferably `$bindable` for consistency with Svelte 5.

---

## 6. Proposed Component Extractions

### 6.1 From `admin/+page.svelte`

Extract into separate components:

| New Component | Responsibility |
|---------------|----------------|
| `AdminDashboard.svelte` | Dashboard view and statistics |
| `AdminUserList.svelte` | User table with filtering, sorting, pagination |
| `AdminUserForm.svelte` | Create/edit user form (modal or page) |
| `AdminUserBulkActions.svelte` | Bulk enable/disable UI |
| `AdminOrgList.svelte` | Organization table |
| `AdminOrgForm.svelte` | Create organization form |
| `ChangePasswordModal.svelte` | Password change modal (generic) |
| `DisableUserModal.svelte` | User disable confirmation |

**Suggested Structure:**
```
src/routes/admin/
├── +page.svelte              # Routing/orchestration only
├── components/
│   ├── AdminDashboard.svelte
│   ├── AdminUserList.svelte
│   ├── AdminUserForm.svelte
│   ├── AdminUserBulkActions.svelte
│   ├── AdminOrgList.svelte
│   └── AdminOrgForm.svelte
```

---

### 6.2 From `KnowledgeBaseDetail.svelte`

Extract into:

| New Component | Responsibility |
|---------------|----------------|
| `KBFilesTab.svelte` | File listing and management |
| `KBIngestTab.svelte` | Ingestion interface |
| `KBIngestPluginSelector.svelte` | Plugin dropdown and config |
| `KBIngestParameters.svelte` | Dynamic parameter form |
| `KBIngestJobStatus.svelte` | Job progress display |
| `KBQueryTab.svelte` | Query interface |
| `KBQueryResults.svelte` | Search results display |

**Suggested Structure:**
```
src/lib/components/knowledgebase/
├── KnowledgeBaseDetail.svelte  # Orchestration with tabs
├── KBFilesTab.svelte
├── KBIngestTab.svelte
├── KBIngestPluginSelector.svelte
├── KBIngestParameters.svelte
├── KBIngestJobStatus.svelte
├── KBQueryTab.svelte
└── KBQueryResults.svelte
```

---

### 6.3 From `org-admin/+page.svelte`

Extract into:

| New Component | Responsibility |
|---------------|----------------|
| `OrgAdminDashboard.svelte` | Dashboard view |
| `OrgAdminUserList.svelte` | Organization user management |
| `OrgAdminAssistantList.svelte` | Organization assistants |
| `OrgAdminSettings.svelte` | Settings container |
| `OrgAdminAPISettings.svelte` | API provider configuration |
| `OrgAdminKBSettings.svelte` | Knowledge base settings |
| `OrgAdminModelSettings.svelte` | Model selection and transfer |

---

## 7. New Components to Develop

### 7.1 Generic/Reusable Components

#### `ConfirmationModal.svelte`

**Purpose**: Generic confirmation modal to replace various delete/disable modals

**Props**:
```javascript
{
  isOpen: boolean,      // $bindable
  title: string,
  message: string,
  confirmText: string,  // default: "Confirm"
  cancelText: string,   // default: "Cancel"
  variant: 'danger' | 'warning' | 'info',
  isLoading: boolean,   // $bindable
}
```

**Events**: `confirm`, `cancel`

---

#### `DataTable.svelte`

**Purpose**: Standardized table component with built-in:
- Sorting
- Filtering
- Pagination
- Row selection
- Loading states
- Empty states

**Usage Example**:
```svelte
<DataTable
  data={users}
  columns={[
    { key: 'name', label: 'Name', sortable: true },
    { key: 'email', label: 'Email' },
    { key: 'status', label: 'Status', component: StatusBadge },
  ]}
  on:rowClick={handleRowClick}
  on:sort={handleSort}
/>
```

---

#### `FormField.svelte`

**Purpose**: Standardized form field wrapper with:
- Label
- Error display
- Help text
- Required indicator

```svelte
<FormField label="Email" required error={emailError} helpText="Enter your work email">
  <input type="email" bind:value={email} />
</FormField>
```

---

#### `TabGroup.svelte`

**Purpose**: Reusable tab interface

```svelte
<TabGroup tabs={['Files', 'Ingest', 'Query']} bind:activeTab>
  {#if activeTab === 'Files'}
    <KBFilesTab {kb} />
  {/if}
  <!-- ... -->
</TabGroup>
```

---

### 7.2 Feature-Specific Components

#### `UserTypeSelector.svelte`

**Purpose**: Consistent user type selection (creator/end_user)

---

#### `OrganizationSelector.svelte`

**Purpose**: Organization dropdown with loading state (used in admin forms)

---

#### `ModelSelector.svelte`

**Purpose**: LLM model selection with provider grouping (used in assistant form and org settings)

---

## 8. Code Quality Improvements

### 8.1 Svelte 5 Migration Checklist

Components still using legacy patterns:

| Component | Issue | Fix |
|-----------|-------|-----|
| ~~`AssistantAccessManager.svelte`~~ | ~~Uses `$:` reactive declarations~~ | REMOVED (orphaned) |
| Various | Uses `export let` for props | Convert to `$props()` |
| Various | Uses `on:click` | Convert to `onclick` |

### 8.2 Styling Standardization

**Rule**: All new components should use TailwindCSS exclusively.

**Migration Priority**:
1. ~~`AssistantAccessManager.svelte`~~ - REMOVED
2. `AssistantSharingModal.svelte` - Heavy inline CSS
3. ~~`org-admin/assistants/+page.svelte`~~ - REMOVED

### 8.3 Error Handling Standardization

Create `lib/utils/errorHandler.js`:

```javascript
/**
 * Standardized error handling for API calls
 */
export function handleApiError(error, context = '') {
  console.error(`[${context}]`, error);
  
  if (error.response?.data?.detail) {
    return error.response.data.detail;
  }
  
  if (error.message) {
    return error.message;
  }
  
  return 'An unexpected error occurred';
}
```

### 8.4 Debug Code Cleanup

Create `lib/utils/logger.js`:

```javascript
const isDev = import.meta.env.DEV;

export const logger = {
  debug: (...args) => isDev && console.log('[DEBUG]', ...args),
  info: (...args) => console.info('[INFO]', ...args),
  warn: (...args) => console.warn('[WARN]', ...args),
  error: (...args) => console.error('[ERROR]', ...args),
};
```

---

## 9. Testing Strategy

### 9.1 Existing Test Coverage

| Test File | Coverage | Status |
|-----------|----------|--------|
| `creator_flow.spec.js` | KB CRUD, Assistant CRUD, Chat | ✅ Good |
| `admin_and_sharing_flow.spec.js` | Admin, Users, Orgs, Sharing | ✅ Good |
| `moodle_lti.spec.js` | LTI integration | ✅ Good |

### 9.2 New Tests Needed

#### Priority 1: Critical Path Tests

```javascript
// prompt_templates_flow.spec.js
test.describe('Prompt Templates Flow', () => {
  test('Create template', async ({ page }) => {});
  test('Edit template', async ({ page }) => {});
  test('Share template', async ({ page }) => {});
  test('Duplicate template', async ({ page }) => {});
  test('Delete template', async ({ page }) => {});
  test('Export templates', async ({ page }) => {});
});
```

```javascript
// rubrics_flow.spec.js
test.describe('Rubrics Flow', () => {
  test('Create rubric manually', async ({ page }) => {});
  test('Create rubric with AI', async ({ page }) => {});
  test('Edit rubric', async ({ page }) => {});
  test('Delete rubric', async ({ page }) => {});
});
```

#### Priority 2: Edge Cases

```javascript
// form_validation.spec.js
test.describe('Form Validation', () => {
  test('Assistant form - dirty state prevents navigation', async ({ page }) => {});
  test('Assistant form - name conflict error', async ({ page }) => {});
  test('KB name sanitization preview', async ({ page }) => {});
});
```

```javascript
// error_handling.spec.js
test.describe('Error Handling', () => {
  test('Network error shows appropriate message', async ({ page }) => {});
  test('Auth token expiry redirects to login', async ({ page }) => {});
  test('KB server offline shows error state', async ({ page }) => {});
});
```

#### Priority 3: Component-Level Tests After Refactoring

After extracting components, add targeted tests:

```javascript
// admin_components.spec.js
test.describe('Admin Components', () => {
  test('AdminUserList - filtering', async ({ page }) => {});
  test('AdminUserList - sorting', async ({ page }) => {});
  test('AdminUserList - pagination', async ({ page }) => {});
  test('AdminUserList - bulk selection', async ({ page }) => {});
});
```

### 9.3 Test Utilities to Create

```javascript
// testing/playwright/helpers/auth.js
export async function loginAs(page, userType = 'admin') {
  // Reusable login helper
}

export async function logout(page) {
  // Reusable logout helper
}
```

```javascript
// testing/playwright/helpers/navigation.js
export async function navigateToAssistants(page) {
  await page.goto('/assistants');
  await page.waitForLoadState('networkidle');
}

export async function navigateToAdmin(page, view = 'dashboard') {
  await page.goto(`/admin?view=${view}`);
  await page.waitForLoadState('networkidle');
}
```

---

## 10. Implementation Phases

### Phase 1: Quick Wins - Confirmed Removals ✅ COMPLETE

> ⚠️ **IMPORTANT**: Even for "quick wins", the MANDATORY METHODOLOGY must be followed.
> Each item requires browser testing, user confirmation, and Playwright tests.

| # | Task | Status | UI Impact |
|---|------|--------|-----------|
| 1.1 | Remove `routes/chat/+page.svelte` entirely | ✅ **DONE** | None (orphaned) |
| 1.2 | Remove commented `PublishModal` import in `AssistantsList.svelte` | ✅ **DONE** | None |
| 1.3 | Remove `handleClone` placeholder in `AssistantsList.svelte` | ✅ **DONE** | None |
| 1.4 | Remove Help System TODOs in `Nav.svelte` | ✅ **DONE** | None |
| 1.5 | Remove Help System TODOs in `+layout.svelte` | ✅ **DONE** | None |
| 1.6 | Remove commented functions in `assistantService.js` | ✅ **DONE** | None |
| 1.7 | Remove debug `console.log` statements in `config.js` | ✅ **DONE** | None |
| 1.8 | Create `logger.js` utility | ✅ **DONE** | None |
| 1.9 | Create `errorHandler.js` utility | ✅ **DONE** | None |
| 1.10 | Remove `AssistantAccessManager.svelte` (orphaned feature) | ✅ **DONE** | None |
| 1.11 | Remove `/org-admin/assistants/+page.svelte` (redundant page) | ✅ **DONE** | None |
| 1.12 | Remove `getAssistantAccess`/`updateAssistantAccess` from `organizationService.js` | ✅ **DONE** | None |

### Phase 2: Pattern Standardization

1. Create generic `ConfirmationModal.svelte`
3. Replace specific delete/disable modals with generic one
4. Standardize modal open/close patterns
5. Extract locale-checking into composable

### Phase 3: Admin Page Refactoring (5-7 days)

1. Extract `AdminDashboard.svelte`
2. Extract `AdminUserList.svelte`
3. Extract `AdminUserForm.svelte`
4. Extract `AdminOrgList.svelte`
5. Extract `AdminOrgForm.svelte`
6. Update Playwright tests to work with new structure
7. Add component-specific tests

### Phase 4: KnowledgeBase Detail Refactoring (5-7 days)

1. Create new `knowledgebase/` component folder
2. Extract `KBFilesTab.svelte`
3. Extract `KBIngestTab.svelte` and sub-components
4. Extract `KBQueryTab.svelte`
5. Update parent orchestration
6. Update and expand tests

### Phase 5: Org-Admin Refactoring (3-5 days)

1. Extract settings sub-components
2. Extract user/assistant list components
3. Reuse components from Phase 3 where applicable

### Phase 6: Testing & Polish (2-3 days)

1. Add all Priority 1 tests
2. Add Priority 2 edge case tests
3. Documentation updates
4. Final code review

---

## 11. Risk Assessment

### High Risk Areas

| Area | Risk | Mitigation |
|------|------|------------|
| `admin/+page.svelte` refactoring | May break existing admin workflows | Comprehensive Playwright tests before refactoring |
| State management changes | Could introduce race conditions | Careful review of `$effect` dependencies |
| Modal pattern changes | May affect UX consistency | Test all modal interactions |

### Low Risk Areas

| Area | Notes |
|------|-------|
| Dead code removal | Well-documented, clear what's unused |
| Debug log removal | No functional impact |
| New utility creation | Additive, no breaking changes |

### Testing Requirements Before Merge

For each phase, require:
1. All existing Playwright tests pass
2. New tests written for changed functionality
3. Manual smoke test of affected features
4. Code review by team member

---

## Appendix A: Files Requiring No Changes

The following files were analyzed and found to be well-structured:

- `lib/stores/userStore.js` - Clean, well-documented
- `lib/stores/templateStore.js` - Clean, follows patterns
- `lib/utils/listHelpers.js` - Excellent documentation and utility
- `lib/components/common/FilterBar.svelte` - Reusable, well-structured
- `lib/components/common/Pagination.svelte` - Reusable, well-structured
- `lib/components/modals/DeleteConfirmationModal.svelte` - Clean
- `lib/components/modals/CreateKnowledgeBaseModal.svelte` - Clean
- All `evaluaitor/` components - Well-organized

---

## Appendix B: Reference Architecture

### Ideal Component Pattern (Svelte 5)

```svelte
<script>
  import { _ } from '$lib/i18n';
  import { someService } from '$lib/services/someService';
  
  // Props with destructuring
  let { 
    data = [],
    isLoading = $bindable(false),
    onSelect
  } = $props();
  
  // Local state
  let selected = $state(null);
  let error = $state('');
  
  // Derived values
  let sortedData = $derived(
    [...data].sort((a, b) => a.name.localeCompare(b.name))
  );
  
  // Effects (side effects only)
  $effect(() => {
    if (selected) {
      console.log('Selection changed:', selected);
    }
  });
  
  // Event handlers
  function handleSelect(item) {
    selected = item;
    onSelect?.(item);
  }
</script>

<!-- Template uses TailwindCSS -->
<div class="bg-white rounded-lg shadow p-4">
  {#if isLoading}
    <div class="animate-pulse">Loading...</div>
  {:else if error}
    <div class="text-red-500">{error}</div>
  {:else}
    {#each sortedData as item (item.id)}
      <button
        onclick={() => handleSelect(item)}
        class="w-full text-left p-2 hover:bg-gray-50"
      >
        {item.name}
      </button>
    {/each}
  {/if}
</div>
```

---

## Appendix C: i18n Key Conventions

Follow existing patterns:
- `common.*` - Shared UI strings (cancel, save, delete, etc.)
- `assistants.*` - Assistant-related strings
- `knowledgeBases.*` - KB-related strings
- `admin.*` - Admin panel strings
- `promptTemplates.*` - Template-related strings
- `evaluaitor.*` - Rubric-related strings

---

**Document prepared by: AI Assistant**  
**For questions: Contact project maintainers**
