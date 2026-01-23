"""AutoGen multi-agent setup."""

import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from models.generic_ollama_agent import GenericOllamaAgent
# FunctionGemma removed - using tool calling registry instead
from models.tool_calling_registry import get_tool_calling_registry
# DeepSeekAgent removed - using GenericOllamaAgent instead
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
        self.model_name = config.get('model', '') or ''
        self.fallback_model = config.get('fallback_model', '') or ''
        self.tool_categories = config.get('tool_categories', [])
        
        # Resolve model name with flexible support (aliases, env vars, dynamic resolution)
        resolved_model = self._resolve_model_name(self.model_name, self.fallback_model)
        
        # Initialize model agent based on resolved model
        # Check for special agent types first
        if resolved_model.startswith("deepseek-r1") or resolved_model.startswith("deepseek_r1"):
            # DeepSeekAgent removed - using GenericOllamaAgent instead
            self.model_agent = GenericOllamaAgent(
                model_name=resolved_model,
                prompt_template="roles/analyzer.jinja2"
            )
        elif resolved_model == "json_tool_calling" or self.model_name == "functiongemma":
            # Tool calling registry (legacy functiongemma support)
            tool_registry = get_tool_calling_registry()
            self.model_agent = tool_registry.get_model("json_tool_calling")
        else:
            # Use GenericOllamaAgent for any Ollama model (flexible)
            self.model_agent = GenericOllamaAgent(
                model_name=resolved_model,
                prompt_template="autogen_recon.jinja2"
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
        
        # Reference to coordinator (set by coordinator after initialization)
        self.coordinator: Optional['AutoGenCoordinator'] = None
    
    def _resolve_model_name(self, model_name: str, fallback_model: Optional[str] = None) -> str:
        """Resolve model name to actual Ollama model name.
        
        Supports:
        - Direct Ollama model names (e.g., "mistral:latest", "qwen2-pentest-v2:latest")
        - Aliases (e.g., "mistral" -> "mistral:latest", "deepseek_r1" -> "deepseek-r1:latest")
        - Environment variable overrides (e.g., RECON_AGENT_MODEL)
        - Fallback to fallback_model if primary not available
        - Empty string -> uses default from models.yaml
        
        Args:
            model_name: Model name from config (can be alias, full name, or empty)
            fallback_model: Fallback model name if primary not available
            
        Returns:
            Resolved Ollama model name
        """
        import os
        from utils.ollama_helper import get_model_names, check_model_exists
        
        # Check for environment variable override (e.g., RECON_AGENT_MODEL)
        agent_env_key = f"{self.name.upper().replace(' ', '_')}_MODEL"
        env_model = os.getenv(agent_env_key)
        if env_model:
            if check_model_exists(env_model):
                return env_model
            # Try to resolve as alias
            resolved = self._resolve_alias(env_model)
            if check_model_exists(resolved):
                return resolved
        
        # If model_name is empty, try to get default from models.yaml
        if not model_name or model_name.strip() == "":
            try:
                from config import load_config
                config = load_config()
                defaults = config.get('models', {}).get('defaults', {})
                # Try to get default based on agent role
                if "recon" in self.name.lower():
                    model_name = defaults.get('analysis_model', 'mistral:latest')
                elif "exploit" in self.name.lower():
                    model_name = defaults.get('synthesis_model', 'deepseek-r1:latest')
                else:
                    model_name = defaults.get('analysis_model', 'mistral:latest')
            except Exception:
                model_name = "mistral:latest"  # Ultimate fallback
        
        # Check if it's already a full model name (contains :)
        if ":" in model_name:
            # Direct model name, check if exists
            if check_model_exists(model_name):
                return model_name
            # Try fallback
            if fallback_model:
                resolved_fallback = self._resolve_alias(fallback_model)
                if check_model_exists(resolved_fallback):
                    return resolved_fallback
        
        # Try to resolve as alias
        resolved = self._resolve_alias(model_name)
        if check_model_exists(resolved):
            return resolved
        
        # Try fallback
        if fallback_model:
            resolved_fallback = self._resolve_alias(fallback_model)
            if check_model_exists(resolved_fallback):
                return resolved_fallback
        
        # Last resort: try to find similar model
        available_models = get_model_names()
        if available_models:
            # Try to find model that starts with the alias
            for available in available_models:
                if model_name.lower() in available.lower() or available.lower().startswith(model_name.lower()):
                    return available
            # Use first available model
            return available_models[0]
        
        # Ultimate fallback
        return "mistral:latest"
    
    def _resolve_alias(self, model_name: str) -> str:
        """Resolve model alias to full model name.
        
        Args:
            model_name: Model name or alias
            
        Returns:
            Resolved model name
        """
        # Load aliases from models.yaml if available
        alias_map = {
            "mistral": "mistral:latest",
            "qwen3": "mistral:latest",
            "llama3.1": "llama3.1:8b",
            "llama3": "llama3.1:8b",
            "deepseek_r1": "deepseek-r1:latest",
            "deepseek": "deepseek-r1:latest",
            "qwen2": "qwen2.5:latest",
            "qwen2_pentest": "qwen2-pentest-v2:latest",
        }
        
        # Try to load from models.yaml
        try:
            from config import load_config
            config = load_config()
            yaml_aliases = config.get('models', {}).get('aliases', {})
            alias_map.update(yaml_aliases)
        except Exception:
            pass  # Use default aliases
        
        # If already contains :, return as is
        if ":" in model_name:
            return model_name
        
        # Check alias map
        if model_name.lower() in alias_map:
            return alias_map[model_name.lower()]
        
        # If not in alias map, try adding :latest
        return f"{model_name}:latest"
    
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
    
    def __init__(self, config_path: Optional[Path] = None, model_overrides: Optional[Dict[str, str]] = None):
        """Initialize AutoGen coordinator.
        
        Args:
            config_path: Path to AutoGen config file
            model_overrides: Optional dict mapping agent_name -> model_name to override
                           config file model assignments. Enables runtime multi-agent
                           multi-model selection from main.py.
                           Example: {"recon_agent": "qwen2-pentest-v2:latest", 
                                    "exploit_agent": "deepseek-r1:latest"}
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "autogen_config.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Store model overrides for reference
        self.model_overrides = model_overrides or {}
        
        # Initialize agents with optional model overrides
        self.agents: Dict[str, AutoGenAgent] = {}
        for agent_name, agent_config in self.config['agents'].items():
            # Apply model override if provided
            if agent_name in self.model_overrides:
                agent_config = agent_config.copy()  # Don't mutate original config
                agent_config['model'] = self.model_overrides[agent_name]
            
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