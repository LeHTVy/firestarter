"""Metasploit tool implementation with subprocess streaming."""

from typing import Dict, Any, Optional, Callable, List
import os
import tempfile
import re
from tools.implementations.cli_executor import run_cli_command, check_tool_installed


def execute(module: str,
           target: str,
           options: Optional[Dict[str, Any]] = None,
           payload: Optional[str] = None,
           stream_callback: Optional[Callable[[str], None]] = None,
           timeout: int = 600) -> Dict[str, Any]:
    """Execute Metasploit exploit module."""
    if not check_tool_installed("msfconsole"):
        return {
            "success": False,
            "error": "msfconsole not found. Install Metasploit Framework.",
            "results": None
        }
    
    if stream_callback:
        stream_callback(f"Metasploit: {module} on {target}")
    
    commands = [
        f"use {module}",
        f"set RHOSTS {target}",
        f"set RHOST {target}"
    ]
    
    if options:
        for key, value in options.items():
            commands.append(f"set {key} {value}")
    
    if payload:
        commands.append(f"set PAYLOAD {payload}")
    
    commands.extend(["show options", "run", "exit -y"])
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rc', delete=False) as f:
        f.write("\n".join(commands))
        rc_file = f.name
    
    try:
        cmd = ["msfconsole", "-q", "-r", rc_file]
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        raw_output = result.get("raw_output", "")
        
        sessions = _parse_sessions(raw_output)
        vulns = _parse_vulns(raw_output)
        
        return {
            "success": result.get("success", False),
            "results": {
                "module": module,
                "target": target,
                "sessions": sessions,
                "vulnerabilities": vulns
            },
            "raw_output": raw_output
        }
    finally:
        try:
            os.unlink(rc_file)
        except Exception:
            pass


def auxiliary_scan(module: str,
                  target: str,
                  options: Optional[Dict[str, Any]] = None,
                  stream_callback: Optional[Callable[[str], None]] = None,
                  timeout: int = 300) -> Dict[str, Any]:
    """Run Metasploit auxiliary module."""
    if not check_tool_installed("msfconsole"):
        return {"success": False, "error": "msfconsole not found", "results": None}
    
    commands = [f"use {module}", f"set RHOSTS {target}"]
    if options:
        for k, v in options.items():
            commands.append(f"set {k} {v}")
    commands.extend(["run", "exit -y"])
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rc', delete=False) as f:
        f.write("\n".join(commands))
        rc_file = f.name
    
    try:
        result = run_cli_command(["msfconsole", "-q", "-r", rc_file], 
                                timeout=timeout, stream_callback=stream_callback)
        return {
            "success": result.get("success", False),
            "results": {"module": module, "target": target},
            "raw_output": result.get("raw_output", "")
        }
    finally:
        try:
            os.unlink(rc_file)
        except Exception:
            pass


def _parse_sessions(output: str) -> List[Dict]:
    """Parse sessions from output."""
    sessions = []
    pattern = r'session (\d+) opened \(([^)]+)\)'
    for match in re.findall(pattern, output, re.IGNORECASE):
        sessions.append({"id": match[0], "connection": match[1]})
    return sessions


def _parse_vulns(output: str) -> List[Dict]:
    """Parse vulnerabilities from output."""
    vulns = []
    patterns = [r'\[\+\]\s+(.+?)\s+is vulnerable', r'VULNERABLE\s*[:\-]\s*(.+)']
    for pattern in patterns:
        for match in re.findall(pattern, output, re.IGNORECASE):
            vulns.append({"description": match.strip()})
    return vulns
