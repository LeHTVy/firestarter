"""Tool executor engine for executing security tools."""

import importlib
import inspect
import subprocess
import threading
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime
import uuid

from tools.registry import ToolRegistry, get_registry, ToolSchema


class ToolExecutor:
    """Engine for executing security tools."""
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        """Initialize tool executor.
        
        Args:
            registry: Tool registry instance. Defaults to global registry.
        """
        self.registry = registry or get_registry()
        self.execution_history: list = []
    
    def execute_tool(self, 
                    tool_name: str,
                    parameters: Dict[str, Any],
                    agent: Optional[str] = None,
                    session_id: Optional[str] = None,
                    command_name: Optional[str] = None) -> Dict[str, Any]:
        """Execute a tool.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            agent: Agent name executing the tool
            session_id: Session identifier
            command_name: Optional command name (for tools with multiple commands)
            
        Returns:
            Execution results with metadata
        """
        # Parse tool_name:command_name format if needed
        if ":" in tool_name and not command_name:
            parts = tool_name.split(":", 1)
            tool_name = parts[0]
            command_name = parts[1] if len(parts) > 1 else None
        
        # Get tool definition
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "tool_name": tool_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Check agent permissions
        if agent and tool.assigned_agents and agent not in tool.assigned_agents:
            return {
                "success": False,
                "error": f"Agent '{agent}' does not have permission to use tool '{tool_name}'",
                "tool_name": tool_name,
                "allowed_agents": tool.assigned_agents,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Validate command exists if specified
        if command_name and tool.commands:
            if command_name not in tool.commands:
                return {
                    "success": False,
                    "error": f"Command '{command_name}' not found for tool '{tool_name}'. Available: {', '.join(tool.list_commands())}",
                    "tool_name": tool_name,
                    "command_name": command_name,
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        # Get parameters schema for command or default
        params_schema = tool.get_parameters_for_command(command_name)
        if not params_schema:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' has no parameters schema",
                "tool_name": tool_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Validate parameters
        validation_result = self._validate_parameters(params_schema, parameters)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": f"Parameter validation failed: {validation_result['error']}",
                "tool_name": tool_name,
                "parameters": parameters,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Execute tool
        execution_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            if tool.implementation:
                # Execute via implementation function
                result = self._execute_implementation(tool.implementation, parameters)
            else:
                # Generic execution: Try to execute as system command
                # This allows tools without Python implementation to still work
                result = self._execute_generic_tool(tool_name, parameters, command_name)
            
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            # Add metadata
            execution_result = {
                "execution_id": execution_id,
                "tool_name": tool_name,
                "command_name": command_name,
                "tool_category": tool.category,
                "parameters": parameters,
                "agent": agent,
                "session_id": session_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "execution_time": execution_time,
                "success": result.get("success", False),
                "results": result.get("results"),
                "error": result.get("error"),
                "raw_output": result.get("raw_output")
            }
            
            # Store in history
            self.execution_history.append(execution_result)
            
            return execution_result
            
        except Exception as e:
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            error_result = {
                "execution_id": execution_id,
                "tool_name": tool_name,
                "tool_category": tool.category,
                "parameters": parameters,
                "agent": agent,
                "session_id": session_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "execution_time": execution_time,
                "success": False,
                "error": str(e),
                "results": None
            }
            
            self.execution_history.append(error_result)
            return error_result
    
    def _validate_parameters(self, params_schema: ToolSchema, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate tool parameters.
        
        Args:
            params_schema: Parameters schema (from tool or command)
            parameters: Parameters to validate
            
        Returns:
            Validation result
        """
        required_params = params_schema.required
        provided_params = set(parameters.keys())
        
        # Check required parameters
        missing = set(required_params) - provided_params
        if missing:
            return {
                "valid": False,
                "error": f"Missing required parameters: {', '.join(missing)}"
            }
        
        # Check parameter types (basic validation)
        for param_name, param_value in parameters.items():
            if param_name in params_schema.properties:
                param_def = params_schema.properties[param_name]
                # Basic type checking
                if param_def.type == "integer" and not isinstance(param_value, int):
                    try:
                        parameters[param_name] = int(param_value)
                    except (ValueError, TypeError):
                        return {
                            "valid": False,
                            "error": f"Parameter '{param_name}' must be an integer"
                        }
                elif param_def.type == "array" and not isinstance(param_value, list):
                    return {
                        "valid": False,
                        "error": f"Parameter '{param_name}' must be an array"
                    }
                elif param_def.type == "object" and not isinstance(param_value, dict):
                    return {
                        "valid": False,
                        "error": f"Parameter '{param_name}' must be an object"
                    }
        
        return {"valid": True}
    
    def _execute_implementation(self, implementation_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool implementation function.
        
        Args:
            implementation_path: Dot-separated path to implementation function
            parameters: Tool parameters
            
        Returns:
            Execution result
        """
        try:
            # Parse implementation path (e.g., "tools.implementations.nmap_tool.execute")
            parts = implementation_path.split(".")
            module_path = ".".join(parts[:-1])
            function_name = parts[-1]
            
            # Import module
            module = importlib.import_module(module_path)
            
            # Get function
            func = getattr(module, function_name)
            
            # Check if function accepts **kwargs
            sig = inspect.signature(func)
            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                # Function accepts **kwargs
                result = func(**parameters)
            else:
                # Function has specific parameters
                # Extract only parameters that function accepts
                func_params = {k: v for k, v in parameters.items() if k in sig.parameters}
                result = func(**func_params)
            
            return result if isinstance(result, dict) else {"success": True, "results": result}
            
        except ImportError as e:
            return {
                "success": False,
                "error": f"Failed to import implementation: {str(e)}"
            }
        except AttributeError as e:
            return {
                "success": False,
                "error": f"Implementation function not found: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Execution error: {str(e)}"
            }
    
    def execute_tool_streaming(self,
                              tool_name: str,
                              parameters: Dict[str, Any],
                              stream_callback: Optional[Callable[[str], None]] = None,
                              agent: Optional[str] = None,
                              session_id: Optional[str] = None,
                              command_name: Optional[str] = None) -> Dict[str, Any]:
        """Execute a tool with streaming output.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            stream_callback: Callback function for streaming output (called with each line)
            agent: Agent name executing the tool
            session_id: Session identifier
            command_name: Optional command name (for tools with multiple commands)
            
        Returns:
            Execution results with metadata
        """
        # Parse tool_name:command_name format if needed
        if ":" in tool_name and not command_name:
            parts = tool_name.split(":", 1)
            tool_name = parts[0]
            command_name = parts[1] if len(parts) > 1 else None
        
        # Get tool definition
        tool = self.registry.get_tool(tool_name)
        if not tool:
            error_msg = f"Tool '{tool_name}' not found"
            if stream_callback:
                stream_callback(f"Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "tool_name": tool_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Check agent permissions
        if agent and tool.assigned_agents and agent not in tool.assigned_agents:
            error_msg = f"Agent '{agent}' does not have permission to use tool '{tool_name}'"
            if stream_callback:
                stream_callback(f"Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "tool_name": tool_name,
                "allowed_agents": tool.assigned_agents,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Validate command exists if specified
        if command_name and tool.commands:
            if command_name not in tool.commands:
                error_msg = f"Command '{command_name}' not found for tool '{tool_name}'"
                if stream_callback:
                    stream_callback(f"Error: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "tool_name": tool_name,
                    "command_name": command_name,
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        # Get parameters schema for command or default
        params_schema = tool.get_parameters_for_command(command_name)
        if not params_schema:
            error_msg = f"Tool '{tool_name}' has no parameters schema"
            if stream_callback:
                stream_callback(f"Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "tool_name": tool_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Validate parameters
        validation_result = self._validate_parameters(params_schema, parameters)
        if not validation_result["valid"]:
            error_msg = f"Parameter validation failed: {validation_result['error']}"
            if stream_callback:
                stream_callback(f"Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "tool_name": tool_name,
                "parameters": parameters,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Execute tool with streaming
        execution_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        if stream_callback:
            stream_callback(f"Starting execution of {tool_name}" + (f":{command_name}" if command_name else ""))
            stream_callback(f"Parameters: {parameters}")
        
        try:
            if tool.implementation:
                # Try to execute with streaming support
                result = self._execute_implementation_streaming(
                    tool.implementation,
                    parameters,
                    stream_callback
                )
            else:
                # Generic execution (placeholder)
                error_msg = f"Tool '{tool_name}' has no implementation"
                if stream_callback:
                    stream_callback(f"Error: {error_msg}")
                result = {
                    "success": False,
                    "error": error_msg,
                    "tool_name": tool_name
                }
            
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            if stream_callback:
                if result.get("success"):
                    stream_callback(f"Execution completed successfully in {execution_time:.2f}s")
                else:
                    stream_callback(f"Execution failed: {result.get('error', 'Unknown error')}")
            
            # Add metadata
            execution_result = {
                "execution_id": execution_id,
                "tool_name": tool_name,
                "command_name": command_name,
                "tool_category": tool.category,
                "parameters": parameters,
                "agent": agent,
                "session_id": session_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "execution_time": execution_time,
                "success": result.get("success", False),
                "results": result.get("results"),
                "error": result.get("error"),
                "raw_output": result.get("raw_output")
            }
            
            # Store in history
            self.execution_history.append(execution_result)
            
            return execution_result
            
        except Exception as e:
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            error_msg = str(e)
            if stream_callback:
                stream_callback(f"Exception during execution: {error_msg}")
            
            error_result = {
                "execution_id": execution_id,
                "tool_name": tool_name,
                "tool_category": tool.category,
                "parameters": parameters,
                "agent": agent,
                "session_id": session_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "execution_time": execution_time,
                "success": False,
                "error": error_msg,
                "results": None
            }
            
            self.execution_history.append(error_result)
            return error_result
    
    def _execute_implementation_streaming(self,
                                          implementation_path: str,
                                          parameters: Dict[str, Any],
                                          stream_callback: Optional[Callable[[str], None]]) -> Dict[str, Any]:
        """Execute tool implementation with streaming support.
        
        Args:
            implementation_path: Dot-separated path to implementation function
            parameters: Tool parameters
            stream_callback: Callback for streaming output
            
        Returns:
            Execution result
        """
        try:
            # Parse implementation path
            parts = implementation_path.split(".")
            module_path = ".".join(parts[:-1])
            function_name = parts[-1]
            
            # Import module
            module = importlib.import_module(module_path)
            
            # Get function
            func = getattr(module, function_name)
            
            # Check if function has streaming support (accepts stream_callback parameter)
            sig = inspect.signature(func)
            has_streaming = 'stream_callback' in sig.parameters
            
            if has_streaming:
                # Function supports streaming
                if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    result = func(stream_callback=stream_callback, **parameters)
                else:
                    func_params = {k: v for k, v in parameters.items() if k in sig.parameters}
                    result = func(stream_callback=stream_callback, **func_params)
            else:
                # Function doesn't support streaming - execute normally and simulate streaming
                if stream_callback:
                    stream_callback("Executing tool...")
                
                if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    result = func(**parameters)
                else:
                    func_params = {k: v for k, v in parameters.items() if k in sig.parameters}
                    result = func(**func_params)
                
                # If result has raw_output, stream it
                if stream_callback and isinstance(result, dict):
                    if result.get("raw_output"):
                        output_lines = str(result["raw_output"]).split("\n")
                        for line in output_lines[:50]:  # Stream first 50 lines
                            if line.strip():
                                stream_callback(line.strip())
                    elif result.get("success"):
                        stream_callback("Tool execution completed successfully")
            
            return result if isinstance(result, dict) else {"success": True, "results": result}
            
        except ImportError as e:
            error_msg = f"Failed to import implementation: {str(e)}"
            if stream_callback:
                stream_callback(f"Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except AttributeError as e:
            error_msg = f"Implementation function not found: {str(e)}"
            if stream_callback:
                stream_callback(f"Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Execution error: {str(e)}"
            if stream_callback:
                stream_callback(f"Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def get_execution_history(self, 
                             tool_name: Optional[str] = None,
                             agent: Optional[str] = None,
                             session_id: Optional[str] = None) -> list:
        """Get execution history with optional filters.
        
        Args:
            tool_name: Filter by tool name
            agent: Filter by agent
            session_id: Filter by session ID
            
        Returns:
            List of execution results
        """
        history = self.execution_history
        
        if tool_name:
            history = [h for h in history if h.get("tool_name") == tool_name]
        
        if agent:
            history = [h for h in history if h.get("agent") == agent]
        
        if session_id:
            history = [h for h in history if h.get("session_id") == session_id]
        
        return history


# Global executor instance
_executor: Optional[ToolExecutor] = None


def get_executor() -> ToolExecutor:
    """Get global tool executor instance.
    
    Returns:
        Tool executor instance
    """
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
