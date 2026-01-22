"""Mode Manager for execution mode control."""

from enum import Enum
from typing import Optional, List

# Mode descriptions
MODE_DESCRIPTIONS = {
    "passive": "OSINT only, no packets sent, legally safe. Use for public information gathering only.",
    "cooperative": "Scanner allowed, authenticated scan, limited scope. Use for authorized network scanning.",
    "simulation": "Lab/digital twin, replay attack chain, no production impact. Use for safe exploit testing."
}


class ExecutionMode(Enum):
    """Execution mode for tool execution control."""
    PASSIVE = "passive"      # OSINT only, no packets sent, legally safe
    COOPERATIVE = "cooperative"  # Scanner allowed, authenticated scan, limited scope
    SIMULATION = "simulation"    # Lab/digital twin, replay attack chain, no production impact


class ModeManager:
    """Manage execution mode per conversation.
    
    Mode Manager controls the level of tool execution aggressiveness,
    providing a safety mechanism for different testing scenarios.
    """
    
    # Default mode compatibility rules
    MODE_COMPATIBILITY = {
        ExecutionMode.PASSIVE: ["passive"],
        ExecutionMode.COOPERATIVE: ["passive", "active"],
        ExecutionMode.SIMULATION: ["passive", "active", "destructive"]
    }
    
    def __init__(self, default_mode: ExecutionMode = ExecutionMode.COOPERATIVE):
        """Initialize Mode Manager.
        
        Args:
            default_mode: Default execution mode
        """
        self.default_mode = default_mode
        self._conversation_modes = {}  # conversation_id -> ExecutionMode
    
    def get_mode(self, conversation_id: Optional[str] = None) -> ExecutionMode:
        """Get execution mode for conversation.
        
        Args:
            conversation_id: Conversation UUID (optional, uses default if not provided)
            
        Returns:
            Current execution mode
        """
        if not conversation_id:
            return self.default_mode
        
        return self._conversation_modes.get(conversation_id, self.default_mode)
    
    def set_mode(self, mode: ExecutionMode, conversation_id: Optional[str] = None) -> bool:
        """Set execution mode for conversation.
        
        Args:
            mode: Execution mode to set
            conversation_id: Conversation UUID (optional, uses default if not provided)
            
        Returns:
            True if set successfully, False otherwise
        """
        if conversation_id:
            self._conversation_modes[conversation_id] = mode
        else:
            self.default_mode = mode
        
        return True
    
    def is_tool_compatible(self, tool_modes: List[str], conversation_id: Optional[str] = None) -> bool:
        """Check if tool is compatible with current mode.
        
        Args:
            tool_modes: List of modes the tool supports (from tool metadata)
            conversation_id: Conversation UUID (optional)
            
        Returns:
            True if compatible, False otherwise
        """
        current_mode = self.get_mode(conversation_id)
        
        # Get allowed modes for current execution mode
        allowed_modes = self.MODE_COMPATIBILITY.get(current_mode, [])
        
        # Check if any tool mode is compatible
        for tool_mode in tool_modes:
            if tool_mode.lower() in [m.lower() for m in allowed_modes]:
                return True
        
        return False
    
    def filter_tools_by_mode(self, tools: List[dict], conversation_id: Optional[str] = None) -> List[dict]:
        """Filter tools by execution mode compatibility.
        
        Args:
            tools: List of tool definitions (must have 'mode' field)
            conversation_id: Conversation UUID (optional)
            
        Returns:
            Filtered list of compatible tools
        """
        current_mode = self.get_mode(conversation_id)
        allowed_modes = self.MODE_COMPATIBILITY.get(current_mode, [])
        
        def is_compatible(tool):
            """Check if tool is compatible with current mode."""
            tool_modes = tool.get("mode", [])
            
            # If tool has no mode specified, allow it (backward compatibility)
            if not tool_modes:
                return True
            
            # Check if any tool mode is compatible
            return any(
                mode.lower() in [a.lower() for a in allowed_modes]
                for mode in tool_modes
            )
        
        return [tool for tool in tools if is_compatible(tool)]
    
    def get_mode_description(self, mode: Optional[ExecutionMode] = None) -> str:
        """Get description of execution mode.
        
        Args:
            mode: Execution mode (uses current mode if not provided)
            
        Returns:
            Mode description
        """
        if mode is None:
            mode = self.default_mode
        
        return MODE_DESCRIPTIONS.get(mode.value, "Unknown mode")
    
    def validate_mode_switch(self, from_mode: ExecutionMode, to_mode: ExecutionMode) -> tuple[bool, Optional[str]]:
        """Validate if mode switch is allowed.
        
        Args:
            from_mode: Current execution mode
            to_mode: Target execution mode
            
        Returns:
            Tuple of (allowed, reason if not allowed)
        """
        mode_order = [ExecutionMode.PASSIVE, ExecutionMode.COOPERATIVE, ExecutionMode.SIMULATION]
        
        from_index = mode_order.index(from_mode) if from_mode in mode_order else -1
        to_index = mode_order.index(to_mode) if to_mode in mode_order else -1
        
        if from_index == -1 or to_index == -1:
            return False, "Invalid mode"
        
        if to_index < from_index:
            return True, f"Warning: Downgrading from {from_mode.value} to {to_mode.value} may limit tool availability"
        
        return True, None
