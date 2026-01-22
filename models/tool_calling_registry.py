"""Tool Calling Model Registry - Manage different tool calling models."""

from typing import Dict, Any, Optional, Protocol, List, Callable
from pathlib import Path

from models.functiongemma_agent import FunctionGemmaAgent
from models.json_tool_calling_agent import JSONToolCallingAgent


class ToolCallingAgent(Protocol):
    """Protocol for tool calling agents."""
    
    def call_with_tools(self,
                       user_prompt: str,
                       tools: Optional[List[str]] = None,
                       agent: Optional[str] = None,
                       session_id: Optional[str] = None,
                       conversation_history: Optional[List[Dict]] = None,
                       stream_callback: Optional[Callable[[str], None]] = None,
                       tool_stream_callback: Optional[Callable[[str, str, str], None]] = None) -> Dict[str, Any]:
        """Call model with tool calling support.
        
        Returns:
            Dict with success, tool_calls, tool_results, final_answer
        """
        ...


class ToolCallingModelRegistry:
    """Registry for managing tool calling models."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize tool calling model registry.
        
        Args:
            config_path: Optional path to config file
        """
        self.config_path = config_path
        self._models: Dict[str, ToolCallingAgent] = {}
        self._default_model = "functiongemma"
        
        # Initialize default models
        self._initialize_default_models()
    
    def _initialize_default_models(self):
        """Initialize default tool calling models."""
        # FunctionGemma (Ollama function calling format)
        try:
            self._models["functiongemma"] = FunctionGemmaAgent(config_path=self.config_path)
        except Exception as e:
            print(f"Warning: Failed to initialize FunctionGemma: {e}")
        
        # JSON Tool Calling (JSON string format)
        try:
            # Default to mistral:latest, can be configured
            self._models["json_tool_calling"] = JSONToolCallingAgent(
                model_name="mistral:latest",
                config_path=self.config_path
            )
        except Exception as e:
            print(f"Warning: Failed to initialize JSON Tool Calling: {e}")
    
    def register_model(self, name: str, agent: ToolCallingAgent):
        """Register a new tool calling model.
        
        Args:
            name: Model name identifier
            agent: Tool calling agent instance
        """
        self._models[name] = agent
    
    def get_model(self, name: Optional[str] = None) -> ToolCallingAgent:
        """Get tool calling model by name.
        
        Args:
            name: Model name. If None, returns default model
            
        Returns:
            Tool calling agent instance
            
        Raises:
            ValueError: If model not found
        """
        model_name = name or self._default_model
        
        if model_name not in self._models:
            raise ValueError(f"Tool calling model '{model_name}' not found. Available: {list(self._models.keys())}")
        
        return self._models[model_name]
    
    def list_models(self) -> List[str]:
        """List all available tool calling models.
        
        Returns:
            List of model names
        """
        return list(self._models.keys())
    
    def set_default(self, name: str):
        """Set default tool calling model.
        
        Args:
            name: Model name
            
        Raises:
            ValueError: If model not found
        """
        if name not in self._models:
            raise ValueError(f"Tool calling model '{name}' not found. Available: {list(self._models.keys())}")
        
        self._default_model = name
    
    def get_default(self) -> str:
        """Get default model name.
        
        Returns:
            Default model name
        """
        return self._default_model


# Global registry instance
_registry: Optional[ToolCallingModelRegistry] = None


def get_tool_calling_registry(config_path: Optional[Path] = None) -> ToolCallingModelRegistry:
    """Get global tool calling model registry.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Tool calling model registry instance
    """
    global _registry
    if _registry is None:
        _registry = ToolCallingModelRegistry(config_path=config_path)
    return _registry
