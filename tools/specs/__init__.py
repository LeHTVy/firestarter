"""Tool Specs Package - Declarative tool specifications."""

from typing import List
from dataclasses import dataclass, field
from enum import Enum


class ToolCategory(str, Enum):
    """Categories of security tools."""
    RECON = "recon"
    SCANNING = "scanning"
    VULN = "vulnerability"
    EXPLOIT = "exploitation"
    ENUM = "enumeration"
    OSINT = "osint"
    BRUTE = "brute_force"
    WEB = "web"
    UTIL = "utility"


@dataclass
class CommandTemplate:
    """Template for a tool command."""
    args: List[str]
    timeout: int = 300
    requires_sudo: bool = False
    output_format: str = "text"
    success_codes: List[int] = field(default_factory=lambda: [0])
    description: str = ""


@dataclass
class ToolSpec:
    """Specification for a security tool.
    
    Defines executable location, available commands, and how to parse outputs.
    """
    name: str
    category: ToolCategory
    description: str
    executable_names: List[str]
    install_hint: str
    commands: dict = field(default_factory=dict)
    executable_path: str = None
    is_available: bool = False
    aliases: List[str] = field(default_factory=list)
    
    def find_executable(self) -> bool:
        """Find the tool executable on the system with enhanced path discovery."""
        import shutil
        import os
        from pathlib import Path
        
        # 1. Check standard PATH
        for exe_name in self.executable_names:
            path = shutil.which(exe_name)
            if path:
                self.executable_path = path
                self.is_available = True
                return True
        
        # 2. Check common non-standard locations (Go, Local Bin, etc.)
        home = str(Path.home())
        extra_paths = [
            os.path.join(home, "go", "bin"),
            os.path.join(home, ".local", "bin"),
            "/usr/local/bin",
            "/snap/bin"
        ]
        
        for exe_name in self.executable_names:
            for base_path in extra_paths:
                full_path = os.path.join(base_path, exe_name)
                # Check different extensions for Windows if needed, though they are likely in PATH already
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    self.executable_path = full_path
                    self.is_available = True
                    return True

        # 3. Fallback: Check if it's a python package
        if "pip" in self.install_hint.lower() or "python" in self.install_hint.lower():
            try:
                import importlib.util
                # Try name variants
                for name in [self.name] + self.executable_names:
                    # heuristic: standard package names vs executable names
                    # e.g. "bbot" (pkg) vs "bbot" (exe), "theHarvester" (pkg) vs "theharvester" (exe)
                    clean_name = name.split()[0].split('-')[-1]
                    if importlib.util.find_spec(clean_name) or importlib.util.find_spec(clean_name.lower()):
                        self.is_available = True
                        # Don't set executable_path, signals to use -m or direct call if in path
                        return True
            except (ImportError, AttributeError):
                pass
                
        return False


def get_all_specs() -> List[ToolSpec]:
    """Get all tool specifications from all spec modules."""
    from tools.specs import recon, scanning, web
    
    all_specs = []
    all_specs.extend(recon.get_specs())
    all_specs.extend(scanning.get_specs())
    all_specs.extend(web.get_specs())
    
    return all_specs


# Re-export executor for convenience
def get_spec_executor():
    """Get global spec executor instance."""
    from tools.specs.executor import get_spec_executor as _get_executor
    return _get_executor()

