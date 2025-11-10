# LAMB Organizations Database Report

**Report Generated:** November 9, 2025  
**Database:** `/opt/lamb/lamb_v4.db`  
**Table:** `LAMB_organizations`

---

## Executive Summary

This database currently contains **2 organizations**:
- 1 system organization (LAMB System)
- 1 regular organization (dev)

### Organizations Overview

| ID | Slug | Name | Type | Status | Users | Assistants | Created | Last Updated |
|----|------|------|------|--------|-------|------------|---------|--------------|
| 1 | lamb | LAMB System Organization | System | active | 1 | 4 | 2025-11-03 11:17 | 2025-11-03 14:56 |
| 2 | dev | dev | Regular | active | 4 | 10 | 2025-11-03 11:20 | 2025-11-03 19:36 |

---

## Organization 1: LAMB System Organization

### Basic Information

| Field | Value |
|-------|-------|
| **ID** | 1 |
| **Slug** | `lamb` |
| **Name** | LAMB System Organization |
| **Is System** | ✅ Yes (System-managed) |
| **Status** | `active` |
| **Created At** | 1762168636 (2025-11-03 11:17:16 UTC) |
| **Updated At** | 1762180589 (2025-11-03 14:56:29 UTC) |
| **Users** | 1 |
| **Assistants** | 4 |

### Configuration Details

#### Version & Metadata

```json
{
  "version": "1.0",
  "metadata": {
    "description": "System default organization",
    "system_managed": true,
    "created_at": "2025-11-03T11:17:16.703710"
  }
}
```

| Field | Value |
|-------|-------|
| Config Version | 1.0 |
| Description | System default organization |
| System Managed | ✅ Yes |

---

#### Provider Configuration (Default Setup)

##### OpenAI Provider

| Setting | Value |
|---------|-------|
| **API Key** | `sk-proj-vj8X...` (truncated for security) |
| **Base URL** | `https://api.openai.com/v1` |
| **Default Model** | `gpt-4.1` |
| **Available Models** | `gpt-4.1` |

##### Ollama Provider

| Setting | Value |
|---------|-------|
| **Base URL** | `http://host.docker.internal:11434` |
| **Default Model** | `nomic-embed-text` |
| **Available Models** | `nomic-embed-text` |

##### Knowledge Base Configuration

| Setting | Value |
|---------|-------|
| **Server URL** | `http://kb:9090` |
| **API Token** | `0p3n-w3bu!` |

---

#### Feature Flags

| Feature | Enabled | Additional Info |
|---------|---------|-----------------|
| **Signup** | ✅ Yes | Signup Key: `pepino-secret-key` |
| **Dev Mode** | ✅ Yes | - |
| **MCP** | ✅ Yes | Model Context Protocol enabled |
| **LTI Publishing** | ✅ Yes | LTI 1.1 integration enabled |
| **RAG** | ✅ Yes | Retrieval-Augmented Generation enabled |

---

#### Usage Limits

| Resource | Limit |
|----------|-------|
| **Tokens per Month** | -1 (Unlimited) |
| **Max Assistants** | -1 (Unlimited) |
| **Storage (GB)** | -1 (Unlimited) |

---

#### Assistant Defaults

##### System Prompts

| Type | Content |
|------|---------|
| **Default System Prompt** | "Eres un asistente de aprendizaje que ayuda a los estudiantes a aprender sobre un tema especifico. Utiliza el contexto para responder las preguntas del usuario." |
| **Surfer System Prompt** | "You are a wise surfer dude and a helpful teaching assistant that uses Retrieval-Augmented Generation (RAG) to improve your answers." |

##### Plugin Configuration

| Plugin Type | Default Value |
|-------------|---------------|
| **Prompt Processor** | `simple_augment` |
| **Connector** | `openai` |
| **Default LLM** | `gpt-4.1` |
| **RAG Processor** | `No RAG` |

##### Other Defaults

| Setting | Value |
|---------|-------|
| **Helper Assistant** | `lamb_assistant.1` |
| **RAG Placeholders** | `["--- {context} --- ", "--- {user_input} ---"]` |

---

## Organization 2: dev

### Basic Information

| Field | Value |
|-------|-------|
| **ID** | 2 |
| **Slug** | `dev` |
| **Name** | dev |
| **Is System** | ❌ No (Regular organization) |
| **Status** | `active` |
| **Created At** | 1762168839 (2025-11-03 11:20:39 UTC) |
| **Updated At** | 1762330585 (2025-11-04 19:36:25 UTC) |
| **Users** | 4 |
| **Assistants** | 10 |

### Configuration Details

#### Version & Metadata

```json
{
  "version": "1.0",
  "metadata": {
    "description": "Organization created from system baseline",
    "system_managed": false,
    "created_from_system": true,
    "admin_user_id": 2,
    "admin_user_email": "admin@dev.com",
    "created_by_system_admin": true
  }
}
```

| Field | Value |
|-------|-------|
| Config Version | 1.0 |
| Description | Organization created from system baseline |
| System Managed | ❌ No |
| Created from System | ✅ Yes |
| Admin User ID | 2 |
| Admin Email | admin@dev.com |
| Created by System Admin | ✅ Yes |

---

#### Provider Configuration (Default Setup)

##### OpenAI Provider

| Setting | Value |
|---------|-------|
| **API Key** | `sk-proj-vj8X...` (truncated for security) |
| **Base URL** | `https://api.openai.com/v1` |
| **Default Model** | `gpt-4o-mini` |
| **Available Models** | `gpt-4o-mini`, `gpt-4o`, `gpt-4.1` |

##### Ollama Provider

| Setting | Value |
|---------|-------|
| **Base URL** | `http://192.168.1.47:11434` |
| **Default Model** | `qwen3:32b` |
| **Available Models** | `gpt-oss:20b`, `gpt-oss:120b`, `qwen3:32b`, `llama3.1:latest`, `deepseek-r1:70b`, `llama3.3:latest`, `llama3.2-vision:90b` |

**Note:** This organization has 7 Ollama models configured, significantly more than the system organization.

##### Knowledge Base Configuration

| Setting | Value |
|---------|-------|
| **Server URL** | `http://kb:9090` |
| **API Token** | `0p3n-w3bu!` |

---

#### Feature Flags

| Feature | Enabled | Additional Info |
|---------|---------|-----------------|
| **Signup** | ✅ Yes | Signup Key: `dev-signup-key` |
| **Dev Mode** | ✅ Yes | - |
| **MCP** | ✅ Yes | Model Context Protocol enabled |
| **LTI Publishing** | ✅ Yes | LTI 1.1 integration enabled |
| **RAG** | ✅ Yes | Retrieval-Augmented Generation enabled |

---

#### Usage Limits

| Resource | Limit |
|----------|-------|
| **Tokens per Month** | 1,000,000 |
| **Max Assistants** | 100 |
| **Max Assistants per User** | 10 |
| **Storage (GB)** | 10 |

**Note:** Unlike the system organization, this organization has defined resource limits.

---

#### Assistant Defaults

##### System Prompts

| Type | Content |
|------|---------|
| **Default System Prompt** | "You are a wise surfer dude who helps out everyone who answers questions" |
| **Boring System Prompt** | "Eres un asistente de aprendizaje que ayuda a los estudiantes a aprender sobre un tema especifico. Utiliza el contexto para responder las preguntas del usuario." |

##### Plugin Configuration

| Plugin Type | Default Value |
|-------------|---------------|
| **Prompt Processor** | `simple_augment` |
| **Connector** | `openai` |
| **Default LLM** | `gpt-4.1` |
| **RAG Processor** | `No RAG` |

##### Other Defaults

| Setting | Value |
|---------|-------|
| **Helper Assistant** | `lamb_assistant.1` |
| **RAG Placeholders** | `["--- {context} --- ", "--- {user_input} ---"]` |

---

## Comparative Analysis

### Key Differences Between Organizations

| Aspect | LAMB System | dev |
|--------|-------------|-----|
| **Type** | System Organization | Regular Organization |
| **OpenAI Models** | 1 model (`gpt-4.1`) | 3 models (`gpt-4o-mini`, `gpt-4o`, `gpt-4.1`) |
| **OpenAI Default** | `gpt-4.1` | `gpt-4o-mini` |
| **Ollama Models** | 1 model (`nomic-embed-text`) | 7 models (various) |
| **Ollama Base URL** | `host.docker.internal:11434` | `192.168.1.47:11434` (External IP) |
| **Signup Key** | `pepino-secret-key` | `dev-signup-key` |
| **Token Limit** | Unlimited (-1) | 1,000,000/month |
| **Assistant Limit** | Unlimited (-1) | 100 total, 10 per user |
| **Storage Limit** | Unlimited (-1) | 10 GB |
| **Users** | 1 | 4 |
| **Assistants** | 4 | 10 |

---

## Configuration Schema Deep Dive

### Complete JSON Structure Template

Based on the actual data, here's the complete configuration schema:

```json
{
  "version": "1.0",
  "metadata": {
    "description": "string",
    "system_managed": boolean,
    "created_at": "ISO 8601 timestamp",
    "created_from_system": boolean (optional),
    "admin_user_id": integer (optional),
    "admin_user_email": "string" (optional),
    "created_by_system_admin": boolean (optional)
  },
  "setups": {
    "default": {
      "name": "string",
      "is_default": boolean,
      "providers": {
        "openai": {
          "api_key": "string",
          "base_url": "string",
          "models": ["array", "of", "strings"],
          "default_model": "string"
        },
        "ollama": {
          "base_url": "string",
          "models": ["array", "of", "strings"],
          "default_model": "string"
        }
      },
      "knowledge_base": {
        "server_url": "string",
        "api_token": "string"
      }
    }
  },
  "features": {
    "signup_enabled": boolean,
    "dev_mode": boolean,
    "mcp_enabled": boolean,
    "lti_publishing": boolean,
    "rag_enabled": boolean,
    "signup_key": "string"
  },
  "limits": {
    "usage": {
      "tokens_per_month": integer (-1 for unlimited),
      "max_assistants": integer (-1 for unlimited),
      "max_assistants_per_user": integer (optional),
      "storage_gb": integer (-1 for unlimited)
    }
  },
  "assistant_defaults": {
    "lamb_helper_assistant": "string",
    "system_prompt": "string",
    "surfer_system_prompt": "string" (optional),
    "boring_system_prompt": "string" (optional),
    "prompt_template": "string",
    "surfer_prompt_template": "string" (optional),
    "boring_prompt_template": "string" (optional),
    "prompt_processor": "string",
    "connector": "string",
    "llm": "string",
    "rag_processor": "string",
    "rag_placeholders": ["array", "of", "strings"]
  },
  "models": {
    "available": [],
    "limits": {}
  }
}
```

---

## Statistical Summary

### Resource Distribution

| Metric | Total | System Org | dev Org |
|--------|-------|------------|---------|
| **Total Users** | 5 | 1 (20%) | 4 (80%) |
| **Total Assistants** | 14 | 4 (28.6%) | 10 (71.4%) |
| **OpenAI Models** | 4 unique | 1 | 3 |
| **Ollama Models** | 8 unique | 1 | 7 |

### Configuration Patterns

#### Common Patterns
- ✅ Both organizations use the same Knowledge Base server (`http://kb:9090`)
- ✅ Both organizations share the same API token for KB access
- ✅ All features (signup, dev_mode, MCP, LTI, RAG) are enabled in both
- ✅ Both use the same default plugin configuration (`simple_augment`, `openai`, `No RAG`)

#### Unique Patterns
- ⚠️ The dev organization has more restrictive resource limits
- ⚠️ The dev organization uses an external Ollama server (192.168.1.47)
- ⚠️ The system organization uses Docker internal networking for Ollama
- ⚠️ Different signup keys for isolation

---

## Security Observations

### Potential Security Concerns

1. **🔐 API Keys Visible**: Both organizations store the same OpenAI API key in plaintext in the database
2. **🔐 Shared KB Token**: Both organizations use the same Knowledge Base API token (`0p3n-w3bu!`)
3. **🔓 Signup Keys**: Signup keys are stored in plaintext:
   - System: `pepino-secret-key`
   - dev: `dev-signup-key`

### Recommendations

- ✅ Consider encrypting sensitive fields (API keys, tokens)
- ✅ Rotate signup keys periodically
- ✅ Use organization-specific KB tokens for better isolation
- ✅ Consider using environment variable references instead of storing keys directly

---

## Timestamps Analysis

### Creation Timeline

1. **2025-11-03 11:17:16** - LAMB System Organization created
2. **2025-11-03 11:20:39** - dev organization created (3 minutes later)

### Update Timeline

1. **2025-11-03 14:56:29** - LAMB System Organization last updated (~3.5 hours after creation)
2. **2025-11-04 19:36:25** - dev organization last updated (~32 hours after creation)

The dev organization is more actively updated, suggesting it's the primary development/testing organization.

---

## Database Schema

### Table Structure

```sql
CREATE TABLE LAMB_organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    is_system BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'trial')),
    config JSON NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
```

### Field Descriptions

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `slug` | TEXT | No | - | Unique organization identifier |
| `name` | TEXT | No | - | Display name |
| `is_system` | BOOLEAN | No | FALSE | System organization flag |
| `status` | TEXT | No | 'active' | Organization status (active/suspended/trial) |
| `config` | JSON | No | - | Complete organization configuration |
| `created_at` | INTEGER | No | - | Unix timestamp of creation |
| `updated_at` | INTEGER | No | - | Unix timestamp of last update |

---

## Conclusion

The LAMB platform currently has a healthy two-organization setup:
- A system organization with unlimited resources
- A development organization with defined limits and more model options

Both organizations are fully functional with all features enabled, though the dev organization shows more active usage with 4 users and 10 assistants compared to the system organization's 1 user and 4 assistants.

---

**End of Report**

