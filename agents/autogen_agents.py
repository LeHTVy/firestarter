"""AutoGen multi-agent setup."""

import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from models.generic_ollama_agent import GenericOllamaAgent
# FunctionGemma removed - using tool calling registry instead
from models.tool_calling_registry import get_tool_calling_registry
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
            # FunctionGemma removed - use tool calling registry instead
            tool_registry = get_tool_calling_registry()
            self.model_agent = tool_registry.get_model("json_tool_calling")
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
        # Check if model agent has call_with_tools method (tool calling agents)
        if hasattr(self.model_agent, 'call_with_tools'):
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
    """Coordinator for AutoGen multi-agent system with agent-to-agent communication."""
    
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
            agent = AutoGenAgent(agent_config)
            agent.coordinator = self  # Give agents reference to coordinator for communication
            self.agents[agent_name] = agent
        
        # Shared message board for agent-to-agent communication
        self.message_board: List[Dict[str, Any]] = []  # [{from_agent, to_agent, message, data, timestamp}]
        
        # Shared context (findings, results) that all agents can access
        self.shared_context: Dict[str, Any] = {
            "findings": {},  # Findings from each agent
            "results": {},   # Tool results
            "subdomains": [],
            "open_ports": [],
            "vulnerabilities": [],
            "technologies": []
        }
    
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
    
    def send_message(self, from_agent: str, to_agent: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Send message from one agent to another.
        
        Args:
            from_agent: Sender agent name
            to_agent: Receiver agent name
            message: Message content
            data: Optional structured data to share
        """
        from datetime import datetime
        
        message_entry = {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self.message_board.append(message_entry)
        
        # Keep only last 100 messages to prevent memory bloat
        if len(self.message_board) > 100:
            self.message_board = self.message_board[-100:]
    
    def get_messages_for_agent(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all messages for a specific agent.
        
        Args:
            agent_name: Agent name
            
        Returns:
            List of messages (both sent to this agent and broadcast messages)
        """
        messages = []
        for msg in self.message_board:
            # Messages sent to this agent
            if msg["to_agent"] == agent_name:
                messages.append(msg)
            # Broadcast messages (to_agent is None or "all")
            elif msg["to_agent"] in [None, "all", ""]:
                messages.append(msg)
        
        return messages
    
    def update_shared_context(self, agent_name: str, findings: Dict[str, Any]):
        """Update shared context with findings from an agent.
        
        Args:
            agent_name: Agent name that found the data
            findings: Findings dictionary (subdomains, ports, vulnerabilities, etc.)
        """
        # Merge findings into shared context
        if "subdomains" in findings:
            self.shared_context["subdomains"].extend(findings["subdomains"])
            # Remove duplicates
            self.shared_context["subdomains"] = list(set(self.shared_context["subdomains"]))
        
        if "open_ports" in findings:
            self.shared_context["open_ports"].extend(findings["open_ports"])
        
        if "vulnerabilities" in findings:
            self.shared_context["vulnerabilities"].extend(findings["vulnerabilities"])
        
        if "technologies" in findings:
            self.shared_context["technologies"].extend(findings["technologies"])
        
        # Store agent-specific findings
        self.shared_context["findings"][agent_name] = findings
    
    def get_shared_context(self) -> Dict[str, Any]:
        """Get current shared context.
        
        Returns:
            Shared context dictionary
        """
        return self.shared_context.copy()
    
    def request_agent_collaboration(self, 
                                   requesting_agent: str,
                                   target_agent: str,
                                   request: str,
                                   context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Request another agent to perform a task.
        
        Args:
            requesting_agent: Agent making the request
            target_agent: Agent to perform the task
            request: Task description
            context: Additional context for the task
            
        Returns:
            Result from the target agent
        """
        # Send message to target agent
        self.send_message(
            from_agent=requesting_agent,
            to_agent=target_agent,
            message=f"Request from {requesting_agent}: {request}",
            data=context or {}
        )
        
        # Execute task with target agent
        agent = self.get_agent(target_agent)
        if not agent:
            return {
                "success": False,
                "error": f"Agent '{target_agent}' not found"
            }
        
        # Include shared context in the request
        task_context = {
            "requesting_agent": requesting_agent,
            "shared_context": self.get_shared_context(),
            "messages": self.get_messages_for_agent(target_agent)
        }
        if context:
            task_context.update(context)
        
        result = agent.execute(request, task_context)
        
        # If result contains findings, update shared context
        if result.get("success") and result.get("findings"):
            self.update_shared_context(target_agent, result["findings"])
        
        return result