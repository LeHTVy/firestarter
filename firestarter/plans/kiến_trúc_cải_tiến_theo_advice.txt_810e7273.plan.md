---
name: Kiến trúc cải tiến theo advice.txt
overview: "Đánh giá và đề xuất cải tiến kiến trúc Firestarter theo advice.txt: tách rõ trách nhiệm frameworks, thêm Policy Engine, bổ sung tool metadata, cải thiện memory layer, và mode separation."
todos:
  - id: create-architecture-doc
    content: Tạo docs/ARCHITECTURE.md mô tả kiến trúc tổng thể và phân vai frameworks
    status: pending
  - id: create-policy-engine
    content: Tạo agents/policy_engine.py với policy checks cho tool execution
    status: pending
  - id: extend-tool-metadata
    content: Mở rộng ToolDefinition trong tools/registry.py với capability, scope, mode, legal_risk, cost, permission_required, evidence_output
    status: pending
  - id: update-tools-json
    content: Update tools/metadata/tools.json với metadata đầy đủ cho một số tools mẫu
    status: pending
  - id: create-mode-manager
    content: Tạo agents/mode_manager.py với Passive/Cooperative/Simulation modes
    status: pending
  - id: integrate-policy-engine
    content: Integrate Policy Engine vào agents/pentest_graph.py và tools/executor.py
    status: pending
  - id: improve-memory-layer
    content: Đảm bảo Redis usage đúng vai trò trong memory/manager.py
    status: pending
---

# Đánh giá và đề xuất cải tiến kiến trúc Firestarter

## 1. Xác nhận kiến trúc hiện tại

### 1.1. Điểm mạnh

- **LangGraph** làm orchestration chính: workflow control, state machine, conditional routing
- **AutoGen** cho multi-agent roles: ReconAgent, ExploitAgent, AnalysisAgent với tool permissions
- **LlamaIndex** cho knowledge base: CVE, exploits, IOC retrieval
- **PostgreSQL + pgvector**: Long-term state và semantic memory
- **Redis**: Short-term buffer (theo thiết kế)
- **Tool Registry**: Metadata-driven với risk_level, assigned_agents
- **Human in the Loop**: Đã có recommend_tools node

### 1.2. Vấn đề cần cải thiện

1. **Framework overlap**: Chưa rõ LangChain dùng ở đâu - có thể chồng chéo với LangGraph
2. **Policy Gate thiếu**: Chỉ có agent permission check, chưa có policy engine riêng
3. **Tool metadata chưa đủ**: Thiếu capability, scope, mode, legal_risk, cost, permission_required, evidence_output
4. **Memory layer chưa rõ**: Redis usage chưa thấy trong code
5. **Mode separation**: Chưa có Passive/Cooperative/Simulation modes
6. **Context explosion**: Chưa có summarizer, topic graph mạnh

## 2. Đề xuất cải tiến

### 2.1. Khóa cứng phân vai frameworks

**File**: `docs/ARCHITECTURE.md` (tạo mới)

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
 Redis   Postgres  VectorDB
```

**Phân quyền**:

- **LangChain**: Chỉ dùng làm tool wrapper (OllamaLLMClient, OllamaEmbeddingClient)
- **LlamaIndex**: Chỉ dùng cho ingestion + retrieval (CVE/exploit/IOC)
- **AutoGen**: Chỉ dùng cho agent role + dialog
- **LangGraph**: State machine + control flow
- **Redis**: Volatile memory (working buffer)
- **Postgres**: Truth + audit (conversations, entities, assets)
- **VectorDB (pgvector)**: Semantic memory

### 2.2. Thêm Policy Engine

**File**: `agents/policy_engine.py` (tạo mới)

Policy Engine sẽ:

- Check tool risk_level và mode (passive/active/destructive)
- Verify authorization scope
- Require explicit approval cho high-risk tools
- Log all policy decisions

**File**: `agents/pentest_graph.py`

Thêm policy check trước tool execution:

```python
def _check_tool_policy(self, tool_name: str, mode: str) -> Dict[str, Any]:
    """Check if tool execution is allowed.
    
    Returns:
        {"allowed": bool, "reason": str, "requires_approval": bool}
    """
```

### 2.3. Mở rộng Tool Metadata

**File**: `tools/registry.py`, `tools/metadata/tools.json`

Thêm các field:

- `capability`: List[str] - Tool làm được gì
- `scope`: str - network/host/web/cloud
- `mode`: str - passive/active/destructive
- `legal_risk`: str - low/medium/high
- `cost`: Dict[str, Any] - time, bandwidth
- `permission_required`: bool
- `evidence_output`: List[str] - logs, json, pcap

### 2.4. Cải thiện Memory Layer

**File**: `memory/manager.py`

Đảm bảo:

- **Redis**: Conversation buffer (short-term), active context
- **PostgreSQL**: Persistent conversations, agent states, verified targets
- **pgvector**: Semantic search cho conversation context và tool results

Kiểm tra Redis usage hiện tại và đảm bảo đúng vai trò.

### 2.5. Mode Separation

**File**: `agents/mode_manager.py` (tạo mới)

3 modes:

- **Mode 1: Passive** - Chỉ OSINT, suy luận, không gửi packet
- **Mode 2: Cooperative** - Chạy scanner với authorization
- **Mode 3: Simulation** - Lab/digital twin, không động production

**File**: `agents/pentest_graph.py`

Thêm mode check vào workflow.

### 2.6. Context Explosion Prevention

**File**: `memory/summary_compressor.py` (đã có)

Cải thiện:

- Topic extraction mạnh hơn
- Entity-based summarization
- Selective context retrieval (chỉ lấy relevant parts)

**File**: `rag/context_ranker.py` (đã có)

Đảm bảo multi-factor scoring hoạt động tốt.

## 3. Thứ tự implementation

1. **Bước 1**: Tạo Policy Engine (quan trọng nhất cho pentest)
2. **Bước 2**: Mở rộng Tool Metadata
3. **Bước 3**: Thêm Mode Manager
4. **Bước 4**: Cải thiện Memory Layer (Redis usage)
5. **Bước 5**: Documentation (ARCHITECTURE.md)

## 4. Files cần thay đổi

### Files mới

- `docs/ARCHITECTURE.md` - Kiến trúc tổng thể
- `agents/policy_engine.py` - Policy Engine
- `agents/mode_manager.py` - Mode Manager

### Files cần update

- `tools/registry.py` - Thêm metadata fields
- `tools/metadata/tools.json` - Bổ sung metadata đầy đủ
- `agents/pentest_graph.py` - Integrate Policy Engine và Mode Manager
- `tools/executor.py` - Check policy trước execution
- `memory/manager.py` - Đảm bảo Redis usage đúng vai trò