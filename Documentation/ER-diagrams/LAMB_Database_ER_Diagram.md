# LAMB Database Entity-Relationship Diagram

**Database:** LAMB Database (`lamb_v4.db`)  
**Type:** SQLite  
**Last Updated:** November 2025

---

## Overview

This diagram shows all tables in the LAMB database and their relationships. The LAMB database contains:

- **Multi-tenancy structures** (organizations, organization_roles)
- **User accounts** (Creator_users)
- **Core features** (assistants, assistant_shares, assistant_publish)
- **Resources** (rubrics, prompt_templates, kb_registry)
- **Tracking** (usage_logs, lti_users, model_permissions)

---

## Entity-Relationship Diagram

```mermaid
erDiagram
    organizations ||--o{ organization_roles : "has"
    organizations ||--o{ Creator_users : "contains"
    organizations ||--o{ assistants : "owns"
    organizations ||--o{ usage_logs : "tracks"
    organizations ||--o{ rubrics : "contains"
    organizations ||--o{ prompt_templates : "contains"
    organizations ||--o{ kb_registry : "manages"
    
    Creator_users ||--o{ organization_roles : "has"
    Creator_users ||--o{ assistants : "creates"
    Creator_users ||--o{ usage_logs : "generates"
    Creator_users ||--o{ assistant_shares : "shares_from"
    Creator_users ||--o{ assistant_shares : "shares_to"
    Creator_users ||--o{ rubrics : "owns"
    Creator_users ||--o{ prompt_templates : "owns"
    Creator_users ||--o{ kb_registry : "owns"
    
    assistants ||--o{ assistant_publish : "published_as"
    assistants ||--o{ lti_users : "accessed_by"
    assistants ||--o{ usage_logs : "tracked_in"
    assistants ||--o{ assistant_shares : "shared_via"
    
    rubrics ||--o{ rubrics : "parent_child"
    
    organizations {
        INTEGER id PK
        TEXT slug UK "Unique organization identifier"
        TEXT name "Organization display name"
        BOOLEAN is_system "System org flag"
        TEXT status "active, suspended, trial"
        JSON config "Provider configs, KB server, features"
        INTEGER created_at
        INTEGER updated_at
    }
    
    organization_roles {
        INTEGER id PK
        INTEGER organization_id FK
        INTEGER user_id FK
        TEXT role "owner, admin, member"
        INTEGER created_at
        INTEGER updated_at
    }
    
    Creator_users {
        INTEGER id PK
        INTEGER organization_id FK
        TEXT user_email UK "Unique email"
        TEXT user_name
        TEXT user_type "creator or end_user"
        JSON user_config "User preferences, permissions"
        BOOLEAN enabled "Account status"
        INTEGER created_at
        INTEGER updated_at
    }
    
    assistants {
        INTEGER id PK
        INTEGER organization_id FK
        TEXT name
        TEXT description
        TEXT owner "User email"
        TEXT api_callback "Metadata JSON"
        TEXT system_prompt
        TEXT prompt_template
        TEXT RAG_endpoint "DEPRECATED"
        INTEGER RAG_Top_k
        TEXT RAG_collections "Comma-separated KB IDs"
        TEXT pre_retrieval_endpoint "DEPRECATED"
        TEXT post_retrieval_endpoint "DEPRECATED"
        BOOLEAN published
        INTEGER published_at
        TEXT group_id "OWI group ID"
        TEXT group_name
        TEXT oauth_consumer_name
        INTEGER created_at
        INTEGER updated_at
    }
    
    assistant_publish {
        INTEGER assistant_id PK "Also FK to assistants"
        TEXT assistant_name
        TEXT assistant_owner
        TEXT group_id "OWI group ID"
        TEXT group_name
        TEXT oauth_consumer_name UK
        INTEGER created_at
    }
    
    assistant_shares {
        INTEGER id PK
        INTEGER assistant_id FK
        INTEGER shared_with_user_id FK
        INTEGER shared_by_user_id FK
        INTEGER shared_at
    }
    
    lti_users {
        INTEGER id PK
        TEXT assistant_id
        TEXT assistant_name
        TEXT group_id
        TEXT group_name
        TEXT assistant_owner
        TEXT user_email
        TEXT user_name
        TEXT user_display_name
        TEXT lti_context_id
        TEXT lti_app_id
        TEXT user_role "Learner or Instructor"
        INTEGER created_at
        INTEGER updated_at
    }
    
    usage_logs {
        INTEGER id PK
        INTEGER organization_id FK
        INTEGER user_id FK
        INTEGER assistant_id FK
        JSON usage_data "Event, tokens, model, duration"
        INTEGER created_at
    }
    
    model_permissions {
        INTEGER id PK
        TEXT user_email
        TEXT model_name
        TEXT access_type "include or exclude"
    }
    
    rubrics {
        INTEGER id PK
        TEXT rubric_id UK
        INTEGER organization_id FK
        TEXT owner_email
        TEXT title
        TEXT description
        JSON rubric_data "Criteria and levels"
        BOOLEAN is_public
        BOOLEAN is_showcase
        TEXT parent_rubric_id FK "Self-reference"
        INTEGER created_at
        INTEGER updated_at
    }
    
    prompt_templates {
        INTEGER id PK
        INTEGER organization_id FK
        TEXT owner_email FK
        TEXT name
        TEXT description
        TEXT system_prompt
        TEXT prompt_template
        BOOLEAN is_shared
        JSON metadata
        INTEGER created_at
        INTEGER updated_at
    }
    
    kb_registry {
        INTEGER id PK
        TEXT kb_id UK "ChromaDB collection ID"
        TEXT kb_name
        INTEGER owner_user_id FK
        INTEGER organization_id FK
        BOOLEAN is_shared
        JSON metadata
        INTEGER created_at
        INTEGER updated_at
    }
```

---

## Key Relationships

### Multi-Tenancy (Organizations)
- **organizations** is the root entity for multi-tenancy
- Each organization contains users, assistants, and resources
- Organizations are isolated from each other
- The "lamb" organization is special (is_system = TRUE)

### User Management
- **Creator_users** belong to organizations
- Users have roles within organizations via **organization_roles**
- Two user types: `creator` (full access) and `end_user` (OWI only)
- Users can be enabled/disabled via the `enabled` flag

### Assistants
- **assistants** are created by users and belong to organizations
- Assistants can be published via **assistant_publish** (LTI integration)
- Assistants can be shared via **assistant_shares** (NEW feature)
- LTI users tracked in **lti_users** table

### Resource Sharing
- **rubrics** support forking via self-reference (parent_rubric_id)
- **prompt_templates** can be shared within organizations
- **kb_registry** tracks Knowledge Base sharing metadata

### Soft References
- `assistants.owner` → email (not FK)
- `rubrics.owner_email` → email (not FK)
- Allows flexibility but requires manual integrity management

---

## Cascade Delete Behavior

**ON DELETE CASCADE:**
- Organization deletion → All org resources deleted
- User deletion → User's assistants, shares, KBs deleted
- Assistant deletion → Shares and publish records deleted

**ON DELETE SET NULL:**
- Parent rubric deletion → Child's parent_rubric_id set to NULL

---

## Legend

- **PK** = Primary Key
- **FK** = Foreign Key
- **UK** = Unique Key
- **||--o{** = One-to-Many relationship
- **Timestamps** = All INTEGER fields storing UNIX timestamps

---

**Related Documentation:**
- [Complete Database Schema](../LAMB_DATABASE_SCHEMA.md)
- [Open WebUI Database](./OpenWebUI_Database_ER_Diagram.md)
- [Simplified Overview](./Relationships_Overview_Diagram.md)

