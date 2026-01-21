---
name: Migrate from ChromaDB to pgvector + Redis Architecture
overview: "Thay thế ChromaDB bằng kiến trúc production-grade: PostgreSQL (conversation management) + pgvector (semantic memory) + Redis (short-term buffer), loại bỏ toàn bộ ChromaDB dependencies và code cũ."
todos:
  - id: "1"
    content: "Cập nhật database schema: thêm bảng vector_embeddings với pgvector support và indexes"
    status: completed
  - id: "2"
    content: Tạo PgVectorStore class trong rag/pgvector_store.py thay thế ChromaVectorStore
    status: completed
    dependencies:
      - "1"
  - id: "3"
    content: Tạo RedisBuffer class trong memory/redis_buffer.py cho short-term buffer
    status: completed
  - id: "4"
    content: "Cập nhật rag/retriever.py: thay ChromaVectorStore → PgVectorStore"
    status: completed
    dependencies:
      - "2"
  - id: "5"
    content: "Cập nhật rag/results_storage.py: thay ChromaVectorStore → PgVectorStore"
    status: completed
    dependencies:
      - "2"
  - id: "6"
    content: "Cập nhật memory/manager.py: tích hợp PgVectorStore và RedisBuffer"
    status: completed
    dependencies:
      - "2"
      - "3"
  - id: "7"
    content: "Cập nhật requirements.txt: xóa chromadb, thêm pgvector và redis"
    status: completed
  - id: "8"
    content: "Xóa ChromaDB-related files: scripts/start_chroma_server.sh, docs/CHROMA_*.md"
    status: completed
  - id: "9"
    content: "Cập nhật .env.example: thêm Redis config, xóa Chroma config"
    status: completed
  - id: "10"
    content: Tạo migration script scripts/migrate_chroma_to_pgvector.py (optional, nếu có data cũ)
    status: completed
    dependencies:
      - "2"
  - id: "11"
    content: "Cập nhật documentation: README.md, docs/POSTGRESQL_SETUP.md, tạo docs/REDIS_SETUP.md"
    status: in_progress
    dependencies:
      - "8"
  - id: "12"
    content: "Cập nhật setup.sh: xóa Chroma Server checks, thêm Redis checks"
    status: pending
    dependencies:
      - "11"
---

# Migration từ ChromaDB sang pgvector + Redis Architecture

## Kiến trúc mới

```
User Input
  |
Session Router
  |
Conversation Manager
  |         |              |
PostgreSQL  pgvector      Redis
  |         |              |
Messages   Embeddings    Buffer
Metadata   Semantic      State
           Memory
```

### 3 lớp Memory:

1. **Short-term Buffer (Redis)**: N message gần nhất, active state
2. **Long-term Semantic Memory (pgvector)**: Embeddings, facts, past reasoning
3. **Conversation Graph (PostgreSQL)**: Messages, metadata, summaries, threads

## Các thay đổi chính

### 1. Database Schema Updates

**File**: `database/schema.sql`

Thêm bảng cho vector embeddings:

- `vector_embeddings`: Lưu embeddings với pgvector
- Indexes: HNSW cho similarity search, metadata filtering
- Namespace isolation qua `conversation_id`

### 2. Tạo PgVectorStore

**File mới**: `rag/pgvector_store.py`

Thay thế `ChromaVectorStore` với:

- Kết nối PostgreSQL trực tiếp (không cần Chroma Server)
- Sử dụng pgvector extension cho vector operations
- HNSW index cho similarity search
- Metadata filtering bằng PostgreSQL JSONB
- Namespace isolation qua conversation_id

### 3. Tích hợp Redis

**File mới**: `memory/redis_buffer.py`

Short-term buffer:

- Lưu N message gần nhất (sliding window)
- Active agent state
- Chain-of-thought reasoning
- TTL tự động

### 4. Cập nhật các file sử dụng ChromaVectorStore

**Files cần update**:

- `rag/retriever.py`: Thay `ChromaVectorStore` → `PgVectorStore`
- `rag/results_storage.py`: Thay `ChromaVectorStore` → `PgVectorStore`
- `memory/manager.py`: Thay `ChromaVectorStore` → `PgVectorStore`, thêm Redis buffer

### 5. Loại bỏ ChromaDB

**Files để xóa**:

- `scripts/start_chroma_server.sh`
- `docs/CHROMA_SERVER_SETUP.md`
- `docs/CHROMA_BACKEND_OPTIONS.md`

**Dependencies để xóa**:

- `chromadb>=0.4.0` từ `requirements.txt`

**Dependencies để thêm**:

- `pgvector>=0.2.0` (Python package)
- `redis>=5.0.0`

### 6. Cập nhật Environment Variables

**File**: `.env.example`

Thêm:

- `REDIS_HOST=localhost`
- `REDIS_PORT=6379`
- `REDIS_PASSWORD=` (optional)
- `REDIS_DB=0`

Xóa:

- `CHROMA_SERVER_HOST`
- `CHROMA_SERVER_PORT`
- `CHROMA_SERVER_AUTH_TOKEN`
- `CHROMA_POSTGRES_*` variables

### 7. Migration Script

**File mới**: `scripts/migrate_chroma_to_pgvector.py`

Nếu có data trong ChromaDB (SQLite), migrate sang pgvector:

- Export embeddings từ ChromaDB
- Import vào PostgreSQL với pgvector
- Preserve metadata và conversation_id

### 8. Cập nhật Documentation

**Files cần update**:

- `README.md`: Xóa Chroma Server requirements, thêm Redis
- `docs/POSTGRESQL_SETUP.md`: Thêm hướng dẫn pgvector setup
- Tạo `docs/REDIS_SETUP.md`: Hướng dẫn cài đặt Redis

## Implementation Details

### PgVectorStore API (giữ tương thích với ChromaVectorStore)

```python
class PgVectorStore:
    def __init__(self, collection_name: str = "default", ...)
    def add_documents(self, texts, metadatas, ids)
    def similarity_search(self, query, k=5, filter=None)
    def health_check(self) -> bool
```

### Redis Buffer API

```python
class RedisBuffer:
    def add_message(self, conversation_id, role, content)
    def get_recent_messages(self, conversation_id, n=10)
    def set_state(self, conversation_id, state_type, data)
    def get_state(self, conversation_id, state_type)
```

### Database Schema cho Vector Embeddings

```sql
CREATE TABLE vector_embeddings (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    collection_name TEXT,
    text TEXT NOT NULL,
    embedding vector(768),  -- Adjust dimension based on embedding model
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON vector_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON vector_embeddings(conversation_id, collection_name);
CREATE INDEX ON vector_embeddings USING gin(metadata);
```

## Testing Strategy

1. Unit tests cho PgVectorStore
2. Integration tests cho Redis buffer
3. Migration tests (nếu có data cũ)
4. Performance tests: so sánh với ChromaDB

## Rollback Plan

Nếu migration gặp vấn đề:

- Giữ ChromaDB code trong branch riêng
- Có thể rollback bằng cách restore từ git
- Data migration script có thể chạy ngược (export từ pgvector → ChromaDB format)