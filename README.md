# Firestarter: Advanced Agentic Security Framework

**Firestarter** là một framework AI Cybersecurity Agent tiên tiến, được thiết kế để thực hiện các nhiệm vụ Offensive Security (Pentest/Recon) với khả năng tự chủ cao (High Autonomy). 

Hệ thống hoạt động hoàn toàn **Local** (với Ollama) và hỗ trợ **Live Streaming** kết quả từ các công cụ bảo mật thực tế.

![Architecture](https://img.shields.io/badge/Architecture-LangGraph-blue) ![Memory](https://img.shields.io/badge/Memory-Redis%20%2B%20Postgres-green) ![Tools](https://img.shields.io/badge/Tools-Hybrid%20Execution-orange)

## 🚀 Tính Năng Chính

### 1. **Live Process Streaming** (Real-time PTY)
Khác với các agent thông thường chỉ hiển thị kết quả cuối cùng, Firestarter sử dụng kỹ thuật **PTY (Pseudo-Terminal)** để stream **từng dòng output** (stdout/stderr) của công cụ đang chạy trong thời gian thực.
- **Linux/Mac**: Sử dụng native `pty`.
- **Windows**: Hỗ trợ qua `pywinpty`.
- **UI**: Hiển thị quá trình chạy (Scanning ports, brute-forcing...) sống động như bạn đang gõ lệnh trên terminal.

### 2. **Hybrid Tool Execution Engine**
Hệ thống hỗ trợ thực thi linh hoạt:
- **CLI Binary Tools** (Nmap, GoBuster, Nuclei...): Chạy trực tiếp binary hệ thống thông qua `SpecExecutor` (định nghĩa input/output qua file YAML/Python specs).
- **Python-based Tools** (Web Search, Scripts): Chạy native python code với fallback mechanism thông minh.
- **Auto-Install**: Script hỗ trợ cài đặt tự động các tool còn thiếu.

### 3. **Advanced Memory Architecture**
Hệ thống bộ nhớ phân tầng giúp Agent "nhớ" ngữ cảnh lâu dài:
- **Hot Memory (Redis)**: Lưu trữ trạng thái phiên làm việc (Session State), Context hiện tại, và Tool Logs buffer (tốc độ cao).
- **Cold Memory (PostgreSQL + pgvector)**: Lưu trữ lịch sử trò chuyện, Semantic Search cho kết quả cũ, và Knowledge Base (CVEs, Exploits).
- **Context Switching**: Hỗ trợ lưu/tải và chuyển đổi giữa các phiên pentest khác nhau mà không mất dữ liệu.

### 4. **Multi-Agent Orchestration**
Sử dụng **LangGraph** để điều phối quy trình:
- **Intent Classifier**: Phân loại ý định người dùng.
- **Recon Agent**: Lên kế hoạch và thực thi thu thập thông tin.
- **Exploit Agent**: (Experimental) Thực hiện khai thác dựa trên kết quả recon.
- **Analysis Agent**: Tổng hợp kết quả và đưa ra báo cáo.

---

## 🛠️ Yêu Cầu Hệ Thống

*   **OS**: Linux (Ubuntu Recommended), macOS, hoặc Windows (WSL2 hoặc Native).
*   **Python**: 3.10+
*   **Database**:
    *   **PostgreSQL** (với extension `vector` cho semantic search).
    *   **Redis** (cho caching và hot memory).
*   **AI Engine**: **Ollama** đang chạy local.
*   **System Tools**: `git`, `curl`, `Go` (để cài đặt các tool pentest).

---

## 📦 Cài Đặt

### 1. Clone & Setup Environment

```bash
git clone https://github.com/LeHTVy/firestarter.git
cd firestarter

# Tạo virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Cài đặt Python dependencies
pip install -r requirements.txt
```

### 2. Cài Đặt Security Tools
Sử dụng script cài đặt tự động để tải các công cụ cần thiết (Nmap, Go tools, etc.):

```bash
# Cấp quyền thực thi
chmod +x scripts/install_tools.sh

# Cài đặt toàn bộ (System + Python + Go tools)
./scripts/install_tools.sh

# Hoặc cài riêng lẻ
./scripts/install_tools.sh --go      # Chỉ cài Go tools (subfinder, httpx...)
./scripts/install_tools.sh --python  # Chỉ cài Python tools
```

### 3. Cấu Hình Database (Redis & Postgres)
Đảm bảo Redis và Postgres đang chạy. Cập nhật file `.env`:

```env
# .env file
POSTGRES_DB=firestarter
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

REDIS_HOST=localhost
REDIS_PORT=6379
```

Chạy migration để khởi tạo database schema:
```bash
python scripts/init_db.py
```

### 4. Khởi Động Ollama
Đảm bảo bạn đã pull các model cần thiết:
```bash
ollama serve
# Trong terminal khác:
ollama pull mistral      # Hoặc model bạn chọn trong config
ollama pull qwen2.5:14b  # Recommended cho Agent logic tốt
```

---

## 🖥️ Sử Dụng

Khởi chạy Agent:

```bash
python main.py
```

### Ví dụ lệnh trong Agent CLI:

```text
> assess hellogroup.co.za
```
Agent sẽ:
1.  Phân tích yêu cầu -> Xác định là Recon task.
2.  Lên kế hoạch (Subtasks: DNS Enum -> Subdomain Discovery -> Port Scan...).
3.  Thực thi lần lượt các tool.
4.  **Hiển thị Live Stream** kết quả từng tool trên giao diện.
5.  Tổng hợp báo cáo cuối cùng.

---

## 🧩 Cấu Trúc Dự Án

*   `agents/`: Logic của Agent, LangGraph workflow (`pentest_graph.py`), và Nodes.
*   `tools/`:
    *   `specs/`: Định nghĩa command-line cho tool (Nmap, Amass...).
    *   `executor.py`: Engine thực thi (Hybrid Spec/Python).
    *   `process_streamer.py`: Xử lý PTY streaming.
*   `memory/`: Quản lý Redis và Postgres (`manager.py`, `session.py`).
*   `ui/`: Giao diện dòng lệnh (`streaming_manager.py`, `panels.py`).
*   `websearch/`: Module tìm kiếm (DuckDuckGo/SerpAPI).

---

## ⚠️ Troubleshooting

1.  **Lỗi `Tool not found`**:
    *   Chạy `./scripts/install_tools.sh --check` để xem tool nào thiếu.
    *   Cài đặt thủ công tool đó và đảm bảo nó nằm trong SYSTEM PATH.

2.  **Lỗi PTY trên Windows**:
    *   Đảm bảo đã cài `pywinpty`: `pip install pywinpty`.
    *   Nếu vẫn lỗi, Agent sẽ tự fallback sang chế độ non-interactive (không màu, không live line-by-line).

3.  **Postgres Connection Refused**:
    *   Kiểm tra service Postgres.
    *   Kiểm tra thông tin trong `.env`.

---

**Happy Hacking!** 🔥
