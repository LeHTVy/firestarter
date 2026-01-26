"""Spec Executor - Execute tools from declarative specs.

Simplified version of rutx ToolRegistry.execute().
"""

import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from tools.specs import ToolSpec, CommandTemplate, get_all_specs
from tools.process_streamer import ProcessStreamer


@dataclass
class ToolResult:
    """Standardized result from tool execution."""
    success: bool
    tool: str
    command: str
    output: str
    error: str = ""
    exit_code: int = 0
    elapsed_time: float = 0.0
    parsed_data: Dict[str, Any] = field(default_factory=dict)


class SpecExecutor:
    """Execute tools from declarative specs."""
    
    def __init__(self):
        self.specs: Dict[str, ToolSpec] = {}
        self.aliases: Dict[str, str] = {}
        self._load_specs()
        self._discover_tools()
    
    def _load_specs(self):
        """Load all tool specs."""
        for spec in get_all_specs():
            self.specs[spec.name] = spec
            # Register aliases
            for alias in getattr(spec, 'aliases', []):
                self.aliases[alias] = spec.name
    
    def _discover_tools(self):
        """Discover which tools are installed."""
        for spec in self.specs.values():
            spec.find_executable()
    
    def get_tool(self, name: str) -> Optional[ToolSpec]:
        """Get tool by name or alias."""
        # Try direct match
        if name in self.specs:
            return self.specs[name]
        # Try alias
        if name in self.aliases:
            return self.specs.get(self.aliases[name])
        return None
    
    def list_available(self) -> List[ToolSpec]:
        """List available (installed) tools."""
        return [s for s in self.specs.values() if s.is_available]
    
    def list_missing(self) -> List[ToolSpec]:
        """List missing (not installed) tools."""
        return [s for s in self.specs.values() if not s.is_available]
    
    def execute(
        self,
        tool: str,
        command: str,
        params: Dict[str, Any],
        timeout_override: int = None
    ) -> ToolResult:
        """Execute a tool command.
        
        Args:
            tool: Tool name (e.g., "subfinder")
            command: Command name (e.g., "enum")
            params: Parameters for the command (e.g., {"domain": "example.com"})
            timeout_override: Override default timeout
            
        Returns:
            ToolResult with output
        """
        spec = self.get_tool(tool)
        
        if not spec:
            return ToolResult(
                success=False,
                tool=tool,
                command=command,
                output="",
                error=f"Unknown tool: {tool}"
            )
        
        if not spec.is_available:
            return ToolResult(
                success=False,
                tool=tool,
                command=command,
                output="",
                error=f"⚠️ TOOL NOT INSTALLED: {tool}. {spec.install_hint}"
            )
        
        if command not in spec.commands:
            available = ", ".join(spec.commands.keys())
            return ToolResult(
                success=False,
                tool=tool,
                command=command,
                output="",
                error=f"Unknown command '{command}' for {tool}. Available: {available}"
            )
        
        template = spec.commands[command]
        
        # Build command args
        try:
            use_python_module = False
            if not spec.executable_path and spec.is_available and "python" in spec.install_hint.lower():
                use_python_module = True
            
            # Build args normally first
            template_args = self._build_args(spec, template, params)
            
            if use_python_module:
                import sys
                cmd_args = template_args[1:] 
                args = [sys.executable, "-m", spec.name] + cmd_args
            else:
                args = template_args
                
                
        except KeyError as e:
            return ToolResult(
                success=False,
                tool=tool,
                command=command,
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
                command=command,
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
                command=command,
                output="",
                error=f"Timeout after {timeout}s",
                elapsed_time=elapsed
            )
        except Exception as e:
            elapsed = time.time() - start_time
            return ToolResult(
                success=False,
                tool=tool,
                command=command,
                output="",
                error=str(e),
                elapsed_time=elapsed
            )
    
    def execute_streaming(
        self,
        tool: str,
        command: str,
        params: Dict[str, Any],
        stream_callback: Optional[callable] = None,
        timeout_override: int = None
    ) -> ToolResult:
        """Execute a tool command with real-time streaming output.
        
        Args:
            tool: Tool name
            command: Command name
            params: Parameters for the command
            stream_callback: Callback function(line: str) for each output line
            timeout_override: Override default timeout
            
        Returns:
            ToolResult with output
        """
        spec = self.get_tool(tool)
        
        if not spec:
            if stream_callback:
                stream_callback(f"❌ Unknown tool: {tool}")
            return ToolResult(success=False, tool=tool, command=command, output="", 
                            error=f"Unknown tool: {tool}")
        
        if not spec.is_available:
            error_msg = f"⚠️ TOOL NOT INSTALLED: {tool}. {spec.install_hint}"
            if stream_callback:
                stream_callback(error_msg)
            return ToolResult(success=False, tool=tool, command=command, output="", error=error_msg)
        
        if command not in spec.commands:
            available = ", ".join(spec.commands.keys())
            error_msg = f"Unknown command '{command}'. Available: {available}"
            if stream_callback:
                stream_callback(f"❌ {error_msg}")
            return ToolResult(success=False, tool=tool, command=command, output="", error=error_msg)
        
        template = spec.commands[command]
        
        try:
            args = self._build_args(spec, template, params)
        except KeyError as e:
            error_msg = f"Missing parameter: {e}"
            if stream_callback:
                stream_callback(f"❌ {error_msg}")
            return ToolResult(success=False, tool=tool, command=command, output="", error=error_msg)
        
        timeout = timeout_override or template.timeout
        start_time = time.time()
        output_lines = []
        
        if stream_callback:
            stream_callback(f"🚀 Running: {' '.join(args)}")
        
        if stream_callback:
            stream_callback(f"🚀 Running: {' '.join(args)}")
        
        streamer = ProcessStreamer()
        
        try:
            exit_code = 0
            for line in streamer.execute(args, timeout=timeout):
                clean_line = line.rstrip()
                if not clean_line:
                    continue
                    
                output_lines.append(clean_line)
                if stream_callback:
                    stream_callback(clean_line)
            pass

            success = True 
            
            elapsed = time.time() - start_time
            
            if stream_callback:
                stream_callback(f"✅ Completed in {elapsed:.2f}s")
            
            return ToolResult(
                success=True,
                tool=tool,
                command=command,
                output="\n".join(output_lines),
                error="",
                exit_code=0,
                elapsed_time=elapsed
            )
            
        except Exception as e:
            elapsed = time.time() - start_time
            if stream_callback:
                stream_callback(f"❌ Error: {str(e)}")
            return ToolResult(
                success=False, tool=tool, command=command,
                output="\n".join(output_lines),
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
        args = [spec.executable_path]
        
        # Parameter fallbacks - allow common parameter aliases
        normalized_params = dict(params)
        
        # target fallbacks: domain, url, host, ip can all be used as target
        if 'target' not in normalized_params:
            for fallback in ['domain', 'url', 'host', 'ip', 'address']:
                if fallback in normalized_params:
                    normalized_params['target'] = normalized_params[fallback]
                    break
        
        # domain fallbacks: target, host can be used as domain
        if 'domain' not in normalized_params:
            for fallback in ['target', 'host', 'url']:
                if fallback in normalized_params:
                    normalized_params['domain'] = normalized_params[fallback]
                    break
        
        # url fallbacks: target, domain can be used as url
        if 'url' not in normalized_params:
            for fallback in ['target', 'domain', 'host']:
                if fallback in normalized_params:
                    val = normalized_params[fallback]
                    # Add http:// if not present
                    if not val.startswith('http'):
                        val = f"http://{val}"
                    normalized_params['url'] = val
                    break
        
        for arg in template.args:
            if "{" in arg and "}" in arg:
                # Template variable - substitute
                for key, value in normalized_params.items():
                    arg = arg.replace(f"{{{key}}}", str(value))
                if "{" in arg:
                    # Still has unsubstituted vars
                    raise KeyError(arg)
            args.append(arg)
        
        return args


# Singleton instance
_executor: Optional[SpecExecutor] = None


def get_spec_executor() -> SpecExecutor:
    """Get global spec executor instance."""
    global _executor
    if _executor is None:
        _executor = SpecExecutor()
    return _executor
