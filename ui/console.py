"""
Console Manager - Centralized Rich Console
==========================================

Manages Rich console instance with consistent styling.
"""

from rich.console import Console
from rich.theme import Theme as RichTheme
from typing import Optional

# Global console instance
_console: Optional[Console] = None


def get_console() -> Console:
    """Get or create the global console instance."""
    global _console
    if _console is None:
        # Custom theme for SNODE
        custom_theme = RichTheme({
            "info": "cyan",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "dim": "dim",
            "bold": "bold",
            "title": "bold cyan",
            "subtitle": "cyan",
            "highlight": "yellow",
        })
        _console = Console(theme=custom_theme, width=120)
    return _console


class ConsoleManager:
    """Manages console output with consistent formatting."""
    
    def __init__(self, console: Console = None):
        self.console = console or get_console()
    
    def print_section(self, title: str, content: str = "", style: str = "bold cyan"):
        """Print a section with title."""
        self.console.print(f"\n[{style}]{title}[/]")
        if content:
            self.console.print(content)
    
    def print_success(self, message: str):
        """Print success message."""
        self.console.print(f"[green]✅ {message}[/]")
    
    def print_error(self, message: str):
        """Print error message."""
        self.console.print(f"[red]❌ {message}[/]")
    
    def print_warning(self, message: str):
        """Print warning message."""
        self.console.print(f"[yellow]⚠️ {message}[/]")
    
    def print_info(self, message: str):
        """Print info message."""
        self.console.print(f"[cyan]ℹ️ {message}[/]")
    
    def print_separator(self, char: str = "=", length: int = 70):
        """Print a separator line."""
        self.console.print(char * length)
