"""
Pydantic models for tool definitions.

Adapted from firestarter pattern for cleaner tool registry.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Tool parameter definition."""
    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None
    default: Optional[Any] = None
    required: bool = False


class ToolSchema(BaseModel):
    """Tool parameter schema."""
    type: str = "object"
    properties: Dict[str, ToolParameter] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class CommandDefinition(BaseModel):
    """Command definition within a tool."""
    description: str
    parameters: ToolSchema = Field(default_factory=ToolSchema)
    timeout: Optional[int] = 300
    requires_sudo: bool = False
    output_format: str = "text"
    phase: Optional[int] = None
    phase_reason: Optional[str] = None
    use_cases: Optional[List[str]] = None


class ToolDefinition(BaseModel):
    """Security tool definition."""
    name: str  
    description: str
    category: str
    priority: bool = False
    assigned_agents: List[str] = Field(default_factory=list)
    implementation: Optional[str] = None
    executable_names: List[str] = Field(default_factory=list)
    install_hint: Optional[str] = None
    commands: Dict[str, CommandDefinition] = Field(default_factory=dict)
    
    def get_command(self, command_name: str) -> Optional[CommandDefinition]:
        """Get command definition by name."""
        return self.commands.get(command_name)
    
    def list_commands(self) -> List[str]:
        """List all available commands for this tool."""
        return list(self.commands.keys())
    
    def get_parameters_for_command(self, command_name: Optional[str] = None) -> Optional[ToolSchema]:
        """Get parameters schema for a specific command or default."""
        if command_name and command_name in self.commands:
            return self.commands[command_name].parameters
        # Return first command's parameters as default
        if self.commands:
            return list(self.commands.values())[0].parameters
        return None
    
    def to_ollama_schema(self, command_name: Optional[str] = None) -> Dict[str, Any]:
        """Convert to Ollama function calling format.
        
        Args:
            command_name: Specific command to get schema for
            
        Returns:
            Tool schema in Ollama format
        """
        if command_name and command_name in self.commands:
            cmd = self.commands[command_name]
            func_name = f"{self.name}_{command_name}"
            description = cmd.description
            parameters = cmd.parameters
        else:
            func_name = self.name
            description = self.description
            parameters = self.get_parameters_for_command() or ToolSchema()
        
        # Convert to Ollama format
        properties = {}
        required = []
        
        for param_name, param in parameters.properties.items():
            prop = {"type": param.type}
            if param.description:
                prop["description"] = param.description
            if param.enum:
                prop["enum"] = param.enum
            properties[param_name] = prop
            
            if param.required:
                required.append(param_name)
        
        return {
            "type": "function",
            "function": {
                "name": func_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required or parameters.required
                }
            }
        }
