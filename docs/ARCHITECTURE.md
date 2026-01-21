# Firestarter Architecture

## Overview

Firestarter is an AI-powered penetration testing assistant platform designed for enterprise-grade security research and authorized penetration testing. The architecture follows a cognitive cyber range model with clear separation of concerns between frameworks.

## Architecture Diagram

```
[ UI / API ]
      |
[ Conversation Manager ]
      |
[ LangGraph Orchestrator ]
      |
[ AutoGen Agent Swarm ]
      |
[ Tool Executors ]
      |
[ Memory Layer ]
   |        |        |
 Redis   Postgres  VectorDB (pgvector)
```

## Component Responsibilities

### UI / API Layer
- **Role**: User interface and API endpoints
- **Components**: `main.py`, `api/` directory
- **Responsibilities**: 
  - User interaction
  - Conversation management UI
  - Streaming display
  - Model selection

### Conversation Manager
- **Role**: Manage conversation lifecycle and context switching
- **Components**: `api/conversation_api.py`, `memory/conversation_store.py`
- **Responsibilities**:
  - Create/load/switch conversations
  - Manage conversation metadata
  - Handle conversation state persistence

### LangGraph Orchestrator
- **Role**: Workflow control and state machine
- **Components**: `agents/pentest_graph.py`
- **Responsibilities**:
  - State machine execution
  - Conditional routing between nodes
  - Human-in-the-loop coordination
  - Workflow orchestration
- **NOT responsible for**:
  - Memory storage (uses Memory Layer)
  - Tool execution (delegates to Tool Executors)
  - LLM calls (uses Model Layer)

### AutoGen Agent Swarm
- **Role**: Multi-agent coordination and role-based task execution
- **Components**: `agents/autogen_agents.py`
- **Responsibilities**:
  - Agent role assignment (ReconAgent, ExploitAgent, AnalysisAgent)
  - Agent-to-tool mapping
  - Agent dialog coordination
- **NOT responsible for**:
  - Workflow control (LangGraph handles this)
  - Memory management (uses Memory Layer)
  - Tool implementation (uses Tool Registry)

### Tool Executors
- **Role**: Execute security tools with policy enforcement
- **Components**: `tools/executor.py`, `tools/registry.py`, `agents/policy_engine.py`
- **Responsibilities**:
  - Tool execution with parameter validation
  - Policy enforcement (scope, authorization, risk)
  - Result storage
- **Dependencies**: Tool Registry for metadata, Policy Engine for authorization

### Memory Layer

#### Redis (Volatile Memory)
- **Role**: Short-term working memory
- **Usage**: 
  - Conversation buffer (active conversation)
  - Active context (current session state)
  - Temporary cache
- **NOT used for**:
  - Persistent data (use Postgres)
  - Semantic search (use pgvector)

#### PostgreSQL (Source of Truth)
- **Role**: Persistent data storage and audit trail
- **Tables**:
  - `conversations`: Conversation metadata
  - `agent_states`: Agent state snapshots
  - `tool_executions`: Tool execution history (audit)
  - `verified_targets`: Verified target domains/IPs
- **Responsibilities**:
  - Data persistence
  - Audit logging
  - Transaction management
- **NOT used for**:
  - Semantic search (use pgvector)
  - Temporary cache (use Redis)

#### pgvector (Semantic Memory)
- **Role**: Vector embeddings for semantic search
- **Tables**:
  - `vector_embeddings`: Conversation context and tool results
- **Responsibilities**:
  - Semantic similarity search
  - Context retrieval (RAG)
  - Tool results retrieval
- **NOT used for**:
  - Structured queries (use Postgres)
  - Temporary data (use Redis)

## Framework Roles (Critical Separation)

### LangChain
- **ONLY used for**:
  - Tool wrapper: `OllamaLLMClient`, `OllamaEmbeddingClient`
  - Embeddings: `OllamaEmbeddings` from LangChain
- **NOT used for**:
  - Memory management (custom implementation)
  - Agent orchestration (LangGraph handles this)
  - Workflow control (LangGraph handles this)

### LlamaIndex
- **ONLY used for**:
  - Knowledge base ingestion (CVE, exploits, IOC data)
  - Structured knowledge retrieval (CVE/exploit/IOC queries)
- **NOT used for**:
  - Conversation context (custom RAG handles this)
  - Tool results storage (custom implementation)
  - Memory management (custom implementation)

### AutoGen
- **ONLY used for**:
  - Agent role definitions (ReconAgent, ExploitAgent, AnalysisAgent)
  - Agent dialog coordination
- **NOT used for**:
  - Workflow orchestration (LangGraph handles this)
  - Memory management (custom implementation)
  - Tool execution (custom Tool Executor handles this)

### LangGraph
- **ONLY used for**:
  - State machine definition
  - Workflow control (conditional edges, routing)
  - Human-in-the-loop nodes
- **NOT used for**:
  - Memory storage (delegates to Memory Layer)
  - LLM calls (delegates to Model Layer)
  - Tool execution (delegates to Tool Executors)

## Data Flow

### 1. User Request Flow

```
User Input
  ↓
Conversation Manager (create/load conversation)
  ↓
LangGraph Orchestrator (workflow)
  ↓
Intent Classification
  ↓
Analysis Node (task breakdown)
  ↓
Recommend Tools (Human-in-the-loop)
  ↓
Policy Check (scope, authorization)
  ↓
Tool Execution (with policy enforcement)
  ↓
Result Storage (Postgres + pgvector)
  ↓
Synthesis (combine results)
  ↓
Response to User
```

### 2. Memory Flow

**Writing**:
```
Tool Result → ToolResultsStorage → pgvector (embedding + storage)
Conversation Message → ConversationStore → Postgres + Redis (buffer)
Agent State → MemoryManager → Postgres (agent_states table)
```

**Reading**:
```
User Query → RAG Retriever → pgvector (semantic search)
Conversation Context → MemoryManager → Redis (buffer) + Postgres (persistent)
Tool Results → ResultsStorage → pgvector (semantic search with filters)
```

### 3. Context Flow

**For Analysis**:
```
User Prompt
  + Conversation History (Redis buffer + Postgres)
  + Previous Tool Results (pgvector semantic search)
  + Active Entities (Postgres)
  + Open Tasks (Postgres)
  ↓
Analysis Agent (task breakdown)
```

**For Tool Execution**:
```
Subtask
  + Tool Metadata (Tool Registry)
  + Authorized Scope (Postgres)
  + Execution Mode (GraphState)
  ↓
Policy Engine (authorization check)
  ↓
Tool Executor (execute with parameters)
  ↓
Result Storage (Postgres + pgvector)
```

## Key Design Principles

### 1. Separation of Concerns
- Each framework has a single, well-defined role
- No overlap in responsibilities
- Clear interfaces between components

### 2. Policy-First Architecture
- All tool executions go through Policy Engine
- Scope validation before execution
- Authorization checks at multiple levels
- Audit trail in Postgres

### 3. Human-in-the-Loop
- Tool recommendations require user approval
- Scope expansion requires confirmation
- High-risk operations require explicit permission

### 4. Memory Hierarchy
- **Redis**: Fast, volatile (working memory)
- **Postgres**: Persistent, structured (source of truth)
- **pgvector**: Semantic, searchable (context retrieval)

### 5. Security Research Context
- All system prompts include defensive research context
- Reduces model refusal by framing activities correctly
- Legal and ethical boundaries clearly defined

## Component Dependencies

```
LangGraph Orchestrator
  ├── Depends on: Memory Manager, Context Manager, Tool Executor
  ├── Uses: AutoGen Agents (for agent selection)
  └── Uses: Model Layer (for LLM calls)

AutoGen Agents
  ├── Depends on: Tool Registry (for available tools)
  └── Uses: Model Layer (for agent LLM calls)

Tool Executor
  ├── Depends on: Tool Registry (for tool definitions)
  ├── Depends on: Policy Engine (for authorization)
  └── Depends on: Results Storage (for storing results)

Memory Manager
  ├── Depends on: Conversation Store (Postgres)
  ├── Depends on: RAG Retriever (pgvector)
  └── Depends on: Redis (for buffer)

Policy Engine
  ├── Depends on: Scope Manager (for scope validation)
  ├── Depends on: Tool Registry (for tool metadata)
  └── Depends on: Mode Manager (for mode compatibility)
```

## Extension Points

### Adding New Tools
1. Add tool definition to `tools/metadata/tools.json`
2. Implement tool execution in `tools/implementations/`
3. Update Tool Registry schema if needed
4. Add policy rules in Policy Engine if required

### Adding New Agents
1. Add agent definition to `agents/autogen_agents.py`
2. Create agent prompt in `prompts/autogen_*.jinja2`
3. Update AutoGen coordinator
4. Add agent-to-tool mapping

### Adding New Workflow Nodes
1. Add node method to `agents/pentest_graph.py`
2. Update graph edges in `_build_graph()`
3. Update GraphState TypedDict if needed
4. Add routing logic if conditional

## Security Considerations

### Policy Enforcement
- All tool executions require policy check
- Scope validation prevents unauthorized targets
- Mode switching controls execution level
- Audit logging for compliance

### Memory Isolation
- Conversation-specific vector namespaces
- Agent state isolation per conversation
- Scope isolation per conversation
- No cross-conversation data leakage

### Legal Compliance
- Security Research Context in all prompts
- Explicit authorization requirements
- Audit trail in Postgres
- Scope validation before execution

## Performance Considerations

### Memory Layer
- Redis for fast buffer access
- Postgres for persistent data
- pgvector with indexes for fast semantic search

### Context Management
- Summary compression for long conversations
- Tool result summarization to prevent context explosion
- Selective context retrieval based on relevance

### Tool Execution
- Asynchronous execution where possible
- Result caching for repeated queries
- Efficient parameter validation

## Future Enhancements

1. **Attack Simulation DSL**: Abstract attack graph language
2. **Enhanced Policy Engine**: More granular policy rules
3. **Distributed Execution**: Multi-machine tool execution
4. **Enhanced Summarization**: Better topic extraction and entity-based summarization
5. **Audit Dashboard**: Visual audit trail and compliance reporting
