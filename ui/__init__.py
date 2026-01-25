"""
UI Module - Beautiful Interface Components
==========================================

Centralized UI components for SNODE.
Provides consistent, beautiful formatting for all output.
"""

from .console import get_console, ConsoleManager
from .components import (
    TargetInfoCard,
    FindingCard,
    ToolResultCard,
    AnalysisCard,
    AnalyzerResultCard,
    ProgressIndicator,
    StatusBadge,
    CompanyInfoCard,
)

from .themes import Theme, get_theme, set_theme

# Streaming Display
from .panels import ToolExecutionPanel, ModelResponsePanel, ProgressPanel
from .streaming_manager import StreamingManager, get_streaming_manager

__all__ = [
    # Console
    "get_console",
    "ConsoleManager",
    
    # Components
    "TargetInfoCard",
    "FindingCard",
    "ToolResultCard",
    "AnalysisCard",
    "AnalyzerResultCard",
    "ProgressIndicator",
    "StatusBadge",
    "CompanyInfoCard",
    
    # Themes
    "Theme",
    "get_theme",
    "set_theme",
    
    # Streaming Display
    "ToolExecutionPanel",
    "ModelResponsePanel",
    "ProgressPanel",
    "StreamingManager",
    "get_streaming_manager",
]
