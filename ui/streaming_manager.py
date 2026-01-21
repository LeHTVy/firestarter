"""Streaming manager for coordinating live updates."""

from typing import Dict, Optional, Callable, Any
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel

from ui.panels import ToolExecutionPanel, ModelResponsePanel, ProgressPanel
from ui.keyboard_listener import KeyboardListener


class StreamingManager:
    """Manages streaming events and panel updates."""
    
    def __init__(self, console: Optional[Console] = None, enable_keyboard: bool = True):
        """Initialize streaming manager.
        
        Args:
            console: Rich console instance. Creates new if None.
            enable_keyboard: Enable keyboard listener for expand/collapse
        """
        self.console = console or Console()
        self.tool_panels: Dict[str, ToolExecutionPanel] = {}
        self.model_panels: Dict[str, ModelResponsePanel] = {}
        self.progress_panel = ProgressPanel()
        self.live: Optional[Live] = None
        self.layout: Optional[Layout] = None
        self.keyboard_listener: Optional[KeyboardListener] = None
        self.enable_keyboard = enable_keyboard
    
    def start(self):
        """Start live display and keyboard listener."""
        self.layout = Layout()
        # Give models section more space and allow it to expand for long responses
        self.layout.split_column(
            Layout(name="progress", size=5),
            Layout(name="tools", ratio=1),
            Layout(name="models", ratio=3)  # Increased ratio for models to show full responses
        )
        
        self.live = Live(self.layout, console=self.console, refresh_per_second=10)
        self.live.start()
        self._update_display()
        
        # Start keyboard listener for expand/collapse
        if self.enable_keyboard:
            self._start_keyboard_listener()
    
    def stop(self):
        """Stop live display and keyboard listener."""
        # Stop keyboard listener
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        
        if self.live:
            self.live.stop()
            self.live = None
    
    def create_tool_panel(self, 
                         tool_name: str, 
                         command_name: Optional[str] = None,
                         target: Optional[str] = None) -> str:
        """Create a tool execution panel.
        
        Args:
            tool_name: Tool name
            command_name: Optional command name
            target: Optional target
            
        Returns:
            Panel ID
        """
        panel_id = f"{tool_name}:{command_name}" if command_name else tool_name
        self.tool_panels[panel_id] = ToolExecutionPanel(
            tool_name=tool_name,
            command_name=command_name,
            target=target
        )
        self._update_display()
        return panel_id
    
    def update_tool_output(self, panel_id: str, line: str):
        """Update tool output with a new line.
        
        Args:
            panel_id: Panel ID
            line: Output line
        """
        if panel_id in self.tool_panels:
            self.tool_panels[panel_id].add_output(line)
            self._update_display()
    
    def update_tool_status(self, panel_id: str, status: str):
        """Update tool status.
        
        Args:
            panel_id: Panel ID
            status: Status message
        """
        if panel_id in self.tool_panels:
            self.tool_panels[panel_id].update_status(status)
            self._update_display()
    
    def complete_tool_panel(self, panel_id: str, success: bool = True):
        """Mark tool panel as complete.
        
        Args:
            panel_id: Panel ID
            success: Whether execution was successful
        """
        if panel_id in self.tool_panels:
            status = "✓ Completed" if success else "✗ Failed"
            self.tool_panels[panel_id].update_status(status)
            self._update_display()
    
    def create_model_panel(self, model_name: str) -> str:
        """Create a model response panel.
        
        Args:
            model_name: Model name
            
        Returns:
            Panel ID
        """
        panel_id = model_name
        # Only create if doesn't exist
        if panel_id not in self.model_panels:
            self.model_panels[panel_id] = ModelResponsePanel(model_name=model_name)
        self._update_display()
        return panel_id
    
    def toggle_model_panel(self, panel_id: str):
        """Toggle expand/collapse state of a model panel.
        
        Args:
            panel_id: Panel ID
        """
        if panel_id in self.model_panels:
            self.model_panels[panel_id].toggle_expand()
            self._update_display()
    
    def _start_keyboard_listener(self):
        """Start keyboard listener for expand/collapse."""
        def handle_key(key: str):
            """Handle keyboard input."""
            key_lower = key.lower()
            
            # Toggle all model panels
            if key_lower == 'e':  # Expand
                for panel_id in self.model_panels:
                    panel = self.model_panels[panel_id]
                    if not panel.expanded:
                        panel.toggle_expand()
                        self._update_display()
            elif key_lower == 'c':  # Collapse
                for panel_id in self.model_panels:
                    panel = self.model_panels[panel_id]
                    if panel.expanded:
                        panel.toggle_expand()
                        self._update_display()
            elif key_lower == 't':  # Toggle
                # Toggle the first model panel (or all if multiple)
                if self.model_panels:
                    # Toggle all panels
                    for panel_id in self.model_panels:
                        self.model_panels[panel_id].toggle_expand()
                    self._update_display()
        
        self.keyboard_listener = KeyboardListener(on_key_press=handle_key)
        self.keyboard_listener.start()
    
    def stream_model_response(self, panel_id: str, chunk: str):
        """Stream model response chunk.
        
        Args:
            panel_id: Panel ID
            chunk: Response chunk
        """
        if panel_id in self.model_panels:
            self.model_panels[panel_id].add_chunk(chunk)
            self._update_display()
    
    def update_model_status(self, panel_id: str, status: str):
        """Update model status.
        
        Args:
            panel_id: Panel ID
            status: Status message
        """
        if panel_id in self.model_panels:
            self.model_panels[panel_id].update_status(status)
            self._update_display()
    
    def complete_model_panel(self, panel_id: str):
        """Mark model panel as complete.
        
        Args:
            panel_id: Panel ID
        """
        if panel_id in self.model_panels:
            self.model_panels[panel_id].update_status("✓ Complete")
            self._update_display()
    
    def update_progress(self, step: str):
        """Update progress step.
        
        Args:
            step: Current step name
        """
        self.progress_panel.update_step(step)
        self._update_display()
    
    def complete_progress_step(self, step: str):
        """Mark progress step as complete.
        
        Args:
            step: Step name
        """
        self.progress_panel.complete_step(step)
        self._update_display()
    
    def set_total_steps(self, total: int):
        """Set total number of progress steps.
        
        Args:
            total: Total steps
        """
        self.progress_panel.set_total_steps(total)
        self._update_display()
    
    def _update_display(self):
        """Update the live display."""
        if not self.live or not self.layout:
            return
        
        # Build tools section
        tool_panels_list = [panel.render() for panel in self.tool_panels.values()]
        if tool_panels_list:
            from rich.console import Group as RichGroup
            tools_content = RichGroup(*tool_panels_list)
        else:
            tools_content = Panel("[dim]No tools running...[/dim]", title="[cyan]Tools[/cyan]")
        
        # Build models section
        model_panels_list = [panel.render() for panel in self.model_panels.values()]
        if model_panels_list:
            from rich.console import Group as RichGroup
            models_content = RichGroup(*model_panels_list)
        else:
            models_content = Panel("[dim]No models active...[/dim]", title="[blue]Models[/blue]")
        
        # Update layout
        self.layout["progress"].update(self.progress_panel.render())
        self.layout["tools"].update(tools_content)
        self.layout["models"].update(models_content)
    
    def clear(self):
        """Clear all panels."""
        self.tool_panels.clear()
        self.model_panels.clear()
        self.progress_panel = ProgressPanel()
        self._update_display()
    
    def get_tool_callback(self, panel_id: str) -> Callable[[str], None]:
        """Get a callback function for tool output streaming.
        
        Args:
            panel_id: Panel ID
            
        Returns:
            Callback function
        """
        def callback(line: str):
            self.update_tool_output(panel_id, line)
        return callback
    
    def get_model_callback(self, panel_id: str) -> Callable[[str], None]:
        """Get a callback function for model response streaming.
        
        Args:
            panel_id: Panel ID
            
        Returns:
            Callback function
        """
        def callback(chunk: str):
            self.stream_model_response(panel_id, chunk)
        return callback
