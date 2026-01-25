"""
UI Components - Reusable Display Components
============================================

Beautiful, reusable components for displaying different types of information.
"""

from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich.markdown import Markdown
from rich.box import ROUNDED, DOUBLE_EDGE, MINIMAL
from .console import get_console
from .themes import get_theme, SeverityColor


class TargetInfoCard:
    """Display target information in a beautiful card."""
    
    def __init__(self, console: Console = None):
        self.console = console or get_console()
        self.theme = get_theme()
    
    def render(self, domain: str, company_info: Dict[str, Any] = None) -> Panel:
        """Render target info card."""
        content_parts = [f"[bold {self.theme.primary}]{domain}[/]"]
        
        if company_info:
            content_parts.append("")
            if company_info.get("name") and company_info.get("name") != "N/A":
                content_parts.append(f"[bold]Company:[/] {company_info.get('name')}")
            if company_info.get("location") and company_info.get("location") != "N/A":
                content_parts.append(f"[bold]Location:[/] {company_info.get('location')}")
            if company_info.get("industry") and company_info.get("industry") != "N/A":
                content_parts.append(f"[bold]Industry:[/] {company_info.get('industry')}")
            if company_info.get("description") and company_info.get("description") != "N/A":
                content_parts.append(f"[bold]Description:[/] {company_info.get('description')}")
            if company_info.get("additional_info") and company_info.get("additional_info") != "N/A":
                content_parts.append(f"[bold]Additional Info:[/] {company_info.get('additional_info')}")
        
        content = "\n".join(content_parts)
        return Panel(
            content,
            title=f"{self.theme.icons.get('target', '🎯')} Target Information",
            border_style=self.theme.primary,
            box=ROUNDED
        )




class FindingCard:
    """Display a finding (subdomain, port, vulnerability) in a card."""
    
    def __init__(self, console: Console = None):
        self.console = console or get_console()
        self.theme = get_theme()
    
    def render(self, finding_type: str, data: Dict[str, Any], severity: str = None) -> Panel:
        """Render finding card."""
        icon = self.theme.icons.get(finding_type.lower(), "📌")
        title = f"{icon} {finding_type.upper()}"
        
        content_parts = []
        for key, value in data.items():
            if value:
                content_parts.append(f"[bold]{key.replace('_', ' ').title()}:[/] {value}")
        
        content = "\n".join(content_parts) if content_parts else str(data)
        
        border_color = self.theme.primary
        if severity:
            border_color = self.theme.severity_colors.get(severity.lower(), self.theme.primary)
        
        return Panel(
            content,
            title=title,
            border_style=border_color,
            box=ROUNDED
        )




class AnalysisCard:
    """Display analysis results in a card."""
    
    def __init__(self, console: Console = None):
        self.console = console or get_console()
        self.theme = get_theme()
    
    def render(self, analysis: Dict[str, Any]) -> Panel:
        """Render analysis card."""
        title = f"{self.theme.icons.get('info', 'ℹ️')} Analysis Results"
        
        content_parts = []
        
        # Findings
        if analysis.get("findings"):
            content_parts.append("[bold]Findings:[/]")
            for finding in analysis.get("findings", [])[:5]:
                severity = finding.get("severity", "Unknown")
                color = self.theme.severity_colors.get(severity.lower(), "white")
                content_parts.append(f"  [{color}]• {finding.get('issue', 'N/A')}[/] ({severity})")
            content_parts.append("")
        
        # Summary
        if analysis.get("summary"):
            content_parts.append(f"[bold]Summary:[/] {analysis.get('summary')}")
            content_parts.append("")
        
        # Next steps
        if analysis.get("next_tool"):
            content_parts.append(f"[bold]Next Step:[/] Use {analysis.get('next_tool')}")
        
        content = "\n".join(content_parts) if content_parts else "No analysis available"
        
        return Panel(
            content,
            title=title,
            border_style=self.theme.info,
            box=ROUNDED
        )




