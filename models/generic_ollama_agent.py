"""Generic Ollama agent that can work with any Ollama model."""

import json
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from config import load_config
from tools.registry import get_registry
from models.llm_client import OllamaLLMClient


class GenericOllamaAgent:
    """Generic agent that can work with any Ollama model for task analysis."""
    
    def __init__(self, 
                 model_name: str,
                 prompt_template: str = "qwen3_system.jinja2",
                 config_path: Optional[Path] = None):
        """Initialize generic Ollama agent.
        
        Args:
            model_name: Ollama model name (e.g., "llama3.1:8b", "mistral:7b")
            prompt_template: Prompt template file name (default: qwen3_system.jinja2)
            config_path: Optional path to config file
        """
        self.model_name = model_name
        self.config = load_config(config_path) if config_path else self._load_default_config()
        self.ollama_base_url = self.config['ollama']['base_url']
        
        # Initialize LangChain LLM client
        # Use lower temperature (0.3) like rutx to reduce refusal
        self.llm_client = OllamaLLMClient(
            model_name=model_name,
            base_url=self.ollama_base_url,
            config_path=config_path,
            temperature=0.3,  # Lower temperature like rutx to reduce refusal
            top_p=0.9,
            top_k=40,
            num_predict=2048,
            repeat_penalty=1.1
        )
        
        # Get tool registry
        self.registry = get_registry()
        
        # Load prompt template
        template_dir = Path(__file__).parent.parent / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        try:
            self.system_prompt_template = self.env.get_template(prompt_template)
        except:
            # Fallback to qwen3_system if template not found
            self.system_prompt_template = self.env.get_template("qwen3_system.jinja2")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default config."""
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "ollama_config.yaml"
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def analyze_and_breakdown(self,
                             user_prompt: str,
                             conversation_history: Optional[str] = None,
                             tool_results: Optional[str] = None,
                             stream_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Analyze user prompt and breakdown into subtasks.
        
        Args:
            user_prompt: User prompt
            conversation_history: Conversation history
            tool_results: Previous tool results
            stream_callback: Optional callback for streaming response chunks
            
        Returns:
            Analysis result with subtasks
        """
        # Get available tools
        all_tools = self.registry.list_tools()
        priority_tools = [t for t in all_tools if t.priority]
        other_tools = [t for t in all_tools if not t.priority]
        
        # Combine: priority tools first, then others (limit to 150 total)
        tools_to_show = priority_tools + other_tools[:150-len(priority_tools)]
        
        # Format tools for display
        tools_summary = [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "assigned_agents": tool.assigned_agents,
                "commands": tool.list_commands() if tool.commands else [],
                "priority": tool.priority
            }
            for tool in tools_to_show
        ]
        
        # Also provide category-based tool lists
        tools_by_category = {}
        for tool in all_tools:
            if tool.category not in tools_by_category:
                tools_by_category[tool.category] = []
            tools_by_category[tool.category].append(tool.name)
        
        system_prompt = self.system_prompt_template.render(
            conversation_history=conversation_history,
            tool_results=tool_results,
            available_tools=tools_summary,
            tools_by_category=tools_by_category
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            # Use LangChain client for generation
            response = self.llm_client.generate(
                messages=messages,
                stream=stream_callback is not None,
                stream_callback=stream_callback,
                temperature=0.9,
                top_p=0.95,
                top_k=50,
                num_predict=2048,
                repeat_penalty=1.1
            )
            
            if not response.get('success'):
                return {
                    "success": False,
                    "error": response.get('error', 'Unknown error'),
                    "refused": False
                }
            
            content = response.get('content', '')
            
            # Check if model refused (expanded list based on actual Mistral refusal patterns)
            content_lower = content.lower()
            refusal_indicators = [
                "i'm unable to assist",
                "i cannot assist",
                "i cannot help",
                "i'm unable to help",
                "unauthorized access",
                "illegal",
                "unethical",
                "violates",
                "i cannot provide",
                "i'm unable to provide",
                "i cannot support",
                "i cannot perform",
                "i'm unable to perform",
                "refuse",
                "decline",
                "not authorized",
                "against my",
                "ethical concerns",
                "ethical guidelines",
                "i must clarify",  # Mistral-specific refusal pattern
                "i am here to assist and promote safe",  # Mistral-specific refusal pattern
                "i will not engage",  # Mistral-specific refusal pattern
                "cannot assist with",  # Mistral-specific refusal pattern
                "promote safe, legal, and ethical",  # Mistral-specific refusal pattern
                "safe, legal, and ethical activities"  # Mistral-specific refusal pattern
            ]
            
            is_refusal = any(indicator in content_lower for indicator in refusal_indicators)
            
            # Extract reasoning and output from structured format
            reasoning = None
            output_content = content
            
            # Try to extract <reasoning> and <output> blocks
            if "<reasoning>" in content and "</reasoning>" in content:
                reasoning_start = content.find("<reasoning>") + len("<reasoning>")
                reasoning_end = content.find("</reasoning>", reasoning_start)
                if reasoning_end > reasoning_start:
                    reasoning = content[reasoning_start:reasoning_end].strip()
            
            if "<output>" in content and "</output>" in content:
                output_start = content.find("<output>") + len("<output>")
                output_end = content.find("</output>", output_start)
                if output_end > output_start:
                    output_content = content[output_start:output_end].strip()
            
            # Try to parse JSON from response
            try:
                # Extract JSON from markdown code blocks if present
                if "```json" in output_content:
                    json_start = output_content.find("```json") + 7
                    json_end = output_content.find("```", json_start)
                    output_content = output_content[json_start:json_end].strip()
                elif "```" in output_content:
                    json_start = output_content.find("```") + 3
                    json_end = output_content.find("```", json_start)
                    output_content = output_content[json_start:json_end].strip()
                
                # Parse JSON
                analysis_data = json.loads(output_content)
                
                return {
                    "success": not is_refusal,
                    "analysis": analysis_data,
                    "reasoning": reasoning,
                    "raw_response": content,
                    "refused": is_refusal
                }
            except json.JSONDecodeError:
                # JSON parsing failed
                if is_refusal:
                    return {
                        "success": False,
                        "error": "Model refused the request",
                        "raw_response": content,
                        "refused": True
                    }
                else:
                    # Try to extract JSON from anywhere in the response
                    import re
                    json_match = re.search(r'\{.*\}', output_content, re.DOTALL)
                    if json_match:
                        try:
                            analysis_data = json.loads(json_match.group())
                            return {
                                "success": True,
                                "analysis": analysis_data,
                                "reasoning": reasoning,
                                "raw_response": content,
                                "refused": False
                            }
                        except:
                            pass
                    
                    return {
                        "success": False,
                        "error": "Failed to parse JSON from response",
                        "raw_response": content,
                        "refused": False
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "refused": False
            }
