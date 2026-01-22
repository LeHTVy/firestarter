# Mối Liên Kết Giữa ContextManager và Memory System

## Tổng Quan

`agents/context_manager.py` và `memory/` có mối quan hệ **một chiều** và **loosely coupled**:

- **ContextManager** → **MemoryManager**: ContextManager gọi MemoryManager để persist data
- **MemoryManager** → **ContextManager**: KHÔNG có (MemoryManager không biết về ContextManager)

## Kiến Trúc

```
┌─────────────────────────────────────────────────────────────┐
│                    ContextManager                           │
│  (agents/context_manager.py)                                │
│                                                              │
│  - SessionContext (dataclass)                               │
│    • target_domain, target_ip                               │
│    • subdomains, open_ports, detected_tech                  │
│    • tools_run, current_phase                               │
│                                                              │
│  - ContextManager (class)                                   │
│    • _session_context: SessionContext                       │
│    • _memory_manager: MemoryManager (optional)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ set_memory_manager()
                       │ update_context() → update_agent_context()
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    MemoryManager                            │
│  (memory/manager.py)                                         │
│                                                              │
│  - conversation_store: ConversationStore                    │
│  - summary_compressor: SummaryCompressor                    │
│  - namespace_manager: NamespaceManager                       │
│  - redis_buffer: RedisBuffer                                │
│  - session_memory: SessionMemory                            │
│    └── agent_context: AgentContext                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ├──► ConversationStore (PostgreSQL)
                       ├──► SummaryCompressor
                       ├──► NamespaceManager
                       └──► RedisBuffer
```

## Chi Tiết Mối Liên Kết

### 1. Initialization Flow

**Trong `agents/pentest_graph.py` (line 111-113):**
```python
self.memory_manager = get_memory_manager()
self.context_manager = get_context_manager()
self.context_manager.set_memory_manager(self.memory_manager)
```

**Luồng:**
1. Tạo `MemoryManager` singleton
2. Tạo `ContextManager` singleton
3. Link `ContextManager` → `MemoryManager` qua `set_memory_manager()`

### 2. Data Flow: ContextManager → MemoryManager

**Method: `ContextManager.update_context()` (line 234-255)**

```python
def update_context(self, updates: Dict[str, Any], ...) -> SessionContext:
    current = self.get_context(state)
    updated = current.merge_with(updates)
    
    # Update internal state
    self._session_context = updated
    
    # Also update memory manager if available
    if self._memory_manager:
        self._memory_manager.update_agent_context(updates)  # ← Gọi MemoryManager
    
    return updated
```

**Mapping từ SessionContext → AgentContext:**

| SessionContext (ContextManager) | AgentContext (MemoryManager) |
|--------------------------------|------------------------------|
| `target_domain` | `agent_context.domain` |
| `subdomains` | `agent_context.subdomains` |
| `open_ports` | `agent_context.open_ports` |
| `detected_tech` | `agent_context.technologies` |
| `vulns_found` | `agent_context.vulnerabilities` |
| `tools_run` | `agent_context.tools_run` |

### 3. MemoryManager.update_agent_context() (line 422-487)

**Xử lý updates từ ContextManager:**

```python
def update_agent_context(self, updates: Dict[str, Any]):
    if not self.session_memory:
        self.get_or_create_session()
    
    ctx = self.session_memory.agent_context
    
    # Update subdomains
    if "subdomains" in updates:
        ctx.add_subdomains(updates["subdomains"])
        for subdomain in updates["subdomains"]:
            ctx.add_active_entity(subdomain)
    
    # Update IPs
    if "ips" in updates:
        for ip in updates["ips"]:
            ctx.add_ip(ip)
            ctx.add_active_entity(ip)
    
    # Update ports
    if "open_ports" in updates:
        for port_info in updates["open_ports"]:
            ctx.add_port(...)
    
    # Update vulnerabilities
    if "vulnerabilities" in updates:
        for vuln in updates["vulnerabilities"]:
            ctx.add_vulnerability(...)
    
    # ... và nhiều fields khác
```

### 4. Persistence Flow

**MemoryManager lưu data vào:**

1. **SessionMemory** (in-memory, volatile)
   - `self.session_memory.agent_context` - shared context giữa agents

2. **PostgreSQL** (persistent)
   - `ConversationStore` - conversation metadata, messages
   - `NamespaceManager.save_agent_state()` - agent state persistence

3. **Redis** (short-term buffer)
   - `RedisBuffer.set_state()` - fast access cho agent_context

**Trong `save_turn()` (line 327-339):**
```python
if self.session_memory:
    state_data = {
        "session_memory": self.session_memory.to_dict(),
        "agent_context": self.session_memory.agent_context.to_dict()
    }
    # Save to PostgreSQL (persistent)
    self.namespace_manager.save_agent_state(conv_id, "session_memory", state_data)
    # Save to Redis (short-term, faster access)
    self.redis_buffer.set_state(conv_id, "agent_context", ...)
```

## Các File Trong memory/ và Vai Trò

### 1. `memory/manager.py` - Core Memory Manager
- **Vai trò**: Orchestrator chính cho toàn bộ memory system
- **Liên kết với ContextManager**: 
  - Nhận `update_agent_context()` calls từ ContextManager
  - Quản lý `SessionMemory` và `AgentContext`
  - Persist data qua ConversationStore, NamespaceManager, RedisBuffer

### 2. `memory/session.py` - Session Memory
- **Vai trò**: Volatile in-session context
- **Classes**:
  - `SessionMemory`: Container cho session data
  - `AgentContext`: Shared context giữa agents (subdomains, ports, vulns, etc.)
- **Liên kết**: MemoryManager sử dụng `SessionMemory.agent_context` để lưu findings

### 3. `memory/conversation_store.py` - Persistent Storage
- **Vai trò**: PostgreSQL storage cho conversations
- **Liên kết**: MemoryManager sử dụng để persist conversation metadata và messages
- **Không trực tiếp liên kết với ContextManager**

### 4. `memory/namespace_manager.py` - Namespace Isolation
- **Vai trò**: Quản lý namespace isolation cho multi-conversation
- **Liên kết**: MemoryManager sử dụng để tạo unique namespaces cho mỗi conversation
- **Không trực tiếp liên kết với ContextManager**

### 5. `memory/summary_compressor.py` - Summary Compression
- **Vai trò**: Compress long conversations để giảm context size
- **Liên kết**: MemoryManager sử dụng khi conversation quá dài
- **Không trực tiếp liên kết với ContextManager**

### 6. `memory/redis_buffer.py` - Short-Term Buffer
- **Vai trò**: Redis buffer cho fast access
- **Liên kết**: MemoryManager sử dụng để cache agent_context
- **Không trực tiếp liên kết với ContextManager**

## Data Flow Diagram

```
User Action
    │
    ▼
ContextManager.update_context(updates)
    │
    ├──► SessionContext.merge_with()  [Update local context]
    │
    └──► MemoryManager.update_agent_context(updates)
            │
            ├──► SessionMemory.agent_context.add_*()  [Update in-memory]
            │
            └──► save_turn() [When turn is saved]
                    │
                    ├──► ConversationStore.save_message()  [PostgreSQL]
                    ├──► NamespaceManager.save_agent_state()  [PostgreSQL]
                    └──► RedisBuffer.set_state()  [Redis]
```

## Key Differences

### SessionContext (ContextManager)
- **Scope**: Single request/session snapshot
- **Purpose**: Immutable context cho một request
- **Lifecycle**: Created per request, merged with updates
- **Storage**: In-memory only (không persist)

### AgentContext (MemoryManager)
- **Scope**: Shared context across all agents trong session
- **Purpose**: "Message board" cho inter-agent communication
- **Lifecycle**: Persisted qua PostgreSQL và Redis
- **Storage**: In-memory + PostgreSQL + Redis

## Usage Pattern

**Trong nodes (ví dụ: `analyze_node.py`):**
```python
# Get context từ ContextManager
context = self.context_manager.get_context(state)
target = context.get_target()

# Update context
self.context_manager.update_context({
    "subdomains": ["sub1.example.com", "sub2.example.com"],
    "open_ports": [{"port": 80, "service": "http"}]
})

# ContextManager tự động sync với MemoryManager
# → MemoryManager.update_agent_context() được gọi
# → AgentContext được update
# → Data được persist khi save_turn()
```

## Tóm Tắt

1. **ContextManager** là **thin wrapper** cho session context
2. **MemoryManager** là **persistence layer** cho agent findings
3. **One-way dependency**: ContextManager → MemoryManager (không ngược lại)
4. **Data sync**: Khi `ContextManager.update_context()` được gọi, nó tự động sync với `MemoryManager.update_agent_context()`
5. **Persistence**: MemoryManager persist data qua PostgreSQL (ConversationStore) và Redis (RedisBuffer)
6. **Isolation**: NamespaceManager đảm bảo mỗi conversation có namespace riêng
