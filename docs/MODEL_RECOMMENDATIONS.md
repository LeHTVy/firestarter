# Model Recommendations cho General Analysis

## Vấn đề hiện tại
Qwen3 vẫn refuse security testing requests mặc dù đã có nhiều cải thiện trong prompt.

## Models đề xuất (theo thứ tự ưu tiên)

### 1. **Llama 3.1 8B/70B** ⭐ **KHUYẾN NGHỊ NHẤT**
- **Lý do**: Ít safety filters hơn, dễ fine-tune behavior
- **Ollama**: `ollama pull llama3.1:8b` hoặc `llama3.1:70b`
- **Pros**: 
  - Ít refuse hơn Qwen3
  - Tốt cho task breakdown và analysis
  - Có thể adjust system prompt dễ dàng
- **Cons**: Cần RAM nhiều hơn (70B cần ~40GB RAM)

### 2. **Qwen 2.5 72B** 
- **Lý do**: Phiên bản mới hơn Qwen3, cải thiện instruction following
- **Ollama**: `ollama pull qwen2.5:72b`
- **Pros**:
  - Tốt cho tiếng Việt (nếu cần)
  - Coding và structured output tốt
- **Cons**: Vẫn có thể refuse (nhưng ít hơn Qwen3)

### 3. **Mistral 7B/22B**
- **Lý do**: Rất ít safety filters, được thiết kế cho technical tasks
- **Ollama**: `ollama pull mistral:7b` hoặc `mistral:22b`
- **Pros**:
  - Rất ít refuse
  - Nhanh và hiệu quả
  - Tốt cho structured tasks
- **Cons**: Có thể kém hơn về reasoning so với Llama 3.1

### 4. **DeepSeek-V2 7B/67B**
- **Lý do**: Được train với ít safety filters, focus vào technical tasks
- **Ollama**: `ollama pull deepseek-v2:7b` hoặc `deepseek-v2:67b`
- **Pros**:
  - Rất ít refuse
  - Tốt cho coding và technical analysis
  - Fast inference
- **Cons**: Có thể cần test với security tasks

### 5. **Phi-3 Medium (3.8B)**
- **Lý do**: Microsoft model, ít safety filters, nhẹ
- **Ollama**: `ollama pull phi3:medium`
- **Pros**:
  - Rất nhẹ (chỉ 3.8B)
  - Fast inference
  - Ít refuse
- **Cons**: Có thể kém về reasoning so với models lớn hơn

## Implementation Strategy

### Option 1: Switch ngay sang Llama 3.1 8B
```yaml
# config/ollama_config.yaml
models:
  general_analysis:
    model_name: "llama3.1:8b"
    temperature: 0.8
    top_p: 0.95
```

### Option 2: Multi-model fallback chain
1. Try Llama 3.1 8B first
2. If refuse → fallback to Mistral 7B
3. If still refuse → fallback to DeepSeek-V2 7B

### Option 3: Model selection based on task type
- Security testing tasks → Mistral hoặc DeepSeek-V2
- General analysis → Llama 3.1
- Question answering → Qwen 2.5

## Testing Checklist

Sau khi switch model, test với:
- [ ] "attack hellogroup.co.za"
- [ ] "exploit target.com"
- [ ] "scan 192.168.1.1"
- [ ] "test security of example.com"
- [ ] "assess vulnerabilities in domain.com"

Measure:
- Refusal rate
- JSON output quality
- Task breakdown accuracy
- Response time

## Quick Start

```bash
# Pull recommended model
ollama pull llama3.1:8b

# Update config
# Edit config/ollama_config.yaml: change qwen3 model_name to llama3.1:8b

# Test
python main.py
```
