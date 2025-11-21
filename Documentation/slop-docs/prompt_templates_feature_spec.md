# Prompt Templates Feature Specification

**Version:** 1.0  
**Created:** October 2025  
**Status:** Proposed

---

## 1. Executive Summary

The Prompt Templates feature introduces a reusable template system for assistant prompts within LAMB. This feature allows educators to create, manage, and share standardized prompt configurations that can be quickly applied when creating new assistants. This promotes consistency, saves time, and enables best practice sharing within organizations.

---

## 2. Feature Overview

### 2.1 Core Concept

Prompt Templates are pre-configured combinations of system prompts and prompt templates that encapsulate proven pedagogical approaches, subject-specific configurations, or institutional standards. Users can create personal templates and share them with their organization members.

### 2.2 Key Benefits

- **Time Efficiency:** Quickly apply proven prompt configurations when creating new assistants
- **Consistency:** Maintain standardized approaches across multiple assistants
- **Knowledge Sharing:** Share effective prompt strategies within organizations
- **Best Practices:** Build a library of tested and refined prompt patterns
- **Version Control:** Export/import templates for backup and distribution

### 2.3 User Stories

#### As an Educator (Creator User)
- I want to save my effective prompt configurations as templates so I can reuse them
- I want to browse and use templates shared by my colleagues
- I want to duplicate and modify existing templates to create variations
- I want to export my templates for backup or sharing outside the platform
- I want to organize my templates with clear names and descriptions

#### As an Organization Member
- I want to share my successful templates with other members of my organization
- I want to discover templates created by my colleagues
- I want to build upon shared templates to create specialized versions

#### As an Administrator
- I want members of my organization to share knowledge and best practices
- I want to maintain a library of organizational standard templates

---

## 3. Functional Requirements

### 3.1 Template Management

#### 3.1.1 Template CRUD Operations
- **FR-PT-001:** Users shall create prompt templates with name, description, system prompt, and prompt template
- **FR-PT-002:** Users shall view a list of their own templates
- **FR-PT-003:** Users shall edit their own templates
- **FR-PT-004:** Users shall delete their own templates
- **FR-PT-005:** Users shall duplicate any accessible template (own or shared)
- **FR-PT-006:** System shall prevent duplicate template names per user
- **FR-PT-007:** Templates shall belong to a specific user and organization

#### 3.1.2 Template Sharing
- **FR-PT-008:** Users shall mark templates as "shared" within their organization
- **FR-PT-009:** Users shall view shared templates from other organization members
- **FR-PT-010:** Users shall have separate views for "My Templates" and "Shared Templates"
- **FR-PT-011:** Shared templates shall be read-only for non-owners
- **FR-PT-012:** Users shall see the creator's name on shared templates

#### 3.1.3 Template Export/Import
- **FR-PT-013:** Users shall export individual templates as JSON files
- **FR-PT-014:** Users shall export multiple selected templates as a JSON bundle
- **FR-PT-015:** Exported JSON shall include all template fields and metadata
- **FR-PT-016:** System shall validate imported JSON structure (future enhancement)

### 3.2 Assistant Integration

#### 3.2.1 Template Application
- **FR-PT-017:** Create assistant form shall include "Load Template" button
- **FR-PT-018:** Load Template button shall open a modal with template selection
- **FR-PT-019:** Template selection modal shall show both personal and shared templates
- **FR-PT-020:** Selecting a template shall populate ONLY system prompt and prompt template fields
- **FR-PT-021:** Template application shall not affect other assistant fields
- **FR-PT-022:** Users shall be able to modify populated fields after template application

#### 3.2.2 Template Selection UI
- **FR-PT-023:** Template selection modal shall display template name and description
- **FR-PT-024:** Templates shall be searchable by name and description
- **FR-PT-025:** Templates shall show creator name for shared templates
- **FR-PT-026:** Modal shall have clear "Apply" and "Cancel" actions

### 3.3 Navigation and UI

#### 3.3.1 Menu Integration
- **FR-PT-027:** "Prompt Templates" shall appear as a tab under Learning Assistants menu
- **FR-PT-028:** Tab order shall be: Assistants | Knowledge Bases | Prompt Templates
- **FR-PT-029:** Navigation shall be consistent with existing UI patterns

#### 3.3.2 Template List View
- **FR-PT-030:** List shall support pagination (10/20/50 items per page)
- **FR-PT-031:** List shall show: Name, Description (truncated), Created date, Shared status
- **FR-PT-032:** Each template shall have action buttons: Edit, Duplicate, Export, Delete
- **FR-PT-033:** Shared templates from others shall show: View, Duplicate, Export actions only

---

## 4. Technical Architecture

### 4.1 Database Schema

#### 4.1.1 New Table: prompt_templates

```sql
CREATE TABLE prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    owner_email TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    system_prompt TEXT,
    prompt_template TEXT,
    is_shared BOOLEAN DEFAULT FALSE,
    metadata JSON,  -- For future extensibility
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (owner_email) REFERENCES Creator_users(user_email),
    UNIQUE(organization_id, owner_email, name)
);

-- Index for efficient queries
CREATE INDEX idx_prompt_templates_org_shared 
ON prompt_templates(organization_id, is_shared);

CREATE INDEX idx_prompt_templates_owner 
ON prompt_templates(owner_email);
```

#### 4.1.2 Metadata Structure

```json
{
  "version": "1.0",
  "tags": ["mathematics", "socratic", "beginner"],  // Future enhancement
  "usage_count": 0,  // Track template popularity
  "last_used": null,
  "export_version": "1.0"
}
```

### 4.2 API Endpoints

#### 4.2.1 Template Management Endpoints

| Method | Endpoint | Purpose | Access |
|--------|----------|---------|--------|
| GET | `/creator/prompt-templates/list` | List user's templates | Authenticated |
| GET | `/creator/prompt-templates/shared` | List org shared templates | Authenticated |
| GET | `/creator/prompt-templates/{id}` | Get template details | Owner or shared |
| POST | `/creator/prompt-templates/create` | Create new template | Authenticated |
| PUT | `/creator/prompt-templates/{id}` | Update template | Owner only |
| DELETE | `/creator/prompt-templates/{id}` | Delete template | Owner only |
| POST | `/creator/prompt-templates/{id}/duplicate` | Duplicate template | Authenticated |
| PUT | `/creator/prompt-templates/{id}/share` | Toggle sharing | Owner only |
| POST | `/creator/prompt-templates/export` | Export templates | Authenticated |

#### 4.2.2 Request/Response Examples

**Create Template Request:**
```json
POST /creator/prompt-templates/create
{
  "name": "Socratic Mathematics Tutor",
  "description": "Guide students through problem-solving with questions",
  "system_prompt": "You are a Socratic mathematics tutor...",
  "prompt_template": "Student Question: {user_message}\n\nGuide the student...",
  "is_shared": false
}
```

**List Templates Response:**
```json
{
  "templates": [
    {
      "id": 1,
      "name": "Socratic Mathematics Tutor",
      "description": "Guide students through problem-solving with questions",
      "is_shared": true,
      "owner_email": "prof@university.edu",
      "owner_name": "Dr. Smith",
      "created_at": 1698768000,
      "updated_at": 1698768000,
      "is_owner": true
    }
  ],
  "total": 15,
  "page": 1,
  "limit": 10
}
```

**Export Template Response:**
```json
{
  "export_version": "1.0",
  "exported_at": "2025-10-27T10:00:00Z",
  "templates": [
    {
      "name": "Socratic Mathematics Tutor",
      "description": "Guide students through problem-solving with questions",
      "system_prompt": "You are a Socratic mathematics tutor...",
      "prompt_template": "Student Question: {user_message}\n\nGuide the student...",
      "metadata": {
        "tags": ["mathematics", "socratic"],
        "export_version": "1.0"
      }
    }
  ]
}
```

### 4.3 Frontend Components

#### 4.3.1 New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `PromptTemplates.svelte` | `/routes/prompt-templates/+page.svelte` | Main templates page |
| `TemplatesList.svelte` | `/lib/components/templates/` | Templates list view |
| `TemplateForm.svelte` | `/lib/components/templates/` | Create/edit template form |
| `TemplateCard.svelte` | `/lib/components/templates/` | Template display card |
| `TemplateSelectModal.svelte` | `/lib/components/templates/` | Template selection modal |
| `TemplateExportModal.svelte` | `/lib/components/templates/` | Export options modal |

#### 4.3.2 Modified Components

| Component | Modification |
|-----------|-------------|
| `Nav.svelte` | Add "Prompt Templates" tab to Learning Assistants menu |
| `AssistantForm.svelte` | Add "Load Template" button and integration |

#### 4.3.3 New Services

| Service | Location | Purpose |
|---------|----------|---------|
| `templateService.js` | `/lib/services/` | API client for template operations |

#### 4.3.4 New Stores

| Store | Location | Purpose |
|-------|----------|---------|
| `templateStore.js` | `/lib/stores/` | Template list state management |
| `templateModalStore.js` | `/lib/stores/` | Template selection modal state |

---

## 5. Implementation Plan

### 5.1 Phase 1: Backend Foundation (Week 1)

#### 5.1.1 Database Setup
- [ ] Create database migration for prompt_templates table
- [ ] Add migration to LambDatabaseManager
- [ ] Implement automatic migration on startup
- [ ] Create indexes for performance

#### 5.1.2 Database Manager Methods
- [ ] Implement CRUD operations in LambDatabaseManager
  - [ ] `create_prompt_template()`
  - [ ] `get_prompt_template_by_id()`
  - [ ] `get_user_prompt_templates()`
  - [ ] `get_organization_shared_templates()`
  - [ ] `update_prompt_template()`
  - [ ] `delete_prompt_template()`
  - [ ] `duplicate_prompt_template()`
  - [ ] `toggle_template_sharing()`

#### 5.1.3 API Implementation
- [ ] Create `prompt_templates_router.py` in `/backend/creator_interface/`
- [ ] Implement all template management endpoints
- [ ] Add authentication and authorization checks
- [ ] Implement organization-scoped access control
- [ ] Add input validation and error handling

### 5.2 Phase 2: Frontend Core (Week 1-2)

#### 5.2.1 Navigation and Routing
- [ ] Add route `/prompt-templates` to SvelteKit
- [ ] Update Nav.svelte with new tab
- [ ] Implement tab switching logic

#### 5.2.2 Template Management UI
- [ ] Create PromptTemplates.svelte main page
- [ ] Implement TemplatesList.svelte with:
  - [ ] Tab switching (My Templates / Shared Templates)
  - [ ] Pagination controls
  - [ ] Search functionality
  - [ ] Action buttons per template
- [ ] Create TemplateForm.svelte with:
  - [ ] Form validation
  - [ ] Rich text editing for prompts
  - [ ] Save/Cancel actions
  - [ ] Sharing toggle

#### 5.2.3 Services and State Management
- [ ] Implement templateService.js
- [ ] Create templateStore.js
- [ ] Add error handling and loading states

### 5.3 Phase 3: Assistant Integration (Week 2)

#### 5.3.1 Template Selection Modal
- [ ] Create TemplateSelectModal.svelte
- [ ] Implement template browsing (tabs for My/Shared)
- [ ] Add search and filter capabilities
- [ ] Implement template preview
- [ ] Add Apply/Cancel actions

#### 5.3.2 Assistant Form Integration
- [ ] Add "Load Template" button to AssistantForm.svelte
- [ ] Implement modal trigger and state management
- [ ] Add template application logic
- [ ] Ensure only system_prompt and prompt_template fields are populated
- [ ] Maintain form dirty state after template application

### 5.4 Phase 4: Export and Polish (Week 2-3)

#### 5.4.1 Export Functionality
- [ ] Implement single template export
- [ ] Implement multi-template export
- [ ] Create TemplateExportModal.svelte
- [ ] Add JSON download functionality
- [ ] Implement proper filename generation

#### 5.4.2 UI Polish and UX
- [ ] Add loading spinners and states
- [ ] Implement success/error notifications
- [ ] Add confirmation dialogs for destructive actions
- [ ] Implement keyboard shortcuts
- [ ] Add tooltips and help text

#### 5.4.3 Internationalization
- [ ] Add translation keys for all new UI text
- [ ] Update language files (en, es, ca, eu)

### 5.5 Phase 5: Testing and Documentation (Week 3)

#### 5.5.1 Testing
- [ ] Unit tests for database operations
- [ ] API endpoint tests
- [ ] Frontend component tests
- [ ] End-to-end Playwright tests
- [ ] Test organization isolation
- [ ] Test sharing permissions

#### 5.5.2 Documentation
- [ ] Update API documentation
- [ ] Create user guide for Prompt Templates
- [ ] Add feature to main documentation
- [ ] Create tutorial/best practices guide

---

## 6. Security Considerations

### 6.1 Access Control
- Templates are scoped to organizations
- Only template owners can edit/delete their templates
- Shared templates are read-only for non-owners
- Organization membership required to see shared templates

### 6.2 Data Validation
- Sanitize all text inputs to prevent XSS
- Validate JSON structure on import
- Limit template size to prevent abuse
- Rate limiting on API endpoints

### 6.3 Privacy
- User emails visible only within organization
- No cross-organization template access
- Export includes only template data, no user PII

---

## 7. Performance Considerations

### 7.1 Database
- Indexed queries for template lists
- Pagination to limit data transfer
- Caching for frequently accessed shared templates

### 7.2 Frontend
- Lazy loading of template content
- Virtual scrolling for large template lists
- Debounced search functionality

---

## 8. Future Enhancements

### 8.1 Version 1.1
- Template categories and tags
- Template versioning and history
- Usage analytics (which templates are most used)
- Template ratings and reviews

### 8.2 Version 1.2
- Import functionality from JSON
- Template marketplace (public sharing)
- Template inheritance/composition
- Variables in templates beyond {user_message}

### 8.3 Version 2.0
- AI-assisted template generation
- Template effectiveness metrics
- Collaborative template editing
- Template recommendation engine

---

## 9. Migration Strategy

### 9.1 Database Migration
```python
def add_prompt_templates_table(self):
    """Add prompt_templates table if it doesn't exist"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            owner_email TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            system_prompt TEXT,
            prompt_template TEXT,
            is_shared BOOLEAN DEFAULT FALSE,
            metadata JSON,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (owner_email) REFERENCES Creator_users(user_email),
            UNIQUE(organization_id, owner_email, name)
        )
    """)
```

### 9.2 Backward Compatibility
- Existing assistants continue to work unchanged
- No modifications to existing assistant data
- Feature is additive, no breaking changes

---

## 10. Success Metrics

### 10.1 Adoption Metrics
- Number of templates created per organization
- Percentage of users creating templates
- Number of shared templates per organization
- Template usage rate in new assistants

### 10.2 Efficiency Metrics
- Time saved in assistant creation
- Reduction in prompt iteration cycles
- Increase in assistant consistency

### 10.3 Collaboration Metrics
- Sharing rate of templates
- Duplicate/fork rate of shared templates
- Cross-team template usage

---

## 11. Risks and Mitigation

### 11.1 Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Low adoption | Medium | Medium | Provide starter templates, tutorials |
| Template sprawl | High | Low | Implement search, categories (future) |
| Inconsistent quality | Medium | Medium | Add ratings/reviews (future) |
| Performance impact | Low | Medium | Implement caching, pagination |

### 11.2 Dependencies
- Requires existing organization structure
- Depends on current authentication system
- Integrates with assistant creation workflow

---

## 12. Acceptance Criteria

### 12.1 Feature Complete
- [ ] All CRUD operations functional
- [ ] Sharing mechanism works within organization
- [ ] Export produces valid JSON
- [ ] Template application in assistant creation works
- [ ] UI is responsive and intuitive

### 12.2 Quality Gates
- [ ] All tests passing (>90% coverage)
- [ ] No critical security vulnerabilities
- [ ] Performance within acceptable limits
- [ ] Documentation complete
- [ ] Internationalization complete

---

## 13. Technical Decisions

### 13.1 Why Separate Table?
- Clean separation of concerns
- Easier to query and manage
- Supports future enhancements
- Avoids cluttering assistant table

### 13.2 Why Organization-Scoped?
- Maintains privacy boundaries
- Enables institutional knowledge sharing
- Consistent with existing architecture
- Supports multi-tenancy

### 13.3 Why Not Full Import Yet?
- Export first for backup/sharing
- Import requires validation complexity
- Can be added in future version
- Manual copy-paste works initially

---

## Appendix A: UI Mockups

### A.1 Prompt Templates List View
```
Learning Assistants > Prompt Templates

[My Templates] [Shared Templates]                    [+ New Template]

Search: [_____________________] 

┌─────────────────────────────────────────────────────────────┐
│ Name: Socratic Mathematics Tutor                           │
│ Description: Guide students through problem-solving...      │
│ Created: Oct 15, 2024 | Shared: Yes                        │
│ [Edit] [Duplicate] [Export] [Delete]                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Name: Essay Writing Assistant                              │
│ Description: Help students structure and improve essays... │
│ Created: Oct 10, 2024 | Shared: No                        │
│ [Edit] [Duplicate] [Export] [Delete]                       │
└─────────────────────────────────────────────────────────────┘

[< Previous] Page 1 of 3 [Next >]
```

### A.2 Template Selection Modal (in Assistant Creation)
```
┌─ Select Prompt Template ────────────────────────────────────┐
│                                                             │
│ [My Templates] [Shared Templates]                          │
│                                                             │
│ Search: [_____________________]                            │
│                                                             │
│ ┌───────────────────────────────────────────────────────┐ │
│ │ ○ Socratic Mathematics Tutor                          │ │
│ │   Guide students through problem-solving...           │ │
│ └───────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌───────────────────────────────────────────────────────┐ │
│ │ ● Essay Writing Assistant                             │ │
│ │   Help students structure and improve essays...       │ │
│ └───────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌───────────────────────────────────────────────────────┐ │
│ │ ○ Code Review Mentor (by Dr. Johnson)                 │ │
│ │   Provide constructive feedback on code...            │ │
│ └───────────────────────────────────────────────────────┘ │
│                                                             │
│                              [Cancel] [Apply Template]     │
└─────────────────────────────────────────────────────────────┘
```

---

## Document Control

- **Author:** LAMB Development Team
- **Created:** October 27, 2025
- **Status:** Proposed
- **Review:** Pending
- **Implementation:** Not Started
