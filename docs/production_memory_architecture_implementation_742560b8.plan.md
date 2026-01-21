---
name: Production Memory Architecture Implementation
overview: Implement production-level memory architecture với persistent conversation buffer, conversation metadata store, summary compression, multi-conversation namespace isolation, và conversation switching API để đạt được kiến trúc giống các LLM production platforms.
todos:
  - id: "1"
    content: Create PostgreSQL schema for conversations, messages, and agent states
    status: pending
  - id: "2"
    content: Implement ConversationStore for persistent conversation buffer
    status: pending
    dependencies:
      - "1"
  - id: "3"
    content: Implement SummaryCompressor for conversation history compression
    status: pending
    dependencies:
      - "1"
  - id: "4"
    content: Update MemoryManager to use persistent storage instead of in-memory dicts
    status: pending
    dependencies:
      - "2"
      - "3"
  - id: "5"
    content: Implement NamespaceManager for conversation isolation
    status: pending
    dependencies:
      - "2"
  - id: "6"
    content: Update Vector Store and Retrievers for conversation namespace isolation
    status: pending
    dependencies:
      - "5"
  - id: "7"
    content: Implement ConversationAPI for conversation management and switching
    status: pending
    dependencies:
      - "2"
      - "5"
  - id: "8"
    content: Update main.py to support conversation selection and switching
    status: pending
    dependencies:
      - "7"
  - id: "9"
    content: Update pentest_graph.py to use conversation_id instead of session_id
    status: pending
    dependencies:
      - "4"
  - id: "10"
    content: Test conversation persistence, switching, and namespace isolation
    status: pending
    dependencies:
      - "8"
      - "9"
---

# Production Memory Architecture Implementation

## Mục tiêu

Nâng cấp hệ thống memory từ prototype lên production-level architecture giống các LLM platforms (Claude, ChatGPT, etc.) với:

- Persistent conversation buffer
- Conversation metadata store
- Summary compression
- Multi-conversation namespace isolation
- Conversation switching API

## Kiến trúc hiện tại vs Target

### Hiện tại (Prototype)

```
MemoryManager
├── _conversation_buffers: Dict[str, List]  # In-memory only
├── ConversationRetriever (Vector DB)       # Persistent
└── SessionMemory (Volatile)                 # Lost on restart
```

### Target (Production)

```
Memory Layer
├── Buffer Store (Redis/PostgreSQL)         # Persistent short-term
├── Summary Store (PostgreSQL)               # Compressed history
├── Vector Store (Chroma/pgvector)          # Semantic search
├── State Store (Redis/PostgreSQL)          # Agent state
└── Metadata Store (PostgreSQL)              # Conversation metadata
```

## Implementation Plan

### 1. Database Schema Design

**File**: `database/schema.sql`

Tạo PostgreSQL tables:

```sql
-- Conversation metadata
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    user_id TEXT,  -- For future multi-user support
    metadata JSONB,
    summary TEXT,  -- Compressed summary
    session_id TEXT UNIQUE
);

-- Conversation buffer (full history)
CREATE TABLE conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_messages_conversation ON conversation_messages(conversation_id, sequence_number);
CREATE INDEX idx_messages_created ON conversation_messages(created_at);

-- Agent state (persistent)
CREATE TABLE agent_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    state_type TEXT,  -- 'session_memory', 'agent_context', etc.
    state_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_states_conversation ON agent_states(conversation_id);
```

### 2. Conversation Store Implementation

**File**: `memory/conversation_store.py` (NEW)

```python
class ConversationStore:
    """Persistent store for conversation metadata and buffer."""
    
    def create_conversation(self, title: str = None) -> str:
        """Create new conversation, return conversation_id."""
    
    def get_conversation(self, conversation_id: str) -> Dict:
        """Get conversation metadata."""
    
    def list_conversations(self, limit: int = 50) -> List[Dict]:
        """List all conversations."""
    
    def update_conversation_title(self, conversation_id: str, title: str):
        """Update conversation title."""
    
    def add_message(self, conversation_id: str, role: str, content: str):
        """Add message to conversation buffer."""
    
    def get_messages(self, conversation_id: str, limit: int = None, offset: int = 0) -> List[Dict]:
        """Get messages with sliding window support."""
    
    def get_recent_messages(self, conversation_id: str, k: int = 10) -> List[Dict]:
        """Get last K messages (sliding window)."""
```

### 3. Summary Compression

**File**: `memory/summary_compressor.py` (NEW)

```python
class SummaryCompressor:
    """Compress conversation history when buffer gets too long."""
    
    def should_compress(self, message_count: int, max_messages: int = 50) -> bool:
        """Check if compression needed."""
    
    def compress(self, messages: List[Dict], conversation_id: str) -> str:
        """Compress old messages into summary using LLM."""
    
    def get_context(self, conversation_id: str, query: str) -> Dict:
        """Get context: recent messages + summary + semantic search."""
```

### 4. Enhanced Memory Manager

**File**: `memory/manager.py` (UPDATE)

Thay đổi:

- Thay `_conversation_buffers: Dict` bằng `ConversationStore`
- Thêm `SummaryCompressor` integration
- Thêm persistent state storage
- Thêm conversation switching logic
```python
class MemoryManager:
    def __init__(self):
        self.conversation_store = ConversationStore()
        self.summary_compressor = SummaryCompressor()
        # ... existing code
    
    def switch_conversation(self, conversation_id: str):
        """Switch to different conversation (context switch)."""
        # Load conversation buffer
        # Load summary
        # Load agent state
        # Load vector memory index
```


### 5. Conversation Namespace Isolation

**File**: `memory/namespace_manager.py` (NEW)

```python
class NamespaceManager:
    """Manage conversation namespaces for isolation."""
    
    def get_vector_namespace(self, conversation_id: str) -> str:
        """Get vector DB collection name for conversation."""
    
    def get_state_namespace(self, conversation_id: str) -> str:
        """Get state store key for conversation."""
    
    def load_conversation_context(self, conversation_id: str) -> Dict:
        """Load all context for a conversation."""
    
    def unload_conversation_context(self, conversation_id: str):
        """Unload context (cleanup)."""
```

### 6. Conversation Switching API

**File**: `api/conversation_api.py` (NEW)

```python
class ConversationAPI:
    """API for conversation management."""
    
    def create_conversation(self, title: str = None) -> Dict:
        """Create new conversation."""
    
    def list_conversations(self) -> List[Dict]:
        """List all conversations."""
    
    def switch_conversation(self, conversation_id: str):
        """Switch active conversation."""
    
    def delete_conversation(self, conversation_id: str):
        """Delete conversation and all associated data."""
```

### 7. Update Main Loop

**File**: `main.py` (UPDATE)

Thay đổi:

- Thêm conversation selection UI
- Load conversation context on startup
- Save conversation state on exit
- Support conversation switching

### 8. Update Vector Store for Namespace Isolation

**File**: `rag/retriever.py` (UPDATE)

Thay đổi:

- Sử dụng conversation_id thay vì session_id
- Tạo collection per conversation hoặc filter by conversation_id
- Ensure namespace isolation

## Migration Path

1. **Phase 1: Database Setup**

   - Create PostgreSQL schema
   - Run migration script
   - Test database connections

2. **Phase 2: Core Components**

   - Implement `ConversationStore`
   - Implement `SummaryCompressor`
   - Update `MemoryManager` to use persistent storage

3. **Phase 3: Namespace Isolation**

   - Implement `NamespaceManager`
   - Update Vector Store for isolation
   - Test multi-conversation scenarios

4. **Phase 4: API & UI**

   - Implement conversation switching API
   - Update main loop for conversation management
   - Add conversation selection UI

5. **Phase 5: Testing & Optimization**

   - Test conversation switching
   - Test summary compression
   - Performance optimization

## Files to Create/Modify/Delete

### New Files

1. `database/schema.sql` - PostgreSQL schema
2. `database/migrations/001_initial_schema.sql` - Migration script
3. `memory/conversation_store.py` - Persistent conversation store
4. `memory/summary_compressor.py` - Summary compression
5. `memory/namespace_manager.py` - Namespace isolation
6. `api/conversation_api.py` - Conversation management API
7. `scripts/setup_conversation_db.py` - Database setup script
8. `scripts/migrate_session_to_conversation.py` - Migration script for existing data

### Modified Files (Refactor & Update)

1. **`memory/manager.py`** - MAJOR REFACTOR

   - **Remove**: `_conversation_buffers: Dict[str, List]` (in-memory dict)
   - **Remove**: `_verified_targets: Dict[str, str]` (move to PostgreSQL)
   - **Replace**: In-memory buffer methods với `ConversationStore` calls
   - **Add**: `switch_conversation()` method
   - **Add**: Persistent state storage integration
   - **Keep**: Existing methods nhưng delegate to new stores
   - **Deprecate**: `get_conversation_buffer()` (replace with `ConversationStore.get_messages()`)
   - **Deprecate**: `add_to_conversation_buffer()` (replace with `ConversationStore.add_message()`)

2. **`memory/session.py`** - REFACTOR & ENHANCE

   - **Keep**: `AgentContext` class (tái sử dụng)
   - **Keep**: `SessionMemory` class (tái sử dụng)
   - **Add**: `to_json()` và `from_json()` methods cho persistence
   - **Add**: `save_to_db()` và `load_from_db()` methods
   - **Update**: `SessionMemory` để support conversation_id thay vì chỉ session_id

3. **`agents/context_manager.py`** - MINOR UPDATE

   - **Keep**: `SessionContext` class (tái sử dụng)
   - **Keep**: `ContextManager` class (tái sử dụng)
   - **Update**: Support conversation_id trong context
   - **Update**: Load context from persistent store

4. **`rag/retriever.py`** - UPDATE

   - **Replace**: `session_id` parameter với `conversation_id`
   - **Update**: Metadata filter từ `session_id` sang `conversation_id`
   - **Add**: Namespace isolation support

5. **`rag/results_storage.py`** - UPDATE

   - **Replace**: `session_id` parameter với `conversation_id`
   - **Update**: Metadata filter từ `session_id` sang `conversation_id`

6. **`agents/pentest_graph.py`** - UPDATE

   - **Replace**: All `session_id` references với `conversation_id`
   - **Update**: GraphState để include `conversation_id`
   - **Update**: All nodes để use conversation_id

7. **`main.py`** - MAJOR UPDATE

   - **Remove**: In-memory `conversation_history` list
   - **Add**: Conversation selection UI
   - **Add**: Conversation switching logic
   - **Add**: Load conversation on startup
   - **Add**: Save conversation state on exit
   - **Update**: Use `ConversationStore` instead of in-memory buffer

8. **`agents/target_clarifier.py`** - UPDATE

   - **Update**: Use `conversation_id` instead of `session_id`
   - **Update**: Load verified targets from persistent store

### Deprecated Code (Mark for Removal)

1. **`memory/manager.py`**:

   - `_conversation_buffers: Dict[str, List[Dict]]` - Replace with ConversationStore
   - `_verified_targets: Dict[str, str]` - Move to PostgreSQL
   - `get_conversation_buffer()` - Replace with ConversationStore.get_messages()
   - `add_to_conversation_buffer()` - Replace with ConversationStore.add_message()
   - `clear_conversation_buffer()` - Replace with ConversationStore.delete_messages()

2. **`main.py`**:

   - `conversation_history: List[Dict]` - Replace with ConversationStore
   - In-memory session management - Replace with ConversationAPI

### Migration Strategy

1. **Backward Compatibility Phase**:

   - Keep old methods with deprecation warnings
   - Add new methods alongside old ones
   - Support both `session_id` and `conversation_id` during transition

2. **Data Migration**:

   - Script `scripts/migrate_session_to_conversation.py`:
     - Convert existing session_id to conversation_id
     - Migrate in-memory buffers to PostgreSQL (if any exist)
     - Migrate verified targets to PostgreSQL
     - Update Vector DB metadata from session_id to conversation_id

3. **Cleanup Phase**:

   - Remove deprecated methods after migration period
   - Remove in-memory storage code
   - Update all callers to use new API

### Code Reuse Analysis

**Files to Reuse (No Major Changes)**:

- `memory/session.py` - AgentContext và SessionMemory classes (chỉ cần add persistence)
- `agents/context_manager.py` - SessionContext và ContextManager (chỉ cần update để support conversation_id)

**Files to Refactor (Keep Structure, Change Implementation)**:

- `memory/manager.py` - Keep class structure, replace storage backend
- `rag/retriever.py` - Keep class structure, update metadata keys
- `rag/results_storage.py` - Keep class structure, update metadata keys

**Files to Update (Change Usage)**:

- `main.py` - Change how conversation history is managed
- `agents/pentest_graph.py` - Change session_id to conversation_id
- `agents/target_clarifier.py` - Change session_id to conversation_id

## Testing Strategy

1. **Unit Tests**: Test each component independently
2. **Integration Tests**: Test conversation switching, summary compression
3. **Load Tests**: Test with multiple conversations
4. **Persistence Tests**: Test data survives restarts

## Cleanup & Removal Strategy

### Phase 1: Deprecation (Backward Compatible)

- Add deprecation warnings to old methods
- Keep old methods working but delegate to new implementation
- Support both `session_id` and `conversation_id` during transition
- **No breaking changes** - existing code continues to work

### Phase 2: Migration

- Run migration script to convert existing data
- Update all internal code to use new API
- Test thoroughly with existing workflows

### Phase 3: Cleanup (After Migration Verified)

- Remove deprecated methods from `memory/manager.py`:
  - `_conversation_buffers` dict (line 43)
  - `_verified_targets` dict (line 47)
  - `get_conversation_buffer()` method (line 246-260)
  - `add_to_conversation_buffer()` method (line 262-282)
  - `clear_conversation_buffer()` method (line 284-288)
- Remove in-memory `conversation_history` from `main.py` (line 93)
- Update all callers to use new `ConversationStore` API
- Remove `session_id` parameters, replace with `conversation_id`

### Files That Will Be Completely Removed

**None** - Tất cả files đều được tái sử dụng hoặc refactor, không có file nào bị xóa hoàn toàn.

### Code That Will Be Removed (Within Files)

1. **`memory/manager.py`**:

   - `_conversation_buffers: Dict[str, List[Dict]]` (in-memory storage)
   - `_verified_targets: Dict[str, str]` (in-memory storage)
   - Methods that use in-memory storage (sau khi migration)

2. **`main.py`**:

   - `conversation_history: List[Dict]` (in-memory list)
   - Direct buffer manipulation code

### Code That Will Be Reused (No Removal)

1. **`memory/session.py`**:

   - `AgentContext` class - **KEEP & ENHANCE** (add persistence)
   - `SessionMemory` class - **KEEP & ENHANCE** (add persistence)
   - `Fact` class - **KEEP**

2. **`agents/context_manager.py`**:

   - `SessionContext` class - **KEEP** (chỉ update để support conversation_id)
   - `ContextManager` class - **KEEP** (chỉ update để support conversation_id)

3. **`rag/retriever.py`**:

   - `ConversationRetriever` class - **KEEP** (chỉ update metadata keys)

4. **`rag/results_storage.py`**:

   - `ToolResultsStorage` class - **KEEP** (chỉ update metadata keys)

## Success Criteria

- [ ] Conversations persist across restarts
- [ ] Can switch between multiple conversations
- [ ] Each conversation has isolated memory namespace
- [ ] Summary compression works for long conversations
- [ ] Vector search respects conversation boundaries
- [ ] Agent state persists per conversation
- [ ] Performance acceptable (< 100ms for context switch)
- [ ] All deprecated code removed after migration
- [ ] No breaking changes during transition period
- [ ] Existing code continues to work during migration