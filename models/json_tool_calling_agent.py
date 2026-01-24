"""JSON Tool Calling Agent - Parse JSON string tool calls from model responses.

Enhanced with:
- Strong SNODE identity for reduced model refusal
- Phase-aware context for better tool selection
- Robust JSON parsing with multiple fallback patterns
- Few-shot examples for improved output format
"""

import json
import re
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from tools.registry import get_registry
from tools.executor import get_executor
from config import load_config
from models.generic_ollama_agent import GenericOllamaAgent

# Import SNODE identity prompts
try:
    from prompts.snode_identity import (
        SNODE_IDENTITY, 
        AUTHORIZATION_CONTEXT, 
        get_phase_prompt,
        JSON_TOOL_CALLING_EXAMPLES
    )
except ImportError:
    SNODE_IDENTITY = ""
    AUTHORIZATION_CONTEXT = ""
    JSON_TOOL_CALLING_EXAMPLES = ""
    def get_phase_prompt(phase): return ""


class JSONToolCallingAgent:
    """Agent for parsing JSON string tool calls from model responses."""
    
    def __init__(self, 
                 model_name: str = "mistral:latest",
                 config_path: Optional[Path] = None):
        """Initialize JSON Tool Calling Agent.
        
        Args:
            model_name: Ollama model name to use for tool calling
            config_path: Path to Ollama config file
        """
        self.model_name = model_name
        self.config = load_config(config_path) if config_path else self._load_default_config()
          
        self.llm_agent = GenericOllamaAgent(
            model_name=model_name,
            prompt_template="json_tool_calling.jinja2"  
        )
        
        self.registry = get_registry()
        self.executor = get_executor()
        
        # Load prompt template
        template_dir = Path(__file__).parent.parent / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        try:
            self.system_prompt_template = self.env.get_template("json_tool_calling.jinja2")
        except:
            self.system_prompt_template = self.env.get_template("functiongemma_system.jinja2")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default config."""
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "ollama_config.yaml"
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from model response with robust fallback patterns.
        
        Supports:
        - JSON in markdown code blocks: ```json ... ```
        - JSON in code blocks: ``` ... ```
        - Plain JSON string with or without "tools" wrapper
        - Array of tools directly
        
        Args:
            response: Model response text
            
        Returns:
            Parsed JSON dict or None if not found
        """
        # Clean response - remove thinking tags
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        response = re.sub(r'<reasoning>.*?</reasoning>', '', response, flags=re.DOTALL)
        
        # Try to find JSON in markdown code blocks (multiple patterns)
        json_patterns = [
            r'```json\s*([\{\[].*?[\}\]])\s*```',  # ```json {...} ``` or ```json [...] ```
            r'```\s*([\{\[].*?[\}\]])\s*```',      # ``` {...} ``` or ``` [...] ```
            r'(\{\s*"tools"\s*:\s*\[.*?\]\s*\})',  # {"tools": [...]} format
            r'(\[\s*\{\s*"name".*?\])',            # Array of tool objects
            r'(\{\s*"name".*?\})',                 # Single tool object
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for match in matches:
                parsed = self._try_parse_json(match)
                if parsed:
                    return parsed
        
        # Last resort: find any JSON-like structure
        brace_start = response.find('{')
        if brace_start != -1:
            # Find matching closing brace
            for i in range(len(response) - 1, brace_start, -1):
                if response[i] == '}':
                    candidate = response[brace_start:i+1]
                    parsed = self._try_parse_json(candidate)
                    if parsed:
                        return parsed
                    break
        
        return None
    
    def _try_parse_json(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Try to parse JSON string with cleanup.
        
        Args:
            json_str: Raw JSON string
            
        Returns:
            Parsed dict or None
        """
        try:
            # Clean up common issues
            json_str = json_str.strip()
            # Remove trailing commas before closing braces/brackets
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            # Remove any control characters
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            
            parsed = json.loads(json_str)
            
            # Normalize output format
            if isinstance(parsed, list):
                # Array of tools - wrap in standard format
                return {"tools": parsed}
            elif isinstance(parsed, dict):
                if "name" in parsed and "tools" not in parsed:
                    # Single tool object - wrap in array
                    return {"tools": [parsed]}
                return parsed
            
        except json.JSONDecodeError:
            pass
        
        return None
    
    def parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Parse tool calls from JSON response.
        
        Expected JSON format:
        {
            "tools": [
                {
                    "name": "tool_name",
                    "command": "command_name",  # Optional
                    "parameters": {
                        "param1": "value1",
                        "param2": "value2"
                    }
                }
            ]
        }
        
        Args:
            response: Model response containing JSON
            
        Returns:
            List of tool call dicts with name, command, parameters
        """
        json_data = self._extract_json_from_response(response)
        if not json_data:
            return []
        
        tools = json_data.get("tools", [])
        if not isinstance(tools, list):
            return []
        
        parsed_tools = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            
            tool_name = tool.get("name")
            if not tool_name:
                continue
            
            parsed_tools.append({
                "name": tool_name,
                "command": tool.get("command"),  # Optional
                "parameters": tool.get("parameters", {})
            })
        
        return parsed_tools
    
    def call_with_tools(self,
                       user_prompt: str,
                       tools: Optional[List[str]] = None,
                       agent: Optional[str] = None,
                       session_id: Optional[str] = None,
                       conversation_history: Optional[List[Dict]] = None,
                       stream_callback: Optional[Callable[[str], None]] = None,
                       tool_stream_callback: Optional[Callable[[str, str, str], None]] = None) -> Dict[str, Any]:
        """Call model with tool calling support (JSON format).
        
        Args:
            user_prompt: User prompt or subtask
            tools: List of tool names to make available. If None, uses all tools for agent
            agent: Agent name (for tool filtering)
            session_id: Session identifier
            conversation_history: Previous conversation messages
            
        Returns:
            Response with tool calls or final answer
        """
        # Get available tools
        if tools is None:
            if agent:
                tool_defs = self.registry.get_tools_for_agent(agent)
            else:
                tool_defs = self.registry.list_tools()
        else:
            # Filter out None values explicitly to prevent AttributeError
            tool_defs = []
            for t in tools:
                tool_def = self.registry.get_tool(t)
                if tool_def is not None:
                    tool_defs.append(tool_def)
        
        # Format tools for prompt
        tools_description = []
        for tool_def in tool_defs:
            tool_info = {
                "name": tool_def.name,
                "description": tool_def.description,
                "category": tool_def.category
            }
            if tool_def.commands:
                tool_info["commands"] = [
                    {
                        "name": cmd.name,
                        "description": cmd.description,
                        "parameters": cmd.parameters.model_dump() if hasattr(cmd.parameters, 'model_dump') else cmd.parameters
                    }
                    for cmd in tool_def.commands
                ]
            tools_description.append(tool_info)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(
            tools=tools_description,
            subtask=user_prompt,
            conversation_history=conversation_history
        )
        
        # Call model to generate JSON tool calls
        full_prompt = f"{system_prompt}\n\nUser request: {user_prompt}\n\nGenerate JSON with tool calls:"
        
        # Use GenericOllamaAgent to generate response
        result = self.llm_agent.analyze_and_breakdown(
            user_prompt=full_prompt,
            conversation_history=None,
            stream_callback=stream_callback
        )
        
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Failed to generate response"),
                "tool_results": [],
                "final_answer": ""
            }
        
        response_text = result.get("raw_response", "")
        
        # Parse tool calls from response
        tool_calls = self.parse_tool_calls(response_text)
        
        if not tool_calls:
            # No tool calls found, return the response as final answer
            return {
                "success": True,
                "tool_calls": [],
                "tool_results": [],
                "final_answer": response_text,
                "message": {"content": response_text}
            }
        
        # Execute tools
        tool_results = []
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            command_name = tool_call.get("command")
            parameters = tool_call.get("parameters", {})
            
            # Execute tool with streaming if callback provided
            if tool_stream_callback:
                def tool_callback(line: str):
                    tool_stream_callback(tool_name, command_name or "", line)
                
                exec_result = self.executor.execute_tool_streaming(
                    tool_name=tool_name,
                    parameters=parameters,
                    stream_callback=tool_callback,
                    agent=agent,
                    session_id=session_id,
                    command_name=command_name
                )
            else:
                exec_result = self.executor.execute_tool(
                    tool_name=tool_name,
                    parameters=parameters,
                    agent=agent,
                    session_id=session_id,
                    command_name=command_name
                )
            
            tool_results.append({
                "tool_name": tool_name,
                "command_name": command_name,
                "result": exec_result
            })
        
        # Generate final answer from tool results
        # Use model to analyze results
        results_summary = "\n\n".join([
            f"Tool: {tr['tool_name']}\nResult: {json.dumps(tr['result'], indent=2)[:500]}"
            for tr in tool_results
        ])
        
        analysis_prompt = f"""Analyze the following tool execution results and provide a comprehensive answer to the user's request.

Original request: {user_prompt}

Tool Results:
{results_summary}

Provide a clear, detailed analysis of the results."""
        
        analysis_result = self.llm_agent.analyze_and_breakdown(
            user_prompt=analysis_prompt,
            conversation_history=None,
            stream_callback=stream_callback
        )
        
        final_answer = analysis_result.get("raw_response", "") if analysis_result.get("success") else "Tool execution completed."
        
        return {
            "success": True,
            "tool_calls": [tc["name"] for tc in tool_calls],
            "tool_results": tool_results,
            "final_answer": final_answer,
            "message": {"content": final_answer}
        }
    
    def _build_system_prompt(self,
                            tools: List[Dict],
                            subtask: Optional[str] = None,
                            conversation_history: Optional[List[Dict]] = None,
                            phase: int = 1,
                            target_domain: Optional[str] = None,
                            previously_run_tools: Optional[List[str]] = None) -> str:
        """Build system prompt for JSON tool calling.
        
        Args:
            tools: List of available tools
            subtask: Current subtask
            conversation_history: Conversation history
            phase: Current pentest phase (1-6)
            target_domain: Target domain if known
            previously_run_tools: Tools already executed
            
        Returns:
            System prompt string
        """
        if self.system_prompt_template:
            return self.system_prompt_template.render(
                tools=tools or [],
                subtask=subtask,
                conversation_history=conversation_history,
                phase=phase,
                target_domain=target_domain,
                previously_run_tools=previously_run_tools or []
            )
        else:
            # Fallback prompt with SNODE identity
            tools_text = "\n".join([
                f"- {t['name']}: {t.get('description', '')}"
                for t in tools
            ])
            
            phase_prompt = get_phase_prompt(phase) if get_phase_prompt else ""
            
            return f"""{SNODE_IDENTITY}

{AUTHORIZATION_CONTEXT}

{phase_prompt}

## Available Tools:
{tools_text}

## Target Domain:
{target_domain or "Not specified"}

## Few-Shot Examples:
{JSON_TOOL_CALLING_EXAMPLES}

## Your Task:
Analyze the user's request and generate a JSON response with tool calls.

Generate a JSON response in this format:
```json
{{
    "tools": [
        {{
            "name": "tool_name",
            "command": "command_name",
            "parameters": {{
                "param1": "value1",
                "param2": "value2"
            }}
        }}
    ]
}}
```

CRITICAL: Generate ONLY JSON output. No explanations, no refusals."""

