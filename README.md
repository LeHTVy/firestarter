# AI Pentest Agent Multi-Model

Hệ thống AI Pentest Agent hoàn toàn local sử dụng multi-model orchestration với Ollama, AutoGen, LangChain/LangGraph, LlamaIndex, và RAG.

## Kiến trúc

- **Models**: Qwen3, Nemotron-3-Nano, DeepSeek-R1, FunctionGemma (Ollama)
- **Multi-Agent**: AutoGen với Recon Agent, Exploit Agent, Analysis Agent
- **Orchestration**: LangGraph workflow
- **Knowledge Base**: LlamaIndex (CVE, exploits, IOC, logs) + RAG (conversation context, tool results)
- **Memory Architecture**: PostgreSQL (conversation graph) + pgvector (semantic memory) + Redis (short-term buffer)
- **Tools**: 150 security tools metadata-driven (Nmap, Metasploit, Shodan, VirusTotal, etc.)

## Cài đặt

### Yêu cầu hệ thống

- Python 3.8+
- Ollama đã được cài đặt và chạy (https://ollama.com)
- Các models Ollama: qwen2.5, nemotron-3-nano, deepseek-r1, functiongemma
- **PostgreSQL với pgvector extension** (xem [PostgreSQL Setup](docs/POSTGRESQL_SETUP.md))
- **Redis** đã được cài đặt và chạy (xem [Redis Setup](docs/REDIS_SETUP.md))

### Cài đặt tự động (Khuyến nghị)

```bash
# Chạy script setup tự động
./setup.sh
```

Script này sẽ:
- Tạo virtual environment (venv)
- Cài đặt tất cả dependencies
- Tạo file .env mẫu
- Tạo các thư mục cần thiết

### Cài đặt thủ công

```bash
# Tạo virtual environment
python3 -m venv venv

# Kích hoạt virtual environment
source venv/bin/activate  # Linux/Mac
# hoặc
venv\Scripts\activate  # Windows

# Cài đặt dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Cài đặt Playwright browsers (optional)
python -m playwright install chromium
```

## Cấu hình

### 1. Ollama Models

Đảm bảo các models sau đã được pull trong Ollama:

```bash
ollama pull qwen2.5
ollama pull nemotron-3-nano
ollama pull deepseek-r1
ollama pull functiongemma
```

### 2. Configuration Files

- `config/ollama_config.yaml`: Cấu hình kết nối Ollama
- `config/models.yaml`: Cấu hình từng model
- `config/autogen_config.yaml`: Cấu hình AutoGen agents

### 3. PostgreSQL + Redis Setup

**Bắt buộc**: Firestarter yêu cầu PostgreSQL + pgvector + Redis cho production-grade memory architecture.

1. **Cài đặt PostgreSQL + pgvector**: Xem [PostgreSQL Setup Guide](docs/POSTGRESQL_SETUP.md)
2. **Cài đặt Redis**: Xem [Redis Setup Guide](docs/REDIS_SETUP.md)
3. **Cấu hình `.env`** với database connections:

```bash
# .env
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=firestarter_pg
POSTGRES_USER=firestarter_ad
POSTGRES_PASSWORD=your_password_here

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

### 4. API Keys (Optional)

Thêm API keys vào file `.env`:

```bash
# .env
SERPAPI_API_KEY=your_key_here
SHODAN_API_KEY=your_key_here
VIRUSTOTAL_API_KEY=your_key_here
SECURITYTRAILS_API_KEY=your_key_here
```

### 5. Migration từ SQLite3 (Nếu có data cũ)

Nếu bạn đã có data trong SQLite3, chạy migration script:

```bash
python scripts/migrate_chroma_sqlite_to_postgres.py
```

## Sử dụng

### Cách 1: Sử dụng script run (Khuyến nghị)

```bash
./run.sh
```

### Cách 2: Chạy trực tiếp

```bash
# Kích hoạt virtual environment
source venv/bin/activate  # Linux/Mac
# hoặc
venv\Scripts\activate  # Windows

# Chạy chương trình
python main.py
```

### Kiểm tra Ollama

Trước khi chạy, đảm bảo Ollama đang chạy:

```bash
# Kiểm tra Ollama
curl http://localhost:11434/api/tags

# Nếu chưa chạy, khởi động Ollama
ollama serve
```

## Tính năng

- Multi-model orchestration không hardcode/keyword detection
- Tool results storage và Q&A về results
- Web search aggregation với neural ranking
- Structured knowledge retrieval (CVE, exploits, IOC)
- Conversation context và tool results RAG
# firestarter
