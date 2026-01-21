"""AutoGen multi-agent setup."""

import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from models.generic_ollama_agent import GenericOllamaAgent
from models.functiongemma_agent import FunctionGemmaAgent
from models.deepseek_agent import DeepSeekAgent
from tools.registry import get_registry
from tools.executor import get_executor


class AutoGenAgent:
    """Base AutoGen agent class."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize agent.
        
        Args:
            config: Agent configuration
        """
        self.config = config
        self.name = config['name']
        self.description = config['description']
        self.model_name = config['model']
        self.tool_categories = config.get('tool_categories', [])
        
        # Initialize model agent
        if self.model_name == "qwen3" or self.model_name == "mistral":
            # Use Mistral for general analysis (replacing Qwen3)
            self.model_agent = GenericOllamaAgent(
                model_name="mistral:latest",
                prompt_template="qwen3_system.jinja2"
            )
        elif self.model_name == "functiongemma":
            self.model_agent = FunctionGemmaAgent()
        elif self.model_name == "deepseek_r1":
            self.model_agent = DeepSeekAgent()
        else:
            # Default to Mistral
            self.model_agent = GenericOllamaAgent(
                model_name="mistral:latest",
                prompt_template="qwen3_system.jinja2"
            )
        
        # Load prompt template
        template_dir = Path(__file__).parent.parent / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        prompt_file = config.get('system_prompt_file', '').split('/')[-1]
        self.prompt_template = self.env.get_template(prompt_file) if prompt_file else None
        
        # Get tools for this agent
        self.registry = get_registry()
        self.executor = get_executor()
        self.available_tools = self.registry.get_tools_for_agent(self.name.lower().replace(' ', '_'))
    
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute agent task.
        
        Args:
            task: Task description
            context: Additional context
            
        Returns:
            Execution result
        """
        # Build prompt
        if self.prompt_template:
            prompt = self.prompt_template.render(
                target=context.get('target') if context else None,
                task=task,
                previous_results=context.get('previous_results') if context else None
            )
        else:
            prompt = task
        
        # Execute using model agent
        if isinstance(self.model_agent, FunctionGemmaAgent):
            result = self.model_agent.call_with_tools(
                user_prompt=prompt,
                agent=self.name.lower().replace(' ', '_'),
                session_id=context.get('session_id') if context else None
            )
        else:
            # For other agents, use appropriate method
            result = {
                "success": True,
                "response": f"Agent {self.name} processing: {task}",
                "agent": self.name
            }
        
        return result


class AutoGenCoordinator:
    """Coordinator for AutoGen multi-agent system."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize AutoGen coordinator.
        
        Args:
            config_path: Path to AutoGen config file
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "autogen_config.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize agents
        self.agents: Dict[str, AutoGenAgent] = {}
        for agent_name, agent_config in self.config['agents'].items():
            self.agents[agent_name] = AutoGenAgent(agent_config)
    
    def get_agent(self, agent_name: str) -> Optional[AutoGenAgent]:
        """Get agent by name.
        
        Args:
            agent_name: Agent name
            
        Returns:
            Agent instance or None
        """
        return self.agents.get(agent_name)
    
    def route_task(self, task: str, task_type: str) -> Optional[str]:
        """Route task to appropriate agent.
        
        Args:
            task: Task description
            task_type: Task type (recon, exploitation, analysis)
            
        Returns:
            Agent name or None
        """
        if task_type == "recon":
            return "recon_agent"
        elif task_type == "exploitation":
            return "exploit_agent"
        elif task_type == "analysis":
            return "analysis_agent"
        return None
    
    def execute_with_agent(self,
                           agent_name: str,
                           task: str,
                           context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute task with specific agent.
        
        Args:
            agent_name: Agent name
            task: Task description
            context: Additional context
            
        Returns:
            Execution result
        """
        agent = self.get_agent(agent_name)
        if not agent:
            return {
                "success": False,
                "error": f"Agent '{agent_name}' not found"
            }
        
        return agent.execute(task, context)
