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
        """Find the tool executable on the system."""
        import shutil
        for exe_name in self.executable_names:
            path = shutil.which(exe_name)
            if path:
                self.executable_path = path
                self.is_available = True
                return True
        
        # Fallback: Check if it's a python package
        if "python" in self.install_hint.lower():
            try:
                import importlib.util
                # Try name variants
                for name in [self.name] + self.executable_names:
                    # heuristic: standard package names don't usually have spaces or args
                    clean_name = name.split()[0].split('-')[-1] # e.g. "python3 -m theHarvester" -> "theHarvester"
                    if importlib.util.find_spec(clean_name):
                        self.is_available = True
                        # Don't set executable_path, signals to use -m
                        return True
            except ImportError:
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

