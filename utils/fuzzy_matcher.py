"""Fuzzy matching utilities for tool names and targets."""

from typing import List, Optional, Tuple
from rapidfuzz import fuzz, process
from tools.registry import get_registry


class FuzzyMatcher:
    """Fuzzy matching for tool names and commands."""
    
    def __init__(self):
        """Initialize fuzzy matcher."""
        self.registry = get_registry()
        self._tool_names_cache = None
        self._tool_commands_cache = None
    
    def _get_tool_names(self) -> List[str]:
        """Get all available tool names."""
        if self._tool_names_cache is None:
            # list_tools() returns List[ToolDefinition], extract names
            tools = self.registry.list_tools()
            self._tool_names_cache = [tool.name for tool in tools] if tools else []
        return self._tool_names_cache
    
    def _get_tool_commands(self) -> List[Tuple[str, str]]:
        """Get all tool:command combinations."""
        if self._tool_commands_cache is None:
            commands = []
            for tool_name in self._get_tool_names():
                tool = self.registry.get_tool(tool_name)
                if tool and tool.commands:
                    for cmd_name in tool.list_commands():
                        commands.append((tool_name, cmd_name))
                else:
                    # Tool without commands
                    commands.append((tool_name, None))
            self._tool_commands_cache = commands
        return self._tool_commands_cache
    
    def fuzzy_match_tool(self, 
                        tool_name: str, 
                        threshold: int = 70) -> Optional[str]:
        """Fuzzy match tool name.
        
        Args:
            tool_name: Input tool name (may have typos)
            threshold: Minimum similarity score (0-100)
            
        Returns:
            Matched tool name or None if no match above threshold
        """
        if not tool_name:
            return None
        
        # Check for tool:command format
        if ":" in tool_name:
            parts = tool_name.split(":", 1)
            tool_part = parts[0].strip()
            cmd_part = parts[1].strip() if len(parts) > 1 else None
            
            # Match tool name
            matched_tool = self._match_single_tool(tool_part, threshold)
            if not matched_tool:
                return None
            
            # Match command if provided
            if cmd_part:
                tool = self.registry.get_tool(matched_tool)
                if tool and tool.commands:
                    matched_cmd = self._match_command(tool, cmd_part, threshold)
                    if matched_cmd:
                        return f"{matched_tool}:{matched_cmd}"
                return matched_tool
            else:
                return matched_tool
        
        # Match single tool name
        return self._match_single_tool(tool_name, threshold)
    
    def _match_single_tool(self, tool_name: str, threshold: int) -> Optional[str]:
        """Match a single tool name."""
        tool_names = self._get_tool_names()
        
        if not tool_names:
            return None
        
        # Exact match first
        if tool_name in tool_names:
            return tool_name
        
        # Fuzzy match
        result = process.extractOne(
            tool_name,
            tool_names,
            scorer=fuzz.WRatio,
            score_cutoff=threshold
        )
        
        if result:
            matched_name, score, _ = result
            return matched_name
        
        return None
    
    def _match_command(self, 
                      tool, 
                      command_name: str, 
                      threshold: int) -> Optional[str]:
        """Match command name for a tool."""
        if not tool.commands:
            return None
        
        commands = list(tool.commands.keys())
        
        # Exact match first
        if command_name in commands:
            return command_name
        
        # Fuzzy match
        result = process.extractOne(
            command_name,
            commands,
            scorer=fuzz.WRatio,
            score_cutoff=threshold
        )
        
        if result:
            matched_cmd, score, _ = result
            return matched_cmd
        
        return None
    
    def fuzzy_match_tool_command(self,
                                 tool_name: str,
                                 command_name: Optional[str] = None,
                                 threshold: int = 70) -> Optional[Tuple[str, Optional[str]]]:
        """Fuzzy match tool and command separately.
        
        Args:
            tool_name: Tool name (may have typos)
            command_name: Optional command name (may have typos)
            threshold: Minimum similarity score
            
        Returns:
            Tuple of (matched_tool, matched_command) or None
        """
        matched_tool = self._match_single_tool(tool_name, threshold)
        if not matched_tool:
            return None
        
        matched_cmd = None
        if command_name:
            tool = self.registry.get_tool(matched_tool)
            if tool:
                matched_cmd = self._match_command(tool, command_name, threshold)
        
        return (matched_tool, matched_cmd)
    
    def get_suggestions(self, 
                       tool_name: str, 
                       limit: int = 3) -> List[Tuple[str, int]]:
        """Get tool name suggestions.
        
        Args:
            tool_name: Input tool name
            limit: Maximum number of suggestions
            
        Returns:
            List of (tool_name, score) tuples
        """
        tool_names = self._get_tool_names()
        
        if not tool_names:
            return []
        
        results = process.extract(
            tool_name,
            tool_names,
            scorer=fuzz.WRatio,
            limit=limit
        )
        
        return [(name, score) for name, score, _ in results]
