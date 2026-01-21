"""Prompt router for multi-model coordination."""

from typing import Dict, Any, Optional
from models.generic_ollama_agent import GenericOllamaAgent


class PromptRouter:
    """Router for directing prompts to appropriate models/agents."""
    
    def __init__(self):
        """Initialize prompt router."""
        # Use Mistral for routing (replacing Qwen3)
        self.qwen3 = GenericOllamaAgent(
            model_name="mistral:latest",
            prompt_template="qwen3_system.jinja2"
        )
    
    def route(self, user_prompt: str) -> Dict[str, Any]:
        """Route user prompt to appropriate handler.
        
        Args:
            user_prompt: User prompt
            
        Returns:
            Routing decision
        """
        # Simple routing logic - can be enhanced with ML
        prompt_lower = user_prompt.lower()
        
        # Check for results Q&A
        if any(keyword in prompt_lower for keyword in ["kết quả", "result", "kết quả của", "kết quả tool"]):
            return {
                "handler": "results_qa",
                "confidence": 0.9
            }
        
        # Check for tool execution
        if any(keyword in prompt_lower for keyword in ["scan", "test", "check", "enum"]):
            return {
                "handler": "tool_execution",
                "confidence": 0.8
            }
        
        # Check for web search
        if any(keyword in prompt_lower for keyword in ["tìm", "search", "thông tin về"]):
            return {
                "handler": "web_search",
                "confidence": 0.7
            }
        
        # Default to analysis
        return {
            "handler": "analysis",
            "confidence": 0.5
        }
