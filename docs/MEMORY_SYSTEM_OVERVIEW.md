# Memory System Overview - Firestarter

## Tổng Quan

Folder `memory/` quản lý toàn bộ hệ thống memory cho Firestarter, bao gồm:
- **Persistent Storage**: PostgreSQL cho conversation history và metadata
- **Short-term Buffer**: Redis cho fast access
- **Session Memory**: In-memory context cho agents
- **Summary Compression**: Tự động compress long conversations
- **Namespace Isolation**: Multi-conversation support

## Kiến Trúc Tổng Thể

```
┌─────────────────────────────────────────────────────────────┐
│                    MemoryManager                            │
│  (memory/manager.py) - Orchestrator                         │
│                                                              │
│  Components:                                                 │
│  ├── conversation_store: ConversationStore                  │
│  │   └── PostgreSQL (persistent)                           │
│  ├── redis_buffer: RedisBuffer                              │
│  │   └── Redis (short-term, fast)                          │
│  ├── summary_compressor: SummaryCompressor                  │
│  │   └── LLM-based compression                              │
│  ├── namespace_manager: NamespaceManager                    │
│  │   └── Isolation & state management                       │
│  └── session_memory: SessionMemory                          │
│      └── agent_context: AgentContext                        │
│          └── In-memory shared context                       │
└─────────────────────────────────────────────────────────────┘
```

## Chi Tiết Từng File

### 1. `memory/manager.py` - MemoryManager (Orchestrator)

**Vai trò**: Component chính, điều phối tất cả memory operations.

**Chức năng chính**:
- **Conversation Management**: `start_conversation()`, `get_or_create_session()`
- **Message Handling**: `save_turn()`, `add_to_conversation_buffer()`, `get_conversation_buffer()`
- **Context Retrieval**: `retrieve_context()` - semantic search với ranking
- **Agent Context Updates**: `update_agent_context()` - update findings (subdomains, ports, vulns, etc.)
- **State Persistence**: Save/load agent state qua PostgreSQL và Redis

**Data Flow**:
```
save_turn()
  ├── ConversationStore.add_message() [PostgreSQL - persistent]
  ├── RedisBuffer.add_message() [Redis - short-term]
  ├── ConversationRetriever.add_conversation() [Vector DB - semantic]
  ├── SummaryCompressor.auto_compress_if_needed() [Auto-compress if > threshold]
  └── NamespaceManager.save_agent_state() [PostgreSQL - agent state]
```

**Dependencies**:
- `ConversationStore` (PostgreSQL)
- `RedisBuffer` (Redis)
- `SummaryCompressor` (LLM compression)
- `NamespaceManager` (Isolation)
- `SessionMemory` (In-memory context)
- `ConversationRetriever` (RAG - semantic search)
- `ToolResultsStorage` (RAG - tool results)

---

### 2. `memory/conversation_store.py` - ConversationStore

**Vai trò**: Persistent storage cho conversation metadata và messages (PostgreSQL).

**Chức năng chính**:
- `create_conversation()`: Tạo conversation mới, return `conversation_id`
- `get_conversation()`: Lấy conversation metadata
- `add_message()`: Thêm message vào conversation
- `get_messages()`: Lấy tất cả messages của conversation
- `get_recent_messages()`: Lấy N messages gần nhất
- `update_verified_target()`: Update verified target domain
- `list_conversations()`: List tất cả conversations

**Database Schema** (PostgreSQL):
- `conversations` table: id, title, session_id, created_at, updated_at, verified_target, summary, metadata
- `messages` table: id, conversation_id, role, content, created_at

**Storage Strategy**:
- **Persistent**: Tất cả messages được lưu vào PostgreSQL
- **Metadata**: Conversation metadata (title, verified_target, summary) trong `conversations` table
- **Messages**: Full conversation history trong `messages` table

---

### 3. `memory/redis_buffer.py` - RedisBuffer

**Vai trò**: Short-term memory buffer cho fast access (Redis).

**Chức năng chính**:
- `add_message()`: Thêm message vào Redis buffer (sliding window)
- `get_recent_messages()`: Lấy N messages gần nhất (max 50)
- `set_state()`: Lưu agent state vào Redis
- `get_state()`: Lấy agent state từ Redis
- `health_check()`: Kiểm tra Redis connection

**Storage Strategy**:
- **TTL**: Default 1 hour (3600s) - tự động cleanup
- **Max Messages**: 50 messages per conversation (sliding window)
- **Keys**: `firestarter:buffer:{conversation_id}:messages`, `firestarter:buffer:{conversation_id}:state`

**Use Cases**:
- Fast access cho recent messages
- Temporary agent state caching
- Chain-of-thought reasoning storage

---

### 4. `memory/session.py` - SessionMemory & AgentContext

**Vai trò**: In-memory shared context cho agents trong session.

**Components**:

#### `AgentContext` (Dataclass)
**Vai trò**: "Message board" cho inter-agent communication.

**Structured Data**:
- **Target Info**: `domain`, `targets`, `legal_name`, `target_country`, `target_asn`, `target_ip_ranges`
- **Phase 1 - Recon**: `subdomains`, `ips`, `asns`, `emails`, `technologies`, `dns_records`
- **Phase 2 - Scan**: `open_ports`, `services`, `directories`, `endpoints`
- **Phase 3 - Vuln**: `vulnerabilities`, `misconfigs`, `cves`
- **Phase 4 - Exploit**: `exploits_attempted`, `successful_exploits`, `credentials`, `shells`
- **Phase 5 - Post-Exploit**: `privilege_escalations`, `lateral_movements`, `persistence`
- **Metadata**: `tools_run`, `last_updated`, `active_entities`, `open_tasks`, `topics`, `authorized_scope`

**Methods**:
- `add_subdomain()`, `add_ip()`, `add_port()`, `add_vulnerability()`, etc.
- `add_active_entity()`, `add_open_task()`, `add_topic()`
- `get_targets_for_scanning()`, `get_high_value_targets()`
- `to_dict()`: Serialization

#### `SessionMemory` (Class)
**Vai trò**: Wrapper cho `AgentContext` với session management.

**Chức năng**:
- Quản lý `AgentContext` instance
- Serialization: `to_dict()`, `from_dict()`
- Session ID tracking

**Lifecycle**:
- **Volatile**: In-memory only (không persist trực tiếp)
- **Persisted**: Qua `MemoryManager.save_turn()` → PostgreSQL + Redis

---

### 5. `memory/summary_compressor.py` - SummaryCompressor

**Vai trò**: Tự động compress long conversations để giảm context size.

**Chức năng chính**:
- `should_compress()`: Check nếu message count >= threshold (default: 100)
- `compress()`: Compress old messages thành summary bằng LLM
- `auto_compress_if_needed()`: Tự động compress khi cần

**Compression Strategy**:
- **Threshold**: 100 messages (configurable)
- **Model**: Mistral (default) hoặc configurable
- **Prompt**: Extract key info (targets, findings, tools, vulns), preserve context
- **Storage**: Summary lưu vào `conversations.summary` (PostgreSQL)

**Use Cases**:
- Long conversations (> 100 messages)
- Context window management
- Reduce token usage

---

### 6. `memory/namespace_manager.py` - NamespaceManager

**Vai trò**: Quản lý namespace isolation cho multi-conversation.

**Chức năng chính**:
- `get_vector_namespace()`: Tạo unique collection name cho conversation
  - Format: `conversation_{conversation_id}`
- `get_state_namespace()`: Tạo state store key
  - Format: `state:{conversation_id}`
- `load_conversation_context()`: Load toàn bộ context cho conversation
  - Returns: conversation metadata, messages, summary, agent_state, verified_target, topics, active_entities, open_tasks
- `save_agent_state()`: Lưu agent state vào PostgreSQL
- `load_agent_state()`: Load agent state từ PostgreSQL

**Isolation Strategy**:
- Mỗi conversation có unique namespace
- Vector DB collections: `conversation_{conversation_id}`
- State keys: `state:{conversation_id}`
- Không có cross-conversation leakage

---

## Data Flow Diagrams

### 1. Conversation Start Flow

```
User starts conversation
    │
    ▼
MemoryManager.start_conversation()
    │
    ├──► ConversationStore.create_conversation()
    │   └──► PostgreSQL: INSERT INTO conversations
    │
    ├──► SessionMemory(session_id=conversation_id)
    │   └──► AgentContext() [Initialize empty context]
    │
    └──► RedisBuffer (optional, for fast access)
```

### 2. Message Save Flow

```
User sends message
    │
    ▼
MemoryManager.save_turn(user_msg, assistant_msg)
    │
    ├──► ConversationStore.add_message()
    │   └──► PostgreSQL: INSERT INTO messages
    │
    ├──► RedisBuffer.add_message()
    │   └──► Redis: SET firestarter:buffer:{conv_id}:messages
    │
    ├──► ConversationRetriever.add_conversation()
    │   └──► Vector DB: Embed & store for semantic search
    │
    ├──► SummaryCompressor.auto_compress_if_needed()
    │   └──► If message_count >= 100:
    │       └──► LLM compress → PostgreSQL: UPDATE conversations.summary
    │
    └──► NamespaceManager.save_agent_state()
        └──► PostgreSQL: Save agent_context to state store
```

### 3. Context Retrieval Flow

```
Agent needs context
    │
    ▼
MemoryManager.retrieve_context(query, k=5)
    │
    ├──► ConversationRetriever.retrieve_context()
    │   └──► Vector DB: Semantic search với ranking
    │       └──► Returns: Top K relevant messages
    │
    ├──► ToolResultsStorage.retrieve_results()
    │   └──► Vector DB: Semantic search tool results
    │       └──► Returns: Top K relevant tool results
    │
    ├──► MemoryManager.get_conversation_buffer()
    │   ├──► RedisBuffer.get_recent_messages() [Priority 1]
    │   ├──► ConversationStore.get_messages() [Priority 2]
    │   └──► Legacy in-memory buffer [Fallback]
    │
    └──► Return combined context:
        {
            "conversation_context": [...],
            "tool_results": [...],
            "conversation_buffer": [...],
            "session_memory": {...},
            "verified_target": "..."
        }
```

### 4. Agent Context Update Flow

```
Tool execution finds new data
    │
    ▼
MemoryManager.update_agent_context(updates)
    │
    └──► SessionMemory.agent_context.add_*()
        ├──► add_subdomains() → Update subdomains list
        ├──► add_ip() → Update IPs list
        ├──► add_port() → Update open_ports list
        ├──► add_vulnerability() → Update vulnerabilities list
        └──► add_active_entity() → Track active entities
        │
        └──► [On save_turn()]
            └──► NamespaceManager.save_agent_state()
                └──► PostgreSQL: Persist agent_context
```

## Storage Layers

### Layer 1: In-Memory (Volatile)
- **Component**: `SessionMemory.agent_context`
- **Lifecycle**: Per-session, cleared on restart
- **Use Case**: Fast access cho current session

### Layer 2: Redis (Short-term)
- **Component**: `RedisBuffer`
- **TTL**: 1 hour (default)
- **Use Case**: Fast access cho recent messages và agent state
- **Max Messages**: 50 per conversation

### Layer 3: PostgreSQL (Persistent)
- **Component**: `ConversationStore`, `NamespaceManager`
- **Storage**:
  - `conversations` table: Metadata, summary, verified_target
  - `messages` table: Full conversation history
  - `agent_state` table: Agent context snapshots
- **Use Case**: Long-term storage, conversation history, state persistence

### Layer 4: Vector DB (Semantic)
- **Component**: `ConversationRetriever`, `ToolResultsStorage` (via RAG)
- **Storage**: pgvector embeddings
- **Use Case**: Semantic search, context retrieval với ranking

## Key Design Patterns

### 1. Multi-Layer Storage
- **In-Memory** → **Redis** → **PostgreSQL** → **Vector DB**
- Priority-based retrieval: Fast → Persistent → Semantic

### 2. Namespace Isolation
- Mỗi conversation có unique namespace
- Không có cross-conversation leakage
- Vector collections: `conversation_{conversation_id}`

### 3. Auto-Compression
- Tự động compress khi conversation > 100 messages
- LLM-based summarization
- Preserve critical info (targets, findings, vulns)

### 4. Legacy Support
- Vẫn support `session_id` cho backward compatibility
- In-memory buffers maintained during transition
- Migration path: `session_id` → `conversation_id`

## Integration Points

### 1. ContextManager Integration
- `ContextManager` sử dụng `MemoryManager` để persist context
- `ContextManager.update_context()` → `MemoryManager.update_agent_context()`
- `ContextManager.get_context()` → `MemoryManager.retrieve_context()`

### 2. RAG Integration
- `ConversationRetriever`: Semantic search cho conversation context
- `ToolResultsStorage`: Semantic search cho tool results
- `ContextRanker`: Multi-factor ranking cho retrieved contexts

### 3. PentestGraph Integration
- `PentestGraph` sử dụng `MemoryManager` để:
  - Save conversation turns
  - Retrieve context cho nodes
  - Update agent context với findings

## Performance Considerations

### 1. Redis Caching
- Fast access cho recent messages (50 messages)
- TTL-based cleanup (1 hour)
- Optional: Redis có thể fail, fallback to PostgreSQL

### 2. Summary Compression
- Reduce context size cho long conversations
- LLM-based compression (có thể tốn thời gian)
- Threshold: 100 messages (configurable)

### 3. Vector Search
- Semantic search với pgvector
- Ranking với `ContextRanker` (multi-factor scoring)
- Top K retrieval (default: 5)

## Error Handling

### 1. Redis Failure
- Graceful degradation: Fallback to PostgreSQL
- Non-critical: Redis là optional layer

### 2. PostgreSQL Failure
- Fallback to in-memory buffer (legacy)
- Warnings logged, không crash system

### 3. Compression Failure
- Non-critical: Continue without compression
- Warnings logged

## Future Improvements

1. **Batch Operations**: Batch insert messages để tăng performance
2. **Caching Strategy**: More aggressive caching cho frequently accessed data
3. **Compression Optimization**: Faster compression algorithms
4. **Migration**: Hoàn tất migration từ `session_id` sang `conversation_id`
5. **Cleanup**: Remove legacy in-memory buffers sau migration
