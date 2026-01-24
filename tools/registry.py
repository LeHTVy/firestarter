"""Tool registry for managing security tools metadata."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Tool parameter definition."""
    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None
    default: Optional[Any] = None


class ToolSchema(BaseModel):
    """Tool parameter schema."""
    type: str
    properties: Dict[str, ToolParameter]
    required: List[str] = Field(default_factory=list)


class CommandDefinition(BaseModel):
    """Command definition within a tool."""
    description: str
    parameters: ToolSchema
    timeout: Optional[int] = None
    requires_sudo: bool = False
    output_format: str = "text"


class ToolDefinition(BaseModel):
    """Security tool definition."""
    name: str
    description: str
    category: str
    priority: bool = False
    assigned_agents: List[str] = Field(default_factory=list)
    implementation: Optional[str] = None
    parameters: Optional[ToolSchema] = None
    commands: Optional[Dict[str, CommandDefinition]] = None
    risk_level: str
    requires_auth: bool = False
    aliases: Optional[List[str]] = Field(default_factory=list)
    
    capability: Optional[List[str]] = Field(default_factory=list)
    mode: Optional[List[str]] = Field(default_factory=list)
    scope: Optional[List[str]] = Field(default_factory=list)
    legal_risk: Optional[str] = None
    cost: Optional[Dict[str, Any]] = Field(default_factory=dict)
    permission_required: Optional[bool] = None
    evidence_output: Optional[List[str]] = Field(default_factory=list)
    
    def get_command(self, command_name: str) -> Optional[CommandDefinition]:
        """Get command definition by name.
        
        Args:
            command_name: Command name
            
        Returns:
            Command definition or None if not found
        """
        if self.commands:
            return self.commands.get(command_name)
        return None
    
    def list_commands(self) -> List[str]:
        """List all available commands for this tool.
        
        Returns:
            List of command names
        """
        if self.commands:
            return list(self.commands.keys())
        return []
    
    def get_parameters_for_command(self, command_name: Optional[str] = None) -> Optional[ToolSchema]:
        """Get parameters schema for a specific command or default.
        
        Args:
            command_name: Command name. If None, returns default parameters
            
        Returns:
            Parameters schema or None
        """
        if command_name and self.commands:
            cmd = self.commands.get(command_name)
            if cmd:
                return cmd.parameters
        
        # Fallback to legacy parameters
        return self.parameters


class ToolRegistry:
    """Registry for managing security tools."""
    
    def __init__(self, tools_file: Optional[Path] = None):
        """Initialize tool registry.
        
        Args:
            tools_file: Path to tools.json file. Defaults to metadata/tools.json
        """
        if tools_file is None:
            tools_file = Path(__file__).parent / "metadata" / "tools.json"
        
        self.tools_file = tools_file
        self.tools: Dict[str, ToolDefinition] = {}
        self._alias_map: Dict[str, str] = {}  # alias -> actual tool name
        self._load_tools()
    
    def _load_tools(self) -> None:
        """Load tools from JSON file and build alias map."""
        with open(self.tools_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for tool_data in data.get('tools', []):
            tool = ToolDefinition(**tool_data)
            self.tools[tool.name] = tool
            # Build alias -> tool name mapping
            for alias in tool.aliases or []:
                self._alias_map[alias.lower()] = tool.name
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool by name or alias.
        
        Args:
            name: Tool name or alias
            
        Returns:
            Tool definition or None if not found
        """
        # Try exact match first
        tool = self.tools.get(name)
        if tool:
            return tool
        # Try alias (case-insensitive)
        actual_name = self._alias_map.get(name.lower())
        if actual_name:
            return self.tools.get(actual_name)
        return None
    
    def list_tools(self, 
                   category: Optional[str] = None,
                   agent: Optional[str] = None,
                   priority_only: bool = False) -> List[ToolDefinition]:
        """List tools with optional filters.
        
        Args:
            category: Filter by category
            agent: Filter by assigned agent
            priority_only: Return only priority tools
            
        Returns:
            List of tool definitions
        """
        tools = list(self.tools.values())
        
        if category:
            tools = [t for t in tools if t.category == category]
        
        if agent:
            tools = [t for t in tools if agent in t.assigned_agents]
        
        if priority_only:
            tools = [t for t in tools if t.priority]
        
        return tools
    
    def get_tools_for_agent(self, agent_name: str) -> List[ToolDefinition]:
        """Get all tools assigned to a specific agent.
        
        Args:
            agent_name: Agent name (e.g., 'recon_agent')
            
        Returns:
            List of tool definitions
        """
        return self.list_tools(agent=agent_name)
    
    def get_tool_schema_for_ollama(self, tool_name: str, command_name: Optional[str] = None) -> Optional[Dict]:
        """Get tool schema in Ollama function calling format.
        
        Args:
            tool_name: Tool name
            command_name: Optional command name (for tools with multiple commands)
            
        Returns:
            Tool schema in Ollama format or None
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return None
        
        # Get parameters for specific command or default
        params_schema = tool.get_parameters_for_command(command_name)
        if not params_schema:
            return None
        
        # Convert to Ollama function calling format
        properties = {}
        for param_name, param_def in params_schema.properties.items():
            prop = {
                "type": param_def.type,
                "description": param_def.description or ""
            }
            if param_def.enum:
                prop["enum"] = param_def.enum
            if param_def.default is not None:
                prop["default"] = param_def.default
            properties[param_name] = prop
        
        # Build function name: tool_name or tool_name:command_name
        func_name = f"{tool.name}:{command_name}" if command_name and tool.commands else tool.name
        
        # Build description
        description = tool.description
        if command_name and tool.commands:
            cmd = tool.commands.get(command_name)
            if cmd:
                description = f"{tool.description} - {cmd.description}"
        
        return {
            "type": "function",
            "function": {
                "name": func_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": params_schema.required
                }
            }
        }
    
    def get_all_tool_schemas_for_ollama(self, 
                                        agent: Optional[str] = None,
                                        include_commands: bool = True) -> List[Dict]:
        """Get all tool schemas in Ollama format.
        
        Args:
            agent: Filter by agent name
            include_commands: If True, include each command as separate function
            
        Returns:
            List of tool schemas in Ollama format
        """
        tools = self.get_tools_for_agent(agent) if agent else list(self.tools.values())
        
        schemas = []
        for tool in tools:
            if tool.commands and include_commands:
                # For tools with commands, create a function for each command
                for cmd_name in tool.list_commands():
                    schema = self.get_tool_schema_for_ollama(tool.name, cmd_name)
                    if schema:
                        schemas.append(schema)
            else:
                # Legacy: single function per tool
                schema = self.get_tool_schema_for_ollama(tool.name)
                if schema:
                    schemas.append(schema)
        
        return schemas
    
    def search_tools(self, query: str) -> List[ToolDefinition]:
        """Search tools by name or description.
        
        Args:
            query: Search query
            
        Returns:
            List of matching tool definitions
        """
        query_lower = query.lower()
        matches = []
        
        for tool in self.tools.values():
            if (query_lower in tool.name.lower() or 
                query_lower in tool.description.lower() or
                query_lower in tool.category.lower()):
                matches.append(tool)
        
        return matches


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get global tool registry instance.
    
    Returns:
        Tool registry instance
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
