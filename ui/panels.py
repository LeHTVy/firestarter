"""Rich panel components for streaming display."""

from typing import Optional, List
from rich.console import Console, Group
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.layout import Layout


class ToolExecutionPanel:
    """Panel for displaying tool execution with live output."""
    
    def __init__(self, tool_name: str, command_name: Optional[str] = None, target: Optional[str] = None):
        """Initialize tool execution panel.
        
        Args:
            tool_name: Name of the tool
            command_name: Optional command name
            target: Optional target being scanned
        """
        self.tool_name = tool_name
        self.command_name = command_name
        self.target = target
        self.output_lines: List[str] = []
        self.status = "Initializing..."
        self.max_lines = 50  # Limit output lines to prevent overflow
        
    def update_status(self, status: str):
        """Update status message."""
        self.status = status
    
    def add_output(self, line: str):
        """Add output line."""
        self.output_lines.append(line)
        # Keep only last N lines
        if len(self.output_lines) > self.max_lines:
            self.output_lines = self.output_lines[-self.max_lines:]
    
    def render(self) -> Panel:
        """Render panel."""
        # Build title
        title = f"Tool: {self.tool_name}"
        if self.command_name:
            title += f":{self.command_name}"
        
        # Build content
        content_lines = []
        
        if self.target:
            content_lines.append(f"[bold]Target:[/bold] {self.target}")
            content_lines.append("")
        
        content_lines.append(f"[bold]Status:[/bold] {self.status}")
        content_lines.append("")
        content_lines.append("[bold]Output:[/bold]")
        
        # Add output lines
        for line in self.output_lines[-20:]:  # Show last 20 lines
            content_lines.append(f"  {line}")
        
        if len(self.output_lines) > 20:
            content_lines.append(f"  ... ({len(self.output_lines) - 20} more lines)")
        
        content = "\n".join(content_lines)
        
        return Panel(
            content,
            title=f"[cyan]{title}[/cyan]",
            border_style="cyan",
            expand=False
        )


class ModelResponsePanel:
    """Panel for displaying model responses with streaming."""
    
    def __init__(self, model_name: str):
        """Initialize model response panel.
        
        Args:
            model_name: Name of the model
        """
        self.model_name = model_name
        self.response_text = ""
        self.status = "Thinking..."
        self.expanded = True  # Default to expanded
        self.max_collapsed_lines = 20  # Show first 20 lines when collapsed
    
    def update_status(self, status: str):
        """Update status message."""
        self.status = status
    
    def add_chunk(self, chunk: str):
        """Add response chunk."""
        self.response_text += chunk
    
    def toggle_expand(self):
        """Toggle expanded/collapsed state."""
        self.expanded = not self.expanded
    
    def render(self) -> Panel:
        """Render panel with full content support (no truncation)."""
        content_lines = []
        content_lines.append(f"[bold]Status:[/bold] {self.status}")
        content_lines.append("")
        content_lines.append("[bold]Response:[/bold]")
        content_lines.append("")
        
        if self.response_text:
            # Show full response - no line limit, let Rich handle scrolling
            # Wrap long lines for better display
            lines = self.response_text.split('\n')
            
            # When expanded, show all lines; when collapsed, show first N lines
            if self.expanded:
                display_lines = lines
            else:
                display_lines = lines[:self.max_collapsed_lines]
            
            # Process each line with word wrapping
            for line in display_lines:
                # Wrap very long lines (over 120 chars) for better readability
                # Use terminal width if available, otherwise default to 120
                max_width = 120
                if len(line) > max_width:
                    # Word wrap: break long lines intelligently
                    words = line.split(' ')
                    current_line = ""
                    for word in words:
                        if len(current_line + word) > max_width:
                            if current_line:
                                content_lines.append(current_line.rstrip())
                            current_line = word + " "
                        else:
                            current_line += word + " "
                    if current_line:
                        content_lines.append(current_line.rstrip())
                else:
                    content_lines.append(line)
            
            # Add expand/collapse indicator
            total_lines = len(lines)
            if not self.expanded and total_lines > self.max_collapsed_lines:
                content_lines.append("")
                content_lines.append(f"[dim yellow]💡 Press 'e' to expand or 't' to toggle (showing {self.max_collapsed_lines}/{total_lines} lines)[/dim yellow]")
            elif self.expanded and total_lines > self.max_collapsed_lines:
                content_lines.append("")
                content_lines.append(f"[dim yellow]💡 Press 'c' to collapse or 't' to toggle (showing all {total_lines} lines)[/dim yellow]")
            
            # Add indicator if response is very long
            if total_lines > 100:
                content_lines.append("")
                content_lines.append(f"[dim](Total: {total_lines} lines, {len(self.response_text)} characters)[/dim]")
        else:
            content_lines.append("[dim]Waiting for response...[/dim]")
        
        content = "\n".join(content_lines)
        
        # Build title with expand/collapse indicator
        title = f"[blue]Model: {self.model_name}[/blue]"
        if self.response_text:
            total_lines = len(self.response_text.split('\n'))
            if total_lines > self.max_collapsed_lines:
                title += f" [dim]({'Expanded' if self.expanded else 'Collapsed'})[/dim]"
        
        # Use expand=True to allow panel to use full available space
        # Rich will handle scrolling automatically if content exceeds terminal height
        return Panel(
            content,
            title=title,
            border_style="blue",
            expand=True,  # Always expand to use available space
            height=None  # No height limit - let Rich handle scrolling
        )


class ProgressPanel:
    """Panel for showing overall workflow progress."""
    
    def __init__(self):
        """Initialize progress panel."""
        self.current_step = "Initializing..."
        self.completed_steps: List[str] = []
        self.total_steps = 0
    
    def set_total_steps(self, total: int):
        """Set total number of steps."""
        self.total_steps = total
    
    def update_step(self, step: str):
        """Update current step."""
        self.current_step = step
    
    def complete_step(self, step: str):
        """Mark step as completed."""
        if step not in self.completed_steps:
            self.completed_steps.append(step)
    
    def render(self) -> Panel:
        """Render panel."""
        content_lines = []
        content_lines.append(f"[bold]Current:[/bold] {self.current_step}")
        content_lines.append("")
        
        if self.completed_steps:
            content_lines.append("[bold]Completed:[/bold]")
            for step in self.completed_steps:
                content_lines.append(f"  ✓ {step}")
        
        if self.total_steps > 0:
            progress = len(self.completed_steps) / self.total_steps * 100
            content_lines.append("")
            content_lines.append(f"[bold]Progress:[/bold] {len(self.completed_steps)}/{self.total_steps} ({progress:.0f}%)")
        
        content = "\n".join(content_lines)
        
        return Panel(
            content,
            title="[yellow]Workflow Progress[/yellow]",
            border_style="yellow",
            expand=False
        )
