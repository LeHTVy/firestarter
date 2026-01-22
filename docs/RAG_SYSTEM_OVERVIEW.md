# RAG System Overview - Folder `rag/`

## Tổng Quan

Folder `rag/` chứa **Retrieval-Augmented Generation (RAG)** system cho Firestarter:
- **Vector Storage**: PostgreSQL + pgvector cho semantic search
- **Context Retrieval**: Lấy context từ conversations và tool results
- **Ranking**: Multi-factor scoring để rank context relevance
- **Topic Extraction**: Extract topics từ conversations

## Kiến Trúc

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG System                                │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Embeddings   │  │ VectorStore  │  │ Retriever    │      │
│  │ (embeddings) │  │ (pgvector)  │  │ (retriever)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            │                                  │
│         ┌──────────────────┴──────────────────┐              │
│         │                                      │              │
│  ┌──────▼──────┐                    ┌──────────▼──────┐        │
│  │ Results     │                    │ Context        │        │
│  │ Storage     │                    │ Ranker         │        │
│  │ (results_   │                    │ (context_      │        │
│  │  storage)   │                    │  ranker)       │        │
│  └─────────────┘                    └─────────────────┘        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Topic Extractor (topic_extractor)                    │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## Chi Tiết Từng File

### 1. `rag/embeddings.py` - Embedding Wrapper

**Vai trò**: Wrapper cho Ollama embedding model

**Class**: `NemotronEmbeddings`
- **Model**: `nomic-embed-text` (default)
- **Methods**:
  - `embed_documents(texts)`: Embed nhiều documents
  - `embed_query(text)`: Embed query text

**Sử dụng bởi**:
- `PgVectorStore` - để generate embeddings cho documents và queries

**Lưu ý**: Tên "Nemotron" là legacy, thực tế dùng Ollama embeddings

---

### 2. `rag/pgvector_store.py` - PostgreSQL Vector Store

**Vai trò**: Core vector storage sử dụng PostgreSQL + pgvector extension

**Class**: `PgVectorStore`
- **Storage**: PostgreSQL với pgvector extension
- **Features**:
  - Semantic similarity search
  - Namespace isolation (per conversation)
  - Embedding generation và storage

**Key Methods**:
- `add_documents()`: Thêm documents với embeddings
- `similarity_search()`: Tìm documents tương tự
- `delete_by_ids()`: Xóa documents

**Sử dụng bởi**:
- `ConversationRetriever` - lưu và retrieve conversation context
- `ToolResultsStorage` - lưu và retrieve tool results

**Database Schema**:
```sql
CREATE TABLE vector_embeddings (
    id UUID PRIMARY KEY,
    collection_name TEXT,
    document TEXT,
    embedding vector(768),
    metadata JSONB,
    created_at TIMESTAMP
)
```

---

### 3. `rag/vectorstore.py` - ChromaDB Wrapper (DEPRECATED)

**Vai trò**: ⚠️ **DEPRECATED** - Legacy ChromaDB implementation

**Class**: `ChromaVectorStore`
- **Status**: Deprecated, sẽ bị xóa trong tương lai
- **Replacement**: Sử dụng `PgVectorStore` thay thế

**Lưu ý**: File này chỉ giữ lại cho backward compatibility, không nên sử dụng mới

---

### 4. `rag/retriever.py` - Conversation Retriever

**Vai trò**: Semantic retriever cho conversation context

**Class**: `ConversationRetriever`
- **Purpose**: Retrieve conversation messages dựa trên semantic similarity
- **Namespace Isolation**: Mỗi conversation có collection riêng

**Key Methods**:
- `add_conversation()`: Thêm conversation messages vào vector store
- `retrieve()`: Retrieve relevant conversation context
- `_get_collection_for_conversation()`: Get conversation-specific collection

**Sử dụng bởi**:
- `MemoryManager` - để retrieve conversation context
- `AnalyzeNode` - để lấy context cho analysis

**Flow**:
```
ConversationRetriever.add_conversation(messages)
    ↓
PgVectorStore.add_documents() [với namespace isolation]
    ↓
PostgreSQL + pgvector [persistent storage]
```

---

### 5. `rag/results_storage.py` - Tool Results Storage

**Vai trò**: Storage cho tool execution results với semantic search

**Class**: `ToolResultsStorage`
- **Purpose**: Lưu và retrieve tool execution results
- **Namespace Isolation**: Mỗi conversation có results collection riêng

**Key Methods**:
- `store_result()`: Lưu tool execution result
- `retrieve_results()`: Retrieve results dựa trên query

**Sử dụng bởi**:
- `MemoryManager` - để store và retrieve tool results
- `ToolExecutorNode` - để lưu execution results

**Flow**:
```
ToolResultsStorage.store_result(tool_name, parameters, results)
    ↓
PgVectorStore.add_documents() [với namespace "_results"]
    ↓
PostgreSQL + pgvector [persistent storage]
```

---

### 6. `rag/results_retriever.py` - Results Retriever

**Vai trò**: Specialized retriever cho tool results Q&A

**Class**: `ResultsRetriever`
- **Purpose**: Wrapper đơn giản cho `ToolResultsStorage.retrieve_results()`
- **Use Case**: Q&A về tool results (đã bị xóa `ResultsQAAgent`)

**Key Methods**:
- `retrieve()`: Retrieve tool results với filters

**Lưu ý**: File này rất nhỏ (39 lines), có thể merge vào `results_storage.py`

---

### 7. `rag/context_ranker.py` - Context Ranking

**Vai trò**: Multi-factor scoring algorithm để rank context relevance

**Class**: `ContextRanker`
- **Purpose**: Rank contexts dựa trên nhiều factors:
  - Semantic similarity (α = 0.4)
  - Recency (β = 0.3)
  - Entity match (γ = 0.2)
  - Task relevance (δ = 0.1)

**Formula**:
```
final_score = α * semantic_similarity + β * recency + γ * entity_match + δ * task_relevance
```

**Key Methods**:
- `rank_contexts()`: Rank contexts với multi-factor scoring
- `_extract_entities()`: Extract entities (domains, IPs, CVEs) từ text
- `get_top_k()`: Get top K contexts sau ranking

**Sử dụng bởi**:
- `MemoryManager.retrieve_context()` - để rank retrieved contexts
- `TopicExtractor` - để extract entities

**Features**:
- Entity extraction (domains, IPs, CVEs, tools)
- Recency scoring (newer = higher score)
- Task type matching (recon, exploitation, etc.)

---

### 8. `rag/topic_extractor.py` - Topic Extraction

**Vai trò**: Extract topics từ conversations

**Class**: `TopicExtractor`
- **Purpose**: Extract topics từ conversation messages
- **Method**: Combine entities + keywords, count frequency

**Key Methods**:
- `extract_topics()`: Extract topics từ messages
- `_extract_keywords()`: Extract security-related keywords

**Sử dụng bởi**:
- `MemoryManager` - để extract topics từ conversations
- `SessionMemory` - để track conversation topics

**Flow**:
```
TopicExtractor.extract_topics(messages)
    ↓
ContextRanker._extract_entities() [extract entities]
    ↓
_extract_keywords() [extract keywords]
    ↓
Counter.most_common() [rank by frequency]
    ↓
Return top topics
```

---

## Data Flow

### 1. Storing Conversation Context

```
User Message
    ↓
ConversationRetriever.add_conversation()
    ↓
PgVectorStore.add_documents()
    ↓
NemotronEmbeddings.embed_documents()
    ↓
PostgreSQL (vector_embeddings table)
```

### 2. Retrieving Conversation Context

```
User Query
    ↓
MemoryManager.retrieve_context()
    ↓
ConversationRetriever.retrieve()
    ↓
PgVectorStore.similarity_search()
    ↓
NemotronEmbeddings.embed_query()
    ↓
PostgreSQL (cosine similarity search)
    ↓
ContextRanker.rank_contexts() [optional ranking]
    ↓
Return ranked contexts
```

### 3. Storing Tool Results

```
Tool Execution Result
    ↓
ToolResultsStorage.store_result()
    ↓
PgVectorStore.add_documents() [namespace: conversation_{id}_results]
    ↓
PostgreSQL (vector_embeddings table)
```

### 4. Retrieving Tool Results

```
Query about Results
    ↓
ToolResultsStorage.retrieve_results()
    ↓
PgVectorStore.similarity_search() [namespace: conversation_{id}_results]
    ↓
ContextRanker.rank_contexts() [optional ranking]
    ↓
Return ranked results
```

## Mối Quan Hệ Với Memory System

```
MemoryManager
    ├──► ConversationRetriever (rag/retriever.py)
    │       └──► PgVectorStore (rag/pgvector_store.py)
    │
    ├──► ToolResultsStorage (rag/results_storage.py)
    │       └──► PgVectorStore (rag/pgvector_store.py)
    │
    └──► ContextRanker (rag/context_ranker.py)
            └──► Used for ranking retrieved contexts
```

## Namespace Isolation

Mỗi conversation có namespace riêng:
- **Conversations**: `conversation_{conversation_id}`
- **Tool Results**: `conversation_{conversation_id}_results`

Đảm bảo:
- Data isolation giữa các conversations
- Không bị cross-contamination
- Có thể query riêng từng conversation

## Tóm Tắt

| File | Vai Trò | Status |
|------|---------|--------|
| `embeddings.py` | Embedding wrapper | ✅ Active |
| `pgvector_store.py` | PostgreSQL vector store | ✅ Active (Core) |
| `vectorstore.py` | ChromaDB wrapper | ⚠️ Deprecated |
| `retriever.py` | Conversation retriever | ✅ Active |
| `results_storage.py` | Tool results storage | ✅ Active |
| `results_retriever.py` | Results retriever wrapper | ✅ Active (có thể merge) |
| `context_ranker.py` | Context ranking | ✅ Active |
| `topic_extractor.py` | Topic extraction | ✅ Active |

## Recommendations

1. **Xóa `vectorstore.py`**: File deprecated, không còn sử dụng
2. **Merge `results_retriever.py`**: Có thể merge vào `results_storage.py` vì rất nhỏ
3. **Extract constants**: Extract magic numbers trong `context_ranker.py` (weights, thresholds)
