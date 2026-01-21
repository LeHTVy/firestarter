---
name: implement-novee-inspired-features
overview: "Implement các features inspired từ Novee: structured reasoning format, multi-turn tool execution với feedback loops, tool execution feedback tracking, và environment-coupled learning approach để improve model behavior."
todos:
  - id: structured-reasoning-analysis
    content: Add structured reasoning format (<reasoning> + <output>) cho analysis models (Nemotron/Qwen3)
    status: completed
  - id: structured-reasoning-tools
    content: Add structured reasoning format cho tool execution (FunctionGemma) - explain tool selection
    status: completed
  - id: multi-turn-tool-execution
    content: Implement multi-turn tool execution với feedback loops - probe → observe → adapt
    status: completed
    dependencies:
      - structured-reasoning-tools
  - id: tool-feedback-tracking
    content: Implement tool execution feedback tracking - success rate, error types, execution time
    status: completed
  - id: environment-coupled-learning
    content: Build infrastructure cho environment-coupled learning - collect feedback từ tool executions
    status: completed
    dependencies:
      - tool-feedback-tracking
  - id: multi-turn-reasoning-analysis
    content: Support multi-turn reasoning trong analysis - iterative refinement với feedback
    status: completed
    dependencies:
      - structured-reasoning-analysis
  - id: result-analyzer
    content: Create result analyzer để extract findings và suggest next tools based on results
    status: completed
    dependencies:
      - tool-feedback-tracking
  - id: feedback-prompt-improvement
    content: Implement feedback-based prompt improvement - learn từ success metrics
    status: completed
    dependencies:
      - environment-coupled-learning
---

# Implement Novee-Inspired Features for Firestarter

## Goal:

Áp dụng các techniques từ Novee research vào Firestarter để improve model behavior:

- **Structured reasoning format** - Tách reasoning và output
- **Multi-turn tool execution** - Probe → Observe → Adapt strategy
- **Tool execution feedback tracking** - Learn từ success/failure
- **Environment-coupled learning** - Model adapts based on tool results

## Insights từ Novee:

1. **Small models outperform frontier LLMs** khi trained với right signals
2. **Environment feedback** (browser/tool results) là key cho RL
3. **Structured output** (`<think>` + `<output>`) giúp model focus
4. **Multi-turn reasoning** - Model probe, observe, adapt qua nhiều turns
5. **RL từ environment** - Model learns từ actual tool execution results

## Implementation Plan:

### Task 1: Structured Reasoning Format cho Analysis Model

- **Files**: 
- `prompts/nemotron_system.jinja2`
- `prompts/qwen3_system.jinja2`
- **Action**: 
- Add structured output format: `<reasoning>` và `<output>` blocks
- Model phải explain reasoning trước khi output JSON
- Parse và extract cả reasoning và output
- **Benefit**: Model tập trung vào output quality, easier to debug

### Task 2: Structured Reasoning Format cho Tool Execution

- **Files**: 
- `prompts/functiongemma_system.jinja2`
- **Action**: 
- Add `<reasoning>` block để model explain tool selection
- Format: `<reasoning> why choose this tool </reasoning> <tool_call> actual call </tool_call>`
- Parse reasoning để log và learn
- **Benefit**: Understand model decision-making, improve prompts

### Task 3: Multi-Turn Tool Execution với Feedback Loops

- **Files**: 
- `agents/tool_executor_node.py`
- `agents/pentest_graph.py`
- **Action**: 
- Implement feedback loop: tool execution → analyze results → decide next tool
- Allow model to adapt strategy based on tool outputs
- Support sequential tool execution với context passing
- Add state tracking: previous tools, results, strategy
- **Benefit**: Model có thể probe và adapt như attacker thật

### Task 4: Tool Execution Feedback Tracking

- **Files**: 
- `rag/results_storage.py` (extend)
- New: `agents/tool_feedback_tracker.py`
- **Action**: 
- Track tool execution metrics: success rate, error types, execution time
- Store feedback: which tools work best for which scenarios
- Track parameter effectiveness
- Build feedback dataset cho future training
- **Benefit**: Data-driven improvement của tool selection

### Task 5: Environment-Coupled Learning Infrastructure

- **Files**: 
- New: `agents/feedback_learner.py`
- `agents/pentest_graph.py` (integrate)
- **Action**: 
- Implement feedback collection từ tool executions
- Track: tool success/failure, output quality, time to success
- Use feedback để improve prompts và tool selection logic
- Optional: Implement simple RL loop (reward = tool success)
- **Benefit**: Model improves over time từ actual execution results

### Task 6: Multi-Turn Reasoning trong Analysis

- **Files**: 
- `agents/pentest_graph.py` - `_analyze_node`
- **Action**: 
- Allow analysis model to request more info nếu cần
- Support iterative refinement: initial analysis → get feedback → refine
- Model có thể ask clarifying questions hoặc request tool results
- **Benefit**: Better analysis quality, model adapts to context

### Task 7: Tool Execution Result Analysis

- **Files**: 
- New: `agents/result_analyzer.py`
- **Action**: 
- Analyze tool execution results để determine next steps
- Extract findings: subdomains found, ports open, vulnerabilities detected
- Suggest next tools based on findings
- Similar to Novee's "observe → adapt" pattern
- **Benefit**: Intelligent tool chaining based on actual results

### Task 8: Feedback-Based Prompt Improvement

- **Files**: 
- `agents/prompt_optimizer.py` (new)
- **Action**: 
- Collect feedback từ tool executions
- Identify patterns: which prompts lead to better tool selection
- Automatically improve prompts based on success metrics
- A/B test prompt variations
- **Benefit**: Continuous improvement của model behavior