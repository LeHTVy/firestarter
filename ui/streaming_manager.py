"""Streaming manager for coordinating live updates."""

from typing import Dict, Optional, Callable, Any
from rich.console import Console, Group
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel

from ui.panels import ToolExecutionPanel, ModelResponsePanel, ProgressPanel
from ui.components import TargetInfoCard, FindingCard, AnalysisCard
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
        self.info_panels: List[Panel] = []  # Store static info panels
        self.progress_panel = ProgressPanel()
        self.live: Optional[Live] = None
        self.layout: Optional[Layout] = None
        self.keyboard_listener: Optional[KeyboardListener] = None
        self.enable_keyboard = enable_keyboard
    
    def start(self):
        """Start live display and keyboard listener."""
        if self.live is None:
            self.live = Live(Panel("Initializing..."), console=self.console, refresh_per_second=10)
            self.live.start()
        
        self._update_display()
        
        if self.enable_keyboard and not self.keyboard_listener:
            self._start_keyboard_listener()
    
    def stop(self):
        """Stop live display and keyboard listener."""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        
        if self.live:
            self.live.stop()
            self.live = None
    
    def create_tool_panel(self, 
                         tool_name: str, 
                         command_name: Optional[str] = None,
                         target: Optional[str] = None,
                         parameters: Optional[Dict[str, Any]] = None) -> str:
        """Create a tool execution panel.
        
        Args:
            tool_name: Tool name
            command_name: Optional command name
            target: Optional target
            parameters: Optional parameters used for tool execution
            
        Returns:
            Panel ID
        """
        panel_id = f"{tool_name}:{command_name}" if command_name else tool_name
        self.tool_panels[panel_id] = ToolExecutionPanel(
            tool_name=tool_name,
            command_name=command_name,
            target=target,
            parameters=parameters
        )
        self._update_display()
        return panel_id
    
    def set_tool_result(self, panel_id: str, result: Dict[str, Any]):
        """Set final result for a tool panel.
        
        Args:
            panel_id: Panel ID
            result: Tool execution result dict
        """
        if panel_id in self.tool_panels:
            self.tool_panels[panel_id].set_result(result)
            self._update_display()
    
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
                if self.model_panels:
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
        # Only update if step actually changed to avoid excessive rendering
        if self.progress_panel.current_step != step:
            self.progress_panel.update_step(step)
            self._update_display()
    
    def complete_progress_step(self, step: str):
        """Mark progress step as complete.
        
        Args:
            step: Step name
        """
        self.progress_panel.complete_step(step)
        
        if step == "Workflow completed":
            # Force all steps to be completed visually
            self.progress_panel.completed_steps = [f"Step {i}" for i in range(self.progress_panel.total_steps)]
            self.progress_panel.current_step = "Completed"
            
        self._update_display()
    
    def set_total_steps(self, total: int):
        """Set total number of progress steps.
        
        Args:
            total: Total steps
        """
        self.progress_panel.set_total_steps(total)
        self._update_display()

    def show_target_info(self, domain: str, company_info: Dict[str, Any] = None):
        """Show target information card.
        
        Args:
            domain: Target domain
            company_info: Optional company info
        """
        card = TargetInfoCard(self.console)
        panel = card.render(domain, company_info)
        self.info_panels.append(panel)
        self._update_display()
        
    def show_finding(self, finding_type: str, data: Dict[str, Any], severity: str = None):
        """Show finding card.
        
        Args:
            finding_type: Type of finding
            data: Finding data
            severity: Severity level
        """
        card = FindingCard(self.console)
        panel = card.render(finding_type, data, severity)
        self.info_panels.append(panel)
        self._update_display()
        
    def show_analysis(self, analysis: Dict[str, Any]):
        """Show analysis results card.
        
        Args:
            analysis: Analysis data
        """
        card = AnalysisCard(self.console)
        panel = card.render(analysis)
        self.info_panels.append(panel)
        self._update_display()
    
    def _update_display(self):
        """Update the live display."""
        if not self.live:
            return
        
        renderables = []
        
        def get_recent(panels, count=3):
            return panels[-count:] if len(panels) > count else panels
        
        if self.info_panels:
            renderables.append(Group(*self.info_panels))
        
        renderables.append(self.progress_panel.render())
        
        active_tools = []
        completed_tools = []
        
        for panel_id, panel in self.tool_panels.items():
            if hasattr(panel, 'status') and ("Completed" in panel.status or "Failed" in panel.status or "Detailed" in panel.status):
                 completed_tools.append(panel)
            else:
                 active_tools.append(panel)

        if active_tools:
            active_renderables = [p.render() for p in active_tools]
            renderables.append(Group(*active_renderables))
        if completed_tools:
            from rich.table import Table
            from rich import box
            
            summary_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
            summary_table.add_column("Status", style="bold")
            summary_table.add_column("Tool", style="cyan")
            summary_table.add_column("Result", style="dim")
            
            for p in completed_tools[-5:]: 
                status_icon = "✅" if "Completed" in p.status else "❌"
                summary_table.add_row(status_icon, p.tool_name, p.status)

            renderables.append(Panel(
                summary_table, 
                title=f"[green]Completed Tools ({len(completed_tools)})[/green]",
                expand=False
            ))
            
        if not active_tools and not completed_tools:
            renderables.append(Panel("[dim]No tools running...[/dim]", title="[cyan]Tools[/cyan]"))
        
        model_panels_list = [panel.render() for panel in self.model_panels.values()]
        if model_panels_list:
            renderables.append(Group(*model_panels_list))
        else:
            renderables.append(Panel("[dim]No models active...[/dim]", title="[blue]Models[/blue]"))
            
        self.live.update(Group(*renderables))
    
    def clear(self):
        """Clear all panels."""
        self.tool_panels.clear()
        self.model_panels.clear()
        self.info_panels.clear()
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


# Global instance
_streaming_manager: Optional[StreamingManager] = None


def get_streaming_manager(console: Optional[Console] = None) -> StreamingManager:
    """Get global streaming manager instance."""
    global _streaming_manager
    if _streaming_manager is None:
        _streaming_manager = StreamingManager(console)
    return _streaming_manager
