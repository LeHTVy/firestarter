# Model Configuration Guide

## Overview

Firestarter hỗ trợ **flexible model selection** - bạn có thể đổi models một cách linh hoạt mà không cần hardcode trong code.

## Configuration Files

### 1. `config/models.yaml`
Định nghĩa:
- **Model configuration templates** (temperature, top_p, etc.) - không hardcode model names
- **Model aliases** (e.g., "mistral" → "mistral:latest")
- **Default models** cho các roles khác nhau

### 2. `config/autogen_config.yaml`
Định nghĩa:
- **Agent configurations** với model assignments
- Mỗi agent có thể có `model` và `fallback_model`

## Cách Đổi Models

### Option 1: Đổi trong Config File (Permanent)

Edit `config/autogen_config.yaml`:
```yaml
agents:
  recon_agent:
    model: "qwen2-pentest-v2:latest"  # Đổi model ở đây
    fallback_model: "mistral:latest"
```

### Option 2: Environment Variables (Runtime Override)

Set environment variables trước khi chạy:
```bash
export RECON_AGENT_MODEL="qwen2-pentest-v2:latest"
export EXPLOIT_AGENT_MODEL="deepseek-r1:latest"
export ANALYSIS_AGENT_MODEL="mistral:latest"
./run.sh
```

### Option 3: Sử dụng Aliases

Trong `config/autogen_config.yaml`:
```yaml
agents:
  recon_agent:
    model: "mistral"  # Sẽ resolve thành "mistral:latest"
    # hoặc
    model: "qwen2_pentest"  # Sẽ resolve thành "qwen2-pentest-v2:latest"
```

### Option 4: Dynamic Resolution

Nếu model name không tồn tại, system sẽ:
1. Tự động tìm model tương tự trong Ollama
2. Fallback về model mặc định
3. Sử dụng fallback_model nếu có

## Model Name Formats

### Direct Model Names (Recommended)
```yaml
model: "mistral:latest"
model: "qwen2-pentest-v2:latest"
model: "deepseek-r1:latest"
```

### Aliases
```yaml
model: "mistral"  # → "mistral:latest"
model: "deepseek_r1"  # → "deepseek-r1:latest"
model: "qwen2_pentest"  # → "qwen2-pentest-v2:latest"
```

### Empty String (Uses Default)
```yaml
model: ""  # Sẽ dùng default từ models.yaml hoặc env var
```

## Environment Variable Overrides

Format: `{AGENT_NAME}_MODEL`

Examples:
- `RECON_AGENT_MODEL="qwen2-pentest-v2:latest"`
- `EXPLOIT_AGENT_MODEL="deepseek-r1:latest"`
- `ANALYSIS_AGENT_MODEL="mistral:latest"`
- `RESULTS_QA_AGENT_MODEL="mistral:latest"`

## Priority Order

1. **Environment variable** (highest priority)
2. **Config file model** (if not empty)
3. **Alias resolution** (if alias used)
4. **Default from models.yaml** (if model is empty)
5. **Fallback model** (if primary not available)
6. **Auto-discovery** (find similar model in Ollama)
7. **Ultimate fallback** ("mistral:latest")

## Examples

### Example 1: Đổi tất cả agents sang Qwen2 Pentest
```yaml
# config/autogen_config.yaml
agents:
  recon_agent:
    model: "qwen2-pentest-v2:latest"
  exploit_agent:
    model: "qwen2-pentest-v2:latest"
  analysis_agent:
    model: "qwen2-pentest-v2:latest"
```

### Example 2: Sử dụng Environment Variables
```bash
# .env file hoặc export
RECON_AGENT_MODEL="qwen2-pentest-v2:latest"
EXPLOIT_AGENT_MODEL="deepseek-r1:latest"
ANALYSIS_AGENT_MODEL="mistral:latest"
```

### Example 3: Mixed - Some agents use default, some custom
```yaml
agents:
  recon_agent:
    model: "qwen2-pentest-v2:latest"  # Custom
  exploit_agent:
    model: ""  # Uses default
  analysis_agent:
    model: "mistral"  # Uses alias
```

## Special Models

### DeepSeek-R1
```yaml
model: "deepseek-r1:latest"
# hoặc
model: "deepseek_r1"  # Alias
```
Sử dụng `DeepSeekAgent` class (special handling).

### Tool Calling Models
```yaml
model: "json_tool_calling"  # Uses tool calling registry
```
Sử dụng `ToolCallingModelRegistry` (for tool execution).

## Troubleshooting

### Model không được tìm thấy
1. Kiểm tra model có trong Ollama: `ollama list`
2. Kiểm tra model name đúng format: `model:tag` (e.g., "mistral:latest")
3. Kiểm tra environment variables: `echo $RECON_AGENT_MODEL`
4. Xem logs để biết model nào được resolve

### Model không được sử dụng
1. Kiểm tra priority order (env var > config > default)
2. Kiểm tra model có available trong Ollama
3. Kiểm tra fallback model có được sử dụng không

## Best Practices

1. **Sử dụng full model names** (e.g., "mistral:latest") thay vì aliases để rõ ràng
2. **Set fallback_model** cho mỗi agent để có backup
3. **Sử dụng environment variables** cho testing/development
4. **Document model choices** trong team để consistency
