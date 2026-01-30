# LAMB Advanced Assistants TFG Project Proposal

---

## 1. Project Title

**"Multi-Tool, Flow-Aware, and Agentic Assistants for the LAMB Educational AI Platform"**

### 1.1 Abstract

This project extends the LAMB educational AI platform to support advanced assistant architectures beyond the current single-tool model. We propose three progressive capability levels: (1) **Multi-Tool** assistants that combine multiple knowledge sources and processing tools in a single response, (2) **Flow-Aware** assistants that detect conversation scenarios and adapt their behavior using LLM-based routing with state persistence, and (3) **Agentic** assistants implementing ReAct patterns for autonomous reasoning and tool execution. The project follows a prototype-driven methodology where key architectural decisions emerge through experimentation. A central challenge is maintaining LAMB's intuitive user interface while enabling sophisticated configurations for advanced creators, potentially through AI-assisted setup workflows. All enhancements preserve backwards compatibility with existing simple assistants.

---

## 2. Project Description

### 2.1 Context

LAMB (Learning Assistants Manager and Builder) currently supports "single-tool" assistants where each assistant has exactly one configuration of:
- **Connector** — LLM provider (OpenAI, Ollama, Anthropic, etc.)
- **Prompt Processor (PPS)** — Message augmentation logic
- **RAG Processor** — Knowledge retrieval strategy

This architecture serves simple use cases well but limits the creation of more sophisticated educational AI assistants that could:
- Combine multiple retrieval sources and processing tools
- Adapt behavior based on conversation context and flow
- Autonomously reason and use tools to solve complex problems

### 2.2 Problem Statement

**Current Limitations:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Current: Single-Tool Assistant                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User Message                                                   │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────┐                                               │
│   │ RAG         │  ← Only ONE RAG processor                     │
│   │ Processor   │                                               │
│   └──────┬──────┘                                               │
│          │                                                       │
│          ▼                                                       │
│   ┌─────────────┐                                               │
│   │ Prompt      │  ← Only ONE prompt processor                  │
│   │ Processor   │                                               │
│   └──────┬──────┘                                               │
│          │                                                       │
│          ▼                                                       │
│   ┌─────────────┐                                               │
│   │ Connector   │  ← Only ONE connector                         │
│   │ (LLM)       │                                               │
│   └─────────────┘                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Desired Capabilities (Three Progressive Kinds):**

| Kind | Name | Description | Complexity |
|------|------|-------------|------------|
| **1** | Multi-Tool | Combine multiple tools in single response | Medium |
| **2** | Flow-Aware | Different scenarios trigger different tool configurations | High |
| **3** | Agentic (ReAct) | Autonomous reasoning with tool execution loops | Very High |

### 2.3 Project Nature

This is an **exploratory, research-oriented project** with two main challenges:

1. **Technical (Medium)** — Fit advanced patterns into LAMB's architecture while maintaining scalability and maintainability

2. **User Interface (Hard)** — LAMB's current UI is intuitive; new users create assistants in minutes. Advanced features must not compromise this simplicity for basic use cases while enabling power users to build sophisticated assistants

**Methodology:** Prototyping-driven development with dynamic scope adjustment. Decisions will be made through experimentation rather than upfront specification.

---

## 3. Current Architecture Analysis

### 3.1 Existing Tool Ecosystem

| Tool Type | Examples | Description |
|-----------|----------|-------------|
| RAG Processors | `simple_rag`, `single_file_rag`, `context_aware_rag`, `no_rag` | Query knowledge bases for context |
| Prompt Processors | `simple_augment` | Transform messages, inject system prompts |
| Connectors | `openai`, `ollama`, `anthropic`, `banana_img` | Call LLM providers |
| Evaluators | Rubric tools | Evaluate responses against criteria |

**Notable:** `context_aware_rag` already uses an LLM to reformulate queries — this is a primitive form of "tool chaining" that can inform the multi-tool design.

### 3.2 Current Completion Pipeline

```python
# From lamb/completions/main.py (simplified)
async def process_completion(request, assistant):
    # 1. RAG Processing (single)
    rag_result = rag_processor(messages, assistant)
    
    # 2. Prompt Processing (single)  
    augmented_messages = prompt_processor(request, assistant, rag_result)
    
    # 3. LLM Call (single connector)
    response = await connector.llm_connect(augmented_messages, ...)
    
    return response
```

### 3.3 MCP Status

Current MCP implementation exists but should be **deprecated** in favor of a new, LAMB-native tool system designed for educational use cases.

---

## 4. Proposed Architecture

### 4.1 Kind 1: Multi-Tool Assistants

**Goal:** Allow assistants to use multiple tools in a single response generation.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Kind 1: Multi-Tool Assistant                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User Message                                                   │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Tool Orchestrator                           │   │
│   │                                                          │   │
│   │   ┌──────────┐  ┌──────────┐  ┌──────────┐             │   │
│   │   │ Tool A   │  │ Tool B   │  │ Tool C   │             │   │
│   │   │ (RAG-KB1)│  │ (RAG-KB2)│  │ (Rubric) │             │   │
│   │   └────┬─────┘  └────┬─────┘  └────┬─────┘             │   │
│   │        │             │             │                     │   │
│   │        └─────────────┼─────────────┘                     │   │
│   │                      │                                    │   │
│   │                      ▼                                    │   │
│   │              Context Aggregator                           │   │
│   └──────────────────────┬──────────────────────────────────┘   │
│                          │                                       │
│                          ▼                                       │
│                  ┌─────────────┐                                │
│                  │ Prompt      │                                │
│                  │ Processor   │                                │
│                  └──────┬──────┘                                │
│                         │                                        │
│                         ▼                                        │
│                  ┌─────────────┐                                │
│                  │ Connector   │                                │
│                  │ (LLM)       │                                │
│                  └─────────────┘                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Decisions to Explore:**
- Tool execution order (sequential vs parallel)
- Context sharing between tools
- Result aggregation strategies
- Error handling when one tool fails

### 4.2 Kind 2: Flow-Aware Assistants

**Goal:** Assistants that adapt their behavior based on conversation state and detected scenarios.

```
┌─────────────────────────────────────────────────────────────────┐
│                   Kind 2: Flow-Aware Assistant                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User Message + Conversation History                            │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │           Scenario Router (LLM + Rules)                  │   │
│   │                                                          │   │
│   │   "Which scenario matches this conversation state?"      │   │
│   │                                                          │   │
│   │   ┌─────────────────────────────────────────────────┐   │   │
│   │   │ Routing Prompt:                                  │   │   │
│   │   │ - Scenario A: Student asks conceptual question   │   │   │
│   │   │ - Scenario B: Student submits code for review    │   │   │
│   │   │ - Scenario C: Student requests hints             │   │   │
│   │   │ - Scenario D: Student seems frustrated           │   │   │
│   │   └─────────────────────────────────────────────────┘   │   │
│   └──────────────────────┬──────────────────────────────────┘   │
│                          │                                       │
│          ┌───────────────┼───────────────┐                      │
│          ▼               ▼               ▼                      │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐               │
│   │ Scenario A │  │ Scenario B │  │ Scenario C │               │
│   │            │  │            │  │            │               │
│   │ Tools: ... │  │ Tools: ... │  │ Tools: ... │               │
│   │ Prompt: .. │  │ Prompt: .. │  │ Prompt: .. │               │
│   └────────────┘  └────────────┘  └────────────┘               │
│                          │                                       │
│                          ▼                                       │
│                   Response + State Update                        │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Conversation State Store                    │   │
│   │   {                                                      │   │
│   │     "current_scenario": "B",                            │   │
│   │     "scenario_history": ["A", "A", "B"],                │   │
│   │     "custom_state": { ... }                             │   │
│   │   }                                                      │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Components:**
- **Scenario Router:** Fast LLM (gpt-4o-mini) + rule-based prompts to classify conversation state
- **Scenario Configurations:** Each scenario has its own tools + prompt template
- **State Persistence:** Track conversation flow across messages

**Key Decisions to Explore:**
- State storage mechanism (in LAMB DB vs OWI chat metadata)
- Scenario transition logic
- Default/fallback scenario handling
- State reset conditions

### 4.3 Kind 3: Agentic (ReAct) Assistants

**Goal:** Assistants that can autonomously reason, plan, and execute tools in loops.

```
┌─────────────────────────────────────────────────────────────────┐
│                   Kind 3: Agentic Assistant                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User Message                                                   │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    ReAct Loop                            │   │
│   │                                                          │   │
│   │   ┌──────────────────────────────────────────────────┐  │   │
│   │   │ Thought: I need to find information about X      │  │   │
│   │   │ Action: search_knowledge_base("X")               │  │   │
│   │   │ Observation: [results from KB]                   │  │   │
│   │   │                                                   │  │   │
│   │   │ Thought: Now I should check the rubric criteria  │  │   │
│   │   │ Action: evaluate_with_rubric(response, rubric_id)│  │   │
│   │   │ Observation: [rubric evaluation]                 │  │   │
│   │   │                                                   │  │   │
│   │   │ Thought: I have enough information to respond    │  │   │
│   │   │ Action: final_answer(...)                        │  │   │
│   │   └──────────────────────────────────────────────────┘  │   │
│   │                                                          │   │
│   │   Available Tools:                                       │   │
│   │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│   │   │ RAG      │ │ Rubric   │ │ External │ │ final_   │  │   │
│   │   │ Search   │ │ Evaluate │ │ API      │ │ answer   │  │   │
│   │   └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│   │                                                          │   │
│   │   Guardrails:                                            │   │
│   │   - Max iterations: 10                                   │   │
│   │   - Max tokens consumed: 50000                          │   │
│   │   - Timeout: 60 seconds                                 │   │
│   │   - Forbidden actions: [...]                            │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Components:**
- **ReAct Engine:** Implements Thought → Action → Observation loop
- **Tool Registry:** Available tools with schemas (separate from RAG-like augmentation tools)
- **Guardrails:** Safety limits on agent autonomy
- **Execution Sandbox:** Safe environment for tool execution

**Key Decisions to Explore:**
- Build vs integrate (LangChain, custom, etc.)
- Tool definition format
- Streaming intermediate thoughts to user
- Error recovery strategies

---

## 5. Data Model Extensions

### 5.1 Database Schema Additions

```sql
-- Tool definitions (unified tool registry)
CREATE TABLE tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    tool_type TEXT NOT NULL,           -- 'rag', 'processor', 'evaluator', 'external', 'agent_action'
    
    -- Configuration
    config JSON NOT NULL,              -- Tool-specific configuration
    
    -- Metadata
    organization_id INTEGER,           -- NULL = system tool
    owner_id INTEGER,                  -- NULL = system tool
    is_system BOOLEAN DEFAULT FALSE,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (owner_id) REFERENCES Creator_users(id)
);

-- Assistant tool configurations (Kind 1: Multi-tool)
CREATE TABLE assistant_tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id INTEGER NOT NULL,
    tool_id TEXT NOT NULL,
    
    -- Execution configuration
    execution_order INTEGER DEFAULT 0,
    is_enabled BOOLEAN DEFAULT TRUE,
    tool_config_override JSON,         -- Override default tool config
    
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE,
    FOREIGN KEY (tool_id) REFERENCES tools(id),
    UNIQUE(assistant_id, tool_id)
);

-- Scenarios for flow-aware assistants (Kind 2)
CREATE TABLE assistant_scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id INTEGER NOT NULL,
    
    name TEXT NOT NULL,
    description TEXT,
    
    -- Routing configuration
    routing_rules JSON,                -- Rule-based detection criteria
    routing_prompt TEXT,               -- LLM prompt for detection
    priority INTEGER DEFAULT 0,        -- Higher = checked first
    is_default BOOLEAN DEFAULT FALSE,  -- Fallback scenario
    
    -- Scenario configuration
    prompt_template TEXT,
    tools_config JSON,                 -- Tools to use in this scenario
    
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE
);

-- Conversation state persistence (Kind 2)
CREATE TABLE conversation_states (
    id TEXT PRIMARY KEY,               -- chat_id from OWI
    assistant_id INTEGER NOT NULL,
    
    current_scenario_id INTEGER,
    scenario_history JSON,             -- Array of past scenario IDs
    custom_state JSON,                 -- Scenario-specific state
    
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (assistant_id) REFERENCES assistants(id),
    FOREIGN KEY (current_scenario_id) REFERENCES assistant_scenarios(id)
);

-- Agent tool definitions (Kind 3: ReAct)
CREATE TABLE agent_tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,         -- For LLM to understand when to use
    
    -- Tool schema (JSON Schema format)
    parameters_schema JSON NOT NULL,
    
    -- Execution
    executor_type TEXT NOT NULL,       -- 'builtin', 'http', 'python'
    executor_config JSON NOT NULL,
    
    -- Safety
    requires_approval BOOLEAN DEFAULT FALSE,
    risk_level TEXT DEFAULT 'low',     -- 'low', 'medium', 'high'
    
    organization_id INTEGER,
    
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Agent configurations (Kind 3)
CREATE TABLE assistant_agent_config (
    assistant_id INTEGER PRIMARY KEY,
    
    -- Agent settings
    max_iterations INTEGER DEFAULT 10,
    max_tokens INTEGER DEFAULT 50000,
    timeout_seconds INTEGER DEFAULT 60,
    
    -- Available tools (JSON array of agent_tool IDs)
    enabled_tools JSON,
    
    -- Prompts
    system_prompt TEXT,
    thought_prompt TEXT,               -- Template for ReAct reasoning
    
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_assistant_tools_assistant ON assistant_tools(assistant_id);
CREATE INDEX idx_assistant_scenarios_assistant ON assistant_scenarios(assistant_id);
CREATE INDEX idx_conversation_states_assistant ON conversation_states(assistant_id);
```

### 5.2 Assistant Metadata Extension

```json
{
  "connector": "openai",
  "llm": "gpt-4o",
  "prompt_processor": "simple_augment",
  "rag_processor": "simple_rag",
  "capabilities": {
    "vision": true
  },
  
  "// NEW FIELDS": "───────────────────────────",
  
  "assistant_kind": "simple | multi_tool | flow_aware | agentic",
  
  "multi_tool_config": {
    "execution_mode": "sequential | parallel",
    "context_sharing": true,
    "aggregation_strategy": "concatenate | summarize"
  },
  
  "flow_config": {
    "router_model": "gpt-4o-mini",
    "state_ttl_hours": 24
  },
  
  "agent_config": {
    "enabled": true,
    "guardrails": {
      "max_iterations": 10,
      "require_approval_for": ["external_api"]
    }
  }
}
```

---

## 6. UI/UX Considerations

### 6.1 Design Principles

| Principle | Description |
|-----------|-------------|
| **Progressive Disclosure** | Simple mode by default; advanced features revealed on demand |
| **Backwards Compatible** | Existing simple assistant creation unchanged |
| **AI-Assisted** | Use AI to help configure complex assistants (like rubric creation) |
| **Visual When Helpful** | Consider visual builders for flows, but don't force complexity |

### 6.2 Target User: Advanced Creators

These features target educators who:
- Have created several simple assistants already
- Understand the concept of tools and prompts
- Need more sophisticated pedagogical interactions
- Are willing to invest time in configuration for better outcomes

### 6.3 UI Approach Options (To Explore)

**Option A: Mode Selector**
```
┌─────────────────────────────────────────────────────────────────┐
│  Create Assistant                                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Assistant Type:                                                 │
│                                                                  │
│  ○ Simple          Standard single-tool assistant               │
│                    [Current behavior]                            │
│                                                                  │
│  ○ Multi-Tool      Combine multiple knowledge sources           │
│                    and processing tools                          │
│                                                                  │
│  ○ Flow-Aware      Different behaviors for different            │
│                    conversation scenarios                        │
│                                                                  │
│  ○ Agentic         Autonomous reasoning with tool use           │
│                    [Advanced - Beta]                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Option B: Start Simple, Upgrade**
```
┌─────────────────────────────────────────────────────────────────┐
│  My Assistant (Simple)                              [Upgrade ▾] │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Upgrade menu]                                                  │
│  ┌─────────────────────────────────────┐                        │
│  │ + Add More Tools                    │                        │
│  │ + Add Conversation Flows            │                        │
│  │ + Enable Agentic Mode               │                        │
│  └─────────────────────────────────────┘                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Option C: AI Configuration Assistant**
```
┌─────────────────────────────────────────────────────────────────┐
│  🤖 Assistant Configuration Helper                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Describe what you want your assistant to do:                   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ I want an assistant that helps students with Python      │   │
│  │ programming. When they ask conceptual questions, it      │   │
│  │ should use Socratic method. When they submit code, it    │   │
│  │ should review it against our rubric. It should also be   │   │
│  │ able to search our course materials.                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  [Generate Configuration]                                        │
│                                                                  │
│  ──────────────────────────────────────────────────────────────│
│                                                                  │
│  Suggested Configuration:                                        │
│  • Type: Flow-Aware                                             │
│  • Scenarios:                                                    │
│    - Conceptual Question → Socratic prompt template             │
│    - Code Submission → Code review + Rubric evaluation          │
│    - General → Course materials RAG                             │
│                                                                  │
│  [Accept] [Modify] [Start Over]                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.4 Visual Flow Builder (Kind 2 - Optional)

```
┌─────────────────────────────────────────────────────────────────┐
│  Flow Editor                                        [Save] [Test]│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│      ┌──────────┐                                               │
│      │  START   │                                               │
│      └────┬─────┘                                               │
│           │                                                      │
│           ▼                                                      │
│      ┌──────────┐                                               │
│      │ Scenario │                                               │
│      │ Router   │                                               │
│      └────┬─────┘                                               │
│           │                                                      │
│     ┌─────┼─────┬─────────┐                                     │
│     │     │     │         │                                     │
│     ▼     ▼     ▼         ▼                                     │
│  ┌─────┐┌─────┐┌─────┐┌─────────┐                              │
│  │ Q&A ││Code ││Hints││ Default │                              │
│  │     ││Review│     │         │                              │
│  └─────┘└─────┘└─────┘└─────────┘                              │
│                                                                  │
│  [+ Add Scenario]                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Implementation Approach

### 7.1 Methodology: Prototype-Driven Development

```
┌─────────────────────────────────────────────────────────────────┐
│                    Development Cycle                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│   │ Research │───▶│Prototype │───▶│ Evaluate │───▶│  Decide  │ │
│   │          │    │          │    │          │    │          │ │
│   └──────────┘    └──────────┘    └──────────┘    └────┬─────┘ │
│        ▲                                                │       │
│        │                                                │       │
│        │          ┌──────────┐                         │       │
│        └──────────│  Refine  │◀────────────────────────┘       │
│                   │          │                                  │
│                   └──────────┘                                  │
│                                                                  │
│   Key: Make decisions through experimentation, not upfront      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Phase Overview

| Phase | Focus | Duration | Deliverables |
|-------|-------|----------|--------------|
| **0** | Foundation | 2 weeks | Tool registry, deprecate MCP |
| **1** | Kind 1: Multi-Tool | 6 weeks | Multi-tool orchestration + basic UI |
| **2** | Kind 2: Flow-Aware | 6 weeks | Scenario routing + state persistence |
| **3** | Kind 3: Agentic | 4 weeks | ReAct prototype (if time permits) |
| **4** | Polish & Docs | 4 weeks | Testing, documentation, refinement |

**Total: ~22 weeks** (scope adjusts dynamically based on progress)

### 7.3 Phase 0: Foundation (Weeks 1-2)

**Goals:**
- Create unified tool registry
- Deprecate existing MCP implementation
- Establish plugin architecture for new tool types

**Deliverables:**
- [ ] `tools` table and Tool model
- [ ] Tool registration API
- [ ] Migration of existing tools (RAG processors, rubrics) to registry
- [ ] MCP deprecation plan

**Key Questions to Answer:**
- Tool configuration format
- Tool versioning strategy

### 7.4 Phase 1: Multi-Tool Assistants (Weeks 3-8)

**Goals:**
- Enable assistants to use multiple tools
- Implement tool orchestration
- Create UI for tool selection

**Prototype Experiments:**
1. Sequential tool execution
2. Parallel tool execution
3. Context aggregation strategies
4. Error handling patterns

**Deliverables:**
- [ ] `assistant_tools` table
- [ ] Tool orchestrator service
- [ ] Context aggregator
- [ ] UI: Tool selection in assistant form
- [ ] At least 2 working multi-tool assistant examples

**Key Decisions (via prototyping):**
- Execution order (sequential vs parallel vs configurable)
- Context sharing mechanism
- Result aggregation method

### 7.5 Phase 2: Flow-Aware Assistants (Weeks 9-14)

**Goals:**
- Implement scenario routing
- Add conversation state persistence
- Create scenario configuration UI

**Prototype Experiments:**
1. LLM-based scenario classification
2. Rule-based scenario detection
3. Hybrid approaches
4. State persistence mechanisms

**Deliverables:**
- [ ] `assistant_scenarios` table
- [ ] `conversation_states` table
- [ ] Scenario router service
- [ ] State persistence service
- [ ] UI: Scenario editor
- [ ] At least 2 working flow-aware assistant examples

**Key Decisions (via prototyping):**
- Router prompt engineering
- State storage location
- Scenario transition smoothness
- Default scenario behavior

### 7.6 Phase 3: Agentic Assistants (Weeks 15-18)

**Goals:**
- Implement ReAct loop
- Create tool execution sandbox
- Add safety guardrails

**Note:** This phase may be reduced or extended based on progress in earlier phases.

**Prototype Experiments:**
1. Build vs integrate (LangChain, custom, etc.)
2. Tool definition formats
3. Streaming intermediate thoughts
4. Guardrail effectiveness

**Deliverables:**
- [ ] `agent_tools` table
- [ ] `assistant_agent_config` table
- [ ] ReAct engine
- [ ] Guardrails system
- [ ] UI: Agent tool configuration
- [ ] At least 1 working agentic assistant example

### 7.7 Phase 4: Polish & Documentation (Weeks 19-22)

**Goals:**
- Comprehensive testing
- Documentation
- Performance optimization
- Final refinements

**Deliverables:**
- [ ] Test suite (unit, integration, E2E)
- [ ] User documentation
- [ ] Technical documentation
- [ ] Performance benchmarks
- [ ] TFG memory

---

## 8. Technical Considerations

### 8.1 Backwards Compatibility

**Requirement:** Existing simple assistants MUST continue working unchanged.

**Strategy:**
```python
# In completion pipeline
if assistant.kind == "simple" or assistant.kind is None:
    # Use existing single-tool pipeline (unchanged)
    return await process_simple_completion(request, assistant)
elif assistant.kind == "multi_tool":
    return await process_multi_tool_completion(request, assistant)
elif assistant.kind == "flow_aware":
    return await process_flow_aware_completion(request, assistant)
elif assistant.kind == "agentic":
    return await process_agentic_completion(request, assistant)
```

### 8.2 Performance Considerations

| Concern | Mitigation |
|---------|------------|
| Multiple tool calls = latency | Parallel execution where possible |
| Scenario routing = extra LLM call | Use fast model (gpt-4o-mini), cache common patterns |
| Agent loops = many LLM calls | Strict guardrails, token budgets |
| State persistence = DB overhead | Efficient queries, consider caching |

### 8.3 Error Handling

```python
class ToolExecutionError(Exception):
    """Raised when a tool fails to execute"""
    def __init__(self, tool_id: str, message: str, recoverable: bool = True):
        self.tool_id = tool_id
        self.recoverable = recoverable
        super().__init__(message)

# Strategy: Graceful degradation
async def execute_tools(tools: List[Tool], context: Context):
    results = []
    for tool in tools:
        try:
            result = await tool.execute(context)
            results.append(result)
        except ToolExecutionError as e:
            if e.recoverable:
                logger.warning(f"Tool {e.tool_id} failed, continuing without it")
                results.append(ToolResult.empty())
            else:
                raise
    return results
```

### 8.4 Testing Strategy

| Level | Focus | Tools |
|-------|-------|-------|
| Unit | Individual tools, orchestrator logic | pytest |
| Integration | Tool combinations, state persistence | pytest + test DB |
| E2E | Full assistant interactions | Playwright |
| Manual | UI/UX, edge cases | Human testing |

---

## 9. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Scope creep | High | High | Strict phase gates, dynamic scope adjustment |
| UI complexity overwhelming users | High | Medium | Progressive disclosure, user testing |
| Performance degradation | Medium | Medium | Early benchmarking, optimization sprints |
| Breaking existing assistants | High | Low | Comprehensive backwards compatibility tests |
| Agent safety issues | High | Medium | Conservative guardrails, approval workflows |
| Time underestimation | Medium | Medium | Flexible scope, prioritized features |

---

## 10. Success Criteria

### Minimum Viable Success (Must Have)

- [ ] Multi-tool assistants work with at least 3 tools combined
- [ ] Existing simple assistants unchanged
- [ ] Basic UI for configuring multi-tool assistants
- [ ] Documentation for all implemented features

### Target Success (Should Have)

- [ ] Flow-aware assistants with scenario routing
- [ ] State persistence across conversations
- [ ] UI for scenario configuration
- [ ] At least 3 example assistants demonstrating each kind

### Stretch Goals (Nice to Have)

- [ ] Agentic assistants with ReAct loop
- [ ] AI-assisted configuration helper
- [ ] Visual flow builder
- [ ] Comprehensive test coverage (>80%)

---

## 11. Open Questions (To Answer During Project)

### Technical
1. Tool execution order: sequential, parallel, or configurable?
2. Context sharing: shared context object or isolated?
3. Agent framework: build custom or integrate existing?
4. State persistence: LAMB DB or OWI chat metadata?

### UX
1. Best UI pattern for progressive complexity?
2. Should AI-assisted configuration be core feature?
3. Visual flow builder: necessary or overkill?
4. How to preview/test complex assistants before deployment?

### Educational
1. What pedagogical patterns need flow-awareness?
2. What agent tools are most valuable for education?
3. How to prevent misuse of agentic capabilities?

---

## 12. References

### LAMB Documentation
- [LAMB Architecture v2](../lamb_architecture_v2.md)
- [Completion Pipeline](../lamb_architecture.md#completion-pipeline)
- [Plugin System](../lamb_architecture.md#plugin-system)

### External References
- ReAct: Synergizing Reasoning and Acting in Language Models (Yao et al., 2022)
- LangChain Documentation: https://python.langchain.com/
- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling

---

## 13. Appendix

### A. Current Tool Implementations

| File | Type | Description |
|------|------|-------------|
| `lamb/completions/rag/simple_rag.py` | RAG | Basic knowledge base query |
| `lamb/completions/rag/single_file_rag.py` | RAG | Single file context injection |
| `lamb/completions/rag/context_aware_rag.py` | RAG | LLM-reformulated queries |
| `lamb/completions/pps/simple_augment.py` | PPS | Standard prompt augmentation |
| `creator_interface/evaluaitor_router.py` | Evaluator | Rubric-based evaluation |

### B. Glossary

| Term | Definition |
|------|------------|
| Tool | A processing component that can augment, transform, or generate context |
| RAG | Retrieval-Augmented Generation |
| PPS | Prompt Processing System |
| ReAct | Reasoning + Acting pattern for LLM agents |
| Scenario | A conversation state that triggers specific assistant behavior |
| Flow | The progression through different scenarios in a conversation |
| Guardrails | Safety limits on agent autonomy |

---

*Project proposal for LAMB Advanced Assistants*  
*Dynamic scope — decisions through prototyping*
