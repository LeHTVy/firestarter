# Server Setup Guide - Using Qwen2 Pentest Model

Hướng dẫn chuyển codebase lên server có model `qwen2_pentest` đã được fine-tune.

## 1. Cấu Hình Ollama Server URL

### Option 1: Sử dụng Environment Variable (Recommended)

```bash
export OLLAMA_HOST=http://your-server-ip:11434
# hoặc
export OLLAMA_HOST=http://your-server-domain:11434
```

### Option 2: Sửa Config File

Sửa file `config/ollama_config.yaml`:

```yaml
ollama:
  base_url: "http://your-server-ip:11434"  # Thay đổi URL server của bạn
  timeout: 300
  verify_ssl: false
```

### Option 3: Pass base_url trực tiếp trong code

Nếu cần override động, có thể pass `base_url` khi khởi tạo `OllamaLLMClient`:

```python
from models.llm_client import OllamaLLMClient

client = OllamaLLMClient(
    model_name="qwen2_pentest:latest",
    base_url="http://your-server-ip:11434"
)
```

## 2. Kiểm Tra Model Có Sẵn

Trước khi chạy, kiểm tra model có sẵn trên server:

```bash
# Trên server
ollama list

# Hoặc từ client
curl http://your-server-ip:11434/api/tags
```

Đảm bảo model `qwen2_pentest` (hoặc tên bạn đã đặt) có trong danh sách.

## 3. Cấu Hình Model

Model `qwen2_pentest` đã được thêm vào config:

- **File**: `config/ollama_config.yaml`
  - Model config với temperature=0.3 (tối ưu cho pentest)

- **File**: `config/models.yaml`
  - Role: `task_analysis_and_tool_execution`
  - Có thể dùng cho cả task analysis và tool execution

## 4. Sử Dụng Model

### Option A: Chọn từ Menu (Recommended)

Khi chạy `python main.py`, chọn option **4. Qwen2 Pentest** từ menu:

```
Model Selection
1. Mistral 7B (default)
2. Llama 3.1 8B (less refusal)
3. DeepSeek-V2 7B (technical)
4. Qwen2 Pentest (fine-tuned, recommended for pentest)  ← Chọn option này
5. Custom Ollama model
```

### Option B: Set làm Default Model

Sửa file `config/models.yaml`:

```yaml
selection:
  default_model: "qwen2_pentest:latest"  # Thay đổi từ "mistral:latest"
  fallback_model: "deepseek_r1"
```

### Option C: Dùng cho Tool Execution

Nếu `qwen2_pentest` hỗ trợ function calling tốt, có thể dùng thay cho FunctionGemma:

Sửa file `models/functiongemma_agent.py` hoặc tạo wrapper mới để dùng `qwen2_pentest` cho tool execution.

## 5. Test Connection

Test kết nối đến server:

```python
from models.llm_client import OllamaLLMClient

client = OllamaLLMClient(
    model_name="qwen2_pentest:latest",
    base_url="http://your-server-ip:11434"
)

response = client.generate([
    {"role": "user", "content": "Test connection"}
])

print(response)
```

## 6. Troubleshooting

### Lỗi: Connection refused

- Kiểm tra firewall: port 11434 phải được mở
- Kiểm tra Ollama service đang chạy trên server:
  ```bash
  systemctl status ollama
  ```

### Lỗi: Model not found

- Kiểm tra model name chính xác:
  ```bash
  ollama list  # Trên server
  ```
- Có thể model tag khác (ví dụ: `qwen2_pentest:v1` thay vì `qwen2_pentest:latest`)
- Sửa trong config nếu cần

### Lỗi: Timeout

- Tăng timeout trong `config/ollama_config.yaml`:
  ```yaml
  timeout: 600  # Tăng từ 300 lên 600 giây
  ```

### Model chậm

- Kiểm tra server resources (CPU, RAM, GPU)
- Có thể cần giảm `num_predict` trong config để response nhanh hơn

## 7. Production Deployment

### Security Considerations

1. **HTTPS**: Nếu deploy production, nên dùng HTTPS:
   ```yaml
   base_url: "https://your-server-domain:11434"
   verify_ssl: true
   ```

2. **Authentication**: Nếu Ollama server có authentication, cần thêm vào connection string hoặc dùng API key.

3. **Network**: Đảm bảo network giữa client và server ổn định, đặc biệt cho streaming.

### Performance Optimization

1. **Connection Pooling**: LangChain's ChatOllama tự động handle connection pooling.

2. **Caching**: Có thể enable caching cho embeddings và responses nếu cần.

3. **Batch Processing**: Nếu có nhiều requests, có thể batch để tối ưu throughput.

## 8. Example: Full Setup

```bash
# 1. Set environment variable
export OLLAMA_HOST=http://192.168.1.100:11434

# 2. Run application
python main.py

# 3. Select model option 4 (Qwen2 Pentest)
# 4. Start using!
```

## Notes

- Model `qwen2_pentest` đã được fine-tune nên sẽ có performance tốt hơn cho pentest tasks
- Có thể dùng cho cả task analysis và tool execution nếu model hỗ trợ function calling
- Nếu model không hỗ trợ function calling, vẫn dùng FunctionGemma cho tool execution và `qwen2_pentest` cho analysis
