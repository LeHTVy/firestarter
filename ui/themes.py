"""
UI Themes - Consistent Styling
===============================

Defines themes and color schemes for SNODE UI.
"""

from dataclasses import dataclass
from typing import Dict, Any
from enum import Enum


class SeverityColor(Enum):
    """Color codes for severity levels."""
    CRITICAL = "red"
    HIGH = "yellow"
    MEDIUM = "cyan"
    LOW = "green"
    INFO = "blue"
    UNKNOWN = "dim"


@dataclass
class Theme:
    """UI Theme configuration."""
    
    # Colors
    primary: str = "cyan"
    success: str = "green"
    warning: str = "yellow"
    error: str = "red"
    info: str = "blue"
    dim: str = "dim"
    
    # Status colors
    severity_colors: Dict[str, str] = None
    
    # Icons
    icons: Dict[str, str] = None
    
    def __post_init__(self):
        if self.severity_colors is None:
            self.severity_colors = {
                "critical": SeverityColor.CRITICAL.value,
                "high": SeverityColor.HIGH.value,
                "medium": SeverityColor.MEDIUM.value,
                "low": SeverityColor.LOW.value,
                "info": SeverityColor.INFO.value,
                "unknown": SeverityColor.UNKNOWN.value,
            }
        
        if self.icons is None:
            self.icons = {
                "target": "🎯",
                "subdomain": "🌐",
                "port": "🔌",
                "vulnerability": "🛡️",
                "tool": "🔧",
                "success": "✅",
                "error": "❌",
                "warning": "⚠️",
                "info": "ℹ️",
                "search": "🔍",
                "attack": "⚔️",
                "recon": "📡",
                "scan": "🔍",
                "exploit": "💣",
            }


# Global theme instance
_current_theme: Theme = Theme()


def get_theme() -> Theme:
    """Get current theme."""
    return _current_theme


def set_theme(theme: Theme):
    """Set current theme."""
    global _current_theme
    _current_theme = theme
