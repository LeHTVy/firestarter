"""Generic CLI tool executor with subprocess streaming.

Provides a unified interface for executing command-line security tools
with real-time output streaming, timeout handling, and result parsing.
"""

import subprocess
import shutil
import os
import tempfile
from typing import Dict, Any, Optional, Callable, List, Union
from datetime import datetime
from pathlib import Path


class CLIExecutor:
    """Generic CLI tool executor with streaming support."""
    
    def __init__(self, 
                 default_timeout: int = 600,
                 working_dir: Optional[str] = None):
        """Initialize CLI executor.
        
        Args:
            default_timeout: Default timeout in seconds (10 minutes)
            working_dir: Working directory for command execution
        """
        self.default_timeout = default_timeout
        self.working_dir = working_dir or tempfile.gettempdir()
    
    def run(self,
            cmd: Union[str, List[str]],
            timeout: Optional[int] = None,
            stream_callback: Optional[Callable[[str], None]] = None,
            env: Optional[Dict[str, str]] = None,
            cwd: Optional[str] = None,
            shell: bool = False) -> Dict[str, Any]:
        """Execute a CLI command with streaming output.
        
        Args:
            cmd: Command to execute (string or list)
            timeout: Timeout in seconds (None = use default)
            stream_callback: Callback for streaming output
            env: Environment variables
            cwd: Working directory
            shell: Use shell execution
            
        Returns:
            Execution result dictionary
        """
        timeout = timeout or self.default_timeout
        cwd = cwd or self.working_dir
        
        # Build environment
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        
        # Convert string command to list if needed
        if isinstance(cmd, str) and not shell:
            cmd = cmd.split()
        
        # Check if command exists
        if isinstance(cmd, list) and cmd:
            binary = cmd[0]
            if not shutil.which(binary):
                error_msg = f"Command '{binary}' not found. Please install it first."
                if stream_callback:
                    stream_callback(f"❌ Error: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "results": None,
                    "raw_output": ""
                }
        
        start_time = datetime.utcnow()
        output_lines = []
        
        if stream_callback:
            cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
            stream_callback(f"🚀 Executing: {cmd_str}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=run_env,
                cwd=cwd,
                shell=shell
            )
            
            # Stream output in real-time
            for line in iter(process.stdout.readline, ''):
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    if stream_callback:
                        stream_callback(line)
            
            # Wait for completion
            return_code = process.wait(timeout=timeout)
            
            end_time = datetime.utcnow()
            elapsed = (end_time - start_time).total_seconds()
            
            if stream_callback:
                status = "✅" if return_code == 0 else "⚠️"
                stream_callback(f"{status} Completed in {elapsed:.2f}s (exit code: {return_code})")
            
            return {
                "success": return_code == 0,
                "return_code": return_code,
                "raw_output": "\n".join(output_lines),
                "output_lines": output_lines,
                "elapsed_seconds": elapsed,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "error": None if return_code == 0 else f"Command exited with code {return_code}"
            }
            
        except subprocess.TimeoutExpired:
            process.kill()
            error_msg = f"Command timed out after {timeout} seconds"
            if stream_callback:
                stream_callback(f"⏰ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "raw_output": "\n".join(output_lines),
                "output_lines": output_lines,
                "elapsed_seconds": timeout
            }
            
        except FileNotFoundError as e:
            error_msg = f"Command not found: {str(e)}"
            if stream_callback:
                stream_callback(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "raw_output": "",
                "output_lines": []
            }
            
        except Exception as e:
            error_msg = str(e)
            if stream_callback:
                stream_callback(f"❌ Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "raw_output": "\n".join(output_lines),
                "output_lines": output_lines
            }


# Global executor instance
_cli_executor: Optional[CLIExecutor] = None


def get_cli_executor() -> CLIExecutor:
    """Get global CLI executor instance."""
    global _cli_executor
    if _cli_executor is None:
        _cli_executor = CLIExecutor()
    return _cli_executor


def run_cli_command(cmd: Union[str, List[str]],
                   timeout: Optional[int] = None,
                   stream_callback: Optional[Callable[[str], None]] = None,
                   env: Optional[Dict[str, str]] = None,
                   cwd: Optional[str] = None,
                   shell: bool = False) -> Dict[str, Any]:
    """Convenience function to run a CLI command.
    
    Args:
        cmd: Command to execute
        timeout: Timeout in seconds
        stream_callback: Callback for streaming output
        env: Environment variables
        cwd: Working directory
        shell: Use shell execution
        
    Returns:
        Execution result dictionary
    """
    return get_cli_executor().run(
        cmd=cmd,
        timeout=timeout,
        stream_callback=stream_callback,
        env=env,
        cwd=cwd,
        shell=shell
    )


def check_tool_installed(tool_name: str) -> bool:
    """Check if a tool is installed and available in PATH.
    
    Args:
        tool_name: Name of the tool binary
        
    Returns:
        True if tool is installed
    """
    return shutil.which(tool_name) is not None


def get_tool_path(tool_name: str) -> Optional[str]:
    """Get full path to a tool binary.
    
    Args:
        tool_name: Name of the tool binary
        
    Returns:
        Full path or None if not found
    """
    return shutil.which(tool_name)


def parse_key_value_output(output: str, separator: str = ":") -> Dict[str, str]:
    """Parse key-value output format.
    
    Args:
        output: Raw output string
        separator: Key-value separator
        
    Returns:
        Dictionary of parsed key-value pairs
    """
    result = {}
    for line in output.split("\n"):
        if separator in line:
            parts = line.split(separator, 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                if key:
                    result[key] = value
    return result


def parse_table_output(output: str, 
                      delimiter: Optional[str] = None,
                      header_line: int = 0) -> List[Dict[str, str]]:
    """Parse table-formatted output.
    
    Args:
        output: Raw output string
        delimiter: Column delimiter (None = whitespace)
        header_line: Line number containing headers (0-indexed)
        
    Returns:
        List of dictionaries (one per row)
    """
    lines = [l.strip() for l in output.split("\n") if l.strip()]
    if len(lines) <= header_line:
        return []
    
    # Get headers
    if delimiter:
        headers = [h.strip() for h in lines[header_line].split(delimiter)]
    else:
        headers = lines[header_line].split()
    
    # Parse data rows
    result = []
    for line in lines[header_line + 1:]:
        if delimiter:
            values = [v.strip() for v in line.split(delimiter)]
        else:
            values = line.split()
        
        if len(values) >= len(headers):
            row = {headers[i]: values[i] for i in range(len(headers))}
            result.append(row)
    
    return result
