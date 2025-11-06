# LAMB Database ER Diagrams

This directory contains Entity-Relationship diagrams for the LAMB platform database architecture.

---

## Available Diagrams

### 1. [LAMB Database ER Diagram](./LAMB_Database_ER_Diagram.md)
**Complete detailed diagram of the main LAMB database**

Shows all tables, fields, relationships, and constraints in the LAMB database (`lamb_v4.db`).

**When to use:**
- Understanding the full LAMB database schema
- Implementing new features that interact with multiple tables
- Debugging data relationships
- Planning database migrations

**Key tables covered:**
- organizations, Creator_users, assistants
- assistant_shares, assistant_publish, lti_users
- rubrics, prompt_templates, kb_registry
- usage_logs, model_permissions, organization_roles

---

### 2. [Open WebUI Database ER Diagram](./OpenWebUI_Database_ER_Diagram.md)
**Complete diagram of the Open WebUI integration database**

Shows the Open WebUI database structure (`webui.db`) and how LAMB integrates with it.

**When to use:**
- Understanding authentication flow
- Implementing user management features
- Working on publishing/sharing features
- Debugging OWI integration issues

**Key tables covered:**
- user, auth (authentication)
- group (access control)
- model (published assistants)

---

### 3. [Relationships Overview Diagram](./Relationships_Overview_Diagram.md)
**Simplified high-level architecture view**

Shows how the two databases work together with a simplified view of entity groups and cross-database links.

**When to use:**
- Getting started with LAMB architecture
- Understanding cross-database integration
- Planning new features
- Explaining system to stakeholders

**Key concepts covered:**
- Database separation rationale
- Cross-database linking patterns
- Common workflows (user creation, publishing, sharing, LTI)
- Integration architecture

---

## Diagram Rendering

All diagrams use **Mermaid.js** syntax and can be rendered in:

### Online Tools
- **Mermaid Live Editor**: https://mermaid.live/
- **GitHub/GitLab**: Automatically renders in Markdown files
- **VS Code**: Install "Markdown Preview Mermaid Support" extension

### Documentation Sites
- Docusaurus
- MkDocs
- GitBook
- Read the Docs (with Sphinx extension)

### IDEs
- VS Code (with extension)
- IntelliJ IDEA (built-in)
- JetBrains IDEs (built-in)

---

## Quick Navigation

**Start here if you're new:**
1. Read [Relationships Overview](./Relationships_Overview_Diagram.md) first
2. Then dive into specific database as needed

**For specific tasks:**

| Task | Recommended Diagram |
|------|---------------------|
| Understanding user types | [LAMB Database](./LAMB_Database_ER_Diagram.md) - Creator_users |
| Implementing sharing | [LAMB Database](./LAMB_Database_ER_Diagram.md) - assistant_shares |
| Working with authentication | [Open WebUI Database](./OpenWebUI_Database_ER_Diagram.md) |
| Publishing assistants | [Relationships Overview](./Relationships_Overview_Diagram.md) - Workflow 2 |
| LTI integration | [LAMB Database](./LAMB_Database_ER_Diagram.md) - lti_users + [Overview](./Relationships_Overview_Diagram.md) |
| Multi-tenancy | [LAMB Database](./LAMB_Database_ER_Diagram.md) - organizations |

---

## Related Documentation

### Complete Documentation
- [Complete Database Schema](../LAMB_DATABASE_SCHEMA.md) - Full text-based schema reference
- [Architecture Documentation](../lamb_architecture.md) - Complete system architecture
- [Product Requirements](../prd.md) - Feature specifications

### Feature-Specific
- [Assistant Sharing Implementation](../ASSISTANT_SHARING_IMPLEMENTATION.md)
- [User Blocking Feature](../lamb_architecture.md#16-user-blocking-feature)
- [End User Feature](../lamb_architecture.md#15-end-user-feature)
- [Knowledge Base Sharing](../lamb_architecture.md#96-knowledge-base-sharing)

### Integration
- [OWI Bridge Documentation](../lamb_architecture.md#32-open-webui-integration)
- [LTI Integration](../lamb_architecture.md#10-lti-integration)
- [Plugin Architecture](../lamb_architecture.md#11-plugin-architecture)

---

## Database Files Location

```
LAMB Database:     $LAMB_DB_PATH/lamb_v4.db
Open WebUI DB:     $OWI_PATH/webui.db
Knowledge Base:    $OWI_PATH/vector_db/ (ChromaDB)
```

Default paths in Docker:
```
LAMB Database:     /app/data/lamb_v4.db
Open WebUI DB:     /app/backend/data/webui.db
Knowledge Base:    /app/backend/data/vector_db/
```

---

## Schema Conventions

### Naming Conventions
- **Tables**: lowercase with underscores (e.g., `assistant_shares`)
- **Primary Keys**: `id` (INTEGER or TEXT depending on table)
- **Foreign Keys**: `{table_name}_id` (e.g., `organization_id`)
- **Timestamps**: `created_at`, `updated_at` (INTEGER, UNIX timestamps)
- **Boolean flags**: `is_*` or `enabled` (e.g., `is_shared`, `enabled`)

### Common Patterns
- **Soft references**: Email-based links instead of hard FKs
- **JSON configuration**: Flexible config fields for extensibility
- **Cascade deletes**: Organization/user deletion cascades to owned resources
- **Unique constraints**: Prevent duplicate relationships

### Index Naming
- Format: `idx_{table}_{column}` or `idx_{table}_{col1}_{col2}` for composite
- Example: `idx_assistants_org`, `idx_usage_logs_org_date`

---

## Contributing

When adding new tables or relationships:

1. **Update the diagrams**:
   - Add entities and relationships to appropriate diagram(s)
   - Update field lists if schema changes
   - Add explanatory text in the documentation sections

2. **Update related documentation**:
   - [LAMB_DATABASE_SCHEMA.md](../LAMB_DATABASE_SCHEMA.md) - Add full table definition
   - [lamb_architecture.md](../lamb_architecture.md) - Update data architecture section

3. **Test rendering**:
   - Verify Mermaid syntax is valid (use https://mermaid.live/)
   - Check that diagrams render correctly in GitHub
   - Ensure cross-references work

4. **Document integration points**:
   - If linking across databases, update [Relationships Overview](./Relationships_Overview_Diagram.md)
   - Document the linking pattern and use case

---

## FAQ

**Q: Why are there two databases?**  
A: LAMB integrates with Open WebUI for authentication and chat interface. Separation allows independent scaling and clear separation of concerns.

**Q: How are the databases linked?**  
A: Via email (users) and text-based IDs (groups, models). See [Relationships Overview](./Relationships_Overview_Diagram.md) for details.

**Q: Can I modify the OWI database directly?**  
A: Use the OWI Bridge abstraction layer (`/backend/lamb/owi_bridge/`) instead of direct modifications. This ensures consistency.

**Q: How do I add a new table?**  
A: Update `/backend/lamb/database_manager.py`, create migration logic, update all 3 diagrams, and update the complete schema documentation.

**Q: Where are foreign key constraints defined?**  
A: In the CREATE TABLE statements in `database_manager.py`. Some relationships use soft references (email) instead of FKs.

---

## Version History

- **v1.0** (November 2025) - Initial ER diagrams created
  - LAMB Database ER Diagram
  - Open WebUI Database ER Diagram
  - Relationships Overview Diagram

---

**Maintained by:** LAMB Development Team  
**Last Updated:** November 2025  
**Feedback:** Please create an issue on GitHub or contact the development team

