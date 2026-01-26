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
            # Try executing via specs first
            result = self._execute_via_specs_direct(tool_name, command_name, parameters)
            
            # If not found in specs, try legacy implementation
            if not result.get("success") and "not found in specs" in result.get("error", ""):
                if tool.implementation:
                    result = self._execute_implementation(tool.implementation, parameters)
                else:
                    # Return the original spec error if no implementation fallback
                    pass
            
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
        """Execute python implementation dynamically.
        
        Args:
            implementation_path: Dot-path to function (e.g. 'module.func')
            parameters: Parameters to pass
            
        Returns:
            Execution result
        """
        try:
            module_name, func_name = implementation_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            func = getattr(module, func_name)
            
            # Inspect function signature
            sig = inspect.signature(func)
            
            # Filter parameters to match signature (ignore extra)
            # But also allow **kwargs in function to take all
            valid_params = {}
            has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            
            if has_kwargs:
                valid_params = parameters
            else:
                for k, v in parameters.items():
                    if k in sig.parameters:
                        valid_params[k] = v
            
            # Execute
            result = func(**valid_params)
            
            if isinstance(result, dict) and "success" in result:
                return result
                
            # Wrap simple return values
            return {
                "success": True,
                "results": result,
                "raw_output": str(result)
            }
            
        except ImportError as e:
            return {"success": False, "error": f"Import error: {str(e)}"}
        except AttributeError as e:
            return {"success": False, "error": f"Function not found: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Implementation error: {str(e)}"}

    def _execute_via_specs_direct(
        self,
        tool_name: str,
        command_name: Optional[str],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute tool directly via SpecExecutor.
        
        Args:
            tool_name: Tool name
            command_name: Command to execute (optional, uses default if not provided)
            parameters: Tool parameters
            
        Returns:
            Execution result
        """
        try:
            from tools.specs.executor import get_spec_executor
            
            spec_executor = get_spec_executor()
            spec = spec_executor.get_tool(tool_name)
            
            if not spec:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found in specs"
                }
            
            if not spec.is_available:
                return {
                    "success": False,
                    "error": f"⚠️ TOOL NOT INSTALLED: {tool_name}. {spec.install_hint}"
                }
            
            # Determine command to use
            if command_name and command_name in spec.commands:
                cmd = command_name
            elif spec.commands:
                # Use first command as default
                cmd = list(spec.commands.keys())[0]
            else:
                return {
                    "success": False,
                    "error": f"No commands defined for tool '{tool_name}'"
                }
            
            # Map common parameter names
            mapped_params = {}
            param_mapping = {
                "target": "domain",
                "host": "domain",
                "target_domain": "domain",
            }
            for k, v in parameters.items():
                mapped_key = param_mapping.get(k, k)
                mapped_params[mapped_key] = v
            
            # Execute via specs
            result = spec_executor.execute(tool_name, cmd, mapped_params)
            
            return {
                "success": result.success,
                "results": result.output if result.success else None,
                "raw_output": result.output,
                "error": result.error if not result.success else None,
                "exit_code": result.exit_code,
                "elapsed_time": result.elapsed_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Execution error: {str(e)}"
            }
    
    def _execute_via_specs_streaming(
        self,
        tool_name: str,
        command_name: Optional[str],
        parameters: Dict[str, Any],
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """Execute tool with real-time streaming via SpecExecutor.
        
        Args:
            tool_name: Tool name
            command_name: Command to execute
            parameters: Tool parameters
            stream_callback: Callback for each line of output
            
        Returns:
            Execution result
        """
        try:
            from tools.specs.executor import get_spec_executor
            
            spec_executor = get_spec_executor()
            spec = spec_executor.get_tool(tool_name)
            
            if not spec:
                if stream_callback:
                    stream_callback(f"❌ Tool '{tool_name}' not found")
                return {"success": False, "error": f"Tool '{tool_name}' not found in specs"}
            
            if not spec.is_available:
                error = f"⚠️ TOOL NOT INSTALLED: {tool_name}. {spec.install_hint}"
                if stream_callback:
                    stream_callback(error)
                return {"success": False, "error": error}
            
            # Determine command to use
            if command_name and command_name in spec.commands:
                cmd = command_name
            elif spec.commands:
                cmd = list(spec.commands.keys())[0]
            else:
                return {"success": False, "error": f"No commands for '{tool_name}'"}
            
            # Map parameters
            param_mapping = {"target": "domain", "host": "domain", "target_domain": "domain"}
            mapped_params = {}
            for k, v in parameters.items():
                mapped_key = param_mapping.get(k, k)
                mapped_params[mapped_key] = v
            
            # Execute with streaming
            result = spec_executor.execute_streaming(tool_name, cmd, mapped_params, stream_callback)
            
            return {
                "success": result.success,
                "results": result.output if result.success else None,
                "raw_output": result.output,
                "error": result.error if not result.success else None,
                "exit_code": result.exit_code,
                "elapsed_time": result.elapsed_time
            }
            
        except Exception as e:
            if stream_callback:
                stream_callback(f"❌ Error: {str(e)}")
            return {"success": False, "error": f"Execution error: {str(e)}"}
    
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
            stream_callback(f"🔧 Starting {tool_name}" + (f":{command_name}" if command_name else ""))
        
        try:
            # Execute via SpecExecutor with real-time streaming
            result = self._execute_via_specs_streaming(tool_name, command_name, parameters, stream_callback)
            
            # If not found in specs, try legacy implementation
            if not result.get("success") and "not found in specs" in result.get("error", ""):
                 if stream_callback:
                     stream_callback(f"⚠️ Tool '{tool_name}' not found in specs, falling back to Python implementation...")
                 
                 if tool.implementation:
                     result = self._execute_implementation(tool.implementation, parameters)
                     # Since implementation is sync, we just dump the result/output to stream
                     if stream_callback:
                         if result.get("raw_output"):
                             output = result.get("raw_output")
                             # Pretty print web_search output
                             if tool_name == "web_search" and isinstance(result.get("results"), dict):
                                 try:
                                     search_res = result.get("results", {})
                                     formatted = []
                                     formatted.append(f"\n🔍 Search Query: {search_res.get('query', 'Unknown')}")
                                     formatted.append(f"Found {search_res.get('total_found', 0)} results:\n")
                                     
                                     for i, item in enumerate(search_res.get("results", []), 1):
                                         formatted.append(f"{i}. [bold cyan]{item.get('title', 'No Title')}[/bold cyan]")
                                         formatted.append(f"   Link: {item.get('link', '')}")
                                         formatted.append(f"   Snippet: {item.get('snippet', '')}\n")
                                     
                                     output = "\n".join(formatted)
                                 except Exception:
                                     output = result.get("raw_output") # Fallback
                             
                             stream_callback(str(output))
                         
                         if not result.get("success") and result.get("error"):
                             stream_callback(f"❌ Implementation Error: {result.get('error')}")
                 else:
                     pass # Return original error
            
            # Add metadata
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
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
