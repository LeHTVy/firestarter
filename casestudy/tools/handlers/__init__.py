"""
Tool Handlers - Extracted from Agentic Loop
=============================================

Each handler receives (action_input, state) and returns observation string.
"""
from typing import Dict, Any, Callable

# Handler function type
HandlerFunc = Callable[[Dict[str, Any], Any], str]

# Registry of all handlers
TOOL_HANDLERS: Dict[str, HandlerFunc] = {}

_handlers_loaded = False


def register_handler(action_name: str):
    """Decorator to register a tool handler."""
    def decorator(func: HandlerFunc) -> HandlerFunc:
        TOOL_HANDLERS[action_name] = func
        return func
    return decorator


def _load_handlers():
    """Load all handler modules (called once on first use)."""
    global _handlers_loaded
    if _handlers_loaded:
        return
    
    # Import handler modules to register them
    from app.tools.handlers import recon
    from app.tools.handlers import vuln
    from app.tools.handlers import web
    from app.tools.handlers import memory_tools
    from app.tools.handlers import training_tools
    from app.tools.handlers import exploit
    from app.tools.handlers import brute
    from app.tools.handlers import network
    from app.tools.handlers import osint
    from app.tools.handlers import cloud
    
    _handlers_loaded = True


def execute_tool(action: str, action_input: Dict[str, Any], state: Any) -> str:
    """
    Execute a tool action using registered handlers.
    
    Args:
        action: Tool/action name
        action_input: Parameters for the tool
        state: AgentState with context, memory, etc
        
    Returns:
        Observation string for the agent, or None if handler not found
    """
    _load_handlers()
    
    handler = TOOL_HANDLERS.get(action)
    if handler:
        return handler(action_input, state)
    else:
        return None  # Let agentic_loop handle unknown actions
