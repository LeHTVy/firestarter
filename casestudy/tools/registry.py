"""
ToolRegistry - Unified Tool Management for SNODE
=================================================

Auto-discovers installed security tools and provides
consistent execution API with proper timeout handling.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from enum import Enum
import subprocess
import shutil
import time
import os


class ToolCategory(Enum):
    """Categories of security tools."""
    RECON = "recon"
    SCANNING = "scanning"
    VULN = "vulnerability"
    EXPLOIT = "exploitation"
    ENUM = "enumeration"
    OSINT = "osint"
    BRUTE = "brute_force"
    UTIL = "utility"


@dataclass
class ToolResult:
    """Standardized result from tool execution."""
    success: bool
    tool: str
    action: str
    output: str
    error: str = ""
    exit_code: int = 0
    elapsed_time: float = 0.0
    parsed_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_observation(self) -> str:
        """Convert to agent observation string."""
        if self.success:
            return self.output
        else:
            return f"Error running {self.tool}: {self.error or self.output}"


@dataclass
class CommandTemplate:
    """Template for a tool command."""
    args: List[str]                  # Command args with {placeholders}
    timeout: int = 300               # Seconds
    requires_sudo: bool = False
    output_format: str = "text"      # text, json, xml
    success_codes: List[int] = field(default_factory=lambda: [0])
    phase: Optional[int] = None       # PTES phase (1-6) - None = use tool category default
    phase_reason: Optional[str] = None  # Explanation why this command is in this phase
    description: Optional[str] = None  # Human-readable description of what this command does
    use_cases: Optional[List[str]] = None  # List of use cases for this command (e.g., ["quick port check", "initial reconnaissance"])


@dataclass
class ToolSpec:
    """
    Specification for a security tool.
    
    Defines executable location, available commands,
    and how to parse outputs.
    """
    name: str
    category: ToolCategory
    description: str
    
    # Executable discovery
    executable_names: List[str]      # Names to search for
    install_hint: str                # How to install if missing
    
    # Commands this tool supports
    commands: Dict[str, CommandTemplate] = field(default_factory=dict)
    
    # Runtime state (set by registry)
    executable_path: Optional[str] = None
    is_available: bool = False
    
    def find_executable(self) -> Optional[str]:
        """Find the tool executable on the system."""
        # Check common paths first
        common_paths = [
            "/home/hellrazor/go/bin",
            "/usr/bin",
            "/usr/local/bin",
            "/snap/bin",
            os.path.expanduser("~/go/bin"),
            # Custom SNODE tools
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "custom"),
        ]
        
        for name in self.executable_names:
            # Check common paths
            for path_dir in common_paths:
                full_path = Path(path_dir) / name
                if full_path.exists() and os.access(full_path, os.X_OK):
                    return str(full_path)
                # Also try with .py extension for Python scripts
                py_path = Path(path_dir) / f"{name}.py"
                if py_path.exists():
                    return f"python3 {py_path}"
            
            # Fall back to which
            path = shutil.which(name)
            if path:
                return path
        
        return None


class ToolRegistry:
    """
    Central registry for all security tools.
    
    Provides:
    - Auto-discovery of installed tools
    - Consistent execution API
    - Proper timeout handling
    - Structured output parsing
    """
    
    def __init__(self):
        self.tools: Dict[str, ToolSpec] = {}
        self._load_builtin_specs()
        self._discover_tools()
    
    def _load_builtin_specs(self):
        """Load built-in tool specifications."""
        from app.tools.specs import get_all_specs
        for spec in get_all_specs():
            self.register(spec)
    
    def register(self, spec: ToolSpec) -> None:
        """Register a tool specification."""
        self.tools[spec.name] = spec
    
    def _discover_tools(self) -> None:
        """Discover which tools are installed."""
        for name, spec in self.tools.items():
            # Python-based tools are always available
            if name == "clatscope":
                spec.is_available = True
                spec.executable_path = "python"  # Python-based
                continue
            
            path = spec.find_executable()
            if path:
                spec.executable_path = path
                spec.is_available = True
                # Silently discovered - no verbose output
            else:
                spec.is_available = False
    
    def is_available(self, tool: str) -> bool:
        """Check if a tool is available."""
        return tool in self.tools and self.tools[tool].is_available
    
    def list_tools(self, category: ToolCategory = None) -> List[str]:
        """List available tools, optionally filtered by category."""
        tools = []
        for name, spec in self.tools.items():
            if spec.is_available:
                if category is None or spec.category == category:
                    tools.append(name)
        return tools
    
    def get_install_hint(self, tool: str) -> str:
        """Get installation hint for a missing tool."""
        if tool in self.tools:
            return self.tools[tool].install_hint
        return f"Unknown tool: {tool}"
    
    def get_tools_for_llm(self, category: ToolCategory = None, available_only: bool = True) -> str:
        """
        Format tool metadata for LLM consumption.
        
        Returns a structured string that LLM can use to select tools and commands.
        This allows LLM to make intelligent tool choices based on metadata.
        """
        lines = []
        
        for name, spec in sorted(self.tools.items()):
            if available_only and not spec.is_available:
                continue
            if category and spec.category != category:
                continue
            
            # Tool header
            status = "✓" if spec.is_available else "✗"
            lines.append(f"[{status}] {name} ({spec.category.value})")
            lines.append(f"    Description: {spec.description}")
            
            # Commands
            if spec.commands:
                lines.append(f"    Commands:")
                for cmd_name, cmd_template in spec.commands.items():
                    # Extract required params from args
                    params = [p.strip("{}") for p in cmd_template.args if p.startswith("{")]
                    param_str = f"({', '.join(params)})" if params else ""
                    sudo_str = " [sudo]" if cmd_template.requires_sudo else ""
                    lines.append(f"      - {cmd_name}{param_str}{sudo_str}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def get_tool_spec_dict(self, tool: str) -> Optional[Dict[str, Any]]:
        """
        Get tool spec as dictionary for LLM.
        
        Returns complete metadata for a single tool.
        """
        if tool not in self.tools:
            return None
        
        spec = self.tools[tool]
        return {
            "name": spec.name,
            "category": spec.category.value,
            "description": spec.description,
            "available": spec.is_available,
            "commands": {
                cmd_name: {
                    "args": cmd.args,
                    "timeout": cmd.timeout,
                    "requires_sudo": cmd.requires_sudo,
                    "params": [p.strip("{}") for p in cmd.args if p.startswith("{")]
                }
                for cmd_name, cmd in spec.commands.items()
            }
        }
    
    def get_all_tools_summary(self) -> Dict[str, List[str]]:
        """
        Get summary of tools grouped by category.
        
        Useful for LLM to understand available capabilities.
        """
        by_category = {}
        for name, spec in self.tools.items():
            if not spec.is_available:
                continue
            cat = spec.category.value
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                "name": name,
                "description": spec.description[:50],
                "commands": list(spec.commands.keys())
            })
        return by_category
    
    def execute(
        self,
        tool: str,
        command: str,
        params: Dict[str, Any],
        timeout_override: int = None
    ) -> ToolResult:
        """
        Execute a tool command.
        
        Args:
            tool: Tool name (e.g., "nmap")
            command: Command name (e.g., "service_scan")
            params: Parameters for the command
            timeout_override: Override default timeout
        
        Returns:
            ToolResult with output and parsed data
        """
        # Validate tool
        if tool not in self.tools:
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="",
                error=f"Unknown tool: {tool}"
            )
        
        spec = self.tools[tool]
        
        if not spec.is_available:
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="",
                error=f"⚠️ TOOL NOT INSTALLED: {tool}. {spec.install_hint}"
            )
        
        # Validate command
        if command not in spec.commands:
            available = ", ".join(spec.commands.keys())
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="",
                error=f"Unknown command '{command}' for {tool}. Available: {available}"
            )
        
        template = spec.commands[command]
        
        # Check for Python-based handlers first (securitytrails, clatscope, etc.)
        # These tools use handlers instead of CLI
        from app.tools.handlers import execute_tool as handler_execute
        
        # Inject command into params for handler
        handler_params = params.copy()
        handler_params["command"] = command
        
        # Try handler with pattern: tool_command (e.g., "httpx_probe")
        handler_result = handler_execute(f"{tool}_{command}", handler_params, None)
        # If not found, try just tool name (e.g., "httpx")
        if handler_result is None:
            handler_result = handler_execute(tool, handler_params, None)
        
        if handler_result is not None:
            # Handler found and executed
            start_time = time.time()
            elapsed = time.time() - start_time
            
            # Determine success based on output
            success = not handler_result.startswith("⚠️") and not handler_result.startswith("Error")
            
            return ToolResult(
                success=success,
                tool=tool,
                action=command,
                output=handler_result,
                error="" if success else handler_result,
                elapsed_time=elapsed
            )
        
        # No handler - use CLI execution
        # Build command args
        try:
            args = self._build_args(spec, template, params)
        except KeyError as e:
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="",
                error=f"Missing parameter: {e}"
            )
        
        # Execute
        timeout = timeout_override or template.timeout
        start_time = time.time()
        
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL
            )
            elapsed = time.time() - start_time
            
            success = result.returncode in template.success_codes
            
            return ToolResult(
                success=success,
                tool=tool,
                action=command,
                output=result.stdout.strip(),
                error=result.stderr.strip() if not success else "",
                exit_code=result.returncode,
                elapsed_time=elapsed
            )
            
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="",
                error=f"Timeout after {timeout}s",
                elapsed_time=elapsed
            )
        except Exception as e:
            elapsed = time.time() - start_time
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="",
                error=str(e),
                elapsed_time=elapsed
            )
    
    def _build_args(
        self,
        spec: ToolSpec,
        template: CommandTemplate,
        params: Dict[str, Any]
    ) -> List[str]:
        """Build command arguments from template and params."""
        args = []
        
        # Add sudo if required
        if template.requires_sudo:
            args.append("sudo")
        
        # Add executable - handle 'python3 /path/to/script.py' format
        if spec.executable_path and ' ' in spec.executable_path:
            # Split python3 /path/script.py into separate args
            args.extend(spec.executable_path.split())
        else:
            args.append(spec.executable_path)
        
        # Process template args
        for arg in template.args:
            if "{" in arg and "}" in arg:
                # Replace placeholders
                for key, value in params.items():
                    arg = arg.replace(f"{{{key}}}", str(value))
                
                # Check for unreplaced placeholders
                if "{" in arg:
                    import re
                    missing = re.findall(r'\{(\w+)\}', arg)
                    if missing:
                        raise KeyError(missing[0])
            
            args.append(arg)
        
        return args
    
    def get_tool_info(self, tool: str) -> Dict[str, Any]:
        """Get information about a tool."""
        if tool not in self.tools:
            return {"error": f"Unknown tool: {tool}"}
        
        spec = self.tools[tool]
        return {
            "name": spec.name,
            "category": spec.category.value,
            "description": spec.description,
            "available": spec.is_available,
            "path": spec.executable_path,
            "commands": list(spec.commands.keys()),
            "install_hint": spec.install_hint if not spec.is_available else None
        }
    
    def execute_stream(
        self,
        tool: str,
        command: str,
        params: Dict[str, Any],
        timeout_override: int = None,
        line_callback: Callable[[str], None] = None
    ) -> ToolResult:
        """
        Execute a tool command with streaming output.
        
        Args:
            tool: Tool name (e.g., "nmap")
            command: Command name (e.g., "service_scan")
            params: Parameters for the command
            timeout_override: Override default timeout
            line_callback: Callback function for each output line
        
        Returns:
            ToolResult with output and parsed data
        """
        # Validate tool
        if tool not in self.tools:
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="",
                error=f"Unknown tool: {tool}"
            )
        
        spec = self.tools[tool]
        
        if not spec.is_available:
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="",
                error=f"⚠️ TOOL NOT INSTALLED: {tool}. {spec.install_hint}"
            )
        
        # Validate command
        if command not in spec.commands:
            available = ", ".join(spec.commands.keys())
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="",
                error=f"Unknown command '{command}' for {tool}. Available: {available}"
            )
        
        template = spec.commands[command]
        
        # Build command args
        try:
            args = self._build_args(spec, template, params)
        except KeyError as e:
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="",
                error=f"Missing parameter: {e}"
            )
        
        # Execute with streaming
        timeout = timeout_override or template.timeout
        start_time = time.time()
        output_lines = []
        
        try:
            import select
            
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                stdin=subprocess.DEVNULL
            )
            
            # Stream output line by line
            while True:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    process.kill()
                    return ToolResult(
                        success=False,
                        tool=tool,
                        action=command,
                        output="\n".join(output_lines),
                        error=f"Timeout after {timeout}s",
                        elapsed_time=elapsed
                    )
                
                # Read line
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    continue
                
                line = line.rstrip()
                output_lines.append(line)
                
                # Call callback if provided
                if line_callback:
                    line_callback(line)
            
            elapsed = time.time() - start_time
            success = process.returncode in template.success_codes
            
            return ToolResult(
                success=success,
                tool=tool,
                action=command,
                output="\n".join(output_lines),
                error="" if success else f"Exit code: {process.returncode}",
                exit_code=process.returncode,
                elapsed_time=elapsed
            )
            
        except Exception as e:
            elapsed = time.time() - start_time
            return ToolResult(
                success=False,
                tool=tool,
                action=command,
                output="\n".join(output_lines),
                error=str(e),
                elapsed_time=elapsed
            )
    
    def execute_chain(
        self,
        chain: List[Dict[str, Any]],
        pipe_output: bool = False,
        stop_on_failure: bool = False
    ) -> List[ToolResult]:
        """
        Execute multiple tools in sequence (tool chaining).
        
        Args:
            chain: List of tool execution specs:
                   [{"tool": "subfinder", "command": "enumerate", "params": {...}}, ...]
            pipe_output: If True, pass previous tool's output as input to next
            stop_on_failure: If True, stop chain on first failure
            
        Returns:
            List of ToolResult for each tool in the chain
        """
        results = []
        previous_output = ""
        
        for i, item in enumerate(chain):
            tool = item.get('tool', '')
            command = item.get('command', 'default')
            params = item.get('params', {}).copy()
            timeout = item.get('timeout')
            
            # Pipe previous output if enabled
            if pipe_output and previous_output and i > 0:
                # Add previous output as input parameter
                params['_previous_output'] = previous_output
                # Also try to set common input params
                if 'targets' not in params and 'target' not in params:
                    # Parse output as list of targets
                    lines = [l.strip() for l in previous_output.split('\n') if l.strip()]
                    if lines:
                        params['targets'] = lines[:50]  # Limit
            
            # Execute tool
            result = self.execute(tool, command, params, timeout)
            results.append(result)
            
            # Update previous output
            if result.success:
                previous_output = result.output
            
            # Stop on failure if configured
            if stop_on_failure and not result.success:
                break
        
        return results
    
    def execute_chain_summary(
        self,
        chain: List[Dict[str, Any]],
        pipe_output: bool = False
    ) -> Dict[str, Any]:
        """
        Execute chain and return summary.
        
        Returns:
            Dict with success, results, combined_output, and timing
        """
        import time
        start = time.time()
        
        results = self.execute_chain(chain, pipe_output)
        
        elapsed = time.time() - start
        all_success = all(r.success for r in results)
        combined_output = "\n\n".join([
            f"=== {r.tool}:{r.action} ===\n{r.output}"
            for r in results if r.output
        ])
        
        return {
            "success": all_success,
            "tools_executed": len(results),
            "tools_succeeded": sum(1 for r in results if r.success),
            "elapsed_time": elapsed,
            "combined_output": combined_output,
            "results": results
        }


# Global registry instance
_registry: Optional[ToolRegistry] = None

def get_registry() -> ToolRegistry:
    """Get the global ToolRegistry instance."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
