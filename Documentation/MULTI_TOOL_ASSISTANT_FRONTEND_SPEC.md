# Multi-Tool Assistant System: Frontend Specification

**Version:** 1.0  
**Date:** December 9, 2025  
**Related Documents:**  
- `Documentation/TOOL_ASSISTANTS_ANALYSIS_REPORT.md` (Tool Assistants design)
- `Documentation/lamb_architecture.md` (System architecture)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Analysis](#2-current-architecture-analysis)
3. [Proposed Multi-Tool Architecture](#3-proposed-multi-tool-architecture)
4. [Data Model Changes](#4-data-model-changes)
5. [Component Architecture](#5-component-architecture)
6. [Plugin System Design](#6-plugin-system-design)
7. [UI/UX Specifications](#7-uiux-specifications)
8. [Service Layer Changes](#8-service-layer-changes)
9. [Store Changes](#9-store-changes)
10. [Migration Strategy](#10-migration-strategy)
11. [Implementation Phases](#11-implementation-phases)
12. [Testing Requirements](#12-testing-requirements)

---

## 1. Executive Summary

### 1.1 Background

The current LAMB assistant system allows selecting **one RAG processor** per assistant, which retrieves context and injects it into a single placeholder (`{context}`). After a team meeting, we decided that assistants need the ability to use **multiple tools** in the same pipeline execution.

### 1.2 Key Requirements

An assistant should be able to:
- Use **Simple RAG Tool** → injects content into `{context}`
- Use **Rubric Tool** → injects rubric into `{rubric}`
- Use **Single-File RAG Tool** → injects file contents into `{file}`
- Use **any combination** of the above (and future tools)

### 1.3 Scope of This Document

This specification covers **frontend-only changes**:
- Component architecture for the multi-tool UI
- Plugin system for tool configuration components
- Data model changes in frontend stores and services
- UI/UX design for managing multiple tools

Backend specifications are covered separately.

### 1.4 Key Design Decisions

1. **Tool Configuration Encoding:** All tool configurations stored in assistant metadata as JSON array
2. **Plugin Component System:** Each tool type has a dedicated Svelte 5 component for its configuration UI
3. **Dynamic Placeholder System:** Frontend displays available placeholders based on selected tools
4. **Backward Compatibility:** Must support assistants with legacy single-tool configuration

---

## 2. Current Architecture Analysis

### 2.1 Current AssistantForm.svelte Structure

**Location:** `/frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte`

**Current Size:** ~2,050 lines

**Current Problems:**
1. **Monolithic structure**: All RAG processor UIs embedded in single file
2. **Conditional complexity**: Nested `{#if}` blocks for each processor type
3. **Single-tool limitation**: Only one RAG processor can be selected
4. **Hardcoded placeholders**: `ragPlaceholders` loaded from static config

### 2.2 Current Tool Selection UI

```svelte
<!-- Current: Single dropdown for RAG processor -->
<select id="rag-processor" bind:value={selectedRagProcessor}>
    {#each ragProcessors as processor}
        <option value={processor}>{processor}</option>
    {/each}
</select>

<!-- Conditional UI based on selection -->
{#if selectedRagProcessor === 'simple_rag'}
    <!-- Knowledge Base selector + Top K -->
{:else if selectedRagProcessor === 'rubric_rag'}
    <!-- Rubric selector + format -->
{:else if selectedRagProcessor === 'single_file_rag'}
    <!-- File selector + upload -->
{/if}
```

### 2.3 Current Metadata Structure

```json
{
    "prompt_processor": "simple_augment",
    "connector": "openai",
    "llm": "gpt-4o-mini",
    "rag_processor": "simple_rag",
    "file_path": "",
    "rubric_id": "",
    "rubric_format": "markdown",
    "capabilities": {
        "vision": false,
        "image_generation": false
    }
}
```

### 2.4 Current State Variables in AssistantForm

```javascript
// RAG-specific state scattered throughout component
let selectedRagProcessor = $state('');
let selectedKnowledgeBases = $state([]);
let RAG_Top_k = $state(3);
let selectedFilePath = $state('');
let selectedRubricId = $state('');
let rubricFormat = $state('markdown');

// Loading states
let loadingKnowledgeBases = $state(false);
let loadingFiles = $state(false);
let loadingRubrics = $state(false);

// Data arrays
let ownedKnowledgeBases = $state([]);
let sharedKnowledgeBases = $state([]);
let userFiles = $state([]);
let accessibleRubrics = $state([]);
```

### 2.5 Current Backend RAG Processors

| Processor | Placeholder | Parameters | Location |
|-----------|-------------|------------|----------|
| `simple_rag` | `{context}` | `RAG_collections`, `RAG_Top_k` | `/lamb/completions/rag/simple_rag.py` |
| `rubric_rag` | `{context}` | `rubric_id`, `rubric_format` | `/lamb/completions/rag/rubric_rag.py` |
| `single_file_rag` | `{context}` | `file_path` | `/lamb/completions/rag/single_file_rag.py` |
| `no_rag` | - | - | `/lamb/completions/rag/no_rag.py` |

**Note:** Currently all processors inject into the same `{context}` placeholder.

---

## 3. Proposed Multi-Tool Architecture

### 3.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AssistantForm.svelte                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   ToolsManager.svelte                         │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │                 ToolSelector.svelte                      │ │  │
│  │  │   [+ Add Tool]   Available: KB, Rubric, File, ...       │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │               Active Tools List                          │ │  │
│  │  │  ┌─────────────────────────────────────────────────┐   │ │  │
│  │  │  │ 🗂️ Knowledge Base Tool                           │   │ │  │
│  │  │  │    <KnowledgeBaseToolConfig />                    │   │ │  │
│  │  │  │    Placeholder: {context}                         │   │ │  │
│  │  │  └─────────────────────────────────────────────────┘   │ │  │
│  │  │                                                         │ │  │
│  │  │  ┌─────────────────────────────────────────────────┐   │ │  │
│  │  │  │ 📋 Rubric Tool                                   │   │ │  │
│  │  │  │    <RubricToolConfig />                          │   │ │  │
│  │  │  │    Placeholder: {rubric}                         │   │ │  │
│  │  │  └─────────────────────────────────────────────────┘   │ │  │
│  │  │                                                         │ │  │
│  │  │  ┌─────────────────────────────────────────────────┐   │ │  │
│  │  │  │ 📄 Single File Tool                              │   │ │  │
│  │  │  │    <SingleFileToolConfig />                      │   │ │  │
│  │  │  │    Placeholder: {file}                           │   │ │  │
│  │  │  └─────────────────────────────────────────────────┘   │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Prompt Template Section                          │  │
│  │   Available Placeholders: {context} {rubric} {file} {user_}  │  │
│  │   [Click to insert]                                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Hierarchy

```
AssistantForm.svelte
├── ToolsManager.svelte (NEW - orchestrates tool management)
│   ├── ToolSelector.svelte (NEW - add tool dropdown)
│   └── ToolConfigList.svelte (NEW - renders active tools)
│       ├── ToolConfigCard.svelte (NEW - wrapper for each tool)
│       │   ├── KnowledgeBaseToolConfig.svelte (NEW - plugin)
│       │   ├── RubricToolConfig.svelte (NEW - plugin)
│       │   ├── SingleFileToolConfig.svelte (NEW - plugin)
│       │   └── [Future tool plugins...]
│       └── ToolPlaceholderBadge.svelte (NEW - shows placeholder)
└── PromptTemplateEditor.svelte (REFACTORED - dynamic placeholders)
```

### 3.3 Data Flow

```
┌──────────────────┐
│  AssistantForm   │
│                  │
│  tools = $state([│───────────┐
│    {...},        │           │
│    {...}         │           │
│  ])              │           │
└────────┬─────────┘           │
         │                     │
         │ props               │ events
         ▼                     │
┌──────────────────┐           │
│  ToolsManager    │           │
│                  │           │
│  Receives: tools │           │
│  Emits: change   │───────────┘
└────────┬─────────┘
         │
         │ props + events
         ▼
┌──────────────────┐
│ Tool Plugin      │
│ Components       │
│                  │
│ Receives: config │
│ Emits: update    │
└──────────────────┘
```

---

## 4. Data Model Changes

### 4.1 New Metadata Structure

**Proposed `metadata.tools` Array:**

```json
{
    "prompt_processor": "simple_augment",
    "connector": "openai",
    "llm": "gpt-4o-mini",
    "capabilities": {
        "vision": false,
        "image_generation": false
    },
    "verbose": false,
    "tools": [
        {
            "type": "knowledge_base",
            "enabled": true,
            "placeholder": "{context}",
            "config": {
                "collection_ids": ["abc123", "def456"],
                "top_k": 3
            }
        },
        {
            "type": "rubric",
            "enabled": true,
            "placeholder": "{rubric}",
            "config": {
                "rubric_id": "rubric_xyz",
                "format": "markdown"
            }
        },
        {
            "type": "single_file",
            "enabled": true,
            "placeholder": "{file}",
            "config": {
                "file_path": "user1/documents/reference.md"
            }
        }
    ]
}
```

**Verbose flag:** `verbose: true` enables a developer-facing trace (redacted) showing tool inputs (sans secrets), output lengths, and the prompt after substitution. Default `false`; UI should expose a toggle in AssistantForm and warn that outputs may include operational details.

### 4.2 Tool Type Definitions

```typescript
// TypeScript interfaces for documentation (implementation will be JSDoc)

interface ToolConfig {
    type: ToolType;
    enabled: boolean;
    placeholder: string;
    config: Record<string, unknown>;
}

type ToolType = 
    | 'knowledge_base'
    | 'rubric'
    | 'single_file'
    | 'assistant'  // Future: assistant as tool
    | 'image_gen'  // Future: image generation
    ;

interface KnowledgeBaseToolConfig {
    type: 'knowledge_base';
    enabled: boolean;
    placeholder: '{context}';
    config: {
        collection_ids: string[];
        top_k: number;
    };
}

interface RubricToolConfig {
    type: 'rubric';
    enabled: boolean;
    placeholder: '{rubric}';
    config: {
        rubric_id: string;
        format: 'markdown' | 'json';
    };
}

interface SingleFileToolConfig {
    type: 'single_file';
    enabled: boolean;
    placeholder: '{file}';
    config: {
        file_path: string;
    };
}
```

### 4.3 Tool Registry Structure

Each tool type needs a registry entry defining:

```javascript
// tools/registry.js
export const TOOL_REGISTRY = {
    knowledge_base: {
        type: 'knowledge_base',
        name: 'Knowledge Base',
        icon: '🗂️',
        description: 'Query knowledge bases for relevant context',
        placeholder: '{context}',
        component: 'KnowledgeBaseToolConfig',
        defaultConfig: {
            collection_ids: [],
            top_k: 3
        },
        // Can multiple instances exist?
        allowMultiple: false,
        // Validation function
        validate: (config) => config.collection_ids.length > 0
    },
    rubric: {
        type: 'rubric',
        name: 'Rubric',
        icon: '📋',
        description: 'Include assessment rubric in context',
        placeholder: '{rubric}',
        component: 'RubricToolConfig',
        defaultConfig: {
            rubric_id: '',
            format: 'markdown'
        },
        allowMultiple: false,
        validate: (config) => !!config.rubric_id
    },
    single_file: {
        type: 'single_file',
        name: 'Single File',
        icon: '📄',
        description: 'Include contents of a single file',
        placeholder: '{file}',
        component: 'SingleFileToolConfig',
        defaultConfig: {
            file_path: ''
        },
        allowMultiple: false,
        validate: (config) => !!config.file_path
    }
};
```

### 4.4 Backward Compatibility

**⚠️ IMPORTANT: Backend Handles All Migration**

The backend performs **migrate-on-access**: when a legacy assistant is fetched via `GET /assistants/{id}`, the backend automatically:
1. Detects legacy format (`_format_version` missing or < 2)
2. Migrates to new format with `tools[]` array
3. **Updates the database immediately**
4. Returns new format to frontend

**Frontend receives ONLY new format** - no legacy handling required in normal operation.

**Metadata Version Field:**

All metadata from backend includes `_format_version`:
```json
{
    "_format_version": 2,
    "tools": [...],
    "prompt_processor": "simple_augment",
    ...
}
```

**Frontend Parser (assumes new format):**

```javascript
function parseAssistantMetadata(metadata) {
    // Backend guarantees _format_version >= 2 after migration
    if (!metadata._format_version || metadata._format_version < 2) {
        // This should NEVER happen - backend migrates before returning
        console.error('Received legacy format from backend - this is a bug', metadata);
        return handleLegacyMetadataError(metadata);
    }
    
    return {
        formatVersion: metadata._format_version,
        tools: metadata.tools || [],
        promptProcessor: metadata.prompt_processor,
        connector: metadata.connector,
        llm: metadata.llm,
        capabilities: metadata.capabilities || {}
    };
}
```

**Defensive Fallback (should never execute):**

```javascript
function isLegacyMetadata(metadata) {
    // Should never be true if backend is working correctly
    return !metadata._format_version || metadata._format_version < 2;
}

function handleLegacyMetadataError(metadata) {
    // Log error - this indicates backend bug
    console.error('Legacy metadata received - backend migration may have failed', {
        metadata,
        hasVersion: !!metadata._format_version,
        hasTools: !!metadata.tools,
        hasRagProcessor: !!metadata.rag_processor
    });
    
    // Defensive fallback: treat as empty tools
    // User will need to reconfigure, but app won't crash
    return {
        _format_version: 2,
        tools: [],
        prompt_processor: metadata.prompt_processor || 'simple_augment',
        connector: metadata.connector || 'openai',
        llm: metadata.llm || 'gpt-4o-mini',
        capabilities: metadata.capabilities || {}
    };
}
```

**Key Point:** The frontend migration code from earlier versions is **no longer needed**. All migration happens server-side.

---

## 5. Component Architecture

### 5.1 New Directory Structure

```
frontend/svelte-app/src/lib/
├── components/
│   ├── assistants/
│   │   ├── AssistantForm.svelte          # Refactored (reduced)
│   │   ├── AssistantSharing.svelte       # Unchanged
│   │   ├── AssistantSharingModal.svelte  # Unchanged
│   │   └── tools/                         # NEW DIRECTORY
│   │       ├── ToolsManager.svelte        # Main orchestrator
│   │       ├── ToolSelector.svelte        # Add tool dropdown
│   │       ├── ToolConfigList.svelte      # List of active tools
│   │       ├── ToolConfigCard.svelte      # Card wrapper for tool
│   │       ├── ToolPlaceholderBadge.svelte
│   │       └── plugins/                   # Tool-specific configs
│   │           ├── KnowledgeBaseToolConfig.svelte
│   │           ├── RubricToolConfig.svelte
│   │           ├── SingleFileToolConfig.svelte
│   │           └── index.js               # Plugin registry
│   └── ...
├── stores/
│   ├── assistantConfigStore.js           # Add tool capabilities
│   └── toolStore.js                      # NEW: Tool state management
├── services/
│   ├── assistantService.js               # Add tool serialization
│   └── toolService.js                    # NEW: Tool-specific API calls
└── utils/
    └── toolUtils.js                       # NEW: Tool helpers
```

### 5.2 Component Specifications

#### 5.2.1 ToolsManager.svelte

**Purpose:** Main orchestrator for multi-tool management

**Props:**
```javascript
let {
    tools = [],           // Array of tool configurations
    disabled = false,     // Form editing disabled
    onchange = () => {}   // Callback when tools change
} = $props();
```

**State:**
```javascript
let availableTools = $state([]);  // Tools that can be added
let activeTools = $state([]);     // Currently configured tools
```

**Events:**
- `change` - Emits updated tools array
- `validation` - Emits validation status

**Template Structure:**
```svelte
<div class="tools-manager">
    <div class="tools-header">
        <h3>Tools Configuration</h3>
        <ToolSelector 
            {availableTools} 
            {activeTools}
            onadd={handleAddTool} 
        />
    </div>
    
    <ToolConfigList 
        tools={activeTools}
        {disabled}
        onupdate={handleToolUpdate}
        onremove={handleToolRemove}
        onreorder={handleToolReorder}
    />
    
    {#if activeTools.length === 0}
        <div class="no-tools-message">
            No tools configured. Add tools to enhance your assistant.
        </div>
    {/if}
</div>
```

#### 5.2.2 ToolSelector.svelte

**Purpose:** Dropdown to add new tools

**Props:**
```javascript
let {
    availableTools = [],  // All registered tools
    activeTools = [],     // Currently active (to filter out non-repeatable)
    onadd = () => {}      // Callback when tool selected
} = $props();
```

**Behavior:**
- Shows only tools that can be added (respects `allowMultiple`)
- Groups tools by category (future)
- Shows tool description on hover

**Template:**
```svelte
<div class="tool-selector">
    <button 
        class="add-tool-btn"
        onclick={toggleDropdown}
    >
        + Add Tool
    </button>
    
    {#if dropdownOpen}
        <div class="tool-dropdown">
            {#each selectableTools as tool}
                <button 
                    class="tool-option"
                    onclick={() => handleSelect(tool)}
                >
                    <span class="tool-icon">{tool.icon}</span>
                    <span class="tool-name">{tool.name}</span>
                    <span class="tool-placeholder">{tool.placeholder}</span>
                </button>
            {/each}
        </div>
    {/if}
</div>
```

#### 5.2.3 ToolConfigCard.svelte

**Purpose:** Wrapper card for each tool configuration

**Props:**
```javascript
let {
    tool = {},            // Tool configuration object
    toolMeta = {},        // Tool registry metadata
    disabled = false,
    onupdate = () => {},
    onremove = () => {},
    index = 0             // For reordering
} = $props();
```

**Template:**
```svelte
<div class="tool-card" class:disabled>
    <div class="tool-card-header">
        <span class="tool-icon">{toolMeta.icon}</span>
        <span class="tool-name">{toolMeta.name}</span>
        <ToolPlaceholderBadge placeholder={tool.placeholder} />
        
        <div class="tool-actions">
            <button onclick={handleToggleEnabled}>
                {tool.enabled ? '✓ Enabled' : '○ Disabled'}
            </button>
            <button onclick={() => onremove(index)}>
                Remove
            </button>
        </div>
    </div>
    
    <div class="tool-card-content">
        <!-- Dynamic plugin component -->
        <svelte:component 
            this={getPluginComponent(tool.type)}
            config={tool.config}
            {disabled}
            onchange={handleConfigChange}
        />
    </div>
</div>
```

### 5.3 Svelte 5 State Management

**Key Principles:**
1. Use `$state()` for component-local state
2. Use `$derived()` for computed values
3. Use `$effect()` sparingly for side effects
4. Pass data down via props, events up via callbacks

**Example Pattern:**

```javascript
// In ToolsManager.svelte
let tools = $state(initialTools);

// Derived: available placeholders
let activePlaceholders = $derived(
    tools
        .filter(t => t.enabled)
        .map(t => t.placeholder)
);

// Effect: notify parent when tools change
$effect(() => {
    onchange(tools);
});

// Handler for child updates
function handleToolUpdate(index, newConfig) {
    tools[index] = { ...tools[index], config: newConfig };
    // Svelte 5 reactivity handles the rest
}
```

---

## 6. Plugin System Design

### 6.1 Plugin Component Contract

Each tool plugin component must implement:

**Props (Input):**
```javascript
let {
    config = {},          // Tool-specific configuration
    disabled = false,     // Whether editing is disabled
    onchange = () => {}   // Callback for config updates
} = $props();
```

**Events (Output):**
- `change` - Emit updated config object
- `validate` - Emit validation status (optional)

**Methods (Optional):**
- `validate()` - Returns `{valid: boolean, errors: string[]}`
- `reset()` - Reset to default configuration

### 6.2 Plugin Registry

**Location:** `/lib/components/assistants/tools/plugins/index.js`

```javascript
import KnowledgeBaseToolConfig from './KnowledgeBaseToolConfig.svelte';
import RubricToolConfig from './RubricToolConfig.svelte';
import SingleFileToolConfig from './SingleFileToolConfig.svelte';

export const TOOL_PLUGINS = {
    knowledge_base: {
        component: KnowledgeBaseToolConfig,
        name: 'Knowledge Base',
        icon: '🗂️',
        description: 'Query knowledge bases for relevant context',
        placeholder: '{context}',
        defaultConfig: {
            collection_ids: [],
            top_k: 3
        },
        allowMultiple: false
    },
    rubric: {
        component: RubricToolConfig,
        name: 'Rubric',
        icon: '📋',
        description: 'Include assessment rubric in context',
        placeholder: '{rubric}',
        defaultConfig: {
            rubric_id: '',
            format: 'markdown'
        },
        allowMultiple: false
    },
    single_file: {
        component: SingleFileToolConfig,
        name: 'Single File',
        icon: '📄',
        description: 'Include contents of a single file',
        placeholder: '{file}',
        defaultConfig: {
            file_path: ''
        },
        allowMultiple: false
    }
};

export function getPluginComponent(toolType) {
    return TOOL_PLUGINS[toolType]?.component || null;
}

export function getPluginMeta(toolType) {
    return TOOL_PLUGINS[toolType] || null;
}

export function getAllPlugins() {
    return Object.entries(TOOL_PLUGINS).map(([type, meta]) => ({
        type,
        ...meta
    }));
}
```

### 6.3 Example Plugin: KnowledgeBaseToolConfig.svelte

```svelte
<script>
    import { tick, onMount } from 'svelte';
    import { getUserKnowledgeBases, getSharedKnowledgeBases } from '$lib/services/knowledgeBaseService';
    
    // Props (plugin contract)
    let {
        config = { collection_ids: [], top_k: 3 },
        disabled = false,
        onchange = () => {}
    } = $props();
    
    // Local state
    let ownedKBs = $state([]);
    let sharedKBs = $state([]);
    let loading = $state(false);
    let error = $state('');
    let fetchAttempted = $state(false);
    
    // Derived
    let allKBs = $derived([...ownedKBs, ...sharedKBs]);
    
    // Load KBs on mount
    onMount(async () => {
        await fetchKnowledgeBases();
    });
    
    async function fetchKnowledgeBases() {
        if (loading || fetchAttempted) return;
        
        loading = true;
        error = '';
        
        try {
            const [owned, shared] = await Promise.all([
                getUserKnowledgeBases(),
                getSharedKnowledgeBases()
            ]);
            ownedKBs = owned;
            sharedKBs = shared;
        } catch (err) {
            error = err.message || 'Failed to load knowledge bases';
        } finally {
            loading = false;
            fetchAttempted = true;
        }
    }
    
    function handleCollectionChange(event) {
        const checkbox = event.target;
        const kbId = checkbox.value;
        
        let newIds;
        if (checkbox.checked) {
            newIds = [...config.collection_ids, kbId];
        } else {
            newIds = config.collection_ids.filter(id => id !== kbId);
        }
        
        onchange({ ...config, collection_ids: newIds });
    }
    
    function handleTopKChange(event) {
        const value = parseInt(event.target.value, 10) || 3;
        onchange({ ...config, top_k: Math.min(10, Math.max(1, value)) });
    }
</script>

<div class="kb-tool-config">
    <!-- Top K Setting -->
    <div class="config-field">
        <label for="top-k">Results to retrieve (Top K)</label>
        <input 
            type="number" 
            id="top-k"
            value={config.top_k}
            oninput={handleTopKChange}
            min="1" 
            max="10"
            {disabled}
        />
    </div>
    
    <!-- Knowledge Base Selection -->
    <div class="config-field">
        <label>Knowledge Bases</label>
        
        {#if loading}
            <p class="loading">Loading knowledge bases...</p>
        {:else if error}
            <p class="error">{error}</p>
        {:else if allKBs.length === 0}
            <p class="empty">No knowledge bases available</p>
        {:else}
            <!-- Owned KBs -->
            {#if ownedKBs.length > 0}
                <div class="kb-section">
                    <h5>My Knowledge Bases</h5>
                    {#each ownedKBs as kb (kb.id)}
                        <label class="kb-item">
                            <input 
                                type="checkbox"
                                value={kb.id}
                                checked={config.collection_ids.includes(kb.id)}
                                onchange={handleCollectionChange}
                                {disabled}
                            />
                            <span>{kb.name}</span>
                        </label>
                    {/each}
                </div>
            {/if}
            
            <!-- Shared KBs -->
            {#if sharedKBs.length > 0}
                <div class="kb-section">
                    <h5>Shared Knowledge Bases</h5>
                    {#each sharedKBs as kb (kb.id)}
                        <label class="kb-item">
                            <input 
                                type="checkbox"
                                value={kb.id}
                                checked={config.collection_ids.includes(kb.id)}
                                onchange={handleCollectionChange}
                                {disabled}
                            />
                            <span>{kb.name} <small>(by {kb.shared_by})</small></span>
                        </label>
                    {/each}
                </div>
            {/if}
        {/if}
    </div>
    
    <!-- Validation Message -->
    {#if config.collection_ids.length === 0 && fetchAttempted}
        <p class="validation-warning">Please select at least one knowledge base</p>
    {/if}
</div>

<style>
    .kb-tool-config {
        padding: 0.5rem 0;
    }
    
    .config-field {
        margin-bottom: 1rem;
    }
    
    .kb-section {
        margin-top: 0.5rem;
        padding: 0.5rem;
        border: 1px solid #e2e8f0;
        border-radius: 0.375rem;
    }
    
    .kb-section h5 {
        font-size: 0.875rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .kb-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.25rem 0;
        cursor: pointer;
    }
    
    .kb-item:hover {
        background-color: #f8fafc;
    }
    
    .validation-warning {
        color: #dc2626;
        font-size: 0.75rem;
        margin-top: 0.25rem;
    }
</style>
```

### 6.4 Plugin Loading Strategy

**Dynamic Import (Future Enhancement):**

```javascript
// For large plugins or lazy loading
async function loadPluginComponent(toolType) {
    const pluginModule = await import(`./plugins/${toolType}ToolConfig.svelte`);
    return pluginModule.default;
}
```

**Initial Implementation: Static Imports:**

For MVP, use static imports in the registry to avoid complexity.

---

## 7. UI/UX Specifications

### 7.1 Tools Section Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  🛠️ Tools                                              [+ Add]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 🗂️ Knowledge Base                        {context}  [✓] [×] │ │
│  │ ─────────────────────────────────────────────────────────── │ │
│  │ Top K: [3 ▼]                                                │ │
│  │                                                              │ │
│  │ ☑ My Knowledge Bases:                                       │ │
│  │   ☑ CS101 Lectures                                          │ │
│  │   ☐ Python Tutorials                                        │ │
│  │                                                              │ │
│  │ ☑ Shared Knowledge Bases:                                   │ │
│  │   ☐ Department Resources (by Prof. Smith)                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 📋 Rubric                                {rubric}   [✓] [×] │ │
│  │ ─────────────────────────────────────────────────────────── │ │
│  │ Search: [________________] [🔍]                              │ │
│  │                                                              │ │
│  │ Selected: Essay Writing Rubric                               │ │
│  │                                                              │ │
│  │ ○ My Rubrics                                                 │ │
│  │   ● Essay Writing Rubric                                     │ │
│  │   ○ Code Review Rubric                                       │ │
│  │                                                              │ │
│  │ Format: (●) Markdown  ( ) JSON                               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 💡 Tip: Add tools to enhance your assistant's capabilities.  ││
│  │ Each tool injects content into its placeholder in the       ││
│  │ prompt template.                                             ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Add Tool Dropdown

```
┌─────────────────────────────────────┐
│            + Add Tool               │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ 🗂️ Knowledge Base     → {context}   │
│    Query multiple knowledge bases   │
├─────────────────────────────────────┤
│ 📋 Rubric             → {rubric}    │
│    Include assessment rubric        │
├─────────────────────────────────────┤
│ 📄 Single File        → {file}      │
│    Include file contents            │
├─────────────────────────────────────┤
│ 🤖 Assistant (coming) → {tool_out}  │ ← Grayed out
│    Use another assistant            │
└─────────────────────────────────────┘
```

### 7.3 Tool Card States

**Enabled State:**
- Full color, interactive
- Checkbox shows enabled
- All fields editable

**Disabled State:**
- Grayed out, non-interactive
- Checkbox shows disabled
- Placeholder still shows in list

**Collapsed State (Future):**
- Header only visible
- Click to expand

### 7.4 Placeholder Integration with Prompt Template

```
┌─────────────────────────────────────────────────────────────────┐
│  Prompt Template                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Insert placeholder: [{context}] [{rubric}] [{file}] [{user_in}]│
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Use the following context from knowledge bases:           │  │
│  │ {context}                                                 │  │
│  │                                                           │  │
│  │ Apply this rubric for assessment:                         │  │
│  │ {rubric}                                                  │  │
│  │                                                           │  │
│  │ User's question: {user_input}                             │  │
│  │                                                           │  │
│  │ Now provide a helpful response.                           │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  Preview with highlighted placeholders:                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Use the following context from knowledge bases:           │  │
│  │ [context]  ← Blue highlight                               │  │
│  │                                                           │  │
│  │ Apply this rubric for assessment:                         │  │
│  │ [rubric]   ← Blue highlight                               │  │
│  │ ...                                                       │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.5 Validation Indicators

**Tool-Level Validation:**
- Red border on tool card if invalid
- Warning icon next to tool name
- Tooltip with specific error

**Form-Level Validation:**
- Disabled save button if any tool invalid
- Summary of errors above save button

### 7.6 Streaming Status & Verbose Controls
- When `stream=true`, display markdown status events from backend in the chat stream before/alongside model tokens (e.g., “querying knowledge base {kb}”, “merging contexts”), in order received; style as muted/system messages and throttle to avoid spam.
- AssistantForm: add a `Verbose (developer trace)` toggle (default off) under advanced settings. When enabled, downstream UI can show trace metadata (redacted) such as tool input summaries and prompt-after-substitution.
- Redaction: do not display secrets, tokens, or tool content in status/verbose surfaces; show lengths and safe identifiers only.

---

## 8. Service Layer Changes

### 8.1 assistantService.js Modifications

**Add Tool Serialization:**

```javascript
/**
 * Serializes tools array to metadata JSON
 * @param {Array} tools - Array of tool configurations
 * @returns {Object} - Metadata object with tools
 */
export function serializeToolsToMetadata(tools) {
    return {
        tools: tools.map(tool => ({
            type: tool.type,
            enabled: tool.enabled,
            placeholder: tool.placeholder,
            config: { ...tool.config }
        }))
    };
}

/**
 * Deserializes metadata to tools array
 * @param {Object} metadata - Metadata object (may be legacy or new format)
 * @returns {Array} - Array of tool configurations
 */
export function deserializeToolsFromMetadata(metadata) {
    if (!metadata) return [];
    
    // Check for new format
    if (Array.isArray(metadata.tools)) {
        return metadata.tools;
    }
    
    // Handle legacy format
    return migrateLegacyMetadata(metadata).tools || [];
}
```

**Update createAssistant:**

```javascript
export async function createAssistant(assistantData) {
    // ... existing code ...
    
    // Merge tool configurations into metadata
    const metadataObj = {
        prompt_processor: assistantData.prompt_processor || 'simple_augment',
        connector: assistantData.connector || 'openai',
        llm: assistantData.llm || 'gpt-4o-mini',
        capabilities: assistantData.capabilities || {},
        verbose: !!assistantData.verbose,
        tools: assistantData.tools || []
    };
    
    const payload = {
        ...assistantData,
        metadata: JSON.stringify(metadataObj)
        // NOTE: No longer writing to legacy fields (RAG_collections, RAG_Top_k)
        // Backend reads exclusively from metadata.tools[] after migration
    };
    
    // ... rest of function ...
}
```

**Verbose handling:** Assistant load/save flows should read/write `metadata.verbose` (default `false`) and bind it to the UI toggle. Do not send verbose traces unless toggle enabled.

### 8.2 New toolService.js

```javascript
// lib/services/toolService.js

import { getApiUrl } from '$lib/config';
import { browser } from '$app/environment';

/**
 * Fetches available tool types from backend
 * @returns {Promise<Array>} - List of available tool types with metadata
 */
export async function getAvailableTools() {
    if (!browser) return [];
    
    const token = localStorage.getItem('userToken');
    if (!token) throw new Error('Not authenticated');
    
    try {
        const response = await fetch(getApiUrl('/system/tools'), {
            headers: { Authorization: `Bearer ${token}` }
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch available tools');
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error fetching tools:', error);
        // Return fallback from local registry
        return getFallbackToolList();
    }
}

/**
 * Validates a tool configuration
 * @param {string} toolType - The tool type
 * @param {Object} config - The tool configuration
 * @returns {Promise<{valid: boolean, errors: string[]}>}
 */
export async function validateToolConfig(toolType, config) {
    // Can be expanded to call backend validation
    const { TOOL_PLUGINS } = await import('$lib/components/assistants/tools/plugins');
    const plugin = TOOL_PLUGINS[toolType];
    
    if (!plugin) {
        return { valid: false, errors: ['Unknown tool type'] };
    }
    
    const isValid = plugin.validate ? plugin.validate(config) : true;
    return {
        valid: isValid,
        errors: isValid ? [] : ['Configuration is invalid']
    };
}

function getFallbackToolList() {
    return [
        { type: 'knowledge_base', name: 'Knowledge Base', available: true },
        { type: 'rubric', name: 'Rubric', available: true },
        { type: 'single_file', name: 'Single File', available: true }
    ];
}
```

---

## 9. Store Changes

### 9.1 assistantConfigStore.js Modifications

**Add Tool Capabilities:**

```javascript
// In fetchSystemCapabilities() response handling

const capabilities = capsResponse.data;

// Expected new structure from backend:
// {
//     prompt_processors: [...],
//     connectors: {...},
//     rag_processors: [...],  // Legacy - kept for backward compat
//     tools: [                 // NEW
//         { type: 'knowledge_base', available: true, ... },
//         { type: 'rubric', available: true, ... },
//         ...
//     ]
// }
```

### 9.2 New toolStore.js

```javascript
// lib/stores/toolStore.js

import { writable, derived } from 'svelte/store';
import { TOOL_PLUGINS, getAllPlugins } from '$lib/components/assistants/tools/plugins';

// Store for tool-related state that needs to be shared
function createToolStore() {
    const { subscribe, set, update } = writable({
        availableTools: getAllPlugins(),
        loading: false,
        error: null
    });
    
    return {
        subscribe,
        
        // Get plugin metadata by type
        getPluginMeta: (toolType) => {
            return TOOL_PLUGINS[toolType] || null;
        },
        
        // Get all available tool types
        getAvailableTypes: () => {
            return Object.keys(TOOL_PLUGINS);
        },
        
        // Check if a tool type can have multiple instances
        canAddMore: (toolType, currentTools) => {
            const plugin = TOOL_PLUGINS[toolType];
            if (!plugin) return false;
            
            if (plugin.allowMultiple) return true;
            
            // Check if already exists
            return !currentTools.some(t => t.type === toolType);
        },
        
        // Get default config for a tool type
        getDefaultConfig: (toolType) => {
            const plugin = TOOL_PLUGINS[toolType];
            return plugin ? { ...plugin.defaultConfig } : {};
        },
        
        // Create a new tool object
        createTool: (toolType) => {
            const plugin = TOOL_PLUGINS[toolType];
            if (!plugin) return null;
            
            return {
                type: toolType,
                enabled: true,
                placeholder: plugin.placeholder,
                config: { ...plugin.defaultConfig }
            };
        }
    };
}

export const toolStore = createToolStore();
```

---

## 10. Migration Strategy

### 10.1 Backend-Driven Migration (Simplified)

**The backend handles ALL data migration.** Frontend implementation is simplified:

| Concern | Handled By |
|---------|------------|
| Legacy format detection | Backend |
| Data migration | Backend (on access) |
| Database updates | Backend |
| Version tracking | Backend (`_format_version`) |

**Frontend only needs to:**
1. Build new multi-tool UI components
2. Assume all data from API is in new format
3. Include defensive error handling (should never trigger)

### 10.2 Frontend Implementation Phases

**Phase 1: Build New Components (1-2 weeks)**
- Create `ToolsManager`, `ToolSelector`, plugin components
- No integration with existing form yet
- Test with mock data in new format

**Phase 2: Integration (1 week)**
- Replace existing RAG processor UI with `ToolsManager`
- Update `populateFormFields()` to read `tools[]` array
- Update `handleSubmit()` to write `tools[]` array
- Feature flag for gradual rollout

**Phase 3: Cleanup (1 week)**
- Remove feature flag
- Remove old RAG processor dropdown UI
- Update documentation

### 10.3 What Frontend Does NOT Need

Since backend handles migration:
- ❌ No `migrateLegacyMetadata()` function needed
- ❌ No dual-format parsing logic
- ❌ No legacy field reading (`rag_processor`, etc.)
- ❌ No writing to legacy fields

### 10.4 Backward Compatibility Guarantee

| Scenario | What Happens |
|----------|--------------|
| User opens legacy assistant | Backend migrates → Frontend gets new format |
| User saves legacy assistant | Frontend writes new format only |
| API returns legacy format | **Bug** - Frontend logs error, shows empty tools |

### 10.3 Feature Flag Implementation

```javascript
// lib/config.js
export const FEATURE_FLAGS = {
    MULTI_TOOL_UI: import.meta.env.VITE_FEATURE_MULTI_TOOL === 'true'
};

// In AssistantForm.svelte
{#if FEATURE_FLAGS.MULTI_TOOL_UI}
    <ToolsManager {tools} onchange={handleToolsChange} />
{:else}
    <!-- Legacy RAG processor UI -->
    <select bind:value={selectedRagProcessor}>...</select>
    {#if selectedRagProcessor === 'simple_rag'}...{/if}
{/if}
```

---

## 11. Implementation Phases

### Phase 1: Foundation (Week 1-2)

| Task | Priority | Effort |
|------|----------|--------|
| Create `/tools/` directory structure | HIGH | S |
| Implement `TOOL_PLUGINS` registry | HIGH | S |
| Create `ToolsManager.svelte` shell | HIGH | M |
| Create `ToolSelector.svelte` | HIGH | S |
| Create `ToolConfigCard.svelte` | HIGH | M |
| Add `toolStore.js` | MED | S |

### Phase 2: Plugin Components (Week 2-3)

| Task | Priority | Effort |
|------|----------|--------|
| Extract `KnowledgeBaseToolConfig.svelte` from AssistantForm | HIGH | M |
| Extract `RubricToolConfig.svelte` from AssistantForm | HIGH | M |
| Extract `SingleFileToolConfig.svelte` from AssistantForm | HIGH | M |
| Implement plugin loading in ToolConfigCard | HIGH | S |
| Add validation to each plugin | MED | M |

### Phase 3: Integration (Week 3-4)

| Task | Priority | Effort |
|------|----------|--------|
| Integrate ToolsManager into AssistantForm | HIGH | M |
| Update `populateFormFields()` for multi-tool | HIGH | M |
| Update `handleSubmit()` for multi-tool | HIGH | M |
| Add legacy metadata migration | HIGH | M |
| Update prompt template placeholder buttons | MED | S |

### Phase 4: Polish & Testing (Week 4-5)

| Task | Priority | Effort |
|------|----------|--------|
| Add feature flag | MED | S |
| Comprehensive testing with existing assistants | HIGH | M |
| UI polish and accessibility | MED | M |
| Documentation updates | MED | S |
| Remove legacy code (after validation) | LOW | M |

**Legend:** S = Small (1-2 days), M = Medium (3-5 days), L = Large (1+ week)

---

## 12. Testing Requirements

### 12.1 Unit Tests

**Tool Plugin Tests:**
- Each plugin renders correctly
- Config changes emit events
- Validation works correctly
- Loading states handled

**ToolsManager Tests:**
- Adding tools works
- Removing tools works
- Tool enable/disable works
- Multiple tools can coexist

### 12.2 Integration Tests

**AssistantForm Integration:**
- Creating assistant with multiple tools
- Editing assistant with tools
- Saving persists tool configurations
- Loading displays correct tool configs
- Verbose toggle defaults off, persists on save, and surfaces trace panel only when enabled
- Streaming status events render as muted markdown system messages in order (no secrets shown)

**Legacy Compatibility:**
- Loading legacy single-RAG assistant
- Saving updates to new format
- No data loss during migration

### 12.3 E2E Tests (Playwright)

```javascript
// tests/multi-tool-assistant.spec.js

test('can create assistant with multiple tools', async ({ page }) => {
    await page.goto('/assistants');
    await page.click('[data-testid="create-assistant"]');
    
    // Add Knowledge Base tool
    await page.click('[data-testid="add-tool"]');
    await page.click('[data-testid="tool-option-knowledge_base"]');
    await page.click('[data-testid="kb-checkbox-abc123"]');
    
    // Add Rubric tool
    await page.click('[data-testid="add-tool"]');
    await page.click('[data-testid="tool-option-rubric"]');
    await page.click('[data-testid="rubric-radio-xyz"]');
    
    // Verify both tools visible
    expect(await page.locator('[data-testid="tool-card"]').count()).toBe(2);
    
    // Save and verify
    await page.click('[data-testid="save-assistant"]');
    await expect(page.locator('.success-message')).toBeVisible();
});

test('legacy assistant loads correctly', async ({ page }) => {
    // Navigate to existing legacy assistant
    await page.goto('/assistants?id=123');
    
    // Should show tool card for legacy RAG processor
    await expect(page.locator('[data-testid="tool-card"]')).toBeVisible();
});

test('verbose toggle shows trace metadata', async ({ page }) => {
    await page.goto('/assistants?id=123');
    await page.getByTestId('verbose-toggle').check();
    await page.click('[data-testid="save-assistant"]');
    
    await page.goto('/chat?id=123');
    await page.getByTestId('chat-input').fill('Test streaming');
    await page.getByTestId('chat-send').click();
    
    await expect(page.locator('[data-testid="status-event"]').first()).toContainText('querying knowledge base');
    await expect(page.locator('[data-testid="trace-panel"]')).toBeVisible();
    await expect(page.locator('[data-testid="trace-panel"]')).not.toContainText('sk-'); // redaction check
});
```

### 12.4 Manual Testing Checklist

- [ ] Create new assistant with no tools
- [ ] Create assistant with one tool
- [ ] Create assistant with multiple tools
- [ ] Edit existing legacy assistant
- [ ] Verify placeholder buttons update dynamically
- [ ] Verify validation prevents save with invalid tools
- [ ] Test tool enable/disable toggle
- [ ] Test tool removal
- [ ] Verify prompt template preview updates
- [ ] Test on mobile viewport

---

## Appendix A: File List Summary

### New Files to Create

```
frontend/svelte-app/src/lib/
├── components/assistants/tools/
│   ├── ToolsManager.svelte
│   ├── ToolSelector.svelte
│   ├── ToolConfigList.svelte
│   ├── ToolConfigCard.svelte
│   ├── ToolPlaceholderBadge.svelte
│   └── plugins/
│       ├── index.js
│       ├── KnowledgeBaseToolConfig.svelte
│       ├── RubricToolConfig.svelte
│       └── SingleFileToolConfig.svelte
├── stores/
│   └── toolStore.js
├── services/
│   └── toolService.js
└── utils/
    └── toolUtils.js
```

### Files to Modify

```
frontend/svelte-app/src/lib/
├── components/assistants/
│   └── AssistantForm.svelte        # Major refactor
├── stores/
│   └── assistantConfigStore.js     # Add tool capabilities
└── services/
    └── assistantService.js         # Add tool serialization
```

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Tool** | A configurable module that retrieves or generates content for an assistant |
| **Plugin** | A Svelte component that renders the configuration UI for a specific tool type |
| **Placeholder** | A template variable (e.g., `{context}`) that gets replaced with tool output |
| **Tool Registry** | Central mapping of tool types to their metadata and components |
| **Legacy Format** | Old metadata structure with `rag_processor` at top level |
| **New Format** | New metadata structure with `tools` array |

---

**Document Status:** Draft for Review  
**Author:** AI Analysis  
**Reviewers:** LAMB Development Team

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 9, 2025 | Initial specification |
| 1.1 | Dec 9, 2025 | Simplified migration: backend handles all migration, frontend only receives new format, removed frontend `migrateLegacyMetadata()`, removed legacy field writing |

