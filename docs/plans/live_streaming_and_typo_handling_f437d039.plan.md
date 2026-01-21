---
name: Live Streaming and Typo Handling
overview: Implement live streaming for tool execution and model responses with structured Rich panels, plus fuzzy matching and typo correction for targets, tools, and parameters.
todos:
  - id: streaming_manager
    content: Create StreamingManager class in ui/streaming_manager.py to coordinate all streaming events
    status: completed
  - id: rich_panels
    content: Create Rich panel components in ui/panels.py (ToolExecutionPanel, ModelResponsePanel, ProgressPanel)
    status: completed
  - id: input_normalizer
    content: Create InputNormalizer in utils/input_normalizer.py for typo correction and target extraction
    status: completed
  - id: fuzzy_matcher
    content: Create fuzzy matching utilities in utils/fuzzy_matcher.py for tool name matching
    status: completed
  - id: tool_executor_streaming
    content: Add execute_tool_streaming() method to tools/executor.py with stream_callback support
    status: in_progress
    dependencies:
      - streaming_manager
  - id: model_agents_streaming
    content: Update all model agents (qwen3, functiongemma, deepseek) to support streaming with ollama.chat(stream=True)
    status: pending
    dependencies:
      - streaming_manager
  - id: pentest_graph_streaming
    content: Modify agents/pentest_graph.py to use graph.stream() instead of graph.invoke() and pass streaming callbacks
    status: pending
    dependencies:
      - tool_executor_streaming
      - model_agents_streaming
  - id: main_ui_streaming
    content: Update main.py to use StreamingManager and display structured panels with live updates
    status: pending
    dependencies:
      - rich_panels
      - pentest_graph_streaming
  - id: integrate_normalizer
    content: Integrate InputNormalizer into Qwen3Agent, FunctionGemmaAgent, and ToolExecutor for input preprocessing
    status: pending
    dependencies:
      - input_normalizer
      - fuzzy_matcher
  - id: update_requirements
    content: Add rapidfuzz and python-Levenshtein to requirements.txt
    status: completed
---

# Live Streaming and Typo Handling Implementation

## Overview

This plan implements two major features:

1. **Live Streaming**: Real-time display of tool execution progress and model responses using Rich structured panels
2. **Typo/Fuzzy Matching**: Intelligent target extraction and correction for typos, misspellings, and spacing issues

## Architecture

### Streaming Flow

```
User Input
  ↓
[Input Normalizer] → Fix typos, extract targets
  ↓
[PentestGraph] → Stream events
  ├─→ [Tool Executor] → Stream tool output
  ├─→ [Model Agents] → Stream model responses
  └─→ [Main UI] → Display in structured panels
```

### Typo Handling Flow

```
User Input: "scan 192.168.1. 1" or "nmap scan 192.168.1.1"
  ↓
[Input Parser] → Extract potential targets/tools
  ↓
[Fuzzy Matcher] → Match against known tools/targets
  ├─→ Tool name correction: "nmap scan" → "nmap:quick_scan"
  ├─→ Target normalization: "192.168.1. 1" → "192.168.1.1"
  └─→ Parameter extraction with fuzzy matching
  ↓
[Corrected Input] → Pass to agents
```

## Implementation Details

### 1. Streaming Infrastructure

#### 1.1 Create Streaming Manager

**File**: `ui/streaming_manager.py`

- `StreamingManager` class to handle all streaming events
- Methods:
  - `create_tool_panel(tool_name, command_name)` - Create panel for tool execution
  - `update_tool_output(tool_name, line)` - Stream tool output line-by-line
  - `create_model_panel(model_name)` - Create panel for model response
  - `stream_model_response(model_name, chunk)` - Stream model tokens
  - `complete_panel(panel_id, success)` - Mark panel as complete

#### 1.2 Update Tool Executor

**File**: `tools/executor.py`

- Add `execute_tool_streaming()` method
- Accept `stream_callback: Callable[[str], None]` parameter
- For subprocess-based tools, use `execute_stream()` method (already exists)
- Stream output line-by-line to callback
- Return execution result when complete

#### 1.3 Update Model Agents

**Files**:

- `models/qwen3_agent.py`
- `models/functiongemma_agent.py`
- `models/deepseek_agent.py`

- Add `stream=True` parameter to `ollama.chat()` calls
- Use `ollama.chat(..., stream=True)` which returns generator
- Yield chunks to streaming callback
- Example:
  ```python
  response = ollama.chat(..., stream=True)
  for chunk in response:
      content = chunk.get('message', {}).get('content', '')
      if content:
          stream_callback(content)
  ```


#### 1.4 Update PentestGraph

**File**: `agents/pentest_graph.py`

- Modify `run()` method to accept `stream_callback` parameter
- Use LangGraph's `stream()` instead of `invoke()`
- Stream state updates to callback
- Pass streaming callbacks to tool execution and model calls

#### 1.5 Update Main UI

**File**: `main.py`

- Create `StreamingManager` instance
- Replace `graph.run()` with `graph.stream()`
- Handle streaming events:
  - Tool execution events → Update tool panel
  - Model response events → Update model panel
  - State updates → Show progress

### 2. Typo/Fuzzy Matching

#### 2.1 Create Input Normalizer

**File**: `utils/input_normalizer.py`

- `InputNormalizer` class
- Methods:
  - `normalize_target(target: str) -> str` - Fix spacing, typos in IPs/domains
  - `fuzzy_match_tool(tool_name: str) -> str` - Match tool name with fuzzy matching
  - `extract_targets(text: str) -> List[str]` - Extract IPs, domains, URLs
  - `normalize_input(user_input: str) -> Dict[str, Any]` - Main normalization

#### 2.2 Fuzzy Matching Library

- Use `fuzzywuzzy` or `rapidfuzz` for string matching
- Use `python-Levenshtein` for fast Levenshtein distance
- Create tool name dictionary from registry
- Create target patterns (IP regex, domain regex)

#### 2.3 Target Extraction

- IP addresses: `\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}` with spacing handling
- Domains: Extract with fuzzy matching against common TLDs
- URLs: Parse and normalize

#### 2.4 Integration Points

- **Qwen3Agent**: Normalize input before analysis
- **FunctionGemmaAgent**: Fuzzy match tool names before tool calling
- **Tool Executor**: Normalize target parameters before execution

### 3. Rich UI Components

#### 3.1 Structured Panels

**File**: `ui/panels.py`

- `ToolExecutionPanel` - Shows tool name, command, live output
- `ModelResponsePanel` - Shows model name, streaming response
- `ProgressPanel` - Shows overall workflow progress
- Use Rich's `Live` context manager for real-time updates

#### 3.2 Update Main Loop

**File**: `main.py`

- Replace simple `console.print()` with structured panels
- Use `Live` context for each panel
- Update panels as events stream in

## Files to Create/Modify

### New Files

1. `ui/__init__.py`
2. `ui/streaming_manager.py` - Central streaming coordinator
3. `ui/panels.py` - Rich panel components
4. `utils/__init__.py`
5. `utils/input_normalizer.py` - Typo correction and normalization
6. `utils/fuzzy_matcher.py` - Fuzzy matching utilities

### Modified Files

1. `main.py` - Add streaming UI and input normalization
2. `agents/pentest_graph.py` - Add streaming support to `run()` method
3. `tools/executor.py` - Add `execute_tool_streaming()` method
4. `models/qwen3_agent.py` - Add streaming support
5. `models/functiongemma_agent.py` - Add streaming support
6. `models/deepseek_agent.py` - Add streaming support
7. `requirements.txt` - Add `rapidfuzz`, `python-Levenshtein`

## Dependencies

Add to `requirements.txt`:

```
rapidfuzz>=3.0.0
python-Levenshtein>=0.21.0
```

## Example Usage

### Streaming Output

```
┌─ Tool: nmap:quick_scan ─────────────────────┐
│ Target: 192.168.1.1                        │
│ Status: Running...                          │
│ Output:                                     │
│   Starting Nmap 7.94...                    │
│   Scanning 192.168.1.1...                   │
│   Found 3 open ports                        │
└─────────────────────────────────────────────┘

┌─ Model: qwen3:8b ──────────────────────────┐
│ Analyzing task...                           │
│ Breaking down into subtasks...             │
│ ✓ Identified 3 tools needed                │
└─────────────────────────────────────────────┘
```

### Typo Handling

- Input: `"scan 192.168.1. 1 with nmap"`
- Normalized: `"scan 192.168.1.1 with nmap:quick_scan"`
- Extracted: `{"target": "192.168.1.1", "tool": "nmap:quick_scan"}`

## Testing Strategy

1. Test streaming with long-running tools (nmap full scan)
2. Test typo correction with various misspellings
3. Test target extraction with spacing issues
4. Test fuzzy tool matching with partial names