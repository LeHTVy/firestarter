"""Multi-Agent Model Selection Utility.

Provides interactive UI for assigning Ollama models to different agents.
"""

from typing import Dict, List, Tuple, Optional, Callable
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


class MultiAgentModelSelector:
    """Interactive multi-agent model selection.
    
    Allows users to assign different Ollama models to different agents.
    One model can serve multiple agent roles.
    """
    
    # Define agent roles with (agent_key, display_name, description)
    AGENT_ROLES: List[Tuple[str, str, str]] = [
        ("recon_agent", "Recon Agent", "Network scanning, OSINT, DNS"),
        ("exploit_agent", "Exploit Agent", "Exploit research, CVE analysis"),
        ("analysis_agent", "Analysis Agent", "Result analysis, reporting"),
        ("results_qa_agent", "Results Q&A", "Query tool results"),
    ]
    
    # Recommended models for each agent role (for highlighting)
    RECOMMENDED_MODELS: Dict[str, List[str]] = {
        "recon_agent": ["qwen2-pentest", "mistral"],
        "exploit_agent": ["deepseek", "qwen2-pentest"],
        "analysis_agent": ["deepseek", "mistral"],
        "results_qa_agent": ["mistral", "llama"],
    }
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize model selector.
        
        Args:
            console: Rich console for output. Creates new if not provided.
        """
        self.console = console or Console()
    
    def _is_recommended_for_agent(self, model_name: str, agent_key: str) -> bool:
        """Check if a model is recommended for a specific agent.
        
        Args:
            model_name: Model name to check
            agent_key: Agent key (e.g., "recon_agent")
            
        Returns:
            True if model is recommended for this agent
        """
        recommended = self.RECOMMENDED_MODELS.get(agent_key, [])
        model_lower = model_name.lower()
        return any(rec in model_lower for rec in recommended)
    
    def select_models(
        self,
        available_models: List[str],
        prompt_func: Callable[[str, Optional[str]], str]
    ) -> Dict[str, str]:
        """Interactive model selection for each agent.
        
        Args:
            available_models: List of available Ollama model names
            prompt_func: Function to get user input (prompt_text, default) -> response
            
        Returns:
            Dict mapping agent_key -> model_name
        """
        if not available_models:
            self.console.print("[yellow]⚠️  No models available. Using defaults.[/yellow]")
            return {agent[0]: "mistral:latest" for agent in self.AGENT_ROLES}
        
        # Show header
        self.console.print("\n[bold cyan]Multi-Agent Model Configuration[/bold cyan]")
        self.console.print("[dim]Assign different models to different agents. Press Enter to use same model as previous.[/dim]\n")
        
        # Show available models with numbers
        self.console.print("[bold]Available Models:[/bold]")
        for i, model_name in enumerate(available_models, 1):
            # Check if it's a generally recommended model
            is_recommended = any(keyword in model_name.lower() for keyword in ["pentest", "qwen2", "deepseek"])
            marker = " ⭐" if is_recommended else ""
            self.console.print(f"  {i}. {model_name}{marker}")
        
        self.console.print()
        
        # Collect model assignments
        assignments: Dict[str, str] = {}
        previous_model: Optional[str] = None
        
        for agent_key, display_name, description in self.AGENT_ROLES:
            # Build prompt with recommendation hints
            if previous_model:
                default_hint = f"Enter=same as {previous_model.split(':')[0]}"
            else:
                default_hint = "default: 1"
            
            # Show agent-specific recommendations
            recommended_hint = ""
            for i, model in enumerate(available_models, 1):
                if self._is_recommended_for_agent(model, agent_key):
                    if recommended_hint:
                        recommended_hint += f", {i}"
                    else:
                        recommended_hint = f"recommended: {i}"
            
            # Build full prompt
            prompt_parts = [f"[bold]{display_name}[/bold] [dim]({description})[/dim]"]
            hint_parts = [default_hint]
            if recommended_hint:
                hint_parts.append(recommended_hint)
            
            prompt_text = f"{prompt_parts[0]} [{', '.join(hint_parts)}]"
            
            # Get user input
            try:
                choice = prompt_func(prompt_text, "")
                choice = choice.strip()
            except (KeyboardInterrupt, EOFError):
                # Use previous or first model on interrupt
                choice = ""
            
            # Process choice
            if choice == "" and previous_model:
                # Use previous model
                selected_model = previous_model
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(available_models):
                    selected_model = available_models[idx]
                else:
                    # Invalid number, use previous or first
                    selected_model = previous_model if previous_model else available_models[0]
                    self.console.print(f"  [yellow]⚠️  Invalid choice, using {selected_model}[/yellow]")
            elif choice == "" and not previous_model:
                # First agent, no previous - use first model
                selected_model = available_models[0]
            else:
                # Try to match by name (partial match)
                matched = None
                for model in available_models:
                    if choice.lower() in model.lower():
                        matched = model
                        break
                if matched:
                    selected_model = matched
                else:
                    # No match, use previous or first
                    selected_model = previous_model if previous_model else available_models[0]
                    self.console.print(f"  [yellow]⚠️  Model not found, using {selected_model}[/yellow]")
            
            assignments[agent_key] = selected_model
            previous_model = selected_model
        
        # Display summary
        self.display_summary(assignments)
        
        return assignments
    
    def display_summary(self, assignments: Dict[str, str]) -> None:
        """Display model assignment summary with shared model indicators.
        
        Args:
            assignments: Dict mapping agent_key -> model_name
        """
        self.console.print()
        
        # Count model usage to identify shared models
        model_usage: Dict[str, List[str]] = {}
        for agent_key, model_name in assignments.items():
            if model_name not in model_usage:
                model_usage[model_name] = []
            model_usage[model_name].append(agent_key)
        
        # Create summary table
        table = Table(title="Agent-Model Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Agent", style="bold")
        table.add_column("Model", style="green")
        table.add_column("Status", style="dim")
        
        for agent_key, display_name, _ in self.AGENT_ROLES:
            model_name = assignments.get(agent_key, "unknown")
            
            # Check if model is shared with other agents
            shared_count = len(model_usage.get(model_name, []))
            if shared_count > 1:
                status = f"(shared by {shared_count} agents)"
            else:
                status = ""
            
            table.add_row(display_name, model_name, status)
        
        self.console.print(table)
        self.console.print()
    
    def quick_select_same_model(self, model_name: str) -> Dict[str, str]:
        """Quick assignment of same model to all agents.
        
        Args:
            model_name: Model name to assign to all agents
            
        Returns:
            Dict mapping all agents to the same model
        """
        return {agent[0]: model_name for agent in self.AGENT_ROLES}
    
    def get_default_assignments(self) -> Dict[str, str]:
        """Get default model assignments.
        
        Returns:
            Dict with default model for each agent
        """
        return {
            "recon_agent": "mistral:latest",
            "exploit_agent": "deepseek-r1:latest",
            "analysis_agent": "mistral:latest",
            "results_qa_agent": "mistral:latest",
        }


def get_model_selector(console: Optional[Console] = None) -> MultiAgentModelSelector:
    """Get a model selector instance.
    
    Args:
        console: Optional Rich console
        
    Returns:
        MultiAgentModelSelector instance
    """
    return MultiAgentModelSelector(console=console)
